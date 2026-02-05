# handlers/llm_check_handler.py
import os
import requests
from telegram import Update
from telegram.ext import CallbackContext
from dotenv import load_dotenv

# Загружаем переменные окружения один раз при импорте
load_dotenv()

# === Настройки из .env ===
AUTHORIZATION_KEY = os.getenv("GIGACHAT_CREDENTIALS")
if not AUTHORIZATION_KEY:
    raise ValueError("❌ Missing GIGACHAT_CREDENTIALS in .env")

CA_BUNDLE = "/etc/ssl/certs/ca-certificates.crt"
RQ_UID = "35a720de-1c09-4244-aec2-b0dd896bab7b"

OAUTH_URL = "https://ngw.devices.sberbank.ru:9443/api/v2/oauth"
MODELS_URL = "https://gigachat.devices.sberbank.ru/api/v1/models"

async def giga_check_command(update: Update, context: CallbackContext) -> None:
    try:
        # Шаг 1: Получить access token
        oauth_headers = {
            'Content-Type': 'application/x-www-form-urlencoded',
            'Accept': 'application/json',
            'RqUID': RQ_UID,
            'Authorization': f'Basic {AUTHORIZATION_KEY}'
        }
        oauth_payload = {'scope': 'GIGACHAT_API_PERS'}

        oauth_resp = requests.post(
            OAUTH_URL,
            headers=oauth_headers,
            data=oauth_payload,
            timeout=10,
            verify=CA_BUNDLE  # ← явная проверка
        )
        oauth_resp.raise_for_status()
        access_token = oauth_resp.json().get('access_token')
        if not access_token:
            await update.message.reply_text("❌ Failed to extract access_token from OAuth response.")
            return

        # Шаг 2: Запрос списка моделей
        models_headers = {
            'Accept': 'application/json',
            'Authorization': f'Bearer {access_token}'
        }
        models_resp = requests.get(MODELS_URL, headers=models_headers, timeout=10, verify=CA_BUNDLE)
        models_resp.raise_for_status()

        # Извлекаем имена моделей
        models_data = models_resp.json()
        model_names = [m.get('id', 'unknown') for m in models_data.get('data', [])]
        if model_names:
            models_list = ", ".join(model_names)
            message = f"✅ GigaChat API is UP\nModels: {models_list}"
        else:
            message = "✅ GigaChat API is UP (no models listed)"

        await update.message.reply_text(message)

    except requests.exceptions.Timeout:
        await update.message.reply_text("⚠️ Timeout while connecting to GigaChat API")
    except requests.exceptions.HTTPError as e:
        status = e.response.status_code
        text = e.response.text[:200].strip()
        await update.message.reply_text(f"❌ HTTP {status}: {text}")
    except requests.exceptions.RequestException as e:
        await update.message.reply_text(f"❌ Network error: {str(e)}")
    except Exception as e:
        await update.message.reply_text(f"💥 Unexpected error: {str(e)}")
