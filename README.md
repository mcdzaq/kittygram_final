# Kittygram: контейнеры и CI

Учебная практическая №4: Django API, React, Nginx и PostgreSQL в Docker Compose.
Исходная заготовка — [Yandex-Practicum/kittygram_final](https://github.com/Yandex-Practicum/kittygram_final).

## Локальный запуск

Нужны Docker с Compose v2 и Python 3 для создания конфигурации и HTTP-проверки.

```sh
python3 scripts/init_env.py
docker compose up --build --wait --wait-timeout 180
```

Открыть **http://localhost:9000**, зарегистрироваться и добавить кота с фотографией.
`init_env.py` создаёт `.env` со случайными `SECRET_KEY` и `POSTGRES_PASSWORD`,
правами `0600` и сохраняет существующий файл без изменений. Остальные параметры
описаны в `.env.example`. При смене порта измените также `CSRF_TRUSTED_ORIGINS`.
Сохраните `127.0.0.1` в `ALLOWED_HOSTS`: его использует проверка backend.

При старте backend выполняет миграции и `collectstatic`, затем запускает Gunicorn.
Gateway ждёт готовности backend и завершения копирования frontend.
Frontend — одноразовый контейнер: состояние `Exited (0)` означает успех.

```sh
docker compose ps --all
docker compose logs --tail 100 backend gateway
docker compose exec backend python manage.py createsuperuser
```

Админка: http://localhost:9000/admin/. Порт открыт только на loopback.
Данные сохраняются в томах `pg_data`, `static`, `media`. Обычный
`docker compose down` удаляет контейнеры, сохраняя тома. Опция `--volumes`
удаляет данные: для рабочего локального стенда её использовать не нужно.

## Проверки

Сквозная проверка обращается к настоящему Nginx: SPA-маршруты, JS/CSS,
статика админки, регистрация, TokenAuthentication, CRUD, достижения и PNG-фото.
Повторный вход, записи PostgreSQL и байты фотографии проверяются после
пересоздания контейнеров:

```sh
python3 scripts/smoke.py seed
docker compose down
docker compose up --wait --wait-timeout 180
python3 scripts/smoke.py verify
```

Демонстрационный кот остаётся в приложении. Данные входа находятся в
`.local/smoke.json` (0600, исключён из Git). `verify` можно повторять;
для нового независимого `seed` задайте другой `--state`.

Backend-тесты и исходные проверки файлов:

```sh
python3.12 -m venv .venv
. .venv/bin/activate
pip install -r backend/requirements-dev.txt
ruff check backend scripts
DJANGO_TESTING=1 DB_ENGINE=sqlite python backend/manage.py test cats
DJANGO_TESTING=1 DB_ENGINE=sqlite pytest tests/test_files.py
```

В CI backend-тесты выполняются с PostgreSQL 13. SQLite разрешён только
в явно включённом тестовом режиме. Все версии Python-зависимостей зафиксированы;
в Docker устанавливаются только runtime-зависимости.

Frontend:

```sh
cd frontend
npm ci --no-audit --no-fund
CI=true npm test -- --watchAll=false --runInBand
CI=true npm run build
```

## GitHub Actions и Docker Hub

[Workflow](.github/workflows/main.yml) запускается при push в `main`, pull request
и вручную. Три независимые проверки — backend/инфраструктура, frontend и полный
Compose — должны пройти до публикации. Pull request не публикует образы и не
получает секреты. Actions закреплены по SHA; `GITHUB_TOKEN` имеет `contents: read`.

В репозитории нужны Actions secrets:

| Имя | Значение |
| --- | --- |
| `DOCKERHUB_TOKEN` | Docker Hub PAT пользователя `mcdzaq`, Read & Write |
| `TELEGRAM_TOKEN` | Токен отдельного бота `@mcdzaq_kittygram_bot` |
| `TELEGRAM_TO` | ID личного чата получателя, который запустил бота |

После тестов публикуются публичные `mcdzaq/kittygram_backend`,
`mcdzaq/kittygram_frontend`, `mcdzaq/kittygram_gateway` для `linux/amd64` и
`linux/arm64`, с тегами `latest` и полного SHA коммита. Затем проверяется
публичная доступность всех трёх репозиториев и отправляется уведомление.
Уведомление сообщает об успешных тестах и публикации; серверный деплой не заявляется.
В форке нужно включить Actions. Файл `kittygram_workflow.yml` — точная копия
workflow для проверки задания; CI проверяет их совпадение.

Запуск опубликованных образов без сборки:

```sh
# Остановить локальную сборку, сохранив данные.
docker compose down
# Для воспроизводимого запуска задайте в .env IMAGE_TAG=<полный SHA коммита>.
docker compose -f docker-compose.production.yml pull
docker compose -f docker-compose.production.yml up --wait --wait-timeout 180
```

## Граница текущего этапа

Внешний учебный сервер, Taski и HTTPS пока не настроены; личная VPS не используется.
`tests.yml` честно содержит localhost и `taski_domain: not-configured`.
Исходные `tests/test_connection.py` проверяют внешний HTTPS и два проекта на одном
сервере: они остаются без изменений и требуют следующего этапа. Проверку Docker Hub
`DJANGO_TESTING=1 DB_ENGINE=sqlite pytest tests/test_dockerhub_images.py` можно запускать после публикации образов.

PostgreSQL 13 оставлен по буквальному требованию методички, Django 4.2.30 —
совместимая ветка. Их срок поддержки завершён; перед внешним размещением нужно
согласовать обновление PostgreSQL и Django до поддерживаемой связки.
Также сохранено поведение API заготовки: любой авторизованный пользователь может
редактировать чужих котов; ограничения владельца сейчас есть только в интерфейсе.
Это следует исправить и проверить отдельно до открытия приложения в интернет.
