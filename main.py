import os
import logging
import aiohttp
import asyncio
import re
from aiogram import Bot, Dispatcher, types
from aiogram.fsm.storage.redis import RedisStorage
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.exceptions import TelegramRetryAfter, TelegramBadRequest


logging.basicConfig(level=logging.INFO)


class UserStates(StatesGroup):
    waiting_for_question = State()


REDIS_HOST = os.getenv('REDIS_HOST', 'localhost')
REDIS_PORT = int(os.getenv('REDIS_PORT', 6379))
REDIS_DB = int(os.getenv('REDIS_DB', 0))


token = os.getenv('TG_BOT_API_KEY')
if token is None:
    raise ValueError("BOT_TOKEN environment variable is not set")


storage = RedisStorage.from_url(f'redis://{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}')
bot = Bot(token=token)
dp = Dispatcher(storage=storage)


async def safe_delete_message(bot, chat_id, message_id):
    try:
        await bot.delete_message(chat_id=chat_id, message_id=message_id)
    except TelegramBadRequest as e:
        if "message to delete not found" in str(e):
            logging.warning(f"Message {message_id} already deleted or not found")
        else:
            logging.error(f"Error deleting message: {e}")
    except Exception as e:
        logging.error(f"Error deleting message: {e}")


async def safe_send_message(message_obj, text, parse_mode=None):
    max_retries = 5
    retry_delay = 1
    
    for attempt in range(max_retries):
        try:
            return await message_obj.answer(text, parse_mode=parse_mode)
        except TelegramRetryAfter as e:
            retry_after = e.retry_after
            logging.warning(f"Rate limit hit. Waiting for {retry_after} seconds. Attempt {attempt+1}/{max_retries}")
            await asyncio.sleep(retry_after)
        except Exception as e:
            logging.error(f"Error sending message: {e}")
            if attempt == max_retries - 1:  # Last attempt
                raise
            await asyncio.sleep(retry_delay)
            retry_delay *= 2  # Exponential backoff


def markdown_to_html(text: str) -> str:
    """Convert markdown formatting to HTML for Telegram."""
    text = re.sub(r'^### (.*?)$', r'<b><i>\1</i></b>', text, flags=re.MULTILINE)  # H3 as bold italic
    text = re.sub(r'^## (.*?)$', r'<b>\1</b>', text, flags=re.MULTILINE)  # H2 as bold
    text = re.sub(r'^# (.*?)$', r'<b><u>\1</u></b>', text, flags=re.MULTILINE)  # H1 as bold underlined
    
    text = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', text)
    
    text = re.sub(r'\*(.*?)\*', r'<i>\1</i>', text)
    
    text = re.sub(r'`(.*?)`', r'<code>\1</code>', text)
    
    return text

# Обработчик команды /start
@dp.message(Command('start'))
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()
    
    await message.answer(
        "Ассаламу алейкум! 👋\n\n"
        "Я бот-ассистент по исламским финансам. Задайте мне вопрос, и я постараюсь на него ответить.\n\n"
        "Чтобы начать, просто напишите ваш вопрос."
    )
    await state.set_state(UserStates.waiting_for_question)


@dp.message(Command('help'))
async def cmd_help(message: types.Message):
    await message.answer(
        "Я могу ответить на ваши вопросы об исламских финансах.\n\n"
        "Просто напишите ваш вопрос, и я постараюсь помочь.\n\n"
        "Доступные команды:\n"
        "/start - Начать общение\n"
        "/help - Показать эту справку"
    )


@dp.message(UserStates.waiting_for_question)
async def process_question(message: types.Message, state: FSMContext):
    chat_id = message.chat.id
    question = message.text
    
    try:
        processing_message = await safe_send_message(message, "Обрабатываю ваш вопрос...")
    except Exception as e:
        logging.error(f"Failed to send processing message: {e}")
        return
    
    try:
        payload = {
            "chat_id": chat_id,
            "question": question
        }
        
        # Отправка запроса к API
        async with aiohttp.ClientSession() as session:
            api_host = os.getenv("API_HOST")
            if api_host is None:
                raise ValueError("API_HOST environment variable is not set")
            
            # Add timeout to API request
            async with session.post(f"{api_host}/chat", json=payload, timeout=aiohttp.ClientTimeout(total=240)) as response:
                if response.status == 200:
                    data = await response.json()
                    # Convert markdown to HTML
                    answer = markdown_to_html(data.get("answer", "Извините, не удалось получить ответ."))
                    sources = data.get("sources", [])
                    
                    # Формирование ответа
                    response_text = f"{answer}\n\n"
                    
                    # Добавление источников, если они есть
                    if sources:
                        response_text += "📚 <b>Источники:</b>\n"
                        for i, source in enumerate(sources, 1):
                            response_text += f"{i}. {markdown_to_html(source)}\n"
                    
                    # Safely delete processing message
                    if processing_message:
                        await safe_delete_message(bot, processing_message.chat.id, processing_message.message_id)
                    
                    # Safely send the answer with retry logic
                    await safe_send_message(message, response_text, parse_mode=ParseMode.HTML)
                else:
                    # Safely delete processing message
                    if processing_message:
                        await safe_delete_message(bot, processing_message.chat.id, processing_message.message_id)
                    
                    await safe_send_message(message, "Извините, произошла ошибка при обработке вашего запроса. Пожалуйста, попробуйте позже.")
    except asyncio.TimeoutError:
        logging.error("API request timed out")
        if processing_message:
            await safe_delete_message(bot, processing_message.chat.id, processing_message.message_id)
        await safe_send_message(message, "Извините, запрос занял слишком много времени. Пожалуйста, попробуйте позже.")
    except Exception as e:
        logging.error(f"Error processing question: {e}")
        if processing_message:
            await safe_delete_message(bot, processing_message.chat.id, processing_message.message_id)
        await safe_send_message(message, "Извините, произошла ошибка. Пожалуйста, попробуйте позже.")


@dp.message()
async def echo(message: types.Message):
    await message.answer("Пожалуйста, задайте ваш вопрос об исламских финансах.")


async def main():
    logging.info("Starting bot")
    await dp.start_polling(bot, skip_updates=True)

if __name__ == '__main__':
    asyncio.run(main())