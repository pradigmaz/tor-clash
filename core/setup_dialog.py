"""
GUI диалог для Setup Wizard.
"""
from kivymd.uix.dialog import MDDialog
from kivymd.uix.button import MDFlatButton, MDRaisedButton
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.label import MDLabel
from kivymd.uix.textfield import MDTextField
from kivymd.uix.progressbar import MDProgressBar
from kivy.metrics import dp
from pathlib import Path
import threading
import logging
import webbrowser

from core.setup_wizard import SetupWizard

logger = logging.getLogger(__name__)


class SetupDialog:
    """Диалог первоначальной настройки."""
    
    def __init__(self, on_complete_callback):
        """
        Args:
            on_complete_callback: Функция, вызываемая после успешной настройки
        """
        self.wizard = SetupWizard()
        self.on_complete = on_complete_callback
        self.dialog = None
        self.status_label = None
        self.progress_bar = None
        self.tor_field = None
        self.clash_field = None
        
    def show(self):
        """Показать диалог настройки."""
        content = MDBoxLayout(
            orientation='vertical',
            spacing=dp(10),
            size_hint_y=None,
            height=dp(400)
        )
        
        # Заголовок
        title_label = MDLabel(
            text="Первый запуск - настройка приложения",
            font_style="H6",
            size_hint_y=None,
            height=dp(30)
        )
        content.add_widget(title_label)
        
        # Ссылки для скачивания
        from kivymd.uix.button import MDFlatButton
        download_box = MDBoxLayout(
            orientation='horizontal',
            spacing=dp(5),
            size_hint_y=None,
            height=dp(40),
            padding=[0, dp(5), 0, dp(5)]
        )
        
        download_label = MDLabel(
            text="Скачать:",
            size_hint_x=0.2,
            font_style="Caption"
        )
        download_box.add_widget(download_label)
        
        tor_link_btn = MDFlatButton(
            text="Tor",
            size_hint_x=0.25,
            on_release=lambda x: self._open_url("https://www.torproject.org/download/tor/")
        )
        download_box.add_widget(tor_link_btn)
        
        clash_link_btn = MDFlatButton(
            text="Clash",
            size_hint_x=0.25,
            on_release=lambda x: self._open_url("https://www.clashforwindows.net/clash-for-windows-download/")
        )
        download_box.add_widget(clash_link_btn)
        
        python_link_btn = MDFlatButton(
            text="Python",
            size_hint_x=0.3,
            on_release=lambda x: self._open_url("https://www.python.org/downloads/")
        )
        download_box.add_widget(python_link_btn)
        
        content.add_widget(download_box)
        
        # Статус поиска
        self.status_label = MDLabel(
            text="Нажмите 'Автопоиск' для поиска Tor и Clash\n(Tor: распакуйте .tar.gz архив)",
            size_hint_y=None,
            height=dp(50),
            font_style="Body2"
        )
        content.add_widget(self.status_label)
        
        # Прогресс-бар
        self.progress_bar = MDProgressBar(
            size_hint_y=None,
            height=dp(4)
        )
        content.add_widget(self.progress_bar)
        
        # Поле Tor
        self.tor_field = MDTextField(
            hint_text="Путь к tor.exe",
            helper_text="Будет найден автоматически или укажите вручную",
            helper_text_mode="on_focus",
            size_hint_y=None,
            height=dp(60)
        )
        content.add_widget(self.tor_field)
        
        # Поле Clash
        self.clash_field = MDTextField(
            hint_text="Путь к Clash for Windows.exe",
            helper_text="Будет найден автоматически или укажите вручную",
            helper_text_mode="on_focus",
            size_hint_y=None,
            height=dp(60)
        )
        content.add_widget(self.clash_field)
        
        # Кнопки
        self.dialog = MDDialog(
            title="Настройка",
            type="custom",
            content_cls=content,
            buttons=[
                MDFlatButton(
                    text="ОТМЕНА",
                    on_release=self._on_cancel
                ),
                MDRaisedButton(
                    text="АВТОПОИСК",
                    on_release=self._on_auto_search
                ),
                MDRaisedButton(
                    text="ГОТОВО",
                    on_release=self._on_complete
                ),
            ],
        )
        
        self.dialog.open()
    
    def _on_auto_search(self, *args):
        """Запуск автопоиска."""
        self.status_label.text = "Поиск файлов..."
        self.progress_bar.start()
        
        # Запуск в отдельном потоке
        thread = threading.Thread(target=self._search_thread, daemon=True)
        thread.start()
    
    def _search_thread(self):
        """Поток поиска файлов."""
        def update_status(message):
            self.status_label.text = message
        
        tor_path, clash_path = self.wizard.search_all(progress_callback=update_status)
        
        # Обновление UI в главном потоке
        from kivy.clock import Clock
        Clock.schedule_once(lambda dt: self._on_search_complete(tor_path, clash_path))
    
    def _on_search_complete(self, tor_path, clash_path):
        """Обработка результатов поиска."""
        self.progress_bar.stop()
        
        if tor_path:
            self.tor_field.text = str(tor_path)
            
        if clash_path:
            self.clash_field.text = str(clash_path)
        
        if tor_path and clash_path:
            self.status_label.text = "✓ Все файлы найдены! Нажмите 'Готово'"
        elif tor_path or clash_path:
            self.status_label.text = "⚠ Некоторые файлы не найдены. Укажите вручную"
        else:
            self.status_label.text = "✗ Файлы не найдены. Укажите пути вручную"
    
    def _on_complete(self, *args):
        """Завершение настройки."""
        tor_path = self.tor_field.text.strip()
        clash_path = self.clash_field.text.strip()
        
        if not tor_path:
            self.status_label.text = "✗ Укажите путь к Tor!"
            return
        
        if not clash_path:
            self.status_label.text = "✗ Укажите путь к Clash!"
            return
        
        # Проверка существования файлов
        tor_path_obj = Path(tor_path)
        if not tor_path_obj.exists():
            self.status_label.text = "✗ Tor не найден по указанному пути!"
            return
            
        clash_path_obj = Path(clash_path)
        if not clash_path_obj.exists():
            self.status_label.text = "✗ Clash не найден по указанному пути!"
            return
        
        # Генерация конфигов
        self.status_label.text = "Генерация пароля и хеширование..."
        
        try:
            # Генерация пароля
            password = self.wizard.generate_password()
            
            # Хеширование пароля через Tor
            hashed = self.wizard.hash_password(tor_path_obj, password)
            if not hashed:
                self.status_label.text = "✗ Ошибка хеширования пароля!"
                return
            
            self.status_label.text = "Создание конфигурационных файлов..."
            
            # Создание torrc с хешированным паролем
            torrc_path = Path('torrc')
            self.wizard.generate_torrc(torrc_path, hashed)
            
            # Создание Clash конфига
            clash_config_path = Path('global.txt')
            self.wizard.generate_clash_config(clash_config_path)
            
            # Создание .env с оригинальным паролем
            env_path = Path('.env')
            self.wizard.generate_env_file(
                env_path,
                tor_path_obj,
                torrc_path.absolute(),
                clash_path_obj,
                password=password
            )
            
            logger.info("Настройка завершена успешно")
            self.dialog.dismiss()
            
            # Вызов callback
            if self.on_complete:
                self.on_complete()
                
        except Exception as e:
            logger.error(f"Ошибка при создании конфигов: {e}")
            self.status_label.text = f"✗ Ошибка: {e}"
    
    def _on_cancel(self, *args):
        """Отмена настройки."""
        self.wizard.cancel_search()
        self.dialog.dismiss()
    
    def _open_url(self, url: str):
        """
        Открыть URL в браузере.
        
        Args:
            url: Ссылка для открытия
        """
        try:
            webbrowser.open(url)
            logger.info(f"Открыта ссылка: {url}")
        except Exception as e:
            logger.error(f"Ошибка открытия ссылки: {e}")
