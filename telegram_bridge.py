import os
from dotenv import load_dotenv
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters
from telegram import Update
import asyncio

# Load environment variables
load_dotenv()

async def start(update: Update, context):
    await update.message.reply_text("Hey there. I'm Maya.")

async def mirror_mode(update: Update, context):
    await update.message.reply_text(f"Echo: {update.message.text}")

def setup_telegram_bot(token):
    application = ApplicationBuilder().token(token).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), mirror_mode))

    return application

if __name__ == "__main__":
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    
    if not token:
        print("ERROR: Please set TELEGRAM_BOT_TOKEN in your .env file.")
    else:
        app = setup_telegram_bot(token)
        print("Starting Telegram bot.")
        asyncio.run(app.run_polling())
