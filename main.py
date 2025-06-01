import json
import os
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    ApplicationBuilder, CommandHandler, ContextTypes,
    MessageHandler, ConversationHandler, filters
)
from dotenv import load_dotenv

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
OWNER_ID = int(os.getenv("OWNER_ID"))
ADMINS_FILE = "admins.json"

ADD_ADMIN = 1

def load_json(filename):
    if not os.path.exists(filename):
        return {}
    with open(filename, "r") as f:
        return json.load(f)

def save_json(filename, data):
    with open(filename, "w") as f:
        json.dump(data, f, indent=4)

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
    await update.message.reply_text(
        "Welcome to the bot!",
        reply_markup=get_main_keyboard(user_id)
    )

async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text

    if text == "🧑‍💻 Manage Admins" and user_id == OWNER_ID:
        keyboard = [
            [KeyboardButton("➕ Add Admin")],
            [KeyboardButton("➖ Remove Admin")],
            [KeyboardButton("📃 List Admins")],
            [KeyboardButton("🔙 Back")]
        ]
        await update.message.reply_text(
            "Choose an action:",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        )

    elif text == "➕ Add Admin" and user_id == OWNER_ID:
        await update.message.reply_text("Send the user ID to add as admin (or /cancel to abort):")
        return ADD_ADMIN

    elif text == "📃 List Admins" and user_id == OWNER_ID:
        admins = load_json(ADMINS_FILE)
        admin_list = "\n".join(admins.keys()) or "No admins found."
        await update.message.reply_text(f"👥 Admins:\n{admin_list}")

    elif text == "🔙 Back" and user_id == OWNER_ID:
        await update.message.reply_text(
            "Back to menu.",
            reply_markup=get_main_keyboard(user_id)
        )

    else:
        await update.message.reply_text("Unknown command. Please use the menu.")

async def add_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    new_id = update.message.text.strip()

    if not new_id.isdigit():
        await update.message.reply_text("❌ Invalid user ID. Must be numeric.")
        return ConversationHandler.END

    if int(new_id) == OWNER_ID:
        await update.message.reply_text("⚠️ Already the owner.")
        return ConversationHandler.END

    admins = load_json(ADMINS_FILE)
    if new_id in admins:
        await update.message.reply_text("Already an admin.")
    else:
        admins[new_id] = True
        save_json(ADMINS_FILE, admins)
        await update.message.reply_text("✅ Admin added.")

    await update.message.reply_text(
        "Back to menu.",
        reply_markup=get_main_keyboard(user_id)
    )
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Cancelled.", reply_markup=get_main_keyboard(update.effective_user.id))
    return ConversationHandler.END

if __name__ == '__main__':
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    admin_conv_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.TEXT & filters.Regex("➕ Add Admin"), text_handler)],
        states={
            ADD_ADMIN: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_admin)]
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        allow_reentry=True
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(admin_conv_handler)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))

    app.run_polling()
