# GC.Run Telegram Bot

بوت Telegram ينشئ/يحدّث خدمة Cloud Run باستخدام هوية Google Cloud المصرّح لها.

## متغيرات البيئة

- `BOT_TOKEN` = توكن BotFather
- `CONTAINER_IMAGE` = صورة الحاوية التي تريد نشرها
- `DEFAULT_REGION` = `us-central1`
- `SERVICE_NAME` = `gc-run-service`

## مهم

هذا الإصدار لا يطلب ولا يخزن كلمات مرور Google أو رموز SSO.
الرابط يستخدم فقط لاستخراج Project ID، أما عملية Cloud Run فتتم بواسطة
حساب الخدمة/هوية Google Cloud التي تشغّل البوت.

## الصلاحيات

الهوية التي تشغّل البوت تحتاج صلاحيات Cloud Run المناسبة على المشروع الهدف،
كما يجب أن تكون صورة الحاوية متاحة للـ Cloud Run.
