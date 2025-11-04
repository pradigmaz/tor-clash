"""Валидация входных данных."""
from dataclasses import dataclass
from typing import Literal, Tuple

TimeUnit = Literal["секунд", "минут", "часов"]


@dataclass
class IntervalValidator:
    """Валидатор интервалов ротации."""
    
    RANGES = {
        "секунд": (1, 86400),
        "минут": (0.01, 1440),
        "часов": (0.01, 24)
    }
    
    MULTIPLIERS = {
        "секунд": 1,
        "минут": 60,
        "часов": 3600
    }
    
    @classmethod
    def validate(cls, value: float, unit: TimeUnit) -> Tuple[bool, str]:
        """
        Валидирует интервал.
        
        Args:
            value: Значение интервала
            unit: Единица измерения
            
        Returns:
            (is_valid, error_message): Кортеж с результатом валидации
        """
        if unit not in cls.RANGES:
            return False, f"Неизвестная единица: {unit}"
        
        min_val, max_val = cls.RANGES[unit]
        if not (min_val <= value <= max_val):
            return False, f"Интервал должен быть от {min_val} до {max_val} {unit}"
        
        return True, ""
    
    @classmethod
    def to_seconds(cls, value: float, unit: TimeUnit) -> float:
        """
        Конвертирует интервал в секунды.
        
        Args:
            value: Значение интервала
            unit: Единица измерения
            
        Returns:
            Интервал в секундах
        """
        return value * cls.MULTIPLIERS[unit]
    
    @classmethod
    def get_range(cls, unit: TimeUnit) -> Tuple[float, float]:
        """
        Возвращает допустимый диапазон для единицы измерения.
        
        Args:
            unit: Единица измерения
            
        Returns:
            (min, max): Минимальное и максимальное значение
        """
        return cls.RANGES.get(unit, (0, 0))
