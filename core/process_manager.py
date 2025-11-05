"""Управление процессами Tor и Clash."""
import subprocess
import os
import logging
from typing import Optional
from dataclasses import dataclass

from stem import Signal
from stem.control import Controller

from .config import (
    TOR_PATH, TOR_RC, CLASH_PATH, 
    CREATE_NO_WINDOW, PROCESS_KILL_TIMEOUT,
    CLASH_PORT, DEFAULT_INTERVAL, CONTROL_PORT, CONTROL_PASSWORD
)
from .proxy_manager import enable_system_proxy, disable_system_proxy

logger = logging.getLogger(__name__)


@dataclass
class RotatorState:
    """Состояние процессов ротации."""
    tor_process: Optional[subprocess.Popen] = None
    clash_process: Optional[subprocess.Popen] = None
    enabled: bool = True
    interval_seconds: float = DEFAULT_INTERVAL * 3600
    ip_checker: Optional[object] = None  # IPChecker instance


class ProcessManager:
    """Singleton для управления процессами Tor и Clash."""
    
    _instance = None
    
    def __new__(cls):
        """Создает или возвращает существующий экземпляр."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.state = RotatorState()
        return cls._instance
    
    def start_tor(self) -> bool:
        """
        Запускает процесс Tor.
        
        Returns:
            True если успешно запущен, False при ошибке
        """
        # Проверка существования файлов
        if not os.path.exists(TOR_PATH):
            logger.error(f"Tor не найден: {TOR_PATH}")
            return False
        if not os.path.exists(TOR_RC):
            logger.error(f"Конфиг Tor не найден: {TOR_RC}")
            return False
        
        if not self.state.tor_process or self.state.tor_process.poll() is not None:
            try:
                self.state.tor_process = subprocess.Popen(
                    [TOR_PATH, "-f", TOR_RC],
                    creationflags=CREATE_NO_WINDOW
                )
                logger.info("Tor запущен")
                return True
            except FileNotFoundError:
                logger.error(f"Исполняемый файл не найден: {TOR_PATH}")
                return False
            except PermissionError:
                logger.error(f"Нет прав на запуск: {TOR_PATH}")
                return False
            except Exception as e:
                logger.error(f"Ошибка запуска Tor: {e}", exc_info=True)
                return False
        return True
    
    def stop_tor(self) -> None:
        """Останавливает процесс Tor."""
        self._stop_process(self.state.tor_process, "Tor")
        self.state.tor_process = None
    
    def start_clash(self) -> bool:
        """
        Запускает процесс Clash.
        
        Returns:
            True если успешно запущен, False при ошибке
        """
        # Проверка существования файла
        if not os.path.exists(CLASH_PATH):
            logger.error(f"Clash не найден: {CLASH_PATH}")
            return False
        
        if not self.state.clash_process or self.state.clash_process.poll() is not None:
            try:
                self.state.clash_process = subprocess.Popen(
                    [CLASH_PATH],
                    creationflags=CREATE_NO_WINDOW
                )
                enable_system_proxy(CLASH_PORT)
                logger.info("Clash запущен")
                return True
            except FileNotFoundError:
                logger.error(f"Исполняемый файл не найден: {CLASH_PATH}")
                return False
            except PermissionError:
                logger.error(f"Нет прав на запуск: {CLASH_PATH}")
                return False
            except Exception as e:
                logger.error(f"Ошибка запуска Clash: {e}", exc_info=True)
                return False
        return True
    
    def stop_clash(self) -> None:
        """Останавливает процесс Clash."""
        self._stop_process(self.state.clash_process, "Clash")
        self.state.clash_process = None
        disable_system_proxy()
    
    def change_ip(self) -> str:
        """
        Меняет IP через Tor и возвращает новый адрес.
        
        Returns:
            Новый IP адрес или "—" при ошибке
        """
        try:
            # Отправка сигнала NEWNYM в Tor
            with Controller.from_port(port=CONTROL_PORT) as controller:
                controller.authenticate(password=CONTROL_PASSWORD)
                controller.signal(Signal.NEWNYM)
            
            # Получение нового IP
            if self.state.ip_checker:
                new_ip = self.state.ip_checker.get_ip()
                logger.info(f"IP изменён: {new_ip}")
                return new_ip
            else:
                logger.warning("IP checker не инициализирован")
                return "—"
                
        except Exception as e:
            logger.error(f"Ошибка смены IP: {e}", exc_info=True)
            return "—"
    
    def _stop_process(self, process: Optional[subprocess.Popen], name: str) -> None:
        """
        Корректно завершает процесс с таймаутом.
        
        Args:
            process: Процесс для завершения
            name: Имя процесса для логирования
        """
        if process and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=PROCESS_KILL_TIMEOUT)
                logger.info(f"{name} остановлен")
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
                logger.warning(f"{name} принудительно завершен")
