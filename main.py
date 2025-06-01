import os
import json
import logging
from telegram import (
    Update, ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardButton, InlineKeyboardMarkup
)
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    ConversationHandler, ContextTypes, filters
)
from dotenv import load_dotenv

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
OWNER_ID = int(os.getenv("OWNER_ID", 0))

# JSON files for persistence
ADMINS_FILE = 'admins.json'
CHANNELS_FILE = 'channels.json'
STORED_FILE = 'stored.json'

# Conversation states
(
    WAIT_ADD_CHANNEL,
    WAIT_REMOVE_CHANNEL,
    WAIT_ADD_ADMIN,
    WAIT_REMOVE_ADMIN,
) = range(4)

def load_json(filename):
    try:
        with open(filename, 'r') as f:
            return json.load(f)
    except Exception:
        return {}

def save_json(filename, data):
    with open(filename, 'w') as f:
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

def get_all_admins():
    return load_json(ADMINS_FILE)

def save_all_admins(admins):
    save_json(ADMINS_FILE, admins)

def get_stored_messages(user_id):
    stored = load_json(STORED_FILE)
    return stored.get(str(user_id), [])

def save_stored_messages(user_id, messages):
    all_stored = load_json(STORED_FILE)
    all_stored[str(user_id)] = messages
    save_json(STORED_FILE, all_stored)

def owner_main_keyboard():
    buttons = [
        [KeyboardButton("➕ Add Channel"), KeyboardButton("➖ Remove Channel")],
        [KeyboardButton("📃 My Channels"), KeyboardButton("📤 Post Stored")],
        [KeyboardButton("👨‍💻 Manage Admins")],
        [KeyboardButton("⬅️ Exit")]
    ]
    return ReplyKeyboardMarkup(buttons, resize_keyboard=True)

def admin_main_keyboard():
    buttons = [
        [KeyboardButton("➕ Add Channel"), KeyboardButton("➖ Remove Channel")],
        [KeyboardButton("📃 My Channels"), KeyboardButton("📤 Post Stored")],
        [KeyboardButton("⬅️ Exit")]
    ]
    return ReplyKeyboardMarkup(buttons, resize_keyboard=True)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.message.reply_text("❌ Access denied!")
        return ConversationHandler.END

    if is_owner(user_id):
        await update.message.reply_text("Welcome Owner! Choose an option:", reply_markup=owner_main_keyboard())
    else:
        await update.message.reply_text("Welcome Admin! Choose an option:", reply_markup=admin_main_keyboard())
    return ConversationHandler.END

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text

    if not is_admin(user_id):
        await update.message.reply_text("❌ Access denied!")
        return ConversationHandler.END

    if text == "⬅️ Exit":
        await update.message.reply_text("Bye! Use /start to open menu again.", reply_markup=ReplyKeyboardMarkup([], resize_keyboard=True))
        return ConversationHandler.END

    if text == "➕ Add Channel":
        await update.message.reply_text("Send channel ID or username to add:")
        return WAIT_ADD_CHANNEL

    if text == "➖ Remove Channel":
        user_channels = get_user_channels(user_id)
        if not user_channels:
            await update.message.reply_text("You have no channels to remove.")
            return ConversationHandler.END
        channels_list = "\n".join([f"{name} ({cid})" for cid, name in user_channels.items()])
        await update.message.reply_text(f"Your channels:\n{channels_list}\nSend channel ID to remove:")
        return WAIT_REMOVE_CHANNEL

    if text == "📃 My Channels":
        user_channels = get_user_channels(user_id)
        if not user_channels:
            await update.message.reply_text("You haven't added any channels yet.")
        else:
            channels_list = "\n".join([f"{name} ({cid})" for cid, name in user_channels.items()])
            await update.message.reply_text(f"Your channels:\n{channels_list}")
        return ConversationHandler.END

    if text == "📤 Post Stored":
        # Show post submenu with inline buttons
        keyboard = [
            [InlineKeyboardButton("🧹 Clear Stored", callback_data="clear_stored")],
            [InlineKeyboardButton("📤 Post to All", callback_data="post_all")],
            [InlineKeyboardButton("📂 Select Channel", callback_data="select_channel")],
            [InlineKeyboardButton("⬅️ Back", callback_data="back_main")]
        ]
        await update.message.reply_text("Post Stored Menu:", reply_markup=InlineKeyboardMarkup(keyboard))
        return ConversationHandler.END

    if text == "👨‍💻 Manage Admins":
        if not is_owner(user_id):
            await update.message.reply_text("❌ Only owner can manage admins.")
            return ConversationHandler.END
        keyboard = [
            [KeyboardButton("➕ Add Admin"), KeyboardButton("➖ Remove Admin")],
            [KeyboardButton("📃 List Admins")],
            [KeyboardButton("⬅️ Back")]
        ]
        await update.message.reply_text("Manage Admins Menu:", reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))
        return WAIT_ADD_ADMIN  # We'll use same state to handle admin management text commands

    await update.message.reply_text("❓ Unknown command. Use /start to see menu.")
    return ConversationHandler.END

async def add_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    channel_id = update.message.text.strip()
    try:
        # Optionally verify channel exists by fetching chat
        chat = await context.bot.get_chat(channel_id)
        channel_name = chat.title or channel_id
    except Exception as e:
        await update.message.reply_text("❌ Invalid channel ID or username.")
        return ConversationHandler.END

    user_channels = get_user_channels(user_id)
    user_channels[channel_id] = channel_name
    save_user_channels(user_id, user_channels)

    await update.message.reply_text(f"✅ Channel '{channel_name}' added successfully.")
    return ConversationHandler.END

async def remove_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    channel_id = update.message.text.strip()

    user_channels = get_user_channels(user_id)
    if channel_id in user_channels:
        removed = user_channels.pop(channel_id)
        save_user_channels(user_id, user_channels)
        await update.message.reply_text(f"✅ Channel '{removed}' removed successfully.")
    else:
        await update.message.reply_text("❌ Channel ID not found in your list.")
    return ConversationHandler.END

async def manage_admins(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()

    if not is_owner(user_id):
        await update.message.reply_text("❌ Only owner can manage admins.")
        return ConversationHandler.END

    admins = get_all_admins()

    if text == "⬅️ Back":
        await update.message.reply_text("Back to main menu.", reply_markup=owner_main_keyboard())
        return ConversationHandler.END

    if text == "➕ Add Admin":
        await update.message.reply_text("Send user ID to add as admin:")
        return WAIT_ADD_ADMIN

    if text == "➖ Remove Admin":
        await update.message.reply_text("Send user ID to remove from admins:")
        return WAIT_REMOVE_ADMIN

    if text == "📃 List Admins":
        if not admins:
            await update.message.reply_text("No admins added yet.")
        else:
            admins_list = "\n".join(admins.keys())
            await update.message.reply_text(f"Admins:\n{admins_list}")
        return ConversationHandler.END

    await update.message.reply_text("❓ Unknown command in Manage Admins. Use the buttons.")
    return ConversationHandler.END

async def add_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_owner(user_id):
        await update.message.reply_text("❌ Only owner can add admins.")
        return ConversationHandler.END

    admin_id = update.message.text.strip()
    admins = get_all_admins
