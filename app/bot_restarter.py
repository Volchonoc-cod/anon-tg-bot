"""
Управление перезапуском бота
"""
import os
import sys
import signal
import psutil
import subprocess
import asyncio
import time
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class BotRestarter:
    def __init__(self):
        self.bot_process = None
        self.bot_script = self._find_bot_script()
    
    def _find_bot_script(self):
        """Найти скрипт запуска бота"""
        scripts = [
            'run_bot.py',
            'app/run_bot.py', 
            'bot.py',
            'anon_bot.py',
            'main.py'
        ]
        
        for script in scripts:
            if os.path.exists(script):
                logger.info(f"🔍 Найден скрипт бота: {script}")
                return script
        
        logger.error("❌ Скрипт бота не найден")
        return None
    
    async def find_bot_pid(self):
        """Найти PID процесса бота"""
        if not self.bot_script:
            return None
            
        script_name = os.path.basename(self.bot_script)
        
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                cmdline = proc.info['cmdline']
                if cmdline and len(cmdline) > 1:
                    # Проверяем запущен ли наш скрипт
                    if script_name in cmdline[1]:
                        return proc.info['pid']
            except (psutil.NoSuchProcess, psutil.AccessDenied, AttributeError):
                continue
        return None
    
    async def kill_bot(self):
        """Завершить процесс бота"""
        pid = await self.find_bot_pid()
        if not pid:
            logger.warning("⚠️ Процесс бота не найден")
            return True  # Считаем успехом если бот не запущен
        
        try:
            logger.info(f"⏹️ Завершаю процесс бота (PID: {pid})...")
            
            # 1. Мягкое завершение (SIGTERM)
            try:
                os.kill(pid, signal.SIGTERM)
            except ProcessLookupError:
                logger.info("✅ Процесс уже завершен")
                return True
            
            # 2. Ждем нормального завершения (до 5 секунд)
            for i in range(5):
                try:
                    proc = psutil.Process(pid)
                    status = proc.status()
                    logger.info(f"⏳ Ожидание... {i+1}/5 (статус: {status})")
                    await asyncio.sleep(1)
                except psutil.NoSuchProcess:
                    logger.info("✅ Процесс бота завершен")
                    break
            else:
                # 3. Принудительное завершение (SIGKILL)
                logger.warning("⚠️ Принудительное завершение процесса")
                try:
                    os.kill(pid, signal.SIGKILL)
                except:
                    pass
            
            # 4. Дополнительная пауза
            await asyncio.sleep(2)
            return True
            
        except Exception as e:
            logger.error(f"❌ Ошибка завершения: {e}")
            return False
    
    async def start_bot(self):
        """Запустить бота"""
        if not self.bot_script:
            logger.error("❌ Скрипт бота не найден")
            return False
        
        try:
            logger.info(f"🚀 Запускаю бота: {self.bot_script}")
            
            # Запускаем в фоне
            self.bot_process = subprocess.Popen(
                [sys.executable, self.bot_script],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                start_new_session=True,
                env={**os.environ, 'PYTHONUNBUFFERED': '1'}
            )
            
            logger.info(f"✅ Бот запущен (PID: {self.bot_process.pid})")
            
            # Ждем и проверяем что процесс жив
            await asyncio.sleep(3)
            
            if self.bot_process.poll() is None:
                logger.info("✅ Процесс работает стабильно")
                return True
            else:
                # Читаем ошибки если процесс упал
                stdout, stderr = self.bot_process.communicate()
                logger.error(f"❌ Процесс завершился сразу")
                logger.error(f"STDOUT: {stdout.decode()[:500]}")
                logger.error(f"STDERR: {stderr.decode()[:500]}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Ошибка запуска: {e}")
            return False
    
    async def restart_bot(self):
        """Перезапустить бота"""
        logger.info("🔄 Начинаю перезапуск бота...")
        
        # 1. Завершаем текущий процесс
        kill_success = await self.kill_bot()
        if not kill_success:
            logger.error("❌ Не удалось завершить бота")
            return False
        
        # 2. Короткая пауза
        await asyncio.sleep(2)
        
        # 3. Запускаем новый процесс
        start_success = await self.start_bot()
        if not start_success:
            logger.error("❌ Не удалось запустить бота")
            return False
        
        logger.info("🎉 Бот успешно перезапущен!")
        return True
    
    async def get_bot_status(self):
        """Получить статус бота"""
        pid = await self.find_bot_pid()
        
        if not pid:
            return {
                "status": "stopped",
                "pid": None,
                "running": False
            }
        
        try:
            proc = psutil.Process(pid)
            return {
                "status": "running",
                "pid": pid,
                "running": True,
                "cpu_percent": proc.cpu_percent(),
                "memory_percent": proc.memory_percent(),
                "create_time": datetime.fromtimestamp(proc.create_time()).isoformat(),
                "status_detail": proc.status()
            }
        except psutil.NoSuchProcess:
            return {
                "status": "stopped",
                "pid": pid,
                "running": False
            }

# Глобальный экземпляр
bot_restarter = BotRestarter()
