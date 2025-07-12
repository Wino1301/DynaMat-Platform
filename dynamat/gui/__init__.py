"""
DynaMat Platform GUI Package

Updated to include all new GUI modules and handle import errors gracefully.
"""

# Version information
__version__ = "1.0.0"

# Main application class
try:
    from .app import DynaMatApp
except ImportError:
    DynaMatApp = None

# Ribbon menu
try:
    from .ribbon import RibbonMenu, RibbonButton, RibbonTab
except ImportError:
    RibbonMenu = None
    RibbonButton = None
    RibbonTab = None

# Form classes
try:
    from .forms import OntologyForm, OntologyFormGenerator, FormData, FormTemplate
except ImportError:
    OntologyForm = None
    OntologyFormGenerator = None
    FormData = None
    FormTemplate = None

# Widget classes
try:
    from .widgets import (
        OntologyWidget, MeasurementWidget, OntologySelector,
        TextWidget, NumberWidget, DateWidget, BooleanWidget,
        WidgetData, WidgetState
    )
except ImportError:
    # Individual imports will be None if imports fail
    OntologyWidget = None
    MeasurementWidget = None
    OntologySelector = None
    TextWidget = None
    NumberWidget = None
    DateWidget = None
    BooleanWidget = None
    WidgetData = None
    WidgetState = None

# Mechanical testing components
try:
    from .mechanical.test_selector import TestTypeSelector
    from .mechanical.shpb_setup import SHPBConditionsForm
except ImportError:
    TestTypeSelector = None
    SHPBConditionsForm = None

# Convenience function to check if GUI is available
def is_gui_available():
    """Check if all GUI components are available"""
    return all([
        DynaMatApp is not None,
        RibbonMenu is not None,
        OntologyForm is not None,
        OntologyFormGenerator is not None,
        OntologyWidget is not None
    ])

# List of available components
__all__ = [
    'DynaMatApp',
    'RibbonMenu', 
    'RibbonButton', 
    'RibbonTab',
    'OntologyForm', 
    'OntologyFormGenerator', 
    'FormData', 
    'FormTemplate',
    'OntologyWidget', 
    'MeasurementWidget', 
    'OntologySelector',
    'TextWidget', 
    'NumberWidget', 
    'DateWidget', 
    'BooleanWidget',
    'WidgetData', 
    'WidgetState',
    'TestTypeSelector',
    'SHPBConditionsForm',
    'is_gui_available'
]