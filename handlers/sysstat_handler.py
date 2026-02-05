# handlers/sysstat_handler.py
from telegram import Update
from telegram.ext import CallbackContext
from utils.pi_info import get_loadavg, get_uptime, get_cpu_usage, get_ram_usage

async def sysstat_command(update: Update, context: CallbackContext) -> None:
    loadavg = get_loadavg()
    uptime = get_uptime()
    ram = get_ram_usage()
    cpu = get_cpu_usage()
    await update.message.reply_text(uptime + "\n" + loadavg + "\n\n" + cpu + "\n\n" + ram)
