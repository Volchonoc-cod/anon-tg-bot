#!/usr/bin/env python3
"""
Скрипт автоматического восстановления БД после деплоя на Render
"""
import os
import sys
import logging
import sqlite3
import shutil
from datetime import datetime
import requests

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class AutoRestore:
    def __init__(self):
        self.backup_dir = 'backups'
        self.db_path = 'data/bot.db'
        self.uploads_dir = 'uploads'
        self.latest_backup_url = None  # URL для скачивания бэкапа
        
        # Создаем директории
        os.makedirs(self.backup_dir, exist_ok=True)
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        os.makedirs(self.uploads_dir, exist_ok=True)
    
    def check_db_exists(self):
        """Проверяет существует ли БД"""
        if os.path.exists(self.db_path):
            size = os.path.getsize(self.db_path)
            logger.info(f"📁 БД существует: {self.db_path} ({size:,} байт)")
            
            # Проверяем валидность
            try:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
                tables = cursor.fetchall()
                conn.close()
                
                if len(tables) > 0:
                    logger.info(f"✅ БД валидна, таблиц: {len(tables)}")
                    return True
                else:
                    logger.warning("⚠️ БД пустая (нет таблиц)")
                    return False
            except Exception as e:
                logger.error(f"❌ БД повреждена: {e}")
                return False
        else:
            logger.warning("⚠️ Файл БД не найден")
            return False
    
    def get_latest_backup(self):
        """Находит последний валидный бэкап"""
        if not os.path.exists(self.backup_dir):
            logger.warning("⚠️ Директория бэкапов не найдена")
            return None
        
        backups = []
        for filename in sorted(os.listdir(self.backup_dir)):
            if filename.endswith('.db'):
                filepath = os.path.join(self.backup_dir, filename)
                try:
                    # Проверяем валидность
                    conn = sqlite3.connect(f"file:{filepath}?mode=ro", uri=True)
                    cursor = conn.cursor()
                    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
                    tables = [row[0] for row in cursor.fetchall()]
                    conn.close()
                    
                    # Проверяем обязательные таблицы
                    required_tables = ['users', 'anon_messages', 'payments']
                    found_tables = [t for t in required_tables if t in tables]
                    
                    if len(found_tables) >= 2:  # Хотя бы 2 из 3 таблиц
                        stat = os.stat(filepath)
                        backups.append({
                            'path': filepath,
                            'name': filename,
                            'size': stat.st_size,
                            'created': datetime.fromtimestamp(stat.st_ctime),
                            'tables': tables
                        })
                except Exception:
                    continue
        
        if backups:
            # Сортируем по дате создания (новые сначала)
            backups.sort(key=lambda x: x['created'], reverse=True)
            latest = backups[0]
            logger.info(f"📂 Найден бэкап: {latest['name']} ({latest['size']:,} байт)")
            return latest
        else:
            logger.warning("⚠️ Валидные бэкапы не найдены")
            return None
    
    def restore_from_backup(self, backup_path):
        """Восстанавливает БД из бэкапа"""
        try:
            # Создаем копию текущей БД (если есть)
            if os.path.exists(self.db_path):
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                old_backup = os.path.join(self.backup_dir, f"before_auto_restore_{timestamp}.db")
                shutil.copy2(self.db_path, old_backup)
                logger.info(f"💾 Сохранена текущая БД: {os.path.basename(old_backup)}")
            
            # Восстанавливаем
            logger.info(f"🔄 Восстановление из {os.path.basename(backup_path)}...")
            shutil.copy2(backup_path, self.db_path)
            
            # Проверяем восстановление
            if self.check_db_exists():
                size = os.path.getsize(self.db_path)
                logger.info(f"✅ БД восстановлена! Размер: {size:,} байт")
                return True
            else:
                logger.error("❌ Восстановление не удалось")
                return False
                
        except Exception as e:
            logger.error(f"❌ Ошибка восстановления: {e}")
            return False
    
    def download_from_url(self, url):
        """Скачивает БД с URL"""
        try:
            logger.info(f"🌐 Скачиваю БД с {url}")
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            
            # Сохраняем файл
            filename = f"downloaded_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
            filepath = os.path.join(self.uploads_dir, filename)
            
            with open(filepath, 'wb') as f:
                f.write(response.content)
            
            file_size = os.path.getsize(filepath)
            logger.info(f"📥 Файл скачан: {filename} ({file_size:,} байт)")
            
            # Проверяем валидность
            try:
                conn = sqlite3.connect(f"file:{filepath}?mode=ro", uri=True)
                cursor = conn.cursor()
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
                tables = [row[0] for row in cursor.fetchall()]
                conn.close()
                
                if 'users' in tables and 'anon_messages' in tables:
                    logger.info(f"✅ Файл валиден, таблиц: {len(tables)}")
                    return filepath
                else:
                    logger.warning("⚠️ Файл не содержит нужных таблиц")
                    os.remove(filepath)
                    return None
            except Exception as e:
                logger.error(f"❌ Файл не является SQLite БД: {e}")
                os.remove(filepath)
                return None
                
        except Exception as e:
            logger.error(f"❌ Ошибка скачивания: {e}")
            return None
    
    def run(self):
        """Основной метод"""
        logger.info("🚀 Запуск автоматического восстановления...")
        
        # 1. Проверяем есть ли БД
        if self.check_db_exists():
            logger.info("✅ БД уже существует, восстановление не требуется")
            return True
        
        logger.warning("⚠️ БД не найдена или повреждена, начинаю восстановление...")
        
        # 2. Пробуем скачать с URL если указан
        if self.latest_backup_url:
            downloaded_file = self.download_from_url(self.latest_backup_url)
            if downloaded_file and self.restore_from_backup(downloaded_file):
                logger.info("✅ Восстановлено из URL")
                return True
        
        # 3. Ищем локальный бэкап
        backup = self.get_latest_backup()
        if backup and self.restore_from_backup(backup['path']):
            logger.info("✅ Восстановлено из локального бэкапа")
            return True
        
        # 4. Создаем пустую БД если ничего не нашли
        logger.info("📝 Создаю новую пустую БД...")
        try:
            conn = sqlite3.connect(self.db_path)
            
            # Создаем базовые таблицы
            conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY,
                    telegram_id INTEGER UNIQUE,
                    username TEXT,
                    first_name TEXT,
                    anon_link_uid TEXT UNIQUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    balance INTEGER DEFAULT 0,
                    premium_until TIMESTAMP,
                    available_reveals INTEGER DEFAULT 0
                )
            """)
            
            conn.execute("""
                CREATE TABLE IF NOT EXISTS anon_messages (
                    id INTEGER PRIMARY KEY,
                    sender_id INTEGER,
                    receiver_id INTEGER NOT NULL,
                    text TEXT NOT NULL,
                    is_anonymous BOOLEAN DEFAULT TRUE,
                    is_revealed BOOLEAN DEFAULT FALSE,
                    is_reported BOOLEAN DEFAULT FALSE,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    reply_to_message_id INTEGER,
                    FOREIGN KEY (sender_id) REFERENCES users(id),
                    FOREIGN KEY (receiver_id) REFERENCES users(id),
                    FOREIGN KEY (reply_to_message_id) REFERENCES anon_messages(id)
                )
            """)
            
            conn.execute("""
                CREATE TABLE IF NOT EXISTS payments (
                    id INTEGER PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    amount INTEGER NOT NULL,
                    payment_type TEXT NOT NULL,
                    status TEXT DEFAULT 'pending',
                    yookassa_payment_id TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    completed_at TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id)
                )
            """)
            
            conn.commit()
            conn.close()
            
            logger.info("✅ Создана новая БД с таблицами")
            return True
            
        except Exception as e:
            logger.error(f"❌ Ошибка создания БД: {e}")
            return False

def main():
    """Точка входа"""
    restorer = AutoRestore()
    
    # Можно задать URL для скачивания бэкапа
    # Например, из GitHub или облачного хранилища
    # restorer.latest_backup_url = "https://example.com/backup.db"
    
    success = restorer.run()
    
    if success:
        logger.info("✅ Автовосстановление завершено успешно!")
        return 0
    else:
        logger.error("❌ Автовосстановление не удалось")
        return 1

if __name__ == "__main__":
    sys.exit(main())
