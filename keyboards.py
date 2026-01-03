from telebot import types
from models import CASES, WEEKLY_QUESTS
import time
import random

def main_keyboard(is_admin=False):
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    kb.add("🎮 Игры")
    kb.add("👤 Профиль")
    kb.add("🏆 Топы", "🎁 Ежедневный")
    kb.add("📅 Задания", "🎰 Розыгрыш")
    kb.add("💎 Пополнить", "🔄 Обмен алмазов")
    if is_admin:
        kb.add("🛠 Админ")
    return kb

def games_menu_keyboard():
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("🎁 Сундуки", callback_data="game_cases"),
        types.InlineKeyboardButton("🎮 Игры", callback_data="game_minigames")
    )
    return kb

def cases_keyboard(free_cases):
    kb = types.InlineKeyboardMarkup(row_width=2)
    
    if free_cases > 0:
        kb.add(types.InlineKeyboardButton(
            f"🪵 Деревянный ({free_cases})", 
            callback_data="free_case"
        ))
    
    buttons = []
    for key, case in CASES.items():
        buttons.append(types.InlineKeyboardButton(
            f"{case.emoji} {case.name} ({case.price}💎)", 
            callback_data=key
        ))
    
    for i in range(0, len(buttons), 2):
        if i + 1 < len(buttons):
            kb.add(buttons[i], buttons[i + 1])
        else:
            kb.add(buttons[i])
    
    return kb

def games_keyboard():
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("🎡 Рулетка", callback_data="game_roulette"),
        types.InlineKeyboardButton("🎲 Кубик", callback_data="game_dice"),
    )
    kb.add(
        types.InlineKeyboardButton("✂️ КНБ", callback_data="game_sps"),
        types.InlineKeyboardButton("🎪 Ивенты", callback_data="events"),
    )
    kb.add(
        types.InlineKeyboardButton("🎰 Слоты", callback_data="game_slot"),
        types.InlineKeyboardButton("🃏 Блэкджек", callback_data="game_blackjack"),
    )
    kb.add(
        types.InlineKeyboardButton("📊 Топ уровней", callback_data="top_levels"),
        types.InlineKeyboardButton("🔙 Назад", callback_data="back_games_menu")
    )
    return kb

def profile_keyboard():
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("📊 Статистика", callback_data="profile_stats"),
        types.InlineKeyboardButton("⭐ Уровни", callback_data="levels_info"),
    )
    kb.add(
        types.InlineKeyboardButton("🎫 Промокод", callback_data="enter_promo"),
        types.InlineKeyboardButton("📈 Активность", callback_data="activity_info"),
    )
    kb.add(
        types.InlineKeyboardButton("💳 История покупок", callback_data="payment_history"),
        types.InlineKeyboardButton("🔙 Назад", callback_data="back_main"),
    )
    return kb

def admin_keyboard():
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("➕ Выдать 💎", callback_data="admin_add"),
        types.InlineKeyboardButton("➖ Забрать 💎", callback_data="admin_take"),
    )
    kb.add(
        types.InlineKeyboardButton("📊 Статистика бота", callback_data="admin_stats"),
        types.InlineKeyboardButton("👥 Все пользователи", callback_data="admin_users"),
    )
    kb.add(
        types.InlineKeyboardButton("📢 Рассылка", callback_data="admin_broadcast"),
        types.InlineKeyboardButton("⚙ Настройки", callback_data="admin_settings"),
    )
    kb.add(
        types.InlineKeyboardButton("🎫 Промокоды", callback_data="admin_promocodes"),
        types.InlineKeyboardButton("🎰 Создать розыгрыш", callback_data="admin_create_lottery"),
    )
    kb.add(
        types.InlineKeyboardButton("📺 Спонсоры", callback_data="admin_sponsors"),
        types.InlineKeyboardButton("⭐ Заявки на обмен", callback_data="admin_exchange_requests"),
    )
    kb.add(
        types.InlineKeyboardButton("🔨 Бан пользователя", callback_data="admin_ban_user"),
        types.InlineKeyboardButton("🔓 Разбан пользователя", callback_data="admin_unban_user"),
    )
    kb.add(
        types.InlineKeyboardButton("🔙 Назад", callback_data="back_admin"),
    )
    return kb

def admin_settings_keyboard():
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("👥 Белый список", callback_data="admin_whitelist"),
        types.InlineKeyboardButton("🔄 Перезапустить бота", callback_data="admin_restart"),
    )
    kb.add(
        types.InlineKeyboardButton("📝 Добавить спонсора", callback_data="admin_add_sponsor"),
        types.InlineKeyboardButton("🗑 Удалить спонсора", callback_data="admin_remove_sponsor"),
    )
    kb.add(
        types.InlineKeyboardButton("🔨 Бан пользователя", callback_data="admin_ban_user"),
        types.InlineKeyboardButton("🔓 Разбан пользователя", callback_data="admin_unban_user"),
    )
    kb.add(
        types.InlineKeyboardButton("🔙 Назад", callback_data="back_admin")
    )
    return kb

def admin_promocodes_keyboard():
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("🎫 Создать промокод", callback_data="admin_create_promo"),
        types.InlineKeyboardButton("📋 Список промокодов", callback_data="admin_list_promos"),
    )
    kb.add(
        types.InlineKeyboardButton("🔙 Назад", callback_data="back_admin")
    )
    return kb

def bet_keyboard(game_type):
    kb = types.InlineKeyboardMarkup(row_width=3)
    bets = [10, 25, 50, 100, 250, 500]
    
    row = []
    for bet in bets:
        row.append(types.InlineKeyboardButton(
            f"{bet}💎", 
            callback_data=f"bet_{game_type}_{bet}"
        ))
        if len(row) == 3:
            kb.add(*row)
            row = []
    
    if row:
        kb.add(*row)
    
    kb.add(types.InlineKeyboardButton("🔙 Назад", callback_data="back_games"))
    return kb

def sps_keyboard():
    kb = types.InlineKeyboardMarkup(row_width=3)
    kb.add(
        types.InlineKeyboardButton("🪨 Камень", callback_data="sps_stone"),
        types.InlineKeyboardButton("📄 Бумага", callback_data="sps_paper"),
        types.InlineKeyboardButton("✂️ Ножницы", callback_data="sps_scissors"),
    )
    kb.add(types.InlineKeyboardButton("🔙 Назад", callback_data="back_games"))
    return kb

def tops_keyboard():
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("💎 По балансу", callback_data="top_balance"),
        types.InlineKeyboardButton("👥 По рефералам", callback_data="top_refs"),
    )
    kb.add(
        types.InlineKeyboardButton("🏆 По победам", callback_data="top_wins"),
        types.InlineKeyboardButton("⭐ По уровням", callback_data="top_levels"),
    )
    kb.add(
        types.InlineKeyboardButton("🔙 Назад", callback_data="back_main"),
    )
    return kb

def back_keyboard():
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("🔙 Назад", callback_data="back_main"))
    return kb

def weekly_quests_keyboard():
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(types.InlineKeyboardButton("📋 Мои задания", callback_data="my_quests"))
    kb.add(types.InlineKeyboardButton("🏆 Награды за задания", callback_data="quest_rewards"))
    kb.add(types.InlineKeyboardButton("📊 Прогресс", callback_data="quest_progress"))
    kb.add(types.InlineKeyboardButton("🔙 Назад", callback_data="back_main"))
    return kb

def lottery_keyboard(draw_date, user_tickets_count=0):
    kb = types.InlineKeyboardMarkup(row_width=2)
    
    from config import LOTTERY_TICKET_PRICE
    kb.add(types.InlineKeyboardButton(
        f"🎫 Купить билет ({LOTTERY_TICKET_PRICE}💎)", 
        callback_data="buy_lottery_ticket"
    ))
    
    if user_tickets_count > 0:
        kb.add(types.InlineKeyboardButton(
            f"🎟 Мои билеты ({user_tickets_count})", 
            callback_data="my_lottery_tickets"
        ))
    
    kb.add(types.InlineKeyboardButton(
        "📜 История розыгрышей", 
        callback_data="lottery_history"
    ))
    
    kb.add(types.InlineKeyboardButton(
        "🏆 Текущий приз", 
        callback_data="lottery_jackpot"
    ))
    
    kb.add(types.InlineKeyboardButton("🔙 Назад", callback_data="back_main"))
    return kb

def slot_bet_keyboard():
    kb = types.InlineKeyboardMarkup(row_width=3)
    bets = [10, 25, 50, 100, 250, 500, 1000]
    
    row = []
    for bet in bets:
        row.append(types.InlineKeyboardButton(
            f"{bet}💎", 
            callback_data=f"bet_slot_{bet}"
        ))
        if len(row) == 3:
            kb.add(*row)
            row = []
    
    if row:
        kb.add(*row)
    
    kb.add(types.InlineKeyboardButton("🔙 Назад", callback_data="back_games"))
    return kb

def blackjack_bet_keyboard():
    kb = types.InlineKeyboardMarkup(row_width=3)
    bets = [10, 25, 50, 100, 250, 500, 1000]
    
    row = []
    for bet in bets:
        row.append(types.InlineKeyboardButton(
            f"{bet}💎", 
            callback_data=f"bet_blackjack_{bet}"
        ))
        if len(row) == 3:
            kb.add(*row)
            row = []
    
    if row:
        kb.add(*row)
    
    kb.add(types.InlineKeyboardButton("🔙 Назад", callback_data="back_games"))
    return kb

def buy_almaz_keyboard():
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("⭐ Telegram Stars", callback_data="payment_stars"),
        types.InlineKeyboardButton("🤖 CryptoBot", callback_data="payment_cryptobot")
    )
    kb.add(types.InlineKeyboardButton("🔙 Назад", callback_data="back_main"))
    return kb

def buy_stars_keyboard():
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("⭐ 1 звезда (9💎)", callback_data="stars_1"),
        types.InlineKeyboardButton("⭐ 10 звезд (90💎)", callback_data="stars_10"),
    )
    kb.add(
        types.InlineKeyboardButton("⭐ 50 звезд (450💎)", callback_data="stars_50"),
        types.InlineKeyboardButton("⭐ 100 звезд (900💎)", callback_data="stars_100"),
    )
    kb.add(
        types.InlineKeyboardButton("⭐ 200 звезд (1800💎)", callback_data="stars_200"),
        types.InlineKeyboardButton("⭐ 500 звезд (4500💎)", callback_data="stars_500"),
    )
    kb.add(
        types.InlineKeyboardButton("⭐ 1000 звезд (9000💎)", callback_data="stars_1000"),
        types.InlineKeyboardButton("📝 Ввести свою сумму", callback_data="stars_custom")
    )
    kb.add(types.InlineKeyboardButton("🔙 Назад", callback_data="back_main"))
    return kb

def buy_cryptobot_keyboard():
    kb = types.InlineKeyboardMarkup(row_width=2)
    from config import ALMAZ_PACKAGES
    for amount, price in ALMAZ_PACKAGES.items():
        kb.add(types.InlineKeyboardButton(
            f"{amount}💎 - {price}$", 
            callback_data=f"buy_{amount}"
        ))
    kb.add(types.InlineKeyboardButton("🔙 Назад", callback_data="back_main"))
    return kb

def exchange_menu_keyboard():
    """Меню обмена алмазов на Telegram Stars подарки"""
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("💝 Сердечко (150💎 → 15⭐)", callback_data="exchange_heart"),
        types.InlineKeyboardButton("🌹 Роза (250💎 → 25⭐)", callback_data="exchange_rose"),
    )
    kb.add(
        types.InlineKeyboardButton("🎁 Подарок (250💎 → 25⭐)", callback_data="exchange_gift"),
        types.InlineKeyboardButton("🍾 Шампанское (500💎 → 50⭐)", callback_data="exchange_champagne"),
    )
    kb.add(
        types.InlineKeyboardButton("🎂 Торт (500💎 → 50⭐)", callback_data="exchange_cake"),
        types.InlineKeyboardButton("🏆 Кубок (1000💎 → 100⭐)", callback_data="exchange_trophy"),
    )
    kb.add(
        types.InlineKeyboardButton("💎 Бриллиант (1000💎 → 100⭐)", callback_data="exchange_diamond_gift"),
        types.InlineKeyboardButton("🔙 Назад", callback_data="back_main"),
    )
    return kb

def confirm_exchange_keyboard(exchange_type):
    """Клавиатура подтверждения обмена"""
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("✅ Подтвердить обмен", 
                                 callback_data=f"confirm_exchange_{exchange_type}"),
        types.InlineKeyboardButton("❌ Отмена", callback_data="cancel_exchange")
    )
    return kb

def admin_exchange_requests_keyboard():
    """Клавиатура для админа - управление заявками на обмен"""
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("📋 Список заявок", callback_data="admin_exchange_list"),
        types.InlineKeyboardButton("✅ Заявки на выдачу", callback_data="admin_exchange_pending"),
    )
    kb.add(
        types.InlineKeyboardButton("📊 Статистика обменов", callback_data="admin_exchange_stats"),
        types.InlineKeyboardButton("🔙 Назад", callback_data="back_admin"),
    )
    return kb

def admin_exchange_action_keyboard(request_id):
    """Клавиатура действий с заявкой на обмен"""
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("✅ Выполнено", 
                                 callback_data=f"exchange_complete_{request_id}"),
        types.InlineKeyboardButton("❌ Отклонить", 
                                 callback_data=f"exchange_reject_{request_id}"),
    )
    kb.add(
        types.InlineKeyboardButton("📝 Комментарий", 
                                 callback_data=f"exchange_comment_{request_id}"),
        types.InlineKeyboardButton("🔙 Назад", 
                                 callback_data="admin_exchange_list"),
    )
    return kb

def sponsors_keyboard(sponsors):
    kb = types.InlineKeyboardMarkup(row_width=1)
    for channel_username, channel_name in sponsors:
        kb.add(types.InlineKeyboardButton(
            f"📺 {channel_name}", 
            url=f"https://t.me/{channel_username[1:]}" if channel_username.startswith("@") else f"https://t.me/{channel_username}"
        ))
    kb.add(types.InlineKeyboardButton("✅ Я подписался", callback_data="check_subscription"))
    return kb