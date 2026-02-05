# handlers/watches_handler.py
from telegram import Update
from telegram.ext import CallbackContext
from utils.watch_notifier_ipc import send_bt_message

WATCH_ADDRESSES = ["2C:BC:BB:A7:DE:3A"]

async def watches_command(update: Update, context: CallbackContext) -> None:
    failed = []
    for mac in WATCH_ADDRESSES:
        if not send_bt_message(mac, "Health check"):
            failed.append(mac)

    if failed:
        await update.message.reply_text(
            f"❌ Failed to send to: {', '.join(failed)}"
        )
    else:
        await update.message.reply_text(
            f"✅ Health check sent to {len(WATCH_ADDRESSES)} watch(es)"
        )
