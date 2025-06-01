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

# States for ConversationHandler
(
    ADD_ADMIN, REMOVE_ADMIN, LIST_ADMINS,
    ADD_CHANNEL, REMOVE_CHANNEL,
    POST_SUBMENU, SELECT_CHANNEL_POST,
    ADD_ADMIN_WAIT, REMOVE_ADMIN_WAIT,
    ADD_CHANNEL_WAIT, REMOVE_CHANNEL_WAIT
) = range(11)

# Utility Functions

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

def is_owner(user_id):
    return user_id == OWNER_ID

def is_admin(user_id):
    admins = load_json(ADMINS_FILE)
    return is_owner(user_id) or str(user_id) in admins

def get_user_channels(user_id):
    channels = load_json(CHANNELS_FILE)
    return channels.get(str(user_id), {})

def save_user_channels(user_id, user_channels):
    channels = load_json(CHANNELS_FILE)
    channels[str(user_id)] = user_channels
    save_json(CHANNELS_FILE, channels)

def get_user_stored_messages(user_id):
    stored = load_json(STORED_FILE)
    return stored.get(str(user_id), [])

def save_user_stored_messages(user_id, messages):
    stored = load_json(STORED_FILE)
    stored[str(user_id)] = messages
    save_json(STORED_FILE, stored)

# Keyboards

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

def post_stored_keyboard():
    buttons = [
        [InlineKeyboardButton("🧹 Clear Stored", callback_data="clear_stored")],
        [InlineKeyboardButton("📤 Post to All", callback_data="post_all")],
        [InlineKeyboardButton("📂 Select Channel", callback_data="select_channel")],
        [InlineKeyboardButton("⬅️ Back", callback_data="back_main")]
    ]
    return InlineKeyboardMarkup(buttons)

def select_channel_keyboard(channels: dict):
    buttons = []
    for cid, cname in channels.items():
        buttons.append([InlineKeyboardButton(cname, callback_data=f"post_to|{cid}")])
    buttons.append([InlineKeyboardButton("⬅️ Back", callback_data="back_post_submenu")])
    return InlineKeyboardMarkup(buttons)

def manage_admins_keyboard():
    buttons = [
        [InlineKeyboardButton("➕ Add Admin", callback_data="add_admin")],
        [InlineKeyboardButton("➖ Remove Admin", callback_data="remove_admin")],
        [InlineKeyboardButton("📃 List Admins", callback_data="list_admins")],
        [InlineKeyboardButton("⬅️ Back", callback_data="back_main")]
    ]
    return InlineKeyboardMarkup(buttons)

# Handlers

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.message.reply_text("❌ Access denied. You are not admin or owner.")
        return

    if is_owner(user_id):
        await update.message.reply_text(
            "Welcome Owner! Choose an option:", reply_markup=owner_main_keyboard())
    else:
        await update.message.reply_text(
            "Welcome Admin! Choose an option:", reply_markup=admin_main_keyboard())

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text

    if not is_admin(user_id):
        await update.message.reply_text("❌ Access denied.")
        return

    # Exit option
    if text == "⬅️ Exit":
        await update.message.reply_text("Bye! Use /start to open menu again.",
                                        reply_markup=ReplyKeyboardMarkup([], resize_keyboard=True))
        return ConversationHandler.END

    # Add Channel
    if text == "➕ Add Channel":
        await update.message.reply_text("Send channel ID or username to add:")
        return ADD_CHANNEL_WAIT

    # Remove Channel
    if text == "➖ Remove Channel":
        user_channels = get_user_channels(user_id)
        if not user_channels:
            await update.message.reply_text("❌ You have no channels to remove.")
            return ConversationHandler.END
        channel_list = "\n".join([f"{cname} ({cid})" for cid, cname in user_channels.items()])
        await update.message.reply_text(
            f"Your channels:\n{channel_list}\n\nSend channel ID to remove:")
        return REMOVE_CHANNEL_WAIT

    # My Channels
    if text == "📃 My Channels":
        user_channels = get_user_channels(user_id)
        if not user_channels:
            await update.message.reply_text("You have no channels added.")
        else:
            channel_list = "\n".join([f"{cname} ({cid})" for cid, cname in user_channels.items()])
            await update.message.reply_text(f"Your channels:\n{channel_list}")
        return ConversationHandler.END

    # Post Stored
    if text == "📤 Post Stored":
        # Show post submenu with inline buttons
        await update.message.reply_text("Choose action for stored messages:",
                                        reply_markup=post_stored_keyboard())
        return POST_SUBMENU

    # Manage Admins (only owner)
    if text == "👨‍💻 Manage Admins":
        if not is_owner(user_id):
            await update.message.reply_text("❌ Access denied.")
            return ConversationHandler.END
        await update.message.reply_text(
            "Manage Admins:",
            reply_markup=manage_admins_keyboard())
        return ADD_ADMIN

    await update.message.reply_text("❌ Unknown command or option. Use /start to begin.")
    return ConversationHandler.END

# Add Channel Handler
async def add_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    cid = update.message.text.strip()

    try:
        chat = await context.bot.get_chat(cid)
    except Exception:
        await update.message.reply_text("❌ Invalid channel ID or username.")
        return ConversationHandler.END

    user_channels = get_user_channels(user_id)
    user_channels[cid] = chat.title or cid
    save_user_channels(user_id, user_channels)

    await update.message.reply_text(f"✅ Channel added: {chat.title or cid}")
    return ConversationHandler.END

# Remove Channel Handler
async def remove_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    cid = update.message.text.strip()

    user_channels = get_user_channels(user_id)
    if cid in user_channels:
        del user_channels[cid]
        save_user_channels(user_id, user_channels)
        await update.message.reply_text("✅ Channel removed.")
    else:
        await update.message.reply_text("❌ Channel ID not found in your list.")
    return ConversationHandler.END

# Handle forwarded messages to store
async def handle_forwarded_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        return

    forwarded = update.message

    stored = get_user_stored_messages(user_id)
    # Store chat_id and message_id to forward later
    stored.append({
        "chat_id": forwarded.forward_from_chat.id if forwarded.forward_from_chat else forwarded.chat_id,
        "message_id": forwarded.message_id
    })
    save_user_stored_messages(user_id, stored)
    await update.message.reply_text(f"✅ Message stored. Total stored: {len(stored)}")

# Post submenu callback handler
async def post_submenu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()

    if not is_admin(user_id):
        await query.message.edit_text("❌ Access denied.")
        return

    data = query.data

    if data == "clear_stored":
        save_user_stored_messages(user_id, [])
        await query.message.edit_text("🧹 All
