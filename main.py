import os
import json
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    ContextTypes, filters, ConversationHandler
)
from dotenv import load_dotenv

# Load .env
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
OWNER_ID = int(os.getenv("OWNER_ID", 0))

# Setup Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# File names
ADMINS_FILE = "admins.json"
CHANNELS_FILE = "channels.json"
STORED_FILE = "stored.json"

# States
ADD_ADMIN, REMOVE_ADMIN, ADD_CHANNEL, REMOVE_CHANNEL = range(4)

# Init empty files if not exist
for f in [ADMINS_FILE, CHANNELS_FILE, STORED_FILE]:
    if not os.path.exists(f):
        with open(f, "w") as file:
            json.dump({}, file)

def load_json(path): 
    try: return json.load(open(path))
    except: return {}

def save_json(path, data): 
    json.dump(data, open(path, "w"), indent=2)

def is_owner(uid): return uid == OWNER_ID

def is_admin(uid): 
    admins = load_json(ADMINS_FILE)
    return is_owner(uid) or str(uid) in admins

def get_main_keyboard(uid):
    keyboard = [
        [InlineKeyboardButton("➕ Add Channel", callback_data="add_channel"),
         InlineKeyboardButton("➖ Remove Channel", callback_data="remove_channel")],
        [InlineKeyboardButton("📃 My Channels", callback_data="list_channels"),
         InlineKeyboardButton("📤 Post Stored", callback_data="post_stored")]
    ]
    if is_owner(uid):
        keyboard.append([InlineKeyboardButton("👨‍💻 Manage Admins", callback_data="manage_admins")])
    return InlineKeyboardMarkup(keyboard)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        return await update.message.reply_text("❌ Access denied.")
    await update.message.reply_text("👋 Welcome Admin!", reply_markup=get_main_keyboard(user_id))

async def handle_forward(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id): return

    msg = update.message
    context.user_data["forwarded"] = msg
    stored = load_json(STORED_FILE)
    stored[str(user_id)] = {
        "chat_id": msg.forward_from_chat.id,
        "message_id": msg.message_id
    }
    save_json(STORED_FILE, stored)

    await update.message.reply_text("✅ Message stored. Now choose where to post:", reply_markup=InlineKeyboardMarkup([
        [InlineKeyboardButton("📤 Post to All", callback_data="post_all")],
        [InlineKeyboardButton("📂 Select Channels", callback_data="select_channels")]
    ]))

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()
    data = query.data

    if not is_admin(user_id):
        return await query.message.reply_text("❌ Access denied.")

    admins = load_json(ADMINS_FILE)
    channels = load_json(CHANNELS_FILE)
    user_channels = channels.get(str(user_id), {})

    if data == "post_all":
        msg = context.user_data.get("forwarded")
        if not msg or not user_channels:
            return await query.message.reply_text("⚠️ No message or no channels.")
        success, fail = 0, []
        for cid in user_channels:
            try:
                await msg.copy(chat_id=cid)
                success += 1
            except:
                fail.append(cid)
        await query.message.reply_text(f"✅ Posted to {success} channels. ❌ Failed: {len(fail)}")

    elif data == "select_channels":
        buttons = [[InlineKeyboardButton(v, callback_data=f"post_to|{k}")] for k, v in user_channels.items()]
        await query.message.reply_text("📂 Select channel:", reply_markup=InlineKeyboardMarkup(buttons))

    elif data.startswith("post_to|"):
        cid = data.split("|")[1]
        msg = context.user_data.get("forwarded")
        try:
            await msg.copy(chat_id=cid)
            await query.message.reply_text("✅ Posted.")
        except:
            await query.message.reply_text("❌ Failed to post.")

    elif data == "add_channel":
        await query.message.reply_text("Send channel ID or @username:")
        return ADD_CHANNEL

    elif data == "remove_channel":
        await query.message.reply_text("Send channel ID to remove:")
        return REMOVE_CHANNEL

    elif data == "list_channels":
        if not user_channels:
            await query.message.reply_text("ℹ️ No channels added.")
        else:
            txt = "\n".join([f"{v} ({k})" for k, v in user_channels.items()])
            await query.message.reply_text(txt)

    elif data == "manage_admins" and is_owner(user_id):
        await query.message.reply_text("👨‍💻 Admin Panel", reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("Add Admin", callback_data="add_admin")],
            [InlineKeyboardButton("Remove Admin", callback_data="remove_admin")],
            [InlineKeyboardButton("👥 Admin List", callback_data="admin_list")]
        ]))

    elif data == "add_admin" and is_owner(user_id):
        await query.message.reply_text("Send user ID to add:")
        return ADD_ADMIN

    elif data == "remove_admin" and is_owner(user_id):
        await query.message.reply_text("Send user ID to remove:")
        return REMOVE_ADMIN

    elif data == "admin_list" and is_owner(user_id):
        text = f"👑 Owner: {OWNER_ID}\n\n"
        if admins:
            text += "🛡️ Admins:\n" + "\n".join(admins.keys())
        else:
            text += "No other admins."
        await query.message.reply_text(text)

    elif data == "post_stored":
        stored = load_json(STORED_FILE)
        if not stored.get(str(user_id)):
            return await query.message.reply_text("❌ No stored message.")
        try:
            context.user_data["forwarded"] = await context.bot.forward_message(
                chat_id=user_id,
                from_chat_id=stored[str(user_id)]["chat_id"],
                message_id=stored[str(user_id)]["message_id"]
            )
            await query.message.reply_text("✅ Message loaded.\nChoose where to post:", reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📤 Post to All", callback_data="post_all")],
                [InlineKeyboardButton("📂 Select Channels", callback_data="select_channels")]
            ]))
        except:
            await query.message.reply_text("⚠️ Failed to load stored message.")

async def add_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.message.text.strip()
    admins = load_json(ADMINS_FILE)
    admins[uid] = True
    save_json(ADMINS_FILE, admins)
    await update.message.reply_text("✅ Admin added.")

async def remove_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.message.text.strip()
    admins = load_json(ADMINS_FILE)
    if uid in admins:
        del admins[uid]
        save_json(ADMINS_FILE, admins)
        await update.message.reply_text("✅ Admin removed.")
    else:
        await update.message.reply_text("❌ Admin not found.")

async def add_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    cid = update.message.text.strip()
    try:
        chat = await context.bot.get_chat(cid)
        title = chat.title or cid
        channels = load_json(CHANNELS_FILE)
        user_channels = channels.get(user_id, {})
        if len(user_channels) >= 5:
            return await update.message.reply_text("❌ Max 5 channels allowed.")
        user_channels[cid] = title
        channels[user_id] = user_channels
        save_json(CHANNELS_FILE, channels)
        await update.message.reply_text("✅ Channel added.")
    except:
        await update.message.reply_text("❌ Invalid channel or bot not admin there.")

async def remove_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    cid = update.message.text.strip()
    channels = load_json(CHANNELS_FILE)
    if cid in channels.get(user_id, {}):
        del channels[user_id][cid]
        save_json(CHANNELS_FILE, channels)
        await update.message.reply_text("✅ Channel removed.")
    else:
        await update.message.reply_text("❌ Channel not found.")

def main():
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
