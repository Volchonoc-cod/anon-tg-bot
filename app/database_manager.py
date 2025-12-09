"""
Менеджер базы данных с автоматическим бэкапом/восстановлением
"""
import os
import sqlite3
import shutil
import json
import asyncio
from datetime import datetime, timedelta
import logging
from typing import Optional, List, Dict, Any
import traceback
from aiogram import Bot
from aiogram.types import FSInputFile
import time

logger = logging.getLogger(__name__)


class DatabaseManager:
    """Класс для управления базой данных с бэкапами"""
    
    def __init__(self, db_path: str = None, bot: Bot = None):
        self.bot = bot
        self.db_path = self._find_or_create_db(db_path)
        self.backup_dir = 'backups'
        self.metadata_file = 'data/db_metadata.json'
        
        # Создаем необходимые директории
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        os.makedirs(self.backup_dir, exist_ok=True)
        os.makedirs(os.path.dirname(self.metadata_file), exist_ok=True)
        
        # Настройки
        self.auto_backup_on_exit = True
        self.auto_restore_on_start = True
        self.max_backups = 10
        self.min_db_size = 1024  # 1KB минимальный размер для бэкапа
        
        logger.info(f"📊 Менеджер БД инициализирован: {self.db_path}")
        logger.info(f"📁 Директория бэкапов: {self.backup_dir}")
        
        # Флаг инициализации
        self._initialized = False
    
    def set_bot(self, bot: Bot):
        """Установить бота для отправки уведомлений"""
        self.bot = bot
    
    def _find_or_create_db(self, db_path: str = None) -> str:
        """Найти существующую БД или определить путь для новой"""
        if db_path and os.path.exists(db_path):
            logger.info(f"✅ Используется указанный путь к БД: {db_path}")
            return db_path
        
        # Ищем БД в возможных местах
        possible_paths = [
            'data/bot.db',
            'bot.db',
            './bot.db',
            os.path.join(os.getcwd(), 'bot.db'),
            os.path.join(os.getcwd(), 'data', 'bot.db'),
            os.path.join('/opt/render/project/src', 'data', 'bot.db'),
            os.path.join('/opt/render/project/src', 'bot.db'),
        ]
        
        for path in possible_paths:
            if os.path.exists(path) and os.path.getsize(path) > 0:
                logger.info(f"🔍 Найдена БД: {path} ({os.path.getsize(path):,} байт)")
                return path
        
        # Если БД не найдена, создаем в data/bot.db
        default_path = 'data/bot.db'
        os.makedirs(os.path.dirname(default_path), exist_ok=True)
        logger.info(f"📝 БД не найдена, будет создана новая: {default_path}")
        
        # Создаем пустую БД для инициализации
        try:
            conn = sqlite3.connect(default_path)
            conn.execute("CREATE TABLE IF NOT EXISTS init_table (id INTEGER PRIMARY KEY)")
            conn.execute("INSERT INTO init_table DEFAULT VALUES")
            conn.commit()
            conn.close()
            logger.info(f"✅ Создана новая БД: {default_path}")
        except Exception as e:
            logger.error(f"❌ Ошибка создания БД: {e}")
        
        return default_path
    
    def get_db_info(self) -> Dict[str, Any]:
        """Получить информацию о базе данных"""
        if not os.path.exists(self.db_path):
            return {"exists": False, "size": 0, "tables": [], "error": "Файл не найден"}
        
        try:
            size = os.path.getsize(self.db_path)
            
            # Проверяем что БД не пустая
            if size == 0:
                return {"exists": True, "size": 0, "tables": [], "error": "БД пустая"}
            
            # Получаем список таблиц
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Получаем таблицы
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]
            
            # Получаем статистику по таблицам
            table_stats = {}
            for table in tables:
                try:
                    cursor.execute(f"SELECT COUNT(*) FROM {table}")
                    count = cursor.fetchone()[0]
                    table_stats[table] = count
                except Exception as e:
                    logger.warning(f"⚠️ Не удалось получить статистику для таблицы {table}: {e}")
                    table_stats[table] = 0
            
            conn.close()
            
            last_modified = datetime.fromtimestamp(os.path.getmtime(self.db_path))
            created = datetime.fromtimestamp(os.path.getctime(self.db_path)) if os.path.exists(self.db_path) else None
            
            return {
                "exists": True,
                "path": self.db_path,
                "size": size,
                "size_mb": round(size / (1024 * 1024), 2),
                "tables": tables,
                "table_count": len(tables),
                "table_stats": table_stats,
                "total_records": sum(table_stats.values()),
                "last_modified": last_modified,
                "created": created,
                "status": "ok"
            }
        except Exception as e:
            logger.error(f"❌ Ошибка получения информации о БД: {e}")
            return {"exists": False, "error": str(e), "status": "error"}
    
    def save_metadata(self):
        """Сохранить метаданные базы данных"""
        try:
            metadata = {
                "db_path": self.db_path,
                "last_backup": datetime.now().isoformat(),
                "backup_count": len(self.list_backups()),
                "db_info": self.get_db_info(),
                "version": "1.0",
                "timestamp": datetime.now().isoformat()
            }
            
            with open(self.metadata_file, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, indent=2, default=str)
            
            logger.debug("✅ Метаданные БД сохранены")
            return True
        except Exception as e:
            logger.error(f"❌ Ошибка сохранения метаданных: {e}")
            return False
    
    def load_metadata(self) -> Optional[Dict[str, Any]]:
        """Загрузить метаданные базы данных"""
        if not os.path.exists(self.metadata_file):
            logger.debug("ℹ️ Файл метаданных не найден")
            return None
        
        try:
            with open(self.metadata_file, 'r', encoding='utf-8') as f:
                metadata = json.load(f)
            logger.debug("✅ Метаданные БД загружены")
            return metadata
        except Exception as e:
            logger.error(f"❌ Ошибка загрузки метаданных: {e}")
            return None
    
    def create_backup(self, backup_name: Optional[str] = None, send_to_admins: bool = True) -> Optional[str]:
        """Создать резервную копию базы данных"""
        try:
            # Проверяем существует ли файл БД
            if not os.path.exists(self.db_path):
                logger.warning(f"⚠️ Файл БД не найден: {self.db_path}")
                return None
            
            # Проверяем размер БД
            db_size = os.path.getsize(self.db_path)
            if db_size < self.min_db_size:
                logger.warning(f"⚠️ БД слишком мала ({db_size:,} байт < {self.min_db_size:,}), пропускаю бэкап")
                return None
            
            # Получаем информацию о БД перед бэкапом
            db_info = self.get_db_info()
            if db_info.get("total_records", 0) == 0 and db_info.get("table_count", 0) <= 1:
                logger.warning("⚠️ БД почти пустая, пропускаю бэкап")
                return None
            
            # Генерируем имя файла
            if backup_name is None:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                backup_name = f"backup_{timestamp}.db"
            
            backup_path = os.path.join(self.backup_dir, backup_name)
            
            logger.info(f"💾 Создание бэкапа: {backup_name}")
            
            # Создаем бэкап
            shutil.copy2(self.db_path, backup_path)
            
            # Проверяем что файл создался
            if os.path.exists(backup_path):
                file_size = os.path.getsize(backup_path)
                logger.info(f"✅ Бэкап создан: {backup_name} ({file_size:,} байт)")
                
                # Отправляем админам если есть бот
                if send_to_admins and self.bot:
                    asyncio.create_task(self._send_backup_to_admins(backup_path))
                
                # Сохраняем метаданные
                self.save_metadata()
                
                # Очищаем старые бэкапы
                deleted = self.cleanup_old_backups()
                if deleted > 0:
                    logger.info(f"🧹 Удалено {deleted} старых бэкапов")
                
                return backup_path
            else:
                logger.error(f"❌ Файл бэкапа не создался: {backup_path}")
                return None
                
        except Exception as e:
            logger.error(f"❌ Ошибка создания бэкапа: {e}")
            return None
    
    async def _send_backup_to_admins(self, backup_path: str):
        """Отправить бэкап всем админам"""
        try:
            from app.config import ADMIN_IDS
            
            if not ADMIN_IDS:
                logger.warning("⚠️ ADMIN_IDS не настроены, не могу отправить бэкап")
                return
            
            file_size = os.path.getsize(backup_path)
            file_size_mb = file_size / (1024 * 1024)
            
            caption = (
                f"💾 <b>Новый бекап базы данных</b>\n\n"
                f"📁 Имя: <code>{os.path.basename(backup_path)}</code>\n"
                f"📊 Размер: {file_size_mb:.2f} MB\n"
                f"⏰ Время: {datetime.now().strftime('%H:%M:%S')}\n\n"
                f"💡 Для восстановления используйте команду:\n"
                f"<code>/restore_{os.path.basename(backup_path).replace('.db', '')}</code>"
            )
            
            for admin_id in ADMIN_IDS:
                try:
                    await self.bot.send_document(
                        chat_id=admin_id,
                        document=FSInputFile(backup_path),
                        caption=caption,
                        parse_mode="HTML"
                    )
                    logger.info(f"📤 Бэкап отправлен админу {admin_id}")
                except Exception as e:
                    logger.error(f"❌ Ошибка отправки бэкапа админу {admin_id}: {e}")
            
        except Exception as e:
            logger.error(f"❌ Ошибка отправки бэкапа админам: {e}")
    
    def create_backup_on_exit(self):
        """Создать бэкап при выходе из приложения"""
        if not self.auto_backup_on_exit:
            logger.debug("ℹ️ Автобэкап при выходе отключен")
            return
        
        logger.info("💾 Создание бэкапа перед выходом...")
        
        # Проверяем, нужно ли создавать бэкап
        last_backup = self.get_last_backup_time()
        if last_backup and (datetime.now() - last_backup < timedelta(minutes=5)):
            logger.info("⏭️ Последний бэкап создан менее 5 минут назад, пропускаю")
            return
        
        # Проверяем что БД существует и не пустая
        if not os.path.exists(self.db_path):
            logger.warning("⚠️ БД не существует, пропускаю бэкап")
            return
        
        db_size = os.path.getsize(self.db_path)
        if db_size < self.min_db_size:
            logger.warning(f"⚠️ БД слишком мала ({db_size:,} байт), пропускаю бэкап")
            return
        
        # Проверяем есть ли данные в БД
        db_info = self.get_db_info()
        if db_info.get("total_records", 0) == 0:
            logger.warning("⚠️ БД пустая, пропускаю бэкап")
            return
        
        result = self.create_backup("exit_backup.db", send_to_admins=False)
        if result:
            logger.info(f"✅ Бэкап перед выходом создан: {result}")
        else:
            logger.warning("⚠️ Не удалось создать бэкап перед выходом")
    
    def restore_from_backup(self, backup_path: str) -> bool:
        """Восстановить базу данных из бэкапа"""
        try:
            if not os.path.exists(backup_path):
                logger.error(f"❌ Файл бэкапа не найден: {backup_path}")
                return False
            
            # Проверяем валидность бэкапа
            if not self.validate_backup(backup_path):
                logger.error(f"❌ Бэкап поврежден: {backup_path}")
                return False
            
            # Создаем бэкап текущей БД (если существует)
            if os.path.exists(self.db_path) and os.path.getsize(self.db_path) > self.min_db_size:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                old_backup = os.path.join(self.backup_dir, f"before_restore_{timestamp}.db")
                try:
                    shutil.copy2(self.db_path, old_backup)
                    logger.info(f"💾 Сохранена текущая БД перед восстановлением: {old_backup}")
                except Exception as e:
                    logger.warning(f"⚠️ Не удалось сохранить текущую БД: {e}")
            
            # Останавливаем все соединения с БД
            time.sleep(1)  # Даем время на закрытие соединений
            
            # Восстанавливаем из бэкапа
            logger.info(f"🔄 Восстановление БД из бэкапа: {backup_path}")
            shutil.copy2(backup_path, self.db_path)
            
            # Проверяем что восстановление успешно
            if os.path.exists(self.db_path):
                new_size = os.path.getsize(self.db_path)
                logger.info(f"✅ БД восстановлена из бэкапа: {backup_path} ({new_size:,} байт)")
                return True
            else:
                logger.error(f"❌ БД не была восстановлена")
                return False
            
        except Exception as e:
            logger.error(f"❌ Ошибка восстановления из бэкапа: {e}")
            return False
    
    def auto_restore_on_startup(self) -> bool:
        """Автоматическое восстановление при запуске"""
        if not self.auto_restore_on_start:
            logger.debug("ℹ️ Автовосстановление отключено")
            return False
        
        logger.info("🔍 Проверка необходимости восстановления БД при запуске...")
        
        # Проверяем состояние текущей БД
        db_info = self.get_db_info()
        
        # Если БД существует и содержит данные
        if db_info["exists"] and db_info.get("total_records", 0) > 0:
            logger.info("✅ Текущая БД в порядке, восстановление не требуется")
            return False
        
        # Ищем последний бэкап
        backups = self.list_backups()
        if not backups:
            logger.warning("⚠️ Бэкапы не найдены, восстановление невозможно")
            return False
        
        # Берем последний валидный бэкап
        for backup in reversed(backups):
            if self.validate_backup(backup["path"]):
                latest_backup = backup["path"]
                logger.info(f"🔄 Восстанавливаю БД из последнего валидного бэкапа: {os.path.basename(latest_backup)}")
                return self.restore_from_backup(latest_backup)
        
        logger.warning("⚠️ Валидные бэкапы не найдены")
        return False
    
    def get_last_backup_time(self) -> Optional[datetime]:
        """Получить время последнего бэкапа"""
        backups = self.list_backups()
        if not backups:
            return None
        
        latest_backup = backups[-1]
        return latest_backup.get("created")
    
    def list_backups(self) -> List[Dict[str, Any]]:
        """Получить список всех бэкапов"""
        backups = []
        
        if not os.path.exists(self.backup_dir):
            logger.debug(f"ℹ️ Директория бэкапов не найдена: {self.backup_dir}")
            return backups
        
        try:
            for filename in sorted(os.listdir(self.backup_dir)):
                if filename.endswith('.db'):
                    filepath = os.path.join(self.backup_dir, filename)
                    try:
                        stat = os.stat(filepath)
                        
                        # Пропускаем слишком маленькие файлы
                        if stat.st_size < self.min_db_size:
                            continue
                        
                        # Проверяем валидность бэкапа
                        is_valid = self.validate_backup(filepath)
                        
                        backup_info = {
                            "name": filename,
                            "path": filepath,
                            "size": stat.st_size,
                            "size_mb": round(stat.st_size / (1024 * 1024), 2),
                            "created": datetime.fromtimestamp(stat.st_ctime),
                            "modified": datetime.fromtimestamp(stat.st_mtime),
                            "is_valid": is_valid,
                            "age_days": (datetime.now() - datetime.fromtimestamp(stat.st_ctime)).days
                        }
                        
                        backups.append(backup_info)
                    except Exception as e:
                        logger.warning(f"⚠️ Ошибка чтения бэкапа {filename}: {e}")
            
            # Сортируем по дате создания (старые сначала)
            backups.sort(key=lambda x: x["created"])
            logger.debug(f"ℹ️ Найдено {len(backups)} валидных бэкапов")
            return backups
            
        except Exception as e:
            logger.error(f"❌ Ошибка получения списка бэкапов: {e}")
            return []
    
    def validate_backup(self, backup_path: str) -> bool:
        """Проверить валидность бэкапа"""
        if not os.path.exists(backup_path):
            return False
        
        try:
            # Проверяем размер файла
            file_size = os.path.getsize(backup_path)
            if file_size < self.min_db_size:
                return False
            
            # Пытаемся подключиться к БД
            conn = sqlite3.connect(f"file:{backup_path}?mode=ro", uri=True)
            cursor = conn.cursor()
            
            # Проверяем основные таблицы
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]
            
            # Проверяем наличие обязательных таблиц
            required_tables = ['users', 'anon_messages', 'payments']
            found_tables = [table for table in required_tables if table in tables]
            
            conn.close()
            
            # Проверяем наличие хотя бы одной обязательной таблицы
            if len(found_tables) == 0:
                logger.debug(f"⚠️ Бэкап не содержит обязательных таблиц: {backup_path}")
                return False
            
            logger.debug(f"✅ Бэкап валиден: {backup_path} (таблиц: {len(tables)}, обязательных: {len(found_tables)})")
            return True
            
        except Exception as e:
            logger.debug(f"⚠️ Бэкап невалиден {backup_path}: {e}")
            return False
    
    def cleanup_old_backups(self) -> int:
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
                    # Не удаляем валидные бэкапы, если их мало
                    if backup.get("is_valid", False) and len(backups) <= self.max_backups * 2:
                        continue
                    
                    os.remove(backup["path"])
                    deleted_count += 1
                    logger.debug(f"🗑️ Удален старый бэкап: {backup['name']}")
                except Exception as e:
                    logger.warning(f"⚠️ Ошибка удаления бэкапа {backup['name']}: {e}")
            
            if deleted_count > 0:
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
    
    def export_to_sql(self, sql_file: str = 'data/database_export.sql') -> bool:
        """Экспорт базы данных в SQL файл"""
        try:
            if not os.path.exists(self.db_path):
                logger.error(f"❌ Файл БД не найден: {self.db_path}")
                return False
            
            conn = sqlite3.connect(self.db_path)
            
            os.makedirs(os.path.dirname(sql_file), exist_ok=True)
            
            with open(sql_file, 'w', encoding='utf-8') as f:
                # Пишем информацию о бэкапе
                f.write(f"-- SQL Export from {self.db_path}\n")
                f.write(f"-- Export time: {datetime.now().isoformat()}\n")
                f.write("BEGIN TRANSACTION;\n\n")
                
                # Экспортируем схему
                cursor = conn.cursor()
                cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
                
                for row in cursor.fetchall():
                    if row[0]:
                        f.write(row[0] + ";\n\n")
                
                # Экспортируем данные
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
                tables = [row[0] for row in cursor.fetchall()]
                
                for table in tables:
                    cursor.execute(f"SELECT * FROM {table}")
                    columns = [description[0] for description in cursor.description]
                    
                    f.write(f"-- Data for table: {table}\n")
                    
                    cursor.execute(f"SELECT COUNT(*) FROM {table}")
                    count = cursor.fetchone()[0]
                    f.write(f"-- Records: {count}\n")
                    
                    for row in cursor.fetchall():
                        values = []
                        for value in row:
                            if value is None:
                                values.append("NULL")
                            elif isinstance(value, (int, float)):
                                values.append(str(value))
                            else:
                                # Экранируем одинарные кавычки
                                escaped_value = str(value).replace("'", "''")
                                values.append(f"'{escaped_value}'")
                        
                        insert_sql = f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({', '.join(values)});\n"
                        f.write(insert_sql)
                    
                    f.write("\n")
                
                f.write("COMMIT;\n")
            
            conn.close()
            
            file_size = os.path.getsize(sql_file) if os.path.exists(sql_file) else 0
            logger.info(f"✅ БД экспортирована в SQL: {sql_file} ({file_size:,} байт)")
            return True
            
        except Exception as e:
            logger.error(f"❌ Ошибка экспорта в SQL: {e}")
            return False
    
    def import_from_sql(self, sql_file: str) -> bool:
        """Импорт базы данных из SQL файла"""
        try:
            if not os.path.exists(sql_file):
                logger.error(f"❌ SQL файл не найден: {sql_file}")
                return False
            
            # Создаем бэкап перед импортом
            self.create_backup("before_import.db", send_to_admins=False)
            
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
                    try:
                        temp_cursor.execute(f"SELECT COUNT(*) FROM {table}")
                        count = temp_cursor.fetchone()[0]
                        backup_table_stats[table] = count
                    except:
                        backup_table_stats[table] = 0
                
                temp_conn.close()
                
                backup_info = {
                    "tables": backup_tables,
                    "table_stats": backup_table_stats,
                    "size": os.path.getsize(backup_path) if os.path.exists(backup_path) else 0
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
                "has_changes": any(len(v) > 0 for v in differences.values() if isinstance(v, list))
            }
            
        except Exception as e:
            logger.error(f"❌ Ошибка сравнения БД: {e}")
            return {"error": str(e)}


# Глобальный экземпляр
db_manager = DatabaseManager()


# Инициализация при импорте
_db_initialized = False

def init_database_manager(bot: Bot = None) -> bool:
    """Инициализация менеджера БД при запуске"""
    global _db_initialized
    
    if _db_initialized:
        logger.debug("ℹ️ Менеджер БД уже инициализирован")
        return False
    
    _db_initialized = True
    logger.info("🚀 Инициализация менеджера БД...")
    
    # Устанавливаем бота если передан
    if bot:
        db_manager.set_bot(bot)
    
    # Автоматическое восстановление при запуске
    restored = db_manager.auto_restore_on_startup()
    
    # Ждем инициализации таблиц
    time.sleep(2)
    
    # Создаем начальный бэкап если БД содержит данные
    db_info = db_manager.get_db_info()
    backups = db_manager.list_backups()
    
    if db_info.get("total_records", 0) > 0 and len(backups) == 0:
        logger.info("📝 Создание начального бэкапа...")
        result = db_manager.create_backup("initial_backup.db")
        if result:
            logger.info(f"✅ Начальный бэкап создан: {result}")
        else:
            logger.warning("⚠️ Не удалось создать начальный бэкап")
    elif db_info.get("total_records", 0) > 0:
        logger.info("✅ Бэкапы уже существуют")
    
    logger.info("✅ Менеджер БД готов к работе")
    return restored


# Инициализируем при импорте
if __name__ != "__main__":
    try:
        # Запускаем без бота, бот будет установлен позже
        init_database_manager()
    except Exception as e:
        logger.error(f"❌ Ошибка при автоматической инициализации менеджера БД: {e}")
