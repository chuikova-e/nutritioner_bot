import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardRemove, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters, CallbackQueryHandler, ConversationHandler
from config import TELEGRAM_TOKEN, LOG_LEVEL
from constants import (
    AWAITING_FEEDBACK, AWAITING_CONTEXT, AWAITING_GOALS, AWAITING_WEIGHT, AWAITING_TARGET_WEIGHT,
    TELEGRAM_FORMATTING, DEFAULT_TIMEZONE
)
from auth import check_user_access
from PIL import Image
import io
import tempfile
import os
from datetime import datetime, timedelta
import asyncio
import pytz
from database import (
    save_gpt_response, save_nutrition_goals, get_nutrition_goals,
    get_daily_calories, get_all_active_users, get_daily_food_records,
    save_weight_goal, get_weight_goal, save_weight_measurement, get_weight_history,
    get_weekly_food_records
)
import re
import platform
from openai_utils import (
    analyze_image_with_gpt, transcribe_audio, analyze_nutrition_vs_goals, 
    analyze_weight_progress, encode_image
)

# Start by configuring logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=getattr(logging, LOG_LEVEL.upper())
)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler for /start command"""
    user_id = update.effective_user.id
    username = update.effective_user.username
    
    if not check_user_access(user_id, username):
        await update.message.reply_text("Извините, у вас нет доступа к этому боту.")
        return ConversationHandler.END
        
    logging.info(f"User {user_id} (@{username}) started the bot")
    await update.message.reply_text(
        "Привет! Я бот для подсчета калорий и анализа питания.\n\n"
        "📸 Как начать:\n"
        "1. Установите цели питания через /setgoals\n"
        "2. Отправьте фото блюда для анализа\n"
        "3. При желании добавьте описание или голосовое сообщение\n\n"
        "Используйте /help для подробной информации о всех функциях.",
        parse_mode="HTML"
    )
    return ConversationHandler.END

async def process_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler for receiving messages with photos, text or voice"""
    user_id = update.effective_user.id
    username = update.effective_user.username
    
    if not check_user_access(user_id, username):
        await update.message.reply_text("Извините, у вас нет доступа к этому боту.")
        return ConversationHandler.END
        
    logging.info(f"Received message from user {user_id} (@{username})")
    
    # Initialize user data if not exists
    if 'photos_base64' not in context.user_data:
        context.user_data['photos_base64'] = []
        context.user_data['additional_info'] = []
        context.user_data['has_voice'] = False
    
    # Check if we have photos in media group
    media_group_id = update.message.media_group_id
    
    # If this is part of a media group and we haven't processed it yet
    if media_group_id:
        if context.user_data.get('current_media_group') != media_group_id:
            context.user_data['current_media_group'] = media_group_id
            context.user_data['photos_base64'] = []
            context.user_data['additional_info'] = []
            context.user_data['has_voice'] = False
        
        # If we have a photo, add it to the list
        if update.message.photo:
            try:
                photo = await update.message.photo[-1].get_file()
                with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as temp_file:
                    await photo.download_to_drive(temp_file.name)
                    photo_base64 = encode_image(temp_file.name)
                    context.user_data['photos_base64'].append(photo_base64)
                    os.unlink(temp_file.name)
                
                # If we have collected 5 photos or this is the last photo, process them
                if len(context.user_data['photos_base64']) >= 5:
                    return await process_photos_group(update, context)
                
            except Exception as e:
                logging.error(f"Error processing photo in media group: {str(e)}")
        return
    
    # Process single message
    try:
        # Process voice message if present
        if update.message.voice:
            await update.message.reply_text("🎤 Распознаю голосовое сообщение...")
            voice = await update.message.voice.get_file()
            
            with tempfile.NamedTemporaryFile(delete=False, suffix='.ogg') as temp_file:
                await voice.download_to_drive(temp_file.name)
                transcribed_text = await transcribe_audio(temp_file.name)
                os.unlink(temp_file.name)
                
                if transcribed_text:
                    await update.message.reply_text(
                        f"📝 Распознанный текст:\n{transcribed_text}",
                        parse_mode="HTML"
                    )
                    context.user_data['additional_info'].append(transcribed_text)
                    context.user_data['has_voice'] = True
                else:
                    await update.message.reply_text(
                        "Извините, не удалось распознать голосовое сообщение.\n"
                        "Пожалуйста, попробуйте еще раз или отправьте текстовое сообщение."
                    )
                    return ConversationHandler.END
        # Process text message
        elif update.message.text or update.message.caption:
            text = update.message.text or update.message.caption
            context.user_data['additional_info'].append(text)
            await update.message.reply_text("✅ Текст добавлен")
        # Process photo
        elif update.message.photo:
            await update.message.reply_text("📸 Обрабатываю фото...")
            photo = await update.message.photo[-1].get_file()
            with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as temp_file:
                await photo.download_to_drive(temp_file.name)
                photo_base64 = encode_image(temp_file.name)
                context.user_data['photos_base64'].append(photo_base64)
                os.unlink(temp_file.name)
            await update.message.reply_text("✅ Фото добавлено")
        
        # Show current status and confirmation button
        status_message = "📋 Текущая информация:\n\n"
        if context.user_data['photos_base64']:
            status_message += f"📸 Фото: {len(context.user_data['photos_base64'])} шт.\n"
        if context.user_data['additional_info']:
            status_message += f"📝 Текст: {len(context.user_data['additional_info'])} сообщений\n"
        if context.user_data['has_voice']:
            status_message += "🎤 Голосовое сообщение: добавлено\n"
        
        status_message += "\nХотите добавить еще информацию или начать анализ?"
        
        # Create keyboard with buttons
        keyboard = [
            [
                InlineKeyboardButton("➕ Добавить еще", callback_data='add_more'),
                InlineKeyboardButton("✅ Начать анализ", callback_data='start_analysis')
            ],
            [
                InlineKeyboardButton("🚫 Отменить", callback_data='cancel')
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(status_message, reply_markup=reply_markup)
        return AWAITING_FEEDBACK
        
    except Exception as e:
        logging.error(f"Error processing message: {str(e)}")
        await update.message.reply_text(
            "Произошла ошибка при обработке сообщения.\n"
            "Пожалуйста, попробуйте еще раз."
        )
        return ConversationHandler.END

async def process_photos_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Process collected photos from media group"""
    try:
        photos_base64 = context.user_data.get('photos_base64', [])
        additional_info = context.user_data.get('additional_info', "")
    
        
        # Clear media group data
        context.user_data['current_media_group'] = None
        context.user_data['photos_base64'] = []
        context.user_data['additional_info'] = []

        # Get response from GPT
        gpt_response = await analyze_image_with_gpt(photos_base64, additional_info)
        
        # Store GPT response in context for later saving
        context.user_data['current_gpt_response'] = gpt_response

        # Create keyboard with buttons
        keyboard = [
            [
                InlineKeyboardButton("✅ Верно", callback_data='correct'),
                InlineKeyboardButton("❌ Добавить контекст", callback_data='add_context'),
            ],
            [
                InlineKeyboardButton("🚫 Отменить", callback_data='cancel')
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        # Send response with buttons
        await update.message.reply_text(
            f"{gpt_response}\n\nРезультат верный?",
            reply_markup=reply_markup,
            parse_mode="HTML"
        )
        
        return AWAITING_FEEDBACK

    except Exception as e:
        logging.error(f"Error processing photos group: {str(e)}")
        await update.message.reply_text(
            "Произошла ошибка при обработке фотографий.\n"
            "Пожалуйста, попробуйте еще раз."
        )
        return ConversationHandler.END

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler for button presses"""
    query = update.callback_query
    user_id = update.effective_user.id
    username = update.effective_user.username
    await query.answer()

    if query.data == 'correct':
        # Save the confirmed response to database
        gpt_response = context.user_data.get('current_gpt_response')
        if gpt_response:
            save_gpt_response(gpt_response, username)
            logging.info(f"Saved confirmed GPT response to database for user @{username}")
        
        await query.edit_message_reply_markup(reply_markup=None)
        await query.message.reply_text("Отлично! Рад был помочь! 😊")
        return ConversationHandler.END
    
    elif query.data == 'add_context':
        logging.info(f"User {user_id} (@{username}) requested to add more context")
        await query.edit_message_reply_markup(reply_markup=None)
        await query.message.reply_text(
            "Пожалуйста, отправьте дополнительную информацию о блюде "
            "(например: размер порции, ингредиенты, способ приготовления)"
        )
        return AWAITING_CONTEXT

    elif query.data == 'cancel':
        logging.info(f"User {user_id} (@{username}) cancelled the operation")
        # Clear all user data
        context.user_data.clear()
        await query.edit_message_reply_markup(reply_markup=None)
        await query.message.reply_text("Операция отменена. Отправьте новое фото для анализа.")
        return ConversationHandler.END
        
    elif query.data == 'add_more':
        await query.edit_message_reply_markup(reply_markup=None)
        await query.message.reply_text(
            "Отправьте дополнительную информацию (фото, текст или голосовое сообщение)"
        )
        return ConversationHandler.END
        
    elif query.data == 'start_analysis':
        await query.edit_message_reply_markup(reply_markup=None)
        await query.message.reply_text("🔄 Начинаю анализ...")
        
        # Combine all additional info
        combined_info = "\n".join(context.user_data['additional_info']) if context.user_data['additional_info'] else ""
        
        # Get response from GPT
        gpt_response = await analyze_image_with_gpt(
            context.user_data['photos_base64'],
            combined_info
        )
        
        # Store GPT response in context for later saving
        context.user_data['current_gpt_response'] = gpt_response
        
        # Create keyboard with buttons
        keyboard = [
            [
                InlineKeyboardButton("✅ Верно", callback_data='correct'),
                InlineKeyboardButton("❌ Добавить контекст", callback_data='add_context'),
            ],
            [
                InlineKeyboardButton("🚫 Отменить", callback_data='cancel')
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Send response with buttons
        await query.message.reply_text(
            f"{gpt_response}\n\nРезультат верный?",
            reply_markup=reply_markup
        )
        
        return AWAITING_FEEDBACK

async def process_additional_context(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler for receiving additional context"""
    user_id = update.effective_user.id
    username = update.effective_user.username
    logging.info(f"Received additional context from user {user_id} (@{username})")
    try:
        new_context = update.message.text
        combined_context = f"{context.user_data['last_additional_info']}. Additional context: {new_context}"
        
        # Get new response from GPT with additional context
        gpt_response = await analyze_image_with_gpt(context.user_data['photos_base64'], combined_context)
        
        # Store new GPT response in context for later saving
        context.user_data['current_gpt_response'] = gpt_response

        # Create keyboard with buttons
        keyboard = [
            [
                InlineKeyboardButton("✅ Верно", callback_data='correct'),
                InlineKeyboardButton("❌ Добавить контекст", callback_data='add_context'),
            ],
            [
                InlineKeyboardButton("🚫 Отменить", callback_data='cancel')
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        # Send new response with buttons
        await update.message.reply_text(
            f"{gpt_response}\n\nРезультат верный?",
            reply_markup=reply_markup
        )
        
        # Update saved context
        context.user_data['last_additional_info'] = combined_context
        
        return AWAITING_FEEDBACK

    except Exception as e:
        logging.error(f"Error processing additional context: {str(e)}")
        await update.message.reply_text(
            "Sorry, there was an error processing your request. "
            "Please try sending the photo again."
        )
        return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel current dialog"""
    await update.message.reply_text(
        "Operation cancelled. Send a new photo for analysis.",
        reply_markup=ReplyKeyboardRemove()
    )
    return ConversationHandler.END

async def goals_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler for /goals command"""
    user_id = update.effective_user.id
    username = update.effective_user.username
    
    if not check_user_access(user_id, username):
        await update.message.reply_text("Извините, у вас нет доступа к этому боту.")
        return ConversationHandler.END

    # Get current goals if they exist
    current_goals = get_nutrition_goals(username)
    
    if current_goals:
        await update.message.reply_text(
            f"Ваши текущие цели питания:\n\n{current_goals}\n\n"
            "Чтобы изменить цели, используйте команду /setgoals"
        )
    else:
        await update.message.reply_text(
            "У вас пока не установлены цели питания.\n"
            "Чтобы установить цели, используйте команду /setgoals"
        )
    return ConversationHandler.END

async def set_goals_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler for /setgoals command"""
    user_id = update.effective_user.id
    username = update.effective_user.username
    
    if not check_user_access(user_id, username):
        await update.message.reply_text("Извините, у вас нет доступа к этому боту.")
        return ConversationHandler.END
    
    # Get current goals if they exist
    current_goals = get_nutrition_goals(username)
    
    if current_goals:
        await update.message.reply_text(
            f"Ваши текущие цели питания:\n\n{current_goals}\n\n"
            "Пожалуйста, введите новые цели питания:"
        )
    else:
        await update.message.reply_text(
            "Пожалуйста, введите ваши цели питания.\n"
            "Например:\n"
            "- Дневная норма калорий: 2000 ккал\n"
            "- Белки: 120г\n"
            "- Жиры: 60г\n"
            "- Углеводы: 250г"
        )
    
    return AWAITING_GOALS

async def process_goals(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler for processing new nutrition goals"""
    user_id = update.effective_user.id
    username = update.effective_user.username
    new_goals = update.message.text
    
    if save_nutrition_goals(username, new_goals):
        await update.message.reply_text(
            "Ваши цели питания успешно сохранены!\n"
            "Вы можете просмотреть их с помощью команды /goals"
        )
    else:
        await update.message.reply_text(
            "Произошла ошибка при сохранении целей питания.\n"
            "Пожалуйста, попробуйте позже."
        )
    
    return ConversationHandler.END

async def analyze_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler for /analyze command"""
    user_id = update.effective_user.id
    username = update.effective_user.username
    
    if not check_user_access(user_id, username):
        await update.message.reply_text("Извините, у вас нет доступа к этому боту.")
        return ConversationHandler.END

    # Get today's data
    food_records = get_daily_food_records(username)
    total_calories = get_daily_calories(username)
    goals = get_nutrition_goals(username)
    
    if not food_records:
        await update.message.reply_text(
            "За сегодня еще нет записей о питании.\n"
            "Отправьте фото блюд, чтобы начать отслеживание."
        )
        return ConversationHandler.END
    
    # Prepare base message
    message = f"📊 Анализ питания за сегодня:\n\n"
    message += f"🔢 Всего употреблено: {total_calories:.0f} ккал\n"
    
    # Add calorie goal info if available
    daily_goal = None
    if goals:
        matches = re.findall(r'калори[йя]:\s*(\d+)', goals.lower())
        if matches:
            daily_goal = float(matches[0])
            diff = daily_goal - total_calories
            message += f"🎯 Ваша цель: {daily_goal:.0f} ккал\n"
            if diff > 0:
                message += f"✅ Осталось: {diff:.0f} ккал\n"
            else:
                message += f"⚠️ Превышение: {abs(diff):.0f} ккал\n"
    
    # Add detailed analysis if goals are set
    if goals:
        await update.message.reply_text("🔄 Анализирую ваше питание...")
        analysis = await analyze_nutrition_vs_goals(food_records, goals)
        if analysis:
            message += f"\n📋 Детальный анализ:\n{analysis}"
    
    await update.message.reply_text(message, parse_mode="HTML")
    return ConversationHandler.END

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler for /help command"""
    user_id = update.effective_user.id
    username = update.effective_user.username
    
    if not check_user_access(user_id, username):
        await update.message.reply_text("Извините, у вас нет доступа к этому боту.")
        return ConversationHandler.END
        
    await update.message.reply_text(
        "🤖 Подробная инструкция по использованию бота:\n\n"
        "📸 Способы ввода информации:\n"
        "1. Фото блюда - отправьте фото, и я определю калории\n"
        "2. Текстовое описание - добавьте описание к фото или отправьте отдельным сообщением\n"
        "3. Голосовое сообщение - отправьте голосовое описание блюда\n"
        "4. Группа фото - можно отправить до 5 фото одного блюда\n\n"
        "📋 Команды:\n"
        "/goals - просмотреть ваши цели питания\n"
        "/setgoals - установить цели по калориям и БЖУ\n"
        "/calories - показать калории за сегодня\n"
        "/analyze - детальный анализ питания\n"
        "/weight - внести текущий вес\n"
        "/targetweight - установить целевой вес\n"
        "/help - показать это сообщение\n\n"
        "📊 Автоматические функции:\n"
        "• Ежедневный отчет о питании в полночь\n"
        "• Еженедельный запрос веса по воскресеньям\n"
        "• Анализ прогресса и рекомендации\n\n"
        "📝 Для лучших результатов:\n"
        "• Делайте фото при хорошем освещении\n"
        "• Старайтесь захватить все блюдо целиком\n"
        "• Указывайте размер порции в описании\n"
        "• Добавляйте информацию об ингредиентах\n"
        "• Установите цели питания через /setgoals\n"
        "• Регулярно отмечайте свой вес"
    )
    return ConversationHandler.END

async def calories_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler for /calories command"""
    user_id = update.effective_user.id
    username = update.effective_user.username
    
    if not check_user_access(user_id, username):
        await update.message.reply_text("Извините, у вас нет доступа к этому боту.")
        return ConversationHandler.END

    # Get today's calories
    total_calories = get_daily_calories(username)
    
    # Get user's goals
    goals = get_nutrition_goals(username)
    daily_goal = None
    if goals:
        # Try to extract daily calorie goal
        matches = re.findall(r'калори[йя]:\s*(\d+)', goals.lower())
        if matches:
            daily_goal = float(matches[0])
    
    # Prepare message
    message = f"Сегодня вы употребили: {total_calories:.0f} ккал\n"
    if daily_goal:
        remaining = daily_goal - total_calories
        message += f"Ваша цель на день: {daily_goal:.0f} ккал\n"
        if remaining > 0:
            message += f"Осталось: {remaining:.0f} ккал"
        else:
            message += f"Превышение: {abs(remaining):.0f} ккал"
    
    await update.message.reply_text(message)
    return ConversationHandler.END

async def send_daily_summary(application: Application):
    """Send daily calorie summary to all users"""
    while True:
        try:
            # Wait until midnight
            now = datetime.now(pytz.timezone(DEFAULT_TIMEZONE))
            tomorrow = now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
            wait_seconds = (tomorrow - now).total_seconds()
            await asyncio.sleep(wait_seconds)
            
            # Get all active users
            users = get_all_active_users()
            
            for username in users:
                try:
                    # Get yesterday's date
                    yesterday = (now - timedelta(days=1)).date()
                    
                    # Get all food records and total calories
                    food_records = get_daily_food_records(username, yesterday)
                    total_calories = get_daily_calories(username, yesterday)
                    
                    # Get user's goals
                    goals = get_nutrition_goals(username)
                    daily_goal = None
                    if goals:
                        matches = re.findall(r'калори[йя]:\s*(\d+)', goals.lower())
                        if matches:
                            daily_goal = float(matches[0])
                    
                    # Prepare base message
                    message = f"📊 Итоги дня ({yesterday}):\n\n"
                    message += f"🔢 Всего употреблено: {total_calories:.0f} ккал\n"
                    if daily_goal:
                        diff = total_calories - daily_goal
                        message += f"🎯 Ваша цель: {daily_goal:.0f} ккал\n"
                        if diff > 0:
                            message += f"⚠️ Превышение: {diff:.0f} ккал\n"
                        else:
                            message += f"✅ Осталось: {abs(diff):.0f} ккал\n"
                    
                    # Add nutrition analysis if we have both goals and food records
                    if goals and food_records:
                        analysis = await analyze_nutrition_vs_goals(food_records, goals)
                        if analysis:
                            message += f"\n📋 Анализ питания:\n{analysis}"
                    
                    # Send message to user
                    await application.bot.send_message(
                        chat_id=username,
                        text=message,
                        parse_mode="HTML"
                    )
                    
                except Exception as e:
                    logging.error(f"Error sending summary to user {username}: {str(e)}")
            
        except Exception as e:
            logging.error(f"Error in daily summary task: {str(e)}")
            await asyncio.sleep(60)  # Wait a minute before retrying

async def weight_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler for /weight command"""
    user_id = update.effective_user.id
    username = update.effective_user.username
    
    if not check_user_access(user_id, username):
        await update.message.reply_text("Извините, у вас нет доступа к этому боту.")
        return ConversationHandler.END
    
    await update.message.reply_text(
        "Пожалуйста, введите ваш текущий вес в килограммах (например: 70.5)",
        reply_markup=ReplyKeyboardRemove()
    )
    return AWAITING_WEIGHT

async def process_weight(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler for processing weight input"""
    user_id = update.effective_user.id
    username = update.effective_user.username
    
    try:
        weight = float(update.message.text.replace(',', '.'))
        if weight < 30 or weight > 300:
            await update.message.reply_text(
                "Пожалуйста, введите корректный вес (от 30 до 300 кг)"
            )
            return AWAITING_WEIGHT
    except ValueError:
        await update.message.reply_text(
            "Пожалуйста, введите число (например: 70.5)"
        )
        return AWAITING_WEIGHT
    
    # Save weight measurement
    if not save_weight_measurement(username, weight):
        await update.message.reply_text(
            "Произошла ошибка при сохранении веса.\n"
            "Пожалуйста, попробуйте позже."
        )
        return ConversationHandler.END
    
    await update.message.reply_text("🔄 Анализирую ваш прогресс...")
    
    # Get weekly food records
    start_date = datetime.now(pytz.timezone(DEFAULT_TIMEZONE)).date() - timedelta(days=7)
    food_records = get_weekly_food_records(username, start_date)
    
    # Analyze progress
    if food_records:
        # Получаем необходимые данные для анализа
        history = get_weight_history(username, limit=2)
        target_weight = get_weight_goal(username)
        nutrition_goals = get_nutrition_goals(username)
        
        analysis = await analyze_weight_progress(
            username, 
            weight, 
            food_records, 
            history, 
            target_weight, 
            nutrition_goals
        )
        if analysis:
            await update.message.reply_text(
                f"📋 Анализ прогресса:\n\n{analysis}",
                parse_mode="HTML"
            )
    
    # Calculate time to target if exists
    target_weight = get_weight_goal(username)
    history = get_weight_history(username, limit=2)
    
    if target_weight and len(history) >= 2:
        weight_diff = history[0][1] - history[1][1]  # Weekly weight change
        if abs(weight_diff) > 0.1:
            weeks_remaining = abs((weight - target_weight) / weight_diff)
            if weeks_remaining > 0:
                await update.message.reply_text(
                    f"При текущей скорости прогресса, цель будет достигнута примерно через "
                    f"{int(weeks_remaining)} недель"
                )
    
    return ConversationHandler.END

async def target_weight_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler for /targetweight command"""
    user_id = update.effective_user.id
    username = update.effective_user.username
    
    if not check_user_access(user_id, username):
        await update.message.reply_text("Извините, у вас нет доступа к этому боту.")
        return ConversationHandler.END
    
    current_target = get_weight_goal(username)
    if current_target:
        await update.message.reply_text(
            f"Ваш текущий целевой вес: {current_target} кг\n"
            "Введите новый целевой вес в килограммах (например: 65.5)"
        )
    else:
        await update.message.reply_text(
            "Пожалуйста, введите ваш целевой вес в килограммах (например: 65.5)"
        )
    
    return AWAITING_TARGET_WEIGHT

async def process_target_weight(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler for processing target weight input"""
    user_id = update.effective_user.id
    username = update.effective_user.username
    
    try:
        weight = float(update.message.text.replace(',', '.'))
        if weight < 30 or weight > 300:
            await update.message.reply_text(
                "Пожалуйста, введите корректный вес (от 30 до 300 кг)"
            )
            return AWAITING_TARGET_WEIGHT
    except ValueError:
        await update.message.reply_text(
            "Пожалуйста, введите число (например: 65.5)"
        )
        return AWAITING_TARGET_WEIGHT
    
    if save_weight_goal(username, weight):
        await update.message.reply_text(
            f"Целевой вес {weight} кг успешно сохранен!\n"
            "Теперь я буду учитывать его при анализе прогресса."
        )
    else:
        await update.message.reply_text(
            "Произошла ошибка при сохранении целевого веса.\n"
            "Пожалуйста, попробуйте позже."
        )
    
    return ConversationHandler.END

async def ask_weekly_weight(application: Application):
    """Ask users for weight measurement every Sunday morning"""
    while True:
        try:
            # Wait until next Sunday 9:00
            now = datetime.now(pytz.timezone(DEFAULT_TIMEZONE))
            days_until_sunday = (6 - now.weekday()) % 7
            if days_until_sunday == 0 and now.hour >= 9:
                days_until_sunday = 7
            next_sunday = now.replace(hour=9, minute=0, second=0, microsecond=0) + timedelta(days=days_until_sunday)
            wait_seconds = (next_sunday - now).total_seconds()
            await asyncio.sleep(wait_seconds)
            
            # Get all active users
            users = get_all_active_users()
            
            for username in users:
                try:
                    keyboard = [
                        ["Внести вес сейчас"],
                        ["Напомнить завтра"]
                    ]
                    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
                    
                    await application.bot.send_message(
                        chat_id=username,
                        text="Доброе утро! Пора записать ваш текущий вес.",
                        reply_markup=reply_markup
                    )
                except Exception as e:
                    logging.error(f"Error asking weight from user {username}: {str(e)}")
            
        except Exception as e:
            logging.error(f"Error in weekly weight task: {str(e)}")
            await asyncio.sleep(60)  # Wait a minute before retrying

async def handle_weight_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler for weight request buttons"""
    text = update.message.text
    
    if text == "Внести вес сейчас":
        await update.message.reply_text(
            "Пожалуйста, введите ваш текущий вес в килограммах (например: 70.5)",
            reply_markup=ReplyKeyboardRemove()
        )
        return AWAITING_WEIGHT
    elif text == "Напомнить завтра":
        # Schedule reminder for tomorrow at 9:00
        now = datetime.now(pytz.timezone(DEFAULT_TIMEZONE))
        tomorrow = now.replace(hour=9, minute=0, second=0, microsecond=0) + timedelta(days=1)
        delay = (tomorrow - now).total_seconds()
        
        context.job_queue.run_once(
            remind_weight,
            delay,
            data=update.effective_user.username
        )
        await update.message.reply_text(
            "Хорошо, я напомню вам завтра в 9:00.",
            reply_markup=ReplyKeyboardRemove()
        )
        return ConversationHandler.END

async def remind_weight(context: ContextTypes.DEFAULT_TYPE):
    """Callback for weight reminder"""
    username = context.job.data
    keyboard = [
        ["Внести вес сейчас"],
        ["Напомнить завтра"]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
    
    await context.bot.send_message(
        chat_id=username,
        text="Напоминаю о необходимости записать ваш текущий вес.",
        reply_markup=reply_markup
    )

def main():
    """Main bot launch function"""
    # Create application
    application = Application.builder().token(TELEGRAM_TOKEN).build()

    # Create conversation handler for messages and photos
    message_conv_handler = ConversationHandler(
        entry_points=[
            MessageHandler(filters.PHOTO | filters.TEXT | filters.VOICE & ~filters.COMMAND, process_message)
        ],
        states={
            AWAITING_FEEDBACK: [CallbackQueryHandler(button_callback)],
            AWAITING_CONTEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_additional_context)]
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )

    # Create conversation handler for goals
    goals_conv_handler = ConversationHandler(
        entry_points=[CommandHandler('setgoals', set_goals_command)],
        states={
            AWAITING_GOALS: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_goals)]
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )

    # Create conversation handler for weight
    weight_conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler('weight', weight_command),
            MessageHandler(filters.Regex('^(Внести вес сейчас|Напомнить завтра)$'), handle_weight_button)
        ],
        states={
            AWAITING_WEIGHT: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_weight)]
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )

    # Create conversation handler for target weight
    target_weight_conv_handler = ConversationHandler(
        entry_points=[CommandHandler('targetweight', target_weight_command)],
        states={
            AWAITING_TARGET_WEIGHT: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_target_weight)]
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )

    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("goals", goals_command))
    application.add_handler(CommandHandler("calories", calories_command))
    application.add_handler(CommandHandler("analyze", analyze_command))
    application.add_handler(message_conv_handler)
    application.add_handler(goals_conv_handler)
    application.add_handler(weight_conv_handler)
    application.add_handler(target_weight_conv_handler)

    # Start daily summary task
    application.job_queue.run_custom(send_daily_summary, job_kwargs={"max_instances": 1})

    # Start weekly weight task
    application.job_queue.run_custom(ask_weekly_weight, job_kwargs={"max_instances": 1})

    # Launch bot
    application.run_polling()

if __name__ == '__main__':
    main() 