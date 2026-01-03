import random
import time
from datetime import datetime

class Case:
    def __init__(self, name, price, min_reward, max_reward, safe_range, emoji):
        self.name = name
        self.price = price
        self.min_reward = min_reward
        self.max_reward = max_reward
        self.safe_range = safe_range  # 80% шанс в этом диапазоне (ИЗМЕНЕНО с 90%)
        self.emoji = emoji
    
    def open(self):
        """Открытие платного сундука с новыми шансами"""
        # 80% шанс на безопасный диапазон, 20% на остальное (ИЗМЕНЕНО с 90%)
        if random.random() < 0.8:  # 80% шанс
            return random.randint(self.min_reward, self.safe_range)
        else:  # 20% шанс
            return random.randint(self.safe_range + 1, self.max_reward)

# Определение сундуков с новыми шансами
CASES = {
    "c10": Case("Деревянный", 10, 0, 20, 8, "🪵"),         # 0-20, 80% шанс 0-8 (ИЗМЕНЕНО)
    "c25": Case("Железный", 25, 5, 50, 20, "⚙️"),          # 5-50, 80% шанс 5-20 (ИЗМЕНЕНО)
    "c50": Case("Золотой", 50, 30, 100, 40, "💰"),          # 30-100, 80% шанс 30-40 (ИЗМЕНЕНО)
    "c150": Case("Алмазный", 150, 135, 250, 175, "💎"),     # 135-250, 80% шанс 135-175 (ИЗМЕНЕНО)
    "c500": Case("Незеритовый", 500, 355, 850, 555, "🪨"), # 355-850, 80% шанс 355-555 (ИЗМЕНЕНО)
}

def open_free_case():
    """Открытие бесплатного сундука с новыми шансами"""
    # Деревянный сундук: 0-20, 80% шанс 0-8 (ИЗМЕНЕНО с 90%)
    if random.random() < 0.8:  # 80% шанс
        return random.randint(0, 8)
    else:  # 20% шанс
        return random.randint(9, 20)

class UserModel:
    @staticmethod
    def from_db_row(row):
        """Создает удобный объект из строки БД"""
        return {
            'id': row[0],
            'username': row[1],
            'balance': row[2],
            'free_cases': row[3],
            'last_free': row[4],
            'refs': row[5],
            'opened_cases': row[6],
            'wins': row[7],
            'losses': row[8],
            'daily_streak': row[9],
            'last_daily': row[10],
            'total_wagered': row[11],
            'created_at': row[12],
            'vip_level': row[13]
        }

# Система уровней
LEVELS = {
    1: {"exp_needed": 0, "bonus": 0, "title": "Новичок"},
    2: {"exp_needed": 100, "bonus": 10, "title": "Ученик"},
    3: {"exp_needed": 300, "bonus": 25, "title": "Игрок"},
    4: {"exp_needed": 600, "bonus": 50, "title": "Опытный"},
    5: {"exp_needed": 1000, "bonus": 100, "title": "Мастер"},
    6: {"exp_needed": 1500, "bonus": 150, "title": "Эксперт"},
    7: {"exp_needed": 2100, "bonus": 200, "title": "Гуру"},
    8: {"exp_needed": 2800, "bonus": 300, "title": "Легенда"},
    9: {"exp_needed": 3600, "bonus": 400, "title": "Миф"},
    10: {"exp_needed": 4500, "bonus": 500, "title": "Бог"},
}

# Недельные задания с уменьшенными наградами
WEEKLY_QUESTS = {
    "open_cases": {
        "name": "📦 Открыть сундуки",
        "description": "Откройте 10 сундуков",
        "goal": 10,
        "reward": 10
    },
    "win_games": {
        "name": "🏆 Победить в играх",
        "description": "Выиграйте 5 игр",
        "goal": 5,
        "reward": 8
    },
    "invite_friends": {
        "name": "👥 Пригласить друзей",
        "description": "Пригласите 3 друзей",
        "goal": 3,
        "reward": 15
    },
    "spend_stars": {
        "name": "💎 Потратить алмазы",
        "description": "Потратьте 500 алмазов",
        "goal": 500,
        "reward": 10
    },
    "daily_login": {
        "name": "📅 Ежедневный вход",
        "description": "Зайдите 7 дней подряд",
        "goal": 7,
        "reward": 15
    },
    "play_slot": {
        "name": "🎰 Играть в слоты",
        "description": "Сыграйте 20 раз в слоты",
        "goal": 20,
        "reward": 5
    },
    "play_blackjack": {
        "name": "🃏 Играть в блэкджек",
        "description": "Сыграйте 10 раз в блэкджек",
        "goal": 10,
        "reward": 7
    }
}