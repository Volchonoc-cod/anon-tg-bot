"""
Утилиты для работы с базой данных
"""
import logging
from sqlalchemy import func
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

def get_stats():
    """Получение статистики из БД"""
    try:
        from app.database import get_db
        from app.models import User, AnonMessage, Payment
        
        db = next(get_db())
        
        total_users = db.query(User).count()
        total_messages = db.query(AnonMessage).count()
        active_users = db.query(User).filter(User.anon_link_uid.isnot(None)).count()
        total_payments = db.query(Payment).filter(Payment.status == 'completed').count()
        
        db.close()
        
        return {
            'total_users': total_users,
            'total_messages': total_messages,
            'active_users': active_users,
            'total_payments': total_payments
        }
        
    except Exception as e:
        logger.error(f"Ошибка получения статистики: {e}")
        return {
            'total_users': 0,
            'total_messages': 0,
            'active_users': 0,
            'total_payments': 0
        }
