#!/bin/bash
# TEM-4 自适应备考系统 - 一键启动脚本

set -e

echo "=========================================="
echo "  🌳 TEM-4 自适应备考系统 v1.0"
echo "=========================================="

# 检查 Python
if ! command -v python3 &> /dev/null; then
    echo "❌ 未找到 Python3，请先安装 Python 3.8+"
    exit 1
fi

# 进入项目目录
cd "$(dirname "$0")"

# 安装依赖
echo ""
echo "📦 检查依赖..."
pip install flask --break-system-packages -q 2>/dev/null || pip install flask -q 2>/dev/null
echo "✅ 依赖就绪"

# 启动应用
echo ""
echo "🌿 启动服务器..."
echo "=========================================="
python3 app.py
