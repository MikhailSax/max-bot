# Настройка MAX-бота и Bitrix24

## Установка зависимостей
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -r requirements.txt
```

## Куда вставлять токен MAX
Токен нужно передать через переменную окружения `MAX_BOT_TOKEN`:

```bash
export MAX_BOT_TOKEN="ваш_токен_max"
```

Опционально можно задать базовый URL API MAX:

```bash
export MAX_API_BASE_URL="https://api.max.ru"
```

## Настройка Bitrix24
```bash
export BITRIX24_WEBHOOK_URL="https://your.bitrix24.ru/rest/1/xxxx"
export BITRIX24_OPEN_LINE_ID="3"
# опционально
export BITRIX24_MANAGER_ID="17"
```

## Запуск
```bash
python bot.py
```

## Проверка webhook
```bash
curl -X POST http://localhost:8080/webhook/max \
  -H 'Content-Type: application/json' \
  -d '{"chat_id":"42","text":"Привет"}'
```
