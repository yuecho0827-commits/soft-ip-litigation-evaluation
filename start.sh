#!/bin/bash
# Soft IP 主诉评估系统 - 启动脚本
# 用法: bash start.sh

set -e

echo "========================================="
echo "  Soft IP 主诉评估系统 v0.1.0"
echo "========================================="

if ! command -v python3 >/dev/null 2>&1; then
    echo "Python 3 not found. Please install Python 3 first."
    exit 1
fi

echo "Python: $(python3 --version)"
echo "Installing dependencies..."
python3 -m pip install -q -r requirements.txt

echo "Starting Streamlit on http://localhost:8501"
PYTHONIOENCODING=utf-8 STREAMLIT_BROWSER_GATHER_USAGE_STATS=false python3 -m streamlit run app.py --server.port 8501 --server.headless true --browser.gatherUsageStats false