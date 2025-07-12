"""
DynaMat Ontology Manager - Fixed Version

File location: dynamat/ontology/manager.py

Fixed to properly handle:
1. Hierarchical class structure (subclasses)
2. Both rdfs:label and dyn:hasName annotation properties
3. Individuals of subclasses (e.g., AluminiumAlloy individuals as Materials)
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
    display_name: str  # For GUI display (from hasName or label)
    class_types: List[str] = None
    properties: Dict[str, Any] = None
    description: Optional[str] = None


class OntologyManager:
    """
    Central manager for DynaMat ontology operations.
    
    FOCUSED ON: Reading and querying the core ontology definition.
    Fixed to properly handle hierarchical class structure and both
    rdfs:label and dyn:hasName annotation properties.
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
        self._measurement_paths_cache = {}
        
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
    # UTILITY METHODS
    # =============================================================================
    
    def _extract_name_from_uri(self, uri: str) -> str:
        """Extract the local name from a URI"""
        if '#' in uri:
            return uri.split('#')[-1]
        elif '/' in uri:
            return uri.split('/')[-1]
        return uri
    
    def _get_display_name(self, uri: str) -> tuple:
        """Get both technical name and display name for an entity"""
        tech_name = self._extract_name_from_uri(uri)
        
        # Query for display name using both hasName and rdfs:label
        query = f"""
        SELECT ?displayName WHERE {{
            <{uri}> dyn:hasName ?displayName .
        }}
        UNION
        {{
            <{uri}> rdfs:label ?displayName .
        }}
        """
        
        display_names = []
        for row in self.graph.query(query):
            display_names.append(str(row.displayName))
        
        # Prefer hasName over rdfs:label if both exist
        display_name = display_names[0] if display_names else tech_name
        
        return tech_name, display_name
    
    def _get_class_uri(self, class_name: str) -> str:
        """Get the full URI for a class name"""
        return f"{config.ONTOLOGY_URI}{class_name}"
    
    def _get_individual_uri(self, individual_name: str) -> str:
        """Get the full URI for an individual name"""
        return f"{config.ONTOLOGY_URI}{individual_name}"
    
    def _get_all_subclasses(self, parent_class_uri: str) -> List[str]:
        """Get all subclasses (direct and indirect) of a parent class"""
        query = f"""
        SELECT ?subclass WHERE {{
            ?subclass rdfs:subClassOf* <{parent_class_uri}> .
            ?subclass rdf:type owl:Class .
        }}
        """
        
        subclasses = []
        for row in self.graph.query(query):
            subclass_uri = str(row.subclass)
            if subclass_uri != parent_class_uri:  # Exclude the parent class itself
                subclasses.append(subclass_uri)
        
        return subclasses
    
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
        
        if parent_class:
            # Get all subclasses of the specified parent
            parent_uri = self._get_class_uri(parent_class)
            subclass_uris = self._get_all_subclasses(parent_uri)
            subclass_uris.append(parent_uri)  # Include parent itself
            
            for class_uri in subclass_uris:
                tech_name, display_name = self._get_display_name(class_uri)
                
                # Query for additional info
                query = f"""
                SELECT ?comment WHERE {{
                    <{class_uri}> rdfs:comment ?comment .
                }}
                """
                
                comment = None
                for row in self.graph.query(query):
                    comment = str(row.comment)
                    break
                
                classes[tech_name] = ClassInfo(
                    uri=class_uri,
                    name=tech_name,
                    description=comment
                )
        else:
            # Get all classes
            query = """
            SELECT ?cls ?comment WHERE {
                ?cls rdf:type owl:Class .
                OPTIONAL { ?cls rdfs:comment ?comment }
            }
            """
            
            for row in self.graph.query(query):
                class_uri = str(row.cls)
                tech_name, display_name = self._get_display_name(class_uri)
                
                classes[tech_name] = ClassInfo(
                    uri=class_uri,
                    name=tech_name,
                    description=str(row.comment) if row.comment else None
                )
        
        self._classes_cache[cache_key] = classes
        return classes
    
    # =============================================================================
    # INDIVIDUAL OPERATIONS
    # =============================================================================
    
    def get_individuals(self, class_name: str) -> Dict[str, IndividualInfo]:
        """
        Get all individuals of a class (including subclasses).
        
        Args:
            class_name: The class name to get individuals for
            
        Returns:
            Dictionary mapping individual names to IndividualInfo objects
        """
        cache_key = f"individuals_{class_name}"
        if cache_key in self._individuals_cache:
            return self._individuals_cache[cache_key]
        
        individuals = {}
        
        # Get the parent class URI
        parent_class_uri = self._get_class_uri(class_name)
        
        # Get all subclasses
        all_class_uris = self._get_all_subclasses(parent_class_uri)
        all_class_uris.append(parent_class_uri)  # Include parent class
        
        # Query for individuals of all these classes
        for class_uri in all_class_uris:
            query = f"""
            SELECT ?individual ?comment WHERE {{
                ?individual rdf:type <{class_uri}> .
                ?individual rdf:type owl:NamedIndividual .
                OPTIONAL {{ ?individual rdfs:comment ?comment }}
            }}
            """
            
            for row in self.graph.query(query):
                individual_uri = str(row.individual)
                tech_name, display_name = self._get_display_name(individual_uri)
                
                # Get class types for this individual
                class_types = []
                type_query = f"""
                SELECT ?type WHERE {{
                    <{individual_uri}> rdf:type ?type .
                    ?type rdf:type owl:Class .
                }}
                """
                
                for type_row in self.graph.query(type_query):
                    type_uri = str(type_row.type)
                    type_name = self._extract_name_from_uri(type_uri)
                    class_types.append(type_name)
                
                individuals[tech_name] = IndividualInfo(
                    uri=individual_uri,
                    name=tech_name,
                    display_name=display_name,
                    class_types=class_types,
                    description=str(row.comment) if row.comment else None
                )
        
        self._individuals_cache[cache_key] = individuals
        return individuals
    
    def get_units_for_measurement(self, measurement_type: str) -> List[str]:
        """Get available units for a specific measurement type"""
        
        # First try to find units directly linked to this measurement
        query = f"""
        SELECT ?unit ?unitName ?hasNameValue WHERE {{
            ?measurement rdf:type <{self._get_class_uri(measurement_type)}> .
            ?measurement dyn:hasUnits ?unit .
            OPTIONAL {{ ?unit rdfs:label ?unitName }}
            OPTIONAL {{ ?unit dyn:hasName ?hasNameValue }}
        }}
        """
        
        units = []
        for row in self.graph.query(query):
            unit_name = None
            if row.hasNameValue:
                unit_name = str(row.hasNameValue)
            elif row.unitName:
                unit_name = str(row.unitName)
            else:
                unit_name = self._extract_name_from_uri(str(row.unit))
            units.append(unit_name)
        
        # If no direct units found, try to get units by type
        if not units:
            if 'velocity' in measurement_type.lower() or 'speed' in measurement_type.lower():
                velocity_units = self.get_individuals("VelocityUnit")
                units = [info.display_name for info in velocity_units.values()]
            elif 'pressure' in measurement_type.lower() or 'stress' in measurement_type.lower():
                pressure_units = self.get_individuals("PressureUnit")
                units = [info.display_name for info in pressure_units.values()]
            elif 'temperature' in measurement_type.lower():
                temp_units = self.get_individuals("TemperatureUnit")
                units = [info.display_name for info in temp_units.values()]
            elif 'length' in measurement_type.lower() or 'distance' in measurement_type.lower():
                length_units = self.get_individuals("LengthUnit")
                units = [info.display_name for info in length_units.values()]
            elif 'time' in measurement_type.lower():
                time_units = self.get_individuals("TimeUnit")
                units = [info.display_name for info in time_units.values()]
        
        return units
    
    # =============================================================================
    # PROPERTY OPERATIONS
    # =============================================================================
    
    def get_class_properties(self, class_name: str) -> List[PropertyInfo]:
        """Get all properties that can be applied to a class"""
        cache_key = f"props_{class_name}"
        if cache_key in self._properties_cache:
            return self._properties_cache[cache_key]
        
        properties = []
        class_uri = self._get_class_uri(class_name)
        
        # Query for properties with this class as domain
        query = f"""
        SELECT ?prop ?range ?comment WHERE {{
            ?prop rdfs:domain <{class_uri}> .
            OPTIONAL {{ ?prop rdfs:range ?range }}
            OPTIONAL {{ ?prop rdfs:comment ?comment }}
        }}
        """
        
        for row in self.graph.query(query):
            prop_uri = str(row.prop)
            tech_name, display_name = self._get_display_name(prop_uri)
            
            range_class = None
            if row.range:
                range_class = self._extract_name_from_uri(str(row.range))
            
            properties.append(PropertyInfo(
                uri=prop_uri,
                name=tech_name,
                range_class=range_class,
                domain_class=class_name,
                description=str(row.comment) if row.comment else None
            ))
        
        self._properties_cache[cache_key] = properties
        return properties
    
    # =============================================================================
    # SPECIALIZED GETTERS
    # =============================================================================
    
    def get_materials(self) -> Dict[str, IndividualInfo]:
        """Get all available materials"""
        return self.get_individuals("Material")
    
    def get_units(self) -> Dict[str, IndividualInfo]:
        """Get all available units"""
        return self.get_individuals("Unit")
    
    def get_specimen_roles(self) -> Dict[str, IndividualInfo]:
        """Get all available specimen roles"""
        return self.get_individuals("SpecimenRole")
    
    def get_structures(self) -> Dict[str, IndividualInfo]:
        """Get all available structures"""
        return self.get_individuals("Structure")
    
    def get_shapes(self) -> Dict[str, IndividualInfo]:
        """Get all available shapes"""
        return self.get_individuals("Shape")
    
    def get_momentum_trap_conditions(self) -> Dict[str, IndividualInfo]:
        """Get all momentum trap conditions"""
        # Query for momentum trap states and techniques
        trap_states = self.get_individuals("MomentumTrapState")
        trap_techniques = self.get_individuals("MomentumTrapTechnique")
        
        # Combine both types
        all_traps = {}
        all_traps.update(trap_states)
        all_traps.update(trap_techniques)
        
        return all_traps
    
    def get_users(self) -> Dict[str, IndividualInfo]:
        """Get all available users"""
        return self.get_individuals("User")
    
    # =============================================================================
    # SCHEMA GENERATION
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
        
        # Get object and data properties
        properties = self.get_class_properties(class_name)
        for prop in properties:
            if prop.range_class:
                # Check if range class has individuals
                individuals = self.get_individuals(prop.range_class)
                available_values = [info.display_name for info in individuals.values()]
                
                schema['object_properties'].append({
                    'name': prop.name,
                    'range_class': prop.range_class,
                    'available_values': available_values,
                    'description': prop.description
                })
            else:
                # Data property
                schema['data_properties'].append({
                    'name': prop.name,
                    'data_type': 'string',  # Default type
                    'description': prop.description
                })
        
        return schema
    
    def get_selector_data(self, class_name: str) -> Dict[str, List[str]]:
        """Get selector data for a class (for dropdowns)"""
        
        properties = self.get_class_properties(class_name)
        selector_data = {}
        
        for prop in properties:
            if prop.range_class:
                individuals = self.get_individuals(prop.range_class)
                selector_data[prop.name] = [info.display_name for info in individuals.values()]
        
        return selector_data
    
    # =============================================================================
    # DIAGNOSTIC AND TESTING
    # =============================================================================
    
    def diagnose_ontology(self) -> Dict[str, Any]:
        """Diagnose ontology structure and completeness"""
        
        # Count total triples
        total_triples = len(self.graph)
        
        # Get all classes
        all_classes = self.get_classes()
        
        # Check for essential classes
        essential_classes = ['Material', 'Unit', 'Specimen', 'SHPBTest', 'MomentumTrap', 'Structure', 'Shape']
        class_status = {}
        for cls in essential_classes:
            class_status[cls] = cls in all_classes
        class_status['total'] = len(all_classes)
        
        # Check properties
        all_properties = []
        for cls_name in all_classes:
            props = self.get_class_properties(cls_name)
            all_properties.extend([p.name for p in props])
        
        essential_properties = ['hasMaterial', 'hasStructure', 'hasDimension', 'hasShape', 'hasSpecimenRole']
        property_status = {}
        for prop in essential_properties:
            property_status[prop] = prop in all_properties
        property_status['total'] = len(set(all_properties))
        
        return {
            'total_triples': total_triples,
            'classes': class_status,
            'properties': property_status
        }
    
    def test_measurement_detection(self, class_name: str) -> Dict[str, Any]:
        """Test measurement detection for a specific class"""
        
        # Check if class exists
        all_classes = self.get_classes()
        class_exists = class_name in all_classes
        
        # Get properties
        properties = self.get_class_properties(class_name) if class_exists else []
        property_names = [p.name for p in properties]
        
        # Look for measurement-like properties
        measurement_properties = []
        for prop in properties:
            if any(keyword in prop.name.lower() for keyword in ['dimension', 'measurement', 'value', 'length', 'diameter']):
                measurement_properties.append(prop.name)
        
        return {
            'class_exists': class_exists,
            'properties_found': property_names,
            'measurements_detected': measurement_properties
        }


# Convenience function for global access
_global_manager = None

def get_ontology_manager() -> OntologyManager:
    """Get the global ontology manager instance"""
    global _global_manager
    if _global_manager is None:
        _global_manager = OntologyManager()
    return _global_manager