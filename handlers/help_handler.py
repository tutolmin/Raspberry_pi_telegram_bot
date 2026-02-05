# handlers/help_handler.py
from telegram import Update
from telegram.ext import CallbackContext

async def help_command(update: Update, context: CallbackContext) -> None:
    help_text = (
        "/cameras - Get cameras list\n\n"
        "/checklist - System readiness check\n\n"
        "/cpu - Get CPU usage\n\n"
        "/disk - Get disk usage\n\n"
        "/exec <command> - Execute a command\n\n"
        "/gigachat - Check GigaChat\n\n"
        "/gpio - Get GPIO status\n\n"
        "/help - Show this help message\n\n"
        "/info - Get system information\n\n"
        "/ip - Get IP addresses\n\n"
        "/loadavg - Get load averages\n\n"
        "/netinfo - Get network interfaces\n\n"
        "/ocr - Check Yandex OCR\n\n"
        "/ping - Ping a host\n\n"
        "/ram - Get RAM usage\n\n"
        "/reboot - Reboot the system. use at for the exact time and in for countdown\n\n"
        "/services <all|failed|running> - Show services\n\n"
        "/service - Manage services\n\n"
        "/shutdown - Shutdown the system. use at for the exact time and in for countdown\n\n"
        "/speedtest [run] - Check internet speed\n\n"
        "/sysstat - Check system status (loadavg, cpu, ram, uptime)\n\n"
        "/temperature - Get CPU temperature\n\n"
        "/uptime - Get system uptime\n\n"
        "/watches - Check watches\n\n"
    )
    await update.message.reply_text(help_text)
