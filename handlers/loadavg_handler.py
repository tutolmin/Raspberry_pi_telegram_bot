# handlers/loadavg_handler.py
from telegram import Update
from telegram.ext import CallbackContext
from utils.pi_info import get_loadavg

async def loadavg_command(update: Update, context: CallbackContext) -> None:
    loadavg = get_loadavg()
    await update.message.reply_text(loadavg)
