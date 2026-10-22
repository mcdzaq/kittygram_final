# Backend Kittygram

Django REST Framework API с TokenAuthentication через Djoser.
Инструкция по контейнерам, переменным окружения и CI находится в
[корневом README](../README.md).

Для быстрых локальных тестов на Python 3.12:

```sh
pip install -r requirements-dev.txt
DJANGO_TESTING=1 DB_ENGINE=sqlite python manage.py test cats
```

Обычный запуск требует `SECRET_KEY`, PostgreSQL и его параметров из `.env.example`.
Статика собирается в `/backend_static/static`, фотографии сохраняются в `/app/media`.
Runtime-образ запускает миграции, collectstatic и Gunicorn командой `CMD` из Dockerfile.
