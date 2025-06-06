import logging
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.constants import ParseMode  # ייבוא חדש להדגשה
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
    ConversationHandler,
    JobQueue,
    CallbackQueryHandler,
)

# --- הגדרות בסיסיות ---
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logging.getLogger("httpx").setLevel(logging.WARNING)

TOKEN = '8045531024:AAH4acQo0uWrtU577TmChY73LdR_M_ElA2M'  # !!! החלף בטוקן חדש ובטוח !!!
TZ_ISRAEL = ZoneInfo("Asia/Jerusalem")

# הגדרת מצבי השיחה
(SELECTING_DATE, AWAITING_CUSTOM_DATE,
 SELECTING_TIME, AWAITING_CUSTOM_TIME,
 AWAITING_REMINDER_TEXT) = range(5)


# --- פונקציות עזר ותזכורות ---

async def send_reminder_callback(context: ContextTypes.DEFAULT_TYPE):
    """פונקציה זו מופעלת על ידי ה-JobQueue ושולחת את הודעת התזכורת."""
    job = context.job
    chat_id = job.data['chat_id']
    reminder_text = job.data['text']

    # --- שינוי לשליחת טקסט מודגש ---
    bold_text = f"<b>🔔 תזכורת: {reminder_text}</b>"

    await context.bot.send_message(
        chat_id=chat_id,
        text=bold_text,
        parse_mode=ParseMode.HTML
    )


# --- פקודות ותפריטים ראשיים ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """מציג את התפריט הראשי עם כפתורים."""
    keyboard = [
        [InlineKeyboardButton("➕ קבע תזכורת חדשה", callback_data="new_reminder")],
        [InlineKeyboardButton("❓ עזרה", callback_data="help_command")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    target = update.message or (update.callback_query and update.callback_query.message)
    if not target: return

    if update.callback_query:
        await update.callback_query.answer()
        await target.edit_text("מה תרצה לעשות עכשיו?", reply_markup=reply_markup)
    else:
        await target.reply_text("היי! אני בוט התזכורות שלך. מה תרצה לעשות?", reply_markup=reply_markup)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """מציג הודעת עזרה."""
    help_text = (
        "זהו בוט לקביעת תזכורות.\n\n"
        "לחץ על 'קבע תזכורת חדשה' כדי להתחיל בתהליך.\n"
        "הבוט ינחה אותך שלב אחר שלב לבחור תאריך, שעה ותוכן לתזכורת."
    )
    keyboard = [[InlineKeyboardButton("🔙 חזרה לתפריט", callback_data="back_to_main")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(text=help_text, reply_markup=reply_markup)
    else:
        await update.message.reply_text(help_text, reply_markup=reply_markup)


# --- תהליך שיחה לקביעת תזכורת ---

async def new_reminder_flow_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """מתחיל את תהליך קביעת התזכורת ומציג את אפשרויות התאריך."""
    query = update.callback_query
    await query.answer()
    keyboard = [
        [InlineKeyboardButton("היום", callback_data="date_today"),
         InlineKeyboardButton("מחר", callback_data="date_tomorrow")],
        [InlineKeyboardButton("בחר תאריך...", callback_data="date_custom")],
        [InlineKeyboardButton("🔙 חזרה", callback_data="back_to_main")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text="מתי להזכיר לך?", reply_markup=reply_markup)
    return SELECTING_DATE


async def handle_date_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """מטפל בבחירת תאריך מהכפתורים."""
    query = update.callback_query
    await query.answer()
    selection = query.data

    if selection == "date_custom":
        await query.edit_message_text(text="נא הקלד את התאריך בפורמט DD/MM/YYYY")
        return AWAITING_CUSTOM_DATE

    today = datetime.now(TZ_ISRAEL).date()
    if selection == "date_today":
        context.user_data['date'] = today
    elif selection == "date_tomorrow":
        context.user_data['date'] = today + timedelta(days=1)

    return await ask_for_time(update, context)


async def handle_custom_date(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """מטפל בקבלת תאריך בהקלדה."""
    date_text = update.message.text
    try:
        date_obj = datetime.strptime(date_text, '%d/%m/%Y').date()
        context.user_data['date'] = date_obj
        await update.message.delete()
        return await ask_for_time(update, context)
    except ValueError:
        await update.message.reply_text("פורמט שגוי. נסה שוב: DD/MM/YYYY")
        return AWAITING_CUSTOM_DATE


async def ask_for_time(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """מציג את אפשרויות בחירת השעה."""
    keyboard = [
        [InlineKeyboardButton("בוקר (09:00)", callback_data="time_morning"),
         InlineKeyboardButton("צהריים (14:00)", callback_data="time_afternoon")],
        [InlineKeyboardButton("ערב (20:00)", callback_data="time_evening")],
        [InlineKeyboardButton("בחר שעה...", callback_data="time_custom")],
        [InlineKeyboardButton("🔙 חזרה לבחירת תאריך", callback_data="back_to_date")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    target = update.message or (update.callback_query and update.callback_query.message)
    if update.callback_query:
        await target.edit_text("באיזו שעה?", reply_markup=reply_markup)
    else:
        await target.reply_text("באיזו שעה?", reply_markup=reply_markup)

    return SELECTING_TIME


async def handle_time_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """מטפל בבחירת שעה מהכפתורים."""
    query = update.callback_query
    await query.answer()
    selection = query.data

    if selection == "time_custom":
        await query.edit_message_text(text="נא הקלד את השעה בפורמט HH:MM")
        return AWAITING_CUSTOM_TIME

    if selection == "time_morning":
        context.user_data['time'] = time(9, 0)
    elif selection == "time_afternoon":
        context.user_data['time'] = time(14, 0)
    elif selection == "time_evening":
        context.user_data['time'] = time(20, 0)

    await query.edit_message_text("מצוין. עכשיו, שלח לי את תוכן התזכורת.")
    return AWAITING_REMINDER_TEXT


async def handle_custom_time(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """מטפל בקבלת שעה בהקלדה."""
    time_text = update.message.text
    try:
        time_obj = datetime.strptime(time_text, '%H:%M').time()
        context.user_data['time'] = time_obj
        await update.message.delete()
        target = update.message or (update.callback_query and update.callback_query.message)
        await context.bot.send_message(chat_id=target.chat_id, text="שעה התקבלה. עכשיו, שלח לי את תוכן התזכורת.")
        return AWAITING_REMINDER_TEXT
    except ValueError:
        await update.message.reply_text("פורמט שגוי. נסה שוב: HH:MM")
        return AWAITING_CUSTOM_TIME


async def get_reminder_text_and_set(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """מקבל את טקסט התזכורת, קובע אותה ומסיים את השיחה."""
    reminder_text = update.message.text
    date_obj, time_obj = context.user_data.get('date'), context.user_data.get('time')

    if not all([date_obj, time_obj]):
        await update.message.reply_text("אופס, משהו השתבש. לחץ /start כדי להתחיל מחדש.");
        return ConversationHandler.END

    dt_aware = datetime.combine(date_obj, time_obj, tzinfo=TZ_ISRAEL)
    now_israel = datetime.now(TZ_ISRAEL)

    if dt_aware < now_israel:
        await update.message.reply_text(
            f"הזמן המבוקש ({dt_aware.strftime('%d/%m/%Y %H:%M')}) כבר עבר. לחץ /start כדי לנסות שוב.");
        return ConversationHandler.END

    context.job_queue.run_once(send_reminder_callback, dt_aware,
                               data={'chat_id': update.effective_chat.id, 'text': reminder_text})

    await update.message.reply_text(f"👍 התזכורת נקבעה!")
    context.user_data.clear()

    await start(update, context)  # חזרה לתפריט הראשי
    return ConversationHandler.END


async def back_to_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """מחזיר את המשתמש לתפריט הראשי מהשיחה."""
    await start(update, context)
    return ConversationHandler.END


def main():
    """הפונקציה הראשית שמגדירה ומפעילה את הבוט."""
    job_queue = JobQueue()
    app = ApplicationBuilder().token(TOKEN).job_queue(job_queue).build()

    # הגדרת המטפלים (Handlers)
    conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(new_reminder_flow_start, pattern='^new_reminder$')],
        states={
            SELECTING_DATE: [CallbackQueryHandler(handle_date_selection, pattern='^date_')],
            AWAITING_CUSTOM_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_custom_date)],
            SELECTING_TIME: [
                CallbackQueryHandler(handle_time_selection, pattern='^time_'),
                CallbackQueryHandler(new_reminder_flow_start, pattern='^back_to_date$')
            ],
            AWAITING_CUSTOM_TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_custom_time)],
            AWAITING_REMINDER_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_reminder_text_and_set)],
        },
        fallbacks=[CommandHandler('start', start)],
    )

    app.add_handler(conv_handler)
    app.add_handler(CommandHandler('start', start))
    app.add_handler(CommandHandler('help', help_command))
    app.add_handler(CallbackQueryHandler(help_command, pattern='^help_command$'))
    app.add_handler(CallbackQueryHandler(back_to_main_menu, pattern='^back_to_main$'))

    print("הבוט מתחיל לפעול...")
    app.run_polling()


if __name__ == "__main__":
    main()
