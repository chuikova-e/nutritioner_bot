import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters, CallbackQueryHandler, ConversationHandler
from openai import AsyncOpenAI
from config import TELEGRAM_TOKEN, OPENAI_API_KEY
from PIL import Image
import io
import base64

# Conversation states
AWAITING_FEEDBACK, AWAITING_CONTEXT = range(2)

# Logging setup
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# OpenAI initialization
client = AsyncOpenAI(api_key=OPENAI_API_KEY)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler for /start command"""
    await update.message.reply_text(
        "Hi! I'm a bot for counting calories in food. "
        "Send me a photo of your dish, and I'll try to determine the number of calories. "
        "You can also add a description to the photo for more accurate results."
    )
    return ConversationHandler.END

async def analyze_image_with_gpt(photo_base64: str, additional_info: str) -> str:
    """Sends request to OpenAI and returns response"""
    response = await client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": f"Analyze this food image and determine calories, protein, fat, and carbs. "
                               f"Additional information from user: {additional_info}. Use russian language to answer."
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{photo_base64}"
                        }
                    }
                ]
            }
        ],
        max_tokens=300
    )
    return response.choices[0].message.content

async def process_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler for receiving photos"""
    try:
        # Send processing start message
        await update.message.reply_text("Analyzing the photo...")

        # Get photo in best quality
        photo = await update.message.photo[-1].get_file()
        
        # Get additional text if any
        additional_info = update.message.caption or "No additional information"

        # Download photo
        photo_data = await photo.download_as_bytearray()
        
        # Convert photo for OpenAI
        image = Image.open(io.BytesIO(photo_data))
        
        # Save image to temporary buffer
        image_buffer = io.BytesIO()
        image.save(image_buffer, format='JPEG')
        image_buffer.seek(0)
        
        # Save data in context for possible reuse
        context.user_data['photo_base64'] = base64.b64encode(image_buffer.getvalue()).decode('utf-8')
        context.user_data['last_additional_info'] = additional_info

        # Get response from GPT
        gpt_response = await analyze_image_with_gpt(context.user_data['photo_base64'], additional_info)

        # Create keyboard with buttons
        keyboard = [
            [
                InlineKeyboardButton("✅ Correct", callback_data='correct'),
                InlineKeyboardButton("❌ Add Context", callback_data='add_context')
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        # Send response with buttons
        await update.message.reply_text(
            f"{gpt_response}\n\nIs this result correct?",
            reply_markup=reply_markup
        )
        
        return AWAITING_FEEDBACK

    except Exception as e:
        logging.error(f"Error processing photo: {str(e)}")
        await update.message.reply_text(
            "Sorry, there was an error processing your photo. "
            "Please try again or make sure the photo is clear enough."
        )
        return ConversationHandler.END

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler for button presses"""
    query = update.callback_query
    await query.answer()

    if query.data == 'correct':
        await query.edit_message_reply_markup(reply_markup=None)
        await query.message.reply_text("Great! Glad I could help! 😊")
        return ConversationHandler.END
    
    elif query.data == 'add_context':
        await query.edit_message_reply_markup(reply_markup=None)
        await query.message.reply_text(
            "Please send additional information about the dish "
            "(for example: portion size, ingredients, cooking method)"
        )
        return AWAITING_CONTEXT

async def process_additional_context(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler for receiving additional context"""
    try:
        new_context = update.message.text
        combined_context = f"{context.user_data['last_additional_info']}. Additional context: {new_context}"
        
        # Get new response from GPT with additional context
        gpt_response = await analyze_image_with_gpt(context.user_data['photo_base64'], combined_context)

        # Create keyboard with buttons
        keyboard = [
            [
                InlineKeyboardButton("✅ Correct", callback_data='correct'),
                InlineKeyboardButton("❌ Add Context", callback_data='add_context')
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        # Send new response with buttons
        await update.message.reply_text(
            f"{gpt_response}\n\nIs this result correct?",
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

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler for /help command"""
    await update.message.reply_text(
        "How to use the bot:\n"
        "1. Send a photo of your dish\n"
        "2. Optionally add a description to the photo\n"
        "3. Wait for the response with calorie information\n"
        "4. If the response is inaccurate, click 'Add Context' and provide additional information\n\n"
        "For best results:\n"
        "- Take photos in good lighting\n"
        "- Try to capture the entire dish\n"
        "- Add useful information in the description"
    )
    return ConversationHandler.END

def main():
    """Main bot launch function"""
    # Create application
    application = Application.builder().token(TELEGRAM_TOKEN).build()

    # Create conversation handler
    conv_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.PHOTO, process_photo)],
        states={
            AWAITING_FEEDBACK: [CallbackQueryHandler(button_callback)],
            AWAITING_CONTEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_additional_context)]
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )

    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(conv_handler)

    # Launch bot
    application.run_polling()

if __name__ == '__main__':
    main() 