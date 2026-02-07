"""GUI Core module for ontology-driven form generation.

This module provides the core components for creating dynamic forms from
ontology metadata. It implements the ontology-first design philosophy where
the GUI reads RDF ontology definitions and automatically generates appropriate
form interfaces.

Architecture Overview
---------------------
::

    Ontology Metadata
           |
           v
    +-------------------+     +-------------------+
    |   WidgetFactory   | --> |   FormManager     |
    |  (Widget Creation)|     |  (Orchestration)  |
    +-------------------+     +-------------------+
                                      |
                                      v
                              +-------------------+
                              |  FormDataHandler  |
                              |  (Data I/O)       |
                              +-------------------+

Components
----------
WidgetFactory
    Creates appropriate widgets from property metadata. Maps ontology data types
    and annotations to PyQt6 widgets (line edits, spinboxes, combo boxes, etc.).

FormManager
    Coordinates form creation by combining widget factory, layout manager,
    and data handler. Main entry point for creating complete forms.

FormDataHandler
    Handles extracting and populating data from/to form widgets. Provides
    type-safe value operations across all supported widget types.

SHACLValidator
    Validates RDF instance data against SHACL shapes. Categorizes validation
    results by severity (Violation, Warning, Info).

Form Generation Flow
--------------------
1. User requests form for a class URI (e.g., ``dyn:Specimen``)
2. OntologyManager retrieves class metadata with properties
3. WidgetFactory creates widgets based on property data types and annotations
4. LayoutManager arranges widgets into grouped sections
5. FormDataHandler manages data extraction and population

Example
-------
::

    from dynamat.ontology import OntologyManager
    from dynamat.gui.core import FormManager, FormStyle

    # Initialize
    ontology = OntologyManager()
    form_manager = FormManager(ontology)

    # Create form
    form = form_manager.create_form("dyn:Specimen", style=FormStyle.GROUPED)

    # Get/Set data
    data = form_manager.get_form_data(form)
    form_manager.set_form_data(form, existing_data)

References
----------
PyQt6 Widgets: https://doc.qt.io/qtforpython-6/
RDFLib: https://rdflib.readthedocs.io/
SHACL Spec: https://www.w3.org/TR/shacl/
"""

from .widget_factory import WidgetFactory
from .form_manager import FormManager, FormStyle, FormField
from .data_handler import FormDataHandler
from .form_validator import SHACLValidator, ValidationResult, ValidationIssue

__all__ = [
    'WidgetFactory',
    'FormManager',
    'FormStyle',
    'FormField',
    'FormDataHandler',
    'SHACLValidator',
    'ValidationResult',
    'ValidationIssue',
]