import os
import json
import logging
import sqlite3
import time
import datetime
import fcntl  # For file locking (Linux/Unix only)
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, ConversationHandler, ContextTypes, filters
from dotenv import load_dotenv
import telegram.error

# Logging setup
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Load .env values
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
OWNER_ID = int(os.getenv("OWNER_ID", 0))

# States
ADD_ADMIN, REMOVE_ADMIN, ADD_CHANNEL, REMOVE_CHANNEL, POST_MESSAGE, CONFIRM_ACTION = range(6)

# Rate limiting
LAST_POST_TIME = {}
POST_RATE = 60  # 60 seconds cooldown

# Lock file to prevent multiple instances
LOCK_FILE = "bot.lock"

def acquire_lock():
    try:
        lock_fd = open(LOCK_FILE, 'w')
        fcntl.flock(lock_fd.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        return lock_fd
    except (IOError, OSError):
        logger.error("Another instance of the bot is already running.")
        return None

def release_lock(lock_fd):
    if lock_fd:
        fcntl.flock(lock_fd.fileno(), fcntl.LOCK_UN)
        lock_fd.close()
        try:
            os.remove(LOCK_FILE)
        except OSError:
            pass

# Initialize SQLite database
def initialize_db():
    try:
        conn = sqlite3.connect('bot_data.db')
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS admins (user_id TEXT PRIMARY KEY)''')
        c.execute('''CREATE TABLE IF NOT EXISTS channels (channel_id TEXT PRIMARY KEY, title TEXT)''')
        c.execute('''CREATE TABLE IF NOT EXISTS logs (timestamp TEXT, user_id TEXT, action TEXT, details TEXT)''')
        conn.commit()
    except sqlite3.Error as e:
        logger.error(f"Error initializing database: {e}")
    finally:
        conn.close()

# Load and save data
def load_admins():
    try:
        conn = sqlite3.connect('bot_data.db')
        c = conn.cursor()
        c.execute("SELECT user_id FROM admins")
        admins = {row[0]: True for row in c.fetchall()}
        return admins
    except sqlite3.Error as e:
        logger.error(f"Error loading admins: {e}")
        return {}
    finally:
        conn.close()

def save_admins(admins):
    try:
        conn = sqlite3.connect('bot_data.db')
        c = conn.cursor()
        c.execute("DELETE FROM admins")
        for admin_id in admins:
            c.execute("INSERT INTO admins (user_id) VALUES (?)", (admin_id,))
        conn.commit()
    except sqlite3.Error as e:
        logger.error(f"Error saving admins: {e}")
    finally:
        conn.close()

def load_channels():
    try:
        conn = sqlite3.connect('bot_data.db')
        c = conn.cursor()
        c.execute("SELECT channel_id, title FROM channels")
        channels = {row[0]: row[1] for row in c.fetchall()}
        return channels
    except sqlite3.Error as e:
        logger.error(f"Error loading channels: {e}")
        return {}
    finally:
        conn.close()

def save_channels(channels):
    try:
        conn = sqlite3.connect('bot_data.db')
        c = conn.cursor()
        c.execute("DELETE FROM channels")
        for channel_id, title in channels.items():
            c.execute("INSERT INTO channels (channel_id, title) VALUES (?, ?)", (channel_id, title))
        conn.commit()
    except sqlite3.Error as e:
        logger.error(f"Error saving channels: {e}")
    finally:
        conn.close()

def log_action(user_id, action, details):
    try:
        conn = sqlite3.connect('bot_data.db')
        c = conn.cursor()
        timestamp = datetime.datetime.now().isoformat()
        c.execute("INSERT INTO logs (timestamp, user_id, action, details) VALUES (?, ?, ?, ?)",
                  (timestamp, str(user_id), action, details))
        conn.commit()
    except sqlite3.Error as e:
        logger.error(f"Error logging action: {e}")
    finally:
        conn.close()

def is_admin(user_id):
    admins = load_admins()
    return str(user_id) == str(OWNER_ID) or str(user_id) in admins

async def is_bot_channel_admin(context, channel_id):
    try:
        chat_member = await context.bot.get_chat_member(channel_id, context.bot.id)
        return chat_member.status in ['administrator', 'creator']
    except telegram.error.TelegramError:
        return False

def get_main_keyboard(user_id):
    keyboard = [
        [KeyboardButton("\u2795 Add Channel"), KeyboardButton("\u2796 Remove Channel")],
        [KeyboardButton("\ud83d\udcc3 My Channels"), KeyboardButton("\ud83d\udce4 Post")]
    ]
    if str(user_id) == str(OWNER_ID):
        keyboard.append([KeyboardButton("\ud83e\uddd1\u200d\ud83d\udcbb Manage Admins")])
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)

def get_admin_management_keyboard():
    keyboard = [
        [KeyboardButton("\u2795 Add Admin"), KeyboardButton("\u2796 Remove Admin")],
        [KeyboardButton("\ud83d\udcc3 List Admins")],
        [KeyboardButton("\u2b05\ufe0f Back")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.message.reply_text("\u274c Access denied. Admins only.")
        return ConversationHandler.END
    log_action(user_id, "start", "Started bot")
    await update.message.reply_text("Welcome! Use the menu below:", reply_markup=get_main_keyboard(user_id))
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    log_action(user_id, "cancel", "Cancelled operation")
    await update.message.reply_text("Operation cancelled.", reply_markup=get_main_keyboard(user_id))
    return ConversationHandler.END

async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()

    if not is_admin(user_id):
        await update.message.reply_text("\u274c Access denied.")
        return ConversationHandler.END

    if text == "\ud83e\uddd1\u200d\ud83d\udcbb Manage Admins" and str(user_id) == str(OWNER_ID):
        await update.message.reply_text("Choose an action:", reply_markup=get_admin_management_keyboard())
        return ConversationHandler.END

    elif text == "\u2b05\ufe0f Back" and str(user_id) == str(OWNER_ID):
        await update.message.reply_text("Main menu:", reply_markup=get_main_keyboard(user_id))
        return ConversationHandler.END

    elif text == "\u2795 Add Admin" and str(user_id) == str(OWNER_ID):
        await update.message.reply_text("Send the user ID or @username to add as admin (or /cancel to abort):")
        return ADD_ADMIN

    elif text == "\u2796 Remove Admin" and str(user_id) == str(OWNER_ID):
        await update.message.reply_text("Send the user ID or @username to remove from admins (or /cancel to abort):")
        return REMOVE_ADMIN

    elif text == "\ud83d\udcc3 List Admins" and str(user_id) == str(OWNER_ID):
        admins = load_admins()
        msg = "\ud83d\udc6e Admins List:\n"
        msg += f"\ud83d\udc51 Owner: `{OWNER_ID}`\n"
        if admins:
            msg += "\ud83d\udee1\ufe0f Other Admins:\n" + "\n".join(f"- `{uid}`" for uid in admins)
        else:
            msg += "No other admins."
        await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=get_admin_management_keyboard())
        return ConversationHandler.END

    elif text == "\u2795 Add Channel":
        await update.message.reply_text("Send the channel ID or @username (e.g., @ChannelName or -100123456789) (or /cancel to abort):")
        return ADD_CHANNEL

    elif text == "\u2796 Remove Channel":
        await update.message.reply_text("Send the channel ID or @username to remove (or /cancel to abort):")
        return REMOVE_CHANNEL

    elif text == "\ud83d\udcc3 My Channels":
        channels = load_channels()
        if not channels:
            await update.message.reply_text("No channels added yet.")
        else:
            msg = "\ud83d\udcc3 Channels:\n" + "\n".join(f"{k} ({v})" for k, v in channels.items())
            await update.message.reply_text(msg)
        return ConversationHandler.END

    elif text == "\ud83d\udce4 Post":
        current_time = time.time()
        if user_id in LAST_POST_TIME and current_time - LAST_POST_TIME[user_id] < POST_RATE:
            await update.message.reply_text(f"\u274c Please wait {int(POST_RATE - (current_time - LAST_POST_TIME[user_id]))} seconds before posting again.")
            return ConversationHandler.END
        await update.message.reply_text("Send the message to post to all channels (or /cancel to abort):")
        return POST_MESSAGE

    else:
        await update.message.reply_text("Unknown command. Please use the menu.", reply_markup=get_main_keyboard(user_id))
        return ConversationHandler.END

async def add_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    input_text = update.message.text.strip()

    if input_text.startswith('@'):
        try:
            chat = await context.bot.get_chat(input_text)
            new_id = str(chat.id)
        except telegram.error.TelegramError as e:
            await update.message.reply_text(f"\u274c Error: {e.message}")
            return ConversationHandler.END
    elif input_text.isdigit():
        new_id = input_text
    else:
        await update.message.reply_text("\u274c Invalid user ID or username.")
        return ConversationHandler.END

    if new_id == str(OWNER_ID):
        await update.message.reply_text("\u26a0\ufe0f Already the owner.")
        return ConversationHandler.END

    context.user_data['action'] = 'add_admin'
    context.user_data['new_id'] = new_id
    context.user_data['input_text'] = input_text
    await update.message.reply_text(f"Confirm adding {input_text} as admin? (Yes/No)")
    return CONFIRM_ACTION

async def remove_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    input_text = update.message.text.strip()

    if input_text.startswith('@'):
        try:
            chat = await context.bot.get_chat(input_text)
            remove_id = str(chat.id)
        except telegram.error.TelegramError as e:
            await update.message.reply_text(f"\u274c Error: {e.message}")
            return ConversationHandler.END
    elif input_text.isdigit():
        remove_id = input_text
    else:
        await update.message.reply_text("\u274c Invalid user ID or username.")
        return ConversationHandler.END

    context.user_data['action'] = 'remove_admin'
    context.user_data['remove_id'] = remove_id
    context.user_data['input_text'] = input_text
    await update.message.reply_text(f"Confirm removing {input_text} from admins? (Yes/No)")
    return CONFIRM_ACTION

async def confirm_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    response = update.message.text.strip().lower()
    action = context.user_data.get('action')
    input_text = context.user_data.get('input_text')

    if response != 'yes':
        await update.message.reply_text("Action cancelled.", reply_markup=get_main_keyboard(user_id))
        return ConversationHandler.END

    if action == 'add_admin':
        new_id = context.user_data.get('new_id')
        admins = load_admins()
        if new_id in admins:
            await update.message.reply_text("Already an admin.")
        else:
            admins[new_id] = True
            save_admins(admins)
            log_action(user_id, "add_admin", f"Added admin {input_text}")
            await update.message.reply_text(f"\u2705 Admin {input_text} added.")

    elif action == 'remove_admin':
        remove_id = context.user_data.get('remove_id')
        admins = load_admins()
        if remove_id in admins:
            del admins[remove_id]
            save_admins(admins)
            log_action(user_id, "remove_admin", f"Removed admin {input_text}")
            await update.message.reply_text(f"\u2705 Admin {input_text} removed.")
        else:
            await update.message.reply_text("User ID not found in admin list.")

    elif action == 'add_channel':
        channel_id = context.user_data.get('channel_id')
        title = context.user_data.get('title')
        channels = load_channels()
        if channel_id in channels:
            await update.message.reply_text("Channel already added.")
        else:
            channels[channel_id] = title
            save_channels(channels)
            log_action(user_id, "add_channel", f"Added channel {input_text}")
            await update.message.reply_text(f"\u2705 Channel {input_text} added.")

    elif action == 'remove_channel':
        channel_id = context.user_data.get('channel_id')
        channels = load_channels()
        if channel_id in channels:
            del channels[channel_id]
            save_channels(channels)
            log_action(user_id, "remove_channel", f"Removed channel {input_text}")
            await update.message.reply_text(f"\u2705 Channel {input_text} removed.")
        else:
            await update.message.reply_text("Channel not found in the list.")

    await update.message.reply_text("Main menu:", reply_markup=get_main_keyboard(user_id))
    return ConversationHandler.END

async def add_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    channel = update.message.text.strip()

    if not (channel.startswith('@') or (channel.startswith('-') and channel[1:].isdigit())):
        await update.message.reply_text("\u274c Invalid channel ID or username.")
        return ConversationHandler.END

    if not await is_bot_channel_admin(context, channel):
        await update.message.reply_text("\u274c Bot must be an admin in the channel.")
        return ConversationHandler.END

    try:
        chat = await context.bot.get_chat(channel)
        channel_id = str(chat.id)
        title = chat.title or channel_id
        context.user_data['action'] = 'add_channel'
        context.user_data['channel_id'] = channel_id
        context.user_data['title'] = title
        context.user_data['input_text'] = channel
        await update.message.reply_text(f"Confirm adding channel {channel} ({title})? (Yes/No)")
        return CONFIRM_ACTION
    except telegram.error.TelegramError as e:
        await update.message.reply_text(f"\u274c Error: {e.message}")
        return ConversationHandler.END

async def remove_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    channel = update.message.text.strip()

    if not (channel.startswith('@') or (channel.startswith('-') and channel[1:].isdigit())):
        await update.message.reply_text("\u274c Invalid channel ID or username.")
        return ConversationHandler.END

    try:
        chat = await context.bot.get_chat(channel)
        channel_id = str(chat.id)
        context.user_data['action'] = 'remove_channel'
        context.user_data['channel_id'] = channel_id
        context.user_data['input_text'] = channel
        await update.message.reply_text(f"Confirm removing channel {channel}? (Yes/No)")
        return CONFIRM_ACTION
    except telegram.error.TelegramError as e:
        await update.message.reply_text(f"\u274c Error: {e.message}")
        return ConversationHandler.END

async def post_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    message = update.message.text
    LAST_POST_TIME[user_id] = time.time()

    channels = load_channels()
    if not channels:
        await update.message.reply_text("No channels to post to.")
        await update.message.reply_text("Main menu:", reply_markup=get_main_keyboard(user_id))
        return ConversationHandler.END

    success = 0
    failed = []
    for channel_id in channels:
        if not await is_bot_channel_admin(context, channel_id):
            failed.append(f"{channel_id}: Bot is not an admin")
            continue
        try:
            await context.bot.send_message(chat_id=channel_id, text=message)
            success += 1
        except telegram.error.TelegramError as e:
            failed.append(f"{channel_id}: {e.message}")

    msg = f"\u2705 Posted to {success} channel(s)."
    if failed:
        msg += f"\n\u274c Failed for: {', '.join(failed)}"
    log_action(user_id, "post_message", f"Posted to {success} channels, failed: {len(failed)}")
    await update.message.reply_text(msg)
    await update.message.reply_text("Main menu:", reply_markup=get_main_keyboard(user_id))
    return ConversationHandler.END

def main():
    lock_fd = acquire_lock()
    if not lock_fd:
        logger.error("Cannot start bot: another instance is running.")
        return

    try:
        initialize_db()
        if not BOT_TOKEN or not OWNER_ID:
            logger.error("BOT_TOKEN or OWNER_ID not set")
            return

        app = Application.builder().token(BOT_TOKEN).build()

        conv_handler = ConversationHandler(
            entry_points=[
                CommandHandler("start", start),
                MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler),
            ],
            states={
                ADD_ADMIN: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_admin)],
                REMOVE_ADMIN: [MessageHandler(filters.TEXT & ~filters.COMMAND, remove_admin)],
                ADD_CHANNEL: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_channel)],
                REMOVE_CHANNEL: [MessageHandler(filters.TEXT & ~filters.COMMAND, remove_channel)],
                POST_MESSAGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, post_message)],
                CONFIRM_ACTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, confirm_action)],
            },
            fallbacks=[CommandHandler("cancel", cancel)],
            allow_reentry=True
        )

        app.add_handler(conv_handler)

        logger.info("Bot is starting...")
        max_retries = 5
        retry_delay = 5
        for attempt in range(max_retries):
            try:
                app.run_polling()
                break
            except telegram.error.Conflict as e:
                logger.error(f"Conflict error: {e}. Retrying in {retry_delay} seconds... (Attempt {attempt + 1}/{max_retries})")
                time.sleep(retry_delay)
            except Exception as e:
                logger.error(f"Bot crashed: {e}")
                break
        else:
            logger.error("Max retries reached. Could not resolve conflict. Please ensure only one bot instance is running.")
    finally:
        release_lock(lock_fd)

if __name__ == "__main__":
    main()
