"""
DynaMat Platform - Ontology Module
Provides ontology management and querying capabilities for the DynaMat platform.
"""

from .manager import (
    OntologyManager, 
    PropertyMetadata, 
    ClassMetadata, 
    QueryMode
)

from .query_builder import (
    DynaMatQueryBuilder,
    TestSearchCriteria,
    SpecimenSearchCriteria
)

from .temp_handler import (
    TempInstanceHandler
)

from .template_manager import (
    TemplateManager,
    TemplateMetadata
)

from .validator import (
    SHACLValidator,
    ValidationReport,
    ValidationResult,
    ValidationSeverity
)

__all__ = [
    # Core ontology management
    'OntologyManager',
    'PropertyMetadata', 
    'ClassMetadata',
    'QueryMode',
    
    # Query building
    'DynaMatQueryBuilder',
    'TestSearchCriteria',
    'SpecimenSearchCriteria',
    
    # Temporary file handling
    'TempInstanceHandler',
    
    # Template management
    'TemplateManager',
    'TemplateMetadata',
    
    # Validation
    'SHACLValidator',
    'ValidationReport',
    'ValidationResult',
    'ValidationSeverity'
]