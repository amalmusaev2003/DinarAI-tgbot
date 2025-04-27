import logging
import asyncio
import aiohttp
from aiogram import types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.enums import ParseMode
from aiogram.types import BotCommand

from config import API_HOST, API_TIMEOUT
from states import UserStates
from utils import safe_send_message, safe_delete_message, markdown_to_html


bot = None

def register_bot(bot_instance):
    global bot
    bot = bot_instance

    asyncio.create_task(setup_bot_commands(bot))

async def setup_bot_commands(bot_instance):
    commands = [
        BotCommand(command="start", description="Информация о боте"),
        BotCommand(command="help", description="Показать справку"),
        BotCommand(command="restart", description="Перезапустить диалог")
    ]
    await bot_instance.set_my_commands(commands)


async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()

    await message.answer(
        "🌙 <b>Добро пожаловать в DinarAI!</b> 🌙\n\n"
        "Я ваш персональный эксперт по исламским финансам, готовый помочь вам разобраться в:\n"
        "• 🏦 Исламском банкинге\n"
        "• 📊 Финансовых инструментах, соответствующих шариату\n"
        "Просто задайте вопрос, и я предоставлю вам подробный ответ!.\n\n"
        "<i>Ваш путь к этичным финансам начинается здесь!</i>",
        parse_mode=ParseMode.HTML
    )
    await state.set_state(UserStates.waiting_for_question)


async def cmd_help(message: types.Message):
    await message.answer(
        "Я могу ответить на ваши вопросы об исламских финансах.\n\n"
        "Просто напишите ваш вопрос, и я постараюсь помочь.\n\n"
        "Доступные команды:\n"
        "/start - Информация о боте\n"
        "/help - Показать эту справку\n"
        "/restart - Перезапустить диалог"
    )


async def cmd_restart(message: types.Message, state: FSMContext):
    await state.clear()
    
    await message.answer(
        "Диалог перезапущен. Вы можете задать новый вопрос."
    )
    
    await state.set_state(UserStates.waiting_for_question)


async def process_question(message: types.Message, state: FSMContext):
    chat_id = message.chat.id
    question = message.text
    processing_message = None
    
    try:
        processing_message = await safe_send_message(message, "Обрабатываю ваше сообщение...")
    except Exception as e:
        logging.error(f"Failed to send processing message: {e}")
        return
    
    try:
        payload = {
            "chat_id": chat_id,
            "question": question
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{API_HOST}/chat", 
                json=payload, 
                timeout=aiohttp.ClientTimeout(total=API_TIMEOUT)
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    answer = markdown_to_html(data.get("answer", "Извините, не удалось получить ответ."))
                    sources = data.get("urls", [])
                    logging.info(f"Sources (raw): {sources}")
                    logging.info(f"Sources type: {type(sources)}")

                    response_text = f"{answer}\n\n"

                    if sources:
                        response_text += "📚 <b>Источники:</b>\n"
                        for i, source in enumerate(sources, 1):
                            response_text += f"{i}. {markdown_to_html(source)}\n"

                    if processing_message:
                        await safe_delete_message(bot, processing_message.chat.id, processing_message.message_id)

                    await safe_send_message(message, response_text, parse_mode=ParseMode.HTML)
                else:
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


async def echo(message: types.Message, state: FSMContext):
    await message.answer("Пожалуйста, задайте ваш вопрос об исламских финансах.")


def register_handlers(dp):
    dp.message.register(cmd_start, Command('start'))
    dp.message.register(cmd_help, Command('help'))
    dp.message.register(cmd_restart, Command('restart'))
    dp.message.register(process_question, UserStates.waiting_for_question)
    dp.message.register(echo)