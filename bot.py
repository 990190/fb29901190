import logging
import os
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters
import trafilatura
from lxml import etree
from flask import Flask, request, jsonify
import asyncio

BOT_TOKEN = os.environ["BOT_TOKEN"]
PORT = int(os.environ.get("PORT", 10000))
WEBHOOK_URL = os.environ.get("RENDER_EXTERNAL_URL", "https://fb29901190-bot.onrender.com") + "/webhook"

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

app = Application.builder().token(BOT_TOKEN).build()

async def start(update: Update, context):
    await update.message.reply_text("Привет! Отправь ссылку на статью — я конвертирую её в FB2.")

async def handle_url(update: Update, context):
    url = update.message.text.strip()
    if not url.startswith(('http://', 'https://')):
        await update.message.reply_text("Пожалуйста, отправь корректную ссылку.")
        return

    try:
        downloaded = trafilatura.fetch_url(url)
        if not downloaded:
            raise ValueError("Не удалось загрузить страницу.")

        text = trafilatura.extract(
            downloaded,
            include_comments=False,
            output_format="xml",
            with_metadata=True
        )
        if not text:
            raise ValueError("Не удалось извлечь читаемый текст.")

        wrapper = f"<doc>{text}</doc>"
        tree = etree.fromstring(wrapper.encode("utf-8"))

        title_elem = tree.find(".//title")
        title = title_elem.text if title_elem is not None and title_elem.text else "Без названия"

        body_elem = tree.find(".//body")
        if body_elem is None:
            raise ValueError("Нет содержимого для конвертации.")

        fb2_root = etree.Element("FictionBook", xmlns="http://www.gribuser.ru/xml/fictionbook/2.0")
        desc = etree.SubElement(fb2_root, "description")
        title_info = etree.SubElement(desc, "title-info")
        etree.SubElement(title_info, "book-title").text = title
        etree.SubElement(title_info, "lang").text = "ru"

        body = etree.SubElement(fb2_root, "body")
        section = etree.SubElement(body, "section")

        for p in body_elem.xpath(".//p"):
            para = etree.SubElement(section, "p")
            para.text = (p.text or "").strip() or ""

        fb2_bytes = etree.tostring(fb2_root, encoding="utf-8", xml_declaration=True, pretty_print=True)
        filename = f"{title[:50]}.fb2".replace("/", "_").replace("\\", "_")

        await update.message.reply_document(document=fb2_bytes, filename=filename)

    except Exception as e:
        await update.message.reply_text(f"Ошибка: {str(e)[:200]}")

app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_url))

flask_app = Flask(__name__)

@flask_app.route("/webhook", methods=["POST"])
def telegram_webhook():
    json_data = request.get_json()
    if json_data:
        asyncio.run(app.update_queue.put(Update.de_json(json_data, app.bot)))
    return jsonify({"status": "ok"})

@flask_app.route("/")
def health_check():
    return "OK"

if __name__ == "__main__":
    import threading
    def run_bot():
        asyncio.run(app.bot.set_webhook(url=WEBHOOK_URL))
        app.run_polling()
    threading.Thread(target=run_bot, daemon=True).start()
    flask_app.run(host="0.0.0.0", port=PORT)
