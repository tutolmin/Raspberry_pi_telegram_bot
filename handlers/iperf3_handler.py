import os
import glob
import json
import subprocess
from telegram import Update
from telegram.ext import CallbackContext
from datetime import datetime, timezone
from typing import Dict, Any

def format_speed_report(data: Dict[str, Any]) -> str:
    try:
        # Получаем информацию о подключении
        start_data = data.get("start", {})
        connected = start_data.get("connected", [])
        remote_host = connected[0].get("remote_host", "??") if connected else "??"

        # Получаем временную метку
        timestamp_data = start_data.get("timestamp", {})
        timestamp_str = timestamp_data.get("time", "???")

        # Парсим время и конвертируем в локальную зону сервера
        try:
            if timestamp_str != "???":
                # Парсим время (предполагаем что оно в UTC, т.к. в строке указан GMT)
                dt = datetime.strptime(timestamp_str, "%a, %d %b %Y %H:%M:%S %Z")
                # Добавляем UTC timezone
                dt_utc = dt.replace(tzinfo=timezone.utc)
                # Конвертируем в локальный часовой пояс сервера
                dt_local = dt_utc.astimezone()
                timestamp = dt_local.strftime("%Y-%m-%d %H:%M:%S")
            else:
                timestamp = "???"
        except:
            timestamp = timestamp_str

        # Получаем итоговые данные из секции end
        end_data = data.get("end", {})
        sum_sent = end_data.get("sum_sent", {})
        sum_received = end_data.get("sum_received", {})
        sum_reverse = end_data.get("sum_sent_bidir_reverse", {})

        # Скорость загрузки (download) - это полученные данные (receiver)
        down_bps = sum_received.get("bits_per_second", 0)
        down_mbps = down_bps / 1_000_000

        # Скорость отдачи (upload) - это отправленные данные в обратном направлении
        up_bps = sum_reverse.get("bits_per_second", 0)
        up_mbps = up_bps / 1_000_000

        # Если нет обратного направления, используем sum_sent как upload
        if up_mbps == 0:
            up_bps = sum_sent.get("bits_per_second", 0)
            up_mbps = up_bps / 1_000_000

        # Получаем информацию о потерях и задержках из первого потока
        streams = end_data.get("streams", [])
        ping_info = {}
        loss_pct = 0

        if streams and len(streams) > 0:
            sender_info = streams[0].get("sender", {})
            if sender_info:
                ping_info = {
                    "min_rtt": sender_info.get("min_rtt", 0) / 1000,  # конвертируем в ms
                    "max_rtt": sender_info.get("max_rtt", 0) / 1000,
                    "mean_rtt": sender_info.get("mean_rtt", 0) / 1000
                }
                # Расчет потерь на основе retransmits
                total_packets = sender_info.get("bytes", 0) / 1460  # приблизительно
                retransmits = sender_info.get("retransmits", 0)
                if total_packets > 0:
                    loss_pct = (retransmits / total_packets) * 100

        # Функция для форматирования чисел
        def fmt(x):
            return f"{x:.3f}".rstrip('0').rstrip('.')

        # Формируем сообщение
        message_parts = [
            f"🌐 {remote_host} | 🕒 {timestamp}",
        ]

        if ping_info and ping_info["mean_rtt"] > 0:
            message_parts.append(
                f"📶 Ping: min={fmt(ping_info['min_rtt'])} ms, "
                f"avg={fmt(ping_info['mean_rtt'])} ms, "
                f"max={fmt(ping_info['max_rtt'])} ms"
            )

        if loss_pct > 0:
            message_parts.append(f"⚠️ Packet loss: {loss_pct:.2f}%")

        message_parts.extend([
            f"📥 Download: {fmt(down_mbps)} Mbps",
            f"📤 Upload: {fmt(up_mbps)} Mbps"
        ])

        # Добавляем информацию о ретрансмиссиях если есть
        total_retransmits = sum_sent.get("retransmits", 0)
        if total_retransmits > 0:
            message_parts.append(f"🔄 Retransmits: {total_retransmits}")

        return "\n".join(message_parts)

    except Exception as e:
        return f"⚠️ Error formatting report: {e}"

async def iperf3_command_handler(update: Update, context: CallbackContext) -> None:
    if not context.args:
        # Новый путь к файлам с результатами
        runs_dir = os.path.expanduser("~/.local/share/iperf3/runs/")

        # Ищем все JSON файлы в директории runs
        json_files = glob.glob(os.path.join(runs_dir, "*.json"))

        if not json_files:
            await update.message.reply_text("No previous speed test reports found.")
            return

        # Берем самый последний файл по времени модификации
        latest_file = max(json_files, key=os.path.getmtime)

        try:
            with open(latest_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            message = format_speed_report(data)
            await update.message.reply_text(message)
        except Exception as e:
            await update.message.reply_text(f"❌ Failed to read or parse report: {e}")
        return

    arg = context.args[0].lower()
    if arg == "run":
        try:
            # Перезапускаем сервис через systemctl --user
            result = subprocess.run(
                ["systemctl", "--user", "restart", "iperf3-speedtest.service"],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                await update.message.reply_text("🚀 Speed test started via systemd service.")
            else:
                await update.message.reply_text(f"❌ Failed to restart service:\n{result.stderr}")
        except subprocess.TimeoutExpired:
            await update.message.reply_text("⚠️ Timeout restarting service")
        except Exception as e:
            await update.message.reply_text(f"💥 Error: {str(e)}")
    else:
        await update.message.reply_text("❌ Wrong command. Use `/iperf3` or `/iperf3 run`.")
