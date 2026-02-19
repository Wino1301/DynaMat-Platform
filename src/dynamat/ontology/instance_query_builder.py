"""
DynaMat Platform - Instance Query Builder
SPARQL-based query system for finding and loading entity instances
"""

import logging
from typing import Dict, List, Optional, Any
from pathlib import Path
from datetime import datetime

from rdflib import Graph, Namespace, RDF, RDFS, Literal, URIRef, BNode
from rdflib.namespace import XSD

QUDT = Namespace("http://qudt.org/schema/qudt/")

logger = logging.getLogger(__name__)


class InstanceQueryBuilder:
    """
    Query builder for finding and loading entity instances using SPARQL.

    Uses a hybrid indexing approach:
    1. Scans entity directories (e.g., specimens/) for TTL files
    2. Builds lightweight index graph with key metadata
    3. Provides SPARQL queries for fast searching
    4. Supports lazy loading of full instance data

    Features:
    - Find all instances of a class
    - Filter by properties
    - Get display metadata for lists/tables
    - Load full instance data on demand

    Example:
        query_builder = InstanceQueryBuilder(ontology_manager)
        query_builder.scan_and_index(
            Path("specimens"),
            "https://dynamat.utep.edu/ontology#Specimen",
            "*_specimen.ttl"
        )
        specimens = query_builder.find_all_instances(
            "https://dynamat.utep.edu/ontology#Specimen"
        )
    """

    def __init__(self, ontology_manager=None):
        """
        Initialize the query builder.

        Args:
            ontology_manager: Optional OntologyManager for namespace resolution
        """
        self.logger = logging.getLogger(__name__)
        self.ontology_manager = ontology_manager

        # Index graph for fast queries
        self.index_graph = Graph()

        # Setup namespaces
        self.DYN = Namespace("https://dynamat.utep.edu/ontology#")
        self.GUI = Namespace("https://dynamat.utep.edu/gui/constraints#")
        self.index_graph.bind("dyn", self.DYN)
        self.index_graph.bind("gui", self.GUI)
        self.index_graph.bind("xsd", XSD)

        # Custom property for tracking file paths
        self.FILE_PATH = self.DYN.hasFilePath
        self.LAST_INDEXED = self.DYN.hasLastIndexed

        # Index metadata
        self.indexed_classes = {}  # class_uri -> {'dir': Path, 'pattern': str, 'count': int}

        self.logger.info("InstanceQueryBuilder initialized")

    # ============================================================================
    # INDEXING METHODS
    # ============================================================================

    def scan_and_index(self, entity_dir: Path, class_uri: str, file_pattern: str = "*.ttl") -> int:
        """
        Scan directory and build index for instances of a specific class.

        Builds a lightweight index containing:
        - Instance URI and type
        - Key display properties (ID, label, material, etc.)
        - File path for lazy loading
        - Last indexed timestamp

        Args:
            entity_dir: Directory containing entity folders (e.g., specimens/)
            class_uri: Full URI of the ontology class (e.g., "https://dynamat.utep.edu/ontology#Specimen")
            file_pattern: Glob pattern for TTL files (default: "*.ttl")

        Returns:
            Number of instances indexed
        """
        try:
            self.logger.info(f"Scanning {entity_dir} for {class_uri} instances with pattern {file_pattern}")

            if not entity_dir.exists():
                self.logger.warning(f"Directory does not exist: {entity_dir}")
                return 0

            indexed_count = 0
            class_uri_ref = URIRef(class_uri)

            # Scan directory structure
            for entity_folder in entity_dir.iterdir():
                if not entity_folder.is_dir():
                    continue

                # Find TTL files matching pattern
                ttl_files = list(entity_folder.glob(file_pattern))

                for ttl_file in ttl_files:
                    try:
                        # Extract key metadata from TTL file
                        metadata = self._extract_index_metadata(ttl_file, class_uri_ref)

                        if metadata:
                            # Add to index graph
                            self._add_to_index(metadata, ttl_file, class_uri_ref)
                            indexed_count += 1
                            self.logger.debug(f"Indexed: {ttl_file.name}")

                    except Exception as e:
                        self.logger.error(f"Failed to index {ttl_file}: {e}")
                        continue

            # Store index metadata
            self.indexed_classes[class_uri] = {
                'dir': entity_dir,
                'pattern': file_pattern,
                'count': indexed_count,
                'last_scan': datetime.now()
            }

            self.logger.info(f"Indexed {indexed_count} instances of {class_uri}")
            return indexed_count

        except Exception as e:
            self.logger.error(f"Failed to scan and index {entity_dir}: {e}")
            return 0

    def _extract_index_metadata(self, ttl_file: Path, class_uri: URIRef) -> Optional[Dict[str, Any]]:
        """
        Extract minimal metadata from TTL file for indexing.

        Extracts:
        - Instance URI
        - Instance type (to verify it matches class_uri)
        - Display properties (ID, label, material, shape, etc.)

        Args:
            ttl_file: Path to TTL file
            class_uri: Expected class URI

        Returns:
            Dictionary with metadata, or None if file invalid
        """
        try:
            # Load TTL file
            graph = Graph()
            graph.parse(ttl_file, format="turtle")

            # Find instance of the specified class
            instance_uri = None
            for s in graph.subjects(RDF.type, class_uri):
                instance_uri = s
                break

            if not instance_uri:
                self.logger.debug(f"No instance of {class_uri} found in {ttl_file.name}")
                return None

            # Extract common display properties
            metadata = {
                'uri': instance_uri,
                'type': class_uri
            }

            # Extract all properties for this instance
            for pred, obj in graph.predicate_objects(instance_uri):
                pred_str = str(pred)

                # Convert RDF value to Python value
                if isinstance(obj, Literal):
                    metadata[pred_str] = obj.toPython()
                elif isinstance(obj, URIRef):
                    metadata[pred_str] = str(obj)
                elif isinstance(obj, BNode) and (obj, RDF.type, QUDT.QuantityValue) in graph:
                    metadata[pred_str] = self._extract_quantity_value(graph, obj)

            return metadata

        except Exception as e:
            self.logger.error(f"Failed to extract metadata from {ttl_file}: {e}")
            return None

    def _add_to_index(self, metadata: Dict[str, Any], ttl_file: Path, class_uri: URIRef):
        """
        Add instance metadata to index graph.

        Args:
            metadata: Metadata dictionary from _extract_index_metadata
            ttl_file: Path to source TTL file
            class_uri: Class URI
        """
        instance_uri = metadata['uri']

        # Add instance type
        self.index_graph.add((instance_uri, RDF.type, class_uri))

        # Add file path for lazy loading
        self.index_graph.add((
            instance_uri,
            self.FILE_PATH,
            Literal(str(ttl_file.absolute()))
        ))

        # Add last indexed timestamp
        self.index_graph.add((
            instance_uri,
            self.LAST_INDEXED,
            Literal(datetime.now().isoformat(), datatype=XSD.dateTime)
        ))

        # Add all other properties from metadata
        for prop_uri, value in metadata.items():
            if prop_uri in ['uri', 'type']:
                continue

            try:
                prop_ref = URIRef(prop_uri)

                # Add as literal or URI reference
                if isinstance(value, str) and (value.startswith('http://') or value.startswith('https://')):
                    self.index_graph.add((instance_uri, prop_ref, URIRef(value)))
                else:
                    # Infer datatype
                    if isinstance(value, bool):
                        lit = Literal(value, datatype=XSD.boolean)
                    elif isinstance(value, int):
                        lit = Literal(value, datatype=XSD.integer)
                    elif isinstance(value, float):
                        lit = Literal(value, datatype=XSD.double)
                    else:
                        lit = Literal(str(value))

                    self.index_graph.add((instance_uri, prop_ref, lit))

            except Exception as e:
                self.logger.debug(f"Could not add property {prop_uri}: {e}")

    def rebuild_index(self):
        """
        Rebuild all indexes from scratch.

        Clears current index and re-scans all previously indexed directories.
        """
        self.logger.info("Rebuilding all indexes")

        # Store class info before clearing
        classes_to_rebuild = list(self.indexed_classes.items())

        # Clear index
        self.index_graph = Graph()
        self.index_graph.bind("dyn", self.DYN)
        self.index_graph.bind("gui", self.GUI)
        self.index_graph.bind("xsd", XSD)

        # Rebuild each class
        for class_uri, info in classes_to_rebuild:
            self.scan_and_index(info['dir'], class_uri, info['pattern'])

        self.logger.info("Index rebuild complete")

    # ============================================================================
    # QUERY METHODS
    # ============================================================================

    def find_all_instances(self, class_uri: str, display_properties: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """
        Find all instances of a specific class using SPARQL.

        Args:
            class_uri: Full URI of the class to search for
            display_properties: List of property URIs to include (if None, includes all)

        Returns:
            List of dictionaries containing instance data
        """
        try:
            class_uri_ref = URIRef(class_uri)

            # Build SPARQL query
            if display_properties:
                # Include specific properties
                prop_vars = []
                optional_clauses = []

                for i, prop_uri in enumerate(display_properties):
                    var_name = f"prop{i}"
                    prop_vars.append(f"?{var_name}")
                    optional_clauses.append(f"OPTIONAL {{ ?instance <{prop_uri}> ?{var_name} }}")

                query = f"""
                    SELECT ?instance ?filePath {' '.join(prop_vars)}
                    WHERE {{
                        ?instance a <{class_uri}> .
                        ?instance <{self.FILE_PATH}> ?filePath .
                        {' '.join(optional_clauses)}
                    }}
                    ORDER BY ?instance
                """
            else:
                # Get all properties
                query = f"""
                    SELECT ?instance ?filePath ?property ?value
                    WHERE {{
                        ?instance a <{class_uri}> .
                        ?instance <{self.FILE_PATH}> ?filePath .
                        OPTIONAL {{ ?instance ?property ?value }}
                    }}
                    ORDER BY ?instance
                """

            # Execute query
            results = self.index_graph.query(query)

            # Process results
            if display_properties:
                # Structured results with specific properties
                instances = []
                for row in results:
                    instance_data = {
                        'uri': str(row.instance),
                        'file_path': str(row.filePath)
                    }

                    # Add display properties
                    for i, prop_uri in enumerate(display_properties):
                        var_name = f"prop{i}"
                        value = getattr(row, var_name, None)
                        if value is not None:
                            instance_data[prop_uri] = str(value)

                    instances.append(instance_data)

                return instances
            else:
                # Group by instance URI
                instances_dict = {}
                for row in results:
                    uri = str(row.instance)

                    if uri not in instances_dict:
                        instances_dict[uri] = {
                            'uri': uri,
                            'file_path': str(row.filePath)
                        }

                    # Add property if present
                    if row.property and row.value:
                        prop_uri = str(row.property)
                        if prop_uri != str(self.FILE_PATH) and prop_uri != str(self.LAST_INDEXED):
                            instances_dict[uri][prop_uri] = str(row.value)

                return list(instances_dict.values())

        except Exception as e:
            self.logger.error(f"Failed to find instances of {class_uri}: {e}")
            return []

    def find_instance_by_id(self, class_uri: str, id_property: str, instance_id: str) -> Optional[Dict[str, Any]]:
        """
        Find a specific instance by its ID property.

        Args:
            class_uri: Full URI of the class
            id_property: URI of the ID property (e.g., "hasSpecimenID")
            instance_id: ID value to search for

        Returns:
            Dictionary with instance data, or None if not found
        """
        try:
            # Handle short property names (e.g., "hasSpecimenID" -> full URI)
            if not id_property.startswith('http'):
                id_property = f"{self.DYN}{id_property}"

            query = f"""
                SELECT ?instance ?filePath ?property ?value
                WHERE {{
                    ?instance a <{class_uri}> .
                    ?instance <{id_property}> "{instance_id}"^^xsd:string .
                    ?instance <{self.FILE_PATH}> ?filePath .
                    OPTIONAL {{ ?instance ?property ?value }}
                }}
            """

            results = self.index_graph.query(query)

            # Group properties by instance
            instance_data = None
            for row in results:
                if not instance_data:
                    instance_data = {
                        'uri': str(row.instance),
                        'file_path': str(row.filePath)
                    }

                # Add property
                if row.property and row.value:
                    prop_uri = str(row.property)
                    if prop_uri != str(self.FILE_PATH) and prop_uri != str(self.LAST_INDEXED):
                        instance_data[prop_uri] = str(row.value)

            return instance_data

        except Exception as e:
            self.logger.error(f"Failed to find instance by ID: {e}")
            return None

    def filter_instances(self, class_uri: str, filters: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Filter instances by property values.

        Args:
            class_uri: Full URI of the class
            filters: Dictionary of property_uri -> value to filter by

        Returns:
            List of matching instances
        """
        try:
            # Build filter clauses
            filter_clauses = []
            for prop_uri, value in filters.items():
                # Handle short property names
                if not prop_uri.startswith('http'):
                    prop_uri = f"{self.DYN}{prop_uri}"

                # Build filter based on value type
                # IMPORTANT: Check for URI strings BEFORE generic strings
                # since URIs are also strings
                if isinstance(value, URIRef):
                    filter_clauses.append(f'?instance <{prop_uri}> <{value}>')
                elif isinstance(value, str) and (value.startswith('http://') or value.startswith('https://')):
                    # String that looks like a URI - treat as URI reference
                    filter_clauses.append(f'?instance <{prop_uri}> <{value}>')
                elif isinstance(value, bool):
                    filter_clauses.append(f'?instance <{prop_uri}> "{str(value).lower()}"^^xsd:boolean')
                elif isinstance(value, (int, float)):
                    filter_clauses.append(f'?instance <{prop_uri}> {value}')
                elif isinstance(value, str):
                    # Regular string literal
                    filter_clauses.append(f'?instance <{prop_uri}> "{value}"^^xsd:string')

            query = f"""
                SELECT ?instance ?filePath ?property ?value
                WHERE {{
                    ?instance a <{class_uri}> .
                    {' . '.join(filter_clauses)} .
                    ?instance <{self.FILE_PATH}> ?filePath .
                    OPTIONAL {{ ?instance ?property ?value }}
                }}
                ORDER BY ?instance
            """

            self.logger.debug(f"Filter query: {query}")
            results = self.index_graph.query(query)

            # Group by instance
            instances_dict = {}
            for row in results:
                uri = str(row.instance)

                if uri not in instances_dict:
                    instances_dict[uri] = {
                        'uri': uri,
                        'file_path': str(row.filePath)
                    }

                # Add property
                if row.property and row.value:
                    prop_uri = str(row.property)
                    if prop_uri != str(self.FILE_PATH) and prop_uri != str(self.LAST_INDEXED):
                        instances_dict[uri][prop_uri] = str(row.value)

            return list(instances_dict.values())

        except Exception as e:
            self.logger.error(f"Failed to filter instances: {e}")
            return []

    # ============================================================================
    # LAZY LOADING METHODS
    # ============================================================================

    def get_instance_file_path(self, instance_uri: str) -> Optional[Path]:
        """
        Get the file path for an instance from the index.

        Args:
            instance_uri: URI of the instance

        Returns:
            Path to TTL file, or None if not found
        """
        try:
            query = f"""
                SELECT ?filePath
                WHERE {{
                    <{instance_uri}> <{self.FILE_PATH}> ?filePath
                }}
            """

            results = self.index_graph.query(query)

            for row in results:
                return Path(str(row.filePath))

            return None

        except Exception as e:
            self.logger.error(f"Failed to get file path for {instance_uri}: {e}")
            return None

    def load_full_instance_data(self, instance_uri: str) -> Dict[str, Any]:
        """
        Load complete instance data from TTL file (lazy loading).

        This re-parses the TTL file to get all property values in the format
        expected by form widgets.

        Args:
            instance_uri: URI of the instance to load

        Returns:
            Dictionary of property_uri -> value for form population
        """
        try:
            # Get file path from index
            file_path = self.get_instance_file_path(instance_uri)

            if not file_path or not file_path.exists():
                self.logger.error(f"File not found for instance {instance_uri}")
                return {}

            # Parse full TTL file
            graph = Graph()
            graph.parse(file_path, format="turtle")

            # Extract all properties
            instance_ref = URIRef(instance_uri)
            data = {}

            for pred, obj in graph.predicate_objects(instance_ref):
                pred_str = str(pred)

                # Convert RDF value to Python value
                if isinstance(obj, Literal):
                    data[pred_str] = obj.toPython()
                elif isinstance(obj, URIRef):
                    data[pred_str] = str(obj)
                elif isinstance(obj, BNode) and (obj, RDF.type, QUDT.QuantityValue) in graph:
                    data[pred_str] = self._extract_quantity_value(graph, obj)

            self.logger.info(f"Loaded {len(data)} properties for {instance_uri}")
            return data

        except Exception as e:
            self.logger.error(f"Failed to load full instance data: {e}")
            return {}

    @staticmethod
    def _extract_quantity_value(graph: Graph, bnode: BNode) -> Dict[str, Any]:
        """Extract measurement dict from a QuantityValue BNode."""
        result = {}
        for obj in graph.objects(bnode, QUDT.numericValue):
            if isinstance(obj, Literal):
                result['value'] = float(obj.toPython())
                break
        for obj in graph.objects(bnode, QUDT.unit):
            result['unit'] = str(obj)
            result['reference_unit'] = str(obj)
            break
        for obj in graph.objects(bnode, QUDT.hasQuantityKind):
            result['quantity_kind'] = str(obj)
            break
        return result

    # ============================================================================
    # UTILITY METHODS
    # ============================================================================

    def get_index_statistics(self) -> Dict[str, Any]:
        """
        Get statistics about the current index.

        Returns:
            Dictionary with index statistics
        """
        stats = {
            'indexed_classes': len(self.indexed_classes),
            'total_instances': len(self.index_graph),
            'classes': {}
        }

        for class_uri, info in self.indexed_classes.items():
            stats['classes'][class_uri] = {
                'count': info['count'],
                'directory': str(info['dir']),
                'last_scan': info['last_scan'].isoformat() if info.get('last_scan') else None
            }

        return stats

    def clear_index(self):
        """Clear all indexed data."""
        self.index_graph = Graph()
        self.index_graph.bind("dyn", self.DYN)
        self.index_graph.bind("gui", self.GUI)
        self.index_graph.bind("xsd", XSD)
        self.indexed_classes.clear()
        self.logger.info("Index cleared")
