import os
import json
import logging
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, ConversationHandler,
    filters
)

# Load environment
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
OWNER_ID = int(os.getenv("OWNER_ID"))

# File paths
CHANNELS_FILE = "channels.json"
STORED_FILE = "stored_messages.json"

# States
SELECT_ACTION, CHANNEL_MENU, POST_STORED_MENU = range(3)

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def load_json(file):
    if not os.path.exists(file):
        return {}
    with open(file, "r") as f:
        return json.load(f)


def save_json(file, data):
    with open(file, "w") as f:
        json.dump(data, f, indent=2)


def is_admin(user_id):
    data = load_json("admins.json")
    return user_id == OWNER_ID or str(user_id) in data


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.message.reply_text("🚫 You are not authorized to use this bot.")
        return ConversationHandler.END

    buttons = [
        [InlineKeyboardButton("➕ Add Channel", callback_data="add_channel")],
        [InlineKeyboardButton("📋 List Channels", callback_data="list_channels")],
        [InlineKeyboardButton("❌ Remove Channel", callback_data="remove_channel")],
        [InlineKeyboardButton("📥 Store Forwarded", callback_data="store_forwarded")],
        [InlineKeyboardButton("📤 Post Stored", callback_data="post_stored")],
    ]
    await update.message.reply_text("Welcome to the Bot Panel 👇", reply_markup=InlineKeyboardMarkup(buttons))
    return SELECT_ACTION


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    if not is_admin(user_id):
        await query.message.reply_text("🚫 You are not authorized.")
        return ConversationHandler.END

    data = query.data

    if data == "add_channel":
        await query.message.reply_text("Send me the channel @username or channel ID to add:")
        return CHANNEL_MENU

    elif data == "list_channels":
        channels = load_json(CHANNELS_FILE).get(str(user_id), {})
        if not channels:
            await query.message.reply_text("No channels added yet.")
        else:
            text = "\n".join([f"- {name} (`{chat_id}`)" for chat_id, name in channels.items()])
            await query.message.reply_text(f"Your channels:\n{text}", parse_mode="Markdown")
        return SELECT_ACTION

    elif data == "remove_channel":
        channels = load_json(CHANNELS_FILE).get(str(user_id), {})
        if not channels:
            await query.message.reply_text("You have no channels to remove.")
            return SELECT_ACTION

        buttons = [
            [InlineKeyboardButton(name, callback_data=f"remove|{chat_id}")]
            for chat_id, name in channels.items()
        ]
        buttons.append([InlineKeyboardButton("⬅️ Back", callback_data="back")])
        await query.message.reply_text("Select a channel to remove:", reply_markup=InlineKeyboardMarkup(buttons))
        return SELECT_ACTION

    elif data == "store_forwarded":
        await query.message.reply_text("Forward messages you want to store. Send /done when finished.")
        return POST_STORED_MENU

    elif data == "post_stored":
        buttons = [
            [InlineKeyboardButton("🧹 Clear Stored", callback_data="clear_stored")],
            [InlineKeyboardButton("📤 Post to All", callback_data="post_all")],
            [InlineKeyboardButton("📂 Select Channel", callback_data="select_channel")],
            [InlineKeyboardButton("⬅️ Back", callback_data="back_to_main")]
        ]
        await query.message.reply_text("Post Stored Messages:", reply_markup=InlineKeyboardMarkup(buttons))
        return POST_STORED_MENU

    elif data.startswith("remove|"):
        _, chat_id = data.split("|", 1)
        all_data = load_json(CHANNELS_FILE)
        if str(user_id) in all_data and chat_id in all_data[str(user_id)]:
            del all_data[str(user_id)][chat_id]
            save_json(CHANNELS_FILE, all_data)
            await query.message.reply_text("✅ Channel removed.")
        else:
            await query.message.reply_text("❌ Channel not found.")
        return SELECT_ACTION

    elif data == "clear_stored":
        stored = load_json(STORED_FILE)
        stored[str(user_id)] = []
        save_json(STORED_FILE, stored)
        await query.message.reply_text("✅ Stored messages cleared.")
        return POST_STORED_MENU

    elif data == "post_all":
        stored = load_json(STORED_FILE).get(str(user_id), [])
        if not stored:
            await query.message.reply_text("❌ No messages stored.")
            return POST_STORED_MENU

        channels = load_json(CHANNELS_FILE).get(str(user_id), {})
        if not channels:
            await query.message.reply_text("❌ No channels to post to.")
            return POST_STORED_MENU

        success = 0
        failed = 0
        for msg in stored:
            for chat_id in channels:
                try:
                    await context.bot.copy_message(chat_id=chat_id, from_chat_id=msg["chat_id"], message_id=msg["message_id"])
                    success += 1
                except Exception as e:
                    failed += 1
                    logger.error(e)
        await query.message.reply_text(f"✅ Posted to all channels.\nSuccess: {success}, Failed: {failed}")
        return POST_STORED_MENU

    elif data == "select_channel":
        channels = load_json(CHANNELS_FILE).get(str(user_id), {})
        if not channels:
            await query.message.reply_text("You have no channels.")
            return POST_STORED_MENU

        buttons = [
            [InlineKeyboardButton(name, callback_data=f"select_post|{chat_id}")]
            for chat_id, name in channels.items()
        ]
        buttons.append([InlineKeyboardButton("⬅️ Back", callback_data="post_stored_back")])
        await query.message.reply_text("Choose a channel:", reply_markup=InlineKeyboardMarkup(buttons))
        return POST_STORED_MENU

    elif data.startswith("select_post|"):
        return await post_to_selected_channel(update, context)


async def add_channel_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()

    channels = load_json(CHANNELS_FILE)
    user_channels = channels.get(str(user_id), {})

    if len(user_channels) >= 5:
        await update.message.reply_text("❌ You can only add up to 5 channels.")
        return SELECT_ACTION

    try:
        chat = await context.bot.get_chat(text)
        user_channels[str(chat.id)] = chat.title or chat.username or str(chat.id)
        channels[str(user_id)] = user_channels
        save_json(CHANNELS_FILE, channels)
        await update.message.reply_text(f"✅ Channel '{chat.title}' added.")
    except Exception as e:
        logger.error(e)
        await update.message.reply_text("❌ Failed to add channel. Make sure bot is admin in it.")

    return SELECT_ACTION


async def store_forwarded_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    msg = update.message

    stored = load_json(STORED_FILE)
    user_msgs = stored.get(str(user_id), [])

    user_msgs.append({
        "chat_id": msg.forward_from_chat.id if msg.forward_from_chat else msg.chat.id,
        "message_id": msg.message_id
    })

    stored[str(user_id)] = user_msgs
    save_json(STORED_FILE, stored)
    await update.message.reply_text("✅ Message stored.")


async def done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✅ Done storing messages.")
    return SELECT_ACTION


async def post_to_selected_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    if not is_admin(user_id):
        await query.message.reply_text("❌ Unauthorized.")
        return POST_STORED_MENU

    _, channel_id = query.data.split("|", 1)

    stored = load_json(STORED_FILE).get(str(user_id), [])
    if not stored:
        await query.message.reply_text("❌ No messages stored.")
        return POST_STORED_MENU

    channels = load_json(CHANNELS_FILE).get(str(user_id), {})
    if channel_id not in channels:
        await query.message.reply_text("❌ Invalid channel.")
        return POST_STORED_MENU

    success = 0
    failed = 0
    for msg in stored:
        try:
            await context.bot.copy_message(
                chat_id=channel_id,
                from_chat_id=msg["chat_id"],
                message_id=msg["message_id"]
            )
            success += 1
        except Exception as e:
            failed += 1
            logger.error(f"Failed to post to {channel_id}: {e}")

    await query.message.reply_text(f"✅ Posted {success} messages to '{channels[channel_id]}'. Failed: {failed}")
    return POST_STORED_MENU


def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            SELECT_ACTION: [CallbackQueryHandler(button_handler)],
            CHANNEL_MENU: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_channel_handler)],
            POST_STORED_MENU: [
                MessageHandler(filters.FORWARDED, store_forwarded_message),
                MessageHandler(filters.Regex("^/done$"), done),
                CallbackQueryHandler(button_handler)
            ],
        },
        fallbacks=[CommandHandler("start", start)],
        allow_reentry=True
    )

    app.add_handler(conv)
    app.run_polling()


if __name__ == "__main__":
    main()
