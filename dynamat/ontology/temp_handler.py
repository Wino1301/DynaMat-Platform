"""
DynaMat Platform - Temporary File Handler
Manages temporary TTL files for GUI editing and form operations
Clean implementation using new architecture
"""

import logging
import tempfile
import uuid
from pathlib import Path
from typing import Dict, List, Optional, Any, Union, Tuple
from datetime import datetime

from rdflib import Graph, URIRef, Literal, BNode
from rdflib.namespace import RDF, RDFS, OWL, XSD

from .core.namespace_manager import NamespaceManager
from .query.sparql_executor import SPARQLExecutor
from ..config import config

logger = logging.getLogger(__name__)


class TempInstanceHandler:
    """
    Handles temporary TTL files for GUI editing operations.
    
    Provides methods to create, modify, and save individual instances
    without affecting the main ontology until explicitly saved.
    """
    
    def __init__(self, sparql_executor: SPARQLExecutor, namespace_manager: NamespaceManager):
        """
        Initialize with core components.
        
        Args:
            sparql_executor: SPARQL executor for querying main ontology
            namespace_manager: Namespace manager for URI handling
        """
        self.sparql = sparql_executor
        self.ns_manager = namespace_manager
        
        # Setup temp directory
        self.temp_dir = Path(tempfile.gettempdir()) / "dynamat_temp"
        self.temp_dir.mkdir(exist_ok=True)
        
        # Track active temporary instances
        self.active_instances = {}  # instance_uri -> temp_file_path
        self.instance_graphs = {}   # instance_uri -> Graph
        self.change_log = {}        # instance_uri -> list of changes
        
        logger.info(f"Temporary file handler initialized, temp dir: {self.temp_dir}")
    
    def create_temp_instance(self, class_uri: str, instance_id: Optional[str] = None, 
                           base_data: Optional[Dict[str, Any]] = None) -> Tuple[str, str]:
        """
        Create a new temporary instance for editing.
        
        Args:
            class_uri: URI of the class to instantiate
            instance_id: Optional custom instance ID
            base_data: Optional initial property values
            
        Returns:
            Tuple of (instance_uri, temp_file_path)
        """
        # Generate instance URI
        if instance_id:
            instance_uri = str(self.ns_manager.DYN[instance_id])
        else:
            instance_id = f"temp_{uuid.uuid4().hex[:8]}"
            instance_uri = str(self.ns_manager.DYN[instance_id])
        
        # Create new graph for this instance
        graph = Graph()
        self._setup_graph_namespaces(graph)
        
        # Add basic type assertion
        instance_ref = URIRef(instance_uri)
        class_ref = URIRef(class_uri)
        graph.add((instance_ref, RDF.type, class_ref))
        
        # Add base data if provided
        if base_data:
            for property_uri, value in base_data.items():
                self._add_property_value(graph, instance_uri, property_uri, value)
        
        # Create temporary file
        temp_file = self.temp_dir / f"{instance_id}_new.ttl"
        self._save_graph_to_file(graph, temp_file)
        
        # Track this instance
        self.active_instances[instance_uri] = str(temp_file)
        self.instance_graphs[instance_uri] = graph
        self.change_log[instance_uri] = []
        
        logger.info(f"Created temp instance: {instance_uri} -> {temp_file}")
        return instance_uri, str(temp_file)
    
    def load_instance_for_editing(self, instance_uri: str) -> str:
        """
        Load an existing instance from the main ontology into temporary editing.
        
        Args:
            instance_uri: URI of the instance to load
            
        Returns:
            Path to temporary file
        """
        # Query for all properties of this instance
        query = """
        SELECT ?property ?value WHERE {
            <{instance_uri}> ?property ?value .
        }
        """.format(instance_uri=instance_uri)
        
        results = self.sparql.execute_query(query)
        
        if not results:
            raise ValueError(f"Instance not found: {instance_uri}")
        
        # Create graph from query results
        graph = Graph()
        self._setup_graph_namespaces(graph)
        
        instance_ref = URIRef(instance_uri)
        for result in results:
            property_ref = URIRef(result['property'])
            value = self._convert_query_result_to_rdf(result['value'])
            graph.add((instance_ref, property_ref, value))
        
        # Create temporary file
        instance_id = self._extract_instance_id(instance_uri)
        temp_file = self.temp_dir / f"{instance_id}_edit.ttl"
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
            instance_uri: URI of the instance
            property_uri: URI of the property
            new_value: New value to set
            old_value: Optional old value to remove (if None, removes all)
            
        Returns:
            True if update was successful
        """
        if instance_uri not in self.instance_graphs:
            raise ValueError(f"Instance not in temporary editing: {instance_uri}")
        
        graph = self.instance_graphs[instance_uri]
        instance_ref = URIRef(instance_uri)
        property_ref = URIRef(property_uri)
        
        # Remove old value(s)
        if old_value is not None:
            old_value_ref = self._convert_to_rdf_value(old_value)
            graph.remove((instance_ref, property_ref, old_value_ref))
        else:
            # Remove all values for this property
            graph.remove((instance_ref, property_ref, None))
        
        # Add new value
        new_value_ref = self._convert_to_rdf_value(new_value)
        graph.add((instance_ref, property_ref, new_value_ref))
        
        # Log the change
        self._log_change(instance_uri, property_uri, old_value, new_value, "update")
        
        # Update temporary file
        temp_file = Path(self.active_instances[instance_uri])
        self._save_graph_to_file(graph, temp_file)
        
        logger.debug(f"Updated property {property_uri} = {new_value} for {instance_uri}")
        return True
    
    def add_property(self, instance_uri: str, property_uri: str, value: Any) -> bool:
        """
        Add a property value without removing existing ones.
        
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
        self._add_property_value(graph, instance_uri, property_uri, value)
        
        # Log the change
        self._log_change(instance_uri, property_uri, None, value, "add")
        
        # Update temporary file
        temp_file = Path(self.active_instances[instance_uri])
        self._save_graph_to_file(graph, temp_file)
        
        logger.debug(f"Added property {property_uri} = {value} for {instance_uri}")
        return True
    
    def remove_property(self, instance_uri: str, property_uri: str, value: Any = None) -> bool:
        """
        Remove a property value.
        
        Args:
            instance_uri: URI of the instance
            property_uri: URI of the property
            value: Specific value to remove (if None, removes all)
            
        Returns:
            True if removal was successful
        """
        if instance_uri not in self.instance_graphs:
            raise ValueError(f"Instance not in temporary editing: {instance_uri}")
        
        graph = self.instance_graphs[instance_uri]
        instance_ref = URIRef(instance_uri)
        property_ref = URIRef(property_uri)
        
        if value is not None:
            value_ref = self._convert_to_rdf_value(value)
            graph.remove((instance_ref, property_ref, value_ref))
        else:
            graph.remove((instance_ref, property_ref, None))
        
        # Log the change
        self._log_change(instance_uri, property_uri, value, None, "remove")
        
        # Update temporary file
        temp_file = Path(self.active_instances[instance_uri])
        self._save_graph_to_file(graph, temp_file)
        
        logger.debug(f"Removed property {property_uri} = {value} from {instance_uri}")
        return True
    
    def get_instance_data(self, instance_uri: str) -> Dict[str, List[Any]]:
        """
        Get current property values for an instance.
        
        Args:
            instance_uri: URI of the instance
            
        Returns:
            Dictionary mapping property URIs to lists of values
        """
        if instance_uri not in self.instance_graphs:
            raise ValueError(f"Instance not in temporary editing: {instance_uri}")
        
        graph = self.instance_graphs[instance_uri]
        instance_ref = URIRef(instance_uri)
        
        properties = {}
        for triple in graph.triples((instance_ref, None, None)):
            _, prop, value = triple
            prop_uri = str(prop)
            
            if prop_uri not in properties:
                properties[prop_uri] = []
            
            properties[prop_uri].append(self._convert_from_rdf_value(value))
        
        return properties
    
    def finalize_instance(self, instance_uri: str, output_path: Optional[Path] = None) -> str:
        """
        Finalize the temporary instance and save it permanently.
        
        Args:
            instance_uri: URI of the instance to finalize
            output_path: Optional custom output path
            
        Returns:
            Path to the finalized file
        """
        if instance_uri not in self.instance_graphs:
            raise ValueError(f"Instance not in temporary editing: {instance_uri}")
        
        graph = self.instance_graphs[instance_uri]
        
        # Determine output path
        if output_path is None:
            instance_id = self._extract_instance_id(instance_uri)
            output_path = Path.cwd() / f"{instance_id}.ttl"
        
        # Save finalized version
        self._save_graph_to_file(graph, output_path)
        
        # Cleanup temporary tracking
        temp_file = Path(self.active_instances[instance_uri])
        if temp_file.exists():
            temp_file.unlink()
        
        del self.active_instances[instance_uri]
        del self.instance_graphs[instance_uri]
        del self.change_log[instance_uri]
        
        logger.info(f"Finalized instance {instance_uri} -> {output_path}")
        return str(output_path)
    
    def discard_changes(self, instance_uri: str):
        """
        Discard all changes to an instance and remove from temporary editing.
        
        Args:
            instance_uri: URI of the instance
        """
        if instance_uri not in self.active_instances:
            return
        
        # Remove temporary file
        temp_file = Path(self.active_instances[instance_uri])
        if temp_file.exists():
            temp_file.unlink()
        
        # Cleanup tracking
        del self.active_instances[instance_uri]
        del self.instance_graphs[instance_uri]
        del self.change_log[instance_uri]
        
        logger.info(f"Discarded changes for instance {instance_uri}")
    
    def get_change_log(self, instance_uri: str) -> List[Dict[str, Any]]:
        """Get the change log for an instance."""
        return self.change_log.get(instance_uri, [])
    
    def cleanup_all_temp_files(self):
        """Clean up all temporary files."""
        for instance_uri in list(self.active_instances.keys()):
            self.discard_changes(instance_uri)
        
        logger.info("All temporary files cleaned up")
    
    # ============================================================================
    # PRIVATE HELPER METHODS
    # ============================================================================
    
    def _setup_graph_namespaces(self, graph: Graph):
        """Setup namespaces for a graph."""
        self.ns_manager.setup_graph_namespaces(graph)
    
    def _add_property_value(self, graph: Graph, instance_uri: str, property_uri: str, value: Any):
        """Add a property value to a graph."""
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
                return str(rdf_value)
            else:
                return str(rdf_value)
        else:
            return str(rdf_value)
    
    def _convert_query_result_to_rdf(self, value: str) -> Union[URIRef, Literal]:
        """Convert query result string to appropriate RDF value."""
        if value.startswith("http"):
            return URIRef(value)
        else:
            return Literal(value)
    
    def _log_change(self, instance_uri: str, property_uri: str, old_value: Any, new_value: Any, action: str):
        """Log a change to the change log."""
        change_record = {
            "timestamp": datetime.now().isoformat(),
            "property": property_uri,
            "old_value": old_value,
            "new_value": new_value,
            "action": action
        }
        self.change_log[instance_uri].append(change_record)
    
    def _save_graph_to_file(self, graph: Graph, file_path: Path):
        """Save a graph to a TTL file with proper formatting."""
        with file_path.open("w", encoding="utf-8") as f:
            f.write(graph.serialize(format="turtle"))
    
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