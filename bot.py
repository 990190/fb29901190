import logging
import os
import sys
import re
import html
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters
import trafilatura
from lxml import etree

# --- 1. НАСТРОЙКА И ЗАГРУЗКА ТОКЕНА ---
BOT_TOKEN = os.environ.get("BOT_TOKEN")
if not BOT_TOKEN:
    print("❌ ОШИБКА: Переменная окружения BOT_TOKEN не задана!")
    sys.exit(1)

# --- 2. НАСТРОЙКА ЛОГИРОВАНИЯ ---
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- 3. ФУНКЦИИ БОТА ---
async def start(update: Update, context):
    await update.message.reply_text(
        "Привет! Отправь мне ссылку на статью в интернете, "
        "и я конвертирую её в электронную книгу в формате FB2."
    )

async def handle_url(update: Update, context):
    url = update.message.text.strip()
    
    if not url.startswith(('http://', 'https://')):
        await update.message.reply_text(
            "Пожалуйста, отправь корректную ссылку, "
            "начинающуюся с http:// или https://"
        )
        return

    wait_msg = await update.message.reply_text("⏳ Загружаю и обрабатываю статью...")

    try:
        # Скачивание страницы
        downloaded = trafilatura.fetch_url(url)
        if not downloaded:
            await update.message.reply_text("❌ Не удалось загрузить страницу по этой ссылке.")
            await wait_msg.delete()
            return

        # --- ПРЯМОЕ ИЗВЛЕЧЕНИЕ ЗАГОЛОВКА ИЗ HTML ---
        # Ищем заголовок в исходном HTML
        title = "Статья"  # значение по умолчанию
        
        # Способ 1: Ищем <title> в HTML
        title_match = re.search(r'<title[^>]*>(.*?)</title>', downloaded, re.IGNORECASE | re.DOTALL)
        if title_match:
            title = html.unescape(title_match.group(1).strip())
        
        # Способ 2: Ищем Open Graph заголовок
        if title == "Статья":
            og_match = re.search(r'<meta[^>]*property=["\']og:title["\'][^>]*content=["\'](.*?)["\']', downloaded, re.IGNORECASE)
            if og_match:
                title = html.unescape(og_match.group(1).strip())
        
        # Способ 3: Ищем h1 заголовок
        if title == "Статья":
            h1_match = re.search(r'<h1[^>]*>(.*?)</h1>', downloaded, re.IGNORECASE | re.DOTALL)
            if h1_match:
                # Удаляем HTML-теги внутри h1
                h1_text = re.sub(r'<[^>]+>', '', h1_match.group(1))
                title = html.unescape(h1_text.strip())
        
        # Очищаем заголовок для имени файла
        # Удаляем переносы строк и лишние пробелы
        title_clean = re.sub(r'\s+', ' ', title)
        # Удаляем недопустимые символы для файлов
        title_clean = re.sub(r'[<>:"/\\|?*]', '', title_clean)
        # Обрезаем длину
        if len(title_clean) > 50:
            title_clean = title_clean[:47] + "..."
        
        # Если после очистки пусто
        if not title_clean or title_clean.isspace():
            title_clean = "Статья"
            
        filename = f"{title_clean}.fb2"

        # Извлечение текста через trafilatura (для контента)
        extracted = trafilatura.extract(
            downloaded,
            include_comments=False,
            output_format="xml",
            with_metadata=True
        )
        if not extracted:
            await update.message.reply_text(
                "❌ Не удалось извлечь читаемый текст со страницы. "
                "Возможно, сайт защищен от копирования."
            )
            await wait_msg.delete()
            return

        # Создание XML для контента
        wrapper = f"<doc>{extracted}</doc>"
        tree = etree.fromstring(wrapper.encode("utf-8"))

        # Создание FB2 структуры
        fb2_root = etree.Element(
            "FictionBook", 
            xmlns="http://www.gribuser.ru/xml/fictionbook/2.0"
        )
        
        desc = etree.SubElement(fb2_root, "description")
        title_info = etree.SubElement(desc, "title-info")
        etree.SubElement(title_info, "book-title").text = title  # Оригинальный заголовок
        etree.SubElement(title_info, "lang").text = "ru"

        body = etree.SubElement(fb2_root, "body")
        section = etree.SubElement(body, "section")

        # Добавление абзацев
        for p in tree.xpath(".//p"):
            para_text = (p.text or "").strip()
            if para_text:
                para = etree.SubElement(section, "p")
                para.text = para_text

        # Генерация файла
        fb2_bytes = etree.tostring(
            fb2_root, 
            encoding="utf-8", 
            xml_declaration=True, 
            pretty_print=True
        )

        # Отправка файла
        await wait_msg.delete()
        await update.message.reply_document(
            document=fb2_bytes,
            filename=filename,
            caption=f"📖 {title_clean}"
        )
        
        logger.info(f"Успешно создан FB2: {filename} (ориг: {title[:30]}...) для {url}")

    except Exception as e:
        logger.error(f"Ошибка при обработке {url}: {e}", exc_info=True)
        await update.message.reply_text(
            f"⚠️ Произошла внутренняя ошибка: {str(e)[:150]}"
        )
        try:
            await wait_msg.delete()
        except:
            pass

# --- 4. ЗАПУСК БОТА ---
def main():
    """Запускает бота в режиме polling"""
    print("=== Бот начал запуск ===")
    print(f"Токен получен: {'ДА' if BOT_TOKEN else 'НЕТ'}")

    # Создаем приложение
    application = Application.builder().token(BOT_TOKEN).build()

    # Регистрируем обработчики
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_url))

    # Запускаем бота
    print("Бот запускается в режиме polling...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
