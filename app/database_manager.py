"""
Менеджер базы данных с автоматическим бэкапом/восстановлением
"""
import os
import sqlite3
import shutil
import json
import asyncio
import aiosqlite
from datetime import datetime, timedelta
import logging
from typing import Optional, List, Dict, Any
import threading
import signal
import sys

logger = logging.getLogger(__name__)


class DatabaseManager:
    """Класс для управления базой данных с бэкапами"""
    
    def __init__(self, db_path: str = 'data/bot.db'):
        self.db_path = db_path
        self.backup_dir = 'backups'
        self.metadata_file = 'data/db_metadata.json'
        
        # Создаем необходимые директории
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        os.makedirs(self.backup_dir, exist_ok=True)
        
        # Настройки
        self.auto_backup_on_exit = True
        self.auto_restore_on_start = True
        self.max_backups = 10
        self.backup_interval_hours = 24
        
        # Флаг для отслеживания восстановления
        self._restored = False
        
        # Регистрируем обработчики сигналов
        self._setup_signal_handlers()
        
        logger.info(f"📊 Менеджер БД инициализирован: {self.db_path}")
    
    def _setup_signal_handlers(self):
        """Настройка обработчиков сигналов для graceful shutdown"""
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        # Для Windows
        if hasattr(signal, 'SIGBREAK'):
            signal.signal(signal.SIGBREAK, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """Обработчик сигналов завершения"""
        logger.info(f"📥 Получен сигнал {signum}, создаю бэкап перед выходом...")
        self.create_backup_on_exit()
        sys.exit(0)
    
    def get_db_info(self) -> Dict[str, Any]:
        """Получить информацию о базе данных"""
        if not os.path.exists(self.db_path):
            return {"exists": False, "size": 0, "tables": []}
        
        try:
            size = os.path.getsize(self.db_path)
            
            # Получаем список таблиц
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Получаем таблицы
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]
            
            # Получаем статистику по таблицам
            table_stats = {}
            for table in tables:
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                count = cursor.fetchone()[0]
                table_stats[table] = count
            
            conn.close()
            
            return {
                "exists": True,
                "size": size,
                "size_mb": size / (1024 * 1024),
                "tables": tables,
                "table_stats": table_stats,
                "last_modified": datetime.fromtimestamp(os.path.getmtime(self.db_path))
            }
        except Exception as e:
            logger.error(f"❌ Ошибка получения информации о БД: {e}")
            return {"exists": False, "error": str(e)}
    
    def save_metadata(self):
        """Сохранить метаданные базы данных"""
        try:
            metadata = {
                "db_path": self.db_path,
                "last_backup": datetime.now().isoformat(),
                "backup_count": len(self.list_backups()),
                "db_info": self.get_db_info(),
                "version": "1.0"
            }
            
            with open(self.metadata_file, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, indent=2, default=str)
            
            logger.info("✅ Метаданные БД сохранены")
        except Exception as e:
            logger.error(f"❌ Ошибка сохранения метаданных: {e}")
    
    def load_metadata(self) -> Optional[Dict[str, Any]]:
        """Загрузить метаданные базы данных"""
        if not os.path.exists(self.metadata_file):
            return None
        
        try:
            with open(self.metadata_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"❌ Ошибка загрузки метаданных: {e}")
            return None
    
    def create_backup(self, backup_name: Optional[str] = None) -> Optional[str]:
        """Создать резервную копию базы данных"""
        if not os.path.exists(self.db_path):
            logger.warning(f"⚠️ Файл БД не найден: {self.db_path}")
            return None
        
        try:
            # Генерируем имя файла
            if backup_name is None:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                backup_name = f"backup_{timestamp}.db"
            
            backup_path = os.path.join(self.backup_dir, backup_name)
            
            # Создаем бэкап
            shutil.copy2(self.db_path, backup_path)
            
            # Сохраняем метаданные
            self.save_metadata()
            
            logger.info(f"✅ Бэкап создан: {backup_name}")
            return backup_path
            
        except Exception as e:
            logger.error(f"❌ Ошибка создания бэкапа: {e}")
            return None
    
    def create_backup_on_exit(self):
        """Создать бэкап при выходе из приложения"""
        if not self.auto_backup_on_exit:
            return
        
        logger.info("💾 Создание бэкапа перед выходом...")
        
        # Проверяем, нужно ли создавать бэкап
        last_backup = self.get_last_backup_time()
        if last_backup and (datetime.now() - last_backup < timedelta(hours=1)):
            logger.info("⏭️ Последний бэкап создан менее часа назад, пропускаю")
            return
        
        self.create_backup("exit_backup.db")
    
    def restore_from_backup(self, backup_path: str) -> bool:
        """Восстановить базу данных из бэкапа"""
        try:
            if not os.path.exists(backup_path):
                logger.error(f"❌ Файл бэкапа не найден: {backup_path}")
                return False
            
            # Создаем бэкап текущей БД (если существует)
            if os.path.exists(self.db_path):
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                old_backup = os.path.join(self.backup_dir, f"before_restore_{timestamp}.db")
                shutil.copy2(self.db_path, old_backup)
                logger.info(f"💾 Сохранена текущая БД перед восстановлением: {old_backup}")
            
            # Восстанавливаем из бэкапа
            shutil.copy2(backup_path, self.db_path)
            
            logger.info(f"✅ БД восстановлена из бэкапа: {backup_path}")
            self._restored = True
            return True
            
        except Exception as e:
            logger.error(f"❌ Ошибка восстановления из бэкапа: {e}")
            return False
    
    def auto_restore_on_startup(self):
        """Автоматическое восстановление при запуске"""
        if not self.auto_restore_on_start:
            return False
        
        logger.info("🔍 Проверка необходимости восстановления БД...")
        
        # Проверяем состояние текущей БД
        db_info = self.get_db_info()
        
        # Если БД существует и не пустая
        if db_info["exists"] and db_info.get("size", 0) > 1024:  # Больше 1KB
            logger.info("✅ Текущая БД в порядке, восстановление не требуется")
            return False
        
        # Ищем последний бэкап
        backups = self.list_backups()
        if not backups:
            logger.warning("⚠️ Бэкапы не найдены, восстановление невозможно")
            return False
        
        latest_backup = backups[-1]["path"]
        logger.info(f"🔄 Восстанавливаю БД из последнего бэкапа: {latest_backup}")
        
        return self.restore_from_backup(latest_backup)
    
    def get_last_backup_time(self) -> Optional[datetime]:
        """Получить время последнего бэкапа"""
        backups = self.list_backups()
        if not backups:
            return None
        
        latest_backup = backups[-1]
        return latest_backup.get("modified")
    
    def list_backups(self) -> List[Dict[str, Any]]:
        """Получить список всех бэкапов"""
        backups = []
        
        if not os.path.exists(self.backup_dir):
            return backups
        
        for filename in os.listdir(self.backup_dir):
            if filename.endswith('.db'):
                filepath = os.path.join(self.backup_dir, filename)
                stat = os.stat(filepath)
                
                backup_info = {
                    "name": filename,
                    "path": filepath,
                    "size": stat.st_size,
                    "size_mb": stat.st_size / (1024 * 1024),
                    "created": datetime.fromtimestamp(stat.st_ctime),
                    "modified": datetime.fromtimestamp(stat.st_mtime),
                    "is_valid": self.validate_backup(filepath)
                }
                
                backups.append(backup_info)
        
        # Сортируем по дате создания (старые сначала)
        backups.sort(key=lambda x: x["created"])
        return backups
    
    def validate_backup(self, backup_path: str) -> bool:
        """Проверить валидность бэкапа"""
        try:
            conn = sqlite3.connect(f"file:{backup_path}?mode=ro", uri=True)
            cursor = conn.cursor()
            
            # Проверяем основные таблицы
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]
            
            conn.close()
            
            # Проверяем наличие основных таблиц
            required_tables = {'users', 'anon_messages', 'payments'}
            has_required = any(table in tables for table in required_tables)
            
            return has_required and len(tables) > 0
            
        except Exception as e:
            logger.debug(f"Бэкап не валиден {backup_path}: {e}")
            return False
    
    def cleanup_old_backups(self):
        """Очистить старые бэкапы"""
        try:
            backups = self.list_backups()
            
            # Оставляем только последние max_backups
            if len(backups) <= self.max_backups:
                return 0
            
            to_delete = backups[:-self.max_backups]
            deleted_count = 0
            
            for backup in to_delete:
                try:
                    os.remove(backup["path"])
                    deleted_count += 1
                    logger.info(f"🗑️ Удален старый бэкап: {backup['name']}")
                except Exception as e:
                    logger.error(f"❌ Ошибка удаления бэкапа {backup['name']}: {e}")
            
            logger.info(f"🧹 Удалено старых бэкапов: {deleted_count}")
            return deleted_count
            
        except Exception as e:
            logger.error(f"❌ Ошибка очистки бэкапов: {e}")
            return 0
    
    async def async_create_backup(self) -> Optional[str]:
        """Асинхронное создание бэкапа"""
        return await asyncio.get_event_loop().run_in_executor(
            None, self.create_backup
        )
    
    async def async_restore_from_backup(self, backup_path: str) -> bool:
        """Асинхронное восстановление из бэкапа"""
        return await asyncio.get_event_loop().run_in_executor(
            None, self.restore_from_backup, backup_path
        )
    
    def schedule_periodic_backups(self, interval_hours: int = 24):
        """Запланировать периодические бэкапы"""
        self.backup_interval_hours = interval_hours
        
        def backup_worker():
            while True:
                try:
                    # Ждем указанный интервал
                    time.sleep(interval_hours * 3600)
                    
                    # Проверяем, нужно ли создавать бэкап
                    last_backup = self.get_last_backup_time()
                    if last_backup and (datetime.now() - last_backup < timedelta(hours=interval_hours)):
                        continue
                    
                    logger.info(f"⏰ Создание периодического бэкапа (интервал: {interval_hours}ч)")
                    self.create_backup()
                    self.cleanup_old_backups()
                    
                except Exception as e:
                    logger.error(f"❌ Ошибка в worker периодических бэкапов: {e}")
                    time.sleep(60)  # Ждем минуту при ошибке
        
        # Запускаем в отдельном потоке
        thread = threading.Thread(target=backup_worker, daemon=True)
        thread.start()
        logger.info(f"⏰ Периодические бэкапы запланированы каждые {interval_hours} часов")
    
    
    def import_from_sql(self, sql_file: str) -> bool:
        """Импорт базы данных из SQL файла"""
        try:
            if not os.path.exists(sql_file):
                logger.error(f"❌ SQL файл не найден: {sql_file}")
                return False
            
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            with open(sql_file, 'r', encoding='utf-8') as f:
                sql_script = f.read()
            
            # Выполняем SQL скрипт
            cursor.executescript(sql_script)
            conn.commit()
            conn.close()
            
            logger.info(f"✅ БД импортирована из SQL: {sql_file}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Ошибка импорта из SQL: {e}")
            return False
    
    def compare_with_backup(self, backup_path: str) -> Dict[str, Any]:
        """Сравнить текущую БД с бэкапом"""
        try:
            current_info = self.get_db_info()
            
            # Получаем информацию о бэкапе
            backup_info = {}
            if os.path.exists(backup_path):
                temp_conn = sqlite3.connect(f"file:{backup_path}?mode=ro", uri=True)
                temp_cursor = temp_conn.cursor()
                
                temp_cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
                backup_tables = [row[0] for row in temp_cursor.fetchall()]
                
                backup_table_stats = {}
                for table in backup_tables:
                    temp_cursor.execute(f"SELECT COUNT(*) FROM {table}")
                    count = temp_cursor.fetchone()[0]
                    backup_table_stats[table] = count
                
                temp_conn.close()
                
                backup_info = {
                    "tables": backup_tables,
                    "table_stats": backup_table_stats,
                    "size": os.path.getsize(backup_path)
                }
            
            # Сравниваем
            differences = {
                "tables_added": [],
                "tables_removed": [],
                "tables_changed": [],
                "size_diff": current_info.get("size", 0) - backup_info.get("size", 0)
            }
            
            current_tables = set(current_info.get("tables", []))
            backup_tables_set = set(backup_info.get("tables", []))
            
            differences["tables_added"] = list(current_tables - backup_tables_set)
            differences["tables_removed"] = list(backup_tables_set - current_tables)
            
            # Сравниваем количество записей в общих таблицах
            common_tables = current_tables.intersection(backup_tables_set)
            for table in common_tables:
                current_count = current_info.get("table_stats", {}).get(table, 0)
                backup_count = backup_info.get("table_stats", {}).get(table, 0)
                
                if current_count != backup_count:
                    differences["tables_changed"].append({
                        "table": table,
                        "current": current_count,
                        "backup": backup_count,
                        "diff": current_count - backup_count
                    })
            
            return {
                "current": current_info,
                "backup": backup_info,
                "differences": differences,
                "has_changes": any(differences.values())
            }
            
        except Exception as e:
            logger.error(f"❌ Ошибка сравнения БД: {e}")
            return {"error": str(e)}


# Глобальный экземпляр
db_manager = DatabaseManager()


# Декоратор для автоматического бэкапа при выходе
def backup_on_exit(func):
    """Декоратор для автоматического создания бэкапа при выходе из функции"""
    def wrapper(*args, **kwargs):
        try:
            result = func(*args, **kwargs)
            return result
        finally:
            # Создаем бэкап при выходе
            db_manager.create_backup_on_exit()
    
    async def async_wrapper(*args, **kwargs):
        try:
            result = await func(*args, **kwargs)
            return result
        finally:
            # Создаем бэкап при выходе
            db_manager.create_backup_on_exit()
    
    return async_wrapper if asyncio.iscoroutinefunction(func) else wrapper


# Инициализация при импорте
def init_database_manager():
    """Инициализация менеджера БД при запуске"""
    logger.info("🚀 Инициализация менеджера БД...")
    
    # Автоматическое восстановление при запуске
    restored = db_manager.auto_restore_on_startup()
    
    # Запускаем периодические бэкапы
    db_manager.schedule_periodic_backups(24)  # Каждые 24 часа
    
    # Создаем начальный бэкап если БД только что создана
    db_info = db_manager.get_db_info()
    if db_info["exists"] and len(db_manager.list_backups()) == 0:
        logger.info("📝 Создание начального бэкапа...")
        db_manager.create_backup("initial_backup.db")
    
    logger.info("✅ Менеджер БД готов к работе")
    return restored


# Автоматическая инициализация при импорте
if __name__ != "__main__":
    init_database_manager()
