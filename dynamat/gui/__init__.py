"""
DynaMat Platform GUI Package

File location: dynamat/gui/__init__.py

This file makes the gui directory a proper Python package and provides
convenient imports for the main GUI components.
"""

# Version information
__version__ = "1.0.0"

# Main application class
try:
    from .app import DynaMatApp
except ImportError:
    DynaMatApp = None

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

# Convenience function to check if GUI is available
def is_gui_available():
    """Check if all GUI components are available"""
    return all([
        DynaMatApp is not None,
        OntologyForm is not None,
        OntologyFormGenerator is not None,
        OntologyWidget is not None
    ])

# List of available components
__all__ = [
    'DynaMatApp',
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
    'is_gui_available'
]