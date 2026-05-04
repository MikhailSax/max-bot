import os
from typing import Dict

import requests
from flask import Flask, jsonify, request

app = Flask(__name__)

# In-memory dialog state: chat_id -> step
# For production, replace with Redis or DB.
DIALOG_STATE: Dict[str, str] = {}

COMPANY_TEXT = (
    "Здравствуйте! 👋\n"
    "Мы компания ExampleCo — помогаем бизнесу автоматизировать продажи и поддержку клиентов.\n"
    "Внедряем CRM, чат-боты и интеграции с Битрикс24."
)

QUESTION_TEXT = "Есть ли у вас вопросы? Я могу сразу подключить менеджера из открытых линий Битрикс24."

BITRIX24_WEBHOOK_URL = os.getenv("BITRIX24_WEBHOOK_URL", "").rstrip("/")
OPEN_LINE_ID = os.getenv("BITRIX24_OPEN_LINE_ID", "")
MANAGER_ID = os.getenv("BITRIX24_MANAGER_ID", "")
MAX_BOT_TOKEN = os.getenv("MAX_BOT_TOKEN", "")
MAX_API_BASE_URL = os.getenv("MAX_API_BASE_URL", "https://api.max.ru")




def send_to_max(chat_id: str, text: str) -> None:
    """
    Sends a bot message to MAX via HTTP API.

    Requires env:
      - MAX_BOT_TOKEN
      - MAX_API_BASE_URL (optional, default https://api.max.ru)
    """
    if not MAX_BOT_TOKEN:
        app.logger.warning("MAX_BOT_TOKEN is not configured. Reply is returned only in webhook response.")
        return

    url = f"{MAX_API_BASE_URL.rstrip('/')}/bot/messages/send"
    headers = {"Authorization": f"Bearer {MAX_BOT_TOKEN}"}
    payload = {"chat_id": str(chat_id), "text": text}
    requests.post(url, json=payload, headers=headers, timeout=10)

def send_to_bitrix_open_line(chat_id: str, message: str) -> None:
    """
    Creates a chat in Bitrix24 open lines and forwards first client message.

    Requires env:
      - BITRIX24_WEBHOOK_URL, e.g. https://your.bitrix24.ru/rest/1/xxxx
      - BITRIX24_OPEN_LINE_ID, e.g. 3
      - BITRIX24_MANAGER_ID (optional): transfer to concrete manager
    """
    if not BITRIX24_WEBHOOK_URL or not OPEN_LINE_ID:
        app.logger.warning("Bitrix24 is not configured. Skipping transfer.")
        return

    register_url = f"{BITRIX24_WEBHOOK_URL}/imconnector.send.messages"
    payload = {
        "CONNECTOR": "max",
        "LINE": OPEN_LINE_ID,
        "MESSAGES": [
            {
                "user": {"id": str(chat_id), "name": "Клиент MAX"},
                "message": {"id": f"max-{chat_id}", "date": "", "text": message},
                "chat": {"id": str(chat_id)},
            }
        ],
    }

    requests.post(register_url, json=payload, timeout=10)

    if MANAGER_ID:
        transfer_url = f"{BITRIX24_WEBHOOK_URL}/imopenlines.bot.session.transfer"
        transfer_payload = {
            "CHAT_ID": str(chat_id),
            "USER_ID": str(MANAGER_ID),
        }
        requests.post(transfer_url, json=transfer_payload, timeout=10)


@app.post("/webhook/max")
def max_webhook():
    """
    Expected payload (example):
    {
      "chat_id": "123",
      "text": "Привет"
    }
    """
    data = request.get_json(force=True, silent=True) or {}
    chat_id = str(data.get("chat_id", "")).strip()
    text = str(data.get("text", "")).strip()

    if not chat_id:
        return jsonify({"ok": False, "error": "chat_id is required"}), 400

    step = DIALOG_STATE.get(chat_id, "start")

    if step == "start":
        DIALOG_STATE[chat_id] = "asked_questions"
        reply_text = f"{COMPANY_TEXT}\n\n{QUESTION_TEXT}"
        send_to_max(chat_id, reply_text)
        return jsonify(
            {
                "ok": True,
                "reply": reply_text,
                "handoff": False,
            }
        )

    if step == "asked_questions":
        send_to_bitrix_open_line(chat_id, text or "Клиент готов к общению с менеджером")
        DIALOG_STATE[chat_id] = "transferred"
        reply_text = "Спасибо! Подключаю менеджера. Пожалуйста, оставайтесь на связи 🙌"
        send_to_max(chat_id, reply_text)
        return jsonify(
            {
                "ok": True,
                "reply": reply_text,
                "handoff": True,
            }
        )

    reply_text = "Диалог уже передан менеджеру. Он ответит вам в этом чате."
    send_to_max(chat_id, reply_text)
    return jsonify(
        {
            "ok": True,
            "reply": reply_text,
            "handoff": True,
        }
    )


@app.get("/health")
def health():
    return jsonify({"ok": True})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "8080")))
