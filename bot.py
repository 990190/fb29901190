import logging
import os
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters
import trafilatura
from lxml import etree
from flask import Flask, request, jsonify

# Безопасность и настройки
BOT_TOKEN = os.environ["BOT_TOKEN"]
WEBHOOK_PATH = "/webhook"
PORT = int(os.environ.get("PORT", 10000))
RENDER_EXTERNAL_URL = os.environ.get("RENDER_EXTERNAL_URL", "https://fb29901190-bot.onrender.com")
WEBHOOK_URL = RENDER_EXTERNAL_URL + WEBHOOK_PATH

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Создаём приложение один раз при старте
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

        fb2_bytes = etree.toestring(fb2_root, encoding="utf-8", xml_declaration=True, pretty_print=True)
        filename = f"{title[:50]}.fb2".replace("/", "_").replace("\\", "_")

        await update.message.reply_document(document=fb2_bytes, filename=filename)

    except Exception as e:
        await update.message.reply_text(f"Ошибка: {str(e)[:200]}")

# Регистрируем обработчики
app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_url))

# Flask-сервер
flask_app = Flask(__name__)

@flask_app.route(WEBHOOK_PATH, methods=["POST"])
def webhook():
    json_data = request.get_json()
    if json_
        # Обрабатываем обновление синхронно
        app.update_queue.put_nowait(Update.de_json(json_data, app.bot))
    return jsonify({"ok": True})

@flask_app.route("/setwebhook", methods=["GET"])
def set_webhook():
    # Устанавливаем вебхук вручную при необходимости
    import asyncio
    asyncio.run(app.bot.set_webhook(url=WEBHOOK_URL))
    return "Webhook set!"

@flask_app.route("/")
def index():
    return "FB2 Bot is running."

# Устанавливаем вебхук при первом запуске
if __name__ == "__main__":
    import asyncio
    asyncio.run(app.bot.set_webhook(url=WEBHOOK_URL))
    flask_app.run(host="0.0.0.0", port=PORT)
