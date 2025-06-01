import os
import json
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    ConversationHandler, ContextTypes, filters
)
from dotenv import load_dotenv
import telegram.error

# Logging setup
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Load .env values
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
OWNER_ID = int(os.getenv("OWNER_ID", 0))

ADMINS_FILE = 'admins.json'
CHANNELS_FILE = 'channels.json'

# States
ADD_ADMIN, REMOVE_ADMIN, ADD_CHANNEL, REMOVE_CHANNEL, POST_MESSAGE = range(5)

def initialize_files():
    for file in [ADMINS_FILE, CHANNELS_FILE]:
        if not os.path.exists(file):
            with open(file, 'w') as f:
                json.dump({}, f)

def load_json(file):
    try:
        with open(file, 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error loading {file}: {e}")
        return {}

def save_json(file, data):
    try:
        with open(file, 'w') as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        logger.error(f"Error saving {file}: {e}")

def is_admin(user_id):
    admins = load_json(ADMINS_FILE)
    return user_id == OWNER_ID or str(user_id) in admins

async def is_bot_channel_admin(context, channel_id):
    try:
        chat_member = await context.bot.get_chat_member(channel_id, context.bot.id)
        return chat_member.status in ['administrator', 'creator']
    except telegram.error.TelegramError:
        return False

def get_main_keyboard(user_id):
    keyboard = [
        [InlineKeyboardButton("➕ Add Channel", callback_data="add_channel"),
         InlineKeyboardButton("➖ Remove Channel", callback_data="remove_channel")],
        [InlineKeyboardButton("📃 My Channels", callback_data="list_channels"),
         InlineKeyboardButton("📤 Post", callback_data="post")]
    ]
    if user_id == OWNER_ID:
        keyboard.append([InlineKeyboardButton("🧑‍💻 Manage Admins", callback_data="manage_admins")])
    return InlineKeyboardMarkup(keyboard)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.message.reply_text("❌ Access denied. Admins only.")
        return ConversationHandler.END
    await update.message.reply_text("Welcome! Use the menu below:", reply_markup=get_main_keyboard(user_id))
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    await update.message.reply_text("Operation cancelled.", reply_markup=get_main_keyboard(user_id))
    return ConversationHandler.END

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    if not is_admin(user_id):
        await query.message.reply_text("❌ Access denied.")
        return ConversationHandler.END

    data = query.data

    if data == "manage_admins" and user_id == OWNER_ID:
        keyboard = [
            [InlineKeyboardButton("➕ Add Admin", callback_data="add_admin"),
             InlineKeyboardButton("➖ Remove Admin", callback_data="remove_admin")],
            [InlineKeyboardButton("📋 List Admins", callback_data="list_admins"),
             InlineKeyboardButton("🔙 Back", callback_data="back")]
        ]
        await query.message.reply_text("Admin Panel:", reply_markup=InlineKeyboardMarkup(keyboard))
        return ConversationHandler.END

    elif data == "add_admin" and user_id == OWNER_ID:
        await query.message.reply_text("Send the user ID to add (or /cancel to abort):")
        return ADD_ADMIN

    elif data == "remove_admin" and user_id == OWNER_ID:
        await query.message.reply_text("Send the user ID to remove (or /cancel to abort):")
        return REMOVE_ADMIN

    elif data == "list_admins" and user_id == OWNER_ID:
        admins = list(load_json(ADMINS_FILE).keys())
        msg = "👮‍♂️ Admins:\n" + "\n".join(admins) if admins else "No admins yet."
        await query.message.reply_text(msg)
        return ConversationHandler.END

    elif data == "add_channel":
        await query.message.reply_text("Send the channel ID or username (e.g., @ChannelName or -100123456789) (or /cancel to abort):")
        return ADD_CHANNEL

    elif data == "remove_channel":
        await query.message.reply_text("Send the channel ID or username to remove (or /cancel to abort):")
        return REMOVE_CHANNEL

    elif data == "list_channels":
        channels = load_json(CHANNELS_FILE)
        if not channels:
            await query.message.reply_text("No channels added yet.")
        else:
            msg = "📃 Channels:\n" + "\n".join(f"{k} ({v})" for k, v in channels.items())
            await query.message.reply_text(msg)
        return ConversationHandler.END

    elif data == "post":
        await query.message.reply_text("Send the message to post to all channels (or /cancel to abort):")
        return POST_MESSAGE

    elif data == "back":
        await query.message.reply_text("Main menu:", reply_markup=get_main_keyboard(user_id))
        return ConversationHandler.END

    else:
        await query.message.reply_text("❌ Only the owner can manage admins.", reply_markup=get_main_keyboard(user_id))
        return ConversationHandler.END

async def add_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != OWNER_ID:
        await update.message.reply_text("❌ Only the owner can add admins.", reply_markup=get_main_keyboard(user_id))
        return ConversationHandler.END

    new_id = update.message.text.strip()
    if not new_id.isdigit():
        await update.message.reply_text("❌ Invalid user ID. Must be numeric.")
        return ConversationHandler.END

    if new_id == str(OWNER_ID):
        await update.message.reply_text("⚠️ Already the owner.")
        return ConversationHandler.END

    admins = load_json(ADMINS_FILE)
    if new_id in admins:
        await update.message.reply_text("Already an admin.")
    else:
        admins[new_id] = True
        save_json(ADMINS_FILE, admins)
        await update.message.reply_text("✅ Admin added.")
    await update.message.reply_text("Main menu:", reply_markup=get_main_keyboard(user_id))
    return ConversationHandler.END

async def remove_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != OWNER_ID:
        await update.message.reply_text("❌ Only the owner can remove admins.", reply_markup=get_main_keyboard(user_id))
        return ConversationHandler.END

    del_id = update.message.text.strip()
    if del_id == str(OWNER_ID):
        await update.message.reply_text("❌ Cannot remove owner.")
        return ConversationHandler.END

    admins = load_json(ADMINS_FILE)
    if del_id in admins:
        del admins[del_id]
        save_json(ADMINS_FILE, admins)
        await update.message.reply_text("✅ Admin removed.")
    else:
        await update.message.reply_text("User not found in admin list.")
    await update.message.reply_text("Main menu:", reply_markup=get_main_keyboard(user_id))
    return ConversationHandler.END

async def add_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    channel = update.message.text.strip()

    if channel.startswith('@'):
        channel_id = channel
    elif channel.startswith('-') and channel[1:].isdigit():
        channel_id = channel
    else:
        await update.message.reply_text("❌ Invalid channel ID or username. Use @ChannelName or -100123456789.")
        return ConversationHandler.END

    if not await is_bot_channel_admin(context, channel_id):
        await update.message.reply_text("❌ Bot must be an admin in the channel.")
        return ConversationHandler.END

    channels = load_json(CHANNELS_FILE)
    if channel_id in channels:
        await update.message.reply_text("Channel already added.")
    else:
        try:
            chat = await context.bot.get_chat(channel_id)
            channels[channel_id] = chat.title or channel_id
            save_json(CHANNELS_FILE, channels)
            await update.message.reply_text(f"✅ Channel {channel_id} added.")
        except telegram.error.TelegramError as e:
            await update.message.reply_text(f"❌ Error: {e.message}")
    await update.message.reply_text("Main menu:", reply_markup=get_main_keyboard(user_id))
    return ConversationHandler.END

async def remove_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    channel = update.message.text.strip()

    channels = load_json(CHANNELS_FILE)
    if channel in channels:
        del channels[channel]
        save_json(CHANNELS_FILE, channels)
        await update.message.reply_text(f"✅ Channel {channel} removed.")
    else:
        await update.message.reply_text("Channel not found in the list.")
    await update.message.reply_text("Main menu:", reply_markup=get_main_keyboard(user_id))
    return ConversationHandler.END

async def post_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    message = update.message.text
    channels = load_json(CHANNELS_FILE)

    if not channels:
        await update.message.reply_text("No channels to post to.")
        await update.message.reply_text("Main menu:", reply_markup=get_main_keyboard(user_id))
        return ConversationHandler.END

    success = 0
    failed = []
    for channel_id in channels:
        try:
            await context.bot.send_message(chat_id=channel_id, text=message)
            success += 1
        except telegram.error.TelegramError as e:
            failed.append(f"{channel_id}: {e.message}")

    msg = f"✅ Posted to {success} channel(s)."
    if failed:
        msg += f"\n❌ Failed for: {', '.join(failed)}"
    await update.message.reply_text(msg)
    await update.message.reply_text("Main menu:", reply_markup=get_main_keyboard(user_id))
    return ConversationHandler.END

def main():
    initialize_files()
    if not BOT_TOKEN or not OWNER_ID:
        logger.error("BOT_TOKEN or OWNER_ID not set")
        return

    app = Application.builder().token(BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("start", start),
            CallbackQueryHandler(handle_callback)
        ],
        states={
            ADD_ADMIN: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_admin)],
            REMOVE_ADMIN: [MessageHandler(filters.TEXT & ~filters.COMMAND, remove_admin)],
            ADD_CHANNEL: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_channel)],
            REMOVE_CHANNEL: [MessageHandler(filters.TEXT & ~filters.COMMAND, remove_channel)],
            POST_MESSAGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, post_message)]
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        allow_reentry=True
    )

    app.add_handler(conv_handler)
    logger.info("Bot is running...")
    try:
        app.run_polling()
    except Exception as e:
        logger.error(f"Bot crashed: {e}")

if __name__ == "__main__":
    main()
