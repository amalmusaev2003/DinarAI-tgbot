import logging
import asyncio
import aiohttp
from aiogram import types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.enums import ParseMode

from config import API_HOST, API_TIMEOUT
from states import UserStates
from utils import safe_send_message, safe_delete_message, markdown_to_html

# Store bot instance to be set from main.py
bot = None

def register_bot(bot_instance):
    """Register the bot instance for use in handlers."""
    global bot
    bot = bot_instance

# Command handlers
async def cmd_start(message: types.Message, state: FSMContext):
    """Handle /start command: reset state and send welcome message."""
    await state.clear()
    
    await message.answer(
        "Ассаламу алейкум! 👋\n\n"
        "Я бот-ассистент по исламским финансам. Задайте мне вопрос, и я постараюсь на него ответить.\n\n"
        "Чтобы начать, просто напишите ваш вопрос."
    )
    await state.set_state(UserStates.waiting_for_question)


async def cmd_help(message: types.Message):
    """Handle /help command: show available commands and instructions."""
    await message.answer(
        "Я могу ответить на ваши вопросы об исламских финансах.\n\n"
        "Просто напишите ваш вопрос, и я постараюсь помочь.\n\n"
        "Доступные команды:\n"
        "/start - Начать общение\n"
        "/help - Показать эту справку"
    )


async def process_question(message: types.Message, state: FSMContext):
    """Process user questions by sending them to the API and formatting responses."""
    chat_id = message.chat.id
    question = message.text
    processing_message = None
    
    try:
        # Send "processing" message
        processing_message = await safe_send_message(message, "Обрабатываю ваш вопрос...")
    except Exception as e:
        logging.error(f"Failed to send processing message: {e}")
        return
    
    try:
        # Prepare API request
        payload = {
            "chat_id": chat_id,
            "question": question
        }
        
        # Send request to API
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{API_HOST}/chat", 
                json=payload, 
                timeout=aiohttp.ClientTimeout(total=API_TIMEOUT)
            ) as response:
                if response.status == 200:
                    # Process successful response
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


async def echo(message: types.Message):
    """Handle any other messages."""
    await message.answer("Пожалуйста, задайте ваш вопрос об исламских финансах.")


def register_handlers(dp):
    """Register all handlers with the dispatcher."""
    dp.message.register(cmd_start, Command('start'))
    dp.message.register(cmd_help, Command('help'))
    dp.message.register(process_question, UserStates.waiting_for_question)
    dp.message.register(echo)