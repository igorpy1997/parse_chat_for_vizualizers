FROM ubuntu:latest
LABEL authors="ihor"

ENTRYPOINT ["top", "-b"]


FROM python:3.10-slim

# Установим gcc для компиляции зависимостей
RUN apt-get update && apt-get install -y gcc

# Установим виртуальное окружение
RUN python3.10 -m venv /opt/venv

# Скопируем файлы проекта
COPY . /app

# Установим зависимости
RUN . /opt/venv/bin/activate && pip install -r /app/requirements.txt

# Установим рабочую директорию
WORKDIR /app

# Запустим бота
CMD ["/bin/bash", "-c", ". /opt/venv/bin/activate && python aiogram_bot.py"]
