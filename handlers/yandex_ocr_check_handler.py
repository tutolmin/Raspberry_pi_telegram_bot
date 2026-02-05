# handlers/yandex_ocr_check_handler.py
import os
import json
import time
from telegram import Update
from telegram.ext import CallbackContext
from dotenv import load_dotenv

import jwt  # pyjwt[crypto]
import yandexcloud
from yandex.cloud.iam.v1.iam_token_service_pb2 import CreateIamTokenRequest
from yandex.cloud.iam.v1.iam_token_service_pb2_grpc import IamTokenServiceStub

load_dotenv()

KEY_PATH = os.getenv("YANDEX_SERVICE_ACCOUNT_KEY_PATH")
if not KEY_PATH:
    raise ValueError("❌ Missing YANDEX_SERVICE_ACCOUNT_KEY_PATH in .env")


def create_jwt(sa_key: dict) -> str:
    private_key = sa_key["private_key"]
    key_id = sa_key["id"]
    service_account_id = sa_key["service_account_id"]
    now = int(time.time())
    payload = {
        "aud": "https://iam.api.cloud.yandex.net/iam/v1/tokens",
        "iss": service_account_id,
        "iat": now,
        "exp": now + 3600
    }
    return jwt.encode(
        payload,
        private_key,
        algorithm="PS256",
        headers={"kid": key_id}
    )


async def yandex_ocr_check_command(update: Update, context: CallbackContext) -> None:
    try:
        # === 1. Загрузка ключа ===
        if not os.path.exists(KEY_PATH):
            await update.message.reply_text(f"❌ Key file not found: {KEY_PATH}")
            return

        with open(KEY_PATH, "r", encoding="utf-8") as f:
            key_data = json.load(f)

        sa_key = {
            "id": key_data["id"],
            "service_account_id": key_data["service_account_id"],
            "private_key": key_data["private_key"]
        }

        # === 2. Генерация JWT ===
        jwt_token = create_jwt(sa_key)

        # === 3. Получение IAM-токена через gRPC (как в вашем скрипте) ===
        sdk = yandexcloud.SDK()
        iam_service = sdk.client(IamTokenServiceStub)
        iam_resp = iam_service.Create(CreateIamTokenRequest(jwt=jwt_token))
        iam_token = iam_resp.iam_token

        # Проверка, что токен не пустой
        if iam_token and len(iam_token) > 10:
            await update.message.reply_text("✅ Yandex IAM token obtained successfully → OCR endpoint is ready")
        else:
            await update.message.reply_text("❌ Received empty or invalid IAM token")

    except FileNotFoundError:
        await update.message.reply_text(f"❌ Key file not found: {KEY_PATH}")
    except json.JSONDecodeError:
        await update.message.reply_text("❌ Invalid JSON in service account key file")
    except jwt.InvalidKeyError as e:
        await update.message.reply_text(f"❌ JWT signing error: {str(e)}")
    except Exception as e:
        await update.message.reply_text(f"💥 Error: {str(e)}")
