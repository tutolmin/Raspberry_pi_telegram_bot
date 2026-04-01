# bot_state.py
import asyncio
from pathlib import Path

# Глобальное состояние
preview_task = None
preview_enabled = False
PREVIEW_CHAT_ID = None
PREVIEW_FILE = Path("/mnt/ram_cam/preview.jpg")
PREVIEW_INTERVAL = 5  # секунды

def start_preview_task(application):
    """Запускает фоновую задачу превью."""
    global preview_task, preview_enabled
    
    if preview_task is None or preview_task.done():
        preview_enabled = True
        preview_task = asyncio.create_task(send_preview(application))

def stop_preview_task():
    """Останавливает фоновую задачу превью."""
    global preview_task, preview_enabled
    
    preview_enabled = False
    if preview_task and not preview_task.done():
        preview_task.cancel()

async def send_preview(application):
    """Фоновая задача для отправки превью в канал."""
    global preview_enabled
    
    while preview_enabled:
        try:
            if PREVIEW_FILE.exists():
                stat = PREVIEW_FILE.stat()
                if stat.st_size > 0:
                    with open(PREVIEW_FILE, 'rb') as photo:
                        await application.bot.send_photo(
                            chat_id=PREVIEW_CHAT_ID,
                            photo=photo,
                            caption="📹 Live Preview"
                        )
        except Exception as e:
            # Тихая ошибка, чтобы не спамить в логи при отсутствии фото
            pass
        
        await asyncio.sleep(PREVIEW_INTERVAL)
