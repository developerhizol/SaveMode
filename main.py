import asyncio
import logging
import sys
import os
import random
from pathlib import Path
from uuid import uuid4
from datetime import datetime, timedelta
import aiohttp
import re

from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, html
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart, Command
from aiogram.types import Message as MessageType
from aiogram.types import BusinessMessagesDeleted, FSInputFile, BusinessConnection
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.types import CopyTextButton, LinkPreviewOptions
from sqlmodel import Session as SQLSession
from sqlmodel import select, func

import db
from db.models.message import Message
from db.models.settings import Settings
from db.models.stats import BotStats

load_dotenv()

TOKEN = os.getenv("BOT_TOKEN")
BOT_USERNAME = "SaveModeFreeRobot"
ADMIN_ID = 7752488661
MEDIA_DIR = Path("media")
MEDIA_DIR.mkdir(exist_ok=True)

IMG_DIR = Path("img")
IMG_DIR.mkdir(exist_ok=True)

TEMP_DIR = Path("/tmp/temp_media")
TEMP_DIR.mkdir(exist_ok=True)

dp = Dispatcher()

WELCOME_IMAGE_PATH = IMG_DIR / "welcome.jpg"
CLEANUP_INTERVAL_HOURS = 24


def get_user_link(user_id: int = None, username: str = None, first_name: str = None) -> str:
    if first_name:
        display_name = first_name
    elif username and username != "Нету":
        display_name = username
    else:
        display_name = "пользователь"
    
    if username and username != "Нету":
        return f'<a href="https://t.me/{username}">{display_name}</a>'
    elif user_id:
        return f'<a href="tg://user?id={user_id}">{display_name}</a>'
    else:
        return display_name


def generate_diff_html(old_text: str, new_text: str) -> str:
    if old_text == new_text:
        return html.quote(new_text)
    
    old_words = old_text.split()
    new_words = new_text.split()
    
    i = 0
    while i < len(old_words) and i < len(new_words) and old_words[i] == new_words[i]:
        i += 1
    
    j = 0
    while j < len(old_words) - i and j < len(new_words) - i and old_words[-(j+1)] == new_words[-(j+1)]:
        j += 1
    
    unchanged_start = ' '.join(old_words[:i]) if i > 0 else ''
    unchanged_end = ' '.join(old_words[len(old_words)-j:]) if j > 0 else ''
    
    old_changed = ' '.join(old_words[i:len(old_words)-j]) if i + j < len(old_words) else ''
    new_changed = ' '.join(new_words[i:len(new_words)-j]) if i + j < len(new_words) else ''
    
    result = []
    if unchanged_start:
        result.append(html.quote(unchanged_start))
    
    if old_changed:
        result.append(f'<s>{html.quote(old_changed)}</s>')
    
    if new_changed:
        result.append(f'<b>{html.quote(new_changed)}</b>')
    
    if unchanged_end:
        result.append(html.quote(unchanged_end))
    
    return ' '.join(result)


# ==================== АНИМАЦИИ И КОМАНДЫ ====================

async def animated_text_effect(message: MessageType, text: str):
    """Create animated text effect character by character."""
    loading = ['▌', " "]
    assembled_text = ""
    character_list = []
    
    for char in text:
        character_list.append(char)
        assembled_text = "".join(character_list)
        
        for frame in loading:
            animated_text = f"{assembled_text}{frame}"
            try:
                await message.edit_text(text=animated_text)
            except Exception:
                pass
            await asyncio.sleep(0.15)


async def love_animation(message: MessageType, heart_style: str = "❤️"):
    """Create love animation with hearts."""
    arr = ["❤️", "🧡", "💛", "💚", "💙", "💜", "🤎", "🖤", "💖"]
    h = "🤍"
    first = ""
    
    for i in "".join(
        [h * 9, "\n", h * 2, heart_style * 2, h, heart_style * 2, h * 2, "\n", 
         h, heart_style * 7, h, "\n", h, heart_style * 7, h, "\n", 
         h, heart_style * 7, h, "\n", h * 2, heart_style * 5, h * 2, "\n", 
         h * 3, heart_style * 3, h * 3, "\n", h * 4, heart_style, h * 4]
    ).split("\n"):
        first += i + "\n"
        await message.edit_text(first)
        await asyncio.sleep(0.3)
    
    for i in arr:
        await message.edit_text("".join(
            [h * 9, "\n", h * 2, i * 2, h, i * 2, h * 2, "\n", h, i * 7, h, "\n", 
             h, i * 7, h, "\n", h, i * 7, h, "\n", h * 2, i * 5, h * 2, "\n", 
             h * 3, i * 3, h * 3, "\n", h * 4, i, h * 4, "\n", h * 9]))
        await asyncio.sleep(0.35)
    
    for _ in range(8):
        rand = random.choices(arr, k=34)
        await message.edit_text("".join(
            [h * 9, "\n", h * 2, rand[0], rand[1], h, rand[2], rand[3], h * 2, "\n", 
             h, rand[4], rand[5], rand[6], rand[7], rand[8], rand[9], rand[10], h, "\n", 
             h, rand[11], rand[12], rand[13], rand[14], rand[15], rand[16], rand[17], h, "\n", 
             h, rand[18], rand[19], rand[20], rand[21], rand[22], rand[23], rand[24], h, "\n", 
             h * 2, rand[25], rand[26], rand[27], rand[28], rand[29], h * 2, "\n", 
             h * 3, rand[30], rand[31], rand[32], h * 3, "\n", h * 4, rand[33], h * 4, "\n", h * 9]))
        await asyncio.sleep(0.35)
    
    fourth = "".join(
        [h * 9, "\n", h * 2, heart_style * 2, h, heart_style * 2, h * 2, "\n", 
         h, heart_style * 7, h, "\n", h, heart_style * 7, h, "\n", h, heart_style * 7, h, "\n", 
         h * 2, heart_style * 5, h * 2, "\n", h * 3, heart_style * 3, h * 3, "\n", 
         h * 4, heart_style, h * 4, "\n", h * 9])
    await message.edit_text(fourth)
    
    for _ in range(47):
        fourth = fourth.replace("🤍", heart_style, 1)
        await message.edit_text(fourth)
        await asyncio.sleep(0.25)
    
    for i in range(8):
        await message.edit_text((heart_style * (8 - i) + "\n") * (8 - i))
        await asyncio.sleep(0.4)
    
    for i in ["I", "I ❤️", "I ❤️ YOU"]:
        await message.edit_text(f"<b>{i}</b>", parse_mode="HTML")
        await asyncio.sleep(0.5)


async def love2_animation(message: MessageType):
    """Create love2 animation with hearts."""
    arr = ["🥰", "😚", "☺️", "😘", "🤭", "😍", "😙", "🙃", "🤗"]
    h = "◽"
    first = ""
    
    for i in "".join(
        [h * 9, "\n", h * 2, arr[0] * 2, h, arr[0] * 2, h * 2, "\n", 
         h, arr[0] * 7, h, "\n", h, arr[0] * 7, h, "\n", 
         h, arr[0] * 7, h, "\n", h * 2, arr[0] * 5, h * 2, "\n", 
         h * 3, arr[0] * 3, h * 3, "\n", h * 4, arr[0], h * 4]
    ).split("\n"):
        first += i + "\n"
        await message.edit_text(first)
        await asyncio.sleep(0.3)
    
    for i in arr:
        await message.edit_text("".join(
            [h * 9, "\n", h * 2, i * 2, h, i * 2, h * 2, "\n", h, i * 7, h, "\n", 
             h, i * 7, h, "\n", h, i * 7, h, "\n", h * 2, i * 5, h * 2, "\n", 
             h * 3, i * 3, h * 3, "\n", h * 4, i, h * 4, "\n", h * 9]))
        await asyncio.sleep(0.35)
    
    for _ in range(8):
        rand = random.choices(arr, k=34)
        await message.edit_text("".join(
            [h * 9, "\n", h * 2, rand[0], rand[1], h, rand[2], rand[3], h * 2, "\n", 
             h, rand[4], rand[5], rand[6], rand[7], rand[8], rand[9], rand[10], h, "\n", 
             h, rand[11], rand[12], rand[13], rand[14], rand[15], rand[16], rand[17], h, "\n", 
             h, rand[18], rand[19], rand[20], rand[21], rand[22], rand[23], rand[24], h, "\n", 
             h * 2, rand[25], rand[26], rand[27], rand[28], rand[29], h * 2, "\n", 
             h * 3, rand[30], rand[31], rand[32], h * 3, "\n", h * 4, rand[33], h * 4, "\n", h * 9]))
        await asyncio.sleep(0.35)
    
    fourth = "".join(
        [h * 9, "\n", h * 2, arr[0] * 2, h, arr[0] * 2, h * 2, "\n", 
         h, arr[0] * 7, h, "\n", h, arr[0] * 7, h, "\n", h, arr[0] * 7, h, "\n", 
         h * 2, arr[0] * 5, h * 2, "\n", h * 3, arr[0] * 3, h * 3, "\n", 
         h * 4, arr[0], h * 4, "\n", h * 9])
    await message.edit_text(fourth)
    
    for _ in range(47):
        fourth = fourth.replace("◽", "🥰", 1)
        await message.edit_text(fourth)
        await asyncio.sleep(0.25)
    
    for i in range(8):
        await message.edit_text((arr[0] * (8 - i) + "\n") * (8 - i))
        await asyncio.sleep(0.4)
    
    for i in ["I", "I ❤️", "I ❤️ YOU"]:
        await message.edit_text(f"<b>{i}</b>", parse_mode="HTML")
        await asyncio.sleep(0.5)


# ==================== ХЭНДЛЕРЫ КОМАНД ====================

@dp.message(Command("p"))
async def p_command_handler(message: MessageType):
    """Handle /p command - animated text."""
    # Check if it's a business chat
    if not message.business_connection_id:
        await message.answer("Эта команда доступна только в бизнес-чате.")
        return
    
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer("❌ Введите текст для анимации.\nПример: `/p Привет мир!`", parse_mode=ParseMode.HTML)
        return
    
    text = args[1]
    await animated_text_effect(message, text)


@dp.message(Command("info"))
async def info_command_handler(message: MessageType):
    """Handle /info command - get user metadata from replied message."""
    # Check if it's a business chat
    if not message.business_connection_id:
        await message.answer("Эта команда доступна только в бизнес-чате.")
        return
    
    if not message.reply_to_message:
        await message.answer("❌ Ответьте на сообщение пользователя, чтобы получить информацию о нём.\nПример: `/info` в ответ на сообщение", parse_mode=ParseMode.HTML)
        return
    
    reply_user = message.reply_to_message.from_user
    user_id = reply_user.id
    username = f"@{reply_user.username}" if reply_user.username else "Нет"
    full_name = reply_user.full_name
    
    response = f"""
<blockquote><i>Metadata:</i> 
<b>├</b> <tg-emoji emoji-id="5260399854500191689">👤</tg-emoji> User id: <b>{user_id}</b>
<b>├</b> <tg-emoji emoji-id="5258073068852485953">✈️</tg-emoji> Username: <b>{username}</b>
<b>└</b> <tg-emoji emoji-id="5253959125838090076">👁</tg-emoji> Full Name: <b>{full_name}</b>
</blockquote>
    """
    await message.edit_text(text=response, parse_mode=ParseMode.HTML)


@dp.message(Command("love"))
async def love_command_handler(message: MessageType):
    """Handle /love command - love animation with hearts."""
    if not message.business_connection_id:
        await message.answer("Эта команда доступна только в бизнес-чате.")
        return
    
    await love_animation(message, "❤️")


@dp.message(Command("love2"))
async def love2_command_handler(message: MessageType):
    """Handle /love2 command - love animation with emojis."""
    if not message.business_connection_id:
        await message.answer("Эта команда доступна только в бизнес-чате.")
        return
    
    await love2_animation(message)


@dp.message(Command("help"))
async def help_command_handler(message: MessageType):
    """Handle /help command - show available commands."""
    help_text = """
<b><tg-emoji emoji-id="5257965174979042426">📝</tg-emoji> Команды</b>
<blockquote>  ✦ <code>/love</code> — <b>Магическая анимация любви</b>
  ✦ <code>/love2</code> — <b>Магическая анимация любви v2</b>
  ✦ <code>/info</code> — <b>Метаданные аккаунта (ответьте на сообщение)</b>
  ✦ <code>/p (текст)</code> — <b>Анимация текста</b>
  ✦ <code>/settings</code> — <b>Настройки сохранения</b>
</blockquote>

<b><tg-emoji emoji-id="5258514780469075716">📂</tg-emoji> Другое</b>
<blockquote>  Для сохранения удалённых сообщений подключите бота к бизнес-аккаунту.
  Для сохранения сгорающих сообщений — ответьте на них любым текстом.
</blockquote>
    """
    await message.edit_text(text=help_text, parse_mode=ParseMode.HTML)


# ==================== ОСТАЛЬНЫЕ ХЭНДЛЕРЫ (БЕЗ ИЗМЕНЕНИЙ) ====================

async def update_user_stats(user_id: int, username: str = None, is_connected: bool = None):
    session = SQLSession(db.engine)
    
    try:
        stats = session.exec(select(BotStats).where(BotStats.user_id == user_id)).first()
        
        if not stats:
            stats = BotStats(
                user_id=user_id, 
                username=username,
                first_seen=datetime.now(), 
                last_seen=datetime.now(), 
                is_connected=False
            )
            session.add(stats)
            session.commit()
            print(f"✅ Создана новая запись для user_id={user_id}, username={username}")
        else:
            if username and stats.username != username:
                stats.username = username
                session.commit()
                print(f"🔄 Обновлён username для user_id={user_id}: {username}")
        
        stats.last_seen = datetime.now()
        
        if is_connected is not None:
            stats.is_connected = is_connected
        
        session.commit()
        
    except Exception as e:
        print(f"Error updating stats: {e}")
    finally:
        session.close()


async def cleanup_database_and_media():
    try:
        if MEDIA_DIR.exists():
            for file_path in MEDIA_DIR.iterdir():
                if file_path.is_file():
                    try:
                        file_path.unlink()
                    except:
                        pass
        
        session = SQLSession(db.engine)
        
        messages_deleted = session.exec(select(Message)).all()
        for msg in messages_deleted:
            session.delete(msg)
        
        session.commit()
        session.close()
        
        MEDIA_DIR.mkdir(exist_ok=True)
        
    except Exception as e:
        print(f"Cleanup error: {e}")


async def cleanup_scheduler():
    while True:
        try:
            await asyncio.sleep(CLEANUP_INTERVAL_HOURS * 3600)
            await cleanup_database_and_media()
        except:
            await asyncio.sleep(3600)


def get_settings_keyboard(user_id: int) -> InlineKeyboardMarkup:
    session = SQLSession(db.engine)
    settings = session.exec(select(Settings).where(Settings.user_id == user_id)).first()
    session.close()
    
    if not settings:
        settings = Settings(user_id=user_id)
    
    deleted_messages_status = "🟢" if settings.save_deleted_messages else "🔴"
    deleted_photos_status = "🟢" if settings.save_deleted_photos else "🔴"
    deleted_videos_status = "🟢" if settings.save_deleted_videos else "🔴"
    deleted_voices_status = "🟢" if settings.save_deleted_voices else "🔴"
    deleted_video_notes_status = "🟢" if settings.save_deleted_video_notes else "🔴"
    deleted_documents_status = "🟢" if settings.save_deleted_documents else "🔴"
    edited_messages_status = "🟢" if settings.save_edited_messages else "🔴"
    auto_photos_status = "🟢" if settings.save_auto_photos else "🔴"
    auto_videos_status = "🟢" if settings.save_auto_videos else "🔴"
    auto_video_notes_status = "🟢" if settings.save_auto_video_notes else "🔴"
    auto_voices_status = "🟢" if settings.save_auto_voices else "🔴"
    auto_documents_status = "🟢" if settings.save_auto_documents else "🔴"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"{edited_messages_status} Сохранение изменённых сообщений", callback_data="toggle_edited_messages")],
        [InlineKeyboardButton(text=f"{deleted_messages_status} Сохранение удаленных сообщений", callback_data="toggle_deleted_messages")],
        [InlineKeyboardButton(text=f"{deleted_photos_status} Сохранение удаленных фото", callback_data="toggle_deleted_photos")],
        [InlineKeyboardButton(text=f"{deleted_videos_status} Сохранение удаленных видео", callback_data="toggle_deleted_videos")],
        [InlineKeyboardButton(text=f"{deleted_voices_status} Сохранение удаленных голосовых", callback_data="toggle_deleted_voices")],
        [InlineKeyboardButton(text=f"{deleted_video_notes_status} Сохранение удаленных кружков", callback_data="toggle_deleted_video_notes")],
        [InlineKeyboardButton(text=f"{deleted_documents_status} Сохранение удаленных файлов", callback_data="toggle_deleted_documents")],
        [InlineKeyboardButton(text=f"{auto_photos_status} Сохранение «сгорающих» фото", callback_data="toggle_auto_photos")],
        [InlineKeyboardButton(text=f"{auto_videos_status} Сохранение «сгорающих» видео", callback_data="toggle_auto_videos")],
        [InlineKeyboardButton(text=f"{auto_video_notes_status} Сохранение «сгорающих» кружков", callback_data="toggle_auto_video_notes")],
        [InlineKeyboardButton(text=f"{auto_voices_status} Сохранение «сгорающих» голосовых", callback_data="toggle_auto_voices")],
        [InlineKeyboardButton(text=f"{auto_documents_status} Сохранение «сгорающих» файлов", callback_data="toggle_auto_documents")],
        [InlineKeyboardButton(text="< Назад", callback_data="back_to_welcome")]
    ])
    
    return keyboard


def get_welcome_keyboard() -> InlineKeyboardMarkup:
    copy_button = InlineKeyboardButton(
        text="Скопировать @username",
        copy_text=CopyTextButton(text=f"@{BOT_USERNAME}")
    )
    
    settings_button = InlineKeyboardButton(
        text="Настройки",
        callback_data="open_settings",
        icon_custom_emoji_id="5341715473882955310"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [copy_button],
        [settings_button]
    ])
    return keyboard


def get_stats_keyboard() -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Общая статистика", callback_data="stats_total")],
        [InlineKeyboardButton(text="Статистика за сутки", callback_data="stats_daily")]
    ])
    return keyboard


@dp.message(CommandStart())
async def command_start_handler(message: MessageType) -> None:
    username = message.from_user.username if message.from_user.username else None
    await update_user_stats(message.from_user.id, username)
    
    await message.answer(f"<tg-emoji emoji-id=\"5472055112702629499\">👋</tg-emoji> <b>Добро пожаловать!</b>", parse_mode=ParseMode.HTML)
    await asyncio.sleep(0.5)
    
    welcome_text = (
        "Этот бот создан, чтобы <b>облегчить вам вести диалог в Telegram.</b>\n\n"
        "• Я присылаю уведомления, когда собеседник <b>удаляет или редактирует сообщения.</b>\n"
        "• Могу сохранять <b>сгорающие фото, голосовые, видео и файлы.</b>\n\n"
        "Чтобы сохранить сгорающее сообщение - просто ответьте на него любым текстом.\n\n"
        "Чтобы подключить бота, нажмите на кнопку <b>«Скопировать @username»</b> и следуйте инструкции выше.\n\n"
        "Доступные команды: /help"
    )
    
    if WELCOME_IMAGE_PATH.exists():
        photo = FSInputFile(WELCOME_IMAGE_PATH)
        await message.answer_photo(
            photo=photo,
            caption=welcome_text,
            reply_markup=get_welcome_keyboard(),
            parse_mode=ParseMode.HTML
        )
    else:
        await message.answer(
            text=welcome_text,
            reply_markup=get_welcome_keyboard(),
            parse_mode=ParseMode.HTML
        )


@dp.message(Command("settings"))
async def settings_command_handler(message: MessageType) -> None:
    session = SQLSession(db.engine)
    settings = session.exec(select(Settings).where(Settings.user_id == message.from_user.id)).first()
    
    if not settings:
        settings = Settings(user_id=message.from_user.id)
        session.add(settings)
        session.commit()
    
    session.close()
    
    settings_text = "🔐 <b>Параметры сохранения:</b>\n\nНастройте, какие типы контента нужно сохранять:\n\n"
    
    if WELCOME_IMAGE_PATH.exists():
        photo = FSInputFile(WELCOME_IMAGE_PATH)
        await message.answer_photo(
            photo=photo,
            caption=settings_text,
            reply_markup=get_settings_keyboard(message.from_user.id),
            parse_mode=ParseMode.HTML
        )
    else:
        await message.answer(
            text=settings_text,
            reply_markup=get_settings_keyboard(message.from_user.id),
            parse_mode=ParseMode.HTML
        )


@dp.message(Command("stats"))
async def stats_command_handler(message: MessageType) -> None:
    if message.from_user.id != ADMIN_ID:
        return
    
    stats_text = (
        "👉 В данном разделе собрана вся статистика бота.\n\n"
        "Выберите категорию для просмотра:"
    )
    
    await message.answer(
        text=stats_text,
        reply_markup=get_stats_keyboard(),
        parse_mode=ParseMode.HTML
    )


@dp.callback_query()
async def handle_callback_query(callback: CallbackQuery):
    if callback.data == "open_settings":
        session = SQLSession(db.engine)
        settings = session.exec(select(Settings).where(Settings.user_id == callback.from_user.id)).first()
        if not settings:
            settings = Settings(user_id=callback.from_user.id)
            session.add(settings)
            session.commit()
        session.close()
        
        settings_text = "🔐 <b>Параметры сохранения:</b>\n\nВыберите, какие типы контента нужно сохранять:"
        
        if callback.message.caption:
            await callback.message.edit_caption(
                caption=settings_text,
                reply_markup=get_settings_keyboard(callback.from_user.id),
                parse_mode=ParseMode.HTML
            )
        else:
            await callback.message.edit_text(
                text=settings_text,
                reply_markup=get_settings_keyboard(callback.from_user.id),
                parse_mode=ParseMode.HTML
            )
        await callback.answer()
        return
    
    elif callback.data == "back_to_welcome":
        welcome_text = (
            "Этот бот создан, чтобы <b>облегчить вам вести диалог в Telegram.</b>\n\n"
            "• Я присылаю уведомления, когда собеседник <b>удаляет или редактирует сообщения.</b>\n"
            "• Могу сохранять <b>сгорающие фото, голосовые, видео и файлы.</b>\n\n"
            "Чтобы сохранить сгорающее сообщение - просто ответьте на него любым текстом.\n\n"
            "Чтобы подключить бота, нажмите на кнопку <b>«Скопировать @username»</b> и следуйте инструкции выше.\n\n"
            "Доступные команды: /help"
        )
        
        if callback.message.caption:
            await callback.message.edit_caption(
                caption=welcome_text,
                reply_markup=get_welcome_keyboard(),
                parse_mode=ParseMode.HTML
            )
        else:
            await callback.message.edit_text(
                text=welcome_text,
                reply_markup=get_welcome_keyboard(),
                parse_mode=ParseMode.HTML
            )
        await callback.answer()
        return
    
    elif callback.data == "stats_total":
        session = SQLSession(db.engine)
        
        all_users = session.exec(select(BotStats)).all()
        total_users = len(all_users)
        connected_users = len([u for u in all_users if u.is_connected])
        
        session.close()
        
        stats_text = (
            f"👉 Общее количество пользователей бота: <b>{total_users}</b>\n"
            f"👉 Количество подключенных бизнес-аккаунтов: <b>{connected_users}</b>"
        )
        
        await callback.message.answer(
            text=stats_text,
            parse_mode=ParseMode.HTML
        )
        await callback.answer()
        return
    
    elif callback.data == "stats_daily":
        session = SQLSession(db.engine)
        
        yesterday = datetime.now() - timedelta(days=1)
        
        daily_users = session.exec(
            select(BotStats).where(BotStats.last_seen >= yesterday)
        ).all()
        
        total_daily = len(daily_users)
        connected_daily = len([u for u in daily_users if u.is_connected])
        
        session.close()
        
        stats_text = (
            f"👉 Количество новых пользователей за сутки: <b>{total_daily}</b>\n"
            f"👉 Количество новых подключенний к бизнес-аккаунту за сутки: <b>{connected_daily}</b>"
        )
        
        await callback.message.answer(
            text=stats_text,
            parse_mode=ParseMode.HTML
        )
        await callback.answer()
        return
    
    session = SQLSession(db.engine)
    settings = session.exec(select(Settings).where(Settings.user_id == callback.from_user.id)).first()
    
    if settings:
        if callback.data == "toggle_edited_messages":
            settings.save_edited_messages = not settings.save_edited_messages
        elif callback.data == "toggle_deleted_messages":
            settings.save_deleted_messages = not settings.save_deleted_messages
        elif callback.data == "toggle_deleted_photos":
            settings.save_deleted_photos = not settings.save_deleted_photos
        elif callback.data == "toggle_deleted_videos":
            settings.save_deleted_videos = not settings.save_deleted_videos
        elif callback.data == "toggle_deleted_voices":
            settings.save_deleted_voices = not settings.save_deleted_voices
        elif callback.data == "toggle_deleted_video_notes":
            settings.save_deleted_video_notes = not settings.save_deleted_video_notes
        elif callback.data == "toggle_deleted_documents":
            settings.save_deleted_documents = not settings.save_deleted_documents
        elif callback.data == "toggle_auto_photos":
            settings.save_auto_photos = not settings.save_auto_photos
        elif callback.data == "toggle_auto_videos":
            settings.save_auto_videos = not settings.save_auto_videos
        elif callback.data == "toggle_auto_video_notes":
            settings.save_auto_video_notes = not settings.save_auto_video_notes
        elif callback.data == "toggle_auto_voices":
            settings.save_auto_voices = not settings.save_auto_voices
        elif callback.data == "toggle_auto_documents":
            settings.save_auto_documents = not settings.save_auto_documents
        
        session.commit()
        await callback.message.edit_reply_markup(reply_markup=get_settings_keyboard(callback.from_user.id))
        await callback.answer("✅ Настройки сохранены!", show_alert=False)
    
    session.close()


@dp.business_connection()
async def handle_business_connection(business_connection: BusinessConnection):
    username = business_connection.user.username if business_connection.user.username else None
    await update_user_stats(business_connection.user_chat_id, username, business_connection.is_enabled)
    
    try:
        if business_connection.is_enabled:
            await business_connection.bot.send_message(
                chat_id=business_connection.user_chat_id,
                text="✅ <b>Вы успешно подключили SaveMode к бизнес аккаунту.</b>\n\n"
                     "Теперь я буду сохранять контент согласно вашим настройкам.\n\n"
                     "Чтобы сохранить сгорающее сообщение - просто ответьте на него.\n\n"
                     "Изменить настройки можно в любой момент через команду /settings\n\n"
                     "Доступные команды: /help",
                parse_mode=ParseMode.HTML,
                link_preview_options=LinkPreviewOptions(is_disabled=True)
            )
        else:
            await business_connection.bot.send_message(
                chat_id=business_connection.user_chat_id,
                text="🚫 <b>Внимание! Вы отключили SaveMode от бизнес аккаунта.</b>\n\n"
                     "С этого момента бот не сможет сохранять удаленные сообщения.\n\n"
                     "Чтобы снова начать сохранение, пожалуйста, подключите бота заново.",
                parse_mode=ParseMode.HTML,
                link_preview_options=LinkPreviewOptions(is_disabled=True)
            )
    except Exception as e:
        print(f"Error: {e}")


async def save_auto_delete_media(message: MessageType, reply_to: MessageType, user_chat_id: int, settings: Settings):
    user_link = get_user_link(
        reply_to.from_user.id,
        reply_to.from_user.username,
        reply_to.from_user.first_name
    )
    
    file_id = None
    media_type = None
    
    if reply_to.photo:
        file_id = reply_to.photo[-1].file_id
        media_type = "фото"
        if settings and not settings.save_auto_photos:
            return
    elif reply_to.video:
        file_id = reply_to.video.file_id
        media_type = "видео"
        if settings and not settings.save_auto_videos:
            return
    elif reply_to.video_note:
        file_id = reply_to.video_note.file_id
        media_type = "кружок"
        if settings and not settings.save_auto_video_notes:
            return
    elif reply_to.voice:
        file_id = reply_to.voice.file_id
        media_type = "голосовое"
        if settings and not settings.save_auto_voices:
            return
    elif reply_to.document:
        file_id = reply_to.document.file_id
        media_type = "документ"
        if settings and not settings.save_auto_documents:
            return
    elif reply_to.animation:
        file_id = reply_to.animation.file_id
        media_type = "гифка"
        if settings and not settings.save_auto_videos:
            return
    
    if not file_id:
        await message.bot.send_message(
            chat_id=user_chat_id,
            text=f"❌ Не удалось сохранить сгорающее сообщение от {user_link}",
            parse_mode=ParseMode.HTML
        )
        return
    
    try:
        file = await message.bot.get_file(file_id)
        
        ext_map = {
            "фото": ".jpg",
            "видео": ".mp4",
            "кружок": ".mp4",
            "голосовое": ".ogg",
            "документ": ".bin",
            "гифка": ".gif"
        }
        ext = ext_map.get(media_type, ".bin")
        file_name = f"{uuid4()}{ext}"
        file_path = TEMP_DIR / file_name
        
        await message.bot.download_file(file.file_path, file_path)
        
        if media_type == "фото":
            caption = f"✅ Сохранено сгорающее фото от {user_link}"
            await message.bot.send_photo(
                chat_id=user_chat_id,
                photo=FSInputFile(file_path),
                caption=caption,
                parse_mode=ParseMode.HTML
            )
        elif media_type == "видео":
            caption = f"✅ Сохранено сгорающее видео от {user_link}"
            await message.bot.send_video(
                chat_id=user_chat_id,
                video=FSInputFile(file_path),
                caption=caption,
                parse_mode=ParseMode.HTML
            )
        elif media_type == "кружок":
            await message.bot.send_video_note(
                chat_id=user_chat_id,
                video_note=FSInputFile(file_path)
            )
            await message.bot.send_message(
                chat_id=user_chat_id,
                text=f"✅ Сохранён сгорающий видео-кружок от {user_link}",
                parse_mode=ParseMode.HTML,
                link_preview_options=LinkPreviewOptions(is_disabled=True)
            )
        elif media_type == "голосовое":
            caption = f"✅ Сохранено сгорающее голосовое сообщение от {user_link}"
            await message.bot.send_audio(
                chat_id=user_chat_id,
                audio=FSInputFile(file_path),
                caption=caption,
                parse_mode=ParseMode.HTML
            )
        elif media_type in ["документ", "гифка"]:
            caption = f"✅ Сохранён сгорающий файл от {user_link}"
            await message.bot.send_document(
                chat_id=user_chat_id,
                document=FSInputFile(file_path),
                caption=caption,
                parse_mode=ParseMode.HTML
            )
        
        os.remove(file_path)
        
    except Exception as e:
        await message.bot.send_message(
            chat_id=user_chat_id,
            text=f"❌ Не удалось сохранить сгорающее сообщение от {user_link}",
            parse_mode=ParseMode.HTML
        )
    finally:
        if TEMP_DIR.exists():
            for f in TEMP_DIR.iterdir():
                try:
                    f.unlink()
                except:
                    pass


async def save_message_to_archive(message: MessageType, user_chat_id: int, session: SQLSession, settings: Settings):
    unique_id = f"{message.chat.id}_{message.message_id}"
    
    existing = session.exec(
        select(Message).where(Message.unique_id == unique_id)
    ).first()
    
    if existing:
        return
    
    username = message.from_user.username if message.from_user.username else "Нету"
    full_name = message.from_user.full_name if message.from_user.full_name else username
    
    if message.text:
        if settings and not settings.save_deleted_messages:
            return
        msg = Message(
            unique_id=unique_id,
            chat_id=message.chat.id,
            message_id=message.message_id,
            user_id=user_chat_id,
            from_username=username,
            from_full_name=full_name,
            content=message.text,
            caption=None,
            type="text"
        )
        session.add(msg)
        session.commit()
    
    elif message.photo:
        if settings and not settings.save_deleted_photos:
            return
        largest_photo = message.photo[-1]
        msg = Message(
            unique_id=unique_id,
            chat_id=message.chat.id,
            message_id=message.message_id,
            user_id=user_chat_id,
            from_username=username,
            from_full_name=full_name,
            content=largest_photo.file_id,
            caption=message.caption if message.caption else None,
            type="photos"
        )
        session.add(msg)
        session.commit()
    
    elif message.video:
        if settings and not settings.save_deleted_videos:
            return
        msg = Message(
            unique_id=unique_id,
            chat_id=message.chat.id,
            message_id=message.message_id,
            user_id=user_chat_id,
            from_username=username,
            from_full_name=full_name,
            content=message.video.file_id,
            caption=message.caption if message.caption else None,
            type="video"
        )
        session.add(msg)
        session.commit()
    
    elif message.video_note:
        if settings and not settings.save_deleted_video_notes:
            return
        msg = Message(
            unique_id=unique_id,
            chat_id=message.chat.id,
            message_id=message.message_id,
            user_id=user_chat_id,
            from_username=username,
            from_full_name=full_name,
            content=message.video_note.file_id,
            caption=None,
            type="video_note"
        )
        session.add(msg)
        session.commit()
    
    elif message.voice:
        if settings and not settings.save_deleted_voices:
            return
        msg = Message(
            unique_id=unique_id,
            chat_id=message.chat.id,
            message_id=message.message_id,
            user_id=user_chat_id,
            from_username=username,
            from_full_name=full_name,
            content=message.voice.file_id,
            caption=message.caption if message.caption else None,
            type="audio"
        )
        session.add(msg)
        session.commit()
    
    elif message.document:
        if settings and not settings.save_deleted_documents:
            return
        msg = Message(
            unique_id=unique_id,
            chat_id=message.chat.id,
            message_id=message.message_id,
            user_id=user_chat_id,
            from_username=username,
            from_full_name=full_name,
            content=message.document.file_id,
            caption=message.caption if message.caption else None,
            type="document"
        )
        session.add(msg)
        session.commit()
    
    elif message.animation:
        if settings and not settings.save_deleted_messages:
            return
        msg = Message(
            unique_id=unique_id,
            chat_id=message.chat.id,
            message_id=message.message_id,
            user_id=user_chat_id,
            from_username=username,
            from_full_name=full_name,
            content=message.animation.file_id,
            caption=message.caption if message.caption else None,
            type="animation"
        )
        session.add(msg)
        session.commit()


@dp.business_message()
async def handle_business_message(message: MessageType):
    session = SQLSession(db.engine)
    
    try:
        business_connection = await message.bot.get_business_connection(message.business_connection_id)
        user_chat_id = business_connection.user_chat_id
        
        settings = session.exec(select(Settings).where(Settings.user_id == user_chat_id)).first()
        if not settings:
            settings = Settings(user_id=user_chat_id)
            session.add(settings)
            session.commit()
        
        if message.from_user.id != user_chat_id:
            await save_message_to_archive(message, user_chat_id, session, settings)
        
        if message.reply_to_message:
            reply_to = message.reply_to_message
            
            if message.from_user.id == user_chat_id and reply_to.from_user.id != user_chat_id:
                if reply_to.has_protected_content:
                    await save_auto_delete_media(message, reply_to, user_chat_id, settings)
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        session.close()


@dp.edited_business_message()
async def handle_edited_business_message(message: MessageType) -> None:
    session = SQLSession(db.engine)
    
    try:
        business_connection = await message.bot.get_business_connection(message.business_connection_id)
        user_chat_id = business_connection.user_chat_id
        
        if message.from_user.id == user_chat_id:
            session.close()
            return
        
        unique_id = f"{message.chat.id}_{message.message_id}"
        old_msg = session.exec(
            select(Message).where(Message.unique_id == unique_id)
        ).first()
        
        if not old_msg:
            session.close()
            return
        
        old_text = old_msg.content
        new_text = message.text
        
        if old_text != new_text:
            old_msg.content = new_text
            session.commit()
            print(f"💾 Обновлён текст в БД для {unique_id}")
        
        settings = session.exec(select(Settings).where(Settings.user_id == user_chat_id)).first()
        if not settings:
            settings = Settings(user_id=user_chat_id)
            session.add(settings)
            session.commit()
        
        if not settings.save_edited_messages:
            print(f"⏭️ Сохранение изменений выключено в настройках, но БД обновлена")
            session.close()
            return
        
        if old_text != new_text:
            user_link = get_user_link(
                message.from_user.id, 
                message.from_user.username,
                message.from_user.first_name
            )
            
            diff_html = generate_diff_html(old_text, new_text)
            
            edit_text = (
                f"🔏 <b>{user_link}</b> изменил(а) сообщение:\n\n"
                f"<b>Старый текст:</b>\n"
                f"<blockquote><b>{html.quote(old_text)}</b></blockquote>\n\n"
                f"<b>Новый текст:</b>\n"
                f"<blockquote><b>{html.quote(new_text)}</b></blockquote>\n\n"
                f"<b>Изменилось:</b>\n"
                f"<blockquote>{diff_html}</blockquote>"
            )
            
            await message.bot.send_message(
                chat_id=user_chat_id,
                text=edit_text,
                parse_mode=ParseMode.HTML,
                link_preview_options=LinkPreviewOptions(is_disabled=True)
            )
            
    except Exception as e:
        print(f"Error: {e}")
    finally:
        session.close()


@dp.deleted_business_messages()
async def handle_business_message_deleted(deleted_messages: BusinessMessagesDeleted):
    session = SQLSession(db.engine)
    
    try:
        business_connection = await deleted_messages.bot.get_business_connection(
            deleted_messages.business_connection_id
        )
        user_chat_id = business_connection.user_chat_id
        
        settings = session.exec(select(Settings).where(Settings.user_id == user_chat_id)).first()
        if not settings:
            settings = Settings(user_id=user_chat_id)
            session.add(settings)
            session.commit()
        
        for message_id in deleted_messages.message_ids:
            unique_id = f"{deleted_messages.chat.id}_{message_id}"
            msg = session.exec(
                select(Message).where(Message.unique_id == unique_id)
            ).first()
            
            if not msg:
                continue
            
            user_link = get_user_link(None, msg.from_username, None)
            
            if msg.type == "text":
                if settings and not settings.save_deleted_messages:
                    continue
                text = f"🗑 <b>{user_link}</b> удалил(а) сообщение\n\n<blockquote>{html.quote(msg.content)}</blockquote>"
                await deleted_messages.bot.send_message(
                    chat_id=user_chat_id,
                    text=text,
                    parse_mode=ParseMode.HTML,
                    link_preview_options=LinkPreviewOptions(is_disabled=True)
                )
            
            elif msg.type in ["photos", "photo"]:
                if settings and not settings.save_deleted_photos:
                    continue
                caption = f"🗑 <b>{user_link}</b> удалил(а) фото"
                if msg.caption:
                    caption += f"\n\n{html.quote(msg.caption)}"
                await deleted_messages.bot.send_photo(
                    chat_id=user_chat_id,
                    photo=msg.content,
                    caption=caption,
                    parse_mode=ParseMode.HTML
                )
                
            elif msg.type == "video":
                if settings and not settings.save_deleted_videos:
                    continue
                caption = f"🗑 <b>{user_link}</b> удалил(а) видео"
                if msg.caption:
                    caption += f"\n\n{html.quote(msg.caption)}"
                await deleted_messages.bot.send_video(
                    chat_id=user_chat_id,
                    video=msg.content,
                    caption=caption,
                    parse_mode=ParseMode.HTML
                )
                
            elif msg.type == "video_note":
                if settings and not settings.save_deleted_video_notes:
                    continue
                await deleted_messages.bot.send_video_note(
                    chat_id=user_chat_id,
                    video_note=msg.content
                )
                await deleted_messages.bot.send_message(
                    chat_id=user_chat_id,
                    text=f"🗑 <b>{user_link}</b> удалил(а) видео-кружок",
                    parse_mode=ParseMode.HTML,
                    link_preview_options=LinkPreviewOptions(is_disabled=True)
                )
                
            elif msg.type in ["audio", "voice"]:
                if settings and not settings.save_deleted_voices:
                    continue
                caption = f"🗑 <b>{user_link}</b> удалил(а) голосовое сообщение"
                if msg.caption:
                    caption += f"\n\n{html.quote(msg.caption)}"
                await deleted_messages.bot.send_audio(
                    chat_id=user_chat_id,
                    audio=msg.content,
                    caption=caption,
                    parse_mode=ParseMode.HTML
                )
                
            elif msg.type == "document":
                if settings and not settings.save_deleted_documents:
                    continue
                caption = f"🗑 <b>{user_link}</b> удалил(а) файл"
                if msg.caption:
                    caption += f"\n\n{html.quote(msg.caption)}"
                await deleted_messages.bot.send_document(
                    chat_id=user_chat_id,
                    document=msg.content,
                    caption=caption,
                    parse_mode=ParseMode.HTML
                )
                
            elif msg.type == "animation":
                if settings and not settings.save_deleted_messages:
                    continue
                caption = f"🗑 <b>{user_link}</b> удалил(а) гифку"
                if msg.caption:
                    caption += f"\n\n{html.quote(msg.caption)}"
                await deleted_messages.bot.send_animation(
                    chat_id=user_chat_id,
                    animation=msg.content,
                    caption=caption,
                    parse_mode=ParseMode.HTML
                )
                        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        session.close()


async def main() -> None:
    bot = Bot(
        token=TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    
    asyncio.create_task(cleanup_scheduler())
    
    print("Бот запущен!")
    print("Доступны команды: /start, /help, /settings, /stats, /info, /love, /love2, /p")
    await dp.start_polling(bot)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    db.init()
    asyncio.run(main())