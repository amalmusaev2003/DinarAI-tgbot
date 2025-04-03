import re
import logging
import asyncio
from aiogram.exceptions import TelegramRetryAfter, TelegramBadRequest
from aiogram.enums import ParseMode

from config import MAX_RETRIES, INITIAL_RETRY_DELAY

async def safe_delete_message(bot, chat_id, message_id):
    """Safely delete a message with proper error handling."""
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
    """Send a message with retry logic for rate limits and errors."""
    retry_delay = INITIAL_RETRY_DELAY
    
    for attempt in range(MAX_RETRIES):
        try:
            return await message_obj.answer(text, parse_mode=parse_mode)
        except TelegramRetryAfter as e:
            retry_after = e.retry_after
            logging.warning(f"Rate limit hit. Waiting for {retry_after} seconds. Attempt {attempt+1}/{MAX_RETRIES}")
            await asyncio.sleep(retry_after)
        except Exception as e:
            logging.error(f"Error sending message: {e}")
            if attempt == MAX_RETRIES - 1:  # Last attempt
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