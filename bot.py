import os
import re
import json
import asyncio

from urllib.parse import urlparse, parse_qs, unquote

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

from google.cloud import run_v2
from google.api_core.exceptions import GoogleAPICallError
from google.oauth2 import service_account
import google.auth


TOKEN = os.getenv("BOT_TOKEN")

DEFAULT_REGION = os.getenv(
    "DEFAULT_REGION",
    "us-central1"
)

SERVICE_NAME = os.getenv(
    "SERVICE_NAME",
    "gc-run-service"
)

CONTAINER_IMAGE = os.getenv(
    "CONTAINER_IMAGE"
)

GOOGLE_CREDENTIALS_JSON = os.getenv(
    "GOOGLE_CREDENTIALS_JSON"
)

URL_RE = re.compile(
    r"https?://\S+",
    re.I
)


# =========================================================
# GOOGLE CREDENTIALS
# =========================================================

def get_google_credentials():

    if GOOGLE_CREDENTIALS_JSON:

        try:
            info = json.loads(
                GOOGLE_CREDENTIALS_JSON
            )

            return service_account.Credentials.from_service_account_info(
                info,
                scopes=[
                    "https://www.googleapis.com/auth/cloud-platform"
                ],
            )

        except Exception as exc:
            raise RuntimeError(
                "GOOGLE_CREDENTIALS_JSON غير صالح: "
                f"{type(exc).__name__}: {exc}"
            )

    try:
        credentials, _ = google.auth.default()
        return credentials

    except Exception as exc:
        raise RuntimeError(
            "لم يتم العثور على Google Cloud credentials.\n"
            f"{type(exc).__name__}: {exc}"
        )


# =========================================================
# PROJECT ID
# =========================================================

def extract_project_id(text: str) -> str | None:

    candidates = [text]

    for url in URL_RE.findall(text):
        candidates.append(url)

    for value in candidates:

        decoded = unquote(value)

        parsed = urlparse(decoded)

        query = parse_qs(parsed.query)

        for key in ("project", "project_id"):

            if key in query and query[key]:

                project = query[key][0].strip()

                if re.fullmatch(
                    r"[a-z][a-z0-9-]{4,28}[a-z0-9]",
                    project
                ):
                    return project

        match = re.search(
            r"project(?:%3D|=)"
            r"([a-z][a-z0-9-]{4,28}[a-z0-9])",
            decoded,
        )

        if match:
            return match.group(1)

    value = text.strip()

    if re.fullmatch(
        r"[a-z][a-z0-9-]{4,28}[a-z0-9]",
        value
    ):
        return value

    return None


# =========================================================
# CLOUD RUN
# =========================================================

def service_url(service: run_v2.Service) -> str:

    if service.uri:
        return service.uri

    return "(لم يتم إرجاع رابط الخدمة)"


async def deploy_cloud_run(
    project_id: str
) -> tuple[bool, str]:

    if not CONTAINER_IMAGE:

        return (
            False,
            "لم يتم ضبط CONTAINER_IMAGE في Blitz."
        )

    try:

        credentials = get_google_credentials()

        client = run_v2.ServicesAsyncClient(
            credentials=credentials
        )

        parent = (
            f"projects/{project_id}"
            f"/locations/{DEFAULT_REGION}"
        )

        name = (
            f"{parent}"
            f"/services/{SERVICE_NAME}"
        )

        container = run_v2.types.Container(
            image=CONTAINER_IMAGE
        )

        template = run_v2.types.RevisionTemplate(
            containers=[container]
        )

        # لا نستخدم IngressTraffic هنا
        # لأن النسخة الحالية من مكتبة google-cloud-run
        # لا تحتوي عليه داخل Service

        service = run_v2.types.Service(
            name=name,
            template=template,
        )

        try:

            existing = await client.get_service(
                name=name
            )

            service.name = existing.name

            operation = await client.update_service(
                service=service
            )

        except GoogleAPICallError:

            operation = await client.create_service(
                parent=parent,
                service=service,
                service_id=SERVICE_NAME,
            )

        result = await operation.result()

        return (
            True,
            service_url(result)
        )

    except Exception as exc:

        return (
            False,
            f"{type(exc).__name__}: {exc}"
        )


# =========================================================
# START
# =========================================================

async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    await update.message.reply_text(
        "👋 أهلاً بك في GC.Run\n\n"
        "☁️ Google Cloud → Cloud Run\n\n"
        "📎 أرسل رابط Google Cloud/Skills "
        "الذي يحتوي على Project ID.\n\n"
        "مثال:\n"
        "https://www.cloudskillsboost.google/...\n\n"
        "/help — طريقة الاستخدام\n"
        "/cancel — إلغاء العملية\n"
        "/status — حالة الإعداد"
    )


# =========================================================
# HELP
# =========================================================

async def help_cmd(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    await update.message.reply_text(
        "📖 طريقة الاستخدام:\n\n"
        "1️⃣ اضغط /start\n"
        "2️⃣ أرسل رابط المختبر\n"
        "3️⃣ البوت يستخرج Project ID\n"
        "4️⃣ ينشئ أو يحدّث Cloud Run\n"
        "5️⃣ يرسل رابط الخدمة\n\n"
        "⚠️ لا ترسل كلمات مرور Google "
        "أو رموز تسجيل الدخول."
    )


# =========================================================
# CANCEL
# =========================================================

async def cancel(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    context.user_data["cancelled"] = True

    await update.message.reply_text(
        "🛑 تم إلغاء العملية الحالية."
    )


# =========================================================
# STATUS
# =========================================================

async def status(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    project = context.user_data.get(
        "project_id"
    )

    if project:

        await update.message.reply_text(
            f"📊 الحالة:\n\n"
            f"Project ID: {project}"
        )

    else:

        await update.message.reply_text(
            "📊 لا توجد عملية حالية."
        )


# =========================================================
# MESSAGE
# =========================================================

async def handle_message(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not update.message:
        return

    if not update.message.text:
        return

    project_id = extract_project_id(
        update.message.text
    )

    if not project_id:

        await update.message.reply_text(
            "❌ لم أجد Project ID.\n\n"
            "أرسل رابط المختبر أو Project ID مباشرة."
        )

        return

    context.user_data["project_id"] = project_id
    context.user_data["cancelled"] = False

    progress = await update.message.reply_text(
        "☁️ GC.Run\n\n"
        "✅ تم استلام الرابط.\n"
        "🔎 جاري استخراج Project ID..."
    )

    steps = [
        "1️⃣ فتح الرابط...",
        f"2️⃣ Project ID: {project_id}",
        "3️⃣ التحقق من Cloud Run...",
        "4️⃣ إنشاء/تحديث الخدمة...",
    ]

    for index, step in enumerate(steps):

        if context.user_data.get("cancelled"):
            return

        await asyncio.sleep(0.5)

        await progress.edit_text(
            "☁️ GC.Run\n\n"
            + "\n".join(
                steps[:index + 1]
            )
        )

    ok, result = await deploy_cloud_run(
        project_id
    )

    if ok:

        await progress.edit_text(
            "🎉 تم النشر بنجاح!\n\n"
            "🔗 الرابط:\n"
            f"{result}\n\n"
            "✅ Cloud Run يعمل."
        )

    else:

        await progress.edit_text(
            "❌ فشل النشر.\n\n"
            f"السبب:\n{result}"
        )


# =========================================================
# MAIN
# =========================================================

def main():

    if not TOKEN:
        raise RuntimeError(
            "BOT_TOKEN غير مضبوط في Blitz."
        )

    app = (
        Application
        .builder()
        .token(TOKEN)
        .build()
    )

    app.add_handler(
        CommandHandler("start", start)
    )

    app.add_handler(
        CommandHandler("help", help_cmd)
    )

    app.add_handler(
        CommandHandler("cancel", cancel)
    )

    app.add_handler(
        CommandHandler("status", status)
    )

    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            handle_message
        )
    )

    print("GC.Run bot started")

    app.run_polling()


if __name__ == "__main__":
    main()