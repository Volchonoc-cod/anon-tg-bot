"""
Работа с базой данных через SQLAlchemy
"""
import os
import time
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base
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

def get_db():
    """Фабрика сессий для FastAPI/Dependency Injection"""
    db = get_session_local()()
    try:
        yield db
    finally:
        db.close()

def create_tables():
    """Создает все таблицы в базе данных"""
    try:
        # Импортируем модели, чтобы они зарегистрировались у Base
        from .models import User, AnonMessage, Payment
        Base.metadata.create_all(bind=get_engine())
        logger.info("✅ Таблицы БД созданы/проверены")
        return True
    except Exception as e:
        logger.error(f"❌ Ошибка создания таблиц БД: {e}")
        return False

def force_reconnect():
    """
    Принудительно переподключиться к базе данных
    Полезно после восстановления БД из бэкапа
    """
    global _engine, engine, _SessionLocal, _last_reconnect
    
    logger.info("🔄 Принудительное переподключение к БД...")
    
    try:
        # 1. Закрываем старые соединения
        if _engine:
            _engine.dispose()
            logger.debug("✅ Старые соединения закрыты")
        
        # 2. Сбрасываем кэш
        _engine = None
        engine = None
        _SessionLocal = None
        
        # 3. Даем время на закрытие (особенно для SQLite)
        time.sleep(1)
        
        # 4. Создаем новый engine
        new_engine = create_engine(
            DATABASE_URL,
            echo=False,
            pool_pre_ping=True,
            connect_args={
                "check_same_thread": False,
                "timeout": 30
            } if "sqlite" in DATABASE_URL else {}
        )
        
        # 5. Тестируем подключение
        with new_engine.connect() as conn:
            conn.execute("SELECT 1")
        
        # 6. Обновляем глобальные переменные
        _engine = new_engine
        engine = new_engine
        _SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_engine)
        
        _last_reconnect = time.time()
        
        logger.info("✅ БД успешно переподключена")
        return True
        
    except Exception as e:
        logger.error(f"❌ Ошибка переподключения БД: {e}")
        return False

def check_database_connection():
    """Проверить соединение с БД"""
    try:
        engine = get_engine()
        with engine.connect() as conn:
            result = conn.execute("SELECT 1")
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

# Экспортируемые объекты для обратной совместимости
__all__ = ['get_engine', 'get_engine_instance', 'engine', 'Base', 'get_db', 'get_session_local', 'create_tables']
