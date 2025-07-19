"""
DynaMat Platform - Ontology Manager
Comprehensive manager for RDF ontology navigation and SPARQL querying
"""

import logging
from pathlib import Path
from typing import Dict, List, Optional, Union, Any, Tuple
from dataclasses import dataclass
from enum import Enum

import rdflib
from rdflib import Graph, Namespace, URIRef, Literal, BNode
from rdflib.namespace import RDF, RDFS, OWL, XSD

from ..config import config


# Set up logging
logger = logging.getLogger(__name__)


class QueryMode(Enum):
    """Query execution modes for different use cases"""
    EXPLORATION = "exploration"  # General ontology exploration
    GUI_BUILDING = "gui_building"  # Form generation and UI metadata
    DATA_RETRIEVAL = "data_retrieval"  # Specific instance data queries

    
@dataclass
class PropertyMetadata:
    """Metadata for ontology properties used in GUI generation"""
    uri: str
    name: str
    display_name: str
    form_group: str
    display_order: int
    data_type: str
    is_functional: bool
    is_required: bool
    valid_values: List[str]
    default_unit: Optional[str]
    range_class: Optional[str]
    domain_class: Optional[str]
    description: str

@dataclass
class ClassMetadata:
    """Metadata for ontology classes"""
    uri: str
    name: str
    label: str
    description: str
    parent_classes: List[str]
    properties: List[PropertyMetadata]
    form_groups: Dict[str, List[PropertyMetadata]]


class OntologyManager:
    """
    Comprehensive manager for DynaMat ontology navigation and querying.
    
    Provides high-level methods for ontology exploration and GUI building
    without requiring SPARQL knowledge from users.
    """
    
    def __init__(self, ontology_dir: Optional[Path] = None):
        """
        Initialize the ontology manager.
        
        Args:
            ontology_dir: Path to ontology directory, defaults to config.ONTOLOGY_DIR
        """
        self.ontology_dir = ontology_dir or config.ONTOLOGY_DIR
        self.graph = Graph()
        self.namespaces = {}
        self.classes_cache = {}
        self.properties_cache = {}
        
        # Define standard namespaces
        self._setup_namespaces()
        
        # Load ontology files
        self._load_ontology_files()
        
        logger.info(f"Ontology manager initialized with {len(self.graph)} triples")
    
    def _setup_namespaces(self):
        """Set up standard namespaces for SPARQL queries"""
        self.DYN = Namespace("https://dynamat.utep.edu/ontology#")
        self.QUDT = Namespace("http://qudt.org/schema/qudt/")
        self.UNIT = Namespace("http://qudt.org/vocab/unit/")
        self.QKDV = Namespace("http://qudt.org/vocab/quantitykind/")
        self.SH = Namespace("http://www.w3.org/ns/shacl#")
        self.DC = Namespace("http://purl.org/dc/terms/")
        
        # Bind namespaces to graph
        self.graph.bind("dyn", self.DYN)
        self.graph.bind("qudt", self.QUDT)
        self.graph.bind("unit", self.UNIT)
        self.graph.bind("qkdv", self.QKDV)
        self.graph.bind("sh", self.SH)
        self.graph.bind("dc", self.DC)
        self.graph.bind("rdf", RDF)
        self.graph.bind("rdfs", RDFS)
        self.graph.bind("owl", OWL)
        self.graph.bind("xsd", XSD)
        
        # Store for easy access
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
    
    def _load_ontology_files(self):
        """Load all TTL files from the ontology directory structure"""
        if not self.ontology_dir.exists():
            raise FileNotFoundError(f"Ontology directory not found: {self.ontology_dir}")
        
        # Load files in specific order for dependencies
        load_order = [
            "core/DynaMat_core.ttl",
            "class_properties/*.ttl",
            "shapes/*.ttl",
            "class_individuals/*.ttl"
        ]
        
        files_loaded = 0
        
        for pattern in load_order:
            if "*" in pattern:
                # Handle wildcards
                base_path = self.ontology_dir / pattern.replace("*.ttl", "")
                if base_path.exists():
                    for ttl_file in base_path.glob("*.ttl"):
                        self._load_ttl_file(ttl_file)
                        files_loaded += 1
            else:
                # Handle specific files
                ttl_file = self.ontology_dir / pattern
                if ttl_file.exists():
                    self._load_ttl_file(ttl_file)
                    files_loaded += 1
        
        if files_loaded == 0:
            raise ValueError("No TTL files found in ontology directory")
        
        logger.info(f"Loaded {files_loaded} TTL files")
    
    def _load_ttl_file(self, file_path: Path):
        """Load a single TTL file into the graph"""
        try:
            self.graph.parse(file_path, format="turtle")
            logger.debug(f"Loaded {file_path}")
        except Exception as e:
            logger.error(f"Failed to load {file_path}: {e}")
            raise
    
    def reload_ontology(self):
        """Reload the entire ontology from files"""
        self.graph = Graph()
        self.classes_cache.clear()
        self.properties_cache.clear()
        self._setup_namespaces()
        self._load_ontology_files()
    
    # ============================================================================
    # EXPLORATION METHODS - General ontology navigation
    # ============================================================================
    
    def get_all_classes(self, include_individuals: bool = False) -> List[str]:
        """
        Get all classes defined in the ontology.
        
        Args:
            include_individuals: Whether to include individual instances
            
        Returns:
            List of class URIs
        """
        query = """
        SELECT DISTINCT ?class WHERE {
            ?class rdf:type owl:Class .
        }
        ORDER BY ?class
        """
        
        results = self._execute_query(query)
        classes = [str(row.class) for row in results]
        
        if include_individuals:
            individuals = self.get_all_individuals()
            classes.extend(individuals)
        
        return sorted(set(classes))
    
    def get_class_hierarchy(self, root_class: Optional[str] = None) -> Dict[str, List[str]]:
        """
        Get the class hierarchy starting from a root class.
        
        Args:
            root_class: Root class URI, defaults to dyn:Entity
            
        Returns:
            Dictionary mapping class URIs to their subclasses
        """
        if root_class is None:
            root_class = str(self.DYN.Entity)
        
        query = """
        SELECT ?class ?subclass WHERE {
            ?subclass rdfs:subClassOf* ?rootClass .
            ?subclass rdfs:subClassOf ?class .
        }
        """
        
        results = self._execute_query(query, {"rootClass": URIRef(root_class)})
        
        hierarchy = {}
        for row in results:
            parent = str(row.class)
            child = str(row.subclass)
            
            if parent not in hierarchy:
                hierarchy[parent] = []
            hierarchy[parent].append(child)
        
        return hierarchy
    
    def get_class_properties(self, class_uri: str, include_inherited: bool = True) -> List[PropertyMetadata]:
        """
        Get all properties applicable to a class.
        
        Args:
            class_uri: URI of the class
            include_inherited: Whether to include inherited properties
            
        Returns:
            List of PropertyMetadata objects
        """
        if class_uri in self.properties_cache:
            return self.properties_cache[class_uri]
        
        # Build query for properties
        if include_inherited:
            class_filter = f"?domain rdfs:subClassOf* <{class_uri}> ."
        else:
            class_filter = f"?domain = <{class_uri}> ."
        
        query = f"""
        SELECT DISTINCT ?property ?propertyType ?domain ?range ?displayName ?formGroup 
                       ?displayOrder ?validValues ?defaultUnit ?description ?functional WHERE {{
            ?property rdfs:domain ?domain .
            {class_filter}
            
            ?property rdf:type ?propertyType .
            FILTER(?propertyType IN (owl:DatatypeProperty, owl:ObjectProperty))
            
            OPTIONAL {{ ?property rdfs:range ?range }}
            OPTIONAL {{ ?property dyn:hasDisplayName ?displayName }}
            OPTIONAL {{ ?property dyn:hasFormGroup ?formGroup }}
            OPTIONAL {{ ?property dyn:hasDisplayOrder ?displayOrder }}
            OPTIONAL {{ ?property dyn:hasValidValues ?validValues }}
            OPTIONAL {{ ?property dyn:hasDefaultUnit ?defaultUnit }}
            OPTIONAL {{ ?property rdfs:comment ?description }}
            
            BIND(EXISTS {{ ?property rdf:type owl:FunctionalProperty }} AS ?functional)
        }}
        ORDER BY ?formGroup ?displayOrder ?property
        """
        
        results = self._execute_query(query)
        properties = []
        
        for row in results:
            prop_metadata = PropertyMetadata(
                uri=str(row.property),
                name=self._extract_local_name(str(row.property)),
                display_name=str(row.displayName) if row.displayName else self._extract_local_name(str(row.property)),
                form_group=str(row.formGroup) if row.formGroup else "General",
                display_order=int(row.displayOrder) if row.displayOrder else 999,
                data_type="object" if "ObjectProperty" in str(row.propertyType) else "data",
                is_functional=bool(row.functional),
                is_required=False,  # Will be determined from SHACL shapes
                valid_values=str(row.validValues).split(",") if row.validValues else [],
                default_unit=str(row.defaultUnit) if row.defaultUnit else None,
                range_class=str(row.range) if row.range else None,
                domain_class=str(row.domain),
                description=str(row.description) if row.description else ""
            )
            properties.append(prop_metadata)
        
        # Check SHACL shapes for cardinality constraints
        self._enrich_with_shacl_constraints(class_uri, properties)
        
        self.properties_cache[class_uri] = properties
        return properties
    
    def get_all_individuals(self, class_uri: Optional[str] = None) -> List[str]:
        """
        Get all individual instances.
        
        Args:
            class_uri: Filter by specific class, returns all if None
            
        Returns:
            List of individual URIs
        """
        if class_uri:
            query = """
            SELECT DISTINCT ?individual WHERE {
                ?individual rdf:type ?class .
                ?class rdfs:subClassOf* ?targetClass .
            }
            ORDER BY ?individual
            """
            results = self._execute_query(query, {"targetClass": URIRef(class_uri)})
        else:
            query = """
            SELECT DISTINCT ?individual WHERE {
                ?individual rdf:type owl:NamedIndividual .
            }
            ORDER BY ?individual
            """
            results = self._execute_query(query)
        
        return [str(row.individual) for row in results]
    
    def get_property_range(self, property_uri: str) -> Optional[str]:
        """Get the range (expected value type) of a property"""
        query = """
        SELECT ?range WHERE {
            ?property rdfs:range ?range .
        }
        """
        
        results = self._execute_query(query, {"property": URIRef(property_uri)})
        if results:
            return str(results[0].range)
        return None
    
    # ============================================================================
    # GUI BUILDING METHODS - Form generation and metadata extraction
    # ============================================================================
    
    def get_class_metadata_for_form(self, class_uri: str) -> ClassMetadata:
        """
        Get comprehensive metadata for generating GUI forms.
        
        Args:
            class_uri: URI of the class
            
        Returns:
            ClassMetadata object with all form-building information
        """
        if class_uri in self.classes_cache:
            return self.classes_cache[class_uri]
        
        # Get basic class info
        query = """
        SELECT ?label ?description WHERE {
            ?class rdfs:label ?label .
            OPTIONAL { ?class rdfs:comment ?description }
        }
        """
        
        result = self._execute_query(query, {"class": URIRef(class_uri)})
        if not result:
            raise ValueError(f"Class not found: {class_uri}")
        
        row = result[0]
        
        # Get parent classes
        parent_query = """
        SELECT ?parent WHERE {
            ?class rdfs:subClassOf ?parent .
            ?parent rdf:type owl:Class .
        }
        """
        
        parent_results = self._execute_query(parent_query, {"class": URIRef(class_uri)})
        parent_classes = [str(row.parent) for row in parent_results]
        
        # Get properties with GUI metadata
        properties = self.get_class_properties(class_uri, include_inherited=True)
        
        # Group properties by form group
        form_groups = {}
        for prop in properties:
            group = prop.form_group
            if group not in form_groups:
                form_groups[group] = []
            form_groups[group].append(prop)
        
        # Sort properties within each group
        for group in form_groups:
            form_groups[group].sort(key=lambda p: p.display_order)
        
        metadata = ClassMetadata(
            uri=class_uri,
            name=self._extract_local_name(class_uri),
            label=str(row.label) if row.label else self._extract_local_name(class_uri),
            description=str(row.description) if row.description else "",
            parent_classes=parent_classes,
            properties=properties,
            form_groups=form_groups
        )
        
        self.classes_cache[class_uri] = metadata
        return metadata
    
    def get_valid_values_for_property(self, property_uri: str) -> List[str]:
        """Get valid values for a property (for dropdowns)"""
        query = """
        SELECT ?validValues WHERE {
            ?property dyn:hasValidValues ?validValues .
        }
        """
        
        results = self._execute_query(query, {"property": URIRef(property_uri)})
        if results:
            values_str = str(results[0].validValues)
            return [v.strip() for v in values_str.split(",")]
        
        # If no valid values annotation, check if it's an object property
        # and return available individuals
        range_class = self.get_property_range(property_uri)
        if range_class:
            return self.get_all_individuals(range_class)
        
        return []
    
    def get_form_groups_for_class(self, class_uri: str) -> List[str]:
        """Get ordered list of form groups for a class"""
        properties = self.get_class_properties(class_uri)
        groups = list(set(prop.form_group for prop in properties))
        
        # Sort by the minimum display order in each group
        group_orders = {}
        for prop in properties:
            group = prop.form_group
            if group not in group_orders or prop.display_order < group_orders[group]:
                group_orders[group] = prop.display_order
        
        return sorted(groups, key=lambda g: group_orders.get(g, 999))
    
    # ============================================================================
    # DATA RETRIEVAL METHODS - Specific instance queries
    # ============================================================================
    
    def find_specimens(self, material: Optional[str] = None, 
                      structure: Optional[str] = None,
                      batch_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Find specimens matching criteria.
        
        Args:
            material: Material name or URI
            structure: Structure type name or URI  
            batch_id: Specimen batch ID
            
        Returns:
            List of specimen data dictionaries
        """
        conditions = []
        bindings = {}
        
        if material:
            if material.startswith("http"):
                conditions.append("?specimen dyn:hasMaterial ?material .")
                bindings["material"] = URIRef(material)
            else:
                conditions.append("""
                    ?specimen dyn:hasMaterial ?materialUri .
                    ?materialUri dyn:hasMaterialName ?materialName .
                    FILTER(CONTAINS(LCASE(?materialName), LCASE(?material)))
                """)
                bindings["material"] = Literal(material)
        
        if structure:
            if structure.startswith("http"):
                conditions.append("?specimen dyn:hasStructure ?structure .")
                bindings["structure"] = URIRef(structure)
            else:
                conditions.append("""
                    ?specimen dyn:hasStructure ?structureUri .
                    ?structureUri dyn:hasName ?structureName .
                    FILTER(CONTAINS(LCASE(?structureName), LCASE(?structure)))
                """)
                bindings["structure"] = Literal(structure)
        
        if batch_id:
            conditions.append("?specimen dyn:hasSpecimenBatchID ?batchId .")
            bindings["batchId"] = Literal(batch_id)
        
        query = f"""
        SELECT ?specimen ?specimenID ?materialName ?structureName ?description WHERE {{
            ?specimen rdf:type dyn:Specimen .
            ?specimen dyn:hasSpecimenID ?specimenID .
            
            OPTIONAL {{
                ?specimen dyn:hasMaterial ?materialUri .
                ?materialUri dyn:hasMaterialName ?materialName .
            }}
            
            OPTIONAL {{
                ?specimen dyn:hasStructure ?structureUri .
                ?structureUri dyn:hasName ?structureName .
            }}
            
            OPTIONAL {{ ?specimen dyn:hasDescription ?description }}
            
            {' '.join(conditions)}
        }}
        ORDER BY ?specimenID
        """
        
        results = self._execute_query(query, bindings)
        
        specimens = []
        for row in results:
            specimen_data = {
                "uri": str(row.specimen),
                "specimen_id": str(row.specimenID) if row.specimenID else "",
                "material": str(row.materialName) if row.materialName else "",
                "structure": str(row.structureName) if row.structureName else "",
                "description": str(row.description) if row.description else ""
            }
            specimens.append(specimen_data)
        
        return specimens
    
    def find_tests(self, specimen_id: Optional[str] = None,
                   test_type: Optional[str] = None,
                   date_from: Optional[str] = None,
                   date_to: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Find mechanical tests matching criteria.
        
        Args:
            specimen_id: Specimen ID to filter by
            test_type: Type of test (e.g., "SHPBCompression")
            date_from: Start date (YYYY-MM-DD)
            date_to: End date (YYYY-MM-DD)
            
        Returns:
            List of test data dictionaries
        """
        conditions = []
        bindings = {}
        
        if specimen_id:
            conditions.append("""
                ?test dyn:performedOn ?specimen .
                ?specimen dyn:hasSpecimenID ?specimenID .
                FILTER(?specimenID = ?targetSpecimenID)
            """)
            bindings["targetSpecimenID"] = Literal(specimen_id)
        
        if test_type:
            if test_type.startswith("http"):
                conditions.append("?test rdf:type ?testType .")
                bindings["testType"] = URIRef(test_type)
            else:
                # Map common test type names to URIs
                type_mapping = {
                    "SHPB": self.DYN.SHPBCompression,
                    "SHPBCompression": self.DYN.SHPBCompression,
                    "Quasistatic": self.DYN.QuasistaticTest,
                    "QuasistaticTest": self.DYN.QuasistaticTest,
                    "Tensile": self.DYN.TensileTest,
                    "TensileTest": self.DYN.TensileTest
                }
                
                if test_type in type_mapping:
                    conditions.append("?test rdf:type ?testType .")
                    bindings["testType"] = type_mapping[test_type]
                else:
                    conditions.append("""
                        ?test rdf:type ?testTypeUri .
                        ?testTypeUri rdfs:label ?testTypeLabel .
                        FILTER(CONTAINS(LCASE(?testTypeLabel), LCASE(?testType)))
                    """)
                    bindings["testType"] = Literal(test_type)
        
        if date_from:
            conditions.append("?test dyn:hasTestDate ?testDate . FILTER(?testDate >= ?dateFrom)")
            bindings["dateFrom"] = Literal(date_from, datatype=XSD.date)
        
        if date_to:
            conditions.append("?test dyn:hasTestDate ?testDate . FILTER(?testDate <= ?dateTo)")
            bindings["dateTo"] = Literal(date_to, datatype=XSD.date)
        
        query = f"""
        SELECT ?test ?testID ?testDate ?specimenID ?testType WHERE {{
            ?test rdf:type dyn:MechanicalTest .
            ?test dyn:hasTestID ?testID .
            ?test rdf:type ?testType .
            
            OPTIONAL {{ ?test dyn:hasTestDate ?testDate }}
            OPTIONAL {{
                ?test dyn:performedOn ?specimen .
                ?specimen dyn:hasSpecimenID ?specimenID .
            }}
            
            {' '.join(conditions)}
        }}
        ORDER BY DESC(?testDate) ?testID
        """
        
        results = self._execute_query(query, bindings)
        
        tests = []
        for row in results:
            test_data = {
                "uri": str(row.test),
                "test_id": str(row.testID) if row.testID else "",
                "test_date": str(row.testDate) if row.testDate else "",
                "specimen_id": str(row.specimenID) if row.specimenID else "",
                "test_type": self._extract_local_name(str(row.testType))
            }
            tests.append(test_data)
        
        return tests
    
    def get_specimen_details(self, specimen_uri: str) -> Dict[str, Any]:
        """Get detailed information about a specimen"""
        query = """
        SELECT ?property ?value WHERE {
            ?specimen ?property ?value .
        }
        """
        
        results = self._execute_query(query, {"specimen": URIRef(specimen_uri)})
        
        details = {"uri": specimen_uri}
        for row in results:
            prop_name = self._extract_local_name(str(row.property))
            value = str(row.value)
            details[prop_name] = value
        
        return details
    
    def get_test_details(self, test_uri: str) -> Dict[str, Any]:
        """Get detailed information about a test"""
        query = """
        SELECT ?property ?value WHERE {
            ?test ?property ?value .
        }
        """
        
        results = self._execute_query(query, {"test": URIRef(test_uri)})
        
        details = {"uri": test_uri}
        for row in results:
            prop_name = self._extract_local_name(str(row.property))
            value = str(row.value)
            details[prop_name] = value
        
        return details
    
    # ============================================================================
    # UTILITY METHODS
    # ============================================================================
    
    def _execute_query(self, query: str, bindings: Optional[Dict[str, Union[URIRef, Literal]]] = None) -> List[Any]:
        """Execute a SPARQL query with optional parameter bindings"""
        try:
            if bindings:
                result = self.graph.query(query, initBindings=bindings)
            else:
                result = self.graph.query(query)
            return list(result)
        except Exception as e:
            logger.error(f"SPARQL query failed: {e}")
            logger.debug(f"Query: {query}")
            logger.debug(f"Bindings: {bindings}")
            raise
    
    def _extract_local_name(self, uri: str) -> str:
        """Extract the local name from a URI"""
        if "#" in uri:
            return uri.split("#")[-1]
        elif "/" in uri:
            return uri.split("/")[-1]
        return uri
    
    def _enrich_with_shacl_constraints(self, class_uri: str, properties: List[PropertyMetadata]):
        """Enrich property metadata with SHACL shape constraints"""
        # Find SHACL shape for this class
        shape_query = """
        SELECT ?shape WHERE {
            ?shape sh:targetClass ?class .
        }
        """
        
        shape_results = self._execute_query(shape_query, {"class": URIRef(class_uri)})
        if not shape_results:
            return
        
        shape_uri = shape_results[0].shape
        
        # Get property constraints from the shape
        constraint_query = """
        SELECT ?property ?minCount ?maxCount WHERE {
            ?shape sh:property ?propertyShape .
            ?propertyShape sh:path ?property .
            OPTIONAL { ?propertyShape sh:minCount ?minCount }
            OPTIONAL { ?propertyShape sh:maxCount ?maxCount }
        }
        """
        
        constraint_results = self._execute_query(constraint_query, {"shape": shape_uri})
        
        # Apply constraints to properties
        constraints_map = {}
        for row in constraint_results:
            prop_uri = str(row.property)
            min_count = int(row.minCount) if row.minCount else 0
            max_count = int(row.maxCount) if row.maxCount else None
            constraints_map[prop_uri] = (min_count, max_count)
        
        for prop in properties:
            if prop.uri in constraints_map:
                min_count, max_count = constraints_map[prop.uri]
                prop.is_required = min_count > 0
    
    def validate_instance(self, instance_uri: str) -> List[str]:
        """
        Validate an instance against SHACL shapes.
        
        Args:
            instance_uri: URI of the instance to validate
            
        Returns:
            List of validation error messages (empty if valid)
        """
        # This would require pyshacl integration
        # For now, return empty list indicating no validation errors
        logger.warning("SHACL validation not yet implemented")
        return []
    
    def get_statistics(self) -> Dict[str, int]:
        """Get basic statistics about the ontology"""
        stats = {}
        
        # Count triples
        stats["total_triples"] = len(self.graph)
        
        # Count classes
        class_query = "SELECT (COUNT(DISTINCT ?class) AS ?count) WHERE { ?class rdf:type owl:Class }"
        result = self._execute_query(class_query)
        stats["classes"] = int(result[0].count) if result else 0
        
        # Count properties
        prop_query = """
        SELECT (COUNT(DISTINCT ?property) AS ?count) WHERE { 
            { ?property rdf:type owl:DatatypeProperty } 
            UNION 
            { ?property rdf:type owl:ObjectProperty } 
        }
        """
        result = self._execute_query(prop_query)
        stats["properties"] = int(result[0].count) if result else 0
        
        # Count individuals
        ind_query = "SELECT (COUNT(DISTINCT ?individual) AS ?count) WHERE { ?individual rdf:type owl:NamedIndividual }"
        result = self._execute_query(ind_query)
        stats["individuals"] = int(result[0].count) if result else 0
        
        return stats