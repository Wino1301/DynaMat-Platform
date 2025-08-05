"""
DynaMat Platform - GUI Module
Desktop application for dynamic materials testing data management
"""

from .app import DynaMatApp
from .main_window import MainWindow
from .form_builder import OntologyFormBuilder
from .widgets.specimen_form import SpecimenFormWidget

__all__ = ['DynaMatApp', 'MainWindow', 'OntologyFormBuilder', 'SpecimenFormWidget']