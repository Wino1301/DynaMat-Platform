"""GUI Builders module for form building orchestration.

This module provides high-level form building orchestration components that
coordinate widget creation, layout management, and dependency handling to
create complete ontology-driven forms.

Architecture Overview
---------------------
::

    OntologyFormBuilder (Facade)
           |
           +---> FormManager (widget creation)
           |
           +---> LayoutManager (layout organization)
           |
           +---> DependencyManager (field dependencies)

Components
----------
OntologyFormBuilder
    High-level facade that coordinates all form building components.
    Main entry point for creating ontology-based forms with a simple API.

LayoutManager
    Handles form layout creation and widget grouping. Supports multiple
    layout styles: grouped, tabbed, two-column, and simple.

LayoutStyle
    Enumeration of available layout styles for forms.

Form Building Flow
------------------
1. User calls ``build_form(class_uri)`` on OntologyFormBuilder
2. OntologyFormBuilder delegates to FormManager for widget creation
3. LayoutManager organizes widgets into groups and layouts
4. DependencyManager (if enabled) sets up field dependencies
5. Complete form widget is returned with all metadata attached

Example
-------
::

    from dynamat.ontology import OntologyManager
    from dynamat.gui.builders import OntologyFormBuilder, LayoutStyle

    # Initialize
    ontology = OntologyManager()
    builder = OntologyFormBuilder(ontology)

    # Build form with default layout
    form = builder.build_form("dyn:Specimen")

    # Build form with specific layout
    form = builder.build_form_with_layout(
        "dyn:Specimen",
        LayoutStyle.TABBED_FORM
    )

    # Get/Set data
    data = builder.get_form_data(form)
    builder.set_form_data(form, existing_data)

References
----------
PyQt6 Layouts: https://doc.qt.io/qtforpython-6/
"""

from .ontology_form_builder import OntologyFormBuilder
from .layout_manager import LayoutManager, LayoutStyle
from .group_builder import GroupBuilder
from .default_group_builder import DefaultGroupBuilder
from .customizable_form_builder import CustomizableFormBuilder

__all__ = [
    'OntologyFormBuilder',
    'LayoutManager',
    'LayoutStyle',
    'GroupBuilder',
    'DefaultGroupBuilder',
    'CustomizableFormBuilder',
]