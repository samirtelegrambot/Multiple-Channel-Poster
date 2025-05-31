import os
import json
import logging
from telegram import Update, KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, ConversationHandler,
    ContextTypes, filters
)
from dotenv import load_dotenv

# Set up logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
OWNER_ID = int(os.getenv("OWNER_ID", 0))

# File paths
ADMINS_FILE = 'admins.json'
CHANNELS_FILE = 'channels.json'

# Conversation states
ADD_ADMIN, REMOVE_ADMIN = range(2)

# Initialize required files
def initialize_files():
    for file in [ADMINS_FILE, CHANNELS_FILE]:
        if not os.path.exists(file):
            with open(file, 'w') as f:
                json.dump({}, f)

# Load JSON
def load_json(file):
    try:
        with open(file, 'r') as f:
            return json.load(f)
    except:
        return {}

# Save JSON
def save_json(file, data):
    with open(file, 'w') as f:
        json.dump(data, f, indent=2)

# Admin check
def is_admin(user_id):
    admins = load_json(ADMINS_FILE)
    return str(user_id) in admins or user_id == OWNER_ID

# Main keyboard
def get_main_keyboard(user_id):
    buttons = [
        [KeyboardButton("➕ Add Channel"), KeyboardButton("➖ Remove Channel")],
        [KeyboardButton("📃 My Channels"), KeyboardButton("📤 Post")]
    ]
    if user_id == OWNER_ID:
        buttons.append([KeyboardButton("🧑‍💻 Manage Admins")])
    return ReplyKeyboardMarkup(buttons, resize_keyboard=True)

# Start command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.message.reply_text("❌ Access denied. Admins only.")
        return
    await update.message.reply_text("Welcome!", reply_markup=get_main_keyboard(user_id))

# Menu handler
async def handle_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text

    if not is_admin(user_id):
        await update.message.reply_text("❌ Access denied.")
        return

    if text == "🧑‍💻 Manage Admins" and user_id == OWNER_ID:
        buttons = [
            [KeyboardButton("➕ Add Admin"), KeyboardButton("➖ Remove Admin")],
            [KeyboardButton("📋 List Admins"), KeyboardButton("🔙 Back")]
        ]
        await update.message.reply_text("Admin Panel:", reply_markup=ReplyKeyboardMarkup(buttons, resize_keyboard=True))
        return

    elif text == "➕ Add Admin" and user_id == OWNER_ID:
        await update.message.reply_text("Send the user ID to add:")
        return ADD_ADMIN

    elif text == "➖ Remove Admin" and user_id == OWNER_ID:
        await update.message.reply_text("Send the user ID to remove:")
        return REMOVE_ADMIN

    elif text == "📋 List Admins" and user_id == OWNER_ID:
        admins = list(load_json(ADMINS_FILE).keys())
        msg = "👮‍♂️ Admins:\n" + "\n".join(admins) if admins else "No admins yet."
        await update.message.reply_text(msg)

    elif text == "🔙 Back":
        await update.message.reply_text("Main menu:", reply_markup=get_main_keyboard(user_id))
        return ConversationHandler.END

# Add admin
async def add_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    new_id = update.message.text.strip()
    if not new_id.isdigit():
        await update.message.reply_text("❌ Invalid ID")
        return ConversationHandler.END
    if new_id == str(OWNER_ID):
        await update.message.reply_text("⚠️ Already the owner")
        return ConversationHandler.END
    admins = load_json(ADMINS_FILE)
    if new_id in admins:
        await update.message.reply_text("Already an admin")
    else:
        admins[new_id] = True
        save_json(ADMINS_FILE, admins)
        await update.message.reply_text("✅ Admin added")
    return ConversationHandler.END

# Remove admin
async def remove_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    del_id = update.message.text.strip()
    if del_id == str(OWNER_ID):
        await update.message.reply_text("❌ Cannot remove owner")
        return ConversationHandler.END
    admins = load_json(ADMINS_FILE)
    if del_id in admins:
        del admins[del_id]
        save_json(ADMINS_FILE, admins)
        await update.message.reply_text("✅ Admin removed")
    else:
        await update.message.reply_text("User not found in admin list")
    return ConversationHandler.END

# Main function
def main():
    initialize_files()
    if not BOT_TOKEN or not OWNER_ID:
        logger.error("BOT_TOKEN or OWNER_ID not set")
        return

    app = Application.builder().token(BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("start", start),
            MessageHandler(filters.TEXT & ~filters.COMMAND, handle_menu)
        ],
        states={
            ADD_ADMIN: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_admin)],
            REMOVE_ADMIN: [MessageHandler(filters.TEXT & ~filters.COMMAND, remove_admin)]
        },
        fallbacks=[],
        allow_reentry=True
    )

    app.add_handler(conv_handler)

    logger.info("Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()
