#!/bin/bash
# 诉算项目 — 一键测试脚本
# 运行: bash test.sh

set -e
cd "$(dirname "$0")"

echo "=========================================="
echo "  诉算·SOFT IP — 测试套件"
echo "=========================================="
echo ""

PYTHON=/usr/local/Cellar/python@3.9/3.9.6/bin/python3.9

echo "📦 Python 版本: $($PYTHON --version)"
echo ""

echo "1️⃣  单元测试 (145 个)..."
$PYTHON -m pytest tests/ -q
echo ""

echo "2️⃣  产品功能验证 (48 项)..."
$PYTHON verify_product.py
echo ""

echo "=========================================="
echo "  🎉 全部通过！"
echo "=========================================="
