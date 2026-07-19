#!/bin/bash
# Soft IP 主诉评估系统 - 一键启动脚本（自动打开浏览器）
# 用法: bash start.sh

set -e

echo "========================================="
echo "  Soft IP 主诉评估系统 v0.1.0"
echo "========================================="

# 查找可用的 streamlit 命令
STREAMLIT_CMD=""
for candidate in \
    "$(dirname "$0")/.venv/bin/streamlit" \
    "$HOME/.workbuddy/binaries/python/envs/default/bin/streamlit" \
    "$HOME/Library/Python/3.9/bin/streamlit" \
    "$(command -v streamlit 2>/dev/null)"; do
    if [ -n "$candidate" ] && [ -x "$candidate" ]; then
        STREAMLIT_CMD="$candidate"
        break
    fi
done

if [ -z "$STREAMLIT_CMD" ]; then
    # 尝试通过 python3 -m 方式运行
    if python3 -m streamlit version >/dev/null 2>&1; then
        STREAMLIT_CMD="python3 -m streamlit"
    else
        echo "❌ 未找到 streamlit，请先安装: pip install streamlit"
        exit 1
    fi
fi

echo "✅ Streamlit: $STREAMLIT_CMD"
echo "Starting Streamlit on http://127.0.0.1:8501"
echo "========================================="

# 后台启动 Streamlit
PYTHONIOENCODING=utf-8 STREAMLIT_BROWSER_GATHER_USAGE_STATS=false \
    $STREAMLIT_CMD run app.py --server.port 8501 --server.headless true --browser.gatherUsageStats false &
STREAMLIT_PID=$!

# 等待服务启动（最多15秒）
for i in $(seq 1 15); do
    if curl -s -o /dev/null http://127.0.0.1:8501 2>/dev/null; then
        echo ""
        echo "✅ 服务已启动，正在打开浏览器..."
        sleep 1
        open http://127.0.0.1:8501
        echo "🌐 浏览器已打开: http://127.0.0.1:8501"
        echo ""
        echo "按 Ctrl+C 停止服务"
        echo "========================================="
        wait $STREAMLIT_PID
        exit 0
    fi
    printf "\r  ⏳ 等待服务启动... (%d/15)" "$i"
    sleep 1
done

echo ""
echo "❌ 服务启动超时"
kill $STREAMLIT_PID 2>/dev/null
exit 1
