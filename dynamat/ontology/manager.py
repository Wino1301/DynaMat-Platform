"""
DynaMat Ontology Manager

File location: dynamat/ontology/manager.py

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
        
        # Query for classes - FIXED: Changed ?class to ?cls to avoid Python keyword conflict
        query = """
        SELECT ?cls ?name ?parent ?comment WHERE {
            ?cls a owl:Class .
            OPTIONAL { ?cls rdfs:label ?name }
            OPTIONAL { ?cls rdfs:subClassOf ?parent }
            OPTIONAL { ?cls rdfs:comment ?comment }
        }
        """
        
        for row in self.graph.query(query):
            class_uri = str(row.cls)  # FIXED: Changed from row.class to row.cls
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
        
        # FIXED: Simplified query that works correctly
        query = f"""
        SELECT ?prop ?name ?range ?comment WHERE {{
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
    # MEASUREMENT AND UNITS - FIXED VERSION
    # =============================================================================
    
    def get_measurement_paths(self, class_name: str) -> Dict[str, Dict]:
        """
        Get measurement paths that work with actual ontology structure.
        
        This queries the ontology to find actual measurement relationships
        rather than assuming specific patterns.
        """
        cache_key = f"measurements_{class_name}"
        if cache_key in self._measurement_paths_cache:
            return self._measurement_paths_cache[cache_key]
        
        measurements = {}
        class_uri = self._get_class_uri(class_name)
        
        # Query for properties that could be measurements
        # Look for properties with numeric ranges or unit relationships
        query = f"""
        SELECT DISTINCT ?prop ?propName ?range ?rangeName ?unit ?unitName WHERE {{
            <{class_uri}> ?prop ?range .
            OPTIONAL {{ ?prop rdfs:label ?propName }}
            OPTIONAL {{ ?range rdfs:label ?rangeName }}
            
            # Look for unit relationships
            OPTIONAL {{
                ?range dyn:hasUnits ?unit .
                OPTIONAL {{ ?unit rdfs:label ?unitName }}
            }}
            
            # Or look for numeric/geometry ranges
            OPTIONAL {{
                ?range a ?rangeType .
                FILTER(
                    CONTAINS(LCASE(STR(?rangeType)), "geometry") ||
                    CONTAINS(LCASE(STR(?rangeType)), "dimension") ||
                    CONTAINS(LCASE(STR(?rangeType)), "measurement") ||
                    CONTAINS(LCASE(STR(?rangeType)), "unit")
                )
            }}
        }}
        """
        
        try:
            # Process results and group by property
            prop_data = {}
            for row in self.graph.query(query):
                prop_name = str(row.propName) if row.propName else self._extract_name_from_uri(str(row.prop))
                
                if prop_name not in prop_data:
                    prop_data[prop_name] = {
                        'units': set(),
                        'description': None,
                        'property_uri': str(row.prop)
                    }
                
                # Add unit if found
                if row.unit:
                    unit_name = str(row.unitName) if row.unitName else self._extract_name_from_uri(str(row.unit))
                    prop_data[prop_name]['units'].add(unit_name)
            
            # Convert to final format
            for prop_name, data in prop_data.items():
                if data['units'] or self._looks_like_measurement(prop_name):
                    measurements[prop_name] = {
                        "property_path": [prop_name],
                        "units": list(data['units']) if data['units'] else self._infer_units_from_name(prop_name),
                        "data_type": "float",
                        "description": f"Measurement property: {prop_name}"
                    }
            
        except Exception as e:
            print(f"Error in get_measurement_paths for {class_name}: {e}")
            # Return empty measurements if query fails
            measurements = {}
        
        self._measurement_paths_cache[cache_key] = measurements
        return measurements
    
    def _looks_like_measurement(self, property_name: str) -> bool:
        """Check if a property name suggests it's measurement-related"""
        measurement_indicators = [
            'dimension', 'length', 'width', 'height', 'thickness', 'diameter',
            'area', 'volume', 'mass', 'weight', 'density', 'temperature',
            'pressure', 'velocity', 'force', 'stress', 'strain', 'modulus',
            'strength', 'hardness', 'time', 'rate', 'value'
        ]
        
        prop_lower = property_name.lower()
        return any(indicator in prop_lower for indicator in measurement_indicators)
    
    def _infer_units_from_name(self, property_name: str) -> List[str]:
        """Infer likely units based on property name"""
        prop_lower = property_name.lower()
        
        # Length-related
        if any(word in prop_lower for word in ['length', 'width', 'height', 'thickness', 'diameter']):
            return ['mm', 'inch', 'm', 'cm']
        
        # Area-related  
        if 'area' in prop_lower:
            return ['mm²', 'in²', 'm²']
        
        # Volume-related
        if 'volume' in prop_lower:
            return ['mm³', 'in³', 'm³']
        
        # Mass-related
        if any(word in prop_lower for word in ['mass', 'weight']):
            return ['kg', 'g', 'lb']
        
        # Pressure-related
        if 'pressure' in prop_lower:
            return ['MPa', 'GPa', 'psi']
        
        # Velocity-related
        if 'velocity' in prop_lower or 'speed' in prop_lower:
            return ['m/s', 'mm/s']
        
        # Temperature-related
        if 'temperature' in prop_lower:
            return ['°C', '°F', 'K']
        
        # Stress/Strength-related
        if any(word in prop_lower for word in ['stress', 'strength', 'modulus']):
            return ['MPa', 'GPa', 'psi']
        
        # Generic measurement
        return ['unit']
    
    def get_measurement_units(self, measurement_type: str) -> List[str]:
        """Get available units for a measurement type"""
        # Query for individuals that are units and associated with this measurement
        query = f"""
        SELECT DISTINCT ?unit ?unitName WHERE {{
            ?measurement rdfs:label "{measurement_type}" .
            ?measurement dyn:hasUnits ?unit .
            OPTIONAL {{ ?unit rdfs:label ?unitName }}
        }}
        """
        
        units = []
        for row in self.graph.query(query):
            unit_name = str(row.unitName) if row.unitName else self._extract_name_from_uri(str(row.unit))
            units.append(unit_name)
        
        return units
    
    def get_materials(self) -> Dict[str, IndividualInfo]:
        """Get all available materials"""
        return self.get_individuals("Material")
    
    def get_specimen_roles(self) -> Dict[str, IndividualInfo]:
        """Get all available specimen roles"""
        return self.get_individuals("SpecimenRole")
    
    def get_equipment_types(self) -> Dict[str, ClassInfo]:
        """Get all equipment types"""
        return self.get_classes("Equipment")
    
    # =============================================================================
    # SCHEMA GENERATION (GUI-AGNOSTIC)
    # =============================================================================
    
    def get_class_schema(self, class_name: str) -> Dict[str, Any]:
        """
        Generate a raw schema for a class (GUI-agnostic).
        
        Returns structured data that any GUI framework can interpret.
        """
        schema = {
            'class_name': class_name,
            'object_properties': [],    # Properties linking to other classes/individuals
            'data_properties': [],      # Properties with literal values
            'measurement_properties': []  # Properties with value + unit pairs
        }
        
        # Get measurement paths (handles nested relationships)
        measurements = self.get_measurement_paths(class_name)
        for name, info in measurements.items():
            schema['measurement_properties'].append({
                'name': name,
                'property_path': info['property_path'],
                'available_units': info['units'],
                'data_type': info['data_type'],
                'description': info['description']
            })
        
        # Get object and data properties
        properties = self.get_class_properties(class_name)
        for prop in properties:
            if prop.range_class:
                # Check if range class has individuals
                individuals = self.get_individuals(prop.range_class)
                
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
    # DIAGNOSTIC METHODS
    # =============================================================================
    
    def diagnose_ontology(self) -> Dict[str, Any]:
        """Diagnose what's actually in the ontology for debugging"""
        diagnosis = {
            'total_triples': len(self.graph),
            'classes': {},
            'properties': {},
            'individuals': {},
            'missing_essentials': []
        }
        
        # Count classes - FIXED SPARQL query
        classes_query = "SELECT (COUNT(DISTINCT ?cls) as ?count) WHERE { ?cls a owl:Class . }"
        try:
            results = list(self.graph.query(classes_query))
            if results:
                count_value = results[0][0]  # Access the first column of first row
                diagnosis['classes']['total'] = int(count_value)
            else:
                diagnosis['classes']['total'] = 0
        except Exception as e:
            print(f"Error counting classes: {e}")
            diagnosis['classes']['total'] = 0
        
        # Count properties - FIXED SPARQL query
        props_query = """
        SELECT (COUNT(DISTINCT ?prop) as ?count) WHERE { 
            { ?prop a owl:ObjectProperty . } UNION { ?prop a owl:DatatypeProperty . }
        }
        """
        try:
            results = list(self.graph.query(props_query))
            if results:
                count_value = results[0][0]  # Access the first column of first row
                diagnosis['properties']['total'] = int(count_value)
            else:
                diagnosis['properties']['total'] = 0
        except Exception as e:
            print(f"Error counting properties: {e}")
            diagnosis['properties']['total'] = 0
        
        # Check for essential classes
        essential_classes = ['Specimen', 'SHPBTest', 'Material', 'Structure', 'Shape']
        for class_name in essential_classes:
            class_uri = self._get_class_uri(class_name)
            exists_query = f"ASK {{ <{class_uri}> a owl:Class . }}"
            try:
                exists = bool(self.graph.query(exists_query))
                diagnosis['classes'][class_name] = exists
                if not exists:
                    diagnosis['missing_essentials'].append(f"Class: {class_name}")
            except Exception as e:
                print(f"Error checking class {class_name}: {e}")
                diagnosis['classes'][class_name] = False
                diagnosis['missing_essentials'].append(f"Class: {class_name} (error)")
        
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
            try:
                exists = bool(self.graph.query(exists_query))
                diagnosis['properties'][prop_name] = exists
                if not exists:
                    diagnosis['missing_essentials'].append(f"Property: {prop_name}")
            except Exception as e:
                print(f"Error checking property {prop_name}: {e}")
                diagnosis['properties'][prop_name] = False
                diagnosis['missing_essentials'].append(f"Property: {prop_name} (error)")
        
        return diagnosis
    
    def test_measurement_detection(self, class_name: str) -> Dict[str, Any]:
        """Test measurement detection for a specific class"""
        result = {
            'class_name': class_name,
            'class_exists': False,
            'properties_found': [],
            'measurements_detected': {},
            'individuals_found': {}
        }
        
        try:
            # Check if class exists
            class_uri = self._get_class_uri(class_name)
            exists_query = f"ASK {{ <{class_uri}> a owl:Class . }}"
            result['class_exists'] = bool(self.graph.query(exists_query))
            
            if result['class_exists']:
                # Get properties
                try:
                    properties = self.get_class_properties(class_name)
                    result['properties_found'] = [prop.name for prop in properties]
                except Exception as e:
                    print(f"Error getting properties for {class_name}: {e}")
                    result['properties_found'] = []
                
                # Test measurement detection
                try:
                    measurements = self.get_measurement_paths(class_name)
                    result['measurements_detected'] = measurements
                except Exception as e:
                    print(f"Error detecting measurements for {class_name}: {e}")
                    result['measurements_detected'] = {}
                
                # Get individuals for each property's range class
                for prop in properties:
                    if prop.range_class:
                        try:
                            individuals = self.get_individuals(prop.range_class)
                            result['individuals_found'][prop.range_class] = list(individuals.keys())
                        except Exception as e:
                            print(f"Error getting individuals for {prop.range_class}: {e}")
                            result['individuals_found'][prop.range_class] = []
        
        except Exception as e:
            print(f"Error in test_measurement_detection for {class_name}: {e}")
        
        return result
    
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


# Convenience function for global access
_global_manager = None

def get_ontology_manager() -> OntologyManager:
    """Get the global ontology manager instance"""
    global _global_manager
    if _global_manager is None:
        _global_manager = OntologyManager()
    return _global_manager