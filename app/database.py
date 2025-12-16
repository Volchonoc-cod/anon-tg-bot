"""
Работа с базой данных через SQLAlchemy
"""
import os
import time
from sqlalchemy import create_engine, text, inspect
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import close_all_sessions
import logging

logger = logging.getLogger(__name__)

# Создаем Base здесь для импорта в другие модули
Base = declarative_base()

# Путь к базе данных в папке data
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, 'data')
os.makedirs(DATA_DIR, exist_ok=True)

DATABASE_URL = os.getenv('DATABASE_URL', f'sqlite:///{os.path.join(DATA_DIR, "bot.db")}')

# Если PostgreSQL URL (как на Railway), преобразуем его
if DATABASE_URL.startswith('postgres://'):
    DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)

# Глобальные переменные для управления соединением
_engine = None
engine = None  # Для обратной совместимости
_SessionLocal = None
_scoped_session = None
_last_reconnect = None

def get_engine():
    """Получить или создать engine"""
    global _engine, engine
    if _engine is None:
        _engine = create_engine(
            DATABASE_URL,
            echo=False,
            pool_pre_ping=True,  # Проверка подключения перед использованием
            connect_args={
                "check_same_thread": False,
                "timeout": 30
            } if "sqlite" in DATABASE_URL else {}
        )
        engine = _engine  # Устанавливаем для обратной совместимости
        logger.info(f"✅ Engine БД создан: {DATABASE_URL}")
    return _engine

def get_engine_instance():
    """Получить engine (для обратной совместимости)"""
    return get_engine()

def get_session_local():
    """Получить sessionmaker"""
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=get_engine())
    return _SessionLocal

def get_scoped_session():
    """Получить scoped_session для управления сессиями"""
    global _scoped_session
    if _scoped_session is None:
        _scoped_session = scoped_session(get_session_local())
    return _scoped_session

def get_db():
    """Фабрика сессий для FastAPI/Dependency Injection"""
    SessionLocal = get_session_local()
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def create_tables():
    """Создает все таблицы в базе данных"""
    try:
        # Импортируем модели, чтобы они зарегистрировались у Base
        from app.models import User, AnonMessage, Payment
        Base.metadata.create_all(bind=get_engine())
        logger.info("✅ Таблицы БД созданы/проверены")
        
        # Проверяем что таблицы создались
        engine = get_engine()
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        
        required_tables = ['users', 'anon_messages', 'payments']
        created_tables = []
        missing_tables = []
        
        for table in required_tables:
            if table in tables:
                created_tables.append(table)
            else:
                missing_tables.append(table)
        
        if missing_tables:
            logger.error(f"❌ Отсутствуют таблицы: {missing_tables}")
            
            # Пробуем создать недостающие таблицы вручную через SQL
            logger.info("🔄 Создаю недостающие таблицы вручную...")
            with engine.connect() as conn:
                for table in missing_tables:
                    if table == 'users':
                        conn.execute(text('''
                        CREATE TABLE IF NOT EXISTS users (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            telegram_id INTEGER UNIQUE NOT NULL,
                            username TEXT,
                            first_name TEXT NOT NULL,
                            last_name TEXT,
                            anon_link_uid TEXT UNIQUE,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            is_banned BOOLEAN DEFAULT FALSE,
                            ban_reason TEXT,
                            available_reveals INTEGER DEFAULT 0,
                            total_reveals_used INTEGER DEFAULT 0
                        )
                        '''))
                    elif table == 'anon_messages':
                        conn.execute(text('''
                        CREATE TABLE IF NOT EXISTS anon_messages (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            sender_id INTEGER,
                            receiver_id INTEGER NOT NULL,
                            message_text TEXT NOT NULL,
                            message_type TEXT DEFAULT 'text',
                            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            is_read BOOLEAN DEFAULT FALSE,
                            read_at TIMESTAMP,
                            is_revealed BOOLEAN DEFAULT FALSE,
                            revealed_at TIMESTAMP,
                            parent_message_id INTEGER,
                            FOREIGN KEY (sender_id) REFERENCES users (id),
                            FOREIGN KEY (receiver_id) REFERENCES users (id),
                            FOREIGN KEY (parent_message_id) REFERENCES anon_messages (id)
                        )
                        '''))
                    elif table == 'payments':
                        conn.execute(text('''
                        CREATE TABLE IF NOT EXISTS payments (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            user_id INTEGER NOT NULL,
                            payment_id TEXT UNIQUE,
                            payment_type TEXT NOT NULL,
                            amount INTEGER NOT NULL,
                            currency TEXT DEFAULT 'RUB',
                            status TEXT DEFAULT 'pending',
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            completed_at TIMESTAMP,
                            metadata TEXT,
                            FOREIGN KEY (user_id) REFERENCES users (id)
                        )
                        '''))
                conn.commit()
            
            # Проверяем снова
            tables = inspector.get_table_names()
            missing_tables = [t for t in required_tables if t not in tables]
            if missing_tables:
                logger.error(f"❌ Не удалось создать таблицы: {missing_tables}")
                return False
            else:
                logger.info("✅ Все таблицы созданы вручную")
        
        logger.info(f"📊 Создано таблиц: {len(created_tables)} ({', '.join(created_tables)})")
        return True
        
    except Exception as e:
        logger.error(f"❌ Ошибка создания таблиц БД: {e}")
        import traceback
        traceback.print_exc()
        return False

def init_db():
    """Инициализация базы данных - основная функция для запуска"""
    logger.info("🚀 ИНИЦИАЛИЗАЦИЯ БАЗЫ ДАННЫХ...")
    
    # Создаем директорию если ее нет
    os.makedirs('data', exist_ok=True)
    
    # Создаем таблицы
    success = create_tables()
    
    if success:
        # Проверяем структуру
        engine = get_engine()
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        
        logger.info(f"📊 Итоговая структура БД: {len(tables)} таблиц")
        for table in tables:
            logger.info(f"  - {table}")
            
            # Показываем структуру таблицы
            try:
                columns = inspector.get_columns(table)
                logger.info(f"    Колонки: {len(columns)}")
                for col in columns[:3]:  # Первые 3 колонки для краткости
                    logger.info(f"      - {col['name']} ({col['type']})")
                if len(columns) > 3:
                    logger.info(f"      - ... и еще {len(columns) - 3} колонок")
            except:
                pass
        
        # Проверяем количество записей
        logger.info("📈 Проверка записей в таблицах:")
        with engine.connect() as conn:
            for table in tables:
                try:
                    result = conn.execute(text(f"SELECT COUNT(*) FROM {table}"))
                    count = result.scalar() or 0
                    logger.info(f"  - {table}: {count} записей")
                except Exception as e:
                    logger.warning(f"  - {table}: ошибка чтения ({e})")
        
        logger.info("✅ База данных успешно инициализирована!")
    else:
        logger.error("❌ Ошибка инициализации базы данных!")
    
    return success

def force_reconnect():
    """
    Принудительно переподключиться к базе данных
    Полезно после восстановления БД из бэкапа
    """
    global _engine, engine, _SessionLocal, _scoped_session, _last_reconnect
    
    logger.info("🔁 ПРИНУДИТЕЛЬНОЕ ПЕРЕПОДКЛЮЧЕНИЕ К БД...")
    
    try:
        # 1. Закрываем все существующие сессии
        try:
            close_all_sessions()
            logger.info("✅ Все SQLAlchemy сессии закрыты")
        except Exception as e:
            logger.warning(f"⚠️ Ошибка при закрытии сессий: {e}")
        
        # 2. Закрываем старый engine если существует
        if _engine:
            try:
                _engine.dispose()
                logger.info("✅ Старый engine закрыт")
            except Exception as e:
                logger.warning(f"⚠️ Ошибка при закрытии engine: {e}")
        
        # 3. Сбрасываем ВЕСЬ кэш SQLAlchemy
        try:
            # Очищаем кэш метаданных
            Base.metadata.clear()
            logger.info("✅ Кэш метаданных очищен")
        except Exception as e:
            logger.warning(f"⚠️ Ошибка очистки кэша метаданных: {e}")
        
        # 4. Сбрасываем все глобальные переменные
        _engine = None
        engine = None
        _SessionLocal = None
        _scoped_session = None
        
        # 5. Даем время на закрытие всех соединений
        time.sleep(2)
        
        logger.info("🔄 Создаю новое подключение...")
        
        # 6. Создаем новый engine
        new_engine = create_engine(
            DATABASE_URL,
            echo=False,
            pool_pre_ping=True,
            connect_args={
                "check_same_thread": False,
                "timeout": 30
            } if "sqlite" in DATABASE_URL else {}
        )
        
        # 7. Тестируем подключение С ИСПОЛЬЗОВАНИЕМ text()
        with new_engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            logger.info(f"✅ Тест подключения: {result.scalar()}")
            
            # Проверяем наличие таблиц С ИСПОЛЬЗОВАНИЕМ text()
            result = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))
            tables = [row[0] for row in result.fetchall()]
            logger.info(f"📊 Таблицы в БД после переподключения: {len(tables)} шт")
            
            # Если есть таблица users, показываем статистику
            if 'users' in tables:
                result = conn.execute(text("SELECT COUNT(*) FROM users"))
                user_count = result.scalar()
                logger.info(f"👥 Пользователей в БД: {user_count}")
        
        # 8. Обновляем глобальные переменные
        _engine = new_engine
        engine = new_engine
        _SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_engine)
        _scoped_session = scoped_session(_SessionLocal)
        
        _last_reconnect = time.time()
        
        logger.info("✅ БД успешно переподключена, все кэши очищены")
        return True
        
    except Exception as e:
        logger.error(f"❌ Ошибка переподключения БД: {e}")
        import traceback
        traceback.print_exc()
        return False

def check_database_connection():
    """Проверить соединение с БД"""
    try:
        engine = get_engine()
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            return {
                "success": True,
                "message": "✅ Соединение с БД активно",
                "test_query": result.fetchone()[0] == 1
            }
    except Exception as e:
        return {
            "success": False,
            "message": f"❌ Ошибка подключения к БД: {e}",
            "error": str(e)
        }

def get_database_info():
    """Получить информацию о подключении к БД"""
    return {
        "database_url": DATABASE_URL,
        "engine_exists": _engine is not None,
        "session_exists": _SessionLocal is not None,
        "last_reconnect": _last_reconnect,
        "is_sqlite": "sqlite" in DATABASE_URL,
        "is_postgres": "postgresql" in DATABASE_URL,
        "data_dir": DATA_DIR
    }

def get_direct_connection():
    """Получить прямое соединение с БД (без ORM)"""
    engine = get_engine()
    return engine.connect()

# Функция для получения актуальной статистики напрямую
def get_direct_stats():
    """Получить статистику напрямую из БД"""
    try:
        engine = get_engine()
        with engine.connect() as conn:
            # Пользователи - ВСЕ ЗАПРОСЫ С text()
            result = conn.execute(text("SELECT COUNT(*) FROM users"))
            total_users = result.scalar() or 0
            
            result = conn.execute(text("SELECT COUNT(*) FROM users WHERE anon_link_uid IS NOT NULL"))
            active_users = result.scalar() or 0
            
            # Сообщения
            result = conn.execute(text("SELECT COUNT(*) FROM anon_messages"))
            total_messages = result.scalar() or 0
            
            # Платежи
            result = conn.execute(text("SELECT COUNT(*) FROM payments WHERE status = 'completed'"))
            total_payments = result.scalar() or 0
            
            return {
                'total_users': total_users,
                'active_users': active_users,
                'total_messages': total_messages,
                'total_payments': total_payments
            }
    except Exception as e:
        logger.error(f"Ошибка получения прямой статистики: {e}")
        return {
            'total_users': 0,
            'active_users': 0,
            'total_messages': 0,
            'total_payments': 0
        }

# Экспортируемые объекты для обратной совместимости
__all__ = [
    'get_engine', 
    'get_engine_instance', 
    'engine', 
    'Base', 
    'get_db', 
    'get_session_local',
    'get_scoped_session',
    'create_tables',
    'init_db',  # <-- ДОБАВЛЕНО
    'force_reconnect',
    'check_database_connection',
    'get_database_info',
    'get_direct_connection',
    'get_direct_stats'
]
