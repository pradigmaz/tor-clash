"""Главное приложение для ротации IP через Tor и Clash."""
import time
import threading
import logging
import signal
import atexit
from pathlib import Path
from typing import Any, Callable
from concurrent.futures import ThreadPoolExecutor
from stem import Signal
from stem.control import Controller

from kivymd.app import MDApp
from kivymd.uix.screen import MDScreen
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.label import MDLabel
from kivymd.uix.button import (
    MDRaisedButton, 
    MDFlatButton, 
    MDRectangleFlatButton, 
    MDIconButton, 
    MDFillRoundFlatButton
)
from kivymd.uix.textfield import MDTextField
from kivymd.uix.menu import MDDropdownMenu
from kivymd.uix.card import MDCard
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.metrics import dp
from kivy.lang import Builder

from core.process_manager import ProcessManager
from core.ip_checker import ClashIPChecker
from core import config
from core.validator import IntervalValidator
from core.setup_dialog import SetupDialog

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# UI константы
WINDOW_WIDTH = 550
WINDOW_HEIGHT = 400
STATUS_CARD_HEIGHT = dp(140)
INTERVAL_CARD_HEIGHT = dp(90)
TOGGLE_CARD_HEIGHT = dp(70)
CHANGE_IP_BUTTON_HEIGHT = dp(60)
IP_BOX_HEIGHT = dp(50)
INTERVAL_BOX_HEIGHT = dp(50)
INTERVAL_TITLE_HEIGHT = dp(25)

# Цвета состояний
COLOR_ENABLED = (0.3, 0.9, 0.3, 1)
COLOR_DISABLED = (0.9, 0.3, 0.3, 1)

# Размеры отступов
PADDING = dp(20)
SPACING = dp(15)
CARD_PADDING = dp(15)
CARD_SPACING = dp(10)

# Валидация интервалов
MIN_INTERVAL_SECONDS = 1
MAX_INTERVAL_SECONDS = 86400
MIN_INTERVAL_MINUTES = 0.01
MAX_INTERVAL_MINUTES = 1440
MIN_INTERVAL_HOURS = 0.01
MAX_INTERVAL_HOURS = 24

# KV для MDSwitch
KV = '''
#:import MDSwitch kivymd.uix.selectioncontrol.MDSwitch

<ToggleCard>:
    orientation: 'vertical'
    padding: dp(15)
    size_hint: 1, None
    height: dp(70)
    elevation: 2
    
    MDBoxLayout:
        spacing: dp(10)
        
        MDLabel:
            text: "Автоматическая ротация"
            size_hint_x: 0.6
        
        MDSwitch:
            id: rotation_switch
            active: True
            size_hint_x: 0.4
            pos_hint: {"center_y": 0.5}
'''

# GUI
class RotatorApp(MDApp):
    """
    Главное приложение для ротации IP через Tor и Clash.
    
    Attributes:
        process_manager: Менеджер процессов Tor и Clash
        ip_checker: Проверка IP адреса
        unit_value: Текущая единица измерения интервала
        ip_label: Label для отображения текущего IP
        state_label: Label для отображения состояния ротации
        rotation_switch: Переключатель автоматической ротации
    """
    
    def __init__(self) -> None:
        """Инициализация приложения с регистрацией обработчиков завершения."""
        super().__init__()
        self.process_manager = None
        self.ip_checker = None
        self.executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="rotator")
        self.stop_event = threading.Event()
        self.rotation_event = threading.Event()
        
        # Инициализация менеджеров только если конфиг готов
        if config.is_configured():
            self._init_managers()
        
        # Регистрация обработчиков завершения
        atexit.register(self.cleanup)
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _init_managers(self):
        """Инициализация менеджеров процессов и IP."""
        self.process_manager = ProcessManager()
        self.ip_checker = ClashIPChecker(config.CLASH_PORT)
    
    def _signal_handler(self, signum: int, frame: Any) -> None:
        """
        Обработчик сигналов завершения (SIGINT, SIGTERM).
        
        Args:
            signum: Номер сигнала
            frame: Текущий фрейм стека
        """
        logger.info(f"Получен сигнал {signum}, завершение...")
        self.cleanup()
        exit(0)
    
    def build(self) -> MDScreen:
        """
        Создает и возвращает корневой виджет приложения.
        
        Returns:
            MDScreen: Главный экран приложения
        """
        # Проверка первого запуска
        if not config.is_configured():
            logger.info("Первый запуск - показываем мастер настройки")
            Clock.schedule_once(lambda dt: self.show_setup_wizard(force=True), 0.5)
        
        Builder.load_string(KV)
        
        Window.size = (WINDOW_WIDTH, WINDOW_HEIGHT)
        self.title = "Tor + Clash Rotator"
        self.theme_cls.theme_style = "Dark"
        self.theme_cls.primary_palette = "DeepPurple"
        
        self.unit_value = "часов"
        
        screen = MDScreen()
        layout = MDBoxLayout(orientation='vertical', padding=PADDING, spacing=SPACING)
        
        # Status Card (IP + State)
        status_card = MDCard(
            orientation='vertical',
            padding=CARD_PADDING,
            size_hint=(1, None),
            height=STATUS_CARD_HEIGHT,
            elevation=2
        )
        
        # IP with copy button
        ip_box = MDBoxLayout(spacing=CARD_SPACING, size_hint_y=None, height=IP_BOX_HEIGHT)
        self.ip_label = MDLabel(
            text="Текущий IP: —",
            halign="left",
            font_style="H6",
            size_hint_x=0.85
        )
        ip_box.add_widget(self.ip_label)
        
        copy_btn = MDIconButton(
            icon="content-copy",
            size_hint_x=0.15
        )
        copy_btn.bind(on_release=self.copy_ip)
        ip_box.add_widget(copy_btn)
        
        status_card.add_widget(ip_box)
        
        # State label
        self.state_label = MDLabel(
            text="Ротация: Включена",
            halign="center",
            font_style="H5",
            theme_text_color="Custom",
            text_color=COLOR_ENABLED,
            size_hint_y=None,
            height=dp(60)
        )
        status_card.add_widget(self.state_label)
        
        layout.add_widget(status_card)
        
        # Interval Settings Card
        interval_card = MDCard(
            orientation='vertical',
            padding=CARD_PADDING,
            size_hint=(1, None),
            height=INTERVAL_CARD_HEIGHT,
            elevation=2
        )
        
        interval_title = MDLabel(
            text="Интервал ротации",
            font_style="Subtitle1",
            size_hint_y=None,
            height=INTERVAL_TITLE_HEIGHT
        )
        interval_card.add_widget(interval_title)
        
        interval_box = MDBoxLayout(spacing=CARD_SPACING, size_hint_y=None, height=INTERVAL_BOX_HEIGHT)
        
        self.interval_input = MDTextField(
            text=str(config.DEFAULT_INTERVAL),
            mode="rectangle",
            size_hint_x=0.3
        )
        interval_box.add_widget(self.interval_input)
        
        self.unit_btn = MDRectangleFlatButton(
            text="часов",
            size_hint_x=0.35
        )
        self.unit_btn.bind(on_release=self.show_unit_menu)
        interval_box.add_widget(self.unit_btn)
        
        self.apply_btn = MDRaisedButton(
            text="Установить",
            size_hint_x=0.35
        )
        self.apply_btn.bind(on_release=self.apply_interval)
        interval_box.add_widget(self.apply_btn)
        
        interval_card.add_widget(interval_box)
        layout.add_widget(interval_card)
        
        # Toggle Card with Switch
        toggle_card_content = Builder.load_string('''
MDCard:
    orientation: 'vertical'
    padding: dp(15)
    size_hint: 1, None
    height: dp(70)
    elevation: 2
    
    MDBoxLayout:
        spacing: dp(10)
        
        MDLabel:
            text: "Автоматическая ротация"
            size_hint_x: 0.7
            valign: "center"
        
        MDSwitch:
            id: rotation_switch
            active: True
            size_hint: None, None
            size: dp(36), dp(48)
            pos_hint: {"center_y": 0.5}
        ''')
        self.rotation_switch = toggle_card_content.ids.rotation_switch
        self.rotation_switch.bind(active=self.on_switch_active)
        layout.add_widget(toggle_card_content)
        
        # Buttons Box
        buttons_box = MDBoxLayout(
            spacing=CARD_SPACING,
            size_hint=(1, None),
            height=CHANGE_IP_BUTTON_HEIGHT
        )
        
        # Change IP Button
        self.change_btn = MDFillRoundFlatButton(
            text="Сменить IP сейчас",
            size_hint_x=0.7
        )
        self.change_btn.bind(on_release=lambda x: self.change_ip())
        buttons_box.add_widget(self.change_btn)
        
        # Reconfigure Button
        from kivymd.uix.tooltip import MDTooltip
        from kivymd.uix.button import MDRaisedButton as BaseButton
        
        class TooltipButton(BaseButton, MDTooltip):
            pass
        
        self.reconfig_btn = TooltipButton(
            text="⚙",
            size_hint_x=0.3,
            tooltip_text="Перенастроить приложение"
        )
        self.reconfig_btn.bind(on_release=lambda x: self.show_setup_wizard())
        buttons_box.add_widget(self.reconfig_btn)
        
        layout.add_widget(buttons_box)
        
        screen.add_widget(layout)
        
        # Создание меню для выбора единиц
        menu_items = [
            {"text": "секунд", "on_release": lambda x="секунд": self.set_unit(x)},
            {"text": "минут", "on_release": lambda x="минут": self.set_unit(x)},
            {"text": "часов", "on_release": lambda x="часов": self.set_unit(x)},
        ]
        self.unit_menu = MDDropdownMenu(
            caller=self.unit_btn,
            items=menu_items,
            width_mult=3
        )
        
        # Запуск фонового потока
        self.start_rotator_thread()
        
        # Автозапуск только если конфиг готов
        if self.process_manager:
            self.process_manager.start_tor()
            self.process_manager.start_clash()
            Clock.schedule_once(lambda dt: self.change_ip(), 1)
        
        return screen
    
    def show_unit_menu(self, instance: Any) -> None:
        """
        Открывает меню выбора единиц измерения.
        
        Args:
            instance: Виджет, вызвавший событие
        """
        self.unit_menu.open()
    
    def set_unit(self, unit: str) -> None:
        """
        Устанавливает единицу измерения интервала.
        
        Args:
            unit: Единица измерения (секунд/минут/часов)
        """
        self.unit_value = unit
        self.unit_btn.text = unit
        self.unit_menu.dismiss()
    
    def copy_ip(self, instance: Any) -> None:
        """
        Копирует текущий IP в буфер обмена.
        
        Args:
            instance: Виджет, вызвавший событие
        """
        from kivy.core.clipboard import Clipboard
        ip_text = self.ip_label.text
        if ":" in ip_text:
            ip = ip_text.split(": ", 1)[1]
            if ip != "—" and ip != "Ошибка смены IP":
                Clipboard.copy(ip)
                logger.info(f"IP скопирован в буфер: {ip}")
    
    def on_switch_active(self, instance: Any, value: bool) -> None:
        """
        Обработчик переключателя автоматической ротации.
        
        Args:
            instance: Виджет переключателя
            value: Новое состояние (True/False)
        """
        if not self.process_manager:
            logger.warning("Process manager не инициализирован")
            return
            
        self.process_manager.state.enabled = value
        if value:
            self.process_manager.start_tor()
            self.process_manager.start_clash()
            self.state_label.text = "Ротация: Включена"
            self.state_label.text_color = COLOR_ENABLED
            # Активируем элементы управления
            self.interval_input.disabled = False
            self.unit_btn.disabled = False
            self.apply_btn.disabled = False
            logger.info("Ротация включена")
        else:
            self.process_manager.stop_tor()
            self.process_manager.stop_clash()
            self.state_label.text = "Ротация: Выключена"
            self.state_label.text_color = COLOR_DISABLED
            # Деактивируем элементы управления
            self.interval_input.disabled = True
            self.unit_btn.disabled = True
            self.apply_btn.disabled = True
            logger.info("Ротация выключена")
    
    def apply_interval(self, instance: Any) -> None:
        """
        Применяет новый интервал ротации с валидацией.
        
        Args:
            instance: Виджет кнопки
        """
        if not self.process_manager:
            logger.warning("Process manager не инициализирован")
            return
            
        try:
            v = float(self.interval_input.text)
            unit = self.unit_value
            
            # Валидация через IntervalValidator
            is_valid, error_msg = IntervalValidator.validate(v, unit)
            if not is_valid:
                logger.warning(error_msg)
                return
            
            # Конвертация в секунды
            self.process_manager.state.interval_seconds = IntervalValidator.to_seconds(v, unit)
            
            logger.info(f"Интервал установлен: {v} {unit} ({self.process_manager.state.interval_seconds} сек)")
            
            # Прерываем ожидание для немедленного применения нового интервала
            self.rotation_event.set()
        except ValueError:
            logger.error("Некорректное значение интервала")
    
    def change_ip(self) -> None:
        """
        Запускает смену IP в пуле потоков.
        
        Отправляет сигнал NEWNYM в Tor и обновляет отображаемый IP.
        """
        self.executor.submit(self._change_ip_async)
    
    def _change_ip_async(self) -> None:
        """
        Асинхронная смена IP (выполняется в пуле потоков).
        """
        if not self.ip_checker:
            logger.warning("IP checker не инициализирован")
            return
            
        try:
            with Controller.from_port(port=config.CONTROL_PORT) as c:
                c.authenticate(password=config.CONTROL_PASSWORD)
                c.signal(Signal.NEWNYM)
            new_ip = self.ip_checker.get_ip()
            Clock.schedule_once(lambda dt: setattr(self.ip_label, 'text', f"Текущий IP: {new_ip}"), 0)
        except Exception as e:
            logger.error(f"Ошибка смены IP: {e}")
            Clock.schedule_once(lambda dt: setattr(self.ip_label, 'text', "Ошибка смены IP"), 0)
    
    def start_rotator_thread(self) -> None:
        """
        Запускает фоновый поток автоматической ротации IP.
        
        Использует threading.Event для эффективного ожидания вместо polling.
        """
        def rotator() -> None:
            last_change = time.time()
            while not self.stop_event.is_set():
                if self.process_manager and self.process_manager.state.enabled:
                    elapsed = time.time() - last_change
                    if elapsed >= self.process_manager.state.interval_seconds:
                        self.change_ip()
                        last_change = time.time()
                        wait_time = self.process_manager.state.interval_seconds
                    else:
                        wait_time = self.process_manager.state.interval_seconds - elapsed
                    
                    # Ждем с возможностью прерывания
                    self.rotation_event.wait(timeout=wait_time)
                    self.rotation_event.clear()
                else:
                    # Если ротация выключена, ждем 1 секунду
                    self.stop_event.wait(timeout=1)
        
        threading.Thread(target=rotator, daemon=True, name="rotator-main").start()
    
    def cleanup(self) -> None:
        """
        Корректное завершение всех ресурсов.
        
        Вызывается при закрытии приложения или получении сигнала завершения.
        """
        logger.info("Завершение приложения...")
        
        # Останавливаем поток ротации
        if hasattr(self, 'stop_event'):
            self.stop_event.set()
        if hasattr(self, 'rotation_event'):
            self.rotation_event.set()
        
        # Завершаем пул потоков
        if hasattr(self, 'executor'):
            try:
                self.executor.shutdown(wait=True, cancel_futures=True)
            except Exception as e:
                logger.error(f"Ошибка завершения executor: {e}")
        
        # Останавливаем процессы
        if hasattr(self, 'process_manager'):
            self.process_manager.stop_tor()
            self.process_manager.stop_clash()
        
        logger.info("Приложение закрыто")
    
    def on_stop(self) -> None:
        """
        Вызывается при закрытии приложения.
        
        Делегирует завершение методу cleanup().
        """
        self.cleanup()
    
    def show_setup_wizard(self, force: bool = False) -> None:
        """
        Показывает мастер первоначальной настройки.
        
        Args:
            force: Если True, показывает без подтверждения (для первого запуска)
        """
        # Если конфиг уже есть и не force - показываем подтверждение
        if config.is_configured() and not force:
            self._show_reconfigure_confirmation()
            return
        
        def on_setup_complete():
            logger.info("Настройка завершена, перезагрузка конфигурации...")
            
            # Останавливаем старые процессы если были запущены
            if self.process_manager:
                self.process_manager.stop_tor()
                self.process_manager.stop_clash()
            
            # Перезагружаем конфигурацию
            import importlib
            importlib.reload(config)
            
            # Инициализируем менеджеры с новой конфигурацией
            self._init_managers()
            
            # Запускаем процессы с новыми настройками
            if self.process_manager:
                self.process_manager.start_tor()
                self.process_manager.start_clash()
                Clock.schedule_once(lambda dt: self.change_ip(), 2)
        
        setup_dialog = SetupDialog(on_complete_callback=on_setup_complete)
        setup_dialog.show()
    
    def _backup_configs(self) -> None:
        """Создаёт бэкап текущих конфигов."""
        import shutil
        from datetime import datetime
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_files = ['.env', 'torrc', 'global.txt']
        
        for filename in backup_files:
            filepath = Path(filename)
            if filepath.exists():
                backup_path = filepath.with_suffix(f'.backup_{timestamp}')
                shutil.copy2(filepath, backup_path)
                logger.info(f"Создан бэкап: {backup_path}")
    
    def _show_reconfigure_confirmation(self) -> None:
        """Показывает диалог подтверждения перенастройки."""
        from kivymd.uix.dialog import MDDialog
        from kivymd.uix.button import MDFlatButton, MDRaisedButton
        
        def on_confirm(*args):
            confirm_dialog.dismiss()
            # Создаём бэкап перед перенастройкой
            self._backup_configs()
            self.show_setup_wizard(force=True)
        
        confirm_dialog = MDDialog(
            title="Перенастройка",
            text="Это создаст новые конфигурационные файлы и пароль.\n\n"
                 "Текущие настройки будут сохранены в бэкап.\n\n"
                 "Продолжить?",
            buttons=[
                MDFlatButton(
                    text="ОТМЕНА",
                    on_release=lambda x: confirm_dialog.dismiss()
                ),
                MDRaisedButton(
                    text="ПЕРЕНАСТРОИТЬ",
                    on_release=on_confirm
                ),
            ],
        )
        confirm_dialog.open()

if __name__ == '__main__':
    RotatorApp().run()
