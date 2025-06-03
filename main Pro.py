import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Updater, CommandHandler, CallbackQueryHandler, 
    MessageHandler, Filters, CallbackContext
)
import yt_dlp

# إعدادات التسجيل
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# إعدادات الحساب
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
INSTAGRAM_LINK = os.getenv('INSTAGRAM_LINK', 'https://instagram.com/your_account')
SUBSCRIBED_USERS = set()

# ============== وظائف البوت الأساسية ==============

def start(update: Update, context: CallbackContext) -> None:
    """معالجة أمر /start"""
    user = update.effective_user
    chat_id = update.effective_chat.id
    
    # التحقق من متابعة الإنستجرام
    if chat_id not in SUBSCRIBED_USERS:
        show_instagram_prompt(update)
        return
        
    welcome_message = (
        f"مرحبًا {user.first_name}! 👋\n\n"
        "أنا بوت التنزيل الذكي 🚀\n"
        "أرسل لي رابط أي فيديو، صورة أو أغنية وسأحاول تنزيلها لك.\n\n"
        "📌 *كيفية الاستخدام:*\n"
        "1. أرسل رابط المحتوى\n"
        "2. اختر الجودة المطلوبة\n"
        "3. انتظر حتى أرسل لك الملف"
    )
    
    update.message.reply_text(welcome_message, parse_mode='Markdown')

def show_instagram_prompt(update: Update):
    """عرض رسالة متابعة الإنستجرام"""
    keyboard = [
        [InlineKeyboardButton("متابعة الإنستجرام", url=INSTAGRAM_LINK)],
        [InlineKeyboardButton("✅ تمت المتابعة", callback_data="subscribed")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    update.message.reply_text(
        "⏳ يرجى متابعة حسابنا على الإنستجرام أولاً",
        reply_markup=reply_markup
    )

def handle_callback(update: Update, context: CallbackContext) -> None:
    """معالجة الضغط على الأزرار"""
    query = update.callback_query
    query.answer()
    
    if query.data == "subscribed":
        SUBSCRIBED_USERS.add(query.message.chat.id)
        query.edit_message_text("شكرًا للمتابعة! ✅\nيمكنك الآن استخدام البوت.\nأرسل /start للبدء.")

def handle_url(update: Update, context: CallbackContext) -> None:
    """معالجة الروابط المرسلة"""
    chat_id = update.effective_chat.id
    if chat_id not in SUBSCRIBED_USERS:
        show_instagram_prompt(update)
        return
        
    url = update.message.text
    try:
        # الحصول على معلومات الفيديو
        ydl_opts = {'quiet': True}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            
        # إنشاء زر اختيار الجودة
        formats = info.get('formats', [])
        quality_options = []
        
        # جمع خيارات الجودة المتاحة
        unique_qualities = set()
        for f in formats:
            if f.get('height'):
                quality = f"{f['height']}p"
                if quality not in unique_qualities and f.get('vcodec') != 'none':
                    unique_qualities.add(quality)
                    quality_options.append(InlineKeyboardButton(quality, callback_data=f"quality_{quality}"))
        
        if not quality_options:
            update.message.reply_text("⚠️ لم أتمكن من العثور على خيارات جودة لهذا المحتوى.")
            return
            
        # حفظ معلومات الفيديو مؤقتًا
        context.user_data['video_info'] = info
        context.user_data['video_url'] = url
        
        # إرسال خيارات الجودة
        keyboard = [quality_options[i:i+3] for i in range(0, len(quality_options), 3)]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        update.message.reply_text("📊 اختر جودة التنزيل:", reply_markup=reply_markup)
        
    except Exception as e:
        logger.error(f"Error processing URL: {e}")
        update.message.reply_text("❌ حدث خطأ أثناء معالجة الرابط. يرجى المحاولة مرة أخرى.")

def handle_quality(update: Update, context: CallbackContext) -> None:
    """معالجة اختيار الجودة"""
    query = update.callback_query
    query.answer()
    
    _, quality = query.data.split('_')
    
    if 'video_info' not in context.user_data:
        query.edit_message_text(text="❌ انتهت صلاحية المعلومات. يرجى إرسال الرابط مرة أخرى.")
        return
    
    info = context.user_data['video_info']
    url = context.user_data['video_url']
    
    query.edit_message_text(text=f"⏳ جاري تنزيل الفيديو بجودة {quality}...")
    
    try:
        # تنزيل الفيديو بالجودة المحددة
        ydl_opts = {
            'format': f'bestvideo[height<={quality[:-1]}]+bestaudio/best[height<={quality[:-1]}]',
            'outtmpl': 'downloads/%(title)s.%(ext)s',
            'quiet': True,
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            file_path = ydl.prepare_filename(info)
            
        # إرسال الفيديو للمستخدم
        with open(file_path, 'rb') as video_file:
            context.bot.send_video(
                chat_id=query.message.chat_id,
                video=video_file,
                caption=f"✅ تم التنزيل بنجاح بجودة {quality}"
            )
        
        # حذف الملف بعد الإرسال
        os.remove(file_path)
        
    except Exception as e:
        logger.error(f"Error downloading video: {e}")
        context.bot.send_message(
            chat_id=query.message.chat_id,
            text="❌ حدث خطأ أثناء تنزيل الفيديو. يرجى المحاولة مرة أخرى."
        )

def error_handler(update: Update, context: CallbackContext) -> None:
    """معالجة الأخطاء"""
    logger.error(f'Update {update} caused error {context.error}')
    if update.effective_message:
        update.effective_message.reply_text("❌ حدث خطأ غير متوقع. يرجى المحاولة لاحقًا.")

# ============== التشغيل الرئيسي ==============

def main() -> None:
    # إنشاء البوت
    updater = Updater(TELEGRAM_TOKEN)
    dispatcher = updater.dispatcher

    # تسجيل المعالجات
    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(CallbackQueryHandler(handle_callback))
    dispatcher.add_handler(MessageHandler(Filters.text & (~Filters.command), handle_url))
    dispatcher.add_handler(CallbackQueryHandler(handle_quality, pattern="^quality_"))
    dispatcher.add_error_handler(error_handler)

    # بدء البوت
    updater.start_polling()
    logger.info("Bot started successfully")
    updater.idle()

if __name__ == '__main__':
    main()
