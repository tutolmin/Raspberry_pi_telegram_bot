# handlers/crop_handler.py
import os
import subprocess
import configparser
import logging
from pathlib import Path
from telegram import Update
from telegram.ext import CallbackContext

# Импортируем состояние из отдельного модуля (нет циклической зависимости)
#from bot_state import start_preview_task, stop_preview_task, PREVIEW_CHAT_ID
import bot_state

logger = logging.getLogger(__name__)

CONFIG_FILE = Path.home() / ".config" / "cam_service.ini"
SERVICE_NAME = "cam_capture.service"

async def grid_command(update: Update, context: CallbackContext) -> None:
    """
    Обработчик команды /grid.
    Включает или отключает наложение сетки на изображение.
    Использование: /grid on | /grid off
    """
    user_id = update.effective_user.id
    args = context.args

    # Проверка аргумента
    if not args or len(args) != 1 or args[0].lower() not in ['on', 'off', 'true', 'false', '1', '0']:
        await update.message.reply_text(
            "❌ Некорректное использование команды.\n"
            "Формат: <code>/grid on</code> или <code>/grid off</code>\n\n"
            "• <code>on</code> / <code>true</code> / <code>1</code> — включить сетку\n"
            "• <code>off</code> / <code>false</code> / <code>0</code> — выключить сетку",
            parse_mode='HTML'
        )
        return

    # Нормализация значения
    value = args[0].lower()
    grid_enabled = value in ['on', 'true', '1']
    status_text = "включена" if grid_enabled else "отключена"
    emoji = "🔲" if grid_enabled else "🖼️"

    try:
        # Чтение текущего конфига
        config = configparser.ConfigParser()
        config.read(CONFIG_FILE)

        if 'capture' not in config:
            config['capture'] = {}

        # Обновление параметра grid
        section = 'capture'
        config[section]['grid'] = str(grid_enabled)

        # Запись конфига
        with open(CONFIG_FILE, 'w') as f:
            config.write(f)

        logger.info(f"User {user_id}: Grid {'enabled' if grid_enabled else 'disabled'}")

        # Отправка SIGHUP сервису для перечитки конфига
        result = subprocess.run(
            ["systemctl", "--user", "kill", "-s", "HUP", SERVICE_NAME],
            capture_output=True,
            text=True,
            timeout=10
        )

        if result.returncode == 0:
            await update.message.reply_text(
                f"{emoji} Сетка {status_text}.\n"
                f"🔄 Сервис перечитал конфигурацию (SIGHUP)\n"
                f"💡 Изменение применится к следующему кадру",
                parse_mode='HTML'
            )
        else:
            logger.warning(f"Failed to send SIGHUP: {result.stderr}")
            await update.message.reply_text(
                f"⚠️ Конфиг обновлён ({status_text}), но не удалось уведомить сервис.\n"
                f"Перезапустите вручную: <code>systemctl --user restart {SERVICE_NAME}</code>",
                parse_mode='HTML'
            )

    except FileNotFoundError:
        await update.message.reply_text(
            f"❌ Файл конфигурации не найден: {CONFIG_FILE}\n"
            "Убедитесь, что сервис камеры был хотя бы раз запущен."
        )
        logger.error(f"Config file not found: {CONFIG_FILE}")

    except PermissionError:
        await update.message.reply_text(
            "❌ Ошибка прав доступа к файлу конфигурации.\n"
            "Проверьте права пользователя на запись в ~/.config/"
        )
        logger.error(f"Permission denied writing to {CONFIG_FILE}")

    except subprocess.TimeoutExpired:
        await update.message.reply_text("⏱️ Таймаут при отправке сигнала сервису.")
        logger.error("Timeout sending SIGHUP to service")

    except Exception as e:
        await update.message.reply_text(f"❌ Неожиданная ошибка: {type(e).__name__}: {e}")
        logger.exception("Unexpected error in grid_command")

async def crop_status_command(update: Update, context: CallbackContext) -> None:
    """Показывает текущие настройки кропа из конфига."""
    try:
        config = configparser.ConfigParser()
        config.read(CONFIG_FILE)

        if 'capture' not in config:
            await update.message.reply_text("❌ Секция [capture] не найдена в конфиге")
            return

        c = config['capture']
        status = (
            "📊 <b>Текущие настройки кропа:</b>\n\n"
            f"🔘 Включено: <code>{c.get('crop_enabled', 'False')}</code>\n"
            f"📍 Позиция: x=<code>{c.get('crop_x', '?')}</code>, y=<code>{c.get('crop_y', '?')}</code>\n"
            f"📏 Размер: <code>{c.get('crop_width', '?')}</code>×<code>{c.get('crop_height', '?')}</code>\n\n"
            f"🖼️ Сенсор: <code>{c.get('sensor_width', '?')}</code>×<code>{c.get('sensor_height', '?')}</code>"
        )
        await update.message.reply_text(status, parse_mode='HTML')

    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка чтения конфига: {e}")
        logger.exception("Error reading crop status")

async def crop_reset_command(update: Update, context: CallbackContext) -> None:
    """
    Обработчик команды /cropreset.
    Сбрасывает параметры кропа к полному размеру сенсора.
    """
    user_id = update.effective_user.id

    try:
        # Чтение текущего конфига
        config = configparser.ConfigParser()
        config.read(CONFIG_FILE)

        if 'capture' not in config:
            await update.message.reply_text(
                "❌ Секция [capture] не найдена в конфиге.\n"
                "Убедитесь, что сервис камеры был хотя бы раз запущен."
            )
            return

        section = 'capture'

        # Получаем размеры сенсора (или дефолтные значения)
        sensor_width = int(config.get(section, 'sensor_width', fallback='4608'))
        sensor_height = int(config.get(section, 'sensor_height', fallback='2592'))

        # Сбрасываем параметры кропа к полному сенсору
        config[section]['crop_enabled'] = 'False'  # Отключаем кроп (опционально)
        config[section]['crop_x'] = '0'
        config[section]['crop_y'] = '0'
        config[section]['crop_width'] = str(sensor_width)
        config[section]['crop_height'] = str(sensor_height)

        # Запись конфига
        with open(CONFIG_FILE, 'w') as f:
            config.write(f)

        logger.info(f"User {user_id}: Reset crop to full sensor {sensor_width}x{sensor_height}")

        # Отправка SIGHUP сервису
        result = subprocess.run(
            ["systemctl", "--user", "kill", "-s", "HUP", SERVICE_NAME],
            capture_output=True,
            text=True,
            timeout=10
        )

        if result.returncode == 0:
            await update.message.reply_text(
                f"✅ Кроп сброшен к полному сенсору!\n"
                f"🖼️ Размер: <code>{sensor_width}×{sensor_height}</code>\n"
                f"🔄 Сервис перечитал конфигурацию (SIGHUP)",
                parse_mode='HTML'
            )
        else:
            logger.warning(f"Failed to send SIGHUP: {result.stderr}")
            await update.message.reply_text(
                f"⚠️ Конфиг обновлён, но не удалось уведомить сервис.\n"
                f"Перезапустите вручную: <code>systemctl --user restart {SERVICE_NAME}</code>",
                parse_mode='HTML'
            )

    except FileNotFoundError:
        await update.message.reply_text(
            f"❌ Файл конфигурации не найден: {CONFIG_FILE}"
        )
        logger.error(f"Config file not found: {CONFIG_FILE}")

    except PermissionError:
        await update.message.reply_text("❌ Ошибка прав доступа к файлу конфигурации.")
        logger.error(f"Permission denied writing to {CONFIG_FILE}")

    except subprocess.TimeoutExpired:
        await update.message.reply_text("⏱️ Таймаут при отправке сигнала сервису.")

    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {type(e).__name__}: {e}")
        logger.exception("Unexpected error in crop_reset_command")

async def crop_command(update: Update, context: CallbackContext) -> None:
    """
    Обработчик команды /crop.
    Использование: /crop x y width height
    Пример: /crop 150 100 4400 2400
    """
    user_id = update.effective_user.id
    args = context.args
    
    # Проверка аргументов
    if not args or len(args) != 4:
        await update.message.reply_text(
            "❌ Некорректное использование команды.\n"
            "Формат: <code>/crop x y width height</code>\n"
            "Пример: <code>/crop 150 100 4400 2400</code>\n\n"
            "Параметры:\n"
            "• x, y — координаты левого верхнего угла области интереса\n"
            "• width, height — размеры области обрезки",
            parse_mode='HTML'
        )
        return

    try:
        # Парсинг и валидация значений
        crop_x = int(args[0])
        crop_y = int(args[1])
        crop_width = int(args[2])
        crop_height = int(args[3])
        
        # Базовая валидация (можно настроить под вашу камеру)
        if any(v < 0 for v in [crop_x, crop_y, crop_width, crop_height]):
            raise ValueError("Значения не могут быть отрицательными")
        if crop_width == 0 or crop_height == 0:
            raise ValueError("Ширина и высота должны быть больше 0")
            
    except ValueError as e:
        await update.message.reply_text(f"❌ Ошибка парсинга: {e}")
        return

    try:
        # Чтение текущего конфига
        config = configparser.ConfigParser()
        config.read(CONFIG_FILE)
        
        if 'capture' not in config:
            config['capture'] = {}
        
        # Обновление параметров кропа
        section = 'capture'
        config[section]['crop_enabled'] = 'True'  # Авто-включение кропа
        config[section]['crop_x'] = str(crop_x)
        config[section]['crop_y'] = str(crop_y)
        config[section]['crop_width'] = str(crop_width)
        config[section]['crop_height'] = str(crop_height)
        
        # Запись конфига
        with open(CONFIG_FILE, 'w') as f:
            config.write(f)
        
        logger.info(f"User {user_id}: Updated crop settings to x={crop_x}, y={crop_y}, w={crop_width}, h={crop_height}")
        
        # Отправка SIGHUP сервису для перечитки конфига
        # Используем systemctl --user kill для отправки сигнала
        result = subprocess.run(
            ["systemctl", "--user", "kill", "-s", "HUP", SERVICE_NAME],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode == 0:
            await update.message.reply_text(
                f"✅ Настройки кропа обновлены!\n"
                f"📐 x={crop_x}, y={crop_y}\n"
                f"📏 {crop_width}×{crop_height}\n"
                f"🔄 Сервис перечитал конфигурацию (SIGHUP)",
                parse_mode='HTML'
            )
        else:
            # Сервис мог быть неактивен, но конфиг всё равно сохранён
            logger.warning(f"Failed to send SIGHUP: {result.stderr}")
            await update.message.reply_text(
                f"⚠️ Конфиг обновлен, но не удалось уведомить сервис.\n"
                f"Попробуйте перезапустить сервис вручную:\n"
                f"<code>systemctl --user restart {SERVICE_NAME}</code>",
                parse_mode='HTML'
            )
            
    except FileNotFoundError:
        await update.message.reply_text(
            f"❌ Файл конфигурации не найден: {CONFIG_FILE}\n"
            "Убедитесь, что сервис камеры был хотя бы раз запущен."
        )
        logger.error(f"Config file not found: {CONFIG_FILE}")
        
    except PermissionError:
        await update.message.reply_text(
            "❌ Ошибка прав доступа к файлу конфигурации.\n"
            "Проверьте права пользователя на запись в ~/.config/"
        )
        logger.error(f"Permission denied writing to {CONFIG_FILE}")
        
    except subprocess.TimeoutExpired:
        await update.message.reply_text("⏱️ Таймаут при отправке сигнала сервису.")
        logger.error("Timeout sending SIGHUP to service")
        
    except Exception as e:
        await update.message.reply_text(f"❌ Неожиданная ошибка: {type(e).__name__}: {e}")
        logger.exception("Unexpected error in crop_command")

# В handlers/crop_handler.py замените preview_command на:

async def preview_command(update: Update, context: CallbackContext) -> None:
    """
    Обработчик команды /preview.
    Включает или отключает режим превью.
    """
    user_id = update.effective_user.id
    args = context.args
    
    if not args or len(args) != 1 or args[0].lower() not in ['on', 'off', 'true', 'false', '1', '0']:
        await update.message.reply_text(
            "❌ Некорректное использование команды.\n"
            "Формат: <code>/preview on</code> или <code>/preview off</code>",
            parse_mode='HTML'
        )
        return

    value = args[0].lower()
    preview_enabled = value in ['on', 'true', '1']
    status_text = "включён" if preview_enabled else "выключен"
    emoji = "📹" if preview_enabled else "⏹️"
    
    try:
        config = configparser.ConfigParser()
        config.read(CONFIG_FILE)
        
        if 'capture' not in config:
            config['capture'] = {}
        
        section = 'capture'
        config[section]['preview_enabled'] = str(preview_enabled)
        
        with open(CONFIG_FILE, 'w') as f:
            config.write(f)
        
        logger.info(f"User {user_id}: Preview {'enabled' if preview_enabled else 'disabled'}")
        
        # Управление задачей через bot_state (БЕЗ импорта из main!)
        if preview_enabled:
            bot_state.PREVIEW_CHAT_ID = update.effective_chat.id
            bot_state.start_preview_task(context.application)
        else:
            bot_state.stop_preview_task()

        # Отправка SIGHUP сервису камеры
        result = subprocess.run(
            ["systemctl", "--user", "kill", "-s", "HUP", SERVICE_NAME],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode == 0:
            await update.message.reply_text(
                f"{emoji} Режим превью {status_text}.\n"
                f"🔄 Сервис камеры перечитал конфигурацию\n"
                f"{'📸 Фото будут отправляться в канал каждые 3 секунды' if preview_enabled else '🛑 Отправка фото остановлена'}",
                parse_mode='HTML'
            )
        else:
            await update.message.reply_text(
                f"⚠️ Конфиг обновлён, но не удалось уведомить сервис камеры.\n"
                f"Перезапустите: <code>systemctl --user restart cam_capture.service</code>",
                parse_mode='HTML'
            )
            
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {type(e).__name__}: {e}")
        logger.exception("Unexpected error in preview_command")
