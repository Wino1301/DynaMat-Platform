"""
DynaMat Platform - GUI Core Module
Core components for form creation and data handling
"""

from .widget_factory import WidgetFactory
from .form_manager import FormManager
from .data_handler import FormDataHandler

__all__ = [
    'WidgetFactory',
    'FormManager', 
    'FormDataHandler'
]