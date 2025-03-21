import os
import logging
import aiohttp
import asyncio
import re
from fastapi import FastAPI, Request
from contextlib import asynccontextmanager
from aiogram import Bot, Dispatcher, types
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramRetryAfter, TelegramBadRequest

# Настройка логирования с подробным выводом
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Получение токена
token = os.getenv('TG_BOT_API_KEY')
if token is None:
    raise ValueError("BOT_TOKEN environment variable is not set")

# Инициализация бота и диспетчера
bot = Bot(token=token)
dp = Dispatcher()

# Lifespan-обработчик для запуска и завершения приложения
@asynccontextmanager
async def lifespan(app: FastAPI):
    webhook_url = 'https://your-service.onrender.com/webhook'  # Замените на ваш URL
    logger.info("Проверка текущего webhook...")
    current_webhook = await bot.get_webhook_info()
    if current_webhook.url != webhook_url:
        logger.info(f"Установка webhook на {webhook_url}")
        await bot.set_webhook(webhook_url)
        logger.info(f"Webhook успешно установлен на {webhook_url}")
    else:
        logger.info("Webhook уже установлен")
    yield
    logger.info("Удаление webhook перед завершением...")
    await bot.delete_webhook()
    await bot.session.close()
    logger.info("Webhook удален и сессия закрыта")

# Создание FastAPI-приложения с lifespan
app = FastAPI(lifespan=lifespan)

# Безопасная отправка сообщений с обработкой лимитов
async def safe_send_message(message_obj, text, parse_mode=None):
    max_retries = 5
    retry_delay = 1
    for attempt in range(max_retries):
        try:
            logger.info(f"Отправка сообщения: {text[:50]}...")
            return await message_obj.answer(text, parse_mode=parse_mode)
        except TelegramRetryAfter as e:
            retry_after = e.retry_after
            logger.warning(f"Лимит Telegram, ждем {retry_after} секунд, попытка {attempt+1}/{max_retries}")
            await asyncio.sleep(retry_after)
        except Exception as e:
            logger.error(f"Ошибка отправки сообщения: {e}")
            if attempt == max_retries - 1:
                raise
            await asyncio.sleep(retry_delay)
            retry_delay *= 2

# Конвертация Markdown в HTML
def markdown_to_html(text: str) -> str:
    text = re.sub(r'^### (.*?)$', r'<b><i>\1</i></b>', text, flags=re.MULTILINE)
    text = re.sub(r'^## (.*?)$', r'<b>\1</b>', text, flags=re.MULTILINE)
    text = re.sub(r'^# (.*?)$', r'<b><u>\1</u></b>', text, flags=re.MULTILINE)
    text = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', text)
    text = re.sub(r'\*(.*?)\*', r'<i>\1</i>', text)
    text = re.sub(r'`(.*?)`', r'<code>\1</code>', text)
    return text

# Обработка всех сообщений
@dp.message()
async def handle_message(message: types.Message):
    chat_id = message.chat.id
    question = message.text
    logger.info(f"Получено сообщение от {chat_id}: {question}")

    # Отправка запроса к API
    try:
        payload = {"chat_id": chat_id, "question": question}
        logger.info(f"Отправка запроса к API: {payload}")
        async with aiohttp.ClientSession() as session:
            api_host = os.getenv("API_HOST")
            if api_host is None:
                raise ValueError("API_HOST environment variable is not set")
            async with session.post(f"{api_host}/chat", json=payload, timeout=aiohttp.ClientTimeout(total=240)) as response:
                logger.info(f"Получен ответ от API с кодом {response.status}")
                if response.status == 200:
                    data = await response.json()
                    answer = markdown_to_html(data.get("answer", "Извините, не удалось получить ответ."))
                    sources = data.get("sources", [])
                    response_text = f"{answer}\n\n"
                    if sources:
                        response_text += "📚 <b>Источники:</b>\n"
                        for i, source in enumerate(sources, 1):
                            response_text += f"{i}. {markdown_to_html(source)}\n"
                    await safe_send_message(message, response_text, parse_mode=ParseMode.HTML)
                    logger.info("Ответ успешно отправлен пользователю")
                else:
                    await safe_send_message(message, "Извините, произошла ошибка при обработке вашего запроса.")
                    logger.error(f"API вернул ошибку: {response.status}")
    except asyncio.TimeoutError:
        logger.error("API запрос превысил время ожидания")
        await safe_send_message(message, "Извините, запрос занял слишком много времени.")
    except Exception as e:
        logger.error(f"Ошибка обработки запроса: {e}")
        await safe_send_message(message, "Извините, произошла ошибка.")

# Маршрут для проверки активности
@app.get("/")
async def home():
    logger.info("Получен запрос к /")
    return {"message": "I'm alive"}

# Маршрут для webhook
@app.post("/webhook")
async def webhook(request: Request):
    try:
        logger.info("Получен запрос к /webhook")
        update = types.Update(**(await request.json()))
        await dp.feed_update(bot, update)
        logger.info("Обновление успешно обработано")
        return {"status": "OK"}
    except Exception as e:
        logger.error(f"Ошибка в webhook: {e}")
        return {"status": "ERROR"}, 500

# Запуск приложения
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=75)