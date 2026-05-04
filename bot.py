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
        return jsonify(
            {
                "ok": True,
                "reply": f"{COMPANY_TEXT}\n\n{QUESTION_TEXT}",
                "handoff": False,
            }
        )

    if step == "asked_questions":
        send_to_bitrix_open_line(chat_id, text or "Клиент готов к общению с менеджером")
        DIALOG_STATE[chat_id] = "transferred"
        return jsonify(
            {
                "ok": True,
                "reply": "Спасибо! Подключаю менеджера. Пожалуйста, оставайтесь на связи 🙌",
                "handoff": True,
            }
        )

    return jsonify(
        {
            "ok": True,
            "reply": "Диалог уже передан менеджеру. Он ответит вам в этом чате.",
            "handoff": True,
        }
    )


@app.get("/health")
def health():
    return jsonify({"ok": True})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "8080")))
