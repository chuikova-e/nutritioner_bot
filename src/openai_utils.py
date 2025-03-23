import logging
import base64
from openai import AsyncOpenAI
from config import OPENAI_API_KEY, GPT_MODEL
from constants import TELEGRAM_FORMATTING

# OpenAI client initialization
client = AsyncOpenAI(api_key=OPENAI_API_KEY)


async def analyze_image_with_gpt(photos_base64: list, additional_info: str) -> str:
    """Sends request to OpenAI and returns response"""
    # Prepare base prompt
    prompt = (
        f"Определи КБЖУ блюда по {'фотографии' if photos_base64 else 'описанию'}. "
        f"Рассчитай КБЖУ для каждого продукта и суммарные значения. "
        f"Если количество продукта не указано, используй стандартную порцию. "
        f"Отвечай кратко, без вводных фраз и пояснений.\n\n"
        f"{TELEGRAM_FORMATTING}"
    )

    # Add additional info if not empty
    if additional_info:
        prompt += f"\n\nОписание блюда: {additional_info}"

    messages = [{"type": "text", "text": prompt}]

    # Add photos if any
    for photo_base64 in photos_base64:
        messages.append(
            {
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{photo_base64}"},
            }
        )

    # Log the prompt at DEBUG level
    logging.debug(f"GPT Prompt for image analysis:\n{messages}")

    response = await client.chat.completions.create(
        model=GPT_MODEL,
        messages=[{"role": "user", "content": messages}],
        max_tokens=500,
    )
    return response.choices[0].message.content


def encode_image(image_path):
    """Function to encode the image"""
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode("utf-8")


async def transcribe_audio(audio_file: str) -> str:
    """Transcribe audio using OpenAI Whisper"""
    try:
        with open(audio_file, "rb") as audio:
            response = await client.audio.transcriptions.create(
                model="whisper-1", file=audio, language="ru"
            )
            return response.text
    except Exception as e:
        logging.error(f"Error transcribing audio: {str(e)}")
        return None


async def analyze_nutrition_vs_goals(food_records: list, goals: str) -> str:
    """Analyze how well the daily nutrition matches user's goals"""
    if not food_records or not goals:
        return None

    # Prepare the daily nutrition summary with timing information
    daily_nutrition = []
    for time, record in food_records:
        daily_nutrition.append(f"[{time.strftime('%H:%M')}] {record}")

    daily_nutrition_text = "\n\n".join(daily_nutrition)

    try:
        prompt = f"""Проанализируй, насколько питание человека за день соответствует его целям.

Цели:
{goals}

Питание за день (время приема пищи указано в квадратных скобках):
{daily_nutrition_text}

Проведи анализ как опытный нутрициолог. Оцени:
1. Соответствие калорийности (если указана цель)
2. Баланс БЖУ (если указаны цели)
3. Соответствие качественным целям (например, количество овощей, процент сладкого и т.д.)
4. Время приема пищи:
   - Распределение калорий в течение дня
   - Интервалы между приемами пищи
   - Соответствие времени приема пищи физиологической норме
5. Общие рекомендации по улучшению

Ответ дай на русском языке в формате:
- Краткий вывод (1-2 предложения)
- Детальный анализ по пунктам
- Рекомендации на следующий день

{TELEGRAM_FORMATTING}"""

        # Log the prompt at DEBUG level
        logging.debug(f"GPT Prompt for nutrition analysis:\n{prompt}")

        response = await client.chat.completions.create(
            model=GPT_MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1000,
        )
        return response.choices[0].message.content
    except Exception as e:
        logging.error(f"Error analyzing nutrition vs goals: {str(e)}")
        return None


async def analyze_weight_progress(
    username: str,
    current_weight: float,
    food_records: list,
    weight_history,
    target_weight,
    nutrition_goals,
) -> str:
    """Analyze weight progress and nutrition"""
    history = weight_history

    if len(history) < 2:
        weight_change = "первое измерение"
    else:
        prev_weight = history[1][1]  # Previous weight
        weight_diff = current_weight - prev_weight
        if abs(weight_diff) < 0.1:
            weight_change = "без изменений"
        else:
            weight_change = f"{'увеличился' if weight_diff > 0 else 'снизился'} на {abs(weight_diff):.1f} кг"

    try:
        prompt = f"""Проанализируй прогресс в снижении веса и питание за неделю.

Информация о весе:
- Текущий вес: {current_weight} кг
- Изменение веса: {weight_change}
- Целевой вес: {target_weight if target_weight else 'не указан'} кг

Цели по питанию:
{nutrition_goals if nutrition_goals else 'не указаны'}

Питание за неделю:
{chr(10).join(food_records)}

Проведи анализ как опытный нутрициолог. Важно:
1. Анализ должен быть доказательным и адекватным
2. Снижение веса на 100-300 грамм в неделю - это нормально и полезно
3. Резкие ограничения и жесткие диеты недопустимы
4. Важно поддерживать здоровое и комфортное питание
5. Все рекомендации должны учитывать цели по питанию пользователя

Оцени:
1. Прогресс в весе (если вес не снижается или растет, укажи возможные причины в питании)
2. Соответствие питания установленным целям (калории, БЖУ, другие качественные цели)
3. Продукты и привычки, которые помогают или мешают достижению целей
4. Позитивные изменения в питании

Ответ дай на русском языке в формате:
- Краткий вывод о прогрессе и соответствии целям
- Детальный анализ питания
- Рекомендации по улучшению (с учетом целей)

{TELEGRAM_FORMATTING}"""

        # Log the prompt at DEBUG level
        logging.debug(f"GPT Prompt for weight progress analysis:\n{prompt}")

        response = await client.chat.completions.create(
            model=GPT_MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1000,
        )
        return response.choices[0].message.content
    except Exception as e:
        logging.error(f"Error analyzing weight progress: {str(e)}")
        return None
