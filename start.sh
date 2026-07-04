#!/bin/bash
# Soft IP 主诉评估系统 - 启动脚本
# 用法: bash start.sh

echo "========================================="
echo "  ⚖️  Soft IP 主诉评估系统 v0.1.0"
echo "========================================="

# 检查 Python
if ! command -v python3 &> /dev/null; then
    echo "❌ 未找到 Python 3，请先安装 Python 3"
    exit 1
fi

echo "✅ Python $(python3 --version)"

# 安装依赖
echo ""
echo "📦 安装依赖..."
pip3 install -q -r requirements.txt
if [ $? -ne 0 ]; then
    echo "❌ 依赖安装失败"
    exit 1
fi
echo "✅ 依赖安装完成"

# 启动
echo ""
echo "🚀 启动应用..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  浏览器将自动打开: http://localhost:8501"
echo "  按 Ctrl+C 停止"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

streamlit run app.py
