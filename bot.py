import os
import asyncio

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

TOKEN = os.getenv("BOT_TOKEN")


# =========================================================
# START
# =========================================================

async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    await update.message.reply_text(
        "👋 أهلاً بك في GC.Run\n\n"
        "🤖 البوت يعمل الآن على Blitz\n"
        "🟢 التشغيل مستقل عن Google Cloud Lab\n\n"
        "📌 لا تحتاج إلى Project ID.\n"
        "📌 لا تحتاج إلى Cloud Run.\n\n"
        "/help — طريقة الاستخدام\n"
        "/status — حالة البوت"
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
        "2️⃣ استخدم الأوامر المتاحة\n"
        "3️⃣ البوت يعمل من Blitz في الخلفية\n\n"
        "☁️ لا يوجد اعتماد على Google Cloud Lab."
    )


# =========================================================
# STATUS
# =========================================================

async def status(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    await update.message.reply_text(
        "📊 حالة البوت\n\n"
        "🟢 Bot: Online\n"
        "🟢 Blitz: Running in background\n"
        "☁️ Google Cloud: غير مستخدم\n"
        "🚀 Cloud Run: غير مستخدم"
    )


# =========================================================
# MESSAGE
# =========================================================

async def handle_message(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    if not update.message or not update.message.text:
        return

    await update.message.reply_text(
        "✅ وصلت رسالتك.\n\n"
        "هذا الإصدار من البوت لا يحتاج إلى "
        "Project ID أو Google Cloud."
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