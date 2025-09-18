"""
DynaMat Platform - Ontology Loader
Handles TTL file loading and graph management
Extracted from manager.py for better separation of concerns
"""

import logging
from pathlib import Path
from typing import List

from rdflib import Graph

logger = logging.getLogger(__name__)


class OntologyLoader:
    """
    Handles loading and managing TTL files into RDF graphs.
    
    Responsibilities:
    - Load TTL files from directory structure
    - Handle file dependencies and load order
    - Provide graph reloading capabilities
    - Manage graph state
    """
    
    def __init__(self, ontology_dir: Path):
        """
        Initialize the ontology loader.
        
        Args:
            ontology_dir: Path to directory containing TTL files
        """
        self.ontology_dir = ontology_dir
        self.graph = Graph()
        self._files_loaded = 0
        
        logger.info(f"Ontology loader initialized with directory: {ontology_dir}")
    
    def load_ontology_files(self) -> Graph:
        """
        Load all TTL files from the ontology directory structure.
        
        Returns:
            The loaded RDF graph
            
        Raises:
            FileNotFoundError: If ontology directory doesn't exist
            ValueError: If no TTL files are found
        """
        if not self.ontology_dir.exists():
            raise FileNotFoundError(f"Ontology directory not found: {self.ontology_dir}")
        
        # Load files in specific order for dependencies
        load_order = [
            "core/DynaMat_core.ttl",
            "class_properties/*.ttl",
            "shapes/*.ttl",
            "class_individuals/*.ttl"
        ]
        
        self._files_loaded = 0
        
        for pattern in load_order:
            if "*" in pattern:
                # Handle wildcards
                base_path = self.ontology_dir / pattern.replace("*.ttl", "")
                if base_path.exists():
                    for ttl_file in sorted(base_path.glob("*.ttl")):
                        self._load_ttl_file(ttl_file)
                        self._files_loaded += 1
            else:
                # Handle specific files
                ttl_file = self.ontology_dir / pattern
                if ttl_file.exists():
                    self._load_ttl_file(ttl_file)
                    self._files_loaded += 1
        
        if self._files_loaded == 0:
            raise ValueError("No TTL files found in ontology directory")
        
        logger.info(f"Loaded {self._files_loaded} TTL files successfully")
        return self.graph
    
    def _load_ttl_file(self, file_path: Path):
        """
        Load a single TTL file into the graph.
        
        Args:
            file_path: Path to the TTL file
            
        Raises:
            Exception: If file cannot be parsed
        """
        try:
            self.graph.parse(file_path, format="turtle")
            logger.debug(f"Loaded TTL file: {file_path}")
        except Exception as e:
            logger.error(f"Failed to load {file_path}: {e}")
            raise
    
    def reload_ontology(self) -> Graph:
        """
        Reload the entire ontology from files.
        
        Clears the current graph and reloads all files.
        
        Returns:
            The reloaded RDF graph
        """
        logger.info("Reloading ontology files...")
        self.graph = Graph()
        return self.load_ontology_files()
    
    def get_graph(self) -> Graph:
        """Get the current RDF graph."""
        return self.graph
    
    def get_files_loaded_count(self) -> int:
        """Get the number of files successfully loaded."""
        return self._files_loaded
    
    def is_loaded(self) -> bool:
        """Check if any files have been loaded."""
        return self._files_loaded > 0