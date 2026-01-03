from config import ADMINS
from database import is_user_banned

def is_admin(user_id):
    """Проверка, является ли пользователь администратором"""
    return user_id in ADMINS

def get_admin_ids():
    """Получить список ID администраторов"""
    return ADMINS.copy()

def is_user_allowed(user_id):
    """Проверка, разрешен ли пользователю доступ к боту"""
    if is_admin(user_id):
        return True
    
    # Проверка бана
    if is_user_banned(user_id):
        return False
    
    # Дополнительные проверки (белый список и т.д.) могут быть добавлены здесь
    return True