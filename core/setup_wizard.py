"""
Setup Wizard для первого запуска.
Автоматический поиск Tor/Clash и генерация конфигов.
"""
import os
import logging
import subprocess
import secrets
import string
from pathlib import Path
from typing import Optional, Tuple
import threading

logger = logging.getLogger(__name__)


class SetupWizard:
    """Мастер настройки для первого запуска."""
    
    # Приоритетные директории для поиска
    SEARCH_PATHS = [
        Path(os.environ.get('PROGRAMFILES', 'C:\\Program Files')),
        Path(os.environ.get('PROGRAMFILES(X86)', 'C:\\Program Files (x86)')),
        Path(os.environ.get('LOCALAPPDATA', os.path.expanduser('~\\AppData\\Local'))),
        Path(os.path.expanduser('~\\Downloads')),
        Path('C:\\'),
    ]
    
    # Дефолтный torrc конфиг (хеш будет заменён)
    TORRC_TEMPLATE = """SocksPort 9050
ControlPort 9061
HashedControlPassword {hashed_password}
CookieAuthentication 0
"""
    
    # Дефолтный Clash конфиг
    CLASH_CONFIG_TEMPLATE = """port: 7890
socks-port: 7891
allow-lan: false
mode: Global
log-level: info
external-controller: 127.0.0.1:9090

proxies:
  - name: "Tor"
    type: socks5
    server: 127.0.0.1
    port: 9050

proxy-groups:
  - name: "PROXY"
    type: select
    proxies:
      - "Tor"

rules:
  - MATCH,PROXY
"""
    
    def __init__(self):
        self.tor_path: Optional[Path] = None
        self.clash_path: Optional[Path] = None
        self.search_cancelled = False
        self.generated_password: Optional[str] = None
        self.hashed_password: Optional[str] = None
        
    def find_executable(self, filename: str, max_depth: int = 4) -> Optional[Path]:
        """
        Поиск исполняемого файла в приоритетных директориях.
        
        Args:
            filename: Имя файла для поиска (например, 'tor.exe')
            max_depth: Максимальная глубина поиска
            
        Returns:
            Path к найденному файлу или None
        """
        logger.info(f"Поиск {filename}...")
        
        for search_path in self.SEARCH_PATHS:
            if self.search_cancelled:
                return None
                
            if not search_path.exists():
                continue
                
            logger.debug(f"Сканирование {search_path}")
            
            try:
                result = self._search_in_directory(search_path, filename, max_depth)
                if result:
                    logger.info(f"Найден {filename}: {result}")
                    return result
            except PermissionError:
                logger.debug(f"Нет доступа к {search_path}")
                continue
                
        logger.warning(f"{filename} не найден")
        return None
    
    # Папки для исключения из поиска
    EXCLUDED_DIRS = {
        '$recycle.bin',
        'windows',
        'system volume information',
        'programdata',
        'perflogs',
        'recovery',
        '$windows.~bt',
        '$windows.~ws',
        'windows.old',
    }
    
    def _search_in_directory(self, directory: Path, filename: str, max_depth: int, current_depth: int = 0) -> Optional[Path]:
        """Рекурсивный поиск файла в директории."""
        if current_depth > max_depth or self.search_cancelled:
            return None
        
        # Исключаем системные папки
        if directory.name.lower() in self.EXCLUDED_DIRS:
            return None
            
        try:
            for item in directory.iterdir():
                if self.search_cancelled:
                    return None
                
                # Исключаем скрытые и системные папки
                if item.name.startswith('.') or item.name.startswith('$'):
                    continue
                    
                if item.is_file() and item.name.lower() == filename.lower():
                    return item
                    
                if item.is_dir():
                    result = self._search_in_directory(item, filename, max_depth, current_depth + 1)
                    if result:
                        return result
        except (PermissionError, OSError):
            pass
            
        return None
    
    def search_all(self, progress_callback=None) -> Tuple[Optional[Path], Optional[Path]]:
        """
        Поиск Tor и Clash.
        
        Args:
            progress_callback: Функция для обновления прогресса (message: str)
            
        Returns:
            Tuple (tor_path, clash_path)
        """
        self.search_cancelled = False
        
        if progress_callback:
            progress_callback("Поиск Tor...")
        self.tor_path = self.find_executable('tor.exe')
        
        if progress_callback:
            progress_callback("Поиск Clash...")
        self.clash_path = self.find_executable('Clash for Windows.exe')
        
        if not self.clash_path:
            self.clash_path = self.find_executable('clash.exe')
        
        return self.tor_path, self.clash_path
    
    def cancel_search(self):
        """Отмена поиска."""
        self.search_cancelled = True
        logger.info("Поиск отменён пользователем")
    
    def generate_password(self, length: int = 16) -> str:
        """
        Генерация случайного пароля.
        
        Args:
            length: Длина пароля
            
        Returns:
            Сгенерированный пароль
        """
        alphabet = string.ascii_letters + string.digits
        password = ''.join(secrets.choice(alphabet) for _ in range(length))
        self.generated_password = password
        logger.info("Сгенерирован новый пароль")
        return password
    
    def hash_password(self, tor_exe_path: Path, password: str) -> Optional[str]:
        """
        Генерация хеша пароля через tor --hash-password.
        
        Args:
            tor_exe_path: Путь к tor.exe
            password: Пароль для хеширования
            
        Returns:
            Хешированный пароль или None при ошибке
        """
        try:
            result = subprocess.run(
                [str(tor_exe_path), '--hash-password', password],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                # Tor выводит хеш в stdout
                hashed = result.stdout.strip()
                # Убираем возможные лишние строки (Tor может выводить предупреждения)
                lines = hashed.split('\n')
                for line in lines:
                    if line.startswith('16:'):
                        self.hashed_password = line
                        logger.info("Пароль успешно хеширован")
                        return line
                
                logger.error("Не найден хеш в выводе Tor")
                return None
            else:
                logger.error(f"Ошибка хеширования пароля: {result.stderr}")
                return None
                
        except subprocess.TimeoutExpired:
            logger.error("Таймаут при хешировании пароля")
            return None
        except Exception as e:
            logger.error(f"Ошибка при вызове tor --hash-password: {e}")
            return None
    
    def generate_torrc(self, output_path: Path, hashed_password: str) -> bool:
        """
        Генерация torrc файла с хешированным паролем.
        
        Args:
            output_path: Путь для сохранения torrc
            hashed_password: Хешированный пароль от Tor
            
        Returns:
            True если успешно
        """
        try:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            torrc_content = self.TORRC_TEMPLATE.format(hashed_password=hashed_password)
            output_path.write_text(torrc_content, encoding='utf-8')
            logger.info(f"Создан torrc: {output_path}")
            return True
        except Exception as e:
            logger.error(f"Ошибка создания torrc: {e}")
            return False
    
    def generate_clash_config(self, output_path: Path) -> bool:
        """
        Генерация Clash конфига.
        
        Args:
            output_path: Путь для сохранения global.txt
            
        Returns:
            True если успешно
        """
        try:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(self.CLASH_CONFIG_TEMPLATE, encoding='utf-8')
            logger.info(f"Создан Clash конфиг: {output_path}")
            return True
        except Exception as e:
            logger.error(f"Ошибка создания Clash конфига: {e}")
            return False
    
    def generate_env_file(self, env_path: Path, tor_path: Path, torrc_path: Path, 
                         clash_path: Path, password: str = "your_password") -> bool:
        """
        Генерация .env файла.
        
        Args:
            env_path: Путь для .env
            tor_path: Путь к tor.exe
            torrc_path: Путь к torrc
            clash_path: Путь к Clash
            password: Пароль для Tor Control (дефолтный: your_password)
            
        Returns:
            True если успешно
        """
        env_content = f"""# Tor Configuration
TOR_PATH={tor_path}
TOR_RC={torrc_path}
CONTROL_PASSWORD={password}
CONTROL_PORT=9061

# Clash Configuration
CLASH_PATH={clash_path}
CLASH_PORT=7890
"""
        
        try:
            env_path.write_text(env_content, encoding='utf-8')
            logger.info(f"Создан .env: {env_path}")
            return True
        except Exception as e:
            logger.error(f"Ошибка создания .env: {e}")
            return False
