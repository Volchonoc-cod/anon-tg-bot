"""
Утилиты для работы с базой данных для веб-панели
"""
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

def get_stats():
    """Получение статистики из БД для веб-панели"""
    try:
        from app.database import get_direct_stats
        
        # Используем функцию для получения прямой статистики
        stats = get_direct_stats()
        
        return {
            'total_users': stats.get('total_users', 0),
            'total_messages': stats.get('total_messages', 0),
            'active_users': stats.get('active_users', 0),
            'total_payments': stats.get('total_payments', 0)
        }
        
    except Exception as e:
        logger.error(f"Ошибка получения статистики для веб-панели: {e}")
        return {
            'total_users': 0,
            'total_messages': 0,
            'active_users': 0,
            'total_payments': 0
        }

def get_detailed_stats():
    """Получение детальной статистики"""
    try:
        from app.database import get_engine
        
        engine = get_engine()
        
        with engine.connect() as conn:
            # Общая статистика
            result = conn.execute("SELECT COUNT(*) FROM users")
            total_users = result.scalar() or 0
            
            today = datetime.now().date().strftime('%Y-%m-%d')
            result = conn.execute(f"SELECT COUNT(*) FROM users WHERE DATE(created_at) = '{today}'")
            today_users = result.scalar() or 0
            
            week_ago = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
            result = conn.execute(f"SELECT COUNT(*) FROM users WHERE DATE(created_at) >= '{week_ago}'")
            week_users = result.scalar() or 0
            
            result = conn.execute("SELECT COUNT(*) FROM anon_messages")
            total_messages = result.scalar() or 0
            
            result = conn.execute(f"SELECT COUNT(*) FROM anon_messages WHERE DATE(timestamp) = '{today}'")
            today_messages = result.scalar() or 0
            
            result = conn.execute(f"SELECT COUNT(*) FROM anon_messages WHERE DATE(timestamp) >= '{week_ago}'")
            week_messages = result.scalar() or 0
            
            result = conn.execute("SELECT COUNT(*) FROM payments WHERE status = 'completed'")
            total_payments = result.scalar() or 0
            
            result = conn.execute(f"SELECT COUNT(*) FROM payments WHERE status = 'completed' AND DATE(created_at) >= '{week_ago}'")
            week_payments = result.scalar() or 0
            
            result = conn.execute("SELECT COALESCE(SUM(amount), 0) FROM payments WHERE status = 'completed'")
            total_revenue = result.scalar() or 0
            
            result = conn.execute(f"SELECT COALESCE(SUM(amount), 0) FROM payments WHERE status = 'completed' AND DATE(created_at) >= '{week_ago}'")
            week_revenue = result.scalar() or 0
            
            result = conn.execute(f"SELECT COUNT(DISTINCT sender_id) FROM anon_messages WHERE DATE(timestamp) >= '{week_ago}'")
            active_users = result.scalar() or 0
            
        return {
            'total_users': total_users,
            'today_users': today_users,
            'week_users': week_users,
            'total_messages': total_messages,
            'today_messages': today_messages,
            'week_messages': week_messages,
            'total_payments': total_payments,
            'week_payments': week_payments,
            'total_revenue': total_revenue / 100,  # В рублях
            'week_revenue': week_revenue / 100,    # В рублях
            'active_users': active_users
        }
        
    except Exception as e:
        logger.error(f"Ошибка получения детальной статистики: {e}")
        return {
            'total_users': 0,
            'today_users': 0,
            'week_users': 0,
            'total_messages': 0,
            'today_messages': 0,
            'week_messages': 0,
            'total_payments': 0,
            'week_payments': 0,
            'total_revenue': 0,
            'week_revenue': 0,
            'active_users': 0
        }

def get_recent_activity(limit=10):
    """Получить последнюю активность"""
    try:
        from app.database import get_engine
        
        engine = get_engine()
        
        with engine.connect() as conn:
            # Последние сообщения
            result = conn.execute(f"""
                SELECT am.id, am.text, am.timestamp, 
                       u1.first_name as sender_name, 
                       u2.first_name as receiver_name
                FROM anon_messages am
                LEFT JOIN users u1 ON am.sender_id = u1.id
                LEFT JOIN users u2 ON am.receiver_id = u2.id
                ORDER BY am.timestamp DESC
                LIMIT {limit}
            """)
            recent_messages = []
            for row in result.fetchall():
                recent_messages.append({
                    'id': row[0],
                    'text': row[1][:50] + '...' if len(row[1]) > 50 else row[1],
                    'timestamp': row[2],
                    'sender': row[3] or 'Аноним',
                    'receiver': row[4]
                })
            
            # Последние пользователи
            result = conn.execute(f"""
                SELECT id, telegram_id, first_name, username, created_at
                FROM users
                ORDER BY created_at DESC
                LIMIT {limit}
            """)
            recent_users = []
            for row in result.fetchall():
                recent_users.append({
                    'id': row[0],
                    'telegram_id': row[1],
                    'first_name': row[2],
                    'username': row[3] or 'нет',
                    'created_at': row[4]
                })
            
            # Последние платежи
            result = conn.execute(f"""
                SELECT p.id, p.amount, p.status, p.created_at, u.first_name
                FROM payments p
                LEFT JOIN users u ON p.user_id = u.id
                ORDER BY p.created_at DESC
                LIMIT {limit}
            """)
            recent_payments = []
            for row in result.fetchall():
                recent_payments.append({
                    'id': row[0],
                    'amount': row[1] / 100,  # В рублях
                    'status': row[2],
                    'created_at': row[3],
                    'user': row[4]
                })
        
        return {
            'recent_messages': recent_messages,
            'recent_users': recent_users,
            'recent_payments': recent_payments
        }
        
    except Exception as e:
        logger.error(f"Ошибка получения последней активности: {e}")
        return {
            'recent_messages': [],
            'recent_users': [],
            'recent_payments': []
        }
