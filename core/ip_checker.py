"""Проверка IP адреса через различные методы."""
import logging
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
    """Проверка IP через Clash прокси."""
    
    def __init__(self, port: int):
        """
        Инициализация проверки IP через Clash.
        
        Args:
            port: Порт Clash прокси
        """
        self.port = port
    
    def get_ip(self) -> str:
        """
        Получает IP через Clash прокси.
        
        Returns:
            IP адрес или "—" при ошибке
        """
        proxies = {
            "http": f"http://127.0.0.1:{self.port}",
            "https": f"http://127.0.0.1:{self.port}"
        }
        try:
            r = requests.get("https://api.ipify.org", proxies=proxies, timeout=10)
            r.raise_for_status()
            ip = r.text.strip()
            logger.info(f"Получен IP: {ip}")
            return ip
        except requests.RequestException as e:
            logger.error(f"Ошибка HTTP запроса: {e}")
            return "—"
        except Exception as e:
            logger.error(f"Ошибка получения IP: {e}")
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
