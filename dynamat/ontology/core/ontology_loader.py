"""
DynaMat Platform - Ontology Loader
Handles TTL file loading and graph management
Extracted from manager.py for better separation of concerns
"""

import logging
from pathlib import Path
from typing import List, Dict, Any

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

        # Statistics tracking (always-on)
        self._loaded_files = []  # List of (filename, triples_added, load_time_seconds)
        self._failed_files = []  # List of (filename, error_message)
        self._total_load_time = 0.0

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
        import time

        try:
            # Track graph size before loading
            triples_before = len(self.graph)
            start_time = time.time()

            # Load the file
            self.graph.parse(file_path, format="turtle")

            # Calculate metrics
            load_time = time.time() - start_time
            triples_added = len(self.graph) - triples_before

            # Track statistics
            self._loaded_files.append((str(file_path), triples_added, load_time))
            self._total_load_time += load_time

            logger.debug(f"Loaded TTL file: {file_path} (+{triples_added} triples in {load_time:.3f}s)")

        except Exception as e:
            logger.error(f"Failed to load {file_path}: {e}")
            # Track failed file
            self._failed_files.append((str(file_path), str(e)))
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

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get comprehensive loader statistics for testing and debugging.

        Returns:
            Dictionary with statistics categories:
            - configuration: Directory and basic info
            - execution: Load statistics
            - health: Success/failure metrics
            - performance: Timing information
        """
        from typing import Dict, Any

        return {
            'configuration': {
                'ontology_directory': str(self.ontology_dir),
                'directory_exists': self.ontology_dir.exists()
            },
            'execution': {
                'files_loaded': self._files_loaded,
                'is_loaded': self.is_loaded(),
                'graph_size': len(self.graph) if self.graph else 0,
                'loaded_files': [
                    {
                        'filename': filename,
                        'triples_added': triples,
                        'load_time_ms': load_time * 1000
                    }
                    for filename, triples, load_time in self._loaded_files
                ],
                'failed_files': [
                    {
                        'filename': filename,
                        'error': error
                    }
                    for filename, error in self._failed_files
                ]
            },
            'health': {
                'total_failures': len(self._failed_files),
                'success_rate': (
                    self._files_loaded / (self._files_loaded + len(self._failed_files))
                    if (self._files_loaded + len(self._failed_files)) > 0
                    else 0.0
                )
            },
            'performance': {
                'total_load_time_ms': self._total_load_time * 1000,
                'average_load_time_ms': (
                    (self._total_load_time / self._files_loaded * 1000)
                    if self._files_loaded > 0
                    else 0
                )
            }
        }

    def get_load_order(self) -> List[str]:
        """
        Get the order files were loaded.

        Returns:
            List of filenames in load order
        """
        return [filename for filename, _, _ in self._loaded_files]