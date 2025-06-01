import os
import json
import logging
from telegram import (
    Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
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

ADMINS_FILE = "admins.json"
CHANNELS_FILE = "channels.json"
STORED_FILE = "stored_messages.json"

# States for ConversationHandler
(
    ADD_ADMIN, REMOVE_ADMIN, LIST_ADMINS,
    ADD_CHANNEL, REMOVE_CHANNEL,
    POST_STORED_MENU, SELECT_CHANNEL_POST,
    ADD_ADMIN_WAIT, REMOVE_ADMIN_WAIT,
    ADD_CHANNEL_WAIT, REMOVE_CHANNEL_WAIT
) = range(11)

def initialize_files():
    for file in [ADMINS_FILE, CHANNELS_FILE, STORED_FILE]:
        if not os.path.exists(file):
            with open(file, 'w') as f:
                if file == ADMINS_FILE:
                    json.dump({str(OWNER_ID): True}, f)
                else:
                    json.dump({}, f)

def load_json(file):
    try:
        with open(file, 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error loading {file}: {e}")
        return {}

def save_json(file, data):
    try:
        with open(file, 'w') as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        logger.error(f"Error saving {file}: {e}")

def is_owner(user_id):
    return user_id == OWNER_ID

def is_admin(user_id):
    admins = load_json(ADMINS_FILE)
    return is_owner(user_id) or str(user_id) in admins

def get_main_keyboard(user_id):
    base_buttons = [
        [KeyboardButton("➕ Add Channel"), KeyboardButton("➖ Remove Channel")],
        [KeyboardButton("📃 My Channels"), KeyboardButton("📤 Post Stored")],
    ]
    if is_owner(user_id):
        base_buttons.append([KeyboardButton("👨‍💻 Manage Admins")])
    return ReplyKeyboardMarkup(base_buttons, resize_keyboard=True)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.message.reply_text("❌ You are not authorized to use this bot.")
        return ConversationHandler.END
    await update.message.reply_text(
        "Welcome!\nChoose an option from the menu below:",
        reply_markup=get_main_keyboard(user_id)
    )
    return ConversationHandler.END

# --------- Admin Management ---------

async def manage_admins_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_owner(user_id):
        await update.message.reply_text("❌ Only owner can manage admins.")
        return ConversationHandler.END

    buttons = [
        [InlineKeyboardButton("➕ Add Admin", callback_data="add_admin")],
        [InlineKeyboardButton("➖ Remove Admin", callback_data="remove_admin")],
        [InlineKeyboardButton("📃 List Admins", callback_data="list_admins")],
        [InlineKeyboardButton("⬅️ Back", callback_data="back_to_main")]
    ]
    await update.message.reply_text("Manage Admins Menu:", reply_markup=InlineKeyboardMarkup(buttons))
    return LIST_ADMINS

async def add_admin_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.message.reply_text("Send the user ID to ADD as admin:")
    return ADD_ADMIN_WAIT

async def add_admin_finish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if not is_owner(user_id):
        await update.message.reply_text("❌ Only owner can add admins.")
        return ConversationHandler.END

    text = update.message.text.strip()
    if not text.isdigit():
        await update.message.reply_text("❌ Invalid user ID. Send numeric user ID.")
        return ADD_ADMIN_WAIT

    admins = load_json(ADMINS_FILE)
    if text in admins:
        await update.message.reply_text("⚠️ This user is already an admin.")
        return ConversationHandler.END

    admins[text] = True
    save_json(ADMINS_FILE, admins)
    await update.message.reply_text(f"✅ User {text} added as admin.")
    return ConversationHandler.END

async def remove_admin_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.message.reply_text("Send the user ID to REMOVE from admins:")
    return REMOVE_ADMIN_WAIT

async def remove_admin_finish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if not is_owner(user_id):
        await update.message.reply_text("❌ Only owner can remove admins.")
        return ConversationHandler.END

    text = update.message.text.strip()
    admins = load_json(ADMINS_FILE)
    if text not in admins:
        await update.message.reply_text("⚠️ This user is not an admin.")
        return ConversationHandler.END

    if text == str(OWNER_ID):
        await update.message.reply_text("❌ Cannot remove the owner.")
        return ConversationHandler.END

    del admins[text]
    save_json(ADMINS_FILE, admins)
    await update.message.reply_text(f"✅ User {text} removed from admins.")
    return ConversationHandler.END

async def list_admins_show(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    admins = load_json(ADMINS_FILE)
    if not admins:
        await query.message.reply_text("No admins found.")
        return LIST_ADMINS

    text = "👨‍💻 Admins List:\n"
    for admin_id in admins:
        text += f"- {admin_id}\n"
    await query.message.reply_text(text)
    return LIST_ADMINS

async def back_to_main(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    await query.message.reply_text(
        "Returning to main menu:",
        reply_markup=get_main_keyboard(user_id)
    )
    return ConversationHandler.END

# --------- Channel Management ---------

async def add_channel_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if not is_admin(user_id):
        await update.message.reply_text("❌ You are not authorized.")
        return ConversationHandler.END
    await update.message.reply_text("Send the channel ID or username to add (e.g., @ChannelUsername or -100123456789):")
    return ADD_CHANNEL_WAIT

async def add_channel_finish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if not is_admin(user_id):
        await update.message.reply_text("❌ You are not authorized.")
        return ConversationHandler.END

    channel_id_or_username = update.message.text.strip()

    try:
        chat = await context.bot.get_chat(channel_id_or_username)
        if chat.type not in ["channel", "supergroup", "group"]:
            await update.message.reply_text("❌ Invalid channel or group.")
            return ConversationHandler.END
        # Check if bot is admin in the channel
        chat_member = await context.bot.get_chat_member(chat_id=chat.id, user_id=context.bot.id)
        if chat_member.status not in ['administrator', 'creator']:
            await update.message.reply_text("❌ Bot must be an admin in the channel.")
            return ConversationHandler.END
    except Exception as e:
        await update.message.reply_text(f"❌ Error fetching chat: {e}")
        return ConversationHandler.END

    channels = load_json(CHANNELS_FILE)
    user_channels = channels.get(str(user_id), {})
    if str(chat.id) in user_channels:
        await update.message.reply_text(f"⚠️ Channel '{chat.title}' is already added.")
        return ConversationHandler.END
    user_channels[str(chat.id)] = chat.title or str(chat.id)
    channels[str(user_id)] = user_channels
    save_json(CHANNELS_FILE, channels)

    await update.message.reply_text(f"✅ Channel '{chat.title}' added successfully.")
    return ConversationHandler.END

async def remove_channel_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if not is_admin(user_id):
        await update.message.reply_text("❌ You are not authorized.")
        return ConversationHandler.END
    await update.message.reply_text("Send the channel ID to remove (e.g., -100123456789):")
    return REMOVE_CHANNEL_WAIT

async def remove_channel_finish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if not is_admin(user_id):
        await update.message.reply_text("❌ You are not authorized.")
        return ConversationHandler.END

    channel_id = update.message.text.strip()
    channels = load_json(CHANNELS_FILE)
    user_channels = channels.get(str(user_id), {})

    if channel_id not in user_channels:
        await update.message.reply_text("❌ Channel ID not found in your list.")
        return ConversationHandler.END

    del user_channels[channel_id]
    channels[str(user_id)] = user_channels
    save_json(CHANNELS_FILE, channels)
    await update.message.reply_text("✅ Channel removed successfully.")
    return ConversationHandler.END

async def show_my_channels(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if not is_admin(user_id):
        await update.message.reply_text("❌ You are not authorized.")
        return ConversationHandler.END

    channels = load_json(CHANNELS_FILE)
    user_channels = channels.get(str(user_id), {})

    if not user_channels:
        await update.message.reply_text("You have not added any channels yet.")
        return ConversationHandler.END

    text = "📃 Your Channels:\n"
    for cid, cname in user_channels.items():
        text += f"- {cname} ({cid})\n"
    await update.message.reply_text(text)
    return ConversationHandler.END

# --------- Post Stored Menu ---------

async def post_stored_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if not is_admin(user_id):
        await update.message.reply_text("❌ Unauthorized.")
        return ConversationHandler.END

    buttons = [
        [InlineKeyboardButton("🧹 Clear Stored", callback_data="clear_stored")],
        [InlineKeyboardButton("📤 Post to All", callback_data="post_all")],
        [InlineKeyboardButton("📂 Select Channel", callback_data="select_channel")],
        [InlineKeyboardButton("⬅️ Back", callback_data="back_to_main")]
    ]
    await update.message.reply_text("Post Stored Messages:", reply_markup=InlineKeyboardMarkup(buttons))
    return POST_STORED_MENU

async def clear_stored(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    stored = load_json(STORED_FILE)
    if str(user_id) in stored:
        stored[str(user_id)] = []
        save_json(STORED_FILE, stored)
        await query.message.reply_text("🧹 Your stored messages have been cleared.")
    else:
        await query.message.reply_text("You have no stored messages.")
    return POST_STORED_MENU

async def post_to_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    stored = load_json(STORED_FILE).get(str(user_id), [])
    if not stored:
        await query.message.reply_text("❌ You have no stored messages to post.")
        return POST_STORED_MENU

    channels = load_json(CHANNELS_FILE).get(str(user_id), {})
    if not channels:
        await query.message.reply_text("❌ You have no channels to post to.")
        return POST_STORED_MENU

    success = 0
    failed = 0
    for cid in channels:
        for msg in stored:
            try:
                await context.bot.copy_message(
                    chat_id=cid,
                    from_chat_id=msg["chat_id"],
                    message_id=msg["message_id"]
                )
                success += 1
            except Exception as e:
                failed += 1
                logger.error(f"Failed to post to {cid}: {e}")
    await query.message.reply_text(f"✅ Posted {success} messages to all your channels. Failed: {failed}")
    return POST_STORED_MENU

async def select_channel_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    channels = load_json(CHANNELS_FILE).get(str(user_id), {})
    if not channels:
        await query.message.reply_text("❌ You have no channels.")
        return POST_STORED_MENU

    buttons = []
    for cid, cname in channels.items():
        buttons.append([InlineKeyboardButton(cname, callback_data=f"post_channel|{cid}")])
    buttons.append([InlineKeyboardButton("⬅️ Back", callback_data="post_stored_back")])

    await query.message.reply_text("Select a channel to post stored messages:", reply_markup=InlineKeyboardMarkup(buttons))
    return SELECT_CHANNEL_POST

async def post_to_selected_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    if not is_admin(user_id):
        await query.message.reply_text("❌ Unauthorized.")
        return POST_STORED_MENU

    data = query.data
    if data == "post_stored_back":
        buttons = [
            [InlineKeyboardButton("🧹 Clear Stored", callback_data="clear_stored")],
            [InlineKeyboardButton("📤 Post to All", callback_data="post_all")],
            [InlineKeyboardButton("📂 Select Channel", callback_data="select_channel")],
            [InlineKeyboardButton("⬅️ Back", callback_data="back_to_main")]
        ]
        await query.message.reply_text("Post Stored Messages:", reply_markup=InlineKeyboardMarkup(buttons))
        return POST_STORED_MENU

    _, channel_id = data.split("|", 1)

    stored = load_json(STORED_FILE).get(str(user_id), [])
    if not stored:
        await query.message.reply_text("❌ You have no stored messages to post.")
        return POST_STORED_MENU

    channels = load_json(CHANNELS_FILE).get(str(user_id), {})
    if channel_id not in channels:
        await query.message.reply_text("❌ Invalid channel selected.")
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

    await query.message.reply_text(f"✅ Posted {success} messages to channel {channels[channel_id]}. Failed: {failed}")
    return POST_STORED_MENU

async def store_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if not is_admin(user_id):
        return

    if update.message.chat.type != "private":
        return

    stored = load_json(STORED_FILE)
    user_stored = stored.get(str(user_id), [])
    user_stored.append({
        "chat_id": update.message.chat.id,
        "message_id": update.message.message_id
    })
    stored[str(user_id)] = user_stored
    save_json(STORED_FILE, stored)
    await update.message.reply_text("✅ Message stored successfully.")

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    await update.message.reply_text(
        "Operation cancelled.", reply_markup=get_main_keyboard(user_id)
    )
    return ConversationHandler.END

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "add_admin":
        return await add_admin_start(update, context)
    elif data == "remove_admin":
        return await remove_admin_start(update, context)
    elif data == "list_admins":
        return await list_admins_show(update, context)
    elif data == "back_to_main":
        return await back_to_main(update, context)
    elif data == "clear_stored":
        return await clear_stored(update, context)
    elif data == "post_all":
        return await post_to_all(update, context)
    elif data == "select_channel":
        return await select_channel_post(update, context)
    elif data.startswith("post_channel|"):
        return await post_to_selected_channel(update, context)
    elif data == "post_stored_back":
        return await post_to_selected_channel(update, context)
    else:
        await query.message.reply_text("Unknown action.")
        return ConversationHandler.END

def main():
    initialize_files()
    application = Application.builder().token(BOT_TOKEN).build()

    # Conversation handler for admin management
    admin_conv = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex("👨‍💻 Manage Admins"), manage_admins_menu)
        ],
        states={
            LIST_ADMINS: [CallbackQueryHandler(button_callback)],
            ADD_ADMIN_WAIT: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_admin_finish)],
            REMOVE_ADMIN_WAIT: [MessageHandler(filters.TEXT & ~filters.COMMAND, remove_admin_finish)],
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    )

    # Conversation handler for channel management
    channel_conv = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex("➕ Add Channel"), add_channel_start),
            MessageHandler(filters.Regex("➖ Remove Channel"), remove_channel_start),
            MessageHandler(filters.Regex("📃 My Channels"), show_my_channels),
            MessageHandler(filters.Regex("📤 Post Stored"), post_stored_menu),
        ],
        states={
            ADD_CHANNEL_WAIT: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_channel_finish)],
            REMOVE_CHANNEL_WAIT: [MessageHandler(filters.TEXT & ~filters.COMMAND, remove_channel_finish)],
            POST_STORED_MENU: [CallbackQueryHandler(button_callback)],
            SELECT_CHANNEL_POST: [CallbackQueryHandler(button_callback)],
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    )

    application.add_handler(CommandHandler("start", start))
    application.add_handler(admin_conv)
    application.add_handler(channel_conv)
    application.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, store_message))

    application.run_polling()

if __name__ == "__main__":
    main()
