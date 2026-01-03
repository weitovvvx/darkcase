import sqlite3
import time
import json
from contextlib import contextmanager
from utils import logger

conn = sqlite3.connect("casino.db", check_same_thread=False, isolation_level=None)
cursor = conn.cursor()

# Создаем все таблицы
cursor.executescript("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    username TEXT,
    balance INTEGER DEFAULT 0,
    free_cases INTEGER DEFAULT 0,
    last_free INTEGER DEFAULT 0,
    refs INTEGER DEFAULT 0,
    referrer_id INTEGER DEFAULT 0,
    opened_cases INTEGER DEFAULT 0,
    wins INTEGER DEFAULT 0,
    losses INTEGER DEFAULT 0,
    daily_streak INTEGER DEFAULT 0,
    last_daily INTEGER DEFAULT 0,
    total_wagered INTEGER DEFAULT 0,
    created_at INTEGER DEFAULT 0,
    vip_level INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS active_mines_games (
    user_id INTEGER PRIMARY KEY,
    bet_amount INTEGER,
    difficulty TEXT,
    mines_count INTEGER,
    multiplier REAL,
    field_data TEXT,
    opened_cells TEXT,
    current_multiplier REAL,
    start_time INTEGER
);

CREATE TABLE IF NOT EXISTS achievements (
    user_id INTEGER,
    achievement TEXT,
    unlocked_at INTEGER,
    PRIMARY KEY (user_id, achievement)
);

CREATE TABLE IF NOT EXISTS transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    type TEXT,
    amount INTEGER,
    details TEXT,
    created_at INTEGER
);

CREATE TABLE IF NOT EXISTS user_levels (
    user_id INTEGER PRIMARY KEY,
    level INTEGER DEFAULT 1,
    exp INTEGER DEFAULT 0,
    total_exp INTEGER DEFAULT 0,
    last_level_up INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS weekly_quests (
    user_id INTEGER,
    quest_id TEXT,
    progress INTEGER DEFAULT 0,
    completed INTEGER DEFAULT 0,
    claimed INTEGER DEFAULT 0,
    week_number INTEGER,
    PRIMARY KEY (user_id, quest_id, week_number)
);

CREATE TABLE IF NOT EXISTS lottery_tickets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    ticket_number INTEGER,
    draw_date TEXT,
    created_at INTEGER
);

CREATE TABLE IF NOT EXISTS lottery_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    draw_date TEXT,
    winner_id INTEGER,
    winner_username TEXT,
    prize INTEGER,
    ticket_count INTEGER,
    created_at INTEGER
);

CREATE TABLE IF NOT EXISTS user_activity (
    user_id INTEGER PRIMARY KEY,
    last_active INTEGER,
    daily_login_count INTEGER DEFAULT 0,
    streak_bonus_claimed INTEGER DEFAULT 0,
    first_game_bonus INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS sponsors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    channel_username TEXT UNIQUE,
    channel_name TEXT,
    added_by INTEGER,
    added_at INTEGER
);

CREATE TABLE IF NOT EXISTS promo_codes (
    code TEXT PRIMARY KEY,
    reward INTEGER,
    usage_limit INTEGER DEFAULT 1,
    used_count INTEGER DEFAULT 0,
    created_by INTEGER,
    created_at INTEGER,
    expires_at INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS promo_usage (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    promo_code TEXT,
    used_at INTEGER
);

CREATE TABLE IF NOT EXISTS active_lotteries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    prize_amount INTEGER,
    ticket_price INTEGER,
    end_date TEXT,
    created_by INTEGER,
    created_at INTEGER,
    is_active INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS custom_lottery_tickets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    lottery_id INTEGER,
    user_id INTEGER,
    ticket_number INTEGER,
    created_at INTEGER,
    FOREIGN KEY (lottery_id) REFERENCES active_lotteries(id)
);

CREATE TABLE IF NOT EXISTS payments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    amount INTEGER,
    invoice_id TEXT UNIQUE,
    status TEXT DEFAULT 'pending',
    created_at INTEGER,
    completed_at INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS whitelist (
    user_id INTEGER PRIMARY KEY,
    added_by INTEGER,
    added_at INTEGER
);

CREATE TABLE IF NOT EXISTS exchange_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    username TEXT,
    stars_amount INTEGER,
    gift_name TEXT,
    gift_emoji TEXT,
    diamonds_cost INTEGER,
    status TEXT DEFAULT 'pending', 
    admin_id INTEGER DEFAULT 0,
    admin_comment TEXT,
    created_at INTEGER,
    completed_at INTEGER DEFAULT 0,
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);

CREATE TABLE IF NOT EXISTS exchange_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    username TEXT,
    stars_amount INTEGER,
    gift_name TEXT,
    diamonds_cost INTEGER,
    status TEXT,
    admin_id INTEGER,
    created_at INTEGER,
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);

CREATE TABLE IF NOT EXISTS stars_payments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    stars_amount INTEGER,
    diamonds_received INTEGER,
    invoice_payload TEXT,
    status TEXT DEFAULT 'pending', 
    created_at INTEGER,
    completed_at INTEGER DEFAULT 0,
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);

CREATE TABLE IF NOT EXISTS banned_users (
    user_id INTEGER PRIMARY KEY,
    banned_by INTEGER,
    reason TEXT DEFAULT '',
    banned_at INTEGER,
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);
""")
conn.commit()

@contextmanager
def transaction():
    try:
        yield
        conn.commit()
    except Exception as e:
        conn.rollback()
        logger.error(f"Transaction failed: {e}")
        raise

# Основные функции
def get_user(uid):
    cursor.execute("SELECT * FROM users WHERE user_id=?", (uid,))
    return cursor.fetchone()

def create_user(uid, username, referrer_id=0):
    with transaction():
        cursor.execute("SELECT 1 FROM users WHERE user_id=?", (uid,))
        if cursor.fetchone():
            return False
        
        # ИСПРАВЛЕНО: правильно сохраняем referrer_id
        cursor.execute("""
            INSERT INTO users (user_id, username, free_cases, last_daily, created_at, referrer_id) 
            VALUES (?, ?, 1, ?, ?, ?)
        """, (uid, username, int(time.time()), int(time.time()), referrer_id))
        
        cursor.execute("""
            INSERT OR IGNORE INTO user_levels (user_id) VALUES (?)
        """, (uid,))
        
        cursor.execute("""
            INSERT OR IGNORE INTO user_activity (user_id, last_active) VALUES (?, ?)
        """, (uid, int(time.time())))
        
        init_weekly_quests(uid)
        
        logger.info(f"Created user {uid} (@{username}), Referrer: {referrer_id}")
        return True

def init_weekly_quests(uid):
    week_number = get_current_week_number()
    quests = [
        ("open_cases", 10),
        ("win_games", 5),
        ("invite_friends", 3),
        ("spend_stars", 500),
        ("daily_login", 7),
        ("play_slot", 20),
        ("play_blackjack", 10)
    ]
    
    with transaction():
        for quest_id, goal in quests:
            cursor.execute("""
                INSERT OR IGNORE INTO weekly_quests (user_id, quest_id, week_number)
                VALUES (?, ?, ?)
            """, (uid, quest_id, week_number))

def get_current_week_number():
    return int(time.time() / (7 * 86400))

def add_referral(ref_uid):
    """Добавить бонус рефереру - ИСПРАВЛЕННАЯ ВЕРСИЯ"""
    with transaction():
        cursor.execute("SELECT user_id FROM users WHERE user_id=?", (ref_uid,))
        if not cursor.fetchone():
            return False
        
        # ИСПРАВЛЕНО: добавляем сундук и увеличиваем счетчик рефералов
        cursor.execute("""
            UPDATE users 
            SET free_cases = free_cases + 1, refs = refs + 1 
            WHERE user_id = ?
        """, (ref_uid,))
        
        week_number = get_current_week_number()
        cursor.execute("""
            UPDATE weekly_quests 
            SET progress = progress + 1 
            WHERE user_id=? AND quest_id='invite_friends' AND week_number=?
        """, (ref_uid, week_number))
        
        logger.info(f"Bonus given to referrer {ref_uid}: +1 free case, +1 ref")
        return True

def update_balance(uid, amount, reason=""):
    with transaction():
        cursor.execute("UPDATE users SET balance=balance+? WHERE user_id=?", (amount, uid))
        
        if reason:
            cursor.execute("""
                INSERT INTO transactions (user_id, type, amount, details, created_at)
                VALUES (?, ?, ?, ?, ?)
            """, (uid, reason, amount, "", int(time.time())))
        
        if amount < 0:
            week_number = get_current_week_number()
            cursor.execute("""
                UPDATE weekly_quests 
                SET progress = progress + ABS(?) 
                WHERE user_id=? AND quest_id='spend_stars' AND week_number=?
            """, (abs(amount), uid, week_number))
        
        logger.info(f"Balance update: user {uid}, amount {amount}, reason: {reason}")

def get_user_referrals(uid):
    """Получить список рефералов пользователя"""
    cursor.execute("SELECT user_id, username, created_at FROM users WHERE referrer_id=? ORDER BY created_at DESC", (uid,))
    return cursor.fetchall()

def get_referrer_info(uid):
    """Получить информацию о реферере"""
    cursor.execute("SELECT referrer_id FROM users WHERE user_id=?", (uid,))
    result = cursor.fetchone()
    if result and result[0] > 0:
        cursor.execute("SELECT user_id, username FROM users WHERE user_id=?", (result[0],))
        return cursor.fetchone()
    return None

def use_free_case(uid):
    with transaction():
        cursor.execute("UPDATE users SET free_cases=free_cases-1 WHERE user_id=?", (uid,))

def update_last_free(uid):
    with transaction():
        cursor.execute("UPDATE users SET last_free=? WHERE user_id=?", (int(time.time()), uid))

def update_case_stats(uid, win, amount_won=0):
    with transaction():
        cursor.execute("""
            UPDATE users 
            SET opened_cases=opened_cases+1, 
                wins=wins+?, 
                losses=losses+?,
                total_wagered=total_wagered+?
            WHERE user_id=?
        """, (1 if win else 0, 0 if win else 1, amount_won, uid))
        
        week_number = get_current_week_number()
        cursor.execute("""
            UPDATE weekly_quests 
            SET progress = progress + 1 
            WHERE user_id=? AND quest_id='open_cases' AND week_number=?
        """, (uid, week_number))

def update_game_stats(uid, win):
    with transaction():
        cursor.execute("""
            UPDATE users 
            SET wins=wins+?, 
                losses=losses+?
            WHERE user_id=?
        """, (1 if win else 0, 0 if win else 1, uid))
        
        week_number = get_current_week_number()
        if win:
            cursor.execute("""
                UPDATE weekly_quests 
                SET progress = progress + 1 
                WHERE user_id=? AND quest_id='win_games' AND week_number=?
            """, (uid, week_number))

def add_exp(uid, exp_amount):
    with transaction():
        cursor.execute("""
            UPDATE user_levels 
            SET exp = exp + ?, total_exp = total_exp + ? 
            WHERE user_id=?
        """, (exp_amount, exp_amount, uid))
        
        cursor.execute("SELECT level, exp FROM user_levels WHERE user_id=?", (uid,))
        level_data = cursor.fetchone()
        if level_data:
            current_level = level_data[0]
            current_exp = level_data[1]
            exp_needed = int(100 * (current_level ** 1.5))
            
            if current_exp >= exp_needed:
                new_level = current_level + 1
                new_exp = current_exp - exp_needed
                
                cursor.execute("""
                    UPDATE user_levels 
                    SET level = ?, exp = ?, last_level_up = ?
                    WHERE user_id=?
                """, (new_level, new_exp, int(time.time()), uid))
                
                level_reward = new_level * 50
                update_balance(uid, level_reward, f"level_up_{new_level}")
                return new_level, level_reward
    return None, 0

def get_user_level(uid):
    cursor.execute("""
        SELECT ul.level, ul.exp, ul.total_exp,
               (SELECT COUNT(*) FROM achievements a WHERE a.user_id = ul.user_id) as achievements_count
        FROM user_levels ul
        WHERE ul.user_id=?
    """, (uid,))
    return cursor.fetchone()

def get_weekly_quests(uid):
    week_number = get_current_week_number()
    cursor.execute("""
        SELECT quest_id, progress, completed, claimed,
               CASE quest_id
                   WHEN 'open_cases' THEN 10
                   WHEN 'win_games' THEN 5
                   WHEN 'invite_friends' THEN 3
                   WHEN 'spend_stars' THEN 500
                   WHEN 'daily_login' THEN 7
                   WHEN 'play_slot' THEN 20
                   WHEN 'play_blackjack' THEN 10
               END as goal
        FROM weekly_quests 
        WHERE user_id=? AND week_number=?
        ORDER BY quest_id
    """, (uid, week_number))
    return cursor.fetchall()

def update_quest_progress(uid, quest_id, amount=1):
    week_number = get_current_week_number()
    with transaction():
        cursor.execute("""
            UPDATE weekly_quests 
            SET progress = progress + ?
            WHERE user_id=? AND quest_id=? AND week_number=?
        """, (amount, uid, quest_id, week_number))

def complete_quest(uid, quest_id):
    week_number = get_current_week_number()
    with transaction():
        cursor.execute("""
            UPDATE weekly_quests 
            SET completed = 1
            WHERE user_id=? AND quest_id=? AND week_number=?
        """, (uid, quest_id, week_number))

def claim_quest_reward(uid, quest_id):
    week_number = get_current_week_number()
    with transaction():
        cursor.execute("""
            UPDATE weekly_quests 
            SET claimed = 1
            WHERE user_id=? AND quest_id=? AND week_number=?
        """, (uid, quest_id, week_number))

def buy_lottery_ticket(uid, draw_date):
    with transaction():
        cursor.execute("SELECT COUNT(*) FROM lottery_tickets WHERE draw_date=?", (draw_date,))
        count = cursor.fetchone()[0]
        ticket_number = count + 1
        
        cursor.execute("""
            INSERT INTO lottery_tickets (user_id, ticket_number, draw_date, created_at)
            VALUES (?, ?, ?, ?)
        """, (uid, ticket_number, draw_date, int(time.time())))
        return ticket_number

def get_user_tickets(uid, draw_date):
    cursor.execute("""
        SELECT ticket_number FROM lottery_tickets 
        WHERE user_id=? AND draw_date=?
        ORDER BY ticket_number
    """, (uid, draw_date))
    return [row[0] for row in cursor.fetchall()]

def get_all_tickets(draw_date):
    cursor.execute("""
        SELECT user_id, ticket_number FROM lottery_tickets 
        WHERE draw_date=?
        ORDER BY ticket_number
    """, (draw_date,))
    return cursor.fetchall()

def get_lottery_stats(draw_date):
    cursor.execute("""
        SELECT COUNT(DISTINCT user_id), COUNT(*) 
        FROM lottery_tickets 
        WHERE draw_date=?
    """, (draw_date,))
    return cursor.fetchone()

def add_lottery_winner(draw_date, winner_id, winner_username, prize, ticket_count):
    with transaction():
        cursor.execute("""
            INSERT INTO lottery_history (draw_date, winner_id, winner_username, prize, ticket_count, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (draw_date, winner_id, winner_username, prize, ticket_count, int(time.time())))

def get_lottery_history(limit=10):
    cursor.execute("""
        SELECT draw_date, winner_username, prize, ticket_count, created_at
        FROM lottery_history
        ORDER BY created_at DESC
        LIMIT ?
    """, (limit,))
    return cursor.fetchall()

def update_user_activity(uid):
    now = int(time.time())
    with transaction():
        cursor.execute("""
            INSERT OR REPLACE INTO user_activity (user_id, last_active, daily_login_count)
            VALUES (?, ?, COALESCE((SELECT daily_login_count FROM user_activity WHERE user_id=?) + 1, 1))
        """, (uid, now, uid))

def get_user_activity(uid):
    cursor.execute("SELECT * FROM user_activity WHERE user_id=?", (uid,))
    return cursor.fetchone()

def claim_streak_bonus(uid, bonus_amount):
    with transaction():
        cursor.execute("""
            UPDATE user_activity 
            SET streak_bonus_claimed = 1 
            WHERE user_id=?
        """, (uid,))
        update_balance(uid, bonus_amount, "streak_bonus")

def claim_first_game_bonus(uid, bonus_amount):
    with transaction():
        cursor.execute("""
            UPDATE user_activity 
            SET first_game_bonus = 1 
            WHERE user_id=?
        """, (uid,))
        update_balance(uid, bonus_amount, "first_game_bonus")

def get_daily_info(uid):
    cursor.execute("SELECT daily_streak, last_daily FROM users WHERE user_id=?", (uid,))
    row = cursor.fetchone()
    if row:
        return row
    return (0, 0)

def update_daily_streak(uid, streak):
    with transaction():
        cursor.execute("""
            UPDATE users 
            SET daily_streak=?, last_daily=?, free_cases=free_cases+1 
            WHERE user_id=?
        """, (streak, int(time.time()), uid))
        
        week_number = get_current_week_number()
        cursor.execute("""
            UPDATE weekly_quests 
            SET progress = progress + 1 
            WHERE user_id=? AND quest_id='daily_login' AND week_number=?
        """, (uid, week_number))

def get_top_balance(limit=10):
    cursor.execute("""
        SELECT username, balance 
        FROM users 
        WHERE username IS NOT NULL 
        ORDER BY balance DESC 
        LIMIT ?
    """, (limit,))
    return cursor.fetchall()

def get_top_refs(limit=10):
    cursor.execute("""
        SELECT username, refs 
        FROM users 
        WHERE username IS NOT NULL 
        ORDER BY refs DESC 
        LIMIT ?
    """, (limit,))
    return cursor.fetchall()

def get_top_players(limit=10):
    cursor.execute("""
        SELECT username, wins 
        FROM users 
        WHERE username IS NOT NULL 
        ORDER BY wins DESC 
        LIMIT ?
    """, (limit,))
    return cursor.fetchall()

def get_top_levels(limit=10):
    cursor.execute("""
        SELECT u.username, ul.level, ul.total_exp
        FROM user_levels ul
        JOIN users u ON u.user_id = ul.user_id
        WHERE u.username IS NOT NULL 
        ORDER BY ul.level DESC, ul.total_exp DESC
        LIMIT ?
    """, (limit,))
    return cursor.fetchall()

def get_all_users():
    cursor.execute("SELECT user_id, username, balance FROM users")
    return cursor.fetchall()

def get_bot_stats():
    cursor.execute("""
        SELECT 
            COUNT(*) as total_users,
            SUM(balance) as total_balance,
            SUM(opened_cases) as total_cases,
            SUM(refs) as total_refs,
            SUM(wins) as total_wins,
            (SELECT SUM(prize) FROM lottery_history) as total_lottery_paid
        FROM users
    """)
    return cursor.fetchone()

def add_sponsor_channel(channel_username, channel_name, added_by):
    with transaction():
        cursor.execute("""
            INSERT OR REPLACE INTO sponsors (channel_username, channel_name, added_by, added_at)
            VALUES (?, ?, ?, ?)
        """, (channel_username, channel_name, added_by, int(time.time())))
        return True

def remove_sponsor_channel(channel_username):
    with transaction():
        cursor.execute("DELETE FROM sponsors WHERE channel_username=?", (channel_username,))
        return cursor.rowcount > 0

def get_sponsor_channels():
    cursor.execute("SELECT channel_username, channel_name FROM sponsors")
    return cursor.fetchall()

def create_promo_code(code, reward, usage_limit, created_by, expires_hours=168):
    with transaction():
        expires_at = int(time.time()) + (expires_hours * 3600) if expires_hours > 0 else 0
        cursor.execute("""
            INSERT INTO promo_codes (code, reward, usage_limit, used_count, created_by, created_at, expires_at)
            VALUES (?, ?, ?, 0, ?, ?, ?)
        """, (code, reward, usage_limit, created_by, int(time.time()), expires_at))
        return True

def get_promo_code(code):
    cursor.execute("SELECT * FROM promo_codes WHERE code=?", (code,))
    return cursor.fetchone()

def use_promo_code(user_id, code):
    with transaction():
        promo = get_promo_code(code)
        if not promo:
            return False, "Промокод не найден"
        
        code, reward, usage_limit, used_count, created_by, created_at, expires_at = promo
        
        if expires_at > 0 and time.time() > expires_at:
            return False, "Промокод истек"
        
        if used_count >= usage_limit:
            return False, "Лимит использования исчерпан"
        
        cursor.execute("SELECT 1 FROM promo_usage WHERE user_id=? AND promo_code=?", (user_id, code))
        if cursor.fetchone():
            return False, "Вы уже использовали этот промокод"
        
        cursor.execute("""
            UPDATE promo_codes 
            SET used_count = used_count + 1 
            WHERE code=?
        """, (code,))
        
        cursor.execute("""
            INSERT INTO promo_usage (user_id, promo_code, used_at)
            VALUES (?, ?, ?)
        """, (user_id, code, int(time.time())))
        
        update_balance(user_id, reward, f"promo_code_{code}")
        return True, reward

def get_all_promo_codes():
    cursor.execute("SELECT code, reward, usage_limit, used_count, created_at, expires_at FROM promo_codes")
    return cursor.fetchall()

def create_custom_lottery(name, prize_amount, ticket_price, end_date, created_by):
    with transaction():
        cursor.execute("""
            INSERT INTO active_lotteries (name, prize_amount, ticket_price, end_date, created_by, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (name, prize_amount, ticket_price, end_date, created_by, int(time.time())))
        return cursor.lastrowid

def buy_custom_lottery_ticket(lottery_id, user_id):
    with transaction():
        cursor.execute("SELECT is_active FROM active_lotteries WHERE id=?", (lottery_id,))
        lottery = cursor.fetchone()
        if not lottery or lottery[0] == 0:
            return False, "Лотерея не активна"
        
        cursor.execute("SELECT COUNT(*) FROM custom_lottery_tickets WHERE lottery_id=?", (lottery_id,))
        count = cursor.fetchone()[0]
        ticket_number = count + 1
        
        cursor.execute("""
            INSERT INTO custom_lottery_tickets (lottery_id, user_id, ticket_number, created_at)
            VALUES (?, ?, ?, ?)
        """, (lottery_id, user_id, ticket_number, int(time.time())))
        return True, ticket_number

def create_payment(user_id, amount, invoice_id):
    with transaction():
        cursor.execute("""
            INSERT INTO payments (user_id, amount, invoice_id, created_at)
            VALUES (?, ?, ?, ?)
        """, (user_id, amount, invoice_id, int(time.time())))
        return True

def get_payment_by_invoice(invoice_id):
    cursor.execute("SELECT * FROM payments WHERE invoice_id=?", (invoice_id,))
    return cursor.fetchone()

def update_payment_status(invoice_id, status):
    with transaction():
        cursor.execute("""
            UPDATE payments 
            SET status = ?, completed_at = ? 
            WHERE invoice_id=?
        """, (status, int(time.time()) if status == 'paid' else 0, invoice_id))
        return True

def get_user_payments(user_id, limit=10):
    cursor.execute("""
        SELECT amount, status, created_at 
        FROM payments 
        WHERE user_id=? 
        ORDER BY created_at DESC 
        LIMIT ?
    """, (user_id, limit))
    return cursor.fetchall()

def add_to_whitelist(user_id, added_by):
    with transaction():
        cursor.execute("""
            INSERT OR REPLACE INTO whitelist (user_id, added_by, added_at)
            VALUES (?, ?, ?)
        """, (user_id, added_by, int(time.time())))
        return True

def remove_from_whitelist(user_id):
    with transaction():
        cursor.execute("DELETE FROM whitelist WHERE user_id=?", (user_id,))
        return cursor.rowcount > 0

def get_whitelist():
    cursor.execute("SELECT user_id FROM whitelist")
    return [row[0] for row in cursor.fetchall()]

def is_in_whitelist(user_id):
    cursor.execute("SELECT 1 FROM whitelist WHERE user_id=?", (user_id,))
    return cursor.fetchone() is not None

def create_exchange_request(user_id, username, stars_amount, gift_name, gift_emoji, diamonds_cost):
    with transaction():
        cursor.execute("""
            INSERT INTO exchange_requests (user_id, username, stars_amount, gift_name, gift_emoji, diamonds_cost, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (user_id, username, stars_amount, gift_name, gift_emoji, diamonds_cost, int(time.time())))
        return cursor.lastrowid

def get_exchange_request(request_id):
    cursor.execute("SELECT * FROM exchange_requests WHERE id=?", (request_id,))
    return cursor.fetchone()

def get_user_exchange_requests(user_id, limit=10):
    cursor.execute("""
        SELECT * FROM exchange_requests 
        WHERE user_id=? 
        ORDER BY created_at DESC 
        LIMIT ?
    """, (user_id, limit))
    return cursor.fetchall()

def get_pending_exchange_requests(limit=50):
    cursor.execute("""
        SELECT * FROM exchange_requests 
        WHERE status='pending' 
        ORDER BY created_at ASC 
        LIMIT ?
    """, (limit,))
    return cursor.fetchall()

def get_all_exchange_requests(limit=100):
    cursor.execute("""
        SELECT * FROM exchange_requests 
        ORDER BY created_at DESC 
        LIMIT ?
    """, (limit,))
    return cursor.fetchall()

def update_exchange_request_status(request_id, status, admin_id=0, comment=""):
    with transaction():
        if status == 'completed':
            cursor.execute("""
                UPDATE exchange_requests 
                SET status = ?, admin_id = ?, admin_comment = ?, completed_at = ?
                WHERE id=?
            """, (status, admin_id, comment, int(time.time()), request_id))
            
            request = get_exchange_request(request_id)
            if request:
                cursor.execute("""
                    INSERT INTO exchange_history (user_id, username, stars_amount, gift_name, diamonds_cost, status, admin_id, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (request[1], request[2], request[3], request[4], request[6], status, admin_id, int(time.time())))
        else:
            cursor.execute("""
                UPDATE exchange_requests 
                SET status = ?, admin_id = ?, admin_comment = ?
                WHERE id=?
            """, (status, admin_id, comment, request_id))
        return True

def get_exchange_stats():
    cursor.execute("""
        SELECT 
            COUNT(*) as total_requests,
            SUM(CASE WHEN status='completed' THEN 1 ELSE 0 END) as completed,
            SUM(CASE WHEN status='pending' THEN 1 ELSE 0 END) as pending,
            SUM(CASE WHEN status='rejected' THEN 1 ELSE 0 END) as rejected,
            SUM(stars_amount) as total_stars,
            SUM(diamonds_cost) as total_diamonds
        FROM exchange_requests
    """)
    return cursor.fetchone()

def create_stars_payment(user_id, stars_amount, diamonds_received, invoice_payload):
    with transaction():
        cursor.execute("""
            INSERT INTO stars_payments (user_id, stars_amount, diamonds_received, invoice_payload, created_at)
            VALUES (?, ?, ?, ?, ?)
        """, (user_id, stars_amount, diamonds_received, invoice_payload, int(time.time())))
        return cursor.lastrowid

def get_stars_payment_by_payload(invoice_payload):
    cursor.execute("SELECT * FROM stars_payments WHERE invoice_payload=?", (invoice_payload,))
    return cursor.fetchone()

def update_stars_payment_status(invoice_payload, status):
    with transaction():
        cursor.execute("""
            UPDATE stars_payments 
            SET status = ?, completed_at = ? 
            WHERE invoice_payload=?
        """, (status, int(time.time()) if status == 'paid' else 0, invoice_payload))
        return True

def get_user_stars_payments(user_id, limit=10):
    cursor.execute("""
        SELECT stars_amount, diamonds_received, status, created_at 
        FROM stars_payments 
        WHERE user_id=? 
        ORDER BY created_at DESC 
        LIMIT ?
    """, (user_id, limit))
    return cursor.fetchall()

def ban_user(user_id, admin_id, reason=""):
    with transaction():
        cursor.execute("""
            INSERT OR REPLACE INTO banned_users (user_id, banned_by, reason, banned_at)
            VALUES (?, ?, ?, ?)
        """, (user_id, admin_id, reason, int(time.time())))
        return True

def unban_user(user_id):
    with transaction():
        cursor.execute("DELETE FROM banned_users WHERE user_id=?", (user_id,))
        return cursor.rowcount > 0

def is_user_banned(user_id):
    cursor.execute("SELECT 1 FROM banned_users WHERE user_id=?", (user_id,))
    return cursor.fetchone() is not None

def check_and_create_tables():
    tables = ['users', 'achievements', 'transactions', 'user_levels', 'weekly_quests', 
              'lottery_tickets', 'lottery_history', 'user_activity', 'sponsors',
              'promo_codes', 'promo_usage', 'active_lotteries', 'custom_lottery_tickets',
              'payments', 'whitelist', 'exchange_requests', 'exchange_history', 
              'stars_payments', 'banned_users']
    
    for table in tables:
        cursor.execute(f"""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='{table}'
        """)
        if not cursor.fetchone():
            logger.info(f"Table {table} not found, creating...")
    
    conn.commit()

check_and_create_tables()