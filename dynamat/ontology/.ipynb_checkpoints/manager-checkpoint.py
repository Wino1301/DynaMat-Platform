"""
Enhanced OntologyManager with SHACL Integration

File location: dynamat/ontology/manager.py

This updated version integrates with the SHACL shape system for improved
GUI form generation and validation capabilities.
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
    display_name: Optional[str] = None  # Added for GUI forms
    required: bool = False               # Added for SHACL integration
    functional: bool = False             # Added for single-value properties


@dataclass
class ClassInfo:
    """Information about an ontology class"""
    uri: str
    name: str
    parent_classes: List[str] = None
    properties: List[PropertyInfo] = None
    description: Optional[str] = None
    display_name: Optional[str] = None


@dataclass
class IndividualInfo:
    """Information about an individual/instance"""
    uri: str
    name: str
    display_name: str
    class_types: List[str] = None
    properties: Dict[str, Any] = None
    description: Optional[str] = None


@dataclass
class FormSchema:
    """Schema for GUI form generation - integrates with SHACL"""
    class_name: str
    title: str
    description: Optional[str] = None
    properties: List[Dict[str, Any]] = None
    groups: Dict[str, str] = None
    validation_rules: Dict[str, Any] = None


class OntologyManager:
    """
    Enhanced Ontology Manager with SHACL integration.
    
    This version provides better support for GUI form generation
    by integrating with the SHACL shape system.
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
        self._form_schemas_cache = {}
        
        # SHACL integration
        self._shape_manager = None
        
        # Load core ontology
        self.load_ontology()
    
    @property
    def shape_manager(self):
        """Lazy-load shape manager to avoid circular imports"""
        if self._shape_manager is None:
            try:
                from .shape_manager import get_shape_manager
                self._shape_manager = get_shape_manager()
            except ImportError:
                pass
        return self._shape_manager
    
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
        self._form_schemas_cache.clear()
    
    def get_form_schema(self, class_name: str, use_shacl: bool = True) -> FormSchema:
        """
        Get form schema for GUI generation.
        
        Args:
            class_name: Name of the class
            use_shacl: Whether to use SHACL shapes (preferred) or ontology structure
            
        Returns:
            FormSchema with all information needed for GUI form generation
        """
        
        cache_key = f"{class_name}_{use_shacl}"
        if cache_key in self._form_schemas_cache:
            return self._form_schemas_cache[cache_key]
        
        # Try SHACL first if available and requested
        if use_shacl and self.shape_manager:
            schema = self._get_shacl_form_schema(class_name)
            if schema:
                self._form_schemas_cache[cache_key] = schema
                return schema
        
        # Fallback to ontology-based schema
        schema = self._get_ontology_form_schema(class_name)
        self._form_schemas_cache[cache_key] = schema
        return schema
    
    def _get_shacl_form_schema(self, class_name: str) -> Optional[FormSchema]:
        """Get form schema from SHACL shapes"""
        
        if not self.shape_manager:
            return None
        
        try:
            gui_schema = self.shape_manager.get_gui_schema(class_name)
            if not gui_schema:
                return None
            
            # Convert SHACL GUI schema to FormSchema
            return FormSchema(
                class_name=class_name,
                title=gui_schema.get('title', f"{class_name} Form"),
                description=gui_schema.get('description'),
                properties=gui_schema.get('properties', []),
                groups=gui_schema.get('groups', {}),
                validation_rules=self._extract_validation_rules(gui_schema)
            )
            
        except Exception as e:
            print(f"Failed to get SHACL schema for {class_name}: {e}")
            return None
    
    def _get_ontology_form_schema(self, class_name: str) -> FormSchema:
        """Get form schema from ontology structure (fallback)"""
        
        properties = self.get_class_properties(class_name)
        
        form_properties = []
        for i, prop in enumerate(properties):
            # Convert PropertyInfo to form property
            form_prop = {
                "name": prop.name,
                "display_name": prop.display_name or self._make_display_name(prop.name),
                "description": prop.description,
                "required": prop.required,
                "order": i,
                "widget_hint": self._suggest_widget_type(prop)
            }
            
            # Add type-specific information
            if prop.range_class:
                form_prop["type"] = "object"
                form_prop["class_constraint"] = prop.range_class
                # Get available values
                individuals = self.get_individuals(prop.range_class)
                form_prop["valid_values"] = [info.display_name for info in individuals.values()]
            elif prop.data_type:
                form_prop["type"] = "data"
                form_prop["datatype"] = prop.data_type
            else:
                form_prop["type"] = "string"
                form_prop["datatype"] = "xsd:string"
            
            form_properties.append(form_prop)
        
        return FormSchema(
            class_name=class_name,
            title=f"{class_name} Data Entry",
            description=f"Form for entering {class_name} information",
            properties=form_properties,
            groups={"default": "Properties"}
        )
    
    def _extract_validation_rules(self, gui_schema: Dict[str, Any]) -> Dict[str, Any]:
        """Extract validation rules from GUI schema"""
        
        rules = {}
        
        for prop in gui_schema.get('properties', []):
            prop_name = prop.get('name')
            if not prop_name:
                continue
            
            prop_rules = {}
            
            if prop.get('required'):
                prop_rules['required'] = True
            
            if 'min_value' in prop:
                prop_rules['min_value'] = prop['min_value']
            
            if 'max_value' in prop:
                prop_rules['max_value'] = prop['max_value']
            
            if 'valid_values' in prop:
                prop_rules['valid_values'] = prop['valid_values']
            
            if 'datatype' in prop:
                prop_rules['datatype'] = prop['datatype']
            
            if prop_rules:
                rules[prop_name] = prop_rules
        
        return rules
    
    def _suggest_widget_type(self, prop: PropertyInfo) -> str:
        """Suggest appropriate widget type for property"""
        
        if prop.range_class:
            return "combobox"  # Object property -> dropdown
        elif prop.data_type:
            if "date" in prop.data_type.lower():
                return "dateedit"
            elif prop.data_type in ["xsd:integer", "xsd:int"]:
                return "spinbox"
            elif prop.data_type in ["xsd:double", "xsd:float"]:
                return "doublespinbox"
            elif prop.data_type == "xsd:boolean":
                return "checkbox"
        
        # Default cases
        if any(keyword in prop.name.lower() for keyword in ['description', 'comment', 'note']):
            return "textedit"
        
        return "lineedit"
    
    def get_class_properties(self, class_name: str) -> List[PropertyInfo]:
        """
        Get all properties for a class with enhanced metadata.
        
        This enhanced version includes information needed for SHACL integration.
        """
        
        if class_name in self._properties_cache:
            return self._properties_cache[class_name]
        
        properties = []
        class_uri = self.dyn[class_name]
        
        # Get all properties that have this class in their domain
        domain_query = f"""
        SELECT DISTINCT ?property ?range ?type ?label ?comment WHERE {{
            ?property rdfs:domain <{class_uri}> .
            OPTIONAL {{ ?property rdfs:range ?range }}
            OPTIONAL {{ ?property rdf:type ?type }}
            OPTIONAL {{ ?property rdfs:label ?label }}
            OPTIONAL {{ ?property rdfs:comment ?comment }}
        }}
        """
        
        for row in self.graph.query(domain_query):
            prop_name = self._extract_name_from_uri(str(row.property))
            
            # Determine if it's functional (single-valued)
            functional = self._is_functional_property(row.property)
            
            # Determine if it's required (this could be enhanced with SHACL)
            required = self._is_required_property(prop_name)
            
            prop_info = PropertyInfo(
                uri=str(row.property),
                name=prop_name,
                range_class=self._extract_name_from_uri(str(row.range)) if row.range else None,
                data_type=str(row.range) if row.range and 'XMLSchema' in str(row.range) else None,
                description=str(row.comment) if row.comment else None,
                display_name=str(row.label) if row.label else None,
                required=required,
                functional=functional
            )
            
            properties.append(prop_info)
        
        # Also get inherited properties from parent classes
        parent_classes = self._get_parent_classes(class_name)
        for parent_class in parent_classes:
            if parent_class != class_name:  # Avoid infinite recursion
                parent_properties = self.get_class_properties(parent_class)
                properties.extend(parent_properties)
        
        # Remove duplicates based on property name
        unique_properties = []
        seen_names = set()
        for prop in properties:
            if prop.name not in seen_names:
                unique_properties.append(prop)
                seen_names.add(prop.name)
        
        self._properties_cache[class_name] = unique_properties
        return unique_properties
    
    def _is_functional_property(self, property_uri: URIRef) -> bool:
        """Check if a property is functional (single-valued)"""
        
        query = f"""
        ASK {{
            <{property_uri}> rdf:type owl:FunctionalProperty .
        }}
        """
        
        return bool(self.graph.query(query))
    
    def _is_required_property(self, prop_name: str) -> bool:
        """
        Determine if property should be required.
        
        This is a heuristic approach - SHACL shapes provide definitive requirements.
        """
        
        required_patterns = [
            "hasName", "hasID", "hasMaterial", "hasDate", 
            "hasUser", "hasTestType", "hasSpecimenRole"
        ]
        
        return any(pattern in prop_name for pattern in required_patterns)
    
    def _get_parent_classes(self, class_name: str) -> List[str]:
        """Get parent classes for inheritance"""
        
        class_uri = self.dyn[class_name]
        
        query = f"""
        SELECT DISTINCT ?parent WHERE {{
            <{class_uri}> rdfs:subClassOf ?parent .
            FILTER(!isBlank(?parent))
        }}
        """
        
        parents = []
        for row in self.graph.query(query):
            parent_name = self._extract_name_from_uri(str(row.parent))
            if parent_name and parent_name != "Thing":  # Exclude owl:Thing
                parents.append(parent_name)
        
        return parents
    
    def _make_display_name(self, prop_name: str) -> str:
        """Convert property name to display name"""
        
        # Remove 'has' prefix
        name = prop_name
        if name.startswith('has'):
            name = name[3:]
        
        # Split camelCase and join with spaces
        import re
        name = re.sub(r'([A-Z])', r' \1', name).strip()
        return name.title()
    
    def _extract_name_from_uri(self, uri: str) -> str:
        """Extract the local name from a URI"""
        if '#' in uri:
            return uri.split('#')[-1]
        elif '/' in uri:
            return uri.split('/')[-1]
        return uri
    
    def validate_form_data(self, class_name: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate form data against ontology/SHACL constraints.
        
        Returns:
            Dictionary with validation results
        """
        
        # Try SHACL validation first
        if self.shape_manager:
            try:
                from .validators import SHACLValidator
                validator = SHACLValidator()
                
                # Create temporary TTL from form data
                temp_ttl = self._create_temp_ttl(class_name, data)
                
                # Validate
                result = validator._validate_basic(temp_ttl, class_name)
                
                return {
                    "valid": result.conforms,
                    "errors": result.errors or [],
                    "warnings": result.warnings or []
                }
                
            except Exception as e:
                print(f"SHACL validation failed: {e}")
        
        # Fallback to basic validation
        schema = self.get_form_schema(class_name, use_shacl=False)
        errors = []
        
        for prop in schema.properties:
            prop_name = prop['name']
            value = data.get(prop_name)
            
            # Check required fields
            if prop.get('required') and not value:
                errors.append(f"{prop.get('display_name', prop_name)} is required")
            
            # Check valid values
            if value and 'valid_values' in prop:
                if value not in prop['valid_values']:
                    errors.append(f"{prop.get('display_name', prop_name)} must be one of: {', '.join(prop['valid_values'])}")
        
        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": []
        }
    
    def _create_temp_ttl(self, class_name: str, data: Dict[str, Any]) -> Graph:
        """Create temporary TTL graph from form data"""
        
        temp_graph = Graph()
        temp_graph.bind("dyn", self.dyn)
        temp_graph.bind("rdf", RDF)
        temp_graph.bind("rdfs", RDFS)
        
        # Create instance
        instance_uri = self.dyn[f"TempInstance"]
        class_uri = self.dyn[class_name]
        
        temp_graph.add((instance_uri, RDF.type, class_uri))
        
        # Add properties
        for prop_name, value in data.items():
            if value:
                prop_uri = self.dyn[prop_name]
                if isinstance(value, str):
                    temp_graph.add((instance_uri, prop_uri, Literal(value)))
                else:
                    temp_graph.add((instance_uri, prop_uri, Literal(value)))
        
        return temp_graph
    
    # Keep all existing methods for backward compatibility
    def get_classes(self) -> Dict[str, ClassInfo]:
        """Get all classes (existing method maintained for compatibility)"""
        
        if self._classes_cache:
            return self._classes_cache
        
        classes = {}
        
        query = """
        SELECT DISTINCT ?class ?label ?comment WHERE {
            ?class rdf:type owl:Class .
            FILTER(!isBlank(?class))
            OPTIONAL { ?class rdfs:label ?label }
            OPTIONAL { ?class rdfs:comment ?comment }
        }
        """
        
        for row in self.graph.query(query):
            class_name = self._extract_name_from_uri(str(row.class))
            
            classes[class_name] = ClassInfo(
                uri=str(row.class),
                name=class_name,
                description=str(row.comment) if row.comment else None,
                display_name=str(row.label) if row.label else None
            )
        
        self._classes_cache = classes
        return classes
    
    def get_individuals(self, class_name: str) -> Dict[str, IndividualInfo]:
        """Get all individuals of a class (existing method maintained)"""
        
        cache_key = f"individuals_{class_name}"
        if cache_key in self._individuals_cache:
            return self._individuals_cache[cache_key]
        
        individuals = {}
        class_uri = self.dyn[class_name]
        
        # Also check subclasses
        all_class_uris = [class_uri]
        subclass_query = f"""
        SELECT DISTINCT ?subclass WHERE {{
            ?subclass rdfs:subClassOf* <{class_uri}> .
        }}
        """
        
        for row in self.graph.query(subclass_query):
            if str(row.subclass) != str(class_uri):
                all_class_uris.append(row.subclass)
        
        # Get individuals for all classes
        for cls_uri in all_class_uris:
            individual_query = f"""
            SELECT DISTINCT ?individual ?name ?label ?comment WHERE {{
                ?individual rdf:type <{cls_uri}> .
                OPTIONAL {{ ?individual dyn:hasName ?name }}
                OPTIONAL {{ ?individual rdfs:label ?label }}
                OPTIONAL {{ ?individual rdfs:comment ?comment }}
            }}
            """
            
            for row in self.graph.query(individual_query):
                individual_name = self._extract_name_from_uri(str(row.individual))
                display_name = str(row.name) if row.name else (str(row.label) if row.label else individual_name)
                
                individuals[individual_name] = IndividualInfo(
                    uri=str(row.individual),
                    name=individual_name,
                    display_name=display_name,
                    class_types=[class_name],
                    description=str(row.comment) if row.comment else None
                )
        
        self._individuals_cache[cache_key] = individuals
        return individuals


# Convenience function for global access
_global_manager = None

def get_ontology_manager() -> OntologyManager:
    """Get the global ontology manager instance"""
    global _global_manager
    if _global_manager is None:
        _global_manager = OntologyManager()
    return _global_manager