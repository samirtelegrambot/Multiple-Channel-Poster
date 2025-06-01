import os
import json
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMedia
from telegram.ext import (Application, CommandHandler, MessageHandler, CallbackQueryHandler,
                          ConversationHandler, ContextTypes, filters)
from dotenv import load_dotenv
import telegram.error

# Logging setup
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
OWNER_ID = int(os.getenv("OWNER_ID", 0))

# Files
ADMINS_FILE = 'admins.json'
CHANNELS_FILE = 'channels.json'
STORED_FILE = 'stored_message.json'

# States
ADD_ADMIN, REMOVE_ADMIN, ADD_CHANNEL, REMOVE_CHANNEL = range(4)

# Initialize storage
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

# Main keyboard
def get_main_keyboard(user_id):
    keyboard = [
        [InlineKeyboardButton("âž• Add Channel", callback_data="add_channel"),
         InlineKeyboardButton("âž– Remove Channel", callback_data="remove_channel")],
        [InlineKeyboardButton("ðŸ“ƒ My Channels", callback_data="list_channels"),
         InlineKeyboardButton("ðŸ“¤ Post Stored", callback_data="post_stored")]
    ]
    if user_id == OWNER_ID:
        keyboard.append([InlineKeyboardButton("ðŸ§‘â€ðŸ’» Manage Admins", callback_data="manage_admins")])
    return InlineKeyboardMarkup(keyboard)

# Start command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.message.reply_text("âŒ Access denied.")
        return

    await update.message.reply_text("Welcome Admin!", reply_markup=get_main_keyboard(user_id))

# Forwarded message handler
async def handle_forward(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        return

    forwarded = update.message
    context.user_data['forwarded'] = forwarded

    # Store message reference for reuse
    stored = load_json(STORED_FILE)
    stored[str(user_id)] = {"chat_id": forwarded.forward_from_chat.id, "message_id": forwarded.message_id}
    save_json(STORED_FILE, stored)

    await update.message.reply_text("âœ… Message stored.
Choose where to post:", reply_markup=InlineKeyboardMarkup([
        [InlineKeyboardButton("ðŸ“¤ Post to All", callback_data="post_all")],
        [InlineKeyboardButton("ðŸ“‚ Select Channels", callback_data="select_channels")]
    ]))

# Callback handler
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = query.data

    if not is_admin(user_id):
        await query.message.reply_text("âŒ Access denied.")
        return

    if data == "post_all":
        channels = load_json(CHANNELS_FILE)
        msg = context.user_data.get("forwarded")
        if not msg or not channels:
            await query.message.reply_text("âš ï¸ No message or channels.")
            return

        success, fail = 0, []
        for cid in channels:
            try:
                await msg.copy(chat_id=cid)
                success += 1
            except:
                fail.append(cid)
        await query.message.reply_text(f"âœ… Posted to {success}, Failed: {len(fail)}")

    elif data == "select_channels":
        channels = load_json(CHANNELS_FILE)
        buttons = [[InlineKeyboardButton(name, callback_data=f"post_to|{cid}")]
                   for cid, name in channels.items()]
        await query.message.reply_text("Select a channel:", reply_markup=InlineKeyboardMarkup(buttons))

    elif data.startswith("post_to|"):
        cid = data.split("|")[1]
        msg = context.user_data.get("forwarded")
        try:
            await msg.copy(chat_id=cid)
            await query.message.reply_text("âœ… Posted.")
        except:
            await query.message.reply_text("âŒ Failed to post.")

    elif data == "add_channel":
        await query.message.reply_text("Send channel ID or username:")
        return ADD_CHANNEL

    elif data == "remove_channel":
        await query.message.reply_text("Send channel ID to remove:")
        return REMOVE_CHANNEL

    elif data == "list_channels":
        channels = load_json(CHANNELS_FILE)
        if not channels:
            await query.message.reply_text("No channels added.")
        else:
            await query.message.reply_text("\n".join([f"{v} ({k})" for k, v in channels.items()]))

    elif data == "manage_admins" and user_id == OWNER_ID:
        await query.message.reply_text("Admin panel", reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("Add Admin", callback_data="add_admin")],
            [InlineKeyboardButton("Remove Admin", callback_data="remove_admin")],
        ]))

    elif data == "add_admin" and user_id == OWNER_ID:
        await query.message.reply_text("Send user ID to add:")
        return ADD_ADMIN

    elif data == "remove_admin" and user_id == OWNER_ID:
        await query.message.reply_text("Send user ID to remove:")
        return REMOVE_ADMIN

    elif data == "post_stored":
        stored = load_json(STORED_FILE)
        if not stored.get(str(user_id)):
            await query.message.reply_text("No stored message.")
            return

        context.user_data["forwarded"] = await context.bot.forward_message(
            chat_id=user_id,
            from_chat_id=stored[str(user_id)]["chat_id"],
            message_id=stored[str(user_id)]["message_id"]
        )
        await query.message.reply_text("Choose where to post:", reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("ðŸ“¤ Post to All", callback_data="post_all")],
            [InlineKeyboardButton("ðŸ“‚ Select Channels", callback_data="select_channels")]
        ]))

# Add admin
async def add_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.message.text.strip()
    admins = load_json(ADMINS_FILE)
    admins[uid] = True
    save_json(ADMINS_FILE, admins)
    await update.message.reply_text("âœ… Admin added.")

# Remove admin
async def remove_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.message.text.strip()
    admins = load_json(ADMINS_FILE)
    if uid in admins:
        del admins[uid]
        save_json(ADMINS_FILE, admins)
        await update.message.reply_text("âœ… Admin removed.")
    else:
        await update.message.reply_text("User not found.")

# Add channel
async def add_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    channel_id = update.message.text.strip()
    try:
        chat = await context.bot.get_chat(channel_id)
        channels = load_json(CHANNELS_FILE)
        channels[channel_id] = chat.title or channel_id
        save_json(CHANNELS_FILE, channels)
        await update.message.reply_text("âœ… Channel added.")
    except:
        await update.message.reply_text("âŒ Failed to add channel.")

# Remove channel
async def remove_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cid = update.message.text.strip()
    channels = load_json(CHANNELS_FILE)
    if cid in channels:
        del channels[cid]
        save_json(CHANNELS_FILE, channels)
        await update.message.reply_text("âœ… Channel removed.")
    else:
        await update.message.reply_text("Channel not found.")

# Main function
def main():
    initialize_files()
    app = Application.builder().token(BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start), CallbackQueryHandler(handle_callback)],
        states={
            ADD_ADMIN: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_admin)],
            REMOVE_ADMIN: [MessageHandler(filters.TEXT & ~filters.COMMAND, remove_admin)],
            ADD_CHANNEL: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_channel)],
            REMOVE_CHANNEL: [MessageHandler(filters.TEXT & ~filters.COMMAND, remove_channel)],
        },
        fallbacks=[],
        allow_reentry=True
    )

    app.add_handler(conv_handler)
    app.add_handler(MessageHandler(filters.FORWARDED, handle_forward))
    logger.info("Bot running...")
    app.run_polling()

if __name__ == "__main__":
    main()
