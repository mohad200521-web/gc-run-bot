import os
import re
import json
import uuid
import asyncio

from urllib.parse import urlparse, parse_qs, unquote, quote

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

from google.cloud import run_v2
from google.api_core.exceptions import GoogleAPICallError, NotFound
from google.oauth2 import service_account
import google.auth


TOKEN = os.getenv("BOT_TOKEN")

DEFAULT_REGION = os.getenv("DEFAULT_REGION", "us-central1")
SERVICE_NAME = os.getenv("SERVICE_NAME", "gc-run-service")
CONTAINER_IMAGE = os.getenv("CONTAINER_IMAGE")
GOOGLE_CREDENTIALS_JSON = os.getenv("GOOGLE_CREDENTIALS_JSON")

WS_PATH = "/vless"


URL_RE = re.compile(r"https?://\S+", re.I)


# =========================================================
# GOOGLE CREDENTIALS
# =========================================================

def get_google_credentials():

    if GOOGLE_CREDENTIALS_JSON:

        try:
            info = json.loads(GOOGLE_CREDENTIALS_JSON)

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

    return ""


async def deploy_cloud_run(
    project_id: str,
    vless_uuid: str,
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
            image=CONTAINER_IMAGE,
            env=[
                run_v2.types.EnvVar(
                    name="VLESS_UUID",
                    value=vless_uuid,
                ),
                run_v2.types.EnvVar(
                    name="WS_PATH",
                    value=WS_PATH,
                ),
            ],
        )

        template = run_v2.types.RevisionTemplate(
            containers=[container]
        )

        service = run_v2.types.Service(
            name=name,
            template=template,
        )

        try:

            await client.get_service(
                name=name
            )

            operation = await client.update_service(
                service=service
            )

        except NotFound:

            operation = await client.create_service(
                parent=parent,
                service=service,
                service_id=SERVICE_NAME,
            )

        result = await operation.result()

        url = service_url(result)

        if not url:

            return (
                False,
                "تم إنشاء الخدمة ولكن لم يتم الحصول على رابط Cloud Run."
            )

        return (
            True,
            url
        )

    except Exception as exc:

        return (
            False,
            f"{type(exc).__name__}: {exc}"
        )


# =========================================================
# VLESS LINK
# =========================================================

def create_vless_link(
    service_url_value: str,
    vless_uuid: str,
) -> str:

    host = service_url_value

    if host.startswith("https://"):
        host = host[8:]

    if host.startswith("http://"):
        host = host[7:]

    host = host.rstrip("/")

    path = quote(
        WS_PATH,
        safe="/"
    )

    return (
        f"vless://{vless_uuid}@{host}:443"
        f"?encryption=none"
        f"&security=tls"
        f"&type=ws"
        f"&host={host}"
        f"&path={path}"
        f"#GC.Run"
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
        "☁️ Google Cloud → Cloud Run\n"
        "🔐 VLESS / WebSocket\n\n"
        "📎 أرسل رابط المختبر أو Project ID.\n\n"
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
        "2️⃣ أرسل Project ID\n"
        "3️⃣ البوت ينشئ UUID تلقائيًا\n"
        "4️⃣ ينشئ/يحدّث Cloud Run\n"
        "5️⃣ يرسل رابط VLESS\n\n"
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

    project = context.user_data.get("project_id")

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
            "أرسل Project ID مباشرة."
        )

        return

    context.user_data["project_id"] = project_id
    context.user_data["cancelled"] = False

    # إنشاء UUID جديد
    vless_uuid = str(uuid.uuid4())

    context.user_data["vless_uuid"] = vless_uuid

    progress = await update.message.reply_text(
        "☁️ GC.Run\n\n"
        "✅ تم استلام Project ID.\n"
        "🔐 تم إنشاء UUID جديد.\n"
        "🚀 جاري إنشاء Cloud Run..."
    )

    steps = [
        "1️⃣ التحقق من Project ID...",
        f"2️⃣ Project ID: {project_id}",
        "3️⃣ إنشاء UUID لـ VLESS...",
        "4️⃣ إنشاء/تحديث Cloud Run...",
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
        project_id,
        vless_uuid,
    )

    if not ok:

        await progress.edit_text(
            "❌ فشل النشر.\n\n"
            f"السبب:\n{result}"
        )

        return

    vless_link = create_vless_link(
        result,
        vless_uuid,
    )

    await progress.edit_text(
        "🎉 تم إنشاء الخدمة!\n\n"
        f"☁️ Cloud Run:\n{result}\n\n"
        "🔐 VLESS:\n"
        f"`{vless_link}`\n\n"
        "✅ تم إنشاء UUID تلقائيًا."
        ,
        parse_mode="Markdown",
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