import os
import json
import logging
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    ConversationHandler, ContextTypes, filters
)
from dotenv import load_dotenv

# Logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Load env vars
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
OWNER_ID = int(os.getenv("OWNER_ID", 0))

# Files
ADMINS_FILE = 'admins.json'
CHANNELS_FILE = 'channels.json'
STORED_FILE = 'stored_messages.json'

# States
ADD_ADMIN, REMOVE_ADMIN, ADD_CHANNEL, REMOVE_CHANNEL = range(4)

def initialize_files():
    for file in [ADMINS_FILE, CHANNELS_FILE, STORED_FILE]:
        if not os.path.exists(file):
            with open(file, 'w') as f:
                json.dump({}, f)

def load_json(file):
    try:
        with open(file, 'r') as f:
            return json.load(f)
    except:
        return {}

def save_json(file, data):
    with open(file, 'w') as f:
        json.dump(data, f, indent=2)

def is_admin(user_id):
    admins = load_json(ADMINS_FILE)
    return user_id == OWNER_ID or str(user_id) in admins

def get_main_keyboard():
    return ReplyKeyboardMarkup([
        [KeyboardButton("➕ Add Channel"), KeyboardButton("➖ Remove Channel")],
        [KeyboardButton("📃 My Channels"), KeyboardButton("📤 Post Stored")],
        [KeyboardButton("🧹 Clear Stored")],
        [KeyboardButton("👨‍💻 Manage Admins"), KeyboardButton("⬅️ Back")]
    ], resize_keyboard=True)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.message.reply_text("❌ Access denied.")
        return
    await update.message.reply_text("Welcome Admin!", reply_markup=get_main_keyboard())

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = update.effective_user.id

    if not is_admin(user_id):
        await update.message.reply_text("❌ Access denied.")
        return

    if text == "📤 Post Stored":
        await show_post_options(update, context, user_id)

    elif text == "🧹 Clear Stored":
        all_stored = load_json(STORED_FILE)
        all_stored[str(user_id)] = []
        save_json(STORED_FILE, all_stored)
        await update.message.reply_text("🧹 All stored messages cleared.")

    elif text == "📃 My Channels":
        channels = load_json(CHANNELS_FILE)
        if not channels:
            await update.message.reply_text("No channels added.")
        else:
            await update.message.reply_text("\n".join([f"{v} ({k})" for k, v in channels.items()]))

    elif text == "➕ Add Channel":
        await update.message.reply_text("Send channel ID or username:")
        return ADD_CHANNEL

    elif text == "➖ Remove Channel":
        await update.message.reply_text("Send channel ID to remove:")
        return REMOVE_CHANNEL

    elif text == "👨‍💻 Manage Admins" and user_id == OWNER_ID:
        await update.message.reply_text("Send user ID to add or remove as admin:\nPrefix with `+` to add, `-` to remove.")
        return ADD_ADMIN

    elif text == "⬅️ Back":
        await update.message.reply_text("⬅️ Back to menu", reply_markup=get_main_keyboard())

async def handle_forward(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        return

    forwarded = update.message
    stored = load_json(STORED_FILE)
    messages = stored.get(str(user_id), [])
    messages.append({
        "chat_id": forwarded.forward_from_chat.id,
        "message_id": forwarded.message_id
    })
    stored[str(user_id)] = messages
    save_json(STORED_FILE, stored)

    await update.message.reply_text(f"✅ Message {len(messages)} stored. Use 📤 Post Stored to post.")

async def show_post_options(update, context, user_id):
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    keyboard = [
        [InlineKeyboardButton("📤 Post to All", callback_data="post_all")],
        [InlineKeyboardButton("📂 Select Channels", callback_data="select_channels")],
        [InlineKeyboardButton("⬅️ Back", callback_data="back")]
    ]
    await update.message.reply_text("Choose where to post stored messages:", reply_markup=InlineKeyboardMarkup(keyboard))

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = query.data

    if not is_admin(user_id):
        await query.message.reply_text("❌ Access denied.")
        return

    stored_all = load_json(STORED_FILE)
    stored = stored_all.get(str(user_id), [])

    if data == "post_all":
        channels = load_json(CHANNELS_FILE)
        if not stored or not channels:
            await query.message.reply_text("⚠️ No stored messages or channels.")
            return
        success = 0
        for cid in channels:
            for msg in stored:
                try:
                    await context.bot.copy_message(
                        chat_id=cid,
                        from_chat_id=msg["chat_id"],
                        message_id=msg["message_id"]
                    )
                    success += 1
                except:
                    continue
        await query.message.reply_text(f"✅ Posted {success} messages to all channels.")

    elif data == "select_channels":
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup
        channels = load_json(CHANNELS_FILE)
        if not channels:
            await query.message.reply_text("❌ No channels available.")
            return
        buttons = [[InlineKeyboardButton(name, callback_data=f"post_to|{cid}")] for cid, name in channels.items()]
        buttons.append([InlineKeyboardButton("⬅️ Back", callback_data="back")])
        await query.message.reply_text("Select a channel:", reply_markup=InlineKeyboardMarkup(buttons))

    elif data.startswith("post_to|"):
        cid = data.split("|")[1]
        posted = 0
        for msg in stored:
            try:
                await context.bot.copy_message(
                    chat_id=cid,
                    from_chat_id=msg["chat_id"],
                    message_id=msg["message_id"]
                )
                posted += 1
            except:
                continue
        await query.message.reply_text(f"✅ Posted {posted} messages.")

    elif data == "back":
        await query.message.reply_text("⬅️ Back to menu", reply_markup=get_main_keyboard())

async def add_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.message.text.strip()
    admins = load_json(ADMINS_FILE)
    if uid.startswith("+"):
        admins[uid[1:]] = True
        await update.message.reply_text("✅ Admin added.")
    elif uid.startswith("-") and uid[1:] in admins:
        del admins[uid[1:]]
        await update.message.reply_text("✅ Admin removed.")
    else:
        await update.message.reply_text("⚠️ Invalid command.")
    save_json(ADMINS_FILE, admins)

async def add_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cid = update.message.text.strip()
    try:
        chat = await context.bot.get_chat(cid)
        channels = load_json(CHANNELS_FILE)
        channels[cid] = chat.title or cid
        save_json(CHANNELS_FILE, channels)
        await update.message.reply_text("✅ Channel added.")
    except:
        await update.message.reply_text("❌ Failed to add channel.")

async def remove_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cid = update.message.text.strip()
    channels = load_json(CHANNELS_FILE)
    if cid in channels:
        del channels[cid]
        save_json(CHANNELS_FILE, channels)
        await update.message.reply_text("✅ Channel removed.")
    else:
        await update.message.reply_text("❌ Channel not found.")

def main():
    initialize_files()
    app = Application.builder().token(BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            ADD_ADMIN: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_admin)],
            ADD_CHANNEL: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_channel)],
            REMOVE_CHANNEL: [MessageHandler(filters.TEXT & ~filters.COMMAND, remove_channel)],
        },
        fallbacks=[],
        allow_reentry=True
    )

    app.add_handler(conv_handler)
    app.add_handler(MessageHandler(filters.FORWARDED, handle_forward))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(CallbackQueryHandler(handle_callback))

    logger.info("Bot running...")
    app.run_polling()

if __name__ == "__main__":
    main()
