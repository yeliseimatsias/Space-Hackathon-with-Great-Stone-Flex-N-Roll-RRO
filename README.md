# Flex-n-Roll PRO — AI-ассистент (FastAPI)

Сервис принимает обновления **Telegram** (вебхук), классифицирует запрос (**Google Gemini**), ищет ответ в **базе знаний** (PostgreSQL + pgvector + sentence-transformers), при необходимости создаёт **лид и задачу в Bitrix24** (входящий вебхук) и уведомляет оператора. Ответ клиенту в Telegram — через **форму в браузере** или **JSON API** с общим секретом.

## Требования

- Python 3.11+
- Docker (PostgreSQL с pgvector для локальной БД)

## Переменные окружения

Скопируйте `.env.example` в `.env` и заполните:

| Переменная | Назначение |
|------------|------------|
| `TELEGRAM_BOT_TOKEN` | Токен бота от @BotFather |
| `BASE_URL` | Публичный HTTPS (ngrok и т.д.), без завершающего `/` |
| `BITRIX_WEBHOOK_URL` | Входящий вебхук Bitrix24 (CRM, задачи, **im**) |
| `DATABASE_URL` | AsyncPG-строка; имя БД в Docker: **`flexnroll`** |
| `LLM_API_KEY` | Ключ Google AI Studio (Gemini) |
| `BITRIX_REPLY_WEBHOOK_SECRET` | Опционально: секрет для `/operator/reply` и `POST /webhook/bitrix/reply` |

**Без Bitrix OAuth:** достаточно вебхука. Оператор видит в уведомлении `telegram_chat_id` и отвечает через `GET /operator/reply` или POST.

## Быстрый старт (Docker: приложение + БД)

В `.env` для контейнера `app` укажите хост БД **`db`**:

`DATABASE_URL=postgresql+asyncpg://app:app@db:5432/flexnroll`

```bash
cd docker
docker compose up --build
```

API: `http://localhost:8000/docs`

## Локально: только БД в Docker

```bash
cd docker
docker compose up db -d
pip install -r requirements.txt
alembic -c alembic/alembic.ini upgrade head
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

`DATABASE_URL` с хостом **`localhost`**: `postgresql+asyncpg://app:app@localhost:5432/flexnroll`

### Windows (PowerShell)

В каталоге **`scripts/`** два вспомогательных файла (запускать из **корня репозитория**):

| Скрипт | Когда | Что делает |
|--------|--------|------------|
| **`setup.ps1`** | Один раз (или после клона) | Если нет `.env` — копирует из `.env.example`; `pip install -r requirements.txt`; поднимает контейнер **`db`** из `docker/docker-compose.yml`; ждёт Postgres; `alembic upgrade head`. |
| **`dev.ps1`** | Каждый раз при разработке | `uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload` |

```powershell
powershell -ExecutionPolicy Bypass -File scripts/setup.ps1
powershell -ExecutionPolicy Bypass -File scripts/dev.ps1
```

На Linux/macOS те же шаги — вручную командами из раздела «Локально» выше; скрипты не обязательны.

## Сценарий демо (MVP)

1. Клиент пишет боту в Telegram → создаётся лид, классификация, при необходимости задача и уведомление оператору в Bitrix (**im**).
2. Оператор отвечает: откройте `{BASE_URL}/operator/reply`, введите секрет из `.env`, `chat_id` из уведомления и текст — клиент получит сообщение в Telegram.
3. Вопросы про технологию/цену с попаданием в базу знаний — мгновенный ответ бота + комментарий к лиду.

Опционально **`PRIMARY_BITRIX_USER_ID`** и **`BITRIX_PRIMARY_USER_ID_SALES_ONLY=true`**, чтобы задачи sales шли на одного пользователя Bitrix, а другие роли — по экспертам из БД.

## Тесты

```bash
pytest
```

## Эндпоинты

| Метод | Путь | Описание |
|--------|------|----------|
| GET | `/` | Краткая информация |
| GET | `/health` | Проверка БД |
| POST | `/webhook/telegram` | Вебхук Telegram |
| POST | `/webhook/bitrix` | Заглушка под исходящие события Bitrix |
| GET | `/operator/reply` | Форма ответа клиенту в Telegram |
| POST | `/webhook/bitrix/reply` | Ответ клиенту (JSON: `secret`, `telegram_chat_id`, `text`) |
| GET | `/admin/employees` | Список сотрудников |
| PATCH | `/admin/employees/{id}/toggle-availability` | Доступность |
| POST | `/admin/employees/{id}/rating` | Рейтинг |
| POST | `/admin/knowledge` | Добавить запись в базу знаний |

## Логи

`structlog`, JSON в stdout, уровень `LOG_LEVEL`.
