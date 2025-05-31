import os
import json
import logging
from telegram import (
    Update, KeyboardButton, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
)
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    ContextTypes, ConversationHandler, filters
)
from telegram.error import TelegramError
from dotenv import load_dotenv

# Logging
logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Load .env
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
OWNER_ID = int(os.getenv("OWNER_ID", 0))

ADMINS_FILE = 'admins.json'
CHANNELS_FILE = 'channels.json'

# States
ADD_ADMIN, REMOVE_ADMIN, ADD_CHANNEL, REMOVE_CHANNEL, FORWARD_COLLECT, SELECT_CHANNELS = range(6)

# Initialize JSON files
def initialize_files():
    for file in [ADMINS_FILE, CHANNELS_FILE]:
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
    return str(user_id) in admins or user_id == OWNER_ID

def get_main_keyboard(user_id):
    buttons = [
        [KeyboardButton("➕ Add Channel"), KeyboardButton("➖ Remove Channel")],
        [KeyboardButton("📃 My Channels"), KeyboardButton("📤 Post")]
    ]
    if user_id == OWNER_ID:
        buttons.append([KeyboardButton("🧑‍💻 Manage Admins")])
    return ReplyKeyboardMarkup(buttons, resize_keyboard=True)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.message.reply_text("❌ Access denied. You are not an admin.")
        return ConversationHandler.END
    await update.message.reply_text("Welcome! 👇 Choose an option:", reply_markup=get_main_keyboard(user_id))
    return ConversationHandler.END

async def handle_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text
    if not is_admin(user_id):
        await update.message.reply_text("❌ Access denied.")
        return ConversationHandler.END

    if text == "➕ Add Channel":
        await update.message.reply_text("Send @channelusername or -100... ID:")
        return ADD_CHANNEL

    elif text == "➖ Remove Channel":
        await update.message.reply_text("Send the @channelusername or ID to remove:")
        return REMOVE_CHANNEL

    elif text == "📃 My Channels":
        channels = load_json(CHANNELS_FILE).get(str(user_id), [])
        msg = "\n".join(channels) if channels else "❌ No channels added."
        await update.message.reply_text(msg)
        return ConversationHandler.END

    elif text == "📤 Post":
        channels = load_json(CHANNELS_FILE).get(str(user_id), [])
        if not channels:
            await update.message.reply_text("❌ No channels to post. Add one first.")
            return ConversationHandler.END
        context.user_data['forwarded_messages'] = []
        await update.message.reply_text("Forward or send messages to post. Type /done when finished.")
        return FORWARD_COLLECT

    elif text == "🧑‍💻 Manage Admins" and user_id == OWNER_ID:
        buttons = [[KeyboardButton("➕ Add Admin"), KeyboardButton("➖ Remove Admin")], [KeyboardButton("🔙 Back")]]
        await update.message.reply_text("Choose:", reply_markup=ReplyKeyboardMarkup(buttons, resize_keyboard=True))
        return ConversationHandler.END

    elif text == "➕ Add Admin" and user_id == OWNER_ID:
        await update.message.reply_text("Send user ID to add as admin:")
        return ADD_ADMIN

    elif text == "➖ Remove Admin" and user_id == OWNER_ID:
        await update.message.reply_text("Send user ID to remove from admin:")
        return REMOVE_ADMIN

    elif text == "🔙 Back":
        await update.message.reply_text("Back to main menu.", reply_markup=get_main_keyboard(user_id))
        return ConversationHandler.END

    else:
        await update.message.reply_text("❌ Invalid option.")
        return ConversationHandler.END

async def add_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    new_id = update.message.text.strip()
    if not new_id.isdigit():
        await update.message.reply_text("❌ Invalid ID.")
        return ConversationHandler.END
    if new_id == str(OWNER_ID):
        await update.message.reply_text("❌ Cannot modify owner.")
        return ConversationHandler.END
    admins = load_json(ADMINS_FILE)
    admins[new_id] = True
    save_json(ADMINS_FILE, admins)
    await update.message.reply_text(f"✅ Admin {new_id} added.")
    return ConversationHandler.END

async def remove_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    del_id = update.message.text.strip()
    if del_id == str(OWNER_ID):
        await update.message.reply_text("❌ Cannot remove owner.")
        return ConversationHandler.END
    admins = load_json(ADMINS_FILE)
    if del_id in admins:
        del admins[del_id]
        save_json(ADMINS_FILE, admins)
        await update.message.reply_text(f"✅ Admin {del_id} removed.")
    else:
        await update.message.reply_text("❌ Admin not found.")
    return ConversationHandler.END

async def add_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    channel = update.message.text.strip()
    if not (channel.startswith("@") or channel.startswith("-100")):
        await update.message.reply_text("❌ Invalid channel format.")
        return ConversationHandler.END

    channels = load_json(CHANNELS_FILE)
    channels.setdefault(user_id, [])
    try:
        member = await context.bot.get_chat_member(channel, context.bot.id)
        if member.status not in ["administrator", "creator"]:
            await update.message.reply_text("❌ Bot must be admin in that channel.")
            return ConversationHandler.END
        if channel not in channels[user_id]:
            channels[user_id].append(channel)
            save_json(CHANNELS_FILE, channels)
            await update.message.reply_text(f"✅ Channel {channel} added.")
        else:
            await update.message.reply_text("⚠️ Channel already added.")
    except TelegramError as e:
        await update.message.reply_text(f"❌ Error: {e.message}")
    return ConversationHandler.END

async def remove_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    channel = update.message.text.strip()
    channels = load_json(CHANNELS_FILE)
    if channel in channels.get(user_id, []):
        channels[user_id].remove(channel)
        save_json(CHANNELS_FILE, channels)
        await update.message.reply_text(f"✅ Channel {channel} removed.")
    else:
        await update.message.reply_text("❌ Channel not found.")
    return ConversationHandler.END

async def collect_forward(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.setdefault("forwarded_messages", []).append(update.message)
    await update.message.reply_text("✅ Message added. Type /done when finished.")
    return FORWARD_COLLECT

async def done_forwarding(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    messages = context.user_data.get("forwarded_messages", [])
    if not messages:
        await update.message.reply_text("❌ No messages to post.")
        return ConversationHandler.END

    channels = load_json(CHANNELS_FILE).get(user_id, [])
    if not channels:
        await update.message.reply_text("❌ No channels to post.")
        return ConversationHandler.END

    buttons = [[InlineKeyboardButton(ch, callback_data=ch)] for ch in channels]
    buttons.append([InlineKeyboardButton("✅ All", callback_data="ALL")])
    await update.message.reply_text("Select channels:", reply_markup=InlineKeyboardMarkup(buttons))
    return SELECT_CHANNELS

async def handle_channel_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    selected = query.data
    user_id = str(query.from_user.id)
    messages = context.user_data.get("forwarded_messages", [])
    targets = load_json(CHANNELS_FILE).get(user_id, [])

    if selected != "ALL":
        if selected not in targets:
            await query.edit_message_text("❌ Invalid channel.")
            return ConversationHandler.END
        targets = [selected]

    success = 0
    for ch in targets:
        try:
            member = await context.bot.get_chat_member(ch, context.bot.id)
            if member.status not in ["administrator", "creator"]:
                continue
            for msg in messages:
                await msg.copy_to(chat_id=ch)
                success += 1
        except:
            continue

    await query.edit_message_text(f"✅ {success} message(s) posted.")
    context.user_data["forwarded_messages"] = []
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["forwarded_messages"] = []
    await update.message.reply_text("❌ Cancelled.", reply_markup=get_main_keyboard(update.effective_user.id))
    return ConversationHandler.END

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.error("Error: %s", context.error)

def main():
    initialize_files()
    if not BOT_TOKEN or not OWNER_ID:
        logger.error("BOT_TOKEN or OWNER_ID not set in .env")
        return

    app = Application.builder().token(BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start), MessageHandler(filters.TEXT & ~filters.COMMAND, handle_menu)],
        states={
            ADD_ADMIN: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_admin)],
            REMOVE_ADMIN: [MessageHandler(filters.TEXT & ~filters.COMMAND, remove_admin)],
            ADD_CHANNEL: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_channel)],
            REMOVE_CHANNEL: [MessageHandler(filters.TEXT & ~filters.COMMAND, remove_channel)],
            FORWARD_COLLECT: [MessageHandler(filters.ALL & ~filters.COMMAND, collect_forward)],
            SELECT_CHANNELS: [CallbackQueryHandler(handle_channel_selection)]
        },
        fallbacks=[
            CommandHandler("cancel", cancel),
            CommandHandler("done", done_forwarding)
        ]
    )

    app.add_handler(conv_handler)
    app.add_error_handler(error_handler)
    logger.info("🤖 Bot running...")
    app.run_polling()

if __name__ == "__main__":
    main()
