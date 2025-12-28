"""
Вспомогательные функции для работы с базой данных
"""
from sqlalchemy import text
from .database import get_engine
import logging

logger = logging.getLogger(__name__)

def safe_execute_query(query, params=None):
    """Безопасное выполнение SQL-запроса с использованием text()"""
    try:
        engine = get_engine()
        with engine.connect() as conn:
            if params:
                result = conn.execute(text(query), params)
            else:
                result = conn.execute(text(query))
            return result
    except Exception as e:
        logger.error(f"Ошибка выполнения запроса: {e}\nЗапрос: {query}")
        raise

def safe_execute_query_fetchone(query, params=None):
    """Безопасное выполнение запроса с возвратом одной строки"""
    try:
        engine = get_engine()
        with engine.connect() as conn:
            result = conn.execute(text(query), params or {})
            return result.fetchone()
    except Exception as e:
        logger.error(f"Ошибка выполнения запроса fetchone: {e}")
        return None

def safe_execute_query_fetchall(query, params=None):
    """Безопасное выполнение запроса с возвратом всех строк"""
    try:
        engine = get_engine()
        with engine.connect() as conn:
            result = conn.execute(text(query), params or {})
            return result.fetchall()
    except Exception as e:
        logger.error(f"Ошибка выполнения запроса fetchall: {e}")
        return []

def safe_execute_scalar(query, params=None):
    """Безопасное выполнение запроса с возвратом скалярного значения"""
    try:
        engine = get_engine()
        with engine.connect() as conn:
            result = conn.execute(text(query), params or {})
            return result.scalar()
    except Exception as e:
        logger.error(f"Ошибка выполнения скалярного запроса: {e}")
        return 0

def get_table_stats():
    """Получить статистику по всем таблицам"""
    try:
        engine = get_engine()
        with engine.connect() as conn:
            # Получаем список всех таблиц
            result = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))
            tables = [row[0] for row in result.fetchall()]
            
            stats = {}
            for table in tables:
                result = conn.execute(text(f"SELECT COUNT(*) FROM {table}"))
                count = result.scalar() or 0
                stats[table] = count
            
            return stats
    except Exception as e:
        logger.error(f"Ошибка получения статистики таблиц: {e}")
        return {}

def get_user_by_id(user_id):
    """Получить пользователя по ID"""
    try:
        result = safe_execute_query_fetchone(
            "SELECT * FROM users WHERE telegram_id = :user_id",
            {"user_id": user_id}
        )
        return result
    except Exception as e:
        logger.error(f"Ошибка получения пользователя {user_id}: {e}")
        return None

def get_users_count() -> int:
    """Получить количество пользователей"""
    try:
        return safe_execute_scalar("SELECT COUNT(*) FROM users")
    except Exception as e:
        logger.error(f"Ошибка получения количества пользователей: {e}")
        return 0

def get_messages_count():
    """Получить количество сообщений"""
    try:
        return safe_execute_scalar("SELECT COUNT(*) FROM anon_messages")
    except Exception as e:
        logger.error(f"Ошибка получения количества сообщений: {e}")
        return 0

def get_payments_count():
    """Получить количество платежей"""
    try:
        return safe_execute_scalar("SELECT COUNT(*) FROM payments WHERE status = 'completed'")
    except Exception as e:
        logger.error(f"Ошибка получения количества платежей: {e}")
        return 0

def get_revenue():
    """Получить общую выручку"""
    try:
        return safe_execute_scalar("SELECT COALESCE(SUM(amount), 0) FROM payments WHERE status = 'completed'")
    except Exception as e:
        logger.error(f"Ошибка получения выручки: {e}")
        return 0

def get_active_users_count() -> int:
    """Получить количество активных пользователей (с ссылками)"""
    try:
        return safe_execute_scalar("SELECT COUNT(*) FROM users WHERE anon_link_uid IS NOT NULL")
    except Exception as e:
        logger.error(f"Ошибка получения активных пользователей: {e}")
        return 0

def get_today_users() -> int:
    """Получить количество новых пользователей сегодня"""
    try:
        return safe_execute_scalar("SELECT COUNT(*) FROM users WHERE DATE(created_at) = DATE('now')")
    except Exception as e:
        logger.error(f"Ошибка получения новых пользователей сегодня: {e}")
        return 0

def get_week_messages() -> int:
    """Получить количество сообщений за последнюю неделю"""
    try:
        return safe_execute_scalar(
            "SELECT COUNT(*) FROM anon_messages WHERE timestamp >= datetime('now', '-7 days')"
        )
    except Exception as e:
        logger.error(f"Ошибка получения сообщений за неделю: {e}")
        return 0

# Экспортируем все функции
__all__ = [
    'safe_execute_query',
    'safe_execute_query_fetchone',
    'safe_execute_query_fetchall',
    'safe_execute_scalar',
    'get_table_stats',
    'get_user_by_id',
    'get_users_count',
    'get_messages_count',
    'get_payments_count',
    'get_revenue',
    'get_active_users_count',
    'get_today_users',
    'get_week_messages'
]
