#!/usr/bin/env python3
"""Minimal Telegram command bot — /gencode for Silent Analyst invite system."""
import os, time, requests as req
from dotenv import load_dotenv

load_dotenv("/home/ubuntu/SilentAnalyst/.env")

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
ADMIN_SECRET = os.environ.get("INVITE_ADMIN_SECRET", "SA-INV-6AC604BC78B4D28B")
BASE = f"https://api.telegram.org/bot{TOKEN}"

def send(chat_id, text, parse_mode="Markdown"):
    try:
        req.post(f"{BASE}/sendMessage",
            json={"chat_id": chat_id, "text": text, "parse_mode": parse_mode},
            timeout=5)
    except:
        pass

def get_updates(offset=None):
    params = {"timeout": 30, "allowed_updates": ["message"]}
    if offset:
        params["offset"] = offset
    r = req.get(f"{BASE}/getUpdates", params=params, timeout=35)
    return r.json().get("result", [])

def handle(message):
    chat_id = message["chat"]["id"]
    text = message.get("text", "")

    if text.startswith("/start"):
        send(chat_id, "Silent Analyst Bot\n\nCommands:\n/gencode [PREFIX] [MAX\\_USES]")
        return

    if not text.startswith("/gencode"):
        return

    parts = text.split()
    args = parts[1:]
    if not args:
        prefix = "TG"
        max_uses = 10
    elif args[0].isdigit():
        prefix = "TG"
        max_uses = int(args[0])
    else:
        prefix = args[0].upper()
        max_uses = int(args[1]) if len(args) > 1 else 10

    try:
        res = req.post(
            "http://localhost:5002/api/admin/gencode",
            headers={"Content-Type": "application/json", "X-Admin-Secret": ADMIN_SECRET},
            json={"prefix": prefix, "role": "beta", "source_tag": "telegram",
                  "campaign": "tg_bot_gen", "max_uses": max_uses},
            timeout=5
        )
        data = res.json()
        code = data.get("code", "")
        if data.get("success"):
            send(chat_id,
                "✅ Invite code generated:\n\n`" + code + "`\n\n"
                "Uses: " + str(max_uses) + "\nShare: silentanalyst.app")
        else:
            send(chat_id, "❌ Failed to generate code.")
    except Exception as e:
        send(chat_id, "❌ Error: " + str(e))

def main():
    if not TOKEN:
        print("ERROR: TELEGRAM_BOT_TOKEN not set")
        return
    print("invite_bot: polling started")
    offset = None
    while True:
        try:
            updates = get_updates(offset)
            for update in updates:
                offset = update["update_id"] + 1
                if "message" in update:
                    handle(update["message"])
        except Exception as e:
            print(f"poll error: {e}")
            time.sleep(5)

if __name__ == "__main__":
    main()