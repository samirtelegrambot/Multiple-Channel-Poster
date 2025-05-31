import json
import logging
from aiogram import Bot, Dispatcher, executor, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup

# Load config
with open("config.json", "r") as f:
    config = json.load(f)

BOT_TOKEN = config["bot_token"]
OWNER_ID = config["owner_id"]

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot, storage=MemoryStorage())

# File paths
USERS_FILE = "users.json"
CHANNEL_LIMIT = 5

# Keyboard
main_menu = ReplyKeyboardMarkup(resize_keyboard=True)
main_menu.row(
    KeyboardButton("➕ Add Channel"),
    KeyboardButton("📃 My Channels")
).row(
    KeyboardButton("🗑 Remove Channel"),
    KeyboardButton("📤 Post Message")
)

# States
class ChannelState(StatesGroup):
    waiting_for_channel = State()
    removing_channel = State()
    waiting_for_post = State()
    choosing_channels = State()

# Helper functions
def load_users():
    try:
        with open(USERS_FILE, "r") as f:
            return json.load(f)
    except:
        return {}

def save_users(data):
    with open(USERS_FILE, "w") as f:
        json.dump(data, f, indent=2)

# Start
@dp.message_handler(commands=["start"])
async def start_cmd(msg: types.Message):
    users = load_users()
    if str(msg.from_user.id) not in users:
        users[str(msg.from_user.id)] = []
        save_users(users)
    await msg.answer("Welcome! Use the keyboard below to manage your channels.", reply_markup=main_menu)

# Add Channel
@dp.message_handler(lambda m: m.text == "➕ Add Channel")
async def add_channel(msg: types.Message):
    users = load_users()
    if len(users.get(str(msg.from_user.id), [])) >= CHANNEL_LIMIT:
        return await msg.answer(f"❌ You can only add up to {CHANNEL_LIMIT} channels.")
    await msg.answer("Send your channel username (without @):", reply_markup=ReplyKeyboardRemove())
    await ChannelState.waiting_for_channel.set()

@dp.message_handler(state=ChannelState.waiting_for_channel)
async def save_channel(msg: types.Message, state: FSMContext):
    username = msg.text.strip().lstrip("@")
    users = load_users()
    user_channels = users.get(str(msg.from_user.id), [])
    if username in user_channels:
        await msg.answer("❗ Channel already added.", reply_markup=main_menu)
    else:
        user_channels.append(username)
        users[str(msg.from_user.id)] = user_channels
        save_users(users)
        await msg.answer(f"✅ Channel @{username} added!", reply_markup=main_menu)
    await state.finish()

# List Channels
@dp.message_handler(lambda m: m.text == "📃 My Channels")
async def list_channels(msg: types.Message):
    users = load_users()
    channels = users.get(str(msg.from_user.id), [])
    if not channels:
        await msg.answer("❌ You have not added any channels yet.")
    else:
        text = "\n".join([f"{i+1}. @{ch}" for i, ch in enumerate(channels)])
        await msg.answer(f"📋 Your Channels:\n{text}")

# Remove Channel
@dp.message_handler(lambda m: m.text == "🗑 Remove Channel")
async def remove_channel_prompt(msg: types.Message):
    users = load_users()
    channels = users.get(str(msg.from_user.id), [])
    if not channels:
        return await msg.answer("❌ You have no channels to remove.")
    await msg.answer("Send the channel username you want to remove:", reply_markup=ReplyKeyboardRemove())
    await ChannelState.removing_channel.set()

@dp.message_handler(state=ChannelState.removing_channel)
async def remove_channel(msg: types.Message, state: FSMContext):
    username = msg.text.strip().lstrip("@")
    users = load_users()
    user_channels = users.get(str(msg.from_user.id), [])
    if username not in user_channels:
        await msg.answer("❌ Channel not found.", reply_markup=main_menu)
    else:
        user_channels.remove(username)
        users[str(msg.from_user.id)] = user_channels
        save_users(users)
        await msg.answer(f"✅ Channel @{username} removed.", reply_markup=main_menu)
    await state.finish()

# Post Message
@dp.message_handler(lambda m: m.text == "📤 Post Message")
async def prompt_post(msg: types.Message):
    users = load_users()
    if not users.get(str(msg.from_user.id)):
        return await msg.answer("❌ You have no channels to post to.")
    await msg.answer("✍️ Send the message you want to post:", reply_markup=ReplyKeyboardRemove())
    await ChannelState.waiting_for_post.set()

@dp.message_handler(state=ChannelState.waiting_for_post, content_types=types.ContentTypes.ANY)
async def choose_channels(msg: types.Message, state: FSMContext):
    await state.update_data(post=msg)
    users = load_users()
    channels = users.get(str(msg.from_user.id), [])
    buttons = [[KeyboardButton(ch)] for ch in channels] + [[KeyboardButton("✅ All"), KeyboardButton("❌ Cancel")]]
    kb = ReplyKeyboardMarkup(resize_keyboard=True, keyboard=buttons)
    await msg.answer("📍 Choose channel to post:", reply_markup=kb)
    await ChannelState.choosing_channels.set()

@dp.message_handler(state=ChannelState.choosing_channels)
async def post_to_channel(msg: types.Message, state: FSMContext):
    users = load_users()
    channels = users.get(str(msg.from_user.id), [])
    text = msg.text.strip()
    data = await state.get_data()
    post = data['post']

    if text == "❌ Cancel":
        await msg.answer("❌ Post cancelled.", reply_markup=main_menu)
        return await state.finish()

    targets = channels if text == "✅ All" else [text]

    for ch in targets:
        try:
            await post.send_copy(f"@{ch}")
        except Exception as e:
            await msg.answer(f"⚠️ Failed to post in @{ch}: {e}")

    await msg.answer("✅ Message posted!", reply_markup=main_menu)
    await state.finish()

# Admin command to view all users and channels
@dp.message_handler(commands=['allusers'])
async def all_users(msg: types.Message):
    if msg.from_user.id != OWNER_ID:
        return
    users = load_users()
    text = "\n".join([f"{uid}: {len(chs)} channel(s)" for uid, chs in users.items()])
    await msg.answer(f"👥 All users:\n{text}")

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    executor.start_polling(dp, skip_updates=True)
