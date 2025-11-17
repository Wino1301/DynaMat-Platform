"""
DynaMat Platform - GUI Dependencies Module
Dependency management, calculation, and generation engines
"""

from .dependency_manager import DependencyManager
from .calculation_engine import CalculationEngine, CalculationType
from .generation_engine import GenerationEngine
from .constraint_manager import (
    ConstraintManager,
    Constraint,
    TriggerLogic
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
    'TriggerLogic'
]