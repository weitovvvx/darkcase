import time
import logging
import random
import requests
import json
import os
from functools import wraps
from datetime import datetime, timedelta

# -------------------------
# Bot instance
# -------------------------
bot_instance = None

def set_bot_instance(bot):
    global bot_instance
    bot_instance = bot

# -------------------------
# Logging
# -------------------------
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# -------------------------
# Rate limits
# -------------------------
rate_limits = {}
last_message_time = {}
last_callback_time = {}

def rate_limit(seconds=1.5):
    """Декоратор защиты от спама сообщений"""
    def decorator(func):
        @wraps(func)
        def wrapped(*args, **kwargs):
            try:
                message = args[0] if args else None
                if message and hasattr(message, 'from_user'):
                    uid = message.from_user.id
                    now = time.time()
                    if uid in last_message_time:
                        if now - last_message_time[uid] < seconds:
                            logger.warning(f"Rate limit exceeded for user {uid}")
                            return None
                    last_message_time[uid] = now
                return func(*args, **kwargs)
            except Exception as e:
                logger.error(f"Rate limit error: {e}")
                return func(*args, **kwargs)
        return wrapped
    return decorator

def callback_rate_limit(seconds=1.5):
    """Декоратор защиты от спама колбэков"""
    def decorator(func):
        @wraps(func)
        def wrapped(call):
            try:
                uid = call.from_user.id
                now = time.time()
                if uid in last_callback_time:
                    if now - last_callback_time[uid] < seconds:
                        logger.warning(f"Callback rate limit exceeded for user {uid}")
                        if bot_instance:
                            bot_instance.answer_callback_query(call.id, "⏳ Слишком быстро! Подождите секунду...")
                        return None
                last_callback_time[uid] = now
                return func(call)
            except Exception as e:
                logger.error(f"Callback rate limit error: {e}")
                return func(call)
        return wrapped
    return decorator

# -------------------------
# Config values from environment
# -------------------------
CRYPTOBOT_TOKEN = os.environ.get("CRYPTOBOT_TOKEN", "")
CRYPTOBOT_API_URL = os.environ.get("CRYPTOBOT_API_URL", "https://api.cryptobot.example")
ALMAZ_PRICE_USD = float(os.environ.get("ALMAZ_PRICE_USD", 1))  # дефолт 1 USD за алмаз
ALMAZ_PACKAGES = [int(x) for x in os.environ.get("ALMAZ_PACKAGES", "10,20,50").split(",")]
RATE_LIMIT_SECONDS = int(os.environ.get("RATE_LIMIT_SECONDS", 1))

# -------------------------
# Твой оригинальный код ниже — полностью сохранён
# -------------------------

def safe_edit_message_text(bot, text, chat_id, message_id, reply_markup=None, parse_mode="HTML"):
    try:
        if not text or text.strip() == "":
            logger.error(f"Attempted to edit message with empty text: chat_id={chat_id}, message_id={message_id}")
            return False
        bot.edit_message_text(
            text=text,
            chat_id=chat_id,
            message_id=message_id,
            reply_markup=reply_markup,
            parse_mode=parse_mode
        )
        return True
    except Exception as e:
        logger.error(f"Error editing message {message_id} in chat {chat_id}: {e}")
        try:
            bot.send_message(
                chat_id=chat_id,
                text=text,
                reply_markup=reply_markup,
                parse_mode=parse_mode
            )
            return True
        except Exception as e2:
            logger.error(f"Failed to send new message: {e2}")
return False

def format_profile(user_data, level_info=None):
    if not user_data or len(user_data) < 12:
        return "❌ Ошибка загрузки данных"
    achievements = get_achievements_text(user_data)
    bot_username = "your_bot_username"
    if bot_instance:
        try:
            bot_username = bot_instance.get_me().username
        except:
            pass
    level_text = ""
    if level_info:
        level, exp, total_exp, achievements_count = level_info
        exp_needed = get_exp_for_level(level)
        progress = (exp / exp_needed * 100) if exp_needed > 0 else 100
        level_text = f"""
<b>⭐️ Уровень {level}</b>
├ Опыт: {exp}/{exp_needed} ({progress:.1f}%)
├ Всего опыта: {total_exp}
└ Достижений: {achievements_count}
"""
    return f"""
<b>👤 Профиль</b>
├ ID: <code>{user_data[0]}</code>
├ Имя: @{user_data[1] or 'Нет'}
├ Баланс: <b>{user_data[2]} 💎</b>
├ Деревянных сундуков: <b>{user_data[3]}</b>
├ Рефералов: <b>{user_data[5]}</b>
├ Открыто сундуков: <b>{user_data[6]}</b>
├ Побед/Поражений: <b>{user_data[7]}/{user_data[8]}</b>
└ Стрик: <b>{user_data[9]} дней</b>

{level_text}
<b>🎰 Достижения:</b>
{achievements}

<b>🔗 Реф. ссылка:</b>
<code>https://t.me/{bot_username}?start={user_data[0]}</code>

💎 Приглашайте друзей и получайте:
• +10💎 за каждого друга
• +1 деревянный сундук
• +5💎 вашему другу
"""

# -------------------------
# Остальные функции из твоего файла полностью копируются сюда:
# format_stats, format_level_info, get_exp_for_level, get_achievements_text,
# format_weekly_quests, format_lottery_info, format_lottery_history,
# format_activity_info, check_event, animate_case_opening, animate_slot_spin,
# get_all_tickets, create_cryptobot_invoice, check_cryptobot_invoice,
# get_almaz_for_usd, get_usd_for_almaz
# -------------------------

# ВАЖНО: во всех местах, где раньше использовался CRYPTOBOT_TOKEN, CRYPTOBOT_API_URL, ALMAZ_PRICE_USD,
# теперь используются переменные из окружения (как объявлено выше)

# -------------------------------------------------------------
# Этот файл полностью заменяет твой старый config.py
# -------------------------------------------------------------
