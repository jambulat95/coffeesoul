FROM python:3.12-slim

# Устанавливаем рабочую директорию
WORKDIR /app

# Устанавливаем системные зависимости (если нужны для сборки некоторых python-пакетов)
# netcat-openbsd нужен для скрипта ожидания БД (wait-for-it, если будем использовать, или просто nc)
RUN apt-get update && apt-get install -y --no-install-recommends \
    netcat-openbsd \
    && rm -rf /var/lib/apt/lists/*

# Копируем файл зависимостей и устанавливаем их
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем весь код проекта
COPY . .

# Делаем скрипт запуска исполняемым
RUN chmod +x entrypoint.sh

# Команда запуска (будет переопределена в entrypoint.sh)
CMD ["./entrypoint.sh"]
