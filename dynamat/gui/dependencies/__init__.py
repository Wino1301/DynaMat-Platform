"""
DynaMat Platform - GUI Dependencies Module
Dependency management and calculation engine
"""

from .dependency_manager import DependencyManager
from .calculation_engine import CalculationEngine, CalculationType

__all__ = [
    'DependencyManager',
    'CalculationEngine', 
    'CalculationType'
]