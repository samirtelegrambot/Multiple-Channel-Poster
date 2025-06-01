import os
import json
from telegram import (
    Update, ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardButton, InlineKeyboardMarkup
)
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, filters,
    CallbackQueryHandler, ContextTypes, ConversationHandler
)
from dotenv import load_dotenv

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
OWNER_ID = int(os.getenv("OWNER_ID", "0"))

ADMINS_FILE = "admins.json"
CHANNELS_FILE = "channels.json"

# States for ConversationHandler
WAIT_ADD_CHANNEL, WAIT_REMOVE_CHANNEL, WAIT_ADD_ADMIN, WAIT_REMOVE_ADMIN = range(4)

def load_json(filename):
    try:
        with open(filename, "r") as f:
            return json.load(f)
    except:
        return {}

def save_json(filename, data):
    with open(filename, "w") as f:
        json.dump(data, f, indent=2)

def is_owner(user_id):
    return user_id == OWNER_ID

def is_admin(user_id):
    admins = load_json(ADMINS_FILE)
    return is_owner(user_id) or str(user_id) in admins

def get_user_channels(user_id):
    channels = load_json(CHANNELS_FILE)
    return channels.get(str(user_id), {})

def save_user_channels(user_id, user_channels):
    all_channels = load_json(CHANNELS_FILE)
    all_channels[str(user_id)] = user_channels
    save_json(CHANNELS_FILE, all_channels)

def owner_keyboard():
    buttons = [
        [KeyboardButton("➕ Add Channel"), KeyboardButton("➖ Remove Channel")],
        [KeyboardButton("📃 My Channels"), KeyboardButton("📤 Post Stored")],
        [KeyboardButton("👨‍💻 Manage Admins")],
        [KeyboardButton("⬅️ Exit")]
    ]
    return ReplyKeyboardMarkup(buttons, resize_keyboard=True)

def admin_keyboard():
    buttons = [
        [KeyboardButton("➕ Add Channel"), KeyboardButton("➖ Remove Channel")],
        [KeyboardButton("📃 My Channels"), KeyboardButton("📤 Post Stored")],
        [KeyboardButton("⬅️ Exit")]
    ]
    return ReplyKeyboardMarkup(buttons, resize_keyboard=True)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.message.reply_text("❌ You are not authorized!")
        return

    if is_owner(user_id):
        await update.message.reply_text("Welcome Owner!", reply_markup=owner_keyboard())
    else:
        await update.message.reply_text("Welcome Admin!", reply_markup=admin_keyboard())

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text

    if not is_admin(user_id):
        await update.message.reply_text("❌ Access denied.")
        return

    if text == "⬅️ Exit":
        await update.message.reply_text("Use /start to open menu again.", reply_markup=ReplyKeyboardMarkup([], resize_keyboard=True))
        return

    if text == "➕ Add Channel":
        await update.message.reply_text("Send channel ID or username to add:")
        return WAIT_ADD_CHANNEL

    if text == "➖ Remove Channel":
        user_channels = get_user_channels(user_id)
        if not user_channels:
            await update.message.reply_text("You have no channels.")
            return
        channels_list = "\n".join([f"{name} ({cid})" for cid, name in user_channels.items()])
        await update.message.reply_text(f"Your channels:\n{channels_list}\nSend channel ID to remove:")
        return WAIT_REMOVE_CHANNEL

    if text == "📃 My Channels":
        user_channels = get_user_channels(user_id)
        if not user_channels:
            await update.message.reply_text("You have no channels.")
        else:
            channels_list = "\n".join([f"{name} ({cid})" for cid, name in user_channels.items()])
            await update.message.reply_text(f"Your channels:\n{channels_list}")

    if text == "👨‍💻 Manage Admins":
        if not is_owner(user_id):
            await update.message.reply_text("❌ Only owner can manage admins.")
            return
        buttons = [
            [KeyboardButton("➕ Add Admin"), KeyboardButton("➖ Remove Admin")],
            [KeyboardButton("📃 List Admins")],
            [KeyboardButton("⬅️ Back")]
        ]
        await update.message.reply_text("Manage Admins Menu:", reply_markup=ReplyKeyboardMarkup(buttons, resize_keyboard=True))
        return WAIT_ADD_ADMIN

    if text == "📤 Post Stored":
        keyboard = [
            [InlineKeyboardButton("🧹 Clear Stored", callback_data="clear_stored")],
            [InlineKeyboardButton("📤 Post to All", callback_data="post_all")],
            [InlineKeyboardButton("📂 Select Channel", callback_data="select_channel")],
            [InlineKeyboardButton("⬅️ Back", callback_data="back_main")]
        ]
        await update.message.reply_text("Post Stored Menu:", reply_markup=InlineKeyboardMarkup(keyboard))

async def add_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    channel_id = update.message.text.strip()
    user_channels = get_user_channels(user_id)
    user_channels[channel_id] = channel_id  # For simplicity, using ID as name
    save_user_channels(user_id, user_channels)
    await update.message.reply_text(f"✅ Channel '{channel_id}' added.")
    return ConversationHandler.END

async def remove_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    channel_id = update.message.text.strip()
    user_channels = get_user_channels(user_id)
    if channel_id in user_channels:
        user_channels.pop(channel_id)
        save_user_channels(user_id, user_channels)
        await update.message.reply_text(f"✅ Channel '{channel_id}' removed.")
    else:
        await update.message.reply_text("❌ Channel ID not found.")
    return ConversationHandler.END

async def manage_admins(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()
    if not is_owner(user_id):
        await update.message.reply_text("❌ Only owner can manage admins.")
        return ConversationHandler.END

    admins = load_json(ADMINS_FILE)

    if text == "⬅️ Back":
        await update.message.reply_text("Back to main menu.", reply_markup=owner_keyboard())
        return ConversationHandler.END

    if text == "➕ Add Admin":
        await update.message.reply_text("Send user ID to add as admin:")
        return WAIT_ADD_ADMIN

    if text == "➖ Remove Admin":
        await update.message.reply_text("Send user ID to remove from admins:")
        return WAIT_REMOVE_ADMIN

    if text == "📃 List Admins":
        if not admins:
            await update.message.reply_text("No admins yet.")
        else:
            admin_list = "\n".join(admins.keys())
            await update.message.reply_text(f"Admins:\n{admin_list}")
        return ConversationHandler.END

async def add_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_owner(user_id):
        await update.message.reply_text("❌ Only owner can add admins.")
        return ConversationHandler.END
    new_admin_id = update.message.text.strip()
    admins = load_json(ADMINS_FILE)
    admins[new_admin_id] = True
    save_json(ADMINS_FILE, admins)
    await update.message.reply_text(f"✅ Admin {new_admin_id} added.")
    return ConversationHandler.END

async def remove_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_owner(user_id):
        await update.message.reply_text("❌ Only owner can remove admins.")
        return ConversationHandler.END
    admin_id = update.message.text.strip()
    admins = load_json(ADMINS_FILE)
    if admin_id in admins:
        admins.pop(admin_id)
        save_json(ADMINS_FILE, admins)
        await update.message.reply_text(f"✅ Admin {admin_id} removed.")
    else:
        await update.message.reply_text("❌ Admin not found.")
    return ConversationHandler.END

async def post_stored_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = query.from_user.id

    if data == "clear_stored":
        # Implement clearing stored messages for user
        await query.edit_message_text("Stored messages cleared.")
    elif data == "post_all":
        await query.edit_message_text("Posting stored messages to all your channels (feature to implement).")
    elif data == "select_channel":
        await query.edit_message_text("Select channel feature to implement.")
    elif data == "back_main":
        if is_owner(user_id):
            await query.edit_message_text("Back to main menu.", reply_markup=owner_keyboard())
        else:
            await query.edit_message_text("Back to main menu.", reply_markup=admin_keyboard())

def main():
    application = ApplicationBuilder().token(BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text)],
        states={
            WAIT_ADD_CHANNEL: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_channel)],
            WAIT_REMOVE_CHANNEL: [MessageHandler(filters.TEXT & ~filters.COMMAND, remove_channel)],
            WAIT_ADD_ADMIN: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_admin)],
            WAIT_REMOVE_ADMIN: [MessageHandler(filters.TEXT & ~filters.COMMAND, remove_admin)],
        },
        fallbacks=[CommandHandler("start", start)],
    )

    application.add_handler(CommandHandler("start", start))
    application.add_handler(conv_handler)
    application.add_handler(CallbackQueryHandler(post_stored_callback))

    application.run_polling()

if __name__ == "__main__":
    main()
