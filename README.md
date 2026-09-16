# USelf Test v0.1 — Render-ready prototype

Минимальный рабочий прототип приватного парного опросника USelf.

## Что реализовано

- создание комнаты;
- две отдельные приватные ссылки;
- независимое прохождение на разных устройствах;
- серверное хранение ответов в PostgreSQL;
- сохранение прогресса;
- `Да / Возможно / Нет`;
- после завершения обоих показываются только взаимные `Да/Возможно`;
- если хотя бы один выбрал `Нет`, вопрос в результат не попадает;
- вопросы фиксируются для комнаты snapshot'ом в момент создания;
- frontend React и backend FastAPI в production работают с одного HTTPS-домена;
- готовый `render.yaml` создаёт Free Web Service + Free PostgreSQL.

## Самый простой деплой

Открой файл [`DEPLOY_RENDER_GITHUB_RU.md`](DEPLOY_RENDER_GITHUB_RU.md) и иди по шагам.

В Render достаточно использовать **New → Blueprint** и подключить этот GitHub-репозиторий. `render.yaml` делает остальное.

## Важно: вопросы пока демонстрационные

`backend/data/questions.demo.json` — небольшой технический набор для проверки механики.

Перед настоящим полным прохождением его нужно заменить финальным каноническим банком USelf.

## Локальный dev-запуск

```bash
cp .env.example .env
docker compose up --build
```

Frontend dev: http://localhost:5173  
API docs: http://localhost:8000/docs

## Production

Root `Dockerfile`:

1. собирает Vite/React;
2. устанавливает Python dependencies;
3. копирует собранный frontend;
4. запускает FastAPI/Uvicorn;
5. FastAPI отдаёт и API, и React с одного домена.

Health check: `/health`.
