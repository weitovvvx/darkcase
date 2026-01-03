import time
import logging
import random
import requests
import json
import os
from functools import wraps
from datetime import datetime, timedelta

# Добавляем глобальную переменную для бота
bot_instance = None

def set_bot_instance(bot):
    global bot_instance
    bot_instance = bot

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Рейт-лимит для защиты от спама
rate_limits = {}
last_message_time = {}
last_callback_time = {}

def rate_limit(seconds=1.5):
    """Декоратор для защиты от спама сообщений"""
    def decorator(func):
        @wraps(func)
        def wrapped(*args, **kwargs):
            try:
                message = args[0] if args else None
                if message and hasattr(message, 'from_user'):
                    uid = message.from_user.id
                    now = time.time()
                    
                    # Проверяем время последнего сообщения
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
    """Декоратор для защиты от спама колбэков"""
    def decorator(func):
        @wraps(func)
        def wrapped(call):
            try:
                uid = call.from_user.id
                now = time.time()
                
                # Проверяем время последнего колбэка
                if uid in last_callback_time:
                    if now - last_callback_time[uid] < seconds:
                        logger.warning(f"Callback rate limit exceeded for user {uid}")
                        bot_instance.answer_callback_query(call.id, "⏳ Слишком быстро! Подождите секунду...")
                        return None
                
                last_callback_time[uid] = now
                return func(call)
            except Exception as e:
                logger.error(f"Callback rate limit error: {e}")
                return func(call)
        return wrapped
    return decorator

def safe_edit_message_text(bot, text, chat_id, message_id, reply_markup=None, parse_mode="HTML"):
    """Безопасное редактирование сообщения с обработкой ошибок"""
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
        
        # Попытка отправить новое сообщение
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
    
    # Получаем username бота для ссылки
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
<b>⭐ Уровень {level}</b>
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

def format_stats(user_data):
    if not user_data or len(user_data) < 9:
        return "❌ Ошибка загрузки данных"
    
    total_games = user_data[7] + user_data[8]
    winrate = (user_data[7] / total_games * 100) if total_games > 0 else 0
    
    return f"""
<b>📊 Статистика</b>
├ Открыто сундуков: <b>{user_data[6]}</b>
├ Побед: <b>{user_data[7]}</b>
├ Проигрышей: <b>{user_data[8]}</b>
├ Рефералов: <b>{user_data[5]}</b>
├ Всего игр: <b>{total_games}</b>
└ Винрейт: <b>{winrate:.1f}%</b>
"""

def format_level_info(level_info, user_data):
    if not level_info:
        return "❌ Ошибка загрузки данных уровня"
    
    level, exp, total_exp, achievements_count = level_info
    exp_needed = get_exp_for_level(level)
    progress = (exp / exp_needed * 100) if exp_needed > 0 else 100
    
    next_level = level + 1
    next_exp_needed = get_exp_for_level(next_level) if next_level <= 10 else "MAX"
    
    from models import LEVELS
    current_title = LEVELS.get(level, {}).get("title", "Неизвестно")
    next_title = LEVELS.get(next_level, {}).get("title", "Максимальный") if next_level <= 10 else "Максимальный"
    
    progress_bar = "🟩" * int(progress / 10) + "⬜" * (10 - int(progress / 10))
    
    return f"""
<b>⭐ УРОВЕНЬ {level} - {current_title}</b>

{progress_bar} {progress:.1f}%

📊 <b>Статистика:</b>
├ Текущий опыт: <b>{exp}/{exp_needed}</b>
├ Всего опыта: <b>{total_exp}</b>
├ Достижений: <b>{achievements_count}</b>
└ Баланс: <b>{user_data[2] if user_data else 0}💎</b>

🎯 <b>Следующий уровень:</b>
├ Уровень {next_level} - {next_title}
└ Нужно опыта: <b>{next_exp_needed}</b>

💡 <b>Как получить опыт:</b>
• Открытие сундуков: +5-20 опыта
• Победы в играх: +10-50 опыта
• Ежедневный вход: +15 опыта
• Выполнение заданий: +25-100 опыта
• Приглашение друзей: +30 опыта
"""

def get_exp_for_level(level):
    return int(100 * (level ** 1.5))

def get_achievements_text(user_data):
    if len(user_data) < 10:
        return "Еще нет достижений"
    
    achievements = []
    
    try:
        if user_data[7] >= 1:
            achievements.append("🎯 Первая победа")
        if user_data[6] >= 50:
            achievements.append("📦 Мастер сундуков")
        if user_data[2] >= 1000:
            achievements.append("💎 Богач")
        if (user_data[7] + user_data[8]) >= 100:
            achievements.append("🎰 Активный игрок")
        if user_data[9] >= 7:
            achievements.append("🔥 Недельный стрик")
        if user_data[5] >= 10:
            achievements.append("👥 Социальный")
        if user_data[9] >= 30:
            achievements.append("⭐ Месячный стрик")
    except (IndexError, TypeError):
        pass
    
    if not achievements:
        return "Еще нет достижений"
    return "\n".join([f"✓ {ach}" for ach in achievements])

def format_weekly_quests(quests_data):
    if not quests_data:
        return "❌ Нет активных заданий"
    
    from models import WEEKLY_QUESTS
    
    text = "<b>📅 НЕДЕЛЬНЫЕ ЗАДАНИЯ</b>\n\n"
    total_reward = 0
    completed_count = 0
    
    for quest_data in quests_data:
        quest_id, progress, completed, claimed, goal = quest_data
        
        if quest_id in WEEKLY_QUESTS:
            quest = WEEKLY_QUESTS[quest_id]
            
            status = ""
            if claimed:
                status = "✅ Получено"
            elif completed or progress >= goal:
                status = "🎁 Забрать награду"
            else:
                status = f"📊 {progress}/{goal}"
            
            reward = quest.get("reward", 0)
            if not claimed and (completed or progress >= goal):
                total_reward += reward
            
            if completed or progress >= goal:
                completed_count += 1
            
            text += f"{quest['name']}\n"
            text += f"└ {quest['description']} - {status}\n"
            if not claimed and (completed or progress >= goal):
                text += f"   💎 Награда: +{reward}💎\n"
            text += "\n"
    
    text += f"<b>📈 Прогресс:</b> {completed_count}/{len(quests_data)} заданий\n"
    text += f"<b>💎 Всего наград:</b> +{total_reward}💎\n\n"
    
    if total_reward > 0:
        text += "🎁 <b>Заберите награды в меню 'Награды за задания'!</b>"
    
    return text

def format_lottery_info(draw_date, ticket_count, user_tickets_count, jackpot):
    from datetime import datetime
    
    try:
        draw_date_obj = datetime.strptime(draw_date, "%Y-%m-%d")
        today = datetime.now()
        days_left = (draw_date_obj - today).days
        
        days_text = f"{days_left} дней"
        if days_left == 1:
            days_text = "1 день"
        elif days_left == 0:
            days_text = "СЕГОДНЯ!"
    except:
        days_text = "скоро"
    
    text = f"""
<b>🎰 РОЗЫГРЫШ</b>

🏆 <b>Следующий розыгрыш:</b> {draw_date}
⏰ <b>Осталось:</b> {days_text}

📊 <b>Статистика:</b>
├ Билетов куплено: <b>{ticket_count}</b>
├ Участников: <b>{len(set([t[0] for t in get_all_tickets(draw_date)])) if ticket_count > 0 else 0}</b>
└ Ваши билеты: <b>{user_tickets_count}</b>

💎 <b>Призовой фонд:</b> <b>{jackpot}💎</b>

🎫 <b>Цена билета:</b> 50💎
🎁 <b>Шанс на победу:</b> 1 к {ticket_count if ticket_count > 0 else 1}

💡 <b>Как участвовать:</b>
1. Купите билет за 50💎
2. Ждите розыгрыша
3. Если ваш билет выиграл - забирайте приз!
"""
    return text

def format_lottery_history(history_data):
    if not history_data:
        return "📜 История розыгрышей пуста"
    
    text = "<b>📜 ИСТОРИЯ РОЗЫГРЫШЕЙ</b>\n\n"
    
    for i, (draw_date, winner_username, prize, ticket_count, created_at) in enumerate(history_data, 1):
        draw_date_str = draw_date
        if len(draw_date_str) > 10:
            draw_date_str = draw_date_str[:10]
        
        text += f"<b>#{i} {draw_date_str}</b>\n"
        text += f"🏆 Победитель: @{winner_username or 'Неизвестно'}\n"
        text += f"💎 Выигрыш: {prize}💎\n"
        text += f"🎫 Билетов: {ticket_count}\n"
        
        if i < len(history_data):
            text += "━━━━━━━━━━━━━━━━\n"
    
    return text

def format_activity_info(activity_data, streak_days):
    if not activity_data:
        return "❌ Нет данных об активности"
    
    user_id, last_active, daily_login_count, streak_bonus_claimed, first_game_bonus = activity_data
    
    from games import ActivitySystem
    streak_bonus, streak_message = ActivitySystem.get_streak_bonus(streak_days)
    first_game_bonus_amount, first_game_message = ActivitySystem.get_first_game_bonus()
    
    can_claim_streak = streak_bonus > 0 and not streak_bonus_claimed
    can_claim_first_game = first_game_bonus_amount > 0 and not first_game_bonus
    
    last_active_time = time.strftime('%H:%M %d.%m.%Y', time.localtime(last_active)) if last_active > 0 else "Никогда"
    
    text = f"""
<b>📈 АКТИВНОСТЬ</b>

📅 <b>Статистика:</b>
├ Последний вход: <b>{last_active_time}</b>
├ Входов сегодня: <b>{daily_login_count}</b>
└ Текущий стрик: <b>{streak_days} дней</b>

🎁 <b>Доступные бонусы:</b>
"""
    
    if can_claim_streak:
        text += f"├ 🔥 Бонус за серию: +{streak_bonus}💎 {streak_message}\n"
    else:
        text += f"├ 🔥 Бонус за серию: Уже получен\n"
    
    if can_claim_first_game:
        text += f"└ 🎮 Бонус за первую игру: +{first_game_bonus_amount}💎 {first_game_message}\n"
    else:
        text += f"└ 🎮 Бонус за первую игру: Уже получен\n"
    
    text += f"\n💡 <b>Бонусы обновляются ежедневно в 00:00</b>"
    
    return text, can_claim_streak, can_claim_first_game, streak_bonus, first_game_bonus_amount

def check_event():
    """Проверка активных ивентов с уменьшенными наградами"""
    now = datetime.now()
    events = []
    
    # Уменьшенные награды для ивентов (10-20 звезд)
    if now.day == 13 and now.weekday() == 4:
        events.append({"name": "🔮 Пятница 13-е", "bonus": "Бонус +15💎 за первую игру дня"})
    
    if now.weekday() >= 5:
        events.append({"name": "🎪 Выходные", "bonus": "Бонус +10💎 за первую победу"})
    
    if 6 <= now.hour < 12:
        events.append({"name": "🌅 Утренний бонус", "bonus": "Бонус +12💎 за открытие сундука"})
    
    if 0 <= now.hour < 6:
        events.append({"name": "🌙 Ночной бонус", "bonus": "Бонус +18💎 за билет розыгрыша"})
    
    if now.day == 1:
        events.append({"name": "📅 Первое число", "bonus": "Бонус +20💎 всем активным игрокам"})
    
    return events

def animate_case_opening(bot, chat_id, message_id, case_emoji="🎁"):
    """Анимация открытия сундука"""
    import time
    
    try:
        # Анимация встряхивания
        for _ in range(3):
            for emoji in ["🎁", "📦", "🎊", "🎉"]:
                try:
                    bot.edit_message_text(f"{emoji} Открываем сундук...", chat_id, message_id)
                    time.sleep(0.2)
                except:
                    pass
        
        # Анимация блеска
        for _ in range(2):
            try:
                bot.edit_message_text(f"✨ {case_emoji} ✨", chat_id, message_id)
                time.sleep(0.3)
                bot.edit_message_text(f"{case_emoji} ✨", chat_id, message_id)
                time.sleep(0.3)
                bot.edit_message_text(f"✨ {case_emoji}", chat_id, message_id)
                time.sleep(0.3)
            except:
                pass
    except Exception as e:
        logger.error(f"Error in case animation: {e}")

def animate_slot_spin(bot, chat_id, message_id):
    """Анимация вращения слотов"""
    import time
    symbols = ["🍒", "🍋", "⭐", "7️⃣", "🔔", "💎"]
    
    try:
        # Быстрая прокрутка
        for i in range(8):
            try:
                if i < 3:
                    delay = 0.1
                elif i < 6:
                    delay = 0.2
                else:
                    delay = 0.3
                
                # Генерируем случайные символы для анимации
                spin_symbols = [random.choice(symbols) for _ in range(3)]
                animation_text = f"🎰 {' '.join(spin_symbols)}"
                
                if i < 6:
                    bot.edit_message_text(f"🎰 Вращаем... {animation_text}", chat_id, message_id)
                else:
                    bot.edit_message_text(f"🎰 Замедляемся... {animation_text}", chat_id, message_id)
                
                time.sleep(delay)
            except:
                pass
        
        # Финальная пауза
        time.sleep(0.5)
        
    except Exception as e:
        logger.error(f"Error in slot animation: {e}")

def get_all_tickets(draw_date):
    from database import get_all_tickets as db_get_all_tickets
    return db_get_all_tickets(draw_date)

# CryptoBot API функции
def create_cryptobot_invoice(amount_usd, description="Пополнение алмазов"):
    """Создать счет в CryptoBot"""
    headers = {
        "Crypto-Pay-API-Token": CRYPTOBOT_TOKEN,
        "Content-Type": "application/json"
    }
    
    data = {
        "amount": str(amount_usd),
        "asset": "USDT",  # Можно изменить на TON, SOL и т.д.
        "description": description,
        "hidden_message": "Спасибо за покупку!",
        "paid_btn_name": "viewItem",
        "paid_btn_url": "https://t.me/darkcase_bot",
        "payload": json.dumps({"type": "almaz_purchase"})
    }
    
    try:
        response = requests.post(f"{CRYPTOBOT_API_URL}/createInvoice", headers=headers, json=data, timeout=10)
        if response.status_code == 200:
            result = response.json()
            if result.get("ok"):
                invoice = result.get("result")
                return invoice.get("invoice_id"), invoice.get("pay_url")
            else:
                logger.error(f"CryptoBot API error: {result.get('error', {}).get('name', 'Unknown error')}")
    except requests.exceptions.Timeout:
        logger.error("CryptoBot API timeout")
    except requests.exceptions.ConnectionError:
        logger.error("CryptoBot API connection error")
    except Exception as e:
        logger.error(f"CryptoBot error: {e}")
    
    return None, None

def check_cryptobot_invoice(invoice_id):
    """Проверить статус счета в CryptoBot"""
    headers = {
        "Crypto-Pay-API-Token": CRYPTOBOT_TOKEN
    }
    
    try:
        response = requests.get(f"{CRYPTOBOT_API_URL}/getInvoices?invoice_ids={invoice_id}", 
                               headers=headers, timeout=10)
        if response.status_code == 200:
            result = response.json()
            if result.get("ok"):
                invoices = result.get("result", {}).get("items", [])
                if invoices:
                    return invoices[0].get("status")
    except requests.exceptions.Timeout:
        logger.error("CryptoBot check timeout")
    except requests.exceptions.ConnectionError:
        logger.error("CryptoBot check connection error")
    except Exception as e:
        logger.error(f"CryptoBot check error: {e}")
    
    return None

def get_almaz_for_usd(amount_usd):
    """Конвертировать USD в алмазы"""
    from config import ALMAZ_PRICE_USD
    return int(amount_usd / ALMAZ_PRICE_USD)

def get_usd_for_almaz(almaz_amount):
    """Конвертировать алмазы в USD"""
    from config import ALMAZ_PRICE_USD
    return al * ALMAZ_PRICE_USD