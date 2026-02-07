"""GUI Dependencies module for form field dependencies and calculations.

This module provides a constraint-based dependency system for ontology-driven
forms. It manages field visibility, calculations, value generation, and
population based on TTL-defined constraints.

Architecture Overview
---------------------
::

    TTL Constraint Files
           |
           v
    +-------------------+
    | ConstraintManager |  (loads & parses TTL constraints)
    +-------------------+
           |
           v
    +-------------------+     +-------------------+     +-------------------+
    | DependencyManager | --> | CalculationEngine | --> | GenerationEngine  |
    |  (orchestration)  |     |  (math functions) |     |  (ID generation)  |
    +-------------------+     +-------------------+     +-------------------+

Components
----------
DependencyManager
    Main orchestrator that connects form widgets to constraints.
    Handles signal connections, constraint evaluation, and operation execution.

ConstraintManager
    Loads and parses constraint definitions from TTL files.
    Provides structured access to constraint properties and operations.

CalculationEngine
    Performs mathematical calculations for derived field values.
    Supports area, volume, density, stress calculations and unit conversions.

GenerationEngine
    Generates formatted values from templates (specimen IDs, batch IDs, etc.).
    Supports sequence numbering and material code extraction.

Constraint Types
----------------
Visibility
    Show/hide fields based on trigger field values.

Calculation
    Compute derived values (e.g., area from diameter).

Generation
    Generate IDs and codes from templates and inputs.

Population
    Auto-populate fields from selected ontology individuals.

Filtering
    Filter dropdown choices based on class membership.

Example
-------
::

    from dynamat.gui.dependencies import DependencyManager

    # Initialize with ontology manager
    dep_manager = DependencyManager(ontology_manager, constraint_dir)

    # Set up dependencies for a form
    dep_manager.setup_dependencies(form_widget, "dyn:Specimen")

    # Connect to signals
    dep_manager.calculation_performed.connect(on_calculation)
    dep_manager.generation_performed.connect(on_generation)

References
----------
RDFLib Collections: https://rdflib.readthedocs.io/
PyQt6 Signals: https://doc.qt.io/qtforpython-6/
"""

from .dependency_manager import DependencyManager
from .calculation_engine import CalculationEngine, CalculationType
from .generation_engine import GenerationEngine
from .constraint_manager import (
    ConstraintManager,
    Constraint,
    TriggerLogic,
)

__all__ = [
    # Main dependency manager
    'DependencyManager',

    # Engines
    'CalculationEngine',
    'CalculationType',
    'GenerationEngine',

    # Constraint system
    'ConstraintManager',
    'Constraint',
    'TriggerLogic',
]