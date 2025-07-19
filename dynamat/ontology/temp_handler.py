"""
DynaMat Platform - Temporary File Handler
Manages temporary TTL files for GUI editing and form operations
"""

import logging
import tempfile
import uuid
from pathlib import Path
from typing import Dict, List, Optional, Any, Union, Tuple
from datetime import datetime

import rdflib
from rdflib import Graph, Namespace, URIRef, Literal, BNode
from rdflib.namespace import RDF, RDFS, OWL, XSD

from .manager import OntologyManager
from ..config import config


logger = logging.getLogger(__name__)


class TempInstanceHandler:
    """
    Handles temporary TTL files for GUI editing operations.
    
    Provides methods to create, modify, and save individual instances
    without affecting the main ontology until explicitly saved.
    """
    
    def __init__(self, ontology_manager: OntologyManager):
        """
        Initialize with an ontology manager.
        
        Args:
            ontology_manager: Main ontology manager instance
        """
        self.manager = ontology_manager
        self.temp_dir = Path(tempfile.gettempdir()) / "dynamat_temp"
        self.temp_dir.mkdir(exist_ok=True)
        
        # Track active temporary instances
        self.active_instances = {}  # instance_uri -> temp_file_path
        self.instance_graphs = {}   # instance_uri -> Graph
        self.change_log = {}        # instance_uri -> list of changes
        
        # Setup namespaces
        self.DYN = self.manager.DYN
        self.namespaces = self.manager.namespaces
        
        logger.info(f"Temporary file handler initialized, temp dir: {self.temp_dir}")
    
    def create_temp_instance(self, class_uri: str, instance_id: Optional[str] = None, 
                           base_data: Optional[Dict[str, Any]] = None) -> Tuple[str, str]:
        """
        Create a new temporary instance for editing.
        
        Args:
            class_uri: URI of the class to instantiate
            instance_id: Specific ID to use, generates UUID if None
            base_data: Initial property values
            
        Returns:
            Tuple of (instance_uri, temp_file_path)
        """
        # Generate instance URI
        if instance_id is None:
            instance_id = f"temp_{uuid.uuid4().hex[:8]}"
        
        instance_uri = str(self.DYN[instance_id])
        
        # Create new graph for this instance
        graph = Graph()
        
        # Bind namespaces
        for prefix, namespace in self.namespaces.items():
            graph.bind(prefix, namespace)
        
        # Add basic RDF type
        graph.add((URIRef(instance_uri), RDF.type, URIRef(class_uri)))
        graph.add((URIRef(instance_uri), RDF.type, OWL.NamedIndividual))
        
        # Add creation timestamp
        now = datetime.now().isoformat()
        graph.add((URIRef(instance_uri), self.DYN.hasCreationTimestamp, Literal(now, datatype=XSD.dateTime)))
        
        # Add base data if provided
        if base_data:
            for property_name, value in base_data.items():
                if property_name.startswith("http"):
                    property_uri = property_name
                else:
                    property_uri = str(self.DYN[property_name])
                
                self._add_property_value(graph, instance_uri, property_uri, value)
        
        # Create temporary file
        temp_file = self.temp_dir / f"{instance_id}.ttl"
        
        # Save to temporary file
        self._save_graph_to_file(graph, temp_file)
        
        # Track this instance
        self.active_instances[instance_uri] = str(temp_file)
        self.instance_graphs[instance_uri] = graph
        self.change_log[instance_uri] = []
        
        logger.info(f"Created temporary instance: {instance_uri} -> {temp_file}")
        return instance_uri, str(temp_file)
    
    def load_temp_instance(self, instance_uri: str, source_file: Optional[Path] = None) -> str:
        """
        Load an existing instance into temporary editing.
        
        Args:
            instance_uri: URI of the instance to load
            source_file: Specific file to load from, searches if None
            
        Returns:
            Path to temporary file
        """
        # Create new graph
        graph = Graph()
        
        # Bind namespaces
        for prefix, namespace in self.namespaces.items():
            graph.bind(prefix, namespace)
        
        if source_file and source_file.exists():
            # Load from specific file
            graph.parse(source_file, format="turtle")
        else:
            # Extract instance data from main ontology
            instance_query = """
            CONSTRUCT {
                ?instance ?property ?value .
            } WHERE {
                ?instance ?property ?value .
            }
            """
            
            results = self.manager._execute_query(instance_query, {"instance": URIRef(instance_uri)})
            
            # Build graph from query results
            for triple in results:
                graph.add(triple)
        
        # Ensure the instance exists in the graph
        if not list(graph.triples((URIRef(instance_uri), None, None))):
            raise ValueError(f"Instance not found: {instance_uri}")
        
        # Create temporary file
        instance_id = self._extract_instance_id(instance_uri)
        temp_file = self.temp_dir / f"{instance_id}_edit.ttl"
        
        # Save to temporary file
        self._save_graph_to_file(graph, temp_file)
        
        # Track this instance
        self.active_instances[instance_uri] = str(temp_file)
        self.instance_graphs[instance_uri] = graph
        self.change_log[instance_uri] = []
        
        logger.info(f"Loaded instance to temp: {instance_uri} -> {temp_file}")
        return str(temp_file)
    
    def update_property(self, instance_uri: str, property_uri: str, 
                       new_value: Any, old_value: Any = None) -> bool:
        """
        Update a single property value in the temporary instance.
        
        Args:
            instance_uri: URI of the instance to update
            property_uri: URI of the property to update
            new_value: New value to set
            old_value: Previous value for change tracking
            
        Returns:
            True if update was successful
        """
        if instance_uri not in self.instance_graphs:
            raise ValueError(f"Instance not in temporary editing: {instance_uri}")
        
        graph = self.instance_graphs[instance_uri]
        instance_ref = URIRef(instance_uri)
        property_ref = URIRef(property_uri)
        
        # Remove existing values for this property
        existing_values = list(graph.triples((instance_ref, property_ref, None)))
        for triple in existing_values:
            graph.remove(triple)
        
        # Add new value if not None/empty
        if new_value is not None and new_value != "":
            self._add_property_value(graph, instance_uri, property_uri, new_value)
        
        # Log the change
        change_record = {
            "timestamp": datetime.now().isoformat(),
            "property": property_uri,
            "old_value": old_value,
            "new_value": new_value,
            "action": "update"
        }
        self.change_log[instance_uri].append(change_record)
        
        # Update the temporary file
        temp_file = Path(self.active_instances[instance_uri])
        self._save_graph_to_file(graph, temp_file)
        
        logger.debug(f"Updated property {property_uri} for {instance_uri}")
        return True
    
    def add_property(self, instance_uri: str, property_uri: str, value: Any) -> bool:
        """
        Add a new property value (for multi-valued properties).
        
        Args:
            instance_uri: URI of the instance
            property_uri: URI of the property
            value: Value to add
            
        Returns:
            True if addition was successful
        """
        if instance_uri not in self.instance_graphs:
            raise ValueError(f"Instance not in temporary editing: {instance_uri}")
        
        graph = self.instance_graphs[instance_uri]
        
        # Add the new value without removing existing ones
        self._add_property_value(graph, instance_uri, property_uri, value)
        
        # Log the change
        change_record = {
            "timestamp": datetime.now().isoformat(),
            "property": property_uri,
            "old_value": None,
            "new_value": value,
            "action": "add"
        }
        self.change_log[instance_uri].append(change_record)
        
        # Update the temporary file
        temp_file = Path(self.active_instances[instance_uri])
        self._save_graph_to_file(graph, temp_file)
        
        logger.debug(f"Added property {property_uri} = {value} for {instance_uri}")
        return True
    
    def remove_property(self, instance_uri: str, property_uri: str, value: Any = None) -> bool:
        """
        Remove a property value.
        
        Args:
            instance_uri: URI of the instance
            property_uri: URI of the property to remove
            value: Specific value to remove, removes all if None
            
        Returns:
            True if removal was successful
        """
        if instance_uri not in self.instance_graphs:
            raise ValueError(f"Instance not in temporary editing: {instance_uri}")
        
        graph = self.instance_graphs[instance_uri]
        instance_ref = URIRef(instance_uri)
        property_ref = URIRef(property_uri)
        
        # Get existing values before removal for change tracking
        existing_values = list(graph.triples((instance_ref, property_ref, None)))
        
        if value is None:
            # Remove all values for this property
            for triple in existing_values:
                graph.remove(triple)
            removed_values = [self._convert_from_rdf_value(triple[2]) for triple in existing_values]
        else:
            # Remove specific value
            value_ref = self._convert_to_rdf_value(value)
            triple_to_remove = (instance_ref, property_ref, value_ref)
            
            if triple_to_remove in graph:
                graph.remove(triple_to_remove)
                removed_values = [value]
            else:
                logger.warning(f"Value {value} not found for property {property_uri}")
                return False
        
        # Log the change
        for removed_value in removed_values:
            change_record = {
                "timestamp": datetime.now().isoformat(),
                "property": property_uri,
                "old_value": removed_value,
                "new_value": None,
                "action": "remove"
            }
            self.change_log[instance_uri].append(change_record)
        
        # Update the temporary file
        temp_file = Path(self.active_instances[instance_uri])
        self._save_graph_to_file(graph, temp_file)
        
        logger.debug(f"Removed property {property_uri} values for {instance_uri}")
        return True
    
    def get_instance_data(self, instance_uri: str) -> Dict[str, Any]:
        """
        Get all property values for an instance.
        
        Args:
            instance_uri: URI of the instance
            
        Returns:
            Dictionary of property_uri -> value(s)
        """
        if instance_uri not in self.instance_graphs:
            raise ValueError(f"Instance not in temporary editing: {instance_uri}")
        
        graph = self.instance_graphs[instance_uri]
        instance_ref = URIRef(instance_uri)
        
        data = {}
        for triple in graph.triples((instance_ref, None, None)):
            property_uri = str(triple[1])
            value = self._convert_from_rdf_value(triple[2])
            
            # Handle multi-valued properties
            if property_uri in data:
                if not isinstance(data[property_uri], list):
                    data[property_uri] = [data[property_uri]]
                data[property_uri].append(value)
            else:
                data[property_uri] = value
        
        return data
    
    def get_change_log(self, instance_uri: str) -> List[Dict[str, Any]]:
        """
        Get the change log for an instance.
        
        Args:
            instance_uri: URI of the instance
            
        Returns:
            List of change records
        """
        return self.change_log.get(instance_uri, [])
    
    def save_temp_instance(self, instance_uri: str, target_file: Path, 
                          merge_mode: str = "replace") -> bool:
        """
        Save temporary instance to permanent file.
        
        Args:
            instance_uri: URI of the instance to save
            target_file: Target file path
            merge_mode: How to handle existing data ("replace", "merge", "append")
            
        Returns:
            True if save was successful
        """
        if instance_uri not in self.instance_graphs:
            raise ValueError(f"Instance not in temporary editing: {instance_uri}")
        
        graph = self.instance_graphs[instance_uri]
        target_file = Path(target_file)
        
        # Ensure target directory exists
        target_file.parent.mkdir(parents=True, exist_ok=True)
        
        if merge_mode == "replace" or not target_file.exists():
            # Simple save - replace entire file
            self._save_graph_to_file(graph, target_file)
        
        elif merge_mode == "merge":
            # Load existing file and merge
            existing_graph = Graph()
            existing_graph.parse(target_file, format="turtle")
            
            # Remove existing triples for this instance
            instance_ref = URIRef(instance_uri)
            existing_triples = list(existing_graph.triples((instance_ref, None, None)))
            for triple in existing_triples:
                existing_graph.remove(triple)
            
            # Add new triples
            for triple in graph.triples((instance_ref, None, None)):
                existing_graph.add(triple)
            
            # Save merged graph
            self._save_graph_to_file(existing_graph, target_file)
        
        elif merge_mode == "append":
            # Append to existing file
            with target_file.open("a", encoding="utf-8") as f:
                f.write("\n# Updated instance data\n")
                f.write(graph.serialize(format="turtle").decode("utf-8"))
        
        # Update change log with save action
        change_record = {
            "timestamp": datetime.now().isoformat(),
            "property": "system:save",
            "old_value": None,
            "new_value": str(target_file),
            "action": "save"
        }
        self.change_log[instance_uri].append(change_record)
        
        logger.info(f"Saved instance {instance_uri} to {target_file}")
        return True
    
    def discard_temp_instance(self, instance_uri: str) -> bool:
        """
        Discard temporary instance and cleanup files.
        
        Args:
            instance_uri: URI of the instance to discard
            
        Returns:
            True if cleanup was successful
        """
        if instance_uri not in self.active_instances:
            return True  # Already cleaned up
        
        # Remove temporary file
        temp_file = Path(self.active_instances[instance_uri])
        if temp_file.exists():
            try:
                temp_file.unlink()
            except Exception as e:
                logger.warning(f"Could not remove temp file {temp_file}: {e}")
        
        # Clean up tracking data
        del self.active_instances[instance_uri]
        del self.instance_graphs[instance_uri]
        del self.change_log[instance_uri]
        
        logger.info(f"Discarded temporary instance: {instance_uri}")
        return True
    
    def list_active_instances(self) -> List[str]:
        """Get list of currently active temporary instances."""
        return list(self.active_instances.keys())
    
    def cleanup_all_temp_files(self) -> int:
        """
        Clean up all temporary files and instances.
        
        Returns:
            Number of instances cleaned up
        """
        count = 0
        for instance_uri in list(self.active_instances.keys()):
            if self.discard_temp_instance(instance_uri):
                count += 1
        
        # Also clean up any orphaned temp files
        try:
            for temp_file in self.temp_dir.glob("*.ttl"):
                if temp_file.is_file():
                    temp_file.unlink()
                    count += 1
        except Exception as e:
            logger.warning(f"Error cleaning up temp directory: {e}")
        
        logger.info(f"Cleaned up {count} temporary instances/files")
        return count
    
    # ============================================================================
    # UTILITY METHODS
    # ============================================================================
    
    def _add_property_value(self, graph: Graph, instance_uri: str, 
                           property_uri: str, value: Any):
        """Add a property value to the graph with proper type conversion."""
        instance_ref = URIRef(instance_uri)
        property_ref = URIRef(property_uri)
        value_ref = self._convert_to_rdf_value(value)
        
        graph.add((instance_ref, property_ref, value_ref))
    
    def _convert_to_rdf_value(self, value: Any) -> Union[URIRef, Literal]:
        """Convert Python value to appropriate RDF value."""
        if isinstance(value, str):
            if value.startswith("http"):
                return URIRef(value)
            else:
                return Literal(value)
        elif isinstance(value, bool):
            return Literal(value, datatype=XSD.boolean)
        elif isinstance(value, int):
            return Literal(value, datatype=XSD.integer)
        elif isinstance(value, float):
            return Literal(value, datatype=XSD.double)
        elif hasattr(value, 'isoformat'):  # datetime/date
            return Literal(value.isoformat(), datatype=XSD.dateTime)
        else:
            return Literal(str(value))
    
    def _convert_from_rdf_value(self, rdf_value: Union[URIRef, Literal]) -> Any:
        """Convert RDF value to appropriate Python value."""
        if isinstance(rdf_value, URIRef):
            return str(rdf_value)
        elif isinstance(rdf_value, Literal):
            if rdf_value.datatype == XSD.boolean:
                return bool(rdf_value)
            elif rdf_value.datatype == XSD.integer:
                return int(rdf_value)
            elif rdf_value.datatype == XSD.double:
                return float(rdf_value)
            elif rdf_value.datatype in (XSD.dateTime, XSD.date):
                return str(rdf_value)  # Keep as string for now
            else:
                return str(rdf_value)
        else:
            return str(rdf_value)
    
    def _save_graph_to_file(self, graph: Graph, file_path: Path):
        """Save a graph to a TTL file with proper formatting."""
        with file_path.open("w", encoding="utf-8") as f:
            f.write(graph.serialize(format="turtle").decode("utf-8"))
    
    def _extract_instance_id(self, instance_uri: str) -> str:
        """Extract a simple ID from an instance URI."""
        if "#" in instance_uri:
            return instance_uri.split("#")[-1]
        elif "/" in instance_uri:
            return instance_uri.split("/")[-1]
        else:
            return instance_uri
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - cleanup temp files."""
        self.cleanup_all_temp_files()