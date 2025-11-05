"""
DynaMat Platform - GUI Module (Refactored)
Desktop application for dynamic materials testing data management

New Architecture:
- Core: Widget creation, form management, and data handling
- Builders: Form building orchestration and layout management  
- Dependencies: Dependency management and calculation engine
- Widgets: Organized base widgets and specialized forms
"""

# Main application components
from .app import DynaMatApp
from .main_window import MainWindow

# New builders architecture
from .builders.ontology_form_builder import OntologyFormBuilder
from .builders.layout_manager import LayoutManager, LayoutStyle

# Core components
from .core.widget_factory import WidgetFactory
from .core.form_manager import FormManager, FormField
from .core.data_handler import FormDataHandler

# Dependencies
from .dependencies.dependency_manager import DependencyManager
from .dependencies.calculation_engine import CalculationEngine, CalculationType

# Widgets (maintaining compatibility)
from .widgets.forms.specimen_form import SpecimenFormWidget
from .widgets.base.unit_value_widget import UnitValueWidget
from .widgets.terminal_widget import TerminalWidget
from .widgets.action_panel import ActionPanelWidget

# Import submodules for organized access
from . import core
from . import builders
from . import dependencies
from . import widgets


__all__ = [
    # Main application
    'DynaMatApp',
    'MainWindow',
    
    # New builders architecture
    'OntologyFormBuilder',
    'LayoutManager',
    'LayoutStyle',
    
    # Core components
    'WidgetFactory',
    'FormManager',
    'FormField',
    'FormDataHandler',
    
    # Dependencies
    'DependencyManager',
    'CalculationEngine',
    'CalculationType',
    
    # Widgets
    'SpecimenFormWidget',
    'UnitValueWidget',
    'TerminalWidget',
    'ActionPanelWidget',
    
    # Submodules
    'core',
    'builders', 
    'dependencies',
    'widgets',   
]

# Version information
__version__ = "2.0.0"
__architecture__ = "refactored"

def get_gui_info():
    """Get information about the GUI module architecture."""
    return {
        'version': __version__,
        'architecture': __architecture__,
        'components': {
            'core': 'Widget creation, form management, data handling',
            'builders': 'Form building orchestration and layout management',
            'dependencies': 'Dependency management and calculation engine',
            'widgets': 'Base widgets and specialized forms'
        },
        'backward_compatibility': True,
        'new_features': [
            'Separation of concerns',
            'Plugin-based widget creation',
            'Multiple layout strategies',
            'Centralized calculation engine',
            'Better error handling',
            'Improved testability'
        ]
    }