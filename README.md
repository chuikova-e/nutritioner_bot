# Telegram Bot for Calorie Counting

This bot analyzes food photos and determines the approximate number of calories in a dish using GPT-4 Vision.

## Project Structure

```
nutri/
├── src/              # Source code
│   ├── __init__.py  # Package initialization
│   ├── main.py      # Main bot file
│   └── config.py    # Configuration
├── requirements.txt  # Project dependencies
├── setup_venv.sh    # Environment setup script
└── .env             # Environment variables file
```

## Requirements

- Python 3.11+
- Telegram Bot Token
- OpenAI API Key

## Virtual Environment

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

## Installation

1. Clone the repository
2. Set up the virtual environment (see above)
3. Create a `.env` file in the project root directory with the following content:
```
TELEGRAM_TOKEN=your_telegram_token
OPENAI_API_KEY=your_openai_key
```

## Running

```bash
# Activate the virtual environment if not already activated
source venv/bin/activate

# Run the bot
python src/main.py
```

## Usage

1. Find the bot on Telegram
2. Send a food photo to the bot
3. Optionally add a description to the photo
4. Receive a response with calorie information
5. If the response is inaccurate, click 'Add Context' and provide additional information

## Note

For best results:
- Take photos in good lighting
- Try to capture the entire dish
- Add useful information in the description (e.g., portion size, ingredients)

## Commands

- `/start` - start working with the bot
- `/help` - get usage help

## Note

For best results:
- Take photos in good lighting
- Try to capture the entire dish
- Add useful information in the description (e.g., portion size, ingredients) 