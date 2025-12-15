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
        
        # Импортируем необходимые модули
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
            
            # Пробуем создать недостающие таблицы вручную
            logger.info("🔄 Пробую создать недостающие таблицы вручную...")
            for table in missing_tables:
                if table == 'users':
                    User.__table__.create(bind=engine, checkfirst=True)
                elif table == 'anon_messages':
                    AnonMessage.__table__.create(bind=engine, checkfirst=True)
                elif table == 'payments':
                    Payment.__table__.create(bind=engine, checkfirst=True)
            
            # Проверяем снова
            tables = inspector.get_table_names()
            missing_tables = [t for t in required_tables if t not in tables]
            if missing_tables:
                raise Exception(f"Не удалось создать таблицы: {missing_tables}")
            else:
                logger.info("✅ Все таблицы созданы (вручную)")
        else:
            logger.info("✅ Все обязательные таблицы созданы")
        
        # Получаем статистику по таблицам
        for table_name in tables:
            try:
                with engine.connect() as conn:
                    result = conn.execute(f"SELECT COUNT(*) FROM {table_name}")
                    count = result.scalar()
                    logger.info(f"  📋 {table_name}: {count} записей")
            except Exception as e:
                logger.warning(f"  ⚠️ Не удалось получить статистику для {table_name}: {e}")
        
        logger.info("✅ Создание таблиц завершено успешно!")
        
    except Exception as e:
        logger.error(f"❌ Критическая ошибка при создании таблиц: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
