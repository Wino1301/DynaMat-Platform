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

from .template_manager import TemplateManager, TemplateMetadata
from .validator import SHACLValidator, ValidationReport, ValidationResult, ValidationSeverity
from .instance_query_builder import InstanceQueryBuilder

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

def create_query_builder(ontology_manager: 'OntologyManager') -> DomainQueries:
    """
    Create a query builder with proper dependencies.

    Returns DomainQueries for backward compatibility with code that used
    create_query_builder(). The DomainQueries class provides all domain
    query methods previously available in DynaMatQueryBuilder.

    For direct access, use ontology_manager.domain_queries instead.
    """
    return ontology_manager.domain_queries

def create_instance_query_builder(ontology_manager: 'OntologyManager') -> InstanceQueryBuilder:
    """Create an InstanceQueryBuilder with proper dependencies."""
    return InstanceQueryBuilder(ontology_manager)

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
    'TemplateManager',
    'TemplateMetadata',
    'SHACLValidator',
    'ValidationReport',
    'ValidationResult',
    'ValidationSeverity',
    'InstanceQueryBuilder',

    # Factory functions
    'create_template_manager',
    'create_validator',
    'create_query_builder',
    'create_instance_query_builder'
]