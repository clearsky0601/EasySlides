#!/bin/zsh
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "$0")" && pwd)"
VENV_DIR="$PROJECT_ROOT/.venv"
PYTHON_BIN="${PYTHON_BIN:-python3}"
PORT="${PORT:-10001}"

cd "$PROJECT_ROOT"

mkdir -p "$PROJECT_ROOT/media"
if [ ! -f "$PROJECT_ROOT/db.sqlite3" ]; then
  touch "$PROJECT_ROOT/db.sqlite3"
fi

if [ ! -d "$VENV_DIR" ]; then
  "$PYTHON_BIN" -m venv "$VENV_DIR"
fi

source "$VENV_DIR/bin/activate"
python -m pip install --upgrade pip >/dev/null
python -m pip install -r "$PROJECT_ROOT/requirements.txt"
python "$PROJECT_ROOT/manage.py" migrate --noinput

python "$PROJECT_ROOT/manage.py" shell -c "
from django.contrib.auth import get_user_model
User = get_user_model()
if not User.objects.filter(is_superuser=True).exists():
    User.objects.create_superuser('admin', '', 'admin')
    print('Created default superuser: admin/admin')
else:
    print('Superuser already exists, skipping creation')
"

exec python -m daphne -b 0.0.0.0 -p "$PORT" eazy_slides.asgi:application
