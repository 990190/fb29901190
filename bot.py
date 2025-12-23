import logging
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters
from readability import Document
import requests
from lxml import etree
import io

# ВАЖНО: замени это на твой токен
BOT_TOKEN = "8320529826:AAE_YQiSY3ti6Hb79NsLy49z_vFBCLzz85U"

# Логирование
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

async def start(update: Update, context):
    await update.message.reply_text("Привет! Отправь мне ссылку на статью — я конвертирую её в FB2.")

async def handle_url(update: Update, context):
    url = update.message.text.strip()
    
    # Проверка URL
    if not url.startswith(('http://', 'https://')):
        await update.message.reply_text("Пожалуйста, отправь корректную ссылку (начинающуюся с http:// или https://).")
        return

    try:
        # Получаем страницу
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        
        # Извлекаем чистый текст с помощью Readability
        doc = Document(response.text)
        title = doc.short_title() or "Без названия"
        content_html = doc.summary()

        # Генерируем FB2
        fb2_content = generate_fb2(title, content_html, url)
        
        # Отправляем файл
        fb2_file = io.BytesIO(fb2_content.encode('utf-8'))
        fb2_file.name = f"{title[:50]}.fb2".replace("/", "_").replace("\\", "_") + ".fb2"
        
        await update.message.reply_document(document=fb2_file, caption="Готово! 📖")

    except Exception as e:
        await update.message.reply_text(f"Ошибка при обработке: {str(e)}")

def generate_fb2(title, content_html, source_url):
    # Базовый шаблон FB2
    root = etree.Element("FictionBook", xmlns="http://www.gribuser.ru/xml/fictionbook/2.0")
    
    # Документ
    description = etree.SubElement(root, "description")
    title_info = etree.SubElement(description, "title-info")
    etree.SubElement(title_info, "genre").text = "nonfiction"
    etree.SubElement(title_info, "author").text = "Автор неизвестен"
    etree.SubElement(title_info, "book-title").text = title
    etree.SubElement(title_info, "date").text = "2025"
    etree.SubElement(title_info, "lang").text = "ru"
    
    # Тело книги
    body = etree.SubElement(root, "body")
    section = etree.SubElement(body, "section")
    p = etree.SubElement(section, "p")
    p.text = "Содержимое извлечено автоматически."
    
    # Добавляем HTML-контент (упрощённо)
    from lxml.html import fromstring
    html_tree = fromstring(content_html)
    for element in html_tree.xpath("//p"):
        p_elem = etree.SubElement(section, "p")
        p_elem.text = element.text_content() if element.text_content().strip() else ""
    
    # Превращаем в строку
    xml_str = etree.tostring(root, encoding='unicode', pretty_print=True)
    return f"""<?xml version="1.0" encoding="utf-8"?>
{xml_str}"""

if __name__ == '__main__':
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_url))
    app.run_polling()
