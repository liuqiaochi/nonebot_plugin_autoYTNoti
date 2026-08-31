#!/bin/bash
# ──────────────────────────────────────────────────────────────
# feiTools 下载服务 一键启动脚本
#   - 激活隔离 venv（含 yt-dlp 2026.8.19 + Flask）
#   - 将 deno 加入 PATH（web 客户端过 YouTube bot 检测必需）
#   - 启动 app.py
#
# 关于画质（重要）：
#   YouTube 在没有 PoToken 时，无论怎么选都只给到 360p。
#   要拿到 1080p+ 必须带 PO Token。设 BGUTIL_BASEURL 后本脚本会
#   自动拉起 bgutil PO Token 后端（需先 git clone 到 ~/Desktop 下），
#   app.py 随即用 web(+cookies)+PoToken 解锁 1080p~4K。
#
# 用法：
#   ./start.sh                       # chrome cookies + 端口 5001（360p 上限）
#   PORT=5001 ./start.sh             # 换端口
#   BGUTIL_BASEURL=http://127.0.0.1:4416 ./start.sh  # 高画质模式（推荐）
#   YT_COOKIES_BROWSER=firefox BGUTIL_BASEURL=http://127.0.0.1:4416 ./start.sh
# ──────────────────────────────────────────────────────────────
set -euo pipefail

# 脚本所在目录（app.py 同目录）
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ── 路径（按需修改）──
VENV="${VENV:-/Users/mac/.workbuddy/binaries/python/envs/default}"
DENO_BIN_DIR="${DENO_HOME:-$HOME/.deno}/bin"

# ── 默认参数（可被环境变量覆盖）──
PORT="${PORT:-5001}"
YT_COOKIES_BROWSER="${YT_COOKIES_BROWSER:-chrome}"
# YT_COOKIES / BGUTIL_BASEURL 留空则不设置
BGUTIL_DIR="${BGUTIL_DIR:-/Users/mac/Desktop/bgutil-ytdlp-pot-provider/server}"

# ── 前置检查 ──
if [ ! -f "$VENV/bin/activate" ]; then
  echo "❌ 找不到 venv: $VENV" >&2
  echo "   请先创建并安装依赖: python3.13 -m venv $VENV && $VENV/bin/pip install yt-dlp flask flask-cors httpx" >&2
  exit 1
fi
if [ ! -x "$DENO_BIN_DIR/deno" ]; then
  echo "⚠️  找不到 deno: $DENO_BIN_DIR/deno" >&2
  echo "   web 客户端过 bot 检测需要 deno，请用以下命令安装:" >&2
  echo "   curl -fsSL https://deno.land/install.sh | sh" >&2
fi

# ── 若启用 BGUTIL_BASEURL 且 4416 未监听，则自动拉起 PO Token 后端 ──
if [ -n "${BGUTIL_BASEURL:-}" ]; then
  if ! lsof -i:4416 >/dev/null 2>&1; then
    if [ -f "$BGUTIL_DIR/build/main.js" ]; then
      echo "▶  自动启动 bgutil PO Token 后端 (4416)..."
      ( node "$BGUTIL_DIR/build/main.js" >/tmp/bgutil.log 2>&1 & )
      sleep 2
    else
      echo "⚠️  找不到 bgutil 后端: $BGUTIL_DIR/build/main.js" >&2
      echo "   请先 clone 并编译: git clone https://github.com/Brainicism/bgutil-ytdlp-pot-provider.git && cd bgutil-ytdlp-pot-provider/server && npm ci && npx tsc" >&2
    fi
  else
    echo "▶  bgutil PO Token 后端已在 4416 运行"
  fi
fi

# ── 激活环境 ──
# shellcheck disable=SC1091
source "$VENV/bin/activate"

# deno 加入 PATH（若已存在则前置）
export PATH="$DENO_BIN_DIR:$PATH"

# 导出 app.py 需要的变量
export PORT
export YT_COOKIES_BROWSER
[ -n "${YT_COOKIES:-}" ] && export YT_COOKIES
[ -n "${BGUTIL_BASEURL:-}" ] && export BGUTIL_BASEURL

# ── 启动信息 ──
echo "────────────────────────────────────────────"
echo " feiTools 下载服务启动中"
echo " venv    : $VENV"
echo " yt-dlp  : $(yt-dlp --version 2>/dev/null || echo unknown)"
echo " deno    : $(command -v deno >/dev/null && deno --version 2>/dev/null | head -1 || echo 'NOT FOUND')"
echo " cookies : ${YT_COOKIES_BROWSER:-$YT_COOKIES:-无(将走 tv/PO Token 模式)}"
echo " PoToken : ${BGUTIL_BASEURL:-未启用(画质上限 360p，建议设 BGUTIL_BASEURL)}"
echo " port    : $PORT"
echo "────────────────────────────────────────────"

cd "$SCRIPT_DIR"
exec python app.py
