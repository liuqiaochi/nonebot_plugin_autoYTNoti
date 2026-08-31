#!/usr/bin/env python3
"""
老肥工具箱 - 视频下载后端服务
支持 YouTube、Bilibili 等平台，部署到你的云服务器，前端页面通过 API 调用 yt-dlp 下载视频。

使用方式：
  1. pip install -r requirements.txt
  2. 确保已安装 yt-dlp: pip install yt-dlp
  3. python app.py
  4. 前端填入 http://你的服务器IP:5001

支持平台：YouTube、Bilibili（BV/av号）、b23.tv 短链等
"""

import os
import json
import uuid
import subprocess
import threading
import time
from pathlib import Path
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS

# 清除可能从外壳/IDE 注入的 HTTP(S) 代理，避免 yt-dlp 子进程继承后连 YouTube 被截断
# (报错 SSL: UNEXPECTED_EOF_WHILE_READING / 502 Bad Gateway)。本机直连 YouTube 是通的
# (历史多次下载成功)。若你的网络必须走代理才能上 YouTube，设 YT_PROXY=http://host:port 即可。
for _p in ('http_proxy', 'https_proxy', 'HTTP_PROXY', 'HTTPS_PROXY', 'all_proxy', 'ALL_PROXY'):
    os.environ.pop(_p, None)

app = Flask(__name__)
CORS(app)

# ── 配置 ──
DOWNLOAD_DIR = Path(os.environ.get('DOWNLOAD_DIR', './downloads'))
DOWNLOAD_DIR.mkdir(exist_ok=True)
MAX_FILE_AGE = 3600  # 文件保留 1 小时
PORT = int(os.environ.get('PORT', 5001))
COOKIES_FILE = Path(__file__).parent / 'cookies.txt'

# ── YouTube 绕过 bot 检测参数 ──
# player 客户端自动选择规则（详见 _resolve_player_client）：
#   - 设了 BGUTIL_BASEURL（PO Token）→ tv 客户端：免登录、免 deno，靠 PO Token 过 bot 检测，
#     返回直链 mp4 格式（最省事的常驻方案）；
#   - 设了 cookies（登录态）→ web 客户端：唯一【既支持 cookies 又返回直链格式】的客户端，
#     ⚠️ 但必须安装 deno 运行时（JS 引擎），否则报 "page needs to be reloaded"；
#   - 都没有 → tv（大概率被 bot 检测挡，仅作兜底）。
# ⚠️ 重要坑：ios / tv / android 客户端【都不支持 cookies】。一旦配了 cookies，
#   这些客户端会被 yt-dlp 静默跳过、回退到默认 web 客户端（需 deno），
#   否则只剩 storyboard 图片 → 报 "Requested format is not available"。
#   而 web_safari 虽支持 cookies，但 YouTube 对其强制 SABR 流，分片下载会 403。
#   所以：带 cookies 用 web(+deno)，不带 cookies 用 tv(+BGUTIL)。
# 手动覆盖：YT_PLAYER_CLIENT=web|web_safari|tv|android|ios|...
# 导出 cookies：
#   YT_COOKIES=/path/cookies.txt               Netscape 格式 cookies 文件
#   YT_COOKIES_BROWSER=chrome|safari|firefox   直接从本机浏览器读取（桌面最省事）
# bgutil PO Token Provider（cookie-free 方案）：先 node build/main.js，再设 BGUTIL_BASEURL=http://127.0.0.1:4416
YT_PLAYER_CLIENT = os.environ.get('YT_PLAYER_CLIENT', '').strip()  # 留空=自动选择
YT_COOKIES = os.environ.get('YT_COOKIES', '').strip()
YT_COOKIES_BROWSER = os.environ.get('YT_COOKIES_BROWSER', '').strip()
BGUTIL_BASEURL = os.environ.get('BGUTIL_BASEURL', '').strip()


def _resolve_player_client():
    """自动选择 player 客户端（见上方注释）：
    - 显式设置 YT_PLAYER_CLIENT 时优先；
    - 有 BGUTIL_BASEURL（PO Token）时：
        * 同时有 cookies → 用 web 客户端（web + PoToken 可解锁 1080p~4K 全画质）；
        * 无 cookies   → 用 tv 客户端（tv + PoToken 免登录免 deno，画质上限 1080p）；
    - 仅有 cookies（无 PoToken）→ web 客户端（但 YouTube 只会给到 360p，需补 PoToken 才高清）；
    - 都没有 → tv（兜底，可能被 bot 检测挡）。
    """
    if YT_PLAYER_CLIENT:
        return YT_PLAYER_CLIENT
    if BGUTIL_BASEURL:
        if YT_COOKIES or YT_COOKIES_BROWSER:
            # web + PoToken + cookies 解锁 1080p H.264（已验证此组合稳定出 1080p）。
            # 注意：曾试过 web,tv 回退，但 tv 客户端现被 YouTube bot 检测挡
            # (报 "page needs to be reloaded")，且逗号客户端列表会吞掉 getpot 参数，
            # 故回退为单一 web。INNERTUBE_CONTEXT 等瞬时抽风由 do_download 应用层
            # 重试循环兜底（重新跑 web 通常即成功）。
            return 'web'
        return 'tv'
    if YT_COOKIES or YT_COOKIES_BROWSER:
        return 'web'
    return 'tv'


def _yt_common_args():
    """YouTube 专用 yt-dlp 参数：指定 player 客户端 + 可选 cookies / PO Token provider。"""
    yt_args = f'player_client={_resolve_player_client()}'
    if BGUTIL_BASEURL:
        # 实测关键：extractor-args 内多个选项必须用「&」分隔（不是 ;）！用 ; 会让
        # getpot_bgutil_baseurl 被整段忽略 → web 客户端拿不到 PoToken → YouTube 限到 360p。
        # 当初把 & 误改成 ; 正是 360p 回归的根因。player_client 用单一 web 即可
        # （避免逗号客户端列表吞掉 getpot 参数）。
        yt_args += f'&getpot_bgutil_baseurl={BGUTIL_BASEURL}'
    args = ['--extractor-args', f'youtube:{yt_args}']
    if YT_COOKIES:
        args += ['--cookies', YT_COOKIES]
    elif YT_COOKIES_BROWSER:
        args += ['--cookies-from-browser', YT_COOKIES_BROWSER]
    # 2026 起 YouTube 的 n 挑战需要额外的「挑战求解脚本」，deno 在但脚本默认被跳过。
    # 必须显式允许从 github 下载 remote components，否则 web 客户端只能拿到图片 →
    # "Requested format is not available"。对 tv 客户端（PO Token）也无害。
    args += ['--remote-components', 'ejs:github']
    # 对已知瞬时抽取错误(如 KeyError INNERTUBE_CONTEXT / API 页偶发拉取失败)自动重试，
    # 避免 YouTube 偶发抽风就直接把任务判失败。
    args += ['--extractor-retries', '3', '--retry-sleep', 'linear=1']
    # 系统 HTTP(S) 代理已在文件顶部清除，yt-dlp 默认直连 YouTube（历史多次下载成功）。
    # 若你的网络必须走代理才能上 YouTube，设 YT_PROXY=http://host:port 走指定代理。
    proxy = os.environ.get('YT_PROXY')
    if proxy:
        args = ['--proxy', proxy] + args
    return args

# ── 检测 ffmpeg ──
HAS_FFMPEG = False
try:
    subprocess.run(['ffmpeg', '-version'], capture_output=True, timeout=5)
    HAS_FFMPEG = True
except Exception:
    pass

# ── 任务状态 ──
tasks = {}  # task_id -> { status, progress, filename, error, created }


def cleanup_old_files():
    """定期清理过期下载文件"""
    while True:
        time.sleep(300)
        now = time.time()
        try:
            for f in DOWNLOAD_DIR.iterdir():
                if f.is_file() and now - f.stat().st_mtime > MAX_FILE_AGE:
                    f.unlink(missing_ok=True)
            # 清理过期任务记录
            expired = [k for k, v in tasks.items() if now - v.get('created', 0) > MAX_FILE_AGE]
            for k in expired:
                tasks.pop(k, None)
        except Exception:
            pass


threading.Thread(target=cleanup_old_files, daemon=True).start()


# ═══════════════════════════════════════════════════════════
# Bilibili 辅助函数
# ═══════════════════════════════════════════════════════════

def is_bilibili(url):
    """判断是否为 Bilibili 链接"""
    return any(d in url for d in ['bilibili.com', 'b23.tv', 'bilibili.tv'])


def validate_netscape_cookies(filepath):
    """检查 cookies.txt 是否为有效的 Netscape 格式"""
    try:
        content = filepath.read_text(encoding='utf-8')
        lines = [l.strip() for l in content.splitlines() if l.strip() and not l.startswith('#')]
        if not lines:
            return False, '文件为空'
        for i, line in enumerate(lines):
            parts = line.split('\t')
            if len(parts) < 7:
                return False, f'第 {i+1} 行字段不足（{len(parts)}/7），可能不是 Netscape 格式'
        return True, f'有效（{len(lines)} 条 Cookie）'
    except Exception as e:
        return False, str(e)


def generate_netscape_cookies(sessdata, bili_jct='', dedeuserid=''):
    """根据 B站 Cookie 值生成 Netscape 格式 cookies.txt 内容"""
    lines = [
        '# Netscape HTTP Cookie File',
        '# https://curl.se/docs/http-cookies.html',
        '# This is a generated file! Do not edit.',
        '',
    ]
    expire = int(time.time()) + 30 * 86400
    if sessdata:
        lines.append(f'.bilibili.com\tTRUE\t/\tTRUE\t{expire}\tSESSDATA\t{sessdata}')
    if bili_jct:
        lines.append(f'.bilibili.com\tTRUE\t/\tTRUE\t{expire}\tbili_jct\t{bili_jct}')
    if dedeuserid:
        lines.append(f'.bilibili.com\tTRUE\t/\tTRUE\t{expire}\tDedeUserID\t{dedeuserid}')
    return '\n'.join(lines) + '\n'


def bilibili_extra_args(url):
    """Bilibili 专用 yt-dlp 参数，解决 412 Precondition Failed"""
    if not is_bilibili(url):
        return []
    args = [
        '--user-agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
        '--referer', 'https://www.bilibili.com',
        '--add-header', 'Referer: https://www.bilibili.com',
    ]
    # 如果存在有效的 cookies.txt，自动使用（用于解锁 1080P+ 画质）
    if COOKIES_FILE.exists():
        valid, _ = validate_netscape_cookies(COOKIES_FILE)
        if valid:
            args += ['--cookies', str(COOKIES_FILE)]
    return args


# ═══════════════════════════════════════════════════════════
# 路由
# ═══════════════════════════════════════════════════════════

@app.route('/')
def index():
    cookies_valid = False
    cookies_msg = ''
    if COOKIES_FILE.exists():
        cookies_valid, cookies_msg = validate_netscape_cookies(COOKIES_FILE)
    return jsonify({
        'service': '老肥工具箱视频下载服务',
        'status': 'running',
        'ffmpeg': HAS_FFMPEG,
        'bilibili_cookies': cookies_valid,
        'cookies_detail': cookies_msg,
        'endpoints': ['/api/info', '/api/formats', '/api/download', '/api/task/<id>', '/api/cookies', '/downloads/<file>']
    })


@app.route('/api/cookies', methods=['GET', 'POST', 'DELETE'])
def manage_cookies():
    """管理 Bilibili Cookie 文件"""
    if request.method == 'GET':
        if not COOKIES_FILE.exists():
            return jsonify({'exists': False, 'valid': False})
        valid, msg = validate_netscape_cookies(COOKIES_FILE)
        return jsonify({'exists': True, 'valid': valid, 'detail': msg})

    if request.method == 'DELETE':
        try:
            COOKIES_FILE.unlink(missing_ok=True)
            return jsonify({'ok': True, 'message': 'cookies.txt 已删除'})
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    # POST: 通过 SESSDATA 等值生成 Netscape 格式 cookies.txt
    data = request.get_json() or {}
    sessdata = data.get('sessdata', '').strip()
    bili_jct = data.get('bili_jct', '').strip()
    dedeuserid = data.get('dedeuserid', '').strip()

    if not sessdata:
        return jsonify({'error': '缺少 sessdata 参数（必填）'}), 400

    try:
        content = generate_netscape_cookies(sessdata, bili_jct, dedeuserid)
        COOKIES_FILE.write_text(content, encoding='utf-8')
        return jsonify({'ok': True, 'message': 'cookies.txt 已生成（Netscape 格式）'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/info', methods=['POST'])
def video_info():
    """获取视频信息"""
    data = request.get_json() or {}
    url = data.get('url', '').strip()
    if not url:
        return jsonify({'error': '缺少 url 参数'}), 400

    try:
        result = subprocess.run(
            ['yt-dlp', '--no-update', '--dump-json', '--no-download']
            + bilibili_extra_args(url) + _yt_common_args() + [url],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode != 0:
            return jsonify({'error': result.stderr.strip() or '获取信息失败'}), 500

        info = json.loads(result.stdout)
        return jsonify({
            'id': info.get('id'),
            'title': info.get('title'),
            'duration': info.get('duration'),
            'uploader': info.get('uploader'),
            'view_count': info.get('view_count'),
            'thumbnail': info.get('thumbnail'),
            'description': (info.get('description') or '')[:300],
        })
    except subprocess.TimeoutExpired:
        return jsonify({'error': '请求超时'}), 504
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/formats', methods=['POST'])
def video_formats():
    """获取所有可用格式"""
    data = request.get_json() or {}
    url = data.get('url', '').strip()
    if not url:
        return jsonify({'error': '缺少 url 参数'}), 400

    try:
        result = subprocess.run(
            ['yt-dlp', '--no-update', '-J', '--no-download']
            + bilibili_extra_args(url) + _yt_common_args() + [url],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode != 0:
            return jsonify({'error': result.stderr.strip() or '获取格式失败'}), 500

        info = json.loads(result.stdout)
        formats = []
        for f in info.get('formats', []):
            formats.append({
                'format_id': f.get('format_id'),
                'ext': f.get('ext'),
                'resolution': f.get('resolution', 'audio only'),
                'fps': f.get('fps'),
                'vcodec': f.get('vcodec', 'none'),
                'acodec': f.get('acodec', 'none'),
                'filesize': f.get('filesize') or f.get('filesize_approx'),
                'note': f.get('format_note', ''),
            })
        return jsonify({'title': info.get('title'), 'formats': formats})
    except subprocess.TimeoutExpired:
        return jsonify({'error': '请求超时'}), 504
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/download', methods=['POST'])
def start_download():
    """启动下载任务（异步）"""
    data = request.get_json() or {}
    url = data.get('url', '').strip()
    mode = data.get('mode', 'best')  # best | 1080 | 720 | 480 | audio_mp3 | audio_best
    if not url:
        return jsonify({'error': '缺少 url 参数'}), 400

    task_id = str(uuid.uuid4())[:8]
    tasks[task_id] = {'status': 'downloading', 'progress': '0%', 'filename': None, 'error': None, 'created': time.time()}

    def do_download():
        output_log = []
        try:
            output_tpl = str(DOWNLOAD_DIR / f'{task_id}_%(title).80s.%(ext)s')

            # 构建 yt-dlp 命令
            cmd = ['yt-dlp', '--no-update', '--no-playlist', '-o', output_tpl, '--newline']

            if mode == 'audio_mp3':
                if HAS_FFMPEG:
                    cmd += ['-x', '--audio-format', 'mp3', '--audio-quality', '0']
                else:
                    cmd += ['-f', 'bestaudio[ext=m4a]/bestaudio']
            elif mode == 'audio_best':
                if HAS_FFMPEG:
                    cmd += ['-x', '--audio-format', 'best']
                else:
                    cmd += ['-f', 'bestaudio[ext=m4a]/bestaudio']
            elif mode in ('1080', '720', '480'):
                height = mode
                if HAS_FFMPEG:
                    # 强制 H.264(avc1) 视频 + AAC(mp4a) 音频，保证全平台可播放。
                    # 原因：YouTube 1080p 的 bestvideo 默认是 AV1(vp9) 编码、bestaudio 是
                    # Opus，yt-dlp 合并仅 stream-copy 不重编码，mp4 里塞 AV1/Opus 多数
                    # 播放器(QuickTime/手机/微信/QQ)解不动 → "能下但播不了"。
                    # 限定 avc1+mp4a 后兼容性最佳；代价：放弃 1080p+ 的 AV1/VP9 流
                    # (YouTube 的 4K 无 H.264 版)，最高到 1080p H.264。
                    cmd += ['-f', f'bestvideo[height<={height}][vcodec^=avc1]+bestaudio[acodec^=mp4a]/best[height<={height}][vcodec^=avc1]/best[height<={height}]/best']
                    cmd += ['--merge-output-format', 'mp4']
                else:
                    cmd += ['-f', f'best[height<={height}][vcodec^=avc1]/best[height<={height}]/best']
            else:
                if HAS_FFMPEG:
                    # 默认最高画质：同样强制 H.264+AAC 以保证可播放（见上方说明）。
                    # 用 avc1 过滤优先选 H.264 流，无更高分辨率 H.264 时回退该分辨率 avc1。
                    cmd += ['-f', 'bestvideo[vcodec^=avc1]+bestaudio[acodec^=mp4a]/best[vcodec^=avc1]/best']
                    cmd += ['--merge-output-format', 'mp4']
                else:
                    cmd += ['-f', 'best[vcodec^=avc1]/best']

            # Bilibili 专用参数（User-Agent + Referer + Cookie）
            cmd += bilibili_extra_args(url)
            # YouTube 专用参数（player 客户端 + 可选 cookies / PO Token，绕过 bot 检测）
            cmd += _yt_common_args()
            cmd.append(url)

            tasks[task_id]['cmd'] = ' '.join(cmd)

            # 应用层重试：YouTube 偶发抽风(如 KeyError INNERTUBE_CONTEXT / API 页拉取失败 /
            # bot 检测)属于瞬时错误，重试往往即可成功。命中瞬时标记才重试，避免对真正的
            # 配置错误(如格式不可用)做无意义循环。
            transient_markers = (
                'INNERTUBE_CONTEXT', 'Sign in to confirm', 'extractor error',
                'page needs to be reloaded', 'Unable to download API page',
            )
            max_attempts = 3
            for attempt in range(1, max_attempts + 1):
                proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
                for line in proc.stdout:
                    line = line.strip()
                    output_log.append(line)
                    if len(output_log) > 50:
                        output_log.pop(0)
                    if '[download]' in line and '%' in line:
                        try:
                            pct = line.split('%')[0].split()[-1]
                            tasks[task_id]['progress'] = pct + '%'
                        except Exception:
                            pass
                proc.wait()
                if proc.returncode == 0:
                    break
                err_lines = [l for l in output_log if 'ERROR' in l or 'error' in l.lower()]
                err_msg = err_lines[-1] if err_lines else '\n'.join(output_log[-5:])
                if attempt < max_attempts and any(m in err_msg for m in transient_markers):
                    output_log.append(f'[重试] 第 {attempt} 次失败（疑似 YouTube 瞬时错误），5s 后自动重试...')
                    time.sleep(5)
                    continue
                tasks[task_id]['status'] = 'error'
                tasks[task_id]['error'] = f'yt-dlp 失败: {err_msg}'
                return

            files = sorted(DOWNLOAD_DIR.glob(f'{task_id}_*'), key=lambda f: f.stat().st_mtime, reverse=True)
            if files:
                tasks[task_id]['status'] = 'done'
                tasks[task_id]['filename'] = files[0].name
                tasks[task_id]['filesize'] = files[0].stat().st_size
                tasks[task_id]['progress'] = '100%'
            else:
                tasks[task_id]['status'] = 'error'
                tasks[task_id]['error'] = '下载完成但未找到文件，日志: ' + '\n'.join(output_log[-3:])

        except Exception as e:
            tasks[task_id]['status'] = 'error'
            tasks[task_id]['error'] = str(e)

    threading.Thread(target=do_download, daemon=True).start()
    return jsonify({'task_id': task_id, 'status': 'downloading'})


@app.route('/api/task/<task_id>')
def task_status(task_id):
    """查询任务状态"""
    task = tasks.get(task_id)
    if not task:
        return jsonify({'error': '任务不存在'}), 404

    resp = {
        'task_id': task_id,
        'status': task['status'],
        'progress': task['progress'],
    }
    if task['status'] == 'done':
        resp['filename'] = task['filename']
        resp['filesize'] = task.get('filesize', 0)
        resp['download_url'] = f'/downloads/{task["filename"]}'
    elif task['status'] == 'error':
        resp['error'] = task['error']
    return jsonify(resp)


@app.route('/downloads/<path:filename>')
def serve_file(filename):
    """提供文件下载"""
    return send_from_directory(DOWNLOAD_DIR, filename, as_attachment=True)


if __name__ == '__main__':
    print(f'🚀 老肥工具箱视频下载服务启动在 http://0.0.0.0:{PORT}')
    print(f'📁 下载目录: {DOWNLOAD_DIR.resolve()}')
    print(f'⏰ 文件保留时间: {MAX_FILE_AGE}s')
    if HAS_FFMPEG:
        print(f'✅ ffmpeg 已检测到，支持视频合并和音频转码')
    else:
        print(f'⚠️  未检测到 ffmpeg！视频将以单文件格式下载（画质可能受限），音频无法转为 mp3')
        print(f'   安装方法: apt install ffmpeg (Ubuntu) / yum install ffmpeg (CentOS) / brew install ffmpeg (macOS)')
    if COOKIES_FILE.exists():
        valid, msg = validate_netscape_cookies(COOKIES_FILE)
        if valid:
            print(f'✅ 检测到 cookies.txt（{msg}），Bilibili 1080P+ 高画质已解锁')
        else:
            print(f'⚠️  cookies.txt 格式无效：{msg}')
            print(f'   请通过页面「设置 Cookie」功能重新配置，或删除该文件')
    else:
        print(f'ℹ️  未检测到 cookies.txt，Bilibili 最高仅支持 480p（未登录）')
        print(f'   如需 1080P+ 画质，请在页面中设置 Cookie，或通过 /api/cookies 接口配置')
    app.run(host='0.0.0.0', port=PORT, debug=False)
