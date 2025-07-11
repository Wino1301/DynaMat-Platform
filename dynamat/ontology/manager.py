"""
DynaMat Ontology Manager

This module provides the main interface for working with the DynaMat ontology,
abstracting away RDF/SPARQL complexity and providing Python-friendly access patterns.
"""

from pathlib import Path
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass
import rdflib
from rdflib import Graph, Namespace, URIRef, Literal
from rdflib.namespace import RDF, RDFS, OWL

from ..config import config


@dataclass
class PropertyInfo:
    """Information about an ontology property"""
    uri: str
    name: str
    range_class: Optional[str] = None
    domain_class: Optional[str] = None
    data_type: Optional[str] = None
    units: List[str] = None
    description: Optional[str] = None


@dataclass
class ClassInfo:
    """Information about an ontology class"""
    uri: str
    name: str
    parent_classes: List[str] = None
    properties: List[PropertyInfo] = None
    description: Optional[str] = None


@dataclass
class IndividualInfo:
    """Information about an individual/instance"""
    uri: str
    name: str
    class_types: List[str] = None
    properties: Dict[str, Any] = None
    description: Optional[str] = None


class OntologyManager:
    """
    Central manager for DynaMat ontology operations.
    
    FOCUSED ON: Reading and querying the core ontology definition.
    NOT FOR: Creating experimental data (use ExperimentBuilder for that).
    
    Provides high-level, Python-friendly interface to the ontology
    without requiring SPARQL knowledge from users.
    """
    
    def __init__(self, ontology_path: Optional[Path] = None):
        """Initialize the ontology manager"""
        self.graph = Graph()
        self.dyn = Namespace(config.ONTOLOGY_URI)
        self.ontology_path = ontology_path or config.ONTOLOGY_DIR / "core" / "DynaMat_core.ttl"
        
        # Bind common namespaces
        self.graph.bind("dyn", self.dyn)
        self.graph.bind("rdf", RDF)
        self.graph.bind("rdfs", RDFS)
        self.graph.bind("owl", OWL)
        
        # Cached data for performance
        self._classes_cache = {}
        self._properties_cache = {}
        self._individuals_cache = {}
        self._measurement_paths_cache = {}  # Cache for nested relationship paths
        
        # Load core ontology
        self.load_ontology()
    
    def load_ontology(self, additional_files: Optional[List[Path]] = None):
        """Load the core ontology and any additional TTL files"""
        try:
            # Load core ontology
            self.graph.parse(str(self.ontology_path), format="turtle")
            
            # Load additional files if provided
            if additional_files:
                for file_path in additional_files:
                    self.graph.parse(str(file_path), format="turtle")
            
            # Clear cache after loading new data
            self._clear_cache()
            
        except Exception as e:
            raise Exception(f"Failed to load ontology: {e}")
    
    def _clear_cache(self):
        """Clear all cached data"""
        self._classes_cache.clear()
        self._properties_cache.clear()
        self._individuals_cache.clear()
        self._measurement_paths_cache.clear()
    
    # =============================================================================
    # CLASS OPERATIONS
    # =============================================================================
    
    def get_classes(self, parent_class: Optional[str] = None) -> Dict[str, ClassInfo]:
        """
        Get all classes or classes with a specific parent.
        
        Args:
            parent_class: Optional parent class name to filter by
            
        Returns:
            Dictionary mapping class names to ClassInfo objects
        """
        cache_key = f"classes_{parent_class or 'all'}"
        if cache_key in self._classes_cache:
            return self._classes_cache[cache_key]
        
        classes = {}
        
        # Query for classes
        query = """
        SELECT ?cls ?name ?parent ?comment WHERE {
            ?cls a owl:Class .
            OPTIONAL { ?cls rdfs:label ?name }
            OPTIONAL { ?cls rdfs:subClassOf ?parent }
            OPTIONAL { ?cls rdfs:comment ?comment }
        }
        """
        
        for row in self.graph.query(query):
            class_uri = str(row.cls)  
            class_name = str(row.name) if row.name else self._extract_name_from_uri(class_uri)
            
            # Filter by parent class if specified
            if parent_class and row.parent:
                parent_name = self._extract_name_from_uri(str(row.parent))
                if parent_name != parent_class:
                    continue
            
            classes[class_name] = ClassInfo(
                uri=class_uri,
                name=class_name,
                description=str(row.comment) if row.comment else None
            )
        
        self._classes_cache[cache_key] = classes
        return classes
    
    def get_class_properties(self, class_name: str) -> List[PropertyInfo]:
        """Get all properties that can be applied to a class"""
        cache_key = f"props_{class_name}"
        if cache_key in self._properties_cache:
            return self._properties_cache[cache_key]
        
        properties = []
        class_uri = self._get_class_uri(class_name)
        
        # Simplified query that extracts class properties
        query = f"""
        SELECT ?prop ?name ?range ?comment WHERE {{
            # Direct domain relationship
            ?prop rdfs:domain <{class_uri}> .
            OPTIONAL {{ ?prop rdfs:label ?name }}
            OPTIONAL {{ ?prop rdfs:range ?range }}
            OPTIONAL {{ ?prop rdfs:comment ?comment }}
        }}
        """
        
        for row in self.graph.query(query):
            prop_uri = str(row.prop)
            prop_name = str(row.name) if row.name else self._extract_name_from_uri(prop_uri)
            
            properties.append(PropertyInfo(
                uri=prop_uri,
                name=prop_name,
                range_class=self._extract_name_from_uri(str(row.range)) if row.range else None,
                domain_class=class_name,
                description=str(row.comment) if row.comment else None
            ))
        
        self._properties_cache[cache_key] = properties
        return properties
    
    # =============================================================================
    # INDIVIDUAL OPERATIONS
    # =============================================================================
    
    def get_individuals(self, class_name: Optional[str] = None) -> Dict[str, IndividualInfo]:
        """
        Get all individuals or individuals of a specific class.
        
        Args:
            class_name: Optional class name to filter by
            
        Returns:
            Dictionary mapping individual names to IndividualInfo objects
        """
        cache_key = f"individuals_{class_name or 'all'}"
        if cache_key in self._individuals_cache:
            return self._individuals_cache[cache_key]
        
        individuals = {}
        
        if class_name:
            class_uri = self._get_class_uri(class_name)
            query = f"""
            SELECT ?individual ?name ?comment WHERE {{
                ?individual a <{class_uri}> .
                OPTIONAL {{ ?individual rdfs:label ?name }}
                OPTIONAL {{ ?individual rdfs:comment ?comment }}
            }}
            """
        else:
            query = """
            SELECT ?individual ?type ?name ?comment WHERE {
                ?individual a ?type .
                ?type a owl:Class .
                OPTIONAL { ?individual rdfs:label ?name }
                OPTIONAL { ?individual rdfs:comment ?comment }
            }
            """
        
        for row in self.graph.query(query):
            individual_uri = str(row.individual)
            individual_name = str(row.name) if row.name else self._extract_name_from_uri(individual_uri)
            
            individuals[individual_name] = IndividualInfo(
                uri=individual_uri,
                name=individual_name,
                description=str(row.comment) if row.comment else None
            )
        
        self._individuals_cache[cache_key] = individuals
        return individuals
    
    def get_individual_properties(self, individual_name: str) -> Dict[str, Any]:
        """Get all property values for an individual"""
        individual_uri = self._get_individual_uri(individual_name)
        
        properties = {}
        query = f"""
        SELECT ?prop ?value WHERE {{
            <{individual_uri}> ?prop ?value .
            FILTER(?prop != rdf:type && ?prop != rdfs:label && ?prop != rdfs:comment)
        }}
        """
        
        for row in self.graph.query(query):
            prop_name = self._extract_name_from_uri(str(row.prop))
            
            # Handle different value types
            if isinstance(row.value, Literal):
                properties[prop_name] = self._convert_literal(row.value)
            else:
                properties[prop_name] = self._extract_name_from_uri(str(row.value))
        
        return properties
    
    # =============================================================================
    # MEASUREMENT AND UNITS - SOLVING THE NESTED TRAVERSAL PROBLEM
    # =============================================================================
    
    def get_measurement_paths(self, class_name: str) -> Dict[str, Dict]:
        """
        1. Direct property relationships
        2. Properties that have units defined
        3. Measurement-related properties based on naming patterns
        """
        cache_key = f"measurements_{class_name}"
        if cache_key in self._measurement_paths_cache:
            return self._measurement_paths_cache[cache_key]
        
        measurements = {}
        class_uri = self._get_class_uri(class_name)
        
        # STEP 1: Get all properties for this class
        properties = self.get_class_properties(class_name)
        
        # STEP 2: For each property, check if it's measurement-related
        for prop in properties:
            # Check if property name suggests it's a measurement
            if self._is_measurement_property(prop.name):
                measurement_info = self._get_measurement_info(prop)
                if measurement_info:
                    measurements[prop.name] = measurement_info
        
        # STEP 3: Add hardcoded measurement patterns for common cases
        common_measurements = self._get_common_measurements_for_class(class_name)
        measurements.update(common_measurements)
        
        self._measurement_paths_cache[cache_key] = measurements
        return measurements
    
    def _is_measurement_property(self, property_name: str) -> bool:
        """Check if a property name suggests it's measurement-related"""
        measurement_keywords = [
            'dimension', 'length', 'width', 'height', 'thickness', 'diameter',
            'area', 'volume', 'mass', 'weight', 'density', 'temperature',
            'pressure', 'velocity', 'force', 'stress', 'strain', 'modulus',
            'strength', 'hardness', 'time', 'rate'
        ]
        
        property_lower = property_name.lower()
        return any(keyword in property_lower for keyword in measurement_keywords)
    
    def _get_measurement_info(self, prop: PropertyInfo) -> Optional[Dict]:
        """Get measurement information for a property"""
        # Try to find units for this property
        units = self._find_units_for_property(prop.name)
        
        if not units:
            # If no units found, provide default units based on property name
            units = self._get_default_units_for_property(prop.name)
        
        if units:
            return {
                "property_path": [prop.name],
                "units": units,
                "data_type": "float",
                "description": prop.description or f"Measurement property: {prop.name}"
            }
        
        return None
    
    def _find_units_for_property(self, property_name: str) -> List[str]:
        """Find units associated with a property in the ontology"""
        # Try different patterns to find units
        units = []
        
        # Pattern 1: Direct unit relationships
        query1 = f"""
        SELECT DISTINCT ?unit ?unitName WHERE {{
            ?prop rdfs:label "{property_name}" .
            ?prop dyn:hasUnits ?unit .
            OPTIONAL {{ ?unit rdfs:label ?unitName }}
        }}
        """
        
        for row in self.graph.query(query1):
            unit_name = str(row.unitName) if row.unitName else self._extract_name_from_uri(str(row.unit))
            units.append(unit_name)
        
        # Pattern 2: Units through instances
        query2 = f"""
        SELECT DISTINCT ?unit ?unitName WHERE {{
            ?instance rdfs:label "{property_name}" .
            ?instance dyn:hasUnits ?unit .
            OPTIONAL {{ ?unit rdfs:label ?unitName }}
        }}
        """
        
        for row in self.graph.query(query2):
            unit_name = str(row.unitName) if row.unitName else self._extract_name_from_uri(str(row.unit))
            if unit_name not in units:
                units.append(unit_name)
        
        return units
    
    def _get_default_units_for_property(self, property_name: str) -> List[str]:
        """Provide sensible default units based on property name patterns"""
        property_lower = property_name.lower()
        
        # Length measurements
        if any(word in property_lower for word in ['length', 'width', 'height', 'thickness', 'diameter']):
            return ['mm', 'inch', 'm', 'cm']
        
        # Area measurements
        if 'area' in property_lower or 'section' in property_lower:
            return ['mm²', 'in²', 'm²', 'cm²']
        
        # Volume measurements
        if 'volume' in property_lower:
            return ['mm³', 'in³', 'm³', 'cm³']
        
        # Mass measurements
        if any(word in property_lower for word in ['mass', 'weight']):
            return ['kg', 'g', 'lb', 'oz']
        
        # Pressure measurements
        if 'pressure' in property_lower:
            return ['MPa', 'GPa', 'Pa', 'psi']
        
        # Velocity measurements
        if 'velocity' in property_lower or 'speed' in property_lower:
            return ['m/s', 'mm/s', 'ft/s']
        
        # Temperature measurements
        if 'temperature' in property_lower:
            return ['°C', '°F', 'K']
        
        # Stress/Strength measurements
        if any(word in property_lower for word in ['stress', 'strength', 'modulus']):
            return ['MPa', 'GPa', 'Pa', 'psi']
        
        # Strain measurements
        if 'strain' in property_lower:
            return ['%', 'mm/mm', 'in/in']
        
        # Time measurements
        if 'time' in property_lower:
            return ['s', 'ms', 'μs', 'min']
        
        # Default for unknown measurements
        return ['unit']
    
    def _get_common_measurements_for_class(self, class_name: str) -> Dict[str, Dict]:
        """Get common measurements expected for specific classes"""
        common_measurements = {}
        
        if class_name == "Specimen":
            common_measurements.update({
                "OriginalLength": {
                    "property_path": ["hasDimension"],
                    "units": ["mm", "inch", "m"],
                    "data_type": "float",
                    "description": "Original length of specimen"
                },
                "OriginalWidth": {
                    "property_path": ["hasDimension"],
                    "units": ["mm", "inch", "m"],
                    "data_type": "float",
                    "description": "Original width of specimen"
                },
                "OriginalThickness": {
                    "property_path": ["hasDimension"],
                    "units": ["mm", "inch", "m"],
                    "data_type": "float",
                    "description": "Original thickness of specimen"
                },
                "Mass": {
                    "property_path": ["hasDimension"],
                    "units": ["g", "kg", "lb"],
                    "data_type": "float",
                    "description": "Mass of specimen"
                }
            })
        
        elif class_name == "SHPBTest":
            common_measurements.update({
                "StrikerVelocity": {
                    "property_path": ["hasTestingConditions"],
                    "units": ["m/s", "mm/s", "ft/s"],
                    "data_type": "float",
                    "description": "Striker bar velocity"
                },
                "TestTemperature": {
                    "property_path": ["hasTestingConditions"],
                    "units": ["°C", "°F", "K"],
                    "data_type": "float",
                    "description": "Test temperature"
                },
                "StrainRate": {
                    "property_path": ["hasSeriesData"],
                    "units": ["1/s", "s⁻¹"],
                    "data_type": "float",
                    "description": "Strain rate during test"
                },
                "MaxStress": {
                    "property_path": ["hasSeriesData"],
                    "units": ["MPa", "GPa", "psi"],
                    "data_type": "float",
                    "description": "Maximum stress achieved"
                }
            })
        
        return common_measurements
    
    # =============================================================================
    # SCHEMA GENERATION (GUI-AGNOSTIC)
    # =============================================================================
    
    def get_class_schema(self, class_name: str) -> Dict[str, Any]:
        """
        
        """
        schema = {
            'class_name': class_name,
            'object_properties': [],
            'data_properties': [],
            'measurement_properties': []
        }
        
        # Get measurement paths (now works with actual ontology)
        measurements = self.get_measurement_paths(class_name)
        for name, info in measurements.items():
            schema['measurement_properties'].append({
                'name': name,
                'property_path': info['property_path'],
                'available_units': info['units'],
                'data_type': info['data_type'],
                'description': info['description']
            })
        
        # Get properties for the class
        properties = self.get_class_properties(class_name)
        for prop in properties:
            if prop.range_class:
                # Check if we can find individuals for this range class
                individuals = self._get_individuals_robust(prop.range_class)
                
                schema['object_properties'].append({
                    'name': prop.name,
                    'range_class': prop.range_class,
                    'available_values': list(individuals.keys()) if individuals else [],
                    'description': prop.description,
                    'required': False
                })
            else:
                # Data property
                schema['data_properties'].append({
                    'name': prop.name,
                    'data_type': prop.data_type or 'string',
                    'description': prop.description,
                    'required': False
                })
        
        # Add hardcoded properties for known classes
        schema = self._add_hardcoded_properties(schema, class_name)
        
        return schema
    
    def get_selector_data(self, class_name: str) -> Dict[str, List[str]]:
        """Get available values for selector properties (GUI-agnostic)"""
        selectors = {}
        
        properties = self.get_class_properties(class_name)
        for prop in properties:
            if prop.range_class:
                individuals = self.get_individuals(prop.range_class)
                if individuals:
                    selectors[prop.name] = list(individuals.keys())
        
        return selectors
    
    def get_measurement_schema(self, class_name: str) -> Dict[str, Dict]:
        """Get measurement-specific schema (GUI-agnostic)"""
        return self.get_measurement_paths(class_name)
    
    # =============================================================================
    # PRIVATE HELPER METHODS
    # =============================================================================
    
    def _extract_name_from_uri(self, uri: str) -> str:
        """Extract the local name from a URI"""
        if '#' in uri:
            return uri.split('#')[-1]
        elif '/' in uri:
            return uri.split('/')[-1]
        return uri
    
    def _get_class_uri(self, class_name: str) -> str:
        """Get the full URI for a class name"""
        return f"{config.ONTOLOGY_URI}{class_name}"
    
    def _get_individual_uri(self, individual_name: str) -> str:
        """Get the full URI for an individual name"""
        return f"{config.ONTOLOGY_URI}{individual_name}"
    
    def _convert_literal(self, literal: Literal) -> Any:
        """Convert RDF literal to appropriate Python type"""
        if literal.datatype:
            datatype = str(literal.datatype)
            if 'float' in datatype or 'double' in datatype:
                return float(literal)
            elif 'int' in datatype:
                return int(literal)
            elif 'boolean' in datatype:
                return bool(literal)
            elif 'date' in datatype:
                return str(literal)  # Could parse to datetime
        
        return str(literal)

    def diagnose_ontology(self) -> Dict[str, Any]:
        """Diagnose what's actually in the ontology for debugging"""
        diagnosis = {
            'total_triples': len(self.graph),
            'classes': {},
            'properties': {},
            'individuals': {},
            'missing_essentials': []
        }
        
        # Count classes
        classes_query = "SELECT (COUNT(DISTINCT ?class) as ?count) WHERE { ?class a owl:Class . }"
        for row in self.graph.query(classes_query):
            diagnosis['classes']['total'] = int(row.count)
        
        # Count properties
        props_query = """
        SELECT (COUNT(DISTINCT ?prop) as ?count) WHERE { 
            { ?prop a owl:ObjectProperty . } UNION { ?prop a owl:DatatypeProperty . }
        }
        """
        for row in self.graph.query(props_query):
            diagnosis['properties']['total'] = int(row.count)
        
        # Check for essential classes
        essential_classes = ['Specimen', 'SHPBTest', 'Material', 'Structure', 'Shape']
        for class_name in essential_classes:
            class_uri = self._get_class_uri(class_name)
            exists_query = f"ASK {{ <{class_uri}> a owl:Class . }}"
            exists = bool(self.graph.query(exists_query))
            diagnosis['classes'][class_name] = exists
            if not exists:
                diagnosis['missing_essentials'].append(f"Class: {class_name}")
        
        # Check for essential properties
        essential_properties = ['hasMaterial', 'hasStructure', 'hasDimension']
        for prop_name in essential_properties:
            prop_uri = f"{self.dyn}{prop_name}"
            exists_query = f"""
            ASK {{ 
                {{ <{prop_uri}> a owl:ObjectProperty . }} UNION 
                {{ <{prop_uri}> a owl:DatatypeProperty . }}
            }}
            """
            exists = bool(self.graph.query(exists_query))
            diagnosis['properties'][prop_name] = exists
            if not exists:
                diagnosis['missing_essentials'].append(f"Property: {prop_name}")
        
        return diagnosis
# Convenience function for global access
_global_manager = None

def get_ontology_manager() -> OntologyManager:
    """Get the global ontology manager instance"""
    global _global_manager
    if _global_manager is None:
        _global_manager = OntologyManager()
    return _global_manager