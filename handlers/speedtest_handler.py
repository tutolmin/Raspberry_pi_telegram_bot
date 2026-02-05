import os
import glob
import json
import subprocess
from telegram import Update
from telegram.ext import CallbackContext
from datetime import datetime, timezone

def format_speed_report(data: dict) -> str:
    try:
        country = data.get("meta", {}).get("country", "??")
        server = data.get("server", "??")

        utc_str = data.get("timestamp_utc")
        if utc_str:
            dt_utc = datetime.fromisoformat(utc_str.replace("Z", "+00:00")).replace(tzinfo=timezone.utc)
            timestamp = dt_utc.astimezone().strftime("%Y-%m-%d %H:%M:%S")
        else:
            timestamp = "???"

        idle_lat = data.get("idle_latency", {})
        ping_median = int(idle_lat.get("median_ms", 0))
        loss_pct = round(idle_lat.get("loss", 0) * 100)

        down_mbps = data.get("download", {}).get("mbps", 0)
        up_mbps = data.get("upload", {}).get("mbps", 0)

        # Округляем до 3 знаков после запятой, но убираем лишние нули через форматирование
        def fmt(x):
            return f"{x:.3f}".rstrip('0').rstrip('.')

        return (
            f"🌐 {country} → {server} | 🕒 {timestamp}\n"
            f"📶 Idle ping: {ping_median} ms (loss: {loss_pct}%)\n"
            f"📥 Down: {fmt(down_mbps)} Mbps\n"
            f"📤 Up: {fmt(up_mbps)} Mbps"
        )
    except Exception as e:
        return f"⚠️ Error formatting report: {e}"

async def speedtest_command_handler(update: Update, context: CallbackContext) -> None:
    if not context.args:
        # Find the latest report
        runs_dir = os.path.expanduser("~/.local/share/cloudflare-speed-cli/runs/")
        json_files = glob.glob(os.path.join(runs_dir, "run-*.json"))
        if not json_files:
            await update.message.reply_text("No previous speed test reports found.")
            return

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
                ["systemctl", "--user", "restart", "cloudflare-speedtest.service"],
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
#        cmd = [os.path.expanduser("~/.local/bin/cloudflare-speed-cli"), "--json", "--silent"]
#        try:
#            subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
#            await update.message.reply_text("🚀 Started new speed test in background.")
#        except Exception as e:
#            await update.message.reply_text(f"❌ Failed to start speed test: {str(e)}")
    else:
        await update.message.reply_text("❌ Wrong command. Use `/speedtest` or `/speedtest run`.")
