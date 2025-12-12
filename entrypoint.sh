#!/bin/bash
set -e

# Создаем папку для логов, если нет
mkdir -p logs

echo "Waiting for database..."
# Простой цикл ожидания порта (можно использовать netcat или python скрипт)
# Но так как мы используем depends_on с healthcheck в docker-compose,
# база скорее всего уже готова.

echo "Applying migrations..."
alembic upgrade head

echo "Starting bot..."
# Запуск через модуль, как мы настраивали
python -m app.main
