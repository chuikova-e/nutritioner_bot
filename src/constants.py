# Constants file for the Nutri app

# Conversation states
AWAITING_FEEDBACK = 0
AWAITING_CONTEXT = 1
AWAITING_GOALS = 2
AWAITING_WEIGHT = 3
AWAITING_TARGET_WEIGHT = 4

# Telegram formatting instructions
TELEGRAM_FORMATTING = """Отвечай, используя только HTML-разметку Telegram:  
- <b>Жирный</b> для важных выводов и итоговых значений.  
- <i>Курсив</i> для пояснений и рекомендаций - используй редко.
- Эмодзи для визуального выделения (📊 для статистики, ⚠️ для предупреждений и т. д.).  
- Добавляй переносы строк для удобочитаемости.  

Не используй `*`, `_` или другие символы Markdown.  
"""

# Default timezone for the application
DEFAULT_TIMEZONE = "Europe/Moscow"
