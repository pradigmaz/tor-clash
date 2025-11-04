"""Управление системным прокси Windows."""
import subprocess
import logging

logger = logging.getLogger(__name__)


def enable_system_proxy(port: int) -> None:
    """
    Включает системный прокси Windows через реестр.
    
    Args:
        port: Порт прокси-сервера
        
    Raises:
        subprocess.CalledProcessError: При ошибке записи в реестр
    """
    try:
        subprocess.run([
            "reg", "add",
            r"HKCU\Software\Microsoft\Windows\CurrentVersion\Internet Settings",
            "/v", "ProxyEnable", "/t", "REG_DWORD", "/d", "1", "/f"
        ], check=True)
        subprocess.run([
            "reg", "add",
            r"HKCU\Software\Microsoft\Windows\CurrentVersion\Internet Settings",
            "/v", "ProxyServer", "/t", "REG_SZ", "/d", f"127.0.0.1:{port}", "/f"
        ], check=True)
        logger.info(f"Системный прокси включен на порту {port}")
    except subprocess.CalledProcessError as e:
        logger.error(f"Ошибка записи в реестр: {e}")
    except Exception as e:
        logger.error(f"Ошибка включения системного прокси: {e}")


def disable_system_proxy() -> None:
    """
    Выключает системный прокси Windows через реестр.
    
    Raises:
        subprocess.CalledProcessError: При ошибке записи в реестр
    """
    try:
        subprocess.run([
            "reg", "add",
            r"HKCU\Software\Microsoft\Windows\CurrentVersion\Internet Settings",
            "/v", "ProxyEnable", "/t", "REG_DWORD", "/d", "0", "/f"
        ], check=True)
        logger.info("Системный прокси выключен")
    except subprocess.CalledProcessError as e:
        logger.error(f"Ошибка записи в реестр: {e}")
    except Exception as e:
        logger.error(f"Ошибка выключения системного прокси: {e}")
