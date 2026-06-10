#!/bin/sh
set -e

# default 库：auth/session；slides 库：幻灯片内容（db_router 路由）
python manage.py migrate --noinput
python manage.py migrate --database=slides slideapp --noinput
python manage.py collectstatic --noinput

exec daphne -b 0.0.0.0 -p 10001 easy_slides.asgi:application
