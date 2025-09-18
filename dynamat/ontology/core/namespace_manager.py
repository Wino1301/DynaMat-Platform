"""
DynaMat Platform - Namespace Manager
Handles all namespace setup and binding for RDF graphs
Extracted from manager.py for better separation of concerns
"""

import logging
from typing import Dict

from rdflib import Graph, Namespace
from rdflib.namespace import RDF, RDFS, OWL, XSD

logger = logging.getLogger(__name__)


class NamespaceManager:
    """
    Manages all RDF namespaces and their bindings.
    
    Responsibilities:
    - Setup and bind all required namespaces
    - Provide easy access to namespace objects
    - Maintain namespace registry
    """
    
    def __init__(self):
        """Initialize the namespace manager."""
        self.namespaces = {}
        self.DYN = None
        self.QUDT = None
        self.UNIT = None
        self.QKDV = None
        self.SH = None
        self.DC = None
        
        self._setup_namespace_uris()
        logger.info("Namespace manager initialized")
    
    def _setup_namespace_uris(self):
        """Setup all namespace URIs."""
        # Core DynaMat namespace
        self.DYN = Namespace("https://dynamat.utep.edu/ontology#")
        
        # External vocabularies
        self.QUDT = Namespace("http://qudt.org/schema/qudt/")
        self.UNIT = Namespace("http://qudt.org/vocab/unit/")
        self.QKDV = Namespace("http://qudt.org/vocab/quantitykind/")
        self.SH = Namespace("http://www.w3.org/ns/shacl#")
        self.DC = Namespace("http://purl.org/dc/terms/")
        
        # Store all namespaces
        self.namespaces = {
            'dyn': self.DYN,
            'qudt': self.QUDT,
            'unit': self.UNIT,
            'qkdv': self.QKDV,
            'sh': self.SH,
            'dc': self.DC,
            'rdf': RDF,
            'rdfs': RDFS,
            'owl': OWL,
            'xsd': XSD
        }
    
    def setup_graph_namespaces(self, graph: Graph):
        """
        Bind all namespaces to the given graph.
        
        Args:
            graph: RDF graph to bind namespaces to
        """
        # Bind custom namespaces
        graph.bind("dyn", self.DYN)
        graph.bind("qudt", self.QUDT)
        graph.bind("unit", self.UNIT)
        graph.bind("qkdv", self.QKDV)
        graph.bind("sh", self.SH)
        graph.bind("dc", self.DC)
        
        # Bind standard namespaces
        graph.bind("rdf", RDF)
        graph.bind("rdfs", RDFS)
        graph.bind("owl", OWL)
        graph.bind("xsd", XSD)
        
        logger.debug("All namespaces bound to graph")
    
    def get_namespace(self, prefix: str) -> Namespace:
        """
        Get namespace by prefix.
        
        Args:
            prefix: Namespace prefix (e.g., 'dyn', 'qudt')
            
        Returns:
            Namespace object
            
        Raises:
            KeyError: If prefix not found
        """
        if prefix not in self.namespaces:
            raise KeyError(f"Namespace prefix '{prefix}' not found")
        return self.namespaces[prefix]
    
    def get_all_namespaces(self) -> Dict[str, Namespace]:
        """Get all registered namespaces."""
        return self.namespaces.copy()
    
    def get_dyn_namespace(self) -> Namespace:
        """Get the main DynaMat namespace."""
        return self.DYN
    
    def get_qudt_namespace(self) -> Namespace:
        """Get the QUDT namespace."""
        return self.QUDT
    
    def get_unit_namespace(self) -> Namespace:
        """Get the UNIT namespace."""
        return self.UNIT
    
    def get_quantity_kind_namespace(self) -> Namespace:
        """Get the quantity kind namespace."""
        return self.QKDV
    
    def get_shapes_namespace(self) -> Namespace:
        """Get the SHACL shapes namespace."""
        return self.SH