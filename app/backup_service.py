import os
import sqlite3
import shutil
import asyncio
from datetime import datetime
from aiogram import Bot
from app.config import BOT_TOKEN, ADMIN_IDS
from app.database import DATA_DIR
from aiogram.types import BufferedInputFile
import logging

logger = logging.getLogger(__name__)


class BackupService:
    def __init__(self):
        self.backup_dir = os.path.join(os.path.dirname(__file__), '..', 'backups')
        os.makedirs(self.backup_dir, exist_ok=True)

        # Используем путь из database.py
        self.db_path = os.path.join(DATA_DIR, 'bot.db')

        # Настройки
        self.max_size_mb = 10  # Предупреждение при 10MB
        self.critical_size_mb = 20  # Критический размер 20MB

    def get_db_size(self):
        """Получить размер базы данных в MB"""
        if os.path.exists(self.db_path):
            size_bytes = os.path.getsize(self.db_path)
            return size_bytes / (1024 * 1024)  # Конвертируем в MB
        return 0

    def get_db_stats(self):
        """Получить статистику базы данных"""
        if not os.path.exists(self.db_path):
            return "База данных не найдена"

        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Получаем статистику
            cursor.execute("SELECT COUNT(*) FROM users")
            users_count = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM anon_messages")
            messages_count = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM payments WHERE status = 'completed'")
            payments_count = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM payments WHERE status = 'pending'")
            pending_payments = cursor.fetchone()[0]

            conn.close()

            return {
                'users': users_count,
                'messages': messages_count,
                'payments': payments_count,
                'pending_payments': pending_payments
            }

        except Exception as e:
            return f"Ошибка получения статистики: {e}"

    def create_backup(self):
        """Создать резервную копию базы данных"""
        if not os.path.exists(self.db_path):
            logger.error(f"❌ Файл базы данных не найден: {self.db_path}")
            return None

        # Создаем имя файла с датой
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_filename = f"bot_backup_{timestamp}.db"
        backup_path = os.path.join(self.backup_dir, backup_filename)

        try:
            # Копируем файл базы данных
            shutil.copy2(self.db_path, backup_path)
            logger.info(f"✅ Резервная копия создана: {backup_filename}")
            
            # Автоматически отправляем в Telegram
            asyncio.create_task(self.send_backup_to_telegram_async(backup_path))
            
            return backup_path
        except Exception as e:
            logger.error(f"❌ Ошибка создания резервной копии: {e}")
            return None

    async def send_backup_to_telegram_async(self, backup_path):
        """Асинхронная отправка backup в Telegram"""
        try:
            if not BOT_TOKEN or not ADMIN_IDS:
                logger.warning("⚠️ BOT_TOKEN или ADMIN_IDS не установлены, пропускаю отправку в Telegram")
                return False
                
            bot = Bot(token=BOT_TOKEN)
            backup_name = os.path.basename(backup_path)
            file_size = os.path.getsize(backup_path)
            file_size_mb = file_size / (1024 * 1024)
            
            # Читаем файл
            with open(backup_path, 'rb') as f:
                file_data = f.read()
            
            success_count = 0
            error_count = 0
            
            for admin_id in ADMIN_IDS:
                if not admin_id.strip():
                    continue
                    
                try:
                    admin_id_int = int(admin_id.strip())
                    
                    # Используем BufferedInputFile для aiogram 3.x
                    input_file = BufferedInputFile(
                        file=file_data,
                        filename=backup_name
                    )
                    
                    await bot.send_document(
                        chat_id=admin_id_int,
                        document=input_file,
                        caption=(
                            f"📦 <b>Автоматический backup базы</b>\n\n"
                            f"📁 Файл: {backup_name}\n"
                            f"📊 Размер: {file_size_mb:.2f} MB\n"
                            f"⏰ Дата: {datetime.now().strftime('%d.%m.%Y %H:%M')}\n\n"
                            f"💾 Сохраните для восстановления"
                        ),
                        parse_mode="HTML"
                    )
                    
                    success_count += 1
                    logger.info(f"✅ Backup автоматически отправлен админу {admin_id_int}")
                    
                    # Небольшая задержка между отправками
                    await asyncio.sleep(0.5)
                    
                except Exception as e:
                    error_count += 1
                    logger.error(f"❌ Ошибка отправки админу {admin_id}: {e}")
            
            await bot.session.close()
            
            logger.info(f"📤 Итог отправки: успешно {success_count}, ошибок {error_count}")
            return success_count > 0
            
        except Exception as e:
            logger.error(f"❌ Ошибка автоматической отправки backup: {e}")
            return False

    async def send_telegram_notification(self, message):
        """Отправить уведомление в Telegram (без файлов)"""
        bot = Bot(token=BOT_TOKEN)

        for admin_id in ADMIN_IDS:
            try:
                await bot.send_message(admin_id, message, parse_mode="HTML")
            except Exception as e:
                logger.error(f"❌ Ошибка отправки уведомления админу {admin_id}: {e}")
        
        await bot.session.close()

    def cleanup_old_backups(self, keep_count=5):
        """Удалить старые резервные копии, оставить только keep_count"""
        try:
            # Получаем все backup файлы
            backups = []
            for filename in os.listdir(self.backup_dir):
                if filename.startswith('bot_backup_') and filename.endswith('.db'):
                    filepath = os.path.join(self.backup_dir, filename)
                    backups.append((filepath, os.path.getctime(filepath)))

            # Сортируем по дате создания (старые сначала)
            backups.sort(key=lambda x: x[1])

            # Удаляем лишние
            deleted_count = 0
            while len(backups) > keep_count:
                old_backup_path, old_time = backups.pop(0)
                os.remove(old_backup_path)
                deleted_count += 1
                logger.info(f"🗑️ Удалена старая резервная копия: {os.path.basename(old_backup_path)}")

            return deleted_count

        except Exception as e:
            logger.error(f"❌ Ошибка очистки старых копий: {e}")
            return 0

    async def check_and_backup(self):
        """Проверить размер базы и создать резервную копию при необходимости"""
        size_mb = self.get_db_size()
        stats = self.get_db_stats()

        logger.info(f"📊 Текущий размер базы: {size_mb:.2f} MB")

        message = None
        backup_created = False

        if size_mb > self.critical_size_mb:
            # КРИТИЧЕСКИЙ размер - срочно делаем backup
            backup_path = self.create_backup()
            backup_created = bool(backup_path)
            message = (
                "🚨 <b>КРИТИЧЕСКИЙ РАЗМЕР БАЗЫ</b>\n\n"
                f"📊 Размер: {size_mb:.2f} MB\n"
                f"👥 Пользователей: {stats.get('users', 'N/A')}\n"
                f"📨 Сообщений: {stats.get('messages', 'N/A')}\n"
                f"💰 Платежей: {stats.get('payments', 'N/A')}\n"
                f"✅ Резервная копия: {'Создана' if backup_created else 'Ошибка'}\n"
                f"📤 Отправлено в Telegram: {'Да' if backup_created else 'Нет'}"
            )

        elif size_mb > self.max_size_mb:
            # Большой размер - предупреждение
            backup_path = self.create_backup()
            backup_created = bool(backup_path)
            message = (
                "⚠️ <b>База данных большая</b>\n\n"
                f"📊 Размер: {size_mb:.2f} MB\n"
                f"👥 Пользователей: {stats.get('users', 'N/A')}\n"
                f"📨 Сообщений: {stats.get('messages', 'N/A')}\n"
                f"✅ Резервная копия: {'Создана' if backup_created else 'Ошибка'}\n"
                f"📤 Отправлено в Telegram: {'Да' if backup_created else 'Нет'}\n"
                f"💡 Рекомендуется почистить старые данные!"
            )

        # Отправляем уведомление если нужно
        if message:
            await self.send_telegram_notification(message)

        # Всегда чистим старые копии
        deleted_count = self.cleanup_old_backups()
        if deleted_count > 0:
            logger.info(f"🗑️ Удалено старых копий: {deleted_count}")

        return size_mb, backup_created


# Глобальный экземпляр
backup_service = BackupService()
