#!/usr/bin/env python3
"""
Скрипт для принудительного создания таблиц в базе данных
Запускается перед стартом приложения на Render
"""
import sys
import os
import logging

# Добавляем путь к проекту
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def main():
    """Создает таблицы в базе данных"""
    try:
        logger.info("🔄 Инициализация создания таблиц БД...")
        
        # Создаем папки если их нет
        os.makedirs('data', exist_ok=True)
        os.makedirs('backups', exist_ok=True)
        os.makedirs('logs', exist_ok=True)
        os.makedirs('uploads', exist_ok=True)
        
        # Импортируем необходимые модули
        logger.info("📦 Импорт модулей...")
        from app.database import get_engine, Base, create_tables
        from app.models import User, AnonMessage, Payment
        
        logger.info("🔄 Получение engine БД...")
        engine = get_engine()
        
        logger.info("🔄 Создание таблиц...")
        
        # Способ 1: Используем функцию create_tables из database.py
        logger.info("🔧 Способ 1: Использую create_tables()...")
        if create_tables():
            logger.info("✅ Таблицы БД созданы успешно (способ 1)")
        else:
            logger.warning("⚠️ Способ 1 не сработал, пробую способ 2...")
            
            # Способ 2: Создаем таблицы напрямую
            try:
                Base.metadata.create_all(bind=engine)
                logger.info("✅ Таблицы БД созданы успешно (способ 2)")
            except Exception as e2:
                logger.error(f"❌ Способ 2 также не сработал: {e2}")
                logger.info("🔧 Пробую способ 3: создание таблиц по одной...")
                
                # Способ 3: Создаем таблицы по одной
                try:
                    User.__table__.create(bind=engine, checkfirst=True)
                    logger.info("✅ Таблица 'users' создана")
                    
                    Payment.__table__.create(bind=engine, checkfirst=True)
                    logger.info("✅ Таблица 'payments' создана")
                    
                    AnonMessage.__table__.create(bind=engine, checkfirst=True)
                    logger.info("✅ Таблица 'anon_messages' создана")
                    
                    logger.info("✅ Все таблицы созданы (способ 3)")
                except Exception as e3:
                    logger.error(f"❌ Способ 3 не сработал: {e3}")
                    raise
        
        # Проверяем что таблицы создались
        from sqlalchemy import inspect
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        
        logger.info(f"📊 Таблицы в БД: {tables}")
        
        # Проверяем обязательные таблицы
        required_tables = ['users', 'anon_messages', 'payments']
        missing_tables = [t for t in required_tables if t not in tables]
        
        if missing_tables:
            logger.error(f"❌ Отсутствуют таблицы: {missing_tables}")
            
            # Пробуем создать недостающие таблицы вручную через SQL
            logger.info("🔄 Пробую создать недостающие таблицы через SQL...")
            with engine.connect() as conn:
                if 'users' in missing_tables:
                    conn.execute("""
                        CREATE TABLE IF NOT EXISTS users (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            telegram_id INTEGER UNIQUE NOT NULL,
                            username TEXT,
                            first_name TEXT NOT NULL,
                            last_name TEXT,
                            anon_link_uid TEXT UNIQUE,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            balance INTEGER DEFAULT 0,
                            premium_until TIMESTAMP,
                            available_reveals INTEGER DEFAULT 0
                        )
                    """)
                    logger.info("✅ Таблица 'users' создана через SQL")
                
                if 'payments' in missing_tables:
                    conn.execute("""
                        CREATE TABLE IF NOT EXISTS payments (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            user_id INTEGER NOT NULL,
                            amount INTEGER NOT NULL,
                            payment_type TEXT NOT NULL,
                            status TEXT DEFAULT 'pending',
                            yookassa_payment_id TEXT,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            completed_at TIMESTAMP,
                            FOREIGN KEY (user_id) REFERENCES users (id)
                        )
                    """)
                    logger.info("✅ Таблица 'payments' создана через SQL")
                
                if 'anon_messages' in missing_tables:
                    conn.execute("""
                        CREATE TABLE IF NOT EXISTS anon_messages (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            sender_id INTEGER,
                            receiver_id INTEGER NOT NULL,
                            text TEXT NOT NULL,
                            is_anonymous BOOLEAN DEFAULT TRUE,
                            is_revealed BOOLEAN DEFAULT FALSE,
                            is_reported BOOLEAN DEFAULT FALSE,
                            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            reply_to_message_id INTEGER,
                            FOREIGN KEY (sender_id) REFERENCES users (id),
                            FOREIGN KEY (receiver_id) REFERENCES users (id),
                            FOREIGN KEY (reply_to_message_id) REFERENCES anon_messages (id)
                        )
                    """)
                    logger.info("✅ Таблица 'anon_messages' создана через SQL")
                
                conn.commit()
            
            # Проверяем снова
            tables = inspector.get_table_names()
            missing_tables = [t for t in required_tables if t not in tables]
            if missing_tables:
                raise Exception(f"Не удалось создать таблицы: {missing_tables}")
            else:
                logger.info("✅ Все таблицы созданы (через SQL)")
        else:
            logger.info("✅ Все обязательные таблицы созданы")
        
        # Получаем статистику по таблицам
        logger.info("📈 Получаю статистику по таблицам...")
        for table_name in tables:
            try:
                with engine.connect() as conn:
                    result = conn.execute(f"SELECT COUNT(*) FROM {table_name}")
                    count = result.scalar() or 0
                    logger.info(f"  📋 {table_name}: {count} записей")
            except Exception as e:
                logger.warning(f"  ⚠️ Не удалось получить статистику для {table_name}: {e}")
        
        # Создаем индексы если их нет
        logger.info("🔍 Проверяю индексы...")
        try:
            with engine.connect() as conn:
                # Проверяем существующие индексы
                result = conn.execute("SELECT name FROM sqlite_master WHERE type='index'")
                existing_indexes = [row[0] for row in result.fetchall()]
                
                # Создаем недостающие индексы
                indexes_to_create = [
                    ("idx_user_telegram_id", "users", "telegram_id"),
                    ("idx_user_anon_link", "users", "anon_link_uid"),
                    ("idx_messages_receiver", "anon_messages", "receiver_id"),
                    ("idx_messages_timestamp", "anon_messages", "timestamp"),
                    ("idx_payment_user", "payments", "user_id"),
                    ("idx_payment_status", "payments", "status"),
                ]
                
                for index_name, table, column in indexes_to_create:
                    if index_name not in existing_indexes:
                        conn.execute(f"CREATE INDEX IF NOT EXISTS {index_name} ON {table} ({column})")
                        logger.info(f"  ✅ Создан индекс: {index_name}")
                    else:
                        logger.info(f"  ℹ️ Индекс уже существует: {index_name}")
                
                conn.commit()
        except Exception as e:
            logger.warning(f"⚠️ Ошибка при создании индексов: {e}")
        
        logger.info("✅ Создание таблиц завершено успешно!")
        
    except Exception as e:
        logger.error(f"❌ Критическая ошибка при создании таблиц: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
