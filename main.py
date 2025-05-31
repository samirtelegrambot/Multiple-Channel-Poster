import os
import json
from telegram import Update, KeyboardButton, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    ConversationHandler,
    filters
)
from dotenv import load_dotenv

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
OWNER_ID = 8150652959
ADMINS_FILE = 'admins.json'
CHANNELS_FILE = 'channels.json'

ADD_ADMIN, REMOVE_ADMIN, ADD_CHANNEL, REMOVE_CHANNEL, FORWARD_COLLECT, SELECT_CHANNELS = range(6)

# Initialize JSON files if not exist
for file in [ADMINS_FILE, CHANNELS_FILE]:
    if not os.path.exists(file):
        with open(file, 'w') as f:
            json.dump({}, f)

def load_json(file):
    with open(file, 'r') as f:
        return json.load(f)

def save_json(file, data):
    with open(file, 'w') as f:
        json.dump(data, f, indent=4)

def is_admin(user_id):
    admins = load_json(ADMINS_FILE)
    # admins stored as list of strings
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
        await update.message.reply_text("❌ Access denied.")
        return
    await update.message.reply_text("Welcome! 👇 Choose an option:", reply_markup=get_main_keyboard(user_id))

async def handle_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.message.reply_text("❌ Access denied.")
        return ConversationHandler.END

    if text == "➕ Add Channel":
        await update.message.reply_text("Send @username or -100... ID of the channel (Bot must be admin).")
        return ADD_CHANNEL

    elif text == "➖ Remove Channel":
        await update.message.reply_text("Send the @username or ID of the channel to remove.")
        return REMOVE_CHANNEL

    elif text == "📃 My Channels":
        channels = load_json(CHANNELS_FILE).get(str(user_id), [])
        if channels:
            formatted = "\n".join(f"- {ch}" for ch in channels)
            await update.message.reply_text(formatted)
        else:
            await update.message.reply_text("❌ No channels added.")
        return ConversationHandler.END

    elif text == "📤 Post":
        channels = load_json(CHANNELS_FILE).get(str(user_id), [])
        if not channels:
            await update.message.reply_text("❌ No channels available.")
            return ConversationHandler.END
        context.user_data['forwarded_messages'] = []
        await update.message.reply_text("📩 Forward all messages you want to post. When done, type /done")
        return FORWARD_COLLECT

    elif text == "🧑‍💻 Manage Admins" and user_id == OWNER_ID:
        buttons = [
            [KeyboardButton("➕ Add Admin"), KeyboardButton("➖ Remove Admin")],
            [KeyboardButton("🔙 Back")]
        ]
        await update.message.reply_text("Manage Admins:", reply_markup=ReplyKeyboardMarkup(buttons, resize_keyboard=True))
        return ConversationHandler.END

    elif text == "➕ Add Admin" and user_id == OWNER_ID:
        await update.message.reply_text("Send the user ID to add as admin:")
        return ADD_ADMIN

    elif text == "➖ Remove Admin" and user_id == OWNER_ID:
        await update.message.reply_text("Send the user ID to remove from admin:")
        return REMOVE_ADMIN

    elif text == "🔙 Back":
        await update.message.reply_text("⬅️ Back to main menu", reply_markup=get_main_keyboard(user_id))
        return ConversationHandler.END

async def add_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    new_id = update.message.text.strip()
    admins = load_json(ADMINS_FILE)
    # Make sure admins is list
    if not isinstance(admins, list):
        admins = []
    if new_id not in admins:
        admins.append(new_id)
        save_json(ADMINS_FILE, admins)
        await update.message.reply_text(f"✅ Admin {new_id} added.")
    else:
        await update.message.reply_text("⚠️ Admin already exists.")
    return ConversationHandler.END

async def remove_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    del_id = update.message.text.strip()
    admins = load_json(ADMINS_FILE)
    if not isinstance(admins, list):
        admins = []
    if del_id in admins:
        admins.remove(del_id)
        save_json(ADMINS_FILE, admins)
        await update.message.reply_text(f"❌ Admin {del_id} removed.")
    else:
        await update.message.reply_text("❌ User not found in admins.")
    return ConversationHandler.END

async def add_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    channel = update.message.text.strip()
    user_id = str(update.effective_user.id)
    channels = load_json(CHANNELS_FILE)
    channels.setdefault(user_id, [])
    if channel not in channels[user_id]:
        channels[user_id].append(channel)
        save_json(CHANNELS_FILE, channels)
        await update.message.reply_text(f"✅ Channel {channel} added.")
    else:
        await update.message.reply_text("⚠️ Channel already added.")
    return ConversationHandler.END

async def remove_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    channel = update.message.text.strip()
    user_id = str(update.effective_user.id)
    channels = load_json(CHANNELS_FILE)
    if channel in channels.get(user_id, []):
        channels[user_id].remove(channel)
        save_json(CHANNELS_FILE, channels)
        await update.message.reply_text(f"❌ Channel {channel} removed.")
    else:
        await update.message.reply_text("❌ Channel not found.")
    return ConversationHandler.END

async def collect_forward(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if 'forwarded_messages' not in context.user_data:
        context.user_data['forwarded_messages'] = []
    context.user_data['forwarded_messages'].append(update.message)
    await update.message.reply_text("✅ Message added. Forward more or type /done.")
    return FORWARD_COLLECT

async def done_forwarding(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    channels = load_json(CHANNELS_FILE).get(user_id, [])
    if not channels:
        await update.message.reply_text("❌ No channels available.")
        return ConversationHandler.END
    buttons = [[InlineKeyboardButton(ch, callback_data=ch)] for ch in channels]
    buttons.append([InlineKeyboardButton("✅ All", callback_data="ALL")])
    await update.message.reply_text("Select channels to post:", reply_markup=InlineKeyboardMarkup(buttons))
    return SELECT_CHANNELS

async def handle_channel_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    selected = query.data
    user_id = str(query.from_user.id)
    messages = context.user_data.get('forwarded_messages', [])

    targets = load_json(CHANNELS_FILE).get(user_id, [])
    if selected != "ALL":
        targets = [selected]

    for msg in messages:
        for ch in targets:
            try:
                await msg.copy_to(chat_id=ch)
            except Exception as e:
                await query.message.reply_text(f"❌ Failed to post in {ch}: {e}")

    await query.edit_message_text("✅ All messages posted.")
    context.user_data['forwarded_messages'] = []
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Cancelled.")
    return ConversationHandler.END

if __name__ == '__main__':
    if not BOT_TOKEN:
        print("Error: BOT_TOKEN not found in environment variables. Please check your .env file.")
        exit(1)

    app = Application.builder().token(BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.TEXT & ~filters.COMMAND, handle_menu)],
        states={
            ADD_ADMIN: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_admin)],
            REMOVE_ADMIN: [MessageHandler(filters.TEXT & ~filters.COMMAND, remove_admin)],
            ADD_CHANNEL: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_channel)],
            REMOVE_CHANNEL: [MessageHandler(filters.TEXT & ~filters.COMMAND, remove_channel)],
            FORWARD_COLLECT: [MessageHandler(filters.ALL & ~filters.COMMAND, collect_forward)],
            SELECT_CHANNELS: [CallbackQueryHandler(handle_channel_selection)]
        },
        fallbacks=[CommandHandler("cancel", cancel), CommandHandler("done", done_forwarding)]
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(conv_handler)

    print("🤖 Bot running...")
    app.run_polling()
