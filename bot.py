import logging
import os
import sys
import re
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

        # Извлечение текста
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

        # Создание XML
        wrapper = f"<doc>{extracted}</doc>"
        tree = etree.fromstring(wrapper.encode("utf-8"))

        # --- УЛУЧШЕННОЕ ПОЛУЧЕНИЕ ЗАГОЛОВКА ---
        # Пытаемся найти заголовок разными способами
        title = "Без названия"
        
        # 1. Ищем в метаданных trafilatura
        title_elem = tree.find(".//title")
        if title_elem is not None and title_elem.text:
            title = title_elem.text.strip()
        
        # 2. Если не нашли, ищем в метатегах HTML
        if title == "Без названия":
            meta_title = tree.find(".//meta[@property='og:title']")
            if meta_title is not None and meta_title.get('content'):
                title = meta_title.get('content').strip()
        
        # 3. Если всё ещё нет, ищем заголовок h1
        if title == "Без названия":
            h1_elem = tree.find(".//h1")
            if h1_elem is not None and h1_elem.text:
                title = h1_elem.text.strip()
        
        # Очищаем заголовок для имени файла
        # Удаляем несколько пробелов/переносов на один пробел
        title_clean = re.sub(r'\s+', ' ', title)
        # Удаляем символы, недопустимые в именах файлов
        title_clean = re.sub(r'[<>:"/\\|?*]', '', title_clean)
        # Обрезаем до разумной длины (макс 50 символов)
        if len(title_clean) > 50:
            title_clean = title_clean[:47] + "..."
        
        # Если после очистки осталась пустая строка
        if not title_clean:
            title_clean = "Статья"
        
        filename = f"{title_clean}.fb2"

        # Создание FB2 структуры
        fb2_root = etree.Element(
            "FictionBook", 
            xmlns="http://www.gribuser.ru/xml/fictionbook/2.0"
        )
        
        desc = etree.SubElement(fb2_root, "description")
        title_info = etree.SubElement(desc, "title-info")
        etree.SubElement(title_info, "book-title").text = title
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
        
        logger.info(f"Успешно создан FB2: {filename} для ссылки: {url}")

    except Exception as e:
        logger.error(f"Ошибка при обработке {url}: {e}")
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
