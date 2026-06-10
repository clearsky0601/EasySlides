# 使用官方Python镜像作为基础镜像（django>=6.0 要求 Python >= 3.12）
FROM python:3.14-slim

# 设置工作目录
WORKDIR /app

# 安装锁定版本的Python依赖
COPY requirements.lock .
RUN pip install --no-cache-dir -r requirements.lock

# 将项目文件复制到容器中
COPY . .
RUN chmod +x docker-entrypoint.sh

# 暴露应用的端口
EXPOSE 10001

# 入口：migrate（default + slides）+ collectstatic 后启动 Daphne
ENTRYPOINT ["./docker-entrypoint.sh"]
