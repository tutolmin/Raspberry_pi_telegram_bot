# handlers/sysstat_handler.py
from telegram import Update
from telegram.ext import CallbackContext
from utils.pi_info import get_cameras

async def cameras_command(update: Update, context: CallbackContext) -> None:
    cameras = get_cameras()
    await update.message.reply_text(cameras)
