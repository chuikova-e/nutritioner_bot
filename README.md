# Telegram Bot for Calorie Tracking

A powerful Telegram bot that leverages GPT-4 vision capabilities to analyze food photos and provide comprehensive nutritional information. This intelligent assistant helps users monitor their daily food intake and make informed dietary choices to achieve their health and fitness goals.

## Key Features

- **Advanced Image Analysis**: Uses GPT-4 to recognize food items from photos with high accuracy
- **Multi-Format Input**: Accepts photos, voice messages, and text descriptions for maximum flexibility
- **Detailed Nutritional Breakdown**: Provides calories, macronutrients (proteins, fats, carbs), and micronutrients
- **Personalized Goal Setting**: Track your progress against customized nutrition and weight targets
- **Interactive Experience**: User-friendly buttons for seamless interaction and feedback
- **Voice Message Processing**: Convert speech to text for hands-free food logging
- **Daily and Weekly Reports**: Automated nutrition summaries and weight tracking reminders
- **Data-Driven Insights**: Personalized recommendations based on your eating patterns and goals
- **Private and Secure**: Access limited to authorized users only

## Usage

1. Find the bot on Telegram and click the "Start" button or send the `/start` command
2. Set up your nutrition goals using the `/setgoals` command (specify calories, proteins, fats, and carbohydrates)
3. Set your target weight with the `/targetweight` command to track your progress
4. Send food photos (up to 5 photos in one message) for analysis
5. For better analysis accuracy, add:
   - Text descriptions to photos (portion size, ingredients)
   - Voice messages with additional information
6. The bot will analyze your photos using GPT-4 and provide:
   - Meal calorie information
   - Protein, fat, and carbohydrate content
   - Nutrition recommendations
7. Use the interactive buttons under the message to:
   - Confirm the analysis is correct
   - Add additional context
   - Cancel the analysis
8. Regularly track your weight using the `/weight` command
9. Receive automatic daily nutrition reports and weekly weight tracking reminders
10. Use the `/goals`, `/calories`, and `/analyze` commands to view statistics and detailed analysis of your nutrition


## Commands

- `/start` - Start the bot and get welcome message
- `/help` - Show detailed usage instructions 
- `/setgoals` - Set your nutrition goals
- `/goals` - View your current nutrition goals
- `/weight` - Track your weight progress
- `/targetweight` - Set your target weight
- `/calories` - View your daily calories consumed
- `/analyze` - Get detailed nutrition analysis


## Security

The bot is configured to only allow access to specific users. Usernames must be added to the `ALLOWED_USERS` environment variable (without @ symbol). Users without a username and unauthorized users will be denied access. All access attempts are logged. 

## Installation


### Requirements

- Python 3.11+
- Telegram Bot Token
- OpenAI API Key

### Virtual Environment

Follow these steps to set up the project's virtual environment:

1. Make sure you have execution rights for the script:
```bash
chmod +x setup_venv.sh
```

2. Run the setup script:
```bash
./setup_venv.sh
```

The script will automatically:
- Check for Python 3.11
- Create a virtual environment
- Activate it
- Update pip
- Install all dependencies from requirements.txt
- Install development tools (pylint, black, pytest)

To activate an existing virtual environment:
```bash
source venv/bin/activate
```

To deactivate the virtual environment:
```bash
deactivate
```

## Running

1. Clone the repository
2. Set up the virtual environment (see above)
3. Create a `.env` file in the project root directory with the following content:
```
TELEGRAM_TOKEN=your_telegram_token
OPENAI_API_KEY=your_openai_key
ALLOWED_USERS=username1,username2  # Comma-separated list of Telegram usernames (without @ symbol)
GPT_MODEL=gpt-4o
```

```bash
# Activate the virtual environment if not already activated
source venv/bin/activate

# Run the bot
python src/main.py
```
