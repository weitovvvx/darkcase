import random
from config import ROULETTE_WIN_CHANCE, MIN_BET
from telebot import types

class Roulette:
    @staticmethod
    def spin(bet):
        if bet < MIN_BET:
            return False, 0
        
        # Уменьшенный шанс выигрыша (20%)
        if random.random() < ROULETTE_WIN_CHANCE:  # 20% шанс
            return True, bet * 2
        return False, 0

class Dice:
    @staticmethod
    def roll(bet):
        if bet < MIN_BET:
            return False, 0, 1
        
        roll = random.randint(1, 6)
        if roll == 6:
            return True, bet * 4, roll  # Уменьшен с x5 до x4
        elif roll == 1:
            return None, bet, roll  # Возврат ставки
        return False, 0, roll  # Проигрыш

class StonePaperScissors:
    @staticmethod
    def play(bet, choice):
        """choice: 'stone', 'paper', 'scissors'"""
        if bet < MIN_BET:
            return False, 0
        
        # Создаем весовую систему с небольшим смещением в пользу компьютера
        choices = ['stone', 'paper', 'scissors']
        weights = [0.32, 0.34, 0.34]  # Слегка смещенные веса
        bot_choice = random.choices(choices, weights=weights, k=1)[0]
        
        # Определяем победителя
        if choice == bot_choice:
            return None, bet, bot_choice  # Ничья - возврат ставки
        elif (choice == 'stone' and bot_choice == 'scissors') or \
             (choice == 'paper' and bot_choice == 'stone') or \
             (choice == 'scissors' and bot_choice == 'paper'):
            # Игрок победил
            return True, bet * 2, bot_choice
        else:
            # Игрок проиграл
            return False, 0, bot_choice

class SlotMachine:
    @staticmethod
    def spin(bet):
        if bet < MIN_BET:
            return False, 0, []
        
        symbols = ["🍒", "🍋", "⭐", "7️⃣", "🔔", "💎"]
        
        # Увеличены веса на менее выигрышные символы
        weights = {
            "🍒": 40,  # Увеличен вес
            "🍋": 35,  # Увеличен вес
            "🔔": 15,  # Уменьшен вес
            "💎": 6,   # Уменьшен вес
            "⭐": 3,    # Уменьшен вес
            "7️⃣": 1    # Минимальный вес
        }
        
        weighted_symbols = []
        for symbol, weight in weights.items():
            weighted_symbols.extend([symbol] * weight)
        
        result = [random.choice(weighted_symbols) for _ in range(3)]
        
        # Определяем выигрыш
        if result[0] == result[1] == result[2]:
            if result[0] == "7️⃣":
                return True, bet * 8, result  # Уменьшен с x10
            elif result[0] == "💎":
                return True, bet * 6, result  # Уменьшен с x8
            elif result[0] == "⭐":
                return True, bet * 4, result  # Уменьшен с x6
            elif result[0] == "🔔":
                return True, bet * 3, result  # Уменьшен с x4
            else:
                return True, bet * 2, result
        elif result[0] == result[1] or result[1] == result[2]:
            # Уменьшенный выигрыш за 2 одинаковых
            if result[0] == "7️⃣" or result[1] == "7️⃣":
                return True, int(bet * 1.3), result  # Уменьшен с x1.5
            else:
                return True, int(bet * 1.1), result  # Уменьшен с x1.2
        
        return False, 0, result

class BlackJack:
    @staticmethod
    def play(bet):
        if bet < MIN_BET:
            return False, 0, ([], [])
        
        player_cards = []
        dealer_cards = []
        
        for _ in range(2):
            player_cards.append(random.randint(1, 11))
            dealer_cards.append(random.randint(1, 11))
        
        player_sum = sum(player_cards)
        dealer_sum = sum(dealer_cards)
        
        # Увеличен шанс взять карту с риском перебора
        if player_sum <= 16 and random.random() < 0.8:
            player_cards.append(random.randint(1, 11))
            player_sum = sum(player_cards)
        
        # Дилер с увеличенным преимуществом
        while dealer_sum < 17:
            dealer_cards.append(random.randint(1, 11))
            dealer_sum = sum(dealer_cards)
        
        # Увеличен шанс выигрыша дилера
        if player_sum > 21:
            return False, 0, (player_cards, dealer_cards)
        elif dealer_sum > 21:
            return True, bet * 2, (player_cards, dealer_cards)
        elif player_sum > dealer_sum:
            # 10% шанс что дилер выиграет даже при меньшей сумме
            if random.random() < 0.1:
                return False, 0, (player_cards, dealer_cards)
            return True, bet * 2, (player_cards, dealer_cards)
        elif player_sum == dealer_sum:
            # 70% шанс что дилер выиграет при ничьей
            if random.random() < 0.7:
                return False, 0, (player_cards, dealer_cards)
            return None, bet, (player_cards, dealer_cards)
        else:
            return False, 0, (player_cards, dealer_cards)

class ActivitySystem:
    @staticmethod
    def get_streak_bonus(streak_days):
        """Получить бонус за серию входов"""
        if streak_days >= 30:
            return 500, "🔥 30 дней подряд!"
        elif streak_days >= 14:
            return 200, "⭐ 2 недели стрика!"
        elif streak_days >= 7:
            return 100, "💎 Недельный стрик!"
        elif streak_days >= 3:
            return 30, "🎯 3 дня подряд!"
        return 0, ""
    
    @staticmethod
    def get_first_game_bonus():
        """Бонус за первую игру дня"""
        return 15, "🎁 Первая игра дня!"

class Lottery:
    @staticmethod
    def get_next_draw_date():
        """Получить дату следующего розыгрыша (каждое воскресенье)"""
        from datetime import datetime, timedelta
        today = datetime.now()
        days_until_sunday = (6 - today.weekday()) % 7
        if days_until_sunday == 0:
            days_until_sunday = 7
        next_sunday = today + timedelta(days=days_until_sunday)
        return next_sunday.strftime("%Y-%m-%d")
    
    @staticmethod
    def get_current_jackpot(ticket_count):
        """Получить текущий джекпот"""
        from config import LOTTERY_TICKET_PRICE
        return ticket_count * LOTTERY_TICKET_PRICE * 2