import logging
import os
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters
import trafilatura
from lxml import etree

# --- 1. НАСТРОЙКА И ЗАГРУЗКА ТОКЕНА ---
# Получаем токен из переменных окружения Render
BOT_TOKEN = os.environ.get("BOT_TOKEN")
if not BOT_TOKEN:
    logging.error("ОШИБКА: Переменная окружения BOT_TOKEN не задана!")
    exit(1)

# --- 2. НАСТРОЙКА ЛОГИРОВАНИЯ ---
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- 3. ФУНКЦИИ БОТА (остаются почти такими же, как у вас) ---
async def start(update: Update, context):
    """Обработчик команды /start"""
    await update.message.reply_text("Привет! Отправь мне ссылку на статью в интернете, и я конвертирую её в электронную книгу в формате FB2.")

async def handle_url(update: Update, context):
    """Обработчик текстовых сообщений (ссылок)"""
    url = update.message.text.strip()
    # Простая проверка на ссылку
    if not url.startswith(('http://', 'https://')):
        await update.message.reply_text("Пожалуйста, отправь корректную ссылку, начинающуюся с http:// или https://")
        return

    # Сообщаем пользователю, что началась работа
    wait_msg = await update.message.reply_text("⏳ Загружаю и обрабатываю статью...")

    try:
        # Пытаемся скачать и извлечь текст
        downloaded = trafilatura.fetch_url(url)
        if not downloaded:
            await update.message.reply_text("❌ Не удалось загрузить страницу по этой ссылке.")
            await wait_msg.delete()
            return

        extracted = trafilatura.extract(
            downloaded,
            include_comments=False,
            output_format="xml",
            with_metadata=True
        )
        if not extracted:
            await update.message.reply_text("❌ Не удалось извлечь читаемый текст со страницы. Возможно, сайт защищен от копирования.")
            await wait_msg.delete()
            return

        # Формируем XML и конвертируем в FB2
        wrapper = f"<doc>{extracted}</doc>"
        tree = etree.fromstring(wrapper.encode("utf-8"))

        title_elem = tree.find(".//title")
        title = title_elem.text if title_elem is not None and title_elem.text else "Без названия"
        # Очищаем название для имени файла
        safe_filename = "".join(c for c in title if c.isalnum() or c in (' ', '-', '_')).rstrip()
        safe_filename = safe_filename[:30] if safe_filename else "book"

        # Создаем структуру FB2
        fb2_root = etree.Element("FictionBook", xmlns="http://www.gribuser.ru/xml/fictionbook/2.0")
        desc = etree.SubElement(fb2_root, "description")
        title_info = etree.SubElement(desc, "title-info")
        etree.SubElement(title_info, "book-title").text = title
        etree.SubElement(title_info, "lang").text = "ru"

        body = etree.SubElement(fb2_root, "body")
        section = etree.SubElement(body, "section")

        # Переносим все абзацы <p> из извлеченного текста
        for p in tree.xpath(".//p"):
            para_text = (p.text or "").strip()
            if para_text:  # Добавляем только непустые абзацы
                para = etree.SubElement(section, "p")
                para.text = para_text

        # Генерируем итоговый файл
        fb2_bytes = etree.tostring(fb2_root, encoding="utf-8", xml_declaration=True, pretty_print=True)
        filename = f"{safe_filename}.fb2"

        # Удаляем сообщение "ждем" и отправляем файл
        await wait_msg.delete()
        await update.message.reply_document(
            document=fb2_bytes,
            filename=filename,
            caption=f"Вот ваша книга: '{title}'"
        )
        logger.info(f"Успешно создан FB2: {filename} для ссылки: {url}")

    except Exception as e:
        logger.error(f"Ошибка при обработке {url}: {e}")
        await update.message.reply_text(f"⚠️ Произошла внутренняя ошибка при обработке ссылки: {str(e)[:150]}")

# --- 4. ГЛАВНАЯ ФУНКЦИЯ ЗАПУСКА ---
def main():
    """Запускает бота в режиме polling"""
    # Создаем приложение
    application = Application.builder().token(BOT_TOKEN).build()

    # Регистрируем обработчики команд и сообщений
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_url))

    # ЗАПУСКАЕМ БОТА В РЕЖИМЕ ОПРОСА (POLLING)
    logger.info("Бот запускается в режиме polling...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
