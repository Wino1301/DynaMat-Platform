"""
DynaMat Platform - Ontology Module
Provides ontology management and querying capabilities for the DynaMat platform.
"""

# Main manager class
from .manager import OntologyManager, QueryMode

# Data classes used by GUI components  
from .schema.gui_schema_builder import (
    PropertyMetadata, 
    ClassMetadata,
    UnitInfo,          
    CacheStatus        
)

# Specialized components for advanced users
from .core.ontology_loader import OntologyLoader
from .core.namespace_manager import NamespaceManager
from .query.sparql_executor import SPARQLExecutor
from .query.domain_queries import DomainQueries
from .cache.metadata_cache import MetadataCache
from .schema.gui_schema_builder import GUISchemaBuilder

# Additional components (refactored)
from .query_builder import (
    DynaMatQueryBuilder,
    TestSearchCriteria,
    SpecimenSearchCriteria
)

from .template_manager import TemplateManager, TemplateMetadata
from .validator import SHACLValidator, ValidationReport, ValidationResult, ValidationSeverity

# Factory functions for refactored components
def create_template_manager(ontology_manager: 'OntologyManager', template_dir=None) -> TemplateManager:
    """Create a TemplateManager with proper dependencies."""
    return TemplateManager(
        ontology_manager.namespace_manager,
        template_dir
    )

def create_validator(ontology_manager: 'OntologyManager', shapes_dir=None) -> SHACLValidator:
    """Create a SHACLValidator with proper dependencies."""
    return SHACLValidator(
        ontology_manager.namespace_manager,
        ontology_manager.sparql_executor,
        shapes_dir
    )

def create_query_builder(ontology_manager: 'OntologyManager') -> DynaMatQueryBuilder:
    """Create a DynaMatQueryBuilder with proper dependencies."""
    return DynaMatQueryBuilder(
        ontology_manager.sparql_executor,
        ontology_manager.namespace_manager
    )

__all__ = [
    # Main interface
    'OntologyManager',
    'QueryMode',
    
    # Data classes
    'PropertyMetadata', 
    'ClassMetadata',
    'UnitInfo',         
    'CacheStatus',
    
    # Specialized components
    'OntologyLoader',
    'NamespaceManager', 
    'SPARQLExecutor',
    'DomainQueries',
    'MetadataCache',
    'GUISchemaBuilder',
    
    # Additional components
    'DynaMatQueryBuilder',
    'TestSearchCriteria',
    'SpecimenSearchCriteria',
    'TemplateManager',
    'TemplateMetadata',
    'SHACLValidator',
    'ValidationReport',
    'ValidationResult',
    'ValidationSeverity',
    
    # Factory functions
    'create_template_manager',
    'create_validator',
    'create_query_builder'
]