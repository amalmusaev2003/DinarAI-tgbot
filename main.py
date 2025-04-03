import logging
import asyncio
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.redis import RedisStorage

from keep_alive import keep_alive
from config import TG_BOT_API_KEY, REDIS_HOST, REDIS_PORT, REDIS_DB
from handlers import register_handlers, register_bot

# Configure logging
logging.basicConfig(level=logging.INFO)

# Start keep-alive thread
keep_alive()

async def main():
    """Initialize and start the bot."""
    # Initialize Redis storage
    storage = RedisStorage.from_url(f'redis://{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}')
    
    # Initialize bot and dispatcher
    bot = Bot(token=TG_BOT_API_KEY)
    dp = Dispatcher(storage=storage)
    
    # Register bot instance with handlers
    register_bot(bot)
    
    # Register all handlers
    register_handlers(dp)
    
    # Start polling
    logging.info("Starting bot")
    await dp.start_polling(bot, skip_updates=True)

if __name__ == '__main__':
    asyncio.run(main())