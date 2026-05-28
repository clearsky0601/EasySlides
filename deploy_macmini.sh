#!/bin/bash
set -e

# 部署脚本 - jyySlideWeb

echo "开始部署 jyySlideWeb..."

# 进入项目目录
cd ~/workspace/jyySlideWeb-main

# 检查Python版本
echo "Python版本: $(python3 --version)"

# 创建虚拟环境
if [ ! -d "venv" ]; then
    echo "创建虚拟环境..."
    python3 -m venv venv
fi

# 激活虚拟环境
source venv/bin/activate

# 安装依赖
echo "安装依赖..."
pip install -r requirements.txt

# 初始化数据库
echo "初始化数据库..."
python manage.py migrate --noinput

# 启动服务
echo "启动服务..."
echo "服务将在端口10001启动"
daphne -b 0.0.0.0 -p 10001 jyy_slide_web.asgi:application &
echo $! > jyySlideWeb.pid
echo "服务已启动，PID: $(cat jyySlideWeb.pid)"

echo "部署完成！访问 http://localhost:10001"
