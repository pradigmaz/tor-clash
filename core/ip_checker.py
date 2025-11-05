"""Проверка IP адреса через различные методы."""
import logging
import time
import requests
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


class IPChecker(ABC):
    """Абстрактный класс для проверки IP адреса."""
    
    @abstractmethod
    def get_ip(self) -> str:
        """
        Получает текущий IP адрес.
        
        Returns:
            IP адрес или "—" при ошибке
        """
        pass


class ClashIPChecker(IPChecker):
    """Проверка IP через Clash прокси с автоматическим переподключением."""
    
    def __init__(self, port: int, max_retries: int = 3, initial_delay: float = 1.0):
        """
        Инициализация проверки IP через Clash.
        
        Args:
            port: Порт Clash прокси
            max_retries: Максимальное количество попыток (по умолчанию 3)
            initial_delay: Начальная задержка между попытками в секундах (по умолчанию 1.0)
        """
        self.port = port
        self.max_retries = max_retries
        self.initial_delay = initial_delay
    
    def get_ip(self) -> str:
        """
        Получает IP через Clash прокси с retry логикой.
        
        Использует exponential backoff для повторных попыток:
        - Попытка 1: без задержки
        - Попытка 2: задержка initial_delay (1 сек)
        - Попытка 3: задержка initial_delay * 2 (2 сек)
        
        Returns:
            IP адрес или "—" при ошибке после всех попыток
        """
        proxies = {
            "http": f"http://127.0.0.1:{self.port}",
            "https": f"http://127.0.0.1:{self.port}"
        }
        
        last_error = None
        for attempt in range(self.max_retries):
            try:
                r = requests.get("https://api.ipify.org", proxies=proxies, timeout=10)
                r.raise_for_status()
                ip = r.text.strip()
                
                if attempt > 0:
                    logger.info(f"Получен IP: {ip} (попытка {attempt + 1})")
                else:
                    logger.info(f"Получен IP: {ip}")
                
                return ip
                
            except requests.exceptions.ProxyError as e:
                last_error = e
                if attempt < self.max_retries - 1:
                    delay = self.initial_delay * (2 ** attempt)
                    logger.warning(f"Clash не готов, повтор через {delay:.1f} сек (попытка {attempt + 1}/{self.max_retries})")
                    time.sleep(delay)
                    
            except requests.RequestException as e:
                last_error = e
                if attempt < self.max_retries - 1:
                    delay = self.initial_delay * (2 ** attempt)
                    logger.warning(f"Ошибка запроса, повтор через {delay:.1f} сек (попытка {attempt + 1}/{self.max_retries})")
                    time.sleep(delay)
                    
            except Exception as e:
                last_error = e
                logger.error(f"Неожиданная ошибка получения IP: {e}")
                break
        
        # Все попытки исчерпаны
        logger.error(f"Не удалось получить IP после {self.max_retries} попыток: {last_error}")
        return "—"


class DirectIPChecker(IPChecker):
    """Проверка IP напрямую (без прокси)."""
    
    def get_ip(self) -> str:
        """
        Получает IP напрямую без прокси.
        
        Returns:
            IP адрес или "—" при ошибке
        """
        try:
            r = requests.get("https://api.ipify.org", timeout=10)
            r.raise_for_status()
            ip = r.text.strip()
            logger.info(f"Получен IP (прямое подключение): {ip}")
            return ip
        except requests.RequestException as e:
            logger.error(f"Ошибка HTTP запроса: {e}")
            return "—"
