import asyncio
import logging
import sys
from os import getenv
from pathlib import Path
from uuid import uuid4
from datetime import datetime

from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, html
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart
from aiogram.types import Message as MessageType
from aiogram.types import BusinessMessagesDeleted, FSInputFile
from sqlmodel import Session as SQLSession
from sqlmodel import select

import db
from db.models.message import Message
from db.models.file import File

load_dotenv()

TOKEN = os.getenv("BOT_TOKEN")
MEDIA_DIR = Path("media")
MEDIA_DIR.mkdir(exist_ok=True)

dp = Dispatcher()

# Приветственное сообщение
@dp.message(CommandStart())
async def command_start_handler(message: MessageType) -> None:
    welcome_text = (
        "👋 <b>Привет! Я бот-архиватор для бизнес-аккаунта</b>\n\n"
        "❓ <b>Что я умею:</b>\n"
        "• Сохраняю все сообщения, фото, видео и файлы\n"
        "• Уведомляю об удалении сообщений с красивым форматированием\n"
        "• Показываю изменения в отредактированных сообщениях\n"
        "• Сохраняю автоудаляющиеся сообщения (если на них ответить)\n\n"
        "📌 <b>Как использовать:</b>\n"
        "• Просто подключи меня к бизнес-аккаунту\n"
        "• Я автоматически начну архивировать все сообщения\n"
        "• Чтобы сохранить автоудаляющееся сообщение - ответь на него\n"
        "• Все удаления и изменения будут отправлены тебе в личку\n\n"
    )
    await message.answer(welcome_text, parse_mode=ParseMode.HTML)


@dp.edited_business_message()
async def handle_edited_business_message(message: MessageType) -> None:
    """Обработка измененных сообщений"""
    session = SQLSession(db.engine)
    
    try:
        business_connection = await message.bot.get_business_connection(message.business_connection_id)
        user_chat_id = business_connection.user_chat_id
        
        # Находим старое сообщение в БД
        old_msg = session.exec(
            select(Message).where(Message.chat_id == message.chat.id)
            .where(Message.id == message.message_id)
        ).first()
        
        if old_msg and old_msg.content != message.text:
            username = message.from_user.username if message.from_user.username else "без юзернейма"
            old_text = old_msg.content
            new_text = message.text
            
            # Формируем красивое сообщение об изменении
            edit_text = (
                f"🔏 <b>{username}</b> изменил сообщение.\n\n"
                f"<b>Старый текст:</b>\n"
                f"<blockquote>{html.quote(old_text)}</blockquote>\n\n"
                f"<b>Новый текст:</b>\n"
                f"<blockquote>{html.quote(new_text)}</blockquote>\n\n"
                f"<b>Изменилось:</b>\n"
                f"<blockquote><s>{html.quote(old_text)}</s> → {html.quote(new_text)}</blockquote>"
            )
            
            await message.bot.send_message(
                chat_id=user_chat_id,
                text=edit_text,
                parse_mode=ParseMode.HTML
            )
            
            # Обновляем в БД
            old_msg.content = new_text
            session.commit()
            
    except Exception as e:
        logging.error(f"Error in edited handler: {e}")
    finally:
        session.close()


@dp.deleted_business_messages()
async def handle_business_message_deleted(deleted_messages: BusinessMessagesDeleted):
    """Обработка удаленных сообщений"""
    session = SQLSession(db.engine)
    
    try:
        business_connection = await deleted_messages.bot.get_business_connection(
            deleted_messages.business_connection_id
        )
        user_chat_id = business_connection.user_chat_id
        
        for message_id in deleted_messages.message_ids:
            msg = session.exec(
                select(Message).where(Message.chat_id == deleted_messages.chat.id)
                .where(Message.id == message_id)
            ).first()
            
            if not msg:
                continue
            
            username = msg.from_username if msg.from_username != "Нету" else "пользователь"
            
            # Форматируем сообщение в зависимости от типа
            if msg.type == "text":
                text = (
                    f"🗑 <b>Это сообщение было удалено</b>\n\n"
                    f"<blockquote>{html.quote(msg.content)}</blockquote>"
                )
                await deleted_messages.bot.send_message(
                    chat_id=user_chat_id,
                    text=text,
                    parse_mode=ParseMode.HTML
                )
                
            elif msg.type in ["video", "video_note"]:
                # Получаем файл
                fileDb = session.exec(
                    select(File).where(File.message_id == msg.id)
                ).first()
                
                if fileDb:
                    file_path = MEDIA_DIR / fileDb.file_name
                    if file_path.exists():
                        file = FSInputFile(file_path)
                        
                        # Отправляем медиа
                        if msg.type == "video":
                            await deleted_messages.bot.send_video(
                                chat_id=user_chat_id,
                                video=file,
                                caption=f"🗑 <b>Это видео было удалено</b>\n\nОт: @{username}",
                                parse_mode=ParseMode.HTML
                            )
                        else:  # video_note
                            await deleted_messages.bot.send_video_note(
                                chat_id=user_chat_id,
                                video_note=file
                            )
                            await deleted_messages.bot.send_message(
                                chat_id=user_chat_id,
                                text=f"🗑 <b>Это видео-кружок был удален</b>\n\nОт: @{username}",
                                parse_mode=ParseMode.HTML
                            )
                            
            elif msg.type in ["photos", "photo"]:
                files = session.exec(
                    select(File).where(File.message_id == msg.id)
                ).all()
                
                if files:
                    # Отправляем первую фотку с описанием
                    first_file = files[0]
                    file_path = MEDIA_DIR / first_file.file_name
                    
                    if file_path.exists():
                        file = FSInputFile(file_path)
                        caption = (
                            f"🗑 <b>Это фото было удалено</b>\n\n"
                            f"От: @{username}\n\n"
                            f"{html.quote(msg.content) if msg.content else ''}"
                        )
                        
                        await deleted_messages.bot.send_photo(
                            chat_id=user_chat_id,
                            photo=file,
                            caption=caption,
                            parse_mode=ParseMode.HTML
                        )
                        
            elif msg.type in ["audio", "voice"]:
                fileDb = session.exec(
                    select(File).where(File.message_id == msg.id)
                ).first()
                
                if fileDb:
                    file_path = MEDIA_DIR / fileDb.file_name
                    if file_path.exists():
                        file = FSInputFile(file_path)
                        await deleted_messages.bot.send_audio(
                            chat_id=user_chat_id,
                            audio=file,
                            caption=f"🗑 <b>Это голосовое сообщение было удалено</b>\n\nОт: @{username}",
                            parse_mode=ParseMode.HTML
                        )
                        
            elif msg.type == "document":
                fileDb = session.exec(
                    select(File).where(File.message_id == msg.id)
                ).first()
                
                if fileDb:
                    file_path = MEDIA_DIR / fileDb.file_name
                    if file_path.exists():
                        file = FSInputFile(file_path)
                        await deleted_messages.bot.send_document(
                            chat_id=user_chat_id,
                            document=file,
                            caption=f"🗑 <b>Этот файл был удален</b>\n\nОт: @{username}\n\n{html.quote(msg.content) if msg.content else ''}",
                            parse_mode=ParseMode.HTML
                        )
                        
    except Exception as e:
        logging.error(f"Error in deleted handler: {e}")
    finally:
        session.close()


@dp.business_message()
async def handle_business_message(message: MessageType):
    """Сохранение всех сообщений"""
    session = SQLSession(db.engine)
    
    try:
        # Проверяем, не ответ ли это на автоудаляющееся сообщение
        if message.reply_to_message:
            reply_to = message.reply_to_message
            
            # Сохраняем автоудаляющееся сообщение, если на него ответили
            await save_auto_delete_message(message, reply_to)
        
        # Сохраняем текущее сообщение
        username = message.from_user.username if message.from_user.username else "Нету"
        
        if message.photo:
            msg = Message(
                chat_id=message.chat.id,
                id=message.message_id,
                type="photos",
                content=message.caption if message.caption else "",
                from_username=username
            )
            session.add(msg)
            session.commit()
            
            # Сохраняем ТОЛЬКО самое большое фото (лучшее качество)
            largest_photo = message.photo[-1]
            file_name = f"{uuid4()}.jpg"
            fl = await message.bot.get_file(largest_photo.file_id)
            await message.bot.download_file(fl.file_path, MEDIA_DIR / file_name)
            
            file = File(file_name=file_name, message_id=message.message_id)
            session.add(file)
            session.commit()
            
        elif message.video:
            msg = Message(
                chat_id=message.chat.id,
                id=message.message_id,
                type="video",
                content=message.caption if message.caption else "",
                from_username=username
            )
            session.add(msg)
            
            file_name = f"{uuid4()}.mp4"
            fl = await message.bot.get_file(message.video.file_id)
            await message.bot.download_file(fl.file_path, MEDIA_DIR / file_name)
            
            file = File(file_name=file_name, message_id=message.message_id)
            session.add(file)
            session.commit()
            
        elif message.video_note:
            msg = Message(
                chat_id=message.chat.id,
                id=message.message_id,
                type="video_note",
                content="",
                from_username=username
            )
            session.add(msg)
            
            file_name = f"{uuid4()}.mp4"
            fl = await message.bot.get_file(message.video_note.file_id)
            await message.bot.download_file(fl.file_path, MEDIA_DIR / file_name)
            
            file = File(file_name=file_name, message_id=message.message_id)
            session.add(file)
            session.commit()
            
        elif message.voice:
            msg = Message(
                chat_id=message.chat.id,
                id=message.message_id,
                type="audio",
                content=message.caption if message.caption else "",
                from_username=username
            )
            session.add(msg)
            
            file_name = f"{uuid4()}.ogg"
            fl = await message.bot.get_file(message.voice.file_id)
            await message.bot.download_file(fl.file_path, MEDIA_DIR / file_name)
            
            file = File(file_name=file_name, message_id=message.message_id)
            session.add(file)
            session.commit()
            
        elif message.document:
            msg = Message(
                chat_id=message.chat.id,
                id=message.message_id,
                type="document",
                content=message.caption if message.caption else "",
                from_username=username
            )
            session.add(msg)
            
            # Получаем расширение файла
            ext = message.document.mime_type.split('/')[1] if '/' in message.document.mime_type else 'bin'
            file_name = f"{uuid4()}.{ext}"
            fl = await message.bot.get_file(message.document.file_id)
            await message.bot.download_file(fl.file_path, MEDIA_DIR / file_name)
            
            file = File(file_name=file_name, message_id=message.message_id)
            session.add(file)
            session.commit()
            
        elif message.text:
            msg = Message(
                chat_id=message.chat.id,
                id=message.message_id,
                type="text",
                content=message.text,
                from_username=username
            )
            session.add(msg)
            session.commit()
            
    except Exception as e:
        logging.error(f"Error in business message handler: {e}")
    finally:
        session.close()


async def save_auto_delete_message(reply_message: MessageType, original_message: MessageType):
    """Сохраняет автоудаляющееся сообщение, на которое ответили"""
    session = SQLSession(db.engine)
    
    try:
        business_connection = await reply_message.bot.get_business_connection(
            reply_message.business_connection_id
        )
        user_chat_id = business_connection.user_chat_id
        
        username = original_message.from_user.username if original_message.from_user.username else "пользователь"
        
        # Проверяем, есть ли уже это сообщение в БД
        existing = session.exec(
            select(Message).where(Message.chat_id == original_message.chat.id)
            .where(Message.id == original_message.message_id)
        ).first()
        
        if existing:
            await reply_message.bot.send_message(
                chat_id=user_chat_id,
                text=f"⚠️ Это сообщение уже сохранено в архиве!",
                parse_mode=ParseMode.HTML
            )
            return
        
        # Сохраняем автоудаляющееся сообщение
        if original_message.video_note:
            msg = Message(
                chat_id=original_message.chat.id,
                id=original_message.message_id,
                type="video_note",
                content="",
                from_username=username
            )
            session.add(msg)
            
            file_name = f"{uuid4()}.mp4"
            fl = await reply_message.bot.get_file(original_message.video_note.file_id)
            await reply_message.bot.download_file(fl.file_path, MEDIA_DIR / file_name)
            
            file = File(file_name=file_name, message_id=original_message.message_id)
            session.add(file)
            session.commit()
            
            await reply_message.bot.send_message(
                chat_id=user_chat_id,
                text=f"✅ Сохранено автоудаляющееся видео-сообщение от @{username}",
                parse_mode=ParseMode.HTML
            )
            
        elif original_message.video:
            msg = Message(
                chat_id=original_message.chat.id,
                id=original_message.message_id,
                type="video",
                content=original_message.caption if original_message.caption else "",
                from_username=username
            )
            session.add(msg)
            
            file_name = f"{uuid4()}.mp4"
            fl = await reply_message.bot.get_file(original_message.video.file_id)
            await reply_message.bot.download_file(fl.file_path, MEDIA_DIR / file_name)
            
            file = File(file_name=file_name, message_id=original_message.message_id)
            session.add(file)
            session.commit()
            
            await reply_message.bot.send_message(
                chat_id=user_chat_id,
                text=f"✅ Сохранено автоудаляющееся видео от @{username}",
                parse_mode=ParseMode.HTML
            )
            
    except Exception as e:
        logging.error(f"Error saving auto-delete message: {e}")
    finally:
        session.close()


async def main() -> None:
    bot = Bot(
        token=TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    
    logging.info("Бот запущен!")
    await dp.start_polling(bot)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    db.init()
    asyncio.run(main())