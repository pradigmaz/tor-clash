"""Конфигурация приложения."""
import os
import logging
from pathlib import Path
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# Загрузка конфигурации из .env (если файл существует)
load_dotenv()

# Пути к исполняемым файлам
TOR_PATH = os.getenv("TOR_PATH")
TOR_RC = os.getenv("TOR_RC")
CLASH_PATH = os.getenv("CLASH_PATH")

# Сетевые настройки
CONTROL_PASSWORD = os.getenv("CONTROL_PASSWORD")
CONTROL_PORT = int(os.getenv("CONTROL_PORT", "9061"))
CLASH_PORT = int(os.getenv("CLASH_PORT", "7890"))

# Константы процессов
CREATE_NO_WINDOW = 0x08000000
PROCESS_KILL_TIMEOUT = 5

# Константы интервалов
DEFAULT_INTERVAL = 1

def is_configured() -> bool:
    """
    Проверка, настроено ли приложение.
    
    Returns:
        True если все обязательные переменные установлены
    """
    return all([TOR_PATH, TOR_RC, CLASH_PATH, CONTROL_PASSWORD])

def validate_config():
    """
    Валидация конфигурации с выбросом исключения при ошибке.
    Используется только после первоначальной настройки.
    """
    if not is_configured():
        logger.error("Не все обязательные переменные установлены в .env файле")
        raise ValueError("Отсутствуют обязательные переменные окружения. Проверьте .env файл.")
