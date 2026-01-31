"""
DynaMat Platform - GUI Widgets Module
Custom widgets for the DynaMat application
"""

# Import from forms
from .forms.specimen_form import SpecimenFormWidget

# Import from base
from .base.unit_value_widget import UnitValueWidget
from .base.entity_selector import (
    EntitySelectorConfig,
    EntitySelectorWidget,
    EntitySelectorDialog,
)

# Import from root widgets (maintaining compatibility)
from .terminal_widget import TerminalWidget
from .action_panel import ActionPanelWidget
from .validation_results_dialog import ValidationResultsDialog

# Import SHPB wizard
from .shpb import SHPBAnalysisWizard

# Import submodules for organized access
from . import base
from . import forms
from . import shpb

__all__ = [
    # Form widgets
    'SpecimenFormWidget',

    # Base widgets
    'UnitValueWidget',

    # Entity selector
    'EntitySelectorConfig',
    'EntitySelectorWidget',
    'EntitySelectorDialog',

    # Dialogs
    'ValidationResultsDialog',

    # Other widgets
    'TerminalWidget',
    'ActionPanelWidget',

    # SHPB
    'SHPBAnalysisWizard',

    # Submodules
    'base',
    'forms',
    'shpb',
]