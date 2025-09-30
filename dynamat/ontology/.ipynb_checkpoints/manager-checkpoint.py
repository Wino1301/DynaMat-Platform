"""
DynaMat Platform - Ontology Manager
Clean, focused manager for ontology operations
"""

import logging
from pathlib import Path
from typing import Dict, List, Optional, Any
from enum import Enum

# Import specialized components
from .core.ontology_loader import OntologyLoader
from .core.namespace_manager import NamespaceManager
from .query.sparql_executor import SPARQLExecutor
from .query.domain_queries import DomainQueries
from .cache.metadata_cache import MetadataCache
from .schema.gui_schema_builder import GUISchemaBuilder, ClassMetadata
from .qudt.qudt_manager import QUDTManager

from ..config import config

logger = logging.getLogger(__name__)


class QueryMode(Enum):
    """Query execution modes for different use cases"""
    EXPLORATION = "exploration"
    GUI_BUILDING = "gui_building" 
    DATA_RETRIEVAL = "data_retrieval"


class OntologyManager:
    """
    Central manager for ontology operations.
    
    Coordinates specialized components to provide a clean interface
    for GUI form building and data queries.
    """
    
    def __init__(self, ontology_dir: Optional[Path] = None):
        """
        Initialize the ontology manager.
        
        Args:
            ontology_dir: Path to ontology TTL files directory
        """
        # Determine ontology directory
        if ontology_dir is None:
            # Instead of using config.PROJECT_ROOT, use a relative path
            current_file = Path(__file__).parent
            ontology_dir = current_file  # This should be dynamat/ontology/
        
        self.ontology_dir = Path(ontology_dir)
        
        self.ontology_dir = Path(ontology_dir)
        
        # Initialize components
        self.loader = OntologyLoader(self.ontology_dir)
        self.namespace_manager = NamespaceManager()
        self.cache = MetadataCache()
        self.qudt_manager = QUDTManager()
        
        # Load ontology and setup components
        self._initialize()
        
        logger.info(f"Ontology manager initialized with {self.loader.get_files_loaded_count()} TTL files")
    
    def _initialize(self):
        """Load ontology and initialize all components."""
        # Load ontology files
        graph = self.loader.load_ontology_files()
        
        # Setup namespaces
        self.namespace_manager = NamespaceManager(graph)
        self.namespace_manager.setup_graph_namespaces(graph)
        
        # Initialize query and schema components
        self.sparql_executor = SPARQLExecutor(graph, self.namespace_manager)
        self.domain_queries = DomainQueries(self.sparql_executor, self.namespace_manager)
        self.gui_schema_builder = GUISchemaBuilder(
                                                    self.sparql_executor, 
                                                    self.namespace_manager, 
                                                    self.cache,
                                                    self.qudt_manager  
                                                )
                                                
        # Load QUDT data after initialization
        logger.info("Loading QUDT units data...")
        self.qudt_manager.load()
        logger.info("QUDT units loaded successfully")
    
    # ============================================================================
    # PRIMARY INTERFACE - Used by form_builder.py
    # ============================================================================
    
    def get_class_metadata_for_form(self, class_uri: str) -> ClassMetadata:
        """
        Get comprehensive class metadata for form building.
        
        This is the main method called by form_builder.py.
        """
        return self.gui_schema_builder.get_class_metadata_for_form(class_uri)
    
    # ============================================================================
    # NAMESPACE ACCESS - Used by form_builder.py and other components
    # ============================================================================
    
    @property
    def DYN(self):
        """Get the DynaMat namespace."""
        return self.namespace_manager.DYN
    
    @property
    def QUDT(self):
        """Get the QUDT namespace."""
        return self.namespace_manager.QUDT
    
    @property
    def UNIT(self):
        """Get the UNIT namespace."""
        return self.namespace_manager.UNIT
    
    @property
    def QKDV(self):
        """Get the quantity kind namespace."""
        return self.namespace_manager.QKDV
    
    @property
    def namespaces(self):
        """Get all namespaces dictionary."""
        return self.namespace_manager.get_all_namespaces()
    
    # ============================================================================
    # COMPONENT ACCESS
    # ============================================================================
    
    @property
    def graph(self):
        """Get the RDF graph."""
        return self.loader.get_graph()
    
    @property
    def classes_cache(self):
        """Get the classes cache - used by form_builder.py for cache clearing."""
        return self.cache.classes_cache
    
    @property
    def properties_cache(self):
        """Get the properties cache."""  
        return self.cache.properties_cache
    
    # ============================================================================
    # QUERY METHODS - Consolidated common operations
    # ============================================================================
    
    def get_all_classes(self) -> List[str]:
        """Get all classes defined in the ontology."""
        return self.domain_queries.get_all_classes()
    
    def get_available_materials(self) -> List[Dict[str, Any]]:
        """Get all available materials with basic properties."""
        return self.domain_queries.get_available_materials()
    
    def find_specimens(self, **criteria) -> List[Dict[str, Any]]:
        """Find specimens based on criteria."""
        return self.domain_queries.find_specimens(**criteria)
    
    def find_tests(self, **criteria) -> List[Dict[str, Any]]:
        """Find tests based on criteria."""
        return self.domain_queries.find_tests(**criteria)
    
    # ============================================================================
    # UTILITY METHODS
    # ============================================================================
    
    def reload_ontology(self):
        """Reload the entire ontology from files."""
        logger.info("Reloading ontology...")
        
        # Clear all caches
        self.cache.clear_all_caches()
        self.sparql_executor.clear_cache()
        
        # Reload ontology
        self._initialize()
        
        logger.info("Ontology reloaded successfully")
    
    def clear_caches(self):
        """Clear all caches."""
        self.cache.clear_all_caches()
        self.sparql_executor.clear_cache()
        logger.info("All caches cleared")
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get manager statistics."""
        cache_stats = self.cache.get_cache_stats()
        query_stats = self.sparql_executor.get_cache_stats()
        
        return {
            'files_loaded': self.loader.get_files_loaded_count(),
            'total_triples': self.sparql_executor.count_triples(),
            'classes_cached': cache_stats.classes_cached,
            'properties_cached': cache_stats.properties_cached,
            'cache_hit_ratio': self.cache.get_cache_hit_ratio(),
            'query_cache_size': query_stats.get('cached_queries', 0)
        }
    
    # ============================================================================
    # COMPONENT FACTORY METHODS
    # ============================================================================
    
    def create_temp_handler(self):
        """Create a TempInstanceHandler with proper dependencies."""
        from .temp_handler import TempInstanceHandler
        return TempInstanceHandler(self.sparql_executor, self.namespace_manager)
    
    def create_template_manager(self, template_dir=None):
        """Create a TemplateManager with proper dependencies."""
        from .template_manager import TemplateManager
        return TemplateManager(self.namespace_manager, template_dir)
    
    def create_validator(self, shapes_dir=None):
        """Create a SHACLValidator with proper dependencies."""
        from .validator import SHACLValidator
        return SHACLValidator(self.namespace_manager, self.sparql_executor, shapes_dir)
    
    def create_query_builder(self):
        """Create a DynaMatQueryBuilder with proper dependencies."""
        from .query_builder import DynaMatQueryBuilder
        return DynaMatQueryBuilder(self.sparql_executor, self.namespace_manager)