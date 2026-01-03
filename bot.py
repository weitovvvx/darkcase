import telebot
import time
import random
import os
import subprocess
import sys
import string
import threading
import uuid
from telebot import types
from telebot.apihelper import ApiException
from datetime import datetime, timedelta

from config import *
from database import *
from models import *
from games import Roulette, Dice, StonePaperScissors, SlotMachine, BlackJack, ActivitySystem, Lottery
from keyboards import *
from utils import *
from admin import is_admin

bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")
logger.info("Бот запускается...")

# Устанавливаем инстанс бота для utils
set_bot_instance(bot)

# Глобальные переменные
sponsor_channels_cache = None
sponsor_channels_time = 0
CACHE_DURATION = 300  # 5 минут

# Функция для автоматического перезапуска бота при ошибках
def restart_bot():
    """Перезапуск бота при критической ошибке"""
    logger.info("Перезапуск бота...")
    time.sleep(5)
    os.execv(sys.executable, [sys.executable] + sys.argv)

def get_sponsor_channels_cached():
    """Кэшированный список спонсорских каналов"""
    global sponsor_channels_cache, sponsor_channels_time
    
    current_time = time.time()
    if sponsor_channels_cache is None or (current_time - sponsor_channels_time) > CACHE_DURATION:
        sponsor_channels_cache = get_sponsor_channels()
        sponsor_channels_time = current_time
    
    return sponsor_channels_cache

def check_subscription(user_id):
    """Проверка подписки на все спонсорские каналы"""
    sponsors = get_sponsor_channels_cached()
    
    if not sponsors:
        return True, None, None  # Нет спонсоров - пропускаем проверку
    
    for channel_username, channel_name in sponsors:
        try:
            # Проверяем подписку пользователя на канал
            member = bot.get_chat_member(chat_id=channel_username, user_id=user_id)
            if member.status not in ['member', 'administrator', 'creator']:
                return False, channel_username, channel_name
        except Exception as e:
            logger.error(f"Error checking subscription to {channel_username}: {e}")
            # Если ошибка, считаем что не подписан для безопасности
            return False, channel_username, channel_name
    
    return True, None, None

def check_whitelist_and_subscription(user_id):
    """Проверка белого списка и подписки"""
    from config import WHITELIST_MODE
    
    # Если включен режим белого списка
    if WHITELIST_MODE:
        if not is_admin(user_id) and not is_in_whitelist(user_id):
            return False, "whitelist"
    
    # Проверка подписки на спонсорские каналы
    subscribed, channel_username, channel_name = check_subscription(user_id)
    if not subscribed:
        return False, "subscription", channel_username, channel_name
    
    return True, None, None, None

def send_with_image(chat_id, text, image_name, reply_markup=None):
    """Отправить сообщение с изображением"""
    try:
        image_path = f"images/{image_name}"
        
        if os.path.exists(image_path):
            try:
                with open(image_path, 'rb') as photo:
                    bot.send_photo(chat_id, photo, caption=text, reply_markup=reply_markup, parse_mode="HTML")
                return True
            except Exception as e:
                logger.error(f"Error sending image {image_name}: {e}")
                # Если ошибка - отправляем текстовое сообщение
                bot.send_message(chat_id, text, reply_markup=reply_markup, parse_mode="HTML")
                return False
        else:
            # Если изображение не найдено
            bot.send_message(chat_id, text, reply_markup=reply_markup, parse_mode="HTML")
            logger.warning(f"Image not found: {image_path}")
            return False
    except Exception as e:
        logger.error(f"Error in send_with_image: {e}")
        bot.send_message(chat_id, text, reply_markup=reply_markup, parse_mode="HTML")
        return False

# ========== ХЕНДЛЕРЫ КОМАНД ==========

@bot.message_handler(commands=["start"])
@rate_limit(seconds=RATE_LIMIT_SECONDS)
def start_command(message):
    uid = message.from_user.id
    username = message.from_user.username or str(uid)
    
    # Проверка подписки
    check_result = check_whitelist_and_subscription(uid)
    if not check_result[0]:
        if check_result[1] == "whitelist":
            bot.send_message(uid, "❌ Бот в режиме обслуживания. Доступ только для администраторов.")
            return
        elif check_result[1] == "subscription":
            channel_username, channel_name = check_result[2], check_result[3]
            sponsors = get_sponsor_channels_cached()
            
            text = f"📺 <b>Для использования бота необходимо подписаться на наш канал:</b>\n\n"
            for sp_username, sp_name in sponsors:
                text += f"• {sp_name} - @{sp_username[1:] if sp_username.startswith('@') else sp_username}\n"
            
            text += f"\nПосле подписки нажмите кнопку '✅ Я подписался'"
            
            bot.send_message(
                uid,
                text,
                reply_markup=sponsors_keyboard(sponsors)
            )
            return
    
    try:
        user_data = get_user(uid)
        referrer_id = 0
        
        # Проверяем реферальную ссылку
        if len(message.text.split()) > 1:
            try:
                ref_id = int(message.text.split()[1])
                # Проверяем, чтобы пользователь не указывал себя как реферала
                if ref_id != uid:
                    ref_data = get_user(ref_id)
                    if ref_data:
                        referrer_id = ref_id
                        logger.info(f"User {uid} came from referral {ref_id}")
            except ValueError:
                pass
        
        if not user_data:
            # Создаем пользователя с указанием реферера
            create_user(uid, username, referrer_id)
            user_data = get_user(uid)
            
            # Если был реферер, начисляем ему бонусы
            if referrer_id > 0 and referrer_id != uid:
                # Даем бонус рефереру
                add_referral(referrer_id)
                update_balance(referrer_id, 10, "ref_bonus")
                
                # Добавляем опыт рефереру
                add_exp(referrer_id, 30)
                
                # Даем бонус новичку
                update_balance(uid, 5, "ref_welcome")
                add_exp(uid, 15)
                
                # Уведомляем реферера
                try:
                    bot.send_message(
                        referrer_id, 
                        f"🎉 По вашей ссылке зарегистрировался новый пользователь @{username}!\n"
                        "На ваш баланс зачислено +10💎\n"
                        "Получено +30 опыта!"
                    )
                except:
                    pass
                
                logger.info(f"User {uid} registered with referral from {referrer_id}")
        else:
            # Пользователь уже существует, обновляем username если изменился
            if user_data[1] != username:
                cursor.execute("UPDATE users SET username=? WHERE user_id=?", (username, uid))
                conn.commit()
            
            # Если пользователь пришел по реферальной ссылке, но у него нет реферера
            if referrer_id > 0 and referrer_id != uid and user_data[14] == 0:  # referrer_id в users таблице
                # Обновляем реферера в базе данных
                cursor.execute("UPDATE users SET referrer_id=? WHERE user_id=?", (referrer_id, uid))
                conn.commit()
                
                # Начисляем бонусы рефереру
                add_referral(referrer_id)
                update_balance(referrer_id, 10, "ref_bonus_late")
                add_exp(referrer_id, 30)
                
                # Уведомляем реферера
                try:
                    bot.send_message(
                        referrer_id, 
                        f"🎉 Пользователь @{username}, который ранее зарегистрировался, стал вашим рефералом!\n"
                        "На ваш баланс зачислено +10💎\n"
                        "Получено +30 опыта!"
                    )
                except:
                    pass
        
        # Обновляем активность
        update_user_activity(uid)
        
        # Проверяем бонусы за активность
        activity_data = get_user_activity(uid)
        daily_info = get_daily_info(uid)
        streak_days = daily_info[0] if daily_info else 0
        
        streak_bonus, streak_message = ActivitySystem.get_streak_bonus(streak_days)
        can_claim_streak = streak_bonus > 0 and activity_data and not activity_data[3]
        
        bonus_text = ""
        if can_claim_streak:
            bonus_text = f"\n\n🎁 <b>Доступен бонус за серию: +{streak_bonus}💎</b>"
        
        # Отправляем приветствие с изображением
        welcome_text = f"""
<b>🎮 DARKCASE - Игровой Бот</b>

💎 <b>Добро пожаловать в мир развлечений!</b>

🎮 <b>Доступные функции:</b>
• Сундуки с наградами
• Мини-игры
• Система уровни и опыта
• Недельные задания
• Еженедельный розыгрыш
• Бонусы за активность
• Обмен алмазов на Telegram Stars
• Пополнение баланса звездами

<u>📋 Пользовательское соглашение:</u>
https://telegra.ph/Polzovatelskoe-soglashenie-01-02-14

🔗 <b>Ваша реф.ссылка:</b>
<code>https://t.me/{bot.get_me().username}?start={uid}</code>
{bonus_text}
"""
        
        send_with_image(uid, welcome_text, "welcome.jpg", main_keyboard(is_admin(uid)))
        logger.info(f"User {uid} started bot")
        
    except Exception as e:
        logger.error(f"Error in start_command: {e}")
        bot.send_message(uid, "❌ Произошла ошибка. Попробуйте позже.")

# ========== ГЛАВНОЕ МЕНЮ ==========

@bot.message_handler(func=lambda m: m.text == "🎮 Игры")
@rate_limit(seconds=RATE_LIMIT_SECONDS)
def games_menu(message):
    uid = message.from_user.id
    
    # Проверка подписки
    check_result = check_whitelist_and_subscription(uid)
    if not check_result[0]:
        handle_subscription_check(message, check_result)
        return
    
    user_data = get_user(uid)
    
    if not user_data:
        bot.send_message(uid, "❌ Сначала напишите /start")
        return
    
    send_with_image(
        uid,
        "<b>🎮 Выберите категорию</b>\n\n"
        "Выберите что вас интересует:",
        "games.jpg",
        games_menu_keyboard()
    )

@bot.message_handler(func=lambda m: m.text == "👤 Профиль")
@rate_limit(seconds=RATE_LIMIT_SECONDS)
def profile_menu(message):
    uid = message.from_user.id
    
    # Проверка подписки
    check_result = check_whitelist_and_subscription(uid)
    if not check_result[0]:
        handle_subscription_check(message, check_result)
        return
    
    user_data = get_user(uid)
    
    if not user_data:
        bot.send_message(uid, "❌ Сначала напишите /start")
        return
    
    # Получаем информацию об уровне
    level_info = get_user_level(uid)
    
    # Проверяем, является ли пользователь администратором
    admin_check = is_admin(uid)
    
    profile_text = format_profile(user_data, level_info, admin_check)
    send_with_image(uid, profile_text, "profile.jpg", profile_keyboard())

@bot.message_handler(func=lambda m: m.text == "🏆 Топы")
@rate_limit(seconds=RATE_LIMIT_SECONDS)
def tops_menu(message):
    uid = message.from_user.id
    
    # Проверка подписки
    check_result = check_whitelist_and_subscription(uid)
    if not check_result[0]:
        handle_subscription_check(message, check_result)
        return
    
    send_with_image(uid, "🏆 <b>Топы игроков</b>", "top.jpg", tops_keyboard())

@bot.message_handler(func=lambda m: m.text == "🎁 Ежедневный")
@rate_limit(seconds=RATE_LIMIT_SECONDS)
def daily_menu(message):
    uid = message.from_user.id
    
    # Проверка подписки
    check_result = check_whitelist_and_subscription(uid)
    if not check_result[0]:
        handle_subscription_check(message, check_result)
        return
    
    user_data = get_user(uid)
    
    if not user_data:
        bot.send_message(uid, "❌ Сначала напишите /start")
        return
    
    daily_info = get_daily_info(uid)
    if not daily_info:
        bot.send_message(uid, "❌ Ошибка получения данных")
        return
    
    streak, last_daily = daily_info
    now = int(time.time())
    
    if now - last_daily < 86400:  # 24 часа
        next_daily = last_daily + 86400
        wait_time = next_daily - now
        hours = wait_time // 3600
        minutes = (wait_time % 3600) // 60
        
        bot.send_message(
            uid,
            f"⏳ Вы уже получали ежедневный бонус сегодня\n\n"
            f"Текущий стрик: <b>{streak} дней</b>\n"
            f"Следующий бонус через: <b>{hours}ч {minutes}м</b>"
        )
        return
    
    # Начисление бонуса
    new_streak = streak + 1 if (now - last_daily) < 172800 else 1  # Сброс если пропустил день
    bonus = DAILY_BONUS_BASE + (new_streak * 5)  # Базовый + за каждый день стрика
    
    update_daily_streak(uid, new_streak)
    update_balance(uid, bonus, "daily_bonus")
    
    # Добавляем опыт за ежедневный бонус
    add_exp(uid, 15)
    
    send_with_image(
        uid,
        f"🎁 <b>Ежедневный бонус получен!</b>\n\n"
        f"Начислено: <b>+{bonus}💎</b>\n"
        f"Получено: <b>+15 опыта</b>\n"
        f"Текущий стрик: <b>{new_streak} дней</b>\n\n"
        f"💡 Возвращайтесь завтра за большей наградой!",
        "top.jpg"
    )
    logger.info(f"User {uid} claimed daily bonus: {bonus} алмазов, streak: {new_streak}")

@bot.message_handler(func=lambda m: m.text == "📅 Задания")
@rate_limit(seconds=RATE_LIMIT_SECONDS)
def weekly_quests_menu(message):
    uid = message.from_user.id
    
    # Проверка подписки
    check_result = check_whitelist_and_subscription(uid)
    if not check_result[0]:
        handle_subscription_check(message, check_result)
        return
    
    user_data = get_user(uid)
    
    if not user_data:
        bot.send_message(uid, "❌ Сначала напишите /start")
        return
    
    send_with_image(
        uid,
        "<b>📅 НЕДЕЛЬНЫЕ ЗАДАНИЯ</b>\n\n"
        "Выполняйте задания и получайте награды!\n"
        "Задания обновляются каждую неделю.",
        "games.jpg",
        weekly_quests_keyboard()
    )

@bot.message_handler(func=lambda m: m.text == "🎰 Розыгрыш")
@rate_limit(seconds=RATE_LIMIT_SECONDS)
def lottery_menu(message):
    uid = message.from_user.id
    
    # Проверка подписки
    check_result = check_whitelist_and_subscription(uid)
    if not check_result[0]:
        handle_subscription_check(message, check_result)
        return
    
    user_data = get_user(uid)
    
    if not user_data:
        bot.send_message(uid, "❌ Сначала напишите /start")
        return
    
    draw_date = Lottery.get_next_draw_date()
    lottery_stats = get_lottery_stats(draw_date)
    ticket_count = lottery_stats[1] if lottery_stats else 0
    
    user_tickets = get_user_tickets(uid, draw_date)
    user_tickets_count = len(user_tickets)
    
    jackpot = Lottery.get_current_jackpot(ticket_count)
    
    lottery_text = format_lottery_info(draw_date, ticket_count, user_tickets_count, jackpot)
    send_with_image(uid, lottery_text, "lottery.jpg", lottery_keyboard(draw_date, user_tickets_count))

@bot.message_handler(func=lambda m: m.text == "💎 Пополнить")
@rate_limit(seconds=RATE_LIMIT_SECONDS)
def buy_almaz_menu(message):
    uid = message.from_user.id
    
    # Проверка подписки
    check_result = check_whitelist_and_subscription(uid)
    if not check_result[0]:
        handle_subscription_check(message, check_result)
        return
    
    user_data = get_user(uid)
    
    if not user_data:
        bot.send_message(uid, "❌ Сначала напишите /start")
        return
    
    text = """
<b>💎 ПОПОЛНЕНИЕ БАЛАНСА</b>

Выберите способ пополнения:

1. <b>⭐ Telegram Stars</b>
   • 1 Telegram Star = 9 алмазов
   • Минимальная сумма: 1 звезда
   • Быстрое пополнение в Telegram

2. <b>🤖 CryptoBot</b>
   • Оплата криптовалютой (USDT, TON, BTC)
   • Выгодные курсы
   • Анонимно и безопасно

Выберите удобный способ оплаты:
"""
    
    send_with_image(uid, text, "profile.jpg", buy_almaz_keyboard())

@bot.message_handler(func=lambda m: m.text == "🔄 Обмен алмазов")
@rate_limit(seconds=RATE_LIMIT_SECONDS)
def exchange_menu(message):
    uid = message.from_user.id
    
    # Проверка подписки
    check_result = check_whitelist_and_subscription(uid)
    if not check_result[0]:
        handle_subscription_check(message, check_result)
        return
    
    user_data = get_user(uid)
    
    if not user_data:
        bot.send_message(uid, "❌ Сначала напишите /start")
        return
    
    text = f"""
<b>🔄 ОБМЕН АЛМАЗОВ НА TELEGRAM STARS</b>

💎 <b>Здесь вы можете обменять свои алмазы на Telegram Stars подарки!</b>

🎁 <b>Доступные подарки:</b>
• 💝 Сердечко - 150💎 (15⭐ Telegram Stars)
• 🌹 Роза - 250💎 (25⭐ Telegram Stars)
• 🎁 Подарок - 250💎 (25⭐ Telegram Stars)
• 🍾 Шампанское - 500💎 (50⭐ Telegram Stars)
• 🎂 Торт - 500💎 (50⭐ Telegram Stars)
• 🏆 Кубок - 1000💎 (100⭐ Telegram Stars)
• 💎 Бриллиант - 1000💎 (100⭐ Telegram Stars)

📋 <b>Как работает обмен:</b>
1. Выбираете желаемый подарок
2. С вашего баланса списываются алмазы
3. Создается заявка для администратора
4. Администратор вручную отправляет вам Telegram Stars подарок
5. Вы получаете уведомление о выполнении заявки

⏱ <b>Время обработки:</b> Обычно 5-30 минут

💡 <b>Ваш текущий баланс:</b> {user_data[2]}💎
"""
    
    send_with_image(uid, text, "profile.jpg", exchange_menu_keyboard())

@bot.message_handler(func=lambda m: m.text == "🛠 Админ")
@rate_limit(seconds=RATE_LIMIT_SECONDS)
def admin_menu(message):
    uid = message.from_user.id
    if not is_admin(uid):
        bot.send_message(uid, "❌ Доступ запрещен")
        return
    
    send_with_image(uid, "🛠 <b>Панель администратора</b>", "profile.jpg", admin_keyboard())

# ========== ОБРАБОТЧИКИ TELEGRAM STARS ==========

def create_stars_invoice(user_id, stars_amount, diamonds_amount):
    """Создать счет на оплату Telegram Stars"""
    try:
        # Генерируем уникальный payload
        invoice_payload = f"stars_{user_id}_{int(time.time())}_{uuid.uuid4().hex[:8]}"
        
        # Сохраняем платеж в БД
        payment_id = create_stars_payment(user_id, stars_amount, diamonds_amount, invoice_payload)
        
        # ИСПРАВЛЕНО: 1 звезда = 1 единица, Telegram сам показывает правильно
        price_amount = stars_amount  # Не умножаем на 100!
        
        # Отправляем счет
        bot.send_invoice(
            chat_id=user_id,
            title=f"Покупка {diamonds_amount} алмазов",
            description=f"Пополнение баланса: {stars_amount} Telegram Stars = {diamonds_amount} алмазов",
            invoice_payload=invoice_payload,
            provider_token="",  # Для Telegram Stars оставляем пустым
            currency="XTR",     # Код валюты для звезд
            prices=[types.LabeledPrice(label=f"{stars_amount} Telegram Stars", amount=price_amount)],
            start_parameter="stars-payment",
            photo_url="https://img.icons8.com/color/96/000000/diamond--v1.png",
            photo_size=100,
            photo_width=96,
            photo_height=96,
            need_name=False,
            need_phone_number=False,
            need_email=False,
            need_shipping_address=False,
            is_flexible=False,
            disable_notification=False,
            protect_content=False,
            reply_to_message_id=None,
            allow_sending_without_reply=True,
            reply_markup=None
        )
        
        logger.info(f"Created stars invoice for user {user_id}: {stars_amount} stars = {diamonds_amount} diamonds")
        return True
        
    except Exception as e:
        logger.error(f"Error creating stars invoice: {e}")
        return False

@bot.pre_checkout_query_handler(func=lambda query: True)
def process_pre_checkout_query(pre_checkout_query):
    """Обработка pre-checkout запроса для Telegram Stars"""
    try:
        # Всегда подтверждаем запрос
        bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)
        logger.info(f"Pre-checkout query processed: {pre_checkout_query.invoice_payload}")
    except Exception as e:
        logger.error(f"Error in pre-checkout: {e}")
        bot.answer_pre_checkout_query(pre_checkout_query.id, ok=False, error_message="Произошла ошибка")

@bot.message_handler(content_types=['successful_payment'])
def process_successful_payment(message):
    """Обработка успешной оплаты Telegram Stars"""
    try:
        payment_info = message.successful_payment
        user_id = message.from_user.id
        invoice_payload = payment_info.invoice_payload
        
        # Проверяем платеж в БД
        payment = get_stars_payment_by_payload(invoice_payload)
        if not payment:
            logger.error(f"Payment not found in DB: {invoice_payload}")
            return
        
        payment_id, db_user_id, stars_amount, diamonds_received, db_payload, status, created_at, completed_at = payment
        
        if status == 'paid':
            bot.send_message(user_id, "✅ Этот платеж уже был обработан ранее.")
            return
        
        # Обновляем статус платежа
        update_stars_payment_status(invoice_payload, 'paid')
        
        # Начисляем алмазы
        update_balance(user_id, diamonds_received, f"stars_payment_{stars_amount}")
        
        # Уведомляем пользователя
        user_data = get_user(user_id)
        current_balance = user_data[2] if user_data else 0
        
        send_with_image(
            user_id,
            f"✅ <b>ОПЛАТА УСПЕШНО ПРИНЯТА!</b>\n\n"
            f"💎 <b>На ваш баланс зачислено:</b> +{diamonds_received} алмазов\n"
            f"⭐ <b>Оплачено:</b> {stars_amount} Telegram Stars\n"
            f"💰 <b>Новый баланс:</b> {current_balance}💎\n\n"
            f"Спасибо за покупку! Приятной игры! 🎰",
            "profile.jpg"
        )
        
        logger.info(f"Stars payment processed for user {user_id}: {stars_amount} stars = {diamonds_received} diamonds")
        
    except Exception as e:
        logger.error(f"Error processing successful payment: {e}")
        try:
            bot.send_message(message.from_user.id, "❌ Произошла ошибка при обработке платежа. Обратитесь к администратору.")
        except:
            pass

# ========== КОЛБЭКИ ==========

@bot.callback_query_handler(func=lambda call: True)
@callback_rate_limit(seconds=RATE_LIMIT_SECONDS)
def callback_handler(call):
    uid = call.from_user.id
    
    try:
        # ПРОВЕРКА ПОДПИСКИ
        if call.data == "check_subscription":
            subscribed, channel_username, channel_name = check_subscription(uid)
            if subscribed:
                bot.answer_callback_query(call.id, "✅ Отлично! Вы подписаны на все каналы")
                bot.delete_message(call.message.chat.id, call.message.message_id)
                # Показываем главное меню
                send_with_image(
                    uid,
                    "🎉 <b>Добро пожаловать в DARKCASE!</b>\n\n"
                    "Теперь вы можете пользоваться всеми функциями бота.",
                    "welcome.jpg",
                    main_keyboard(is_admin(uid))
                )
            else:
                bot.answer_callback_query(
                    call.id,
                    f"❌ Вы не подписан на канал {channel_name}",
                    show_alert=True
                )
            return
        
        # Проверка подписки для всех остальных действий
        check_result = check_whitelist_and_subscription(uid)
        if not check_result[0]:
            if check_result[1] == "subscription":
                channel_username, channel_name = check_result[2], check_result[3]
                sponsors = get_sponsor_channels_cached()
                
                text = f"📺 <b>Для использования бота необходимо подписаться на наш канал:</b>\n\n"
                for sp_username, sp_name in sponsors:
                    text += f"• {sp_name} - @{sp_username[1:] if sp_username.startswith('@') else sp_username}\n"
                
                text += f"\nПосле подписки нажмите кнопку '✅ Я подписался'"
                
                safe_edit_message_text(
                    bot,
                    text,
                    call.message.chat.id,
                    call.message.message_id,
                    reply_markup=sponsors_keyboard(sponsors)
                )
            return
        
        user_data = get_user(uid)
        
        if not user_data:
            bot.answer_callback_query(call.id, "❌ Сначала напишите /start")
            return
        
        # ПОПОЛНЕНИЕ: ВЫБОР СПОСОБА
        if call.data == "payment_stars":
            text = """
<b>⭐ ПОПОЛНЕНИЕ TELEGRAM STARS</b>

💎 <b>Курс:</b> 1 Telegram Star = 9 алмазов

🎁 <b>Популярные пакеты:</b>
• ⭐ 1 звезда = 9💎
• ⭐ 10 звезд = 90💎
• ⭐ 50 звезд = 450💎
• ⭐ 100 звезд = 900💎
• ⭐ 200 звезд = 1800💎
• ⭐ 500 звезд = 4500💎
• ⭐ 1000 звезд = 9000💎

📝 Выберите готовый пакет или введите свою сумму.

💡 После оплаты алмазы начисляются автоматически!
"""
            safe_edit_message_text(
                bot,
                text,
                call.message.chat.id,
                call.message.message_id,
                reply_markup=buy_stars_keyboard()
            )
        
        elif call.data == "payment_cryptobot":
            text = """
<b>🤖 ПОПОЛНЕНИЕ CRYPTOBOT</b>

💎 <b>Курс:</b> 100💎 = 0.32$

Выберите пакет алмазов для покупки:

После выбора пакета вы будете перенаправлены на страницу оплаты CryptoBot (@send).

Поддерживаемые криптовалюты:
• USDT (TRC20)
• TON
• SOL
• BTC
• ETH
"""
            safe_edit_message_text(
                bot,
                text,
                call.message.chat.id,
                call.message.message_id,
                reply_markup=buy_cryptobot_keyboard()
            )
        
        # ПОПОЛНЕНИЕ ЗВЕЗДАМИ: ГОТОВЫЕ ПАКЕТЫ
        elif call.data.startswith("stars_"):
            stars_packages = {
                "stars_1": 1,
                "stars_10": 10,
                "stars_50": 50,
                "stars_100": 100,
                "stars_200": 200,
                "stars_500": 500,
                "stars_1000": 1000
            }
            
            if call.data == "stars_custom":
                # Запрос пользовательской суммы
                msg = bot.send_message(
                    uid,
                    "📝 <b>ВВЕДИТЕ КОЛИЧЕСТВО ЗВЕЗД</b>\n\n"
                    "Отправьте число от 1 до 1000:\n\n"
                    "💎 <b>Курс:</b> 1 Telegram Star = 9 алмазов"
                )
                bot.register_next_step_handler(msg, process_custom_stars_amount)
                bot.answer_callback_query(call.id)
                return
            
            if call.data in stars_packages:
                stars_amount = stars_packages[call.data]
                diamonds_amount = stars_amount * 9  # Курс: 1 звезда = 9 алмазов
                
                # Создаем счет на оплату
                success = create_stars_invoice(uid, stars_amount, diamonds_amount)
                if success:
                    bot.answer_callback_query(call.id, "✅ Счет на оплату создан")
                else:
                    bot.answer_callback_query(call.id, "❌ Ошибка создания счета")
        
        # ОБМЕН АЛМАЗОВ НА TELEGRAM STARS ПОДАРКИ
        elif call.data.startswith("exchange_"):
            exchange_type = call.data.replace("exchange_", "")
            
            from config import EXCHANGE_RATES
            if exchange_type in EXCHANGE_RATES:
                gift_info = EXCHANGE_RATES[exchange_type]
                stars_amount = gift_info["stars"]
                diamonds_cost = gift_info["diamonds"]
                gift_name = gift_info["name"]
                gift_emoji = gift_info["emoji"]
                
                # Проверяем баланс
                if user_data[2] < diamonds_cost:
                    bot.answer_callback_query(
                        call.id,
                        f"❌ Недостаточно алмазов!\nНужно: {diamonds_cost}💎\nУ вас: {user_data[2]}💎",
                        show_alert=True
                    )
                    return
                
                # Показываем подтверждение
                confirm_text = f"""
<b>🔄 ПОДТВЕРЖДЕНИЕ ОБМЕНА</b>

📋 <b>Детали обмена:</b>
• Вы получаете: {gift_emoji} {gift_name}
• Стоимость: {diamonds_cost}💎
• Эквивалент: ⭐ {stars_amount} Telegram Stars
• Ваш баланс: {user_data[2]}💎 → {user_data[2] - diamonds_cost}💎

⚠️ <b>Внимание!</b>
После подтверждения с вашего баланса спишутся {diamonds_cost}💎.
Администратор вручную отправит вам Telegram Stars подарок.
Время обработки: 5-30 минут.

Подтверждаете обмен?
"""
                safe_edit_message_text(
                    bot,
                    confirm_text,
                    call.message.chat.id,
                    call.message.message_id,
                    reply_markup=confirm_exchange_keyboard(exchange_type)
                )
        
        # ПОДТВЕРЖДЕНИЕ ОБМЕНА
        elif call.data.startswith("confirm_exchange_"):
            exchange_type = call.data.replace("confirm_exchange_", "")
            
            from config import EXCHANGE_RATES
            if exchange_type in EXCHANGE_RATES:
                gift_info = EXCHANGE_RATES[exchange_type]
                stars_amount = gift_info["stars"]
                diamonds_cost = gift_info["diamonds"]
                gift_name = gift_info["name"]
                gift_emoji = gift_info["emoji"]
                
                # Проверяем баланс еще раз
                if user_data[2] < diamonds_cost:
                    bot.answer_callback_query(call.id, "❌ Недостаточно алмазов!")
                    return
                
                # Списываем алмазы
                update_balance(uid, -diamonds_cost, f"exchange_{exchange_type}")
                
                # Создаем заявку на обмен
                username = user_data[1] or f"ID {uid}"
                request_id = create_exchange_request(
                    uid, username, stars_amount, gift_name, gift_emoji, diamonds_cost
                )
                
                # Уведомляем пользователя
                bot.answer_callback_query(call.id, "✅ Заявка создана!")
                
                safe_edit_message_text(
                    bot,
                    f"✅ <b>ЗАЯВКА НА ОБМЕН СОЗДАНА!</b>\n\n"
                    f"📋 <b>Детали заявки:</b>\n"
                    f"• ID заявки: #{request_id}\n"
                    f"• Вы получаете: {gift_emoji} {gift_name}\n"
                    f"• Стоимость: {diamonds_cost}💎\n"
                    f"• Эквивалент: ⭐ {stars_amount} Telegram Stars\n"
                    f"• Новый баланс: {user_data[2] - diamonds_cost}💎\n\n"
                    f"⏱ <b>Статус:</b> Ожидание обработки администратором\n"
                    f"💡 Обычно обработка занимает 5-30 минут.\n"
                    f"Вы получите уведомление когда заявка будет выполнена.",
                    call.message.chat.id,
                    call.message.message_id
                )
                
                # Уведомляем администраторов с кнопками
                notify_admins_about_exchange_immediate(request_id, uid, username, stars_amount, gift_name, gift_emoji, diamonds_cost)
                
                logger.info(f"User {uid} created exchange request #{request_id}: {exchange_type}")
        
        # ОТМЕНА ОБМЕНА
        elif call.data == "cancel_exchange":
            safe_edit_message_text(
                bot,
                "❌ <b>ОБМЕН ОТМЕНЕН</b>\n\n"
                "Вы можете выбрать другой подарок или вернуться в главное меню.",
                call.message.chat.id,
                call.message.message_id,
                reply_markup=exchange_menu_keyboard()
            )
        
        # СУНДУКИ: ВЫБОР КАТЕГОРИИ
        elif call.data == "game_cases":
            free_cases = user_data[3]
            events = check_event()
            event_text = ""
            if events:
                event_text = "\n\n<b>🎪 Активные ивенты:</b>\n"
                for event in events:
                    event_text += f"• {event.get('name')}\n"
            
            bot_username = bot.get_me().username
            cases_text = f"""
<b>🎁 Выберите сундук</b>

У вас: <b>{free_cases}</b> деревянных сундуков{event_text}

💎 <b>Доступные сундуки:</b>
• 🪵 Деревянный - 10💎 (бесплатно каждые 24ч)
• ⚙️ Железный - 25💎
• 💰 Золотой - 50💎
• 💎 Алмазный - 150💎
• 🪨 Незеритовый - 500💎

💡 Пригласи друга и получи +1 деревянный сундук!
🔗 Ссылка: https://t.me/{bot_username}?start={uid}
"""
            safe_edit_message_text(
                bot,
                cases_text,
                call.message.chat.id,
                call.message.message_id,
                reply_markup=cases_keyboard(free_cases)
            )
        
        elif call.data == "game_minigames":
            safe_edit_message_text(
                bot,
                "<b>🎮 Выберите игру</b>\n\n"
                "Минимальная ставка: <b>10💎</b>\n"
                "Баланс: <b>{}💎</b>".format(user_data[2]),
                call.message.chat.id,
                call.message.message_id,
                reply_markup=games_keyboard()
            )
        
        elif call.data == "back_games_menu":
            safe_edit_message_text(
                bot,
                "<b>🎮 Выберите категорию</b>\n\n"
                "Выберите что вас интересует:",
                call.message.chat.id,
                call.message.message_id,
                reply_markup=games_menu_keyboard()
            )
        
        # ПРОФИЛЬ: СТАТИСТИКА
        elif call.data == "profile_stats":
            stats_text = format_stats(user_data)
            safe_edit_message_text(
                bot,
                stats_text,
                call.message.chat.id,
                call.message.message_id,
                reply_markup=profile_keyboard()
            )
        
        # ПРОФИЛЬ: УРОВНИ
        elif call.data == "levels_info":
            level_info = get_user_level(uid)
            level_text = format_level_info(level_info, user_data)
            safe_edit_message_text(
                bot,
                level_text,
                call.message.chat.id,
                call.message.message_id,
                reply_markup=profile_keyboard()
            )
        
        # ПРОФИЛЬ: АКТИВНОСТЬ
        elif call.data == "activity_info":
            daily_info = get_daily_info(uid)
            streak_days = daily_info[0] if daily_info else 0
            activity_data = get_user_activity(uid)
            
            if activity_data:
                activity_text, can_claim_streak, can_claim_first_game, streak_bonus, first_game_bonus = format_activity_info(activity_data, streak_days)
                safe_edit_message_text(
                    bot,
                    activity_text,
                    call.message.chat.id,
                    call.message.message_id,
                    reply_markup=profile_keyboard()
                )
        
        # ПРОФИЛЬ: ИСТОРИЯ ПОКУПОК
        elif call.data == "payment_history":
            # Показываем историю покупок
            text = "<b>💳 ИСТОРИЯ ПОКУПОК</b>\n\n"
            
            # Telegram Stars платежи
            stars_payments = get_user_stars_payments(uid, 5)
            if stars_payments:
                text += "<b>⭐ Telegram Stars:</b>\n"
                for payment in stars_payments:
                    stars_amount, diamonds_received, status, created_at = payment
                    time_str = time.strftime('%d.%m.%Y %H:%M', time.localtime(created_at))
                    text += f"• {time_str}: {stars_amount}⭐ → {diamonds_received}💎 ({status})\n"
                text += "\n"
            
            # CryptoBot платежи
            crypto_payments = get_user_payments(uid, 5)
            if crypto_payments:
                text += "<b>🤖 CryptoBot:</b>\n"
                for payment in crypto_payments:
                    amount, status, created_at = payment
                    time_str = time.strftime('%d.%m.%Y %H:%M', time.localtime(created_at))
                    text += f"• {time_str}: {amount}💎 ({status})\n"
            
            if not stars_payments and not crypto_payments:
                text += "У вас еще нет покупок."
            
            safe_edit_message_text(
                bot,
                text,
                call.message.chat.id,
                call.message.message_id,
                reply_markup=profile_keyboard()
            )
        
        # ПРОФИЛЬ: ВВОД ПРОМОКОДА
        elif call.data == "enter_promo":
            msg = bot.send_message(
                uid,
                "🎫 <b>ВВЕДИТЕ ПРОМОКОД</b>\n\n"
                "Отправьте промокод для получения награды:"
            )
            bot.register_next_step_handler(msg, process_promo_code)
            bot.answer_callback_query(call.id)
        
        # ТОПЫ
        elif call.data == "top_balance":
            from database import get_top_balance
            top_users = get_top_balance(10)
            
            text = "🏆 <b>ТОП ПО БАЛАНСУ</b>\n\n"
            for i, (username, balance) in enumerate(top_users, 1):
                text += f"{i}. @{username or 'Неизвестно'} - {balance}💎\n"
            
            safe_edit_message_text(bot, text, call.message.chat.id, call.message.message_id, reply_markup=tops_keyboard())
        
        elif call.data == "top_refs":
            from database import get_top_refs
            top_users = get_top_refs(10)
            
            text = "👥 <b>ТОП ПО РЕФЕРАЛАМ</b>\n\n"
            for i, (username, refs) in enumerate(top_users, 1):
                text += f"{i}. @{username or 'Неизвестно'} - {refs} реф.\n"
            
            safe_edit_message_text(bot, text, call.message.chat.id, call.message.message_id, reply_markup=tops_keyboard())
        
        elif call.data == "top_wins":
            from database import get_top_players
            top_users = get_top_players(10)
            
            text = "🏆 <b>ТОП ПО ПОБЕДАМ</b>\n\n"
            for i, (username, wins) in enumerate(top_users, 1):
                text += f"{i}. @{username or 'Неизвестно'} - {wins} побед\n"
            
            safe_edit_message_text(bot, text, call.message.chat.id, call.message.message_id, reply_markup=tops_keyboard())
        
        elif call.data == "top_levels":
            from database import get_top_levels
            top_users = get_top_levels(10)
            
            text = "⭐ <b>ТОП ПО УРОВНЯМ</b>\n\n"
            for i, (username, level, total_exp) in enumerate(top_users, 1):
                text += f"{i}. @{username or 'Неизвестно'} - Уровень {level} ({total_exp} опыта)\n"
            
            safe_edit_message_text(bot, text, call.message.chat.id, call.message.message_id, reply_markup=tops_keyboard())
        
        # ЗАДАНИЯ
        elif call.data == "my_quests":
            from database import get_weekly_quests
            from utils import format_weekly_quests
            
            quests = get_weekly_quests(uid)
            text = format_weekly_quests(quests)
            safe_edit_message_text(bot, text, call.message.chat.id, call.message.message_id, reply_markup=weekly_quests_keyboard())
        
        elif call.data == "quest_rewards":
            text = """
<b>🏆 НАГРАДЫ ЗА ЗАДАНИЯ</b>

🎁 <b>Награды за выполнение заданий:</b>

• 📦 Открыть сундуки - 10💎
• 🏆 Победить в играх - 8💎
• 👥 Пригласить друзей - 15💎
• 💎 Потратить алмазы - 10💎
• 📅 Ежедневный вход - 15💎
• 🎰 Играть в слоты - 5💎
• 🃏 Играть в блэкджек - 7💎

💡 <b>Как получить награды:</b>
1. Выполните задание
2. Нажмите кнопку "Забрать награду"
3. Алмазы будут зачислены на ваш баланс

🎯 <b>Задания обновляются каждую неделю!</b>
"""
            safe_edit_message_text(bot, text, call.message.chat.id, call.message.message_id, reply_markup=weekly_quests_keyboard())
        
        elif call.data == "quest_progress":
            from database import get_weekly_quests
            quests = get_weekly_quests(uid)
            
            completed = 0
            total_reward = 0
            for quest_data in quests:
                quest_id, progress, completed_flag, claimed, goal = quest_data
                if completed_flag or progress >= goal:
                    completed += 1
            
            text = f"""
<b>📊 ПРОГРЕСС ЗАДАНИЙ</b>

📈 <b>Статистика:</b>
├ Выполнено: {completed}/{len(quests)}
└ Прогресс: {(completed/len(quests)*100):.1f}%

💡 <b>Советы:</b>
• Открывайте сундуки для выполнения задания "Открыть сундуки"
• Играйте в игры для заданий "Победить в играх"
• Приглашайте друзей по реф.ссылке
• Тратьте алмазы в играх
• Заходите каждый день для стрика

🎯 <b>Цель:</b> Выполнить все задания за неделю!
"""
            safe_edit_message_text(bot, text, call.message.chat.id, call.message.message_id, reply_markup=weekly_quests_keyboard())
        
        # РОЗЫГРЫШ
        elif call.data == "buy_lottery_ticket":
            from config import LOTTERY_TICKET_PRICE
            from database import buy_lottery_ticket
            
            if user_data[2] < LOTTERY_TICKET_PRICE:
                bot.answer_callback_query(call.id, "❌ Недостаточно алмазов!")
                return
            
            draw_date = Lottery.get_next_draw_date()
            ticket_number = buy_lottery_ticket(uid, draw_date)
            update_balance(uid, -LOTTERY_TICKET_PRICE, "lottery_ticket")
            
            bot.answer_callback_query(call.id, f"✅ Билет #{ticket_number} куплен!")
            
            # Обновляем информацию о розыгрыше
            lottery_stats = get_lottery_stats(draw_date)
            ticket_count = lottery_stats[1] if lottery_stats else 0
            jackpot = Lottery.get_current_jackpot(ticket_count)
            user_tickets = get_user_tickets(uid, draw_date)
            user_tickets_count = len(user_tickets)
            
            lottery_text = format_lottery_info(draw_date, ticket_count, user_tickets_count, jackpot)
            safe_edit_message_text(
                bot,
                lottery_text,
                call.message.chat.id,
                call.message.message_id,
                reply_markup=lottery_keyboard(draw_date, user_tickets_count)
            )
        
        elif call.data == "my_lottery_tickets":
            draw_date = Lottery.get_next_draw_date()
            user_tickets = get_user_tickets(uid, draw_date)
            user_tickets_count = len(user_tickets)
            
            if user_tickets_count == 0:
                text = "🎟 <b>ВАШИ БИЛЕТЫ</b>\n\n"
                text += "У вас нет билетов на текущий розыгрыш.\n\n"
                text += "🎫 Купите билет, чтобы участвовать в розыгрыше!"
                safe_edit_message_text(bot, text, call.message.chat.id, call.message.message_id, reply_markup=lottery_keyboard(draw_date, 0))
            else:
                text = f"🎟 <b>ВАШИ БИЛЕТЫ ({user_tickets_count})</b>\n\n"
                text += f"🎰 Розыгрыш: {draw_date}\n\n"
                text += f"🎫 Ваши билеты: "
                text += ", ".join([f"#{ticket}" for ticket in user_tickets[:20]])
                if user_tickets_count > 20:
                    text += f" и еще {user_tickets_count - 20}..."
                
                text += f"\n\n🎯 <b>Шанс на победу:</b> 1 к {get_lottery_stats(draw_date)[1] if get_lottery_stats(draw_date) else 1}"
                
                safe_edit_message_text(bot, text, call.message.chat.id, call.message.message_id, reply_markup=lottery_keyboard(draw_date, user_tickets_count))
        
        elif call.data == "lottery_history":
            from database import get_lottery_history
            from utils import format_lottery_history
            
            history = get_lottery_history(10)
            text = format_lottery_history(history)
            safe_edit_message_text(bot, text, call.message.chat.id, call.message.message_id, reply_markup=lottery_keyboard(Lottery.get_next_draw_date(), 0))
        
        elif call.data == "lottery_jackpot":
            draw_date = Lottery.get_next_draw_date()
            lottery_stats = get_lottery_stats(draw_date)
            ticket_count = lottery_stats[1] if lottery_stats else 0
            jackpot = Lottery.get_current_jackpot(ticket_count)
            
            text = f"""
🏆 <b>ТЕКУЩИЙ ПРИЗОВОЙ ФОНД</b>

💎 <b>Сумма приза:</b> {jackpot}💎

📊 <b>Статистика:</b>
├ Билетов куплено: {ticket_count}
├ Участников: {lottery_stats[0] if lottery_stats else 0}
└ Ваши билеты: {len(get_user_tickets(uid, draw_date))}

🎯 <b>Ваш шанс на победу:</b> 1 к {ticket_count if ticket_count > 0 else 1}

💡 <b>Чем больше билетов куплено - тем больше приз!</b>
"""
            safe_edit_message_text(bot, text, call.message.chat.id, call.message.message_id, reply_markup=lottery_keyboard(draw_date, len(get_user_tickets(uid, draw_date))))
        
        # СУНДУКИ (ПЛАТНЫЕ)
        elif call.data in ["c10", "c25", "c50", "c150", "c500"]:
            from models import CASES
            
            if call.data in CASES:
                case = CASES[call.data]
                
                if user_data[2] < case.price:
                    bot.answer_callback_query(call.id, "❌ Недостаточно алмазов!")
                    return
                
                # Списываем стоимость
                update_balance(uid, -case.price, f"case_{call.data}")
                
                # Анимация открытия
                animate_case_opening(bot, call.message.chat.id, call.message.message_id, case.emoji)
                time.sleep(1)
                
                # Открываем сундук
                reward = case.open()
                
                # Начисляем выигрыш
                update_balance(uid, reward, f"case_reward_{call.data}")
                
                # Обновляем статистику
                update_case_stats(uid, reward > 0, reward)
                
                # Добавляем опыт за открытие сундука
                add_exp(uid, 10)
                
                # Определяем, победил ли пользователь (выигрыш >= стоимости)
                is_win = reward >= case.price
                
                # Показываем результат с правильным сообщением
                result_text = f"""
<b>{case.emoji} {case.name} сундук</b>

💰 <b>Стоимость:</b> {case.price}💎
🎁 <b>Выпало:</b> {reward}💎
{"✅" if is_win else "❌"} <b>Результат:</b> {"ПОБЕДА!" if is_win else "Вы выиграли меньше стоимости сундука"}
"""
                
                # Добавляем сообщение о более дорогом кейсе для дешевых кейсов
                if call.data in ["c10", "c25", "c50"]:
                    next_case_msg = ""
                    if call.data == "c10":
                        next_case_msg = "\n💡 В железном сундуке (25💎) вы можете выиграть до 50💎!"
                    elif call.data == "c25":
                        next_case_msg = "\n💡 В золотом сундуке (50💎) вы можете выиграть до 100💎!"
                    elif call.data == "c50":
                        next_case_msg = "\n💡 В алмазном сундуке (150💎) вы можете выиграть до 250💎!"
                    
                    result_text += next_case_msg
                
                result_text += f"\n\n💎 <b>Баланс:</b> {user_data[2] - case.price + reward}💎"
                
                safe_edit_message_text(
                    bot,
                    result_text,
                    call.message.chat.id,
                    call.message.message_id,
                    reply_markup=cases_keyboard(user_data[3])
                )
        
        # СУНДУКИ (БЕСПЛАТНЫЙ)
        elif call.data == "free_case":
            if user_data[3] > 0:
                # Анимация открытия
                animate_case_opening(bot, call.message.chat.id, call.message.message_id, "🪵")
                time.sleep(1)
                
                # Открываем бесплатный сундук
                reward = open_free_case()
                update_balance(uid, reward, "free_case")
                use_free_case(uid)
                update_case_stats(uid, reward > 0, reward)
                
                # Добавляем опыт
                add_exp(uid, 5)
                
                # Для бесплатного сундука всегда показываем "ПОБЕДА!"
                result_text = f"""
<b>🪵 Бесплатный сундук</b>

🎁 <b>Выпало:</b> {reward}💎
✅ <b>Результат:</b> ПОБЕДА!
"""
                
                # Добавляем сообщение о более дорогом кейсе
                result_text += "\n💡 В железном сундуке (25💎) вы можете выиграть до 50💎!"
                
                result_text += f"\n\n💎 <b>Баланс:</b> {user_data[2] + reward}💎"
                
                safe_edit_message_text(
                    bot,
                    result_text,
                    call.message.chat.id,
                    call.message.message_id,
                    reply_markup=cases_keyboard(user_data[3] - 1)
                )
            else:
                bot.answer_callback_query(call.id, "❌ Нет бесплатных сундуков")
        
        # ИГРЫ: КАМЕНЬ-НОЖНИЦЫ-БУМАГА
        elif call.data == "game_sps":
            safe_edit_message_text(
                bot,
                f"✂️ <b>КАМЕНЬ-НОЖНИЦЫ-БУМАГА</b>\n\n"
                f"💰 <b>Ваш баланс:</b> {user_data[2]}💎\n"
                f"🎯 <b>Правила:</b>\n"
                f"• Камень бьет ножницы\n"
                f"• Ножницы бьют бумагу\n"
                f"• Бумага бьет камень\n"
                f"💰 <b>Выигрыш:</b> x2 от ставки\n\n"
                f"Выберите ваш ход:",
                call.message.chat.id,
                call.message.message_id,
                reply_markup=sps_keyboard()
            )
        
        # ИГРЫ: ВЫБОР ХОДА КНБ
        elif call.data in ["sps_stone", "sps_paper", "sps_scissors"]:
            choice_map = {
                "sps_stone": "stone",
                "sps_paper": "paper",
                "sps_scissors": "scissors"
            }
            choice = choice_map[call.data]
            
            choice_emoji = {
                "stone": "🪨",
                "paper": "📄",
                "scissors": "✂️"
            }
            
            text = f"""
✂️ <b>КАМЕНЬ-НОЖНИЦЫ-БУМАГА</b>

🎯 <b>Ваш выбор:</b> {choice_emoji[choice]}

💰 <b>Ваш баланс:</b> {user_data[2]}💎

Выберите сумму ставки:
"""
            safe_edit_message_text(bot, text, call.message.chat.id, call.message.message_id, reply_markup=bet_keyboard(f"sps_{choice}"))
        
        # ИСПРАВЛЕННАЯ ИГРА КНБ: ОБРАБОТКА СТАВОК
        elif call.data.startswith("bet_sps_"):
            try:
                # Разбираем callback data
                parts = call.data.split("_")
                if len(parts) == 4:
                    # Формат: bet_sps_paper_25
                    choice = parts[2]  # paper, stone, scissors
                    bet_amount = int(parts[3])
                    
                    if user_data[2] < bet_amount:
                        bot.answer_callback_query(call.id, "❌ Недостаточно алмазов!")
                        return
                    
                    # Играем в КНБ
                    win, amount_won, bot_choice = StonePaperScissors.play(bet_amount, choice)
                    
                    choice_emoji = {
                        "stone": "🪨",
                        "paper": "📄",
                        "scissors": "✂️"
                    }
                    
                    if win is None:  # Ничья
                        update_balance(uid, 0, "sps_draw")
                        result_text = f"⚖️ <b>НИЧЬЯ!</b>\n\nВаш выбор: {choice_emoji[choice]}\nВыбор бота: {choice_emoji[bot_choice]}\nСтавка возвращена\nНовый баланс: <b>{user_data[2]}💎</b>"
                    elif win:
                        update_balance(uid, amount_won - bet_amount, "sps_win")
                        update_game_stats(uid, True)
                        result_text = f"✅ <b>ПОБЕДА!</b>\n\nВаш выбор: {choice_emoji[choice]}\nВыбор бота: {choice_emoji[bot_choice]}\nВы выиграли: <b>{amount_won - bet_amount}💎</b>\nНовый баланс: <b>{user_data[2] + amount_won - bet_amount}💎</b>"
                    else:
                        update_balance(uid, -bet_amount, "sps_loss")
                        update_game_stats(uid, False)
                        result_text = f"❌ <b>ПОПРОБУЙТЕ ЕЩЕ</b>\n\nВаш выбор: {choice_emoji[choice]}\nВыбор бота: {choice_emoji[bot_choice]}\nВы проиграли: <b>{bet_amount}💎</b>\nНовый баланс: <b>{user_data[2] - bet_amount}💎</b>"
                    
                    # Добавляем опыт за игру
                    add_exp(uid, 5)
                    
                    safe_edit_message_text(bot, result_text, call.message.chat.id, call.message.message_id, reply_markup=sps_keyboard())
                
            except (ValueError, IndexError) as e:
                logger.error(f"Error in KNB game: {e}")
                bot.answer_callback_query(call.id, "❌ Ошибка обработки игры")
        
        # ИГРЫ: РУЛЕТКА
        elif call.data == "game_roulette":
            safe_edit_message_text(
                bot,
                f"🎡 <b>РУЛЕТКА</b>\n\n"
                f"💰 <b>Ваш баланс:</b> {user_data[2]}💎\n"
                f"🎯 <b>Шанс на победу:</b> 20%\n"
                f"💰 <b>Награда:</b> x2 от ставки\n\n"
                f"Выберите ставку:",
                call.message.chat.id,
                call.message.message_id,
                reply_markup=bet_keyboard("roulette")
            )
        
        elif call.data == "game_dice":
            safe_edit_message_text(
                bot,
                f"🎲 <b>КУБИК</b>\n\n"
                f"💰 <b>Ваш баланс:</b> {user_data[2]}💎\n"
                f"🎯 <b>Правила:</b>\n"
                f"• Выпало 6: награда x4\n"
                f"• Выпало 1: возврат ставки\n"
                f"• Другое: попробуйте еще\n\n"
                f"Выберите ставку:",
                call.message.chat.id,
                call.message.message_id,
                reply_markup=bet_keyboard("dice")
            )
        
        # ИГРЫ "МИНЫ" УДАЛЕНЫ
        elif call.data == "game_mines":
            bot.answer_callback_query(call.id, "❌ Игра 'Мины' временно отключена")
            return
        
        elif call.data == "game_slot":
            safe_edit_message_text(
                bot,
                f"🎰 <b>СЛОТ-МАШИНА</b>\n\n"
                f"💰 <b>Ваш баланс:</b> {user_data[2]}💎\n"
                f"🎯 <b>Выигрышные комбинации:</b>\n"
                f"• 3x 7️⃣: x8\n"
                f"• 3x 💎: x6\n"
                f"• 3x ⭐: x4\n"
                f"• 3x 🔔: x3\n"
                f"• 3 одинаковых: x2\n"
                f"• 2 одинаковых: x1.1-1.3\n\n"
                f"Выберите ставку:",
                call.message.chat.id,
                call.message.message_id,
                reply_markup=slot_bet_keyboard()
            )
        
        elif call.data == "game_blackjack":
            safe_edit_message_text(
                bot,
                f"🃏 <b>БЛЭКДЖЕК</b>\n\n"
                f"💰 <b>Ваш баланс:</b> {user_data[2]}💎\n"
                f"🎯 <b>Правила:</b>\n"
                f"• Цель: набрать больше очков чем дилер, но не больше 21\n"
                f"• Карты: 1-11 очков\n"
                f"• Награда: x2 от ставки\n"
                f"• Ничья: возврат ставки\n\n"
                f"Выберите ставку:",
                call.message.chat.id,
                call.message.message_id,
                reply_markup=blackjack_bet_keyboard()
            )
        
        elif call.data == "events":
            events = check_event()
            if events:
                text = "🎪 <b>АКТИВНЫЕ ИВЕНТЫ</b>\n\n"
                for event in events:
                    text += f"• <b>{event.get('name')}</b>\n"
                    text += f"  {event.get('bonus')}\n\n"
            else:
                text = "🎪 <b>АКТИВНЫЕ ИВЕНТЫ</b>\n\n"
                text += "В данный момент нет активных ивентов.\n\n"
                text += "💡 Следите за обновлениями!"
            
            safe_edit_message_text(bot, text, call.message.chat.id, call.message.message_id, reply_markup=games_keyboard())
        
        # ИГРЫ: СТАВКИ (кроме КНБ)
        elif call.data.startswith("bet_"):
            parts = call.data.split("_")
            if len(parts) >= 3:
                game_type = parts[1]
                bet_amount = int(parts[2])
                
                if user_data[2] < bet_amount:
                    bot.answer_callback_query(call.id, "❌ Недостаточно алмазов!")
                    return
                
                # Обработка разных игр (кроме КНБ, который обрабатывается отдельно)
                if game_type == "roulette":
                    win, amount_won = Roulette.spin(bet_amount)
                    
                    if win:
                        update_balance(uid, amount_won, "roulette_win")
                        update_game_stats(uid, True)
                        result_text = f"✅ <b>ПОБЕДА!</b>\n\nВы выиграли: <b>{amount_won}💎</b>\nНовый баланс: <b>{user_data[2] + amount_won - bet_amount}💎</b>"
                    else:
                        update_balance(uid, -bet_amount, "roulette_loss")
                        update_game_stats(uid, False)
                        result_text = f"❌ <b>ПОПРОБУЙТЕ ЕЩЕ</b>\n\nВы не выиграли: <b>{bet_amount}💎</b>\nНовый баланс: <b>{user_data[2] - bet_amount}💎</b>"
                    
                    safe_edit_message_text(bot, result_text, call.message.chat.id, call.message.message_id, reply_markup=bet_keyboard("roulette"))
                
                elif game_type == "dice":
                    win, amount_won, roll = Dice.roll(bet_amount)
                    
                    if win is None:  # Ничья
                        result_text = f"⚖️ <b>НИЧЬЯ!</b>\n\nВыпало: <b>{roll}</b>\nСтавка возвращена\nНовый баланс: <b>{user_data[2]}💎</b>"
                    elif win:
                        update_balance(uid, amount_won - bet_amount, "dice_win")
                        update_game_stats(uid, True)
                        result_text = f"✅ <b>ПОБЕДА!</b>\n\nВыпало: <b>{roll}</b>\nВы выиграли: <b>{amount_won - bet_amount}💎</b>\nНовый баланс: <b>{user_data[2] + amount_won - bet_amount}💎</b>"
                    else:
                        update_balance(uid, -bet_amount, "dice_loss")
                        update_game_stats(uid, False)
                        result_text = f"❌ <b>ПОПРОБУЙТЕ ЕЩЕ</b>\n\nВыпало: <b>{roll}</b>\nВы не выиграли: <b>{bet_amount}💎</b>\nНовый баланс: <b>{user_data[2] - bet_amount}💎</b>"
                    
                    safe_edit_message_text(bot, result_text, call.message.chat.id, call.message.message_id, reply_markup=bet_keyboard("dice"))
                
                elif game_type == "slot":
                    # Анимация слотов
                    animate_slot_spin(bot, call.message.chat.id, call.message.message_id)
                    time.sleep(1)
                    
                    win, amount_won, result = SlotMachine.spin(bet_amount)
                    
                    if win:
                        update_balance(uid, amount_won - bet_amount, "slot_win")
                        update_game_stats(uid, True)
                        result_text = f"✅ <b>ПОБЕДА!</b>\n\nРезультат: {' '.join(result)}\nВы выиграли: <b>{amount_won - bet_amount}💎</b>\nНовый баланс: <b>{user_data[2] + amount_won - bet_amount}💎</b>"
                    else:
                        update_balance(uid, -bet_amount, "slot_loss")
                        update_game_stats(uid, False)
                        result_text = f"❌ <b>ПОПРОБУЙТЕ ЕЩЕ</b>\n\nРезультат: {' '.join(result)}\nВы не выиграли: <b>{bet_amount}💎</b>\nНовый баланс: <b>{user_data[2] - bet_amount}💎</b>"
                    
                    safe_edit_message_text(bot, result_text, call.message.chat.id, call.message.message_id, reply_markup=slot_bet_keyboard())
                
                elif game_type == "blackjack":
                    win, amount_won, cards = BlackJack.play(bet_amount)
                    
                    player_cards, dealer_cards = cards
                    player_sum = sum(player_cards)
                    dealer_sum = sum(dealer_cards)
                    
                    if win is None:  # Ничья
                        result_text = f"⚖️ <b>НИЧЬЯ!</b>\n\nВаши карты: {player_cards} (сумма: {player_sum})\nКарты дилера: {dealer_cards} (сумма: {dealer_sum})\nСтавка возвращена\nНовый баланс: <b>{user_data[2]}💎</b>"
                        update_balance(uid, 0, "blackjack_draw")
                    elif win:
                        update_balance(uid, amount_won - bet_amount, "blackjack_win")
                        update_game_stats(uid, True)
                        result_text = f"✅ <b>ПОБЕДА!</b>\n\nВаши карты: {player_cards} (сумма: {player_sum})\nКарты дилера: {dealer_cards} (сумма: {dealer_sum})\nВы выиграли: <b>{amount_won - bet_amount}💎</b>\nНовый баланс: <b>{user_data[2] + amount_won - bet_amount}💎</b>"
                    else:
                        update_balance(uid, -bet_amount, "blackjack_loss")
                        update_game_stats(uid, False)
                        result_text = f"❌ <b>ПОПРОБУЙТЕ ЕЩЕ</b>\n\nВаши карты: {player_cards} (сумма: {player_sum})\nКарты дилера: {dealer_cards} (сумма: {dealer_sum})\nВы не выиграли: <b>{bet_amount}💎</b>\nНовый баланс: <b>{user_data[2] - bet_amount}💎</b>"
                    
                    safe_edit_message_text(bot, result_text, call.message.chat.id, call.message.message_id, reply_markup=blackjack_bet_keyboard())
                
                # Добавляем опыт за игру
                add_exp(uid, 5)
        
        # ПОКУПКА АЛМАЗОВ ЧЕРЕЗ CRYPTOBOT
        elif call.data.startswith("buy_"):
            try:
                amount = int(call.data.split("_")[1])
                from config import ALMAZ_PACKAGES
                
                if amount in ALMAZ_PACKAGES:
                    price_usd = ALMAZ_PACKAGES[amount]
                    
                    # Создаем счет в CryptoBot
                    invoice_id, pay_url = create_cryptobot_invoice(
                        price_usd,
                        f"Покупка {amount} алмазов"
                    )
                    
                    if invoice_id and pay_url:
                        # Сохраняем платеж в БД
                        create_payment(uid, amount, invoice_id)
                        
                        safe_edit_message_text(
                            bot,
                            f"💎 <b>ПОКУПКА {amount} АЛМАЗОВ</b>\n\n"
                            f"Сумма: <b>{price_usd}$</b>\n"
                            f"Курс: 100💎 = 0.32$\n\n"
                            f"<b>Инструкция:</b>\n"
                            f"1. Нажмите кнопку 'Оплатить'\n"
                            f"2. Оплатите счет криптовалютой\n"
                            f"3. После оплаты алмазы будут зачислены автоматически\n\n"
                            f"Статус: <b>Ожидание оплаты</b>",
                            call.message.chat.id,
                            call.message.message_id,
                            reply_markup=types.InlineKeyboardMarkup().add(
                                types.InlineKeyboardButton("💳 Оплатить", url=pay_url),
                                types.InlineKeyboardButton("🔄 Проверить оплату", callback_data=f"check_payment_{invoice_id}")
                            )
                        )
                    else:
                        bot.answer_callback_query(call.id, "❌ Ошибка создания счета")
                
            except (ValueError, IndexError) as e:
                logger.error(f"Error in buy: {e}")
                bot.answer_callback_query(call.id, "❌ Ошибка обработки запроса")
        
        # ПРОВЕРКА ОПЛАТЫ CRYPTOBOT
        elif call.data.startswith("check_payment_"):
            invoice_id = call.data.split("_")[2]
            payment = get_payment_by_invoice(invoice_id)
            
            if not payment:
                bot.answer_callback_query(call.id, "❌ Платеж не найден")
                return
            
            payment_id, user_id, amount, invoice_id_db, status, created_at, completed_at = payment
            
            if status == 'paid':
                bot.answer_callback_query(call.id, "✅ Платеж уже обработан")
                return
            
            # Проверяем статус в CryptoBot
            invoice_status = check_cryptobot_invoice(invoice_id)
            
            if invoice_status == 'paid':
                # Обновляем статус платежа
                update_payment_status(invoice_id, 'paid')
                
                # Начисляем алмазы
                update_balance(uid, amount, f"cryptobot_payment_{invoice_id}")
                
                safe_edit_message_text(
                    bot,
                    f"✅ <b>ПЛАТЕЖ ОБРАБОТАН!</b>\n\n"
                    f"На ваш баланс зачислено: <b>+{amount}💎</b>\n"
                    f"Новый баланс: <b>{get_user(uid)[2]}💎</b>\n\n"
                    f"Спасибо за покупку!",
                    call.message.chat.id,
                    call.message.message_id
                )
                
                logger.info(f"Payment processed for user {uid}: {amount} алмазов")
            else:
                bot.answer_callback_query(call.id, "⏳ Платеж еще не получен")
        
        # АДМИН ФУНКЦИИ
        elif call.data == "admin_add":
            if not is_admin(uid):
                bot.answer_callback_query(call.id, "❌ Доступ запрещен")
                return
            
            msg = bot.send_message(
                uid,
                "➕ <b>ВЫДАТЬ АЛМАЗЫ</b>\n\n"
                "Введите ID пользователя и количество алмазов через пробел:\n"
                "Например: <code>123456789 100</code>"
            )
            bot.register_next_step_handler(msg, admin_add_balance)
            bot.answer_callback_query(call.id)
        
        elif call.data == "admin_take":
            if not is_admin(uid):
                bot.answer_callback_query(call.id, "❌ Доступ запрещен")
                return
            
            msg = bot.send_message(
                uid,
                "➖ <b>ЗАБРАТЬ АЛМАЗЫ</b>\n\n"
                "Введите ID пользователя и количество алмазов через пробел:\n"
                "Например: <code>123456789 50</code>"
            )
            bot.register_next_step_handler(msg, admin_take_balance)
            bot.answer_callback_query(call.id)
        
        elif call.data == "admin_stats":
            if not is_admin(uid):
                return
            
            from database import get_bot_stats
            stats = get_bot_stats()
            
            if stats:
                total_users, total_balance, total_cases, total_refs, total_wins, total_lottery_paid = stats
                text = f"""
📊 <b>СТАТИСТИКА БОТА</b>

👥 Пользователей: {total_users}
💰 Всего алмазов: {total_balance}💎
📦 Открыто сундуков: {total_cases}
👥 Приглашено: {total_refs}
🏆 Побед: {total_wins}
🎰 Розыгрышей выплачено: {total_lottery_paid or 0}💎
"""
                safe_edit_message_text(bot, text, call.message.chat.id, call.message.message_id, reply_markup=admin_keyboard())
        
        elif call.data == "admin_users":
            if not is_admin(uid):
                bot.answer_callback_query(call.id, "❌ Доступ запрещен")
                return
            
            from database import get_all_users
            users = get_all_users()
            
            if not users:
                text = "👥 <b>СПИСОК ПОЛЬЗОВАТЕЛЕЙ</b>\n\n"
                text += "Пользователей пока нет."
            else:
                text = f"👥 <b>СПИСОК ПОЛЬЗОВАТЕЛЕЙ ({len(users)})</b>\n\n"
                for i, (user_id, username, balance) in enumerate(users[:20], 1):
                    text += f"{i}. @{username or 'Нет'} (ID: {user_id}) - {balance}💎\n"
                
                if len(users) > 20:
                    text += f"\n... и еще {len(users) - 20} пользователей"
            
            safe_edit_message_text(bot, text, call.message.chat.id, call.message.message_id, reply_markup=admin_keyboard())
        
        elif call.data == "admin_broadcast":
            if not is_admin(uid):
                bot.answer_callback_query(call.id, "❌ Доступ запрещен")
                return
            
            msg = bot.send_message(
                uid,
                "📢 <b>РАССЫЛКА</b>\n\n"
                "Введите сообщение для рассылки всем пользователям:\n\n"
                "💡 Можно использовать HTML разметку"
            )
            bot.register_next_step_handler(msg, admin_broadcast_message)
            bot.answer_callback_query(call.id)
        
        elif call.data == "admin_settings":
            if not is_admin(uid):
                bot.answer_callback_query(call.id, "❌ Доступ запрещен")
                return
            
            safe_edit_message_text(
                bot,
                "⚙ <b>НАСТРОЙКИ АДМИНИСТРАТОРА</b>\n\n"
                "Выберите действие:",
                call.message.chat.id,
                call.message.message_id,
                reply_markup=admin_settings_keyboard()
            )
        
        elif call.data == "admin_promocodes":
            if not is_admin(uid):
                bot.answer_callback_query(call.id, "❌ Доступ запрещен")
                return
            
            safe_edit_message_text(
                bot,
                "🎫 <b>УПРАВЛЕНИЕ ПРОМОКОДАМИ</b>\n\n"
                "Выберите действие:",
                call.message.chat.id,
                call.message.message_id,
                reply_markup=admin_promocodes_keyboard()
            )
        
        elif call.data == "admin_create_lottery":
            if not is_admin(uid):
                bot.answer_callback_query(call.id, "❌ Доступ запрещен")
                return
            
            msg = bot.send_message(
                uid,
                "🎰 <b>СОЗДАНИЕ РОЗЫГРЫША</b>\n\n"
                "Введите данные розыгрыша в формате:\n"
                "<code>Название|Приз|Цена билета|Дата окончания (ГГГГ-ММ-ДД)</code>\n\n"
                "Пример:\n"
                "<code>Новогодний розыгрыш|1000|50|2024-12-31</code>"
            )
            bot.register_next_step_handler(msg, admin_create_lottery)
            bot.answer_callback_query(call.id)
        
        elif call.data == "admin_sponsors":
            if not is_admin(uid):
                bot.answer_callback_query(call.id, "❌ Доступ запрещен")
                return
            
            sponsors = get_sponsor_channels_cached()
            
            if not sponsors:
                text = "📺 <b>СПОНСОРСКИЕ КАНАЛЫ</b>\n\n"
                text += "Спонсорские каналы не добавлены."
            else:
                text = "📺 <b>СПОНСОРСКИЕ КАНАЛЫ</b>\n\n"
                for i, (channel_username, channel_name) in enumerate(sponsors, 1):
                    text += f"{i}. {channel_name} - @{channel_username}\n"
            
            safe_edit_message_text(bot, text, call.message.chat.id, call.message.message_id, reply_markup=admin_keyboard())
        
        elif call.data == "admin_exchange_requests":
            if not is_admin(uid):
                bot.answer_callback_query(call.id, "❌ Доступ запрещен")
                return
            
            safe_edit_message_text(
                bot,
                "⭐ <b>УПРАВЛЕНИЕ ЗАЯВКАМИ НА ОБМЕН</b>\n\n"
                "Выберите действие:",
                call.message.chat.id,
                call.message.message_id,
                reply_markup=admin_exchange_requests_keyboard()
            )
        
        elif call.data == "admin_exchange_list":
            if not is_admin(uid):
                bot.answer_callback_query(call.id, "❌ Доступ запрещен")
                return
            
            from database import get_all_exchange_requests
            requests = get_all_exchange_requests(20)
            
            if not requests:
                text = "📋 <b>СПИСОК ЗАЯВОК НА ОБМЕН</b>\n\n"
                text += "Заявок пока нет."
                safe_edit_message_text(bot, text, call.message.chat.id, call.message.message_id, reply_markup=admin_exchange_requests_keyboard())
                return
            
            text = "📋 <b>СПИСОК ЗАЯВОК НА ОБМЕН</b>\n\n"
            for req in requests[:10]:  # Показываем первые 10
                req_id, user_id, username, stars_amount, gift_name, gift_emoji, diamonds_cost, status, admin_id, admin_comment, created_at, completed_at = req
                text += f"<b>#{req_id}</b> - {gift_emoji} {gift_name}\n"
                text += f"Пользователь: @{username} (ID: {user_id})\n"
                text += f"Стоимость: {diamonds_cost}💎 → ⭐ {stars_amount}\n"
                text += f"Статус: {status}\n"
                text += "━━━━━━━━━━━━━━━━\n"
            
            safe_edit_message_text(bot, text, call.message.chat.id, call.message.message_id, reply_markup=admin_exchange_requests_keyboard())
        
        elif call.data == "admin_exchange_pending":
            if not is_admin(uid):
                bot.answer_callback_query(call.id, "❌ Доступ запрещен")
                return
            
            from database import get_pending_exchange_requests
            requests = get_pending_exchange_requests(10)
            
            if not requests:
                text = "✅ <b>ЗАЯВКИ НА ВЫДАЧУ</b>\n\n"
                text += "Нет ожидающих заявок."
                safe_edit_message_text(bot, text, call.message.chat.id, call.message.message_id, reply_markup=admin_exchange_requests_keyboard())
                return
            
            text = "✅ <b>ЗАЯВКИ НА ВЫДАЧУ</b>\n\n"
            for req in requests:
                req_id, user_id, username, stars_amount, gift_name, gift_emoji, diamonds_cost, status, admin_id, admin_comment, created_at, completed_at = req
                text += f"<b>#{req_id}</b> - {gift_emoji} {gift_name}\n"
                text += f"Пользователь: @{username} (ID: {user_id})\n"
                text += f"Стоимость: {diamonds_cost}💎 → ⭐ {stars_amount}\n"
                text += f"Время: {time.strftime('%H:%M %d.%m', time.localtime(created_at))}\n\n"
            
            safe_edit_message_text(bot, text, call.message.chat.id, call.message.message_id, reply_markup=admin_exchange_requests_keyboard())
        
        elif call.data == "admin_exchange_stats":
            if not is_admin(uid):
                bot.answer_callback_query(call.id, "❌ Доступ запрещен")
                return
            
            from database import get_exchange_stats
            stats = get_exchange_stats()
            
            if stats:
                total_requests, completed, pending, rejected, total_stars, total_diamonds = stats
                text = f"""
📊 <b>СТАТИСТИКА ОБМЕНОВ</b>

📋 <b>Заявки:</b>
├ Всего: {total_requests}
├ Выполнено: {completed}
├ Ожидает: {pending}
└ Отклонено: {rejected}

💰 <b>Финансы:</b>
├ Всего звезд: ⭐ {total_stars or 0}
└ Всего алмазов: {total_diamonds or 0}💎

💡 <b>Информация:</b>
• Среднее время обработки: 15-30 минут
• Отклонение заявки: при подозрении на мошенничество
"""
                safe_edit_message_text(bot, text, call.message.chat.id, call.message.message_id, reply_markup=admin_exchange_requests_keyboard())
        
        # ОБРАБОТКА ЗАЯВОК НА ОБМЕН (АДМИН) - НЕПОСРЕДСТВЕННАЯ ОБРАБОТКА
        elif call.data.startswith("admin_exchange_complete_"):
            if not is_admin(uid):
                bot.answer_callback_query(call.id, "❌ Доступ запрещен")
                return
            
            request_id = int(call.data.split("_")[3])
            update_exchange_request_status(request_id, "completed", uid, "Заявка выполнена")
            
            bot.answer_callback_query(call.id, "✅ Заявка отмечена как выполненная")
            
            # Уведомляем пользователя
            request = get_exchange_request(request_id)
            if request:
                req_id, user_id, username, stars_amount, gift_name, gift_emoji, diamonds_cost, status, admin_id, admin_comment, created_at, completed_at = request
                try:
                    bot.send_message(
                        user_id,
                        f"✅ <b>ВАША ЗАЯВКА #{request_id} ВЫПОЛНЕНА!</b>\n\n"
                        f"📋 <b>Детали:</b>\n"
                        f"• Подарок: {gift_emoji} {gift_name}\n"
                        f"• Telegram Stars: ⭐ {stars_amount}\n"
                        f"• Стоимость: {diamonds_cost}💎\n"
                        f"• Администратор: ID {uid}\n\n"
                        f"💡 Telegram Stars подарок должен быть отправлен вам в ближайшее время.\n"
                        f"Если у вас возникли проблемы - обратитесь к администратору."
                    )
                except:
                    pass
            
            # Удаляем сообщение с заявкой
            try:
                bot.delete_message(call.message.chat.id, call.message.message_id)
            except:
                pass
        
        elif call.data.startswith("admin_exchange_reject_"):
            if not is_admin(uid):
                bot.answer_callback_query(call.id, "❌ Доступ запрещен")
                return
            
            request_id = int(call.data.split("_")[3])
            
            # Возвращаем алмазы пользователю
            request = get_exchange_request(request_id)
            if request:
                req_id, user_id, username, stars_amount, gift_name, gift_emoji, diamonds_cost, status, admin_id, admin_comment, created_at, completed_at = request
                update_balance(user_id, diamonds_cost, f"exchange_refund_{request_id}")
                
                # Отмечаем как отклоненную
                update_exchange_request_status(request_id, "rejected", uid, "Заявка отклонена")
                
                bot.answer_callback_query(call.id, "❌ Заявка отклонена, алмазы возвращены")
                
                # Уведомляем пользователя
                try:
                    bot.send_message(
                        user_id,
                        f"❌ <b>ВАША ЗАЯВКА #{request_id} ОТКЛОНЕНА</b>\n\n"
                        f"📋 <b>Детали:</b>\n"
                        f"• Подарок: {gift_emoji} {gift_name}\n"
                        f"• Стоимость: {diamonds_cost}💎 (возвращены)\n"
                        f"• Администратор: ID {uid}\n\n"
                        f"💡 Алмазы возвращены на ваш баланс.\n"
                        f"Причина: проверка безопасности или технические проблемы."
                    )
                except:
                    pass
            
            # Удаляем сообщение с заявкой
            try:
                bot.delete_message(call.message.chat.id, call.message.message_id)
            except:
                pass
        
        # АДМИН: БАН/РАЗБАН
        elif call.data == "admin_ban_user":
            if not is_admin(uid):
                bot.answer_callback_query(call.id, "❌ Доступ запрещен")
                return
            
            msg = bot.send_message(
                uid,
                "🔨 <b>БАН ПОЛЬЗОВАТЕЛЯ</b>\n\n"
                "Введите ID пользователя для бана:\n"
                "Например: <code>123456789</code>\n\n"
                "💡 Забаненные пользователи не смогут пользоваться ботом."
            )
            bot.register_next_step_handler(msg, admin_ban_user)
            bot.answer_callback_query(call.id)
        
        elif call.data == "admin_unban_user":
            if not is_admin(uid):
                bot.answer_callback_query(call.id, "❌ Доступ запрещен")
                return
            
            msg = bot.send_message(
                uid,
                "🔓 <b>РАЗБАН ПОЛЬЗОВАТЕЛЯ</b>\n\n"
                "Введите ID пользователя для разбана:\n"
                "Например: <code>123456789</code>"
            )
            bot.register_next_step_handler(msg, admin_unban_user)
            bot.answer_callback_query(call.id)
        
        # НАЗАД
        elif call.data == "back_games":
            safe_edit_message_text(
                bot,
                "<b>🎮 Выберите игру</b>",
                call.message.chat.id,
                call.message.message_id,
                reply_markup=games_keyboard()
            )
        
        elif call.data == "back_main":
            bot.delete_message(call.message.chat.id, call.message.message_id)
        
        elif call.data == "back_admin":
            safe_edit_message_text(
                bot,
                "🛠 <b>Панель администратора</b>",
                call.message.chat.id,
                call.message.message_id,
                reply_markup=admin_keyboard()
            )
        
        # АДМИН: СПОНСОРЫ
        elif call.data == "admin_whitelist":
            if not is_admin(uid):
                bot.answer_callback_query(call.id, "❌ Доступ запрещен")
                return
            
            whitelist = get_whitelist()
            
            if not whitelist:
                text = "👥 <b>БЕЛЫЙ СПИСОК</b>\n\n"
                text += "Белый список пуст."
            else:
                text = "👥 <b>БЕЛЫЙ СПИСОК</b>\n\n"
                text += f"Пользователей в белом списке: {len(whitelist)}\n\n"
                text += "<b>ID пользователей:</b>\n"
                text += ", ".join([str(user_id) for user_id in whitelist[:20]])
                if len(whitelist) > 20:
                    text += f" и еще {len(whitelist) - 20}..."
            
            safe_edit_message_text(bot, text, call.message.chat.id, call.message.message_id, reply_markup=admin_settings_keyboard())
        
        elif call.data == "admin_restart":
            if not is_admin(uid):
                bot.answer_callback_query(call.id, "❌ Доступ запрещен")
                return
            
            bot.answer_callback_query(call.id, "🔄 Перезапуск бота...")
            bot.send_message(uid, "🔄 <b>Перезапуск бота...</b>")
            
            # Перезапуск бота
            restart_bot()
        
        elif call.data == "admin_add_sponsor":
            if not is_admin(uid):
                bot.answer_callback_query(call.id, "❌ Доступ запрещен")
                return
            
            msg = bot.send_message(
                uid,
                "📝 <b>ДОБАВЛЕНИЕ СПОНСОРА</b>\n\n"
                "Введите username канала и название через пробел:\n"
                "Например: <code>@channel_name Название канала</code>"
            )
            bot.register_next_step_handler(msg, admin_add_sponsor)
            bot.answer_callback_query(call.id)
        
        elif call.data == "admin_remove_sponsor":
            if not is_admin(uid):
                bot.answer_callback_query(call.id, "❌ Доступ запрещен")
                return
            
            sponsors = get_sponsor_channels_cached()
            
            if not sponsors:
                bot.send_message(uid, "❌ Нет спонсорских каналов для удаления")
                return
            
            text = "🗑 <b>УДАЛЕНИЕ СПОНСОРА</b>\n\n"
            text += "Введите username канала для удаления:\n\n"
            text += "<b>Текущие спонсоры:</b>\n"
            for sp_username, sp_name in sponsors:
                text += f"• @{sp_username} - {sp_name}\n"
            
            msg = bot.send_message(uid, text)
            bot.register_next_step_handler(msg, admin_remove_sponsor)
            bot.answer_callback_query(call.id)
        
        # АДМИН: ПРОМОКОДЫ
        elif call.data == "admin_create_promo":
            if not is_admin(uid):
                bot.answer_callback_query(call.id, "❌ Доступ запрещен")
                return
            
            msg = bot.send_message(
                uid,
                "🎫 <b>СОЗДАНИЕ ПРОМОКОДА</b>\n\n"
                "Введите данные промокода в формате:\n"
                "<code>КОД|НАГРАДА|ЛИМИТ|СРОК_ЧАСЫ</code>\n\n"
                "Пример:\n"
                "<code>NEWYEAR2024|100|50|168</code>\n\n"
                "• КОД: промокод (только буквы и цифры)\n"
                "• НАГРАДА: количество алмазов\n"
                "• ЛИМИТ: максимальное количество использований\n"
                "• СРОК_ЧАСЫ: срок действия в часах (0 = бессрочно)"
            )
            bot.register_next_step_handler(msg, admin_create_promo)
            bot.answer_callback_query(call.id)
        
        elif call.data == "admin_list_promos":
            if not is_admin(uid):
                bot.answer_callback_query(call.id, "❌ Доступ запрещен")
                return
            
            from database import get_all_promo_codes
            promos = get_all_promo_codes()
            
            if not promos:
                text = "📋 <b>СПИСОК ПРОМОКОДОВ</b>\n\n"
                text += "Промокодов пока нет."
            else:
                text = "📋 <b>СПИСОК ПРОМОКОДОВ</b>\n\n"
                for promo in promos[:10]:
                    code, reward, usage_limit, used_count, created_at, expires_at = promo
                    time_str = time.strftime('%d.%m.%Y', time.localtime(created_at))
                    expires_str = "Бессрочно" if expires_at == 0 else time.strftime('%d.%m.%Y %H:%M', time.localtime(expires_at))
                    
                    text += f"<b>{code}</b>\n"
                    text += f"Награда: {reward}💎 | Использовано: {used_count}/{usage_limit}\n"
                    text += f"Создан: {time_str} | Действует до: {expires_str}\n"
                    text += "━━━━━━━━━━━━━━━━\n"
                
                if len(promos) > 10:
                    text += f"\n... и еще {len(promos) - 10} промокодов"
            
            safe_edit_message_text(bot, text, call.message.chat.id, call.message.message_id, reply_markup=admin_promocodes_keyboard())
        
        # Если не найдено - просто отвечаем
        else:
            bot.answer_callback_query(call.id, "⏳ Обработка...")
    
    except Exception as e:
        logger.error(f"Error in callback {call.data}: {e}")
        try:
            bot.answer_callback_query(call.id, "❌ Произошла ошибка")
        except:
            pass

# ========== АДМИН ФУНКЦИИ ==========

def admin_add_balance(message):
    """Админ: выдать алмазы"""
    uid = message.from_user.id
    if not is_admin(uid):
        return
    
    try:
        parts = message.text.strip().split()
        if len(parts) != 2:
            bot.send_message(uid, "❌ Неверный формат. Используйте: ID КОЛИЧЕСТВО")
            return
        
        user_id = int(parts[0])
        amount = int(parts[1])
        
        if amount <= 0:
            bot.send_message(uid, "❌ Количество должно быть больше 0")
            return
        
        user_data = get_user(user_id)
        if not user_data:
            bot.send_message(uid, "❌ Пользователь не найден")
            return
        
        update_balance(user_id, amount, "admin_gift")
        
        # Уведомляем пользователя
        try:
            bot.send_message(
                user_id,
                f"🎁 <b>АДМИНИСТРАТОР ВЫДАЛ ВАМ АЛМАЗЫ!</b>\n\n"
                f"💎 <b>Получено:</b> +{amount}💎\n"
                f"💰 <b>Новый баланс:</b> {user_data[2] + amount}💎\n\n"
                f"Спасибо за участие! 🎰"
            )
        except:
            pass
        
        bot.send_message(
            uid,
            f"✅ <b>Алмазы выданы!</b>\n\n"
            f"Пользователь: @{user_data[1] or 'Нет'} (ID: {user_id})\n"
            f"Выдано: +{amount}💎\n"
            f"Новый баланс: {user_data[2] + amount}💎"
        )
        
    except ValueError:
        bot.send_message(uid, "❌ Ошибка: ID и количество должны быть числами")
    except Exception as e:
        logger.error(f"Error in admin_add_balance: {e}")
        bot.send_message(uid, "❌ Произошла ошибка")

def admin_take_balance(message):
    """Админ: забрать алмазы"""
    uid = message.from_user.id
    if not is_admin(uid):
        return
    
    try:
        parts = message.text.strip().split()
        if len(parts) != 2:
            bot.send_message(uid, "❌ Неверный формат. Используйте: ID КОЛИЧЕСТВО")
            return
        
        user_id = int(parts[0])
        amount = int(parts[1])
        
        if amount <= 0:
            bot.send_message(uid, "❌ Количество должно быть больше 0")
            return
        
        user_data = get_user(user_id)
        if not user_data:
            bot.send_message(uid, "❌ Пользователь не найден")
            return
        
        if user_data[2] < amount:
            bot.send_message(uid, f"❌ У пользователя только {user_data[2]}💎")
            return
        
        update_balance(user_id, -amount, "admin_take")
        
        # Уведомляем пользователя
        try:
            bot.send_message(
                user_id,
                f"⚠️ <b>АДМИНИСТРАТОР ИЗЪЯЛ АЛМАЗЫ</b>\n\n"
                f"💎 <b>Изъято:</b> -{amount}💎\n"
                f"💰 <b>Новый баланс:</b> {user_data[2] - amount}💎"
            )
        except:
            pass
        
        bot.send_message(
            uid,
            f"✅ <b>Алмазы изъяты!</b>\n\n"
            f"Пользователь: @{user_data[1] or 'Нет'} (ID: {user_id})\n"
            f"Изъято: -{amount}💎\n"
            f"Новый баланс: {user_data[2] - amount}💎"
        )
        
    except ValueError:
        bot.send_message(uid, "❌ Ошибка: ID и количество должны быть числами")
    except Exception as e:
        logger.error(f"Error in admin_take_balance: {e}")
        bot.send_message(uid, "❌ Произошла ошибка")

def admin_broadcast_message(message):
    """Админ: рассылка сообщений"""
    uid = message.from_user.id
    if not is_admin(uid):
        return
    
    text = message.text
    
    bot.send_message(uid, f"📢 <b>Начинаю рассылку...</b>\n\nПолучателей: ?")
    
    from database import get_all_users
    users = get_all_users()
    
    success = 0
    failed = 0
    
    for user_id, username, _ in users:
        try:
            bot.send_message(user_id, text, parse_mode="HTML")
            success += 1
            time.sleep(0.05)  # Задержка чтобы не превысить лимиты
        except Exception as e:
            logger.error(f"Failed to send to {user_id}: {e}")
            failed += 1
    
    bot.send_message(
        uid,
        f"✅ <b>Рассылка завершена!</b>\n\n"
        f"📊 <b>Результаты:</b>\n"
        f"├ Успешно: {success}\n"
        f"└ Не удалось: {failed}"
    )

def admin_create_lottery(message):
    """Админ: создание розыгрыша"""
    uid = message.from_user.id
    if not is_admin(uid):
        return
    
    try:
        parts = message.text.strip().split("|")
        if len(parts) != 4:
            bot.send_message(uid, "❌ Неверный формат. Используйте: Название|Приз|Цена|Дата")
            return
        
        name = parts[0].strip()
        prize = int(parts[1])
        ticket_price = int(parts[2])
        end_date = parts[3].strip()
        
        if prize <= 0 or ticket_price <= 0:
            bot.send_message(uid, "❌ Приз и цена билета должны быть больше 0")
            return
        
        lottery_id = create_custom_lottery(name, prize, ticket_price, end_date, uid)
        
        bot.send_message(
            uid,
            f"✅ <b>Розыгрыш создан!</b>\n\n"
            f"🎰 <b>Название:</b> {name}\n"
            f"💰 <b>Приз:</b> {prize}💎\n"
            f"🎫 <b>Цена билета:</b> {ticket_price}💎\n"
            f"📅 <b>Дата окончания:</b> {end_date}\n"
            f"🔑 <b>ID розыгрыша:</b> #{lottery_id}"
        )
        
    except ValueError:
        bot.send_message(uid, "❌ Ошибка: приз и цена должны быть числами")
    except Exception as e:
        logger.error(f"Error in admin_create_lottery: {e}")
        bot.send_message(uid, "❌ Произошла ошибка")

def admin_add_sponsor(message):
    """Админ: добавить спонсора"""
    uid = message.from_user.id
    if not is_admin(uid):
        return
    
    try:
        parts = message.text.strip().split()
        if len(parts) < 2:
            bot.send_message(uid, "❌ Неверный формат. Используйте: @username Название")
            return
        
        channel_username = parts[0]
        channel_name = " ".join(parts[1:])
        
        # Проверяем формат username
        if not channel_username.startswith("@"):
            channel_username = "@" + channel_username
        
        success = add_sponsor_channel(channel_username, channel_name, uid)
        
        if success:
            bot.send_message(
                uid,
                f"✅ <b>Спонсор добавлен!</b>\n\n"
                f"📺 <b>Канал:</b> {channel_username}\n"
                f"📝 <b>Название:</b> {channel_name}"
            )
        else:
            bot.send_message(uid, "❌ Ошибка при добавлении спонсора")
        
    except Exception as e:
        logger.error(f"Error in admin_add_sponsor: {e}")
        bot.send_message(uid, "❌ Произошла ошибка")

def admin_remove_sponsor(message):
    """Админ: удалить спонсора"""
    uid = message.from_user.id
    if not is_admin(uid):
        return
    
    try:
        channel_username = message.text.strip()
        
        if not channel_username.startswith("@"):
            channel_username = "@" + channel_username
        
        success = remove_sponsor_channel(channel_username)
        
        if success:
            bot.send_message(uid, f"✅ <b>Спонсор {channel_username} удален!</b>")
        else:
            bot.send_message(uid, f"❌ Спонсор {channel_username} не найден")
        
    except Exception as e:
        logger.error(f"Error in admin_remove_sponsor: {e}")
        bot.send_message(uid, "❌ Произошла ошибка")

def admin_create_promo(message):
    """Админ: создать промокод"""
    uid = message.from_user.id
    if not is_admin(uid):
        return
    
    try:
        parts = message.text.strip().split("|")
        if len(parts) != 4:
            bot.send_message(uid, "❌ Неверный формат. Используйте: КОД|НАГРАДА|ЛИМИТ|СРОК")
            return
        
        code = parts[0].strip().upper()
        reward = int(parts[1])
        usage_limit = int(parts[2])
        expires_hours = int(parts[3])
        
        if reward <= 0:
            bot.send_message(uid, "❌ Награда должна быть больше 0")
            return
        
        if usage_limit <= 0:
            bot.send_message(uid, "❌ Лимит использования должен быть больше 0")
            return
        
        success = create_promo_code(code, reward, usage_limit, uid, expires_hours)
        
        if success:
            expires_text = "бессрочно" if expires_hours == 0 else f"{expires_hours} часов"
            bot.send_message(
                uid,
                f"✅ <b>Промокод создан!</b>\n\n"
                f"🎫 <b>Код:</b> {code}\n"
                f"💎 <b>Награда:</b> {reward}💎\n"
                f"🔢 <b>Лимит:</b> {usage_limit} использований\n"
                f"⏰ <b>Срок:</b> {expires_text}"
            )
        else:
            bot.send_message(uid, "❌ Ошибка при создании промокода")
        
    except ValueError:
        bot.send_message(uid, "❌ Ошибка: награда, лимит и срок должны быть числами")
    except Exception as e:
        logger.error(f"Error in admin_create_promo: {e}")
        bot.send_message(uid, "❌ Произошла ошибка")

def admin_ban_user(message):
    """Админ: забанить пользователя"""
    uid = message.from_user.id
    if not is_admin(uid):
        return
    
    try:
        user_id = int(message.text.strip())
        
        if user_id == uid:
            bot.send_message(uid, "❌ Нельзя забанить самого себя!")
            return
        
        # Добавляем в черный список
        ban_user(user_id, uid, "Бан администратором")
        
        bot.send_message(
            uid,
            f"🔨 <b>Пользователь забанен!</b>\n\n"
            f"ID: {user_id}\n"
            f"Теперь этот пользователь не сможет пользоваться ботом."
        )
        
        # Уведомляем пользователя
        try:
            bot.send_message(
                user_id,
                "🚫 <b>ВЫ ЗАБАНЕНЫ!</b>\n\n"
                "Администратор заблокировал ваш доступ к боту.\n"
                "Если вы считаете, что это ошибка - свяжитесь с администратором."
            )
        except:
            pass
        
        logger.info(f"Admin {uid} banned user {user_id}")
        
    except ValueError:
        bot.send_message(uid, "❌ Ошибка: ID должен быть числом")
    except Exception as e:
        logger.error(f"Error in admin_ban_user: {e}")
        bot.send_message(uid, "❌ Произошла ошибка")

def admin_unban_user(message):
    """Админ: разбанить пользователя"""
    uid = message.from_user.id
    if not is_admin(uid):
        return
    
    try:
        user_id = int(message.text.strip())
        
        # Удаляем из черного списка
        success = unban_user(user_id)
        
        if success:
            bot.send_message(
                uid,
                f"🔓 <b>Пользователь разбанен!</b>\n\n"
                f"ID: {user_id}\n"
                f"Теперь этот пользователь снова может пользоваться ботом."
            )
            
            # Уведомляем пользователя
            try:
                bot.send_message(
                    user_id,
                    "✅ <b>ВЫ РАЗБАНЕНЫ!</b>\n\n"
                    "Администратор разблокировал ваш доступ к боту.\n"
                    "Теперь вы можете снова пользоваться всеми функциями."
                )
            except:
                pass
            
            logger.info(f"Admin {uid} unbanned user {user_id}")
        else:
            bot.send_message(uid, "❌ Пользователь не найден в черном списке")
        
    except ValueError:
        bot.send_message(uid, "❌ Ошибка: ID должен быть числом")
    except Exception as e:
        logger.error(f"Error in admin_unban_user: {e}")
        bot.send_message(uid, "❌ Произошла ошибка")

# ========== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ==========

def process_custom_stars_amount(message):
    """Обработка пользовательской суммы звезд"""
    uid = message.from_user.id
    
    try:
        stars_amount = int(message.text.strip())
        
        if stars_amount < 1:
            bot.send_message(uid, "❌ Минимальная сумма: 1 Telegram Star")
            return
        elif stars_amount > 10000:
            bot.send_message(uid, "❌ Максимальная сумма: 10000 Telegram Stars")
            return
        
        diamonds_amount = stars_amount * 9  # Курс: 1 звезда = 9 алмазов
        
        # Создаем счет на оплату
        success = create_stars_invoice(uid, stars_amount, diamonds_amount)
        if not success:
            bot.send_message(uid, "❌ Ошибка создания счета. Попробуйте позже.")
        
    except ValueError:
        bot.send_message(uid, "❌ Пожалуйста, введите число от 1 до 10000")
    except Exception as e:
        logger.error(f"Error in process_custom_stars_amount: {e}")
        bot.send_message(uid, "❌ Произошла ошибка. Попробуйте позже.")

def notify_admins_about_exchange_immediate(request_id, user_id, username, stars_amount, gift_name, gift_emoji, cost):
    """Уведомить администраторов о новой заявке на обмен с кнопками"""
    from config import ADMINS
    
    for admin_id in ADMINS:
        try:
            bot.send_message(
                admin_id,
                f"🔄 <b>НОВАЯ ЗАЯВКА НА ОБМЕН!</b>\n\n"
                f"📋 <b>Детали заявки #{request_id}:</b>\n"
                f"• Пользователь: @{username}\n"
                f"• User ID: {user_id}\n"
                f"• Подарок: {gift_emoji} {gift_name}\n"
                f"• Telegram Stars: ⭐ {stars_amount}\n"
                f"• Стоимость: {cost}💎\n\n"
                f"⏱ <b>Статус:</b> Ожидает обработки",
                reply_markup=types.InlineKeyboardMarkup().row(
                    types.InlineKeyboardButton("✅ Выполнено", callback_data=f"admin_exchange_complete_{request_id}"),
                    types.InlineKeyboardButton("❌ Отклонить", callback_data=f"admin_exchange_reject_{request_id}")
                )
            )
        except Exception as e:
            logger.error(f"Failed to notify admin {admin_id}: {e}")

def process_promo_code(message):
    """Обработка ввода промокода"""
    uid = message.from_user.id
    promo_code = message.text.strip().upper()
    
    if len(promo_code) < 4:
        bot.send_message(uid, "❌ Промокод слишком короткий")
        return
    
    success, result = use_promo_code(uid, promo_code)
    
    if success:
        reward = result
        bot.send_message(
            uid,
            f"🎉 <b>ПРОМОКОД АКТИВИРОВАН!</b>\n\n"
            f"На ваш баланс зачислено: <b>+{reward}💎</b>\n"
            f"Новый баланс: <b>{get_user(uid)[2]}💎</b>"
        )
        logger.info(f"User {uid} used promo code {promo_code}: {reward} алмазов")
    else:
        bot.send_message(uid, f"❌ {result}")

def handle_subscription_check(message, check_result):
    """Обработка проверки подписки в сообщениях"""
    uid = message.from_user.id
    if check_result[1] == "subscription":
        channel_username, channel_name = check_result[2], check_result[3]
        sponsors = get_sponsor_channels_cached()
        
        text = f"📺 <b>Для использования бота необходимо подписаться на наш канал:</b>\n\n"
        for sp_username, sp_name in sponsors:
            text += f"• {sp_name} - @{sp_username[1:] if sp_username.startswith('@') else sp_username}\n"
        
        text += f"\nПосле подписки нажмите кнопку '✅ Я подписался'"
        
        bot.send_message(
            uid,
            text,
            reply_markup=sponsors_keyboard(sponsors)
        )

# ========== ПРОВЕРКА ПЛАТЕЖЕЙ ПО ТАЙМЕРУ ==========

def check_payments_job():
    """Периодическая проверка статуса платежей"""
    import threading
    
    def job():
        while True:
            try:
                # Получаем все ожидающие платежи
                cursor.execute("SELECT invoice_id FROM payments WHERE status='pending'")
                pending_payments = cursor.fetchall()
                
                for (invoice_id,) in pending_payments:
                    # Проверяем статус в CryptoBot
                    status = check_cryptobot_invoice(invoice_id)
                    
                    if status == 'paid':
                        # Получаем информацию о платеже
                        payment = get_payment_by_invoice(invoice_id)
                        if payment:
                            payment_id, user_id, amount, invoice_id_db, status_db, created_at, completed_at = payment
                            
                            if status_db != 'paid':
                                # Обновляем статус
                                update_payment_status(invoice_id, 'paid')
                                
                                # Начисляем алмазы
                                update_balance(user_id, amount, f"cryptobot_payment_{invoice_id}")
                                
                                # Уведомляем пользователя
                                try:
                                    bot.send_message(
                                        user_id,
                                        f"✅ <b>ПЛАТЕЖ ОБРАБОТАН!</b>\n\n"
                                        f"На ваш баланс зачислено: <b>+{amount}💎</b>\n"
                                        f"Новый баланс: <b>{get_user(user_id)[2]}💎</b>\n\n"
                                        f"Спасибо за покупку!"
                                    )
                                except:
                                    pass
                                
                                logger.info(f"Auto payment processed for user {user_id}: {amount} алмазов")
                
                time.sleep(60)  # Проверяем каждые 60 секунд
                
            except Exception as e:
                logger.error(f"Error in payments job: {e}")
                time.sleep(300)  # При ошибке ждем 5 минут
    
    # Запускаем в отдельном потоке
    thread = threading.Thread(target=job, daemon=True)
    thread.start()

# ========== ЗАПУСК БОТА ==========

if __name__ == "__main__":
    logger.info("=== DARKCASE BOT STARTED ===")
    print("🎮 Бот запущен и готов к работе!")
    print(f"Администраторы: {ADMINS}")
    print("✅ ВСЕ ОБРАБОТЧИКИ ДОБАВЛЕНЫ:")
    print("• ✅ Реферальная система исправлена и работает")
    print("• ❌ Игра 'Мины' удалена")
    print("• ✅ Все сундуки (платные и бесплатные) с исправленными шансами")
    print("• ✅ Все игры (рулетка, кубик, КНБ, слоты, блэкджек)")
    print("• ✅ Все кнопки профиля")
    print("• ✅ Все топы")
    print("• ✅ Все задания")
    print("• ✅ Весь розыгрыш")
    print("• ✅ Вся админ-панель")
    print("• ✅ Обмен алмазов на Stars")
    print("• ✅ Пополнение Telegram Stars и CryptoBot")
    print("• ✅ Проверка подписки")
    print("• ✅ Мгновенное подтверждение обменов администратором")
    print("• ✅ Система бана/разбана пользователей")
    print("• 🖼 Картинки работают")
    print("• 💎 Курс: 1 звезда = 9 алмазов")
    print("• ✂️ Исправлена игра Камень-Ножницы-Бумага")
    print("• 🎁 Исправлены сообщения о выигрыше в сундуках")
    print("• ⏱ Задержка сообщений: 1.5 секунды")
    print("• 📋 Добавлено пользовательское соглашение")
    print("• 🔄 Автоматический перезапуск при критических ошибках")
    print("• 💾 Бот сохраняет состояние при перезагрузке сервера")
    
    # Запускаем проверку платежей
    check_payments_job()
    
    # Основной цикл с перезапуском при ошибках
    while True:
        try:
            bot.infinity_polling(timeout=60, long_polling_timeout=30)
        except Exception as e:
            logger.error(f"Bot crashed: {e}")
            print(f"❌ Бот упал с ошибкой: {e}")
            print("🔄 Перезапуск бота через 10 секунд...")
            time.sleep(10)
            restart_bot()