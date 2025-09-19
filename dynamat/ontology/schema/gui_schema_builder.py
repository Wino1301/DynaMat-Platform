"""
DynaMat Platform - GUI Schema Builder
Generates GUI-specific schemas and metadata from ontology definitions
Extracted from manager.py for better separation of concerns
"""

import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field

from rdflib import URIRef, Literal

from ..query.sparql_executor import SPARQLExecutor
from ..core.namespace_manager import NamespaceManager
from ..cache.metadata_cache import MetadataCache

logger = logging.getLogger(__name__)


@dataclass
class UnitInfo:
    """Information about a measurement unit from QUDT"""
    symbol: str          # Display symbol (mm, kg, etc.)
    uri: str            # QUDT URI (unit:MilliM, unit:KiloGM)
    name: str           # Full name (Millimeter, Kilogram)
    quantity_kind: str  # Quantity kind URI (qkdv:Length, qkdv:Mass)
    is_default: bool = False


@dataclass 
class CacheStatus:
    """Status information about the QUDT cache"""
    total_quantity_kinds: int
    total_units: int
    last_updated: Optional[float]
    is_loaded: bool


@dataclass
class PropertyMetadata:
    """Enhanced metadata for ontology properties used in GUI generation"""
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
    
    # Enhanced fields for better GUI support
    widget_type: Optional[str] = None
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    max_length: Optional[int] = None
    pattern: Optional[str] = None
    group_order: Optional[int] = None  

    # Unit-related fields
    quantity_kind: Optional[str] = None
    compatible_units: Optional[List[UnitInfo]] = field(default_factory=list)
    is_measurement_property: bool = False
    
    def __post_init__(self):
        """Validate and normalize after creation"""
        self.data_type = self.data_type.lower()
        if not self.display_name:
            self.display_name = self._extract_display_name(self.name)
        if not self.form_group:
            self.form_group = "General"
        if self.valid_values:
            self.valid_values = [v.strip() for v in self.valid_values if v.strip()]
            
    def _extract_display_name(self, name: str) -> str:
        """Extract human-readable name"""
        if name.startswith("has") and len(name) > 3:
            name = name[3:]
        result = ""
        for i, char in enumerate(name):
            if char.isupper() and i > 0:
                result += " "
            result += char
        return result.title()
    
    @property
    def is_numeric(self) -> bool:
        return self.data_type in ["integer", "double", "float"]
    
    @property
    def is_text(self) -> bool:
        return self.data_type in ["string", "data"]
    
    @property
    def suggested_widget_type(self) -> str:
        """Suggest best widget type"""
        if self.widget_type:
            return self.widget_type
        if self.valid_values:
            return "combo"
        elif self.data_type == "object":
            return "object_combo"
        elif self.data_type == "boolean":
            return "checkbox"
        elif self.data_type == "date":
            return "date"
        elif self.data_type == "integer":
            return "spinbox"
        elif self.data_type in ["double", "float"]:
            return "double_spinbox"
        elif "note" in self.description.lower():
            return "text_area"
        else:
            return "line_edit"


@dataclass
class ClassMetadata:
    """Enhanced metadata for ontology classes"""
    uri: str
    name: str
    label: str
    description: str
    parent_classes: List[str]
    properties: List[PropertyMetadata]
    form_groups: Dict[str, List[PropertyMetadata]]
    
    # NEW: Additional metadata
    is_abstract: bool = False
    validation_rules: Dict[str, Any] = field(default_factory=dict)
    creation_template: Optional[str] = None

    def __post_init__(self):
        if not self.label:
            self.label = self._extract_display_name(self.name)
    
    def _extract_display_name(self, name: str) -> str:
        result = ""
        for i, char in enumerate(name):
            if char.isupper() and i > 0:
                result += " "
            result += char
        return result.title()
    
    def get_required_properties(self) -> List[PropertyMetadata]:
        return [prop for prop in self.properties if prop.is_required]
    
    def get_ordered_groups(self) -> List[str]:
        def get_group_order(group_name: str) -> int:
            group_props = self.form_groups.get(group_name, [])
            return min(prop.display_order for prop in group_props) if group_props else 999
        return sorted(self.form_groups.keys(), key=get_group_order)


class GUISchemaBuilder:
    """
    Generates GUI-specific schemas and metadata from ontology.
    
    Responsibilities:
    - Extract class metadata for form building
    - Generate property metadata with GUI hints
    - Handle form grouping and ordering
    - Process QUDT units for measurement properties
    """
    
    def __init__(self, sparql_executor: SPARQLExecutor, namespace_manager: NamespaceManager, 
                 cache: MetadataCache):
        """
        Initialize the GUI schema builder.
        
        Args:
            sparql_executor: SPARQL query executor
            namespace_manager: Namespace manager
            cache: Metadata cache
        """
        self.sparql = sparql_executor
        self.ns = namespace_manager
        self.cache = cache
        
        logger.info("GUI schema builder initialized")
    
    def get_class_metadata_for_form(self, class_uri: str) -> ClassMetadata:
        """
        Get comprehensive class metadata optimized for form building.
        
        This is the main method called by form_builder.py.
        
        Args:
            class_uri: URI of the ontology class
            
        Returns:
            ClassMetadata object with all form building information
        """
        # Check cache first
        cached = self.cache.get_cached_class_metadata(class_uri)
        if cached:
            return cached
        
        logger.info(f"Building class metadata for form: {class_uri}")
        
        # Get basic class info
        class_info = self._get_basic_class_info(class_uri)
        
        # Get all properties with metadata
        properties = self._get_class_properties_with_metadata(class_uri)
        
        # Organize properties into form groups
        form_groups = self._organize_properties_into_groups(properties)
        
        # Create class metadata
        metadata = ClassMetadata(
            uri=class_uri,
            name=class_info.get('name', ''),
            label=class_info.get('label', ''),
            description=class_info.get('description', ''),
            parent_classes=class_info.get('parent_classes', []),
            properties=properties,
            form_groups=form_groups,
            is_abstract=class_info.get('is_abstract', False)
        )
        
        # Cache the result
        self.cache.cache_class_metadata(class_uri, metadata)
        
        logger.info(f"Generated metadata for {metadata.name} with {len(properties)} properties in {len(form_groups)} groups")
        return metadata
    
    def _get_basic_class_info(self, class_uri: str) -> Dict[str, Any]:
        """Get basic information about a class."""
        query = """
        SELECT ?name ?label ?description ?parent
        WHERE {{
            OPTIONAL {{ <{class_uri}> rdfs:label ?label . }}
            OPTIONAL {{ <{class_uri}> rdfs:comment ?description . }}
            OPTIONAL {{ <{class_uri}> rdfs:subClassOf ?parent . }}
            BIND(STRAFTER(STR(<{class_uri}>), "#") AS ?name)
        }}
        """.format(class_uri=class_uri)
        
        results = self.sparql.execute_query(query)
        
        if not results:
            # Fallback: extract name from URI
            name = class_uri.split('#')[-1] if '#' in class_uri else class_uri.split('/')[-1]
            return {
                'name': name,
                'label': name,
                'description': '',
                'parent_classes': [],
                'is_abstract': False
            }
        
        # Process results
        info = {
            'name': results[0].get('name', ''),
            'label': results[0].get('label', ''),
            'description': results[0].get('description', ''),
            'parent_classes': [r['parent'] for r in results if r.get('parent')],
            'is_abstract': any(r.get('isAbstract') == 'true' for r in results)
        }
        
        return info
    
    def _get_class_properties_with_metadata(self, class_uri: str) -> List[PropertyMetadata]:
        """Get all properties for a class with complete metadata."""

        # Make sure class_uri is a proper URI
        if not class_uri.startswith("http"):
            class_uri = f"{self.ns.DYN}{class_uri}"
        
        # ENHANCED SPARQL QUERY - Now extracts all needed information
        query = """
        SELECT DISTINCT ?property ?propertyName ?label ?displayName ?description 
                       ?datatype ?range ?isObjectProperty ?isDatatypeProperty
                       ?required ?displayOrder ?formGroup ?groupOrder
                       ?defaultUnit ?minValue ?maxValue ?widgetType
        WHERE {{
            {{
                <{class_uri}> rdfs:subClassOf* ?class .
                ?class rdfs:subClassOf ?restriction .
                ?restriction owl:onProperty ?property .
            }}
            UNION
            {{
                ?property rdfs:domain <{class_uri}> .
            }}
            
            # Extract property name from URI
            BIND(STRAFTER(STR(?property), "#") AS ?propertyName)
            
            # Basic property information
            OPTIONAL {{ ?property rdfs:label ?label . }}
            OPTIONAL {{ ?property dyn:hasDisplayName ?displayName . }}
            OPTIONAL {{ ?property rdfs:comment ?description . }}
            OPTIONAL {{ ?property rdfs:range ?range . }}
            
            # Property type detection
            OPTIONAL {{ ?property rdf:type owl:ObjectProperty . BIND(true AS ?isObjectProperty) }}
            OPTIONAL {{ ?property rdf:type owl:DatatypeProperty . BIND(true AS ?isDatatypeProperty) }}
            
            # Form organization
            OPTIONAL {{ ?property dyn:hasFormGroup ?formGroup . }}
            OPTIONAL {{ ?property dyn:hasGroupOrder ?groupOrder . }}
            OPTIONAL {{ ?property dyn:hasDisplayOrder ?displayOrder . }}
            OPTIONAL {{ ?property dyn:isRequired ?required . }}
            
            # Measurement properties
            OPTIONAL {{ ?property dyn:hasDefaultUnit ?defaultUnit . }}
            OPTIONAL {{ ?property dyn:hasMinValue ?minValue . }}
            OPTIONAL {{ ?property dyn:hasMaxValue ?maxValue . }}
            
            # Widget hints
            OPTIONAL {{ ?property dyn:hasWidgetType ?widgetType . }}
        }}
        ORDER BY ?groupOrder ?displayOrder ?propertyName
        """.format(class_uri=class_uri)
        
        results = self.sparql.execute_query(query)
        
        properties = []
        for result in results:
            # Extract property name with fallback
            prop_name = result.get('propertyName', '') or self._extract_name_from_uri(result['property'])
            
            # Extract display name with fallback chain
            display_name = (
                result.get('displayName') or 
                result.get('label') or 
                self._convert_name_to_display_name(prop_name)
            )
            
            # Determine data type properly
            data_type = self._determine_data_type_from_results(result)
            
            # Create property metadata with all extracted information
            prop_metadata = PropertyMetadata(
                uri=result['property'],
                name=prop_name,
                display_name=display_name,
                form_group=result.get('formGroup', 'General'),
                display_order=int(result.get('displayOrder', 999)),
                data_type=data_type,
                is_functional=self._is_functional_property(result['property']),
                is_required=bool(result.get('required', False)),
                valid_values=self._get_valid_values_for_property(result['property']),
                default_unit=result.get('defaultUnit'),
                range_class=result.get('range'),
                domain_class=class_uri,
                description=result.get('description', ''),
                widget_type=result.get('widgetType'),
                min_value=float(result['minValue']) if result.get('minValue') else None,
                max_value=float(result['maxValue']) if result.get('maxValue') else None,
                group_order=int(result.get('groupOrder', 999))
            )
            
            # Set measurement property flag and units
            if data_type in ['double', 'float', 'integer'] and prop_metadata.default_unit:
                prop_metadata.is_measurement_property = True
                prop_metadata.compatible_units = self._get_compatible_units(prop_metadata.default_unit)
            
            properties.append(prop_metadata)
        
        return properties

    def _extract_name_from_uri(self, uri: str) -> str:
        """Extract property name from URI."""
        if '#' in uri:
            return uri.split('#')[-1]
        elif '/' in uri:
            return uri.split('/')[-1]
        return uri
    
    def _convert_name_to_display_name(self, name: str) -> str:
        """Convert camelCase property name to display name."""
        if not name:
            return "Unknown Property"
        
        # Remove "has" prefix if present
        if name.startswith("has") and len(name) > 3:
            name = name[3:]
        
        # Convert camelCase to spaced words
        import re
        # Insert space before uppercase letters
        spaced = re.sub('([a-z0-9])([A-Z])', r'\1 \2', name)
        
        return spaced.title()
    
    def _determine_data_type_from_results(self, result: Dict[str, Any]) -> str:
        """Determine property data type from SPARQL results."""
        
        # Check if it's an object property
        if result.get('isObjectProperty'):
            return 'object'
        
        # Check if it's a datatype property with specific range
        if result.get('range'):
            range_uri = result['range']
            
            # XSD data types
            if 'XMLSchema#string' in range_uri:
                return 'string'
            elif 'XMLSchema#integer' in range_uri:
                return 'integer'
            elif 'XMLSchema#double' in range_uri or 'XMLSchema#float' in range_uri:
                return 'double'
            elif 'XMLSchema#boolean' in range_uri:
                return 'boolean'
            elif 'XMLSchema#date' in range_uri:
                return 'date'
            elif 'XMLSchema#anyURI' in range_uri:
                return 'uri'
        
        # Default fallback
        return 'string'

    def _get_valid_values_for_property(self, property_uri: str) -> List[str]:
        """Get valid values for properties that should have combo boxes."""
        
        # Query for individuals of the range class for object properties
        query = """
        SELECT DISTINCT ?individual ?label
        WHERE {{
            <{property_uri}> rdfs:range ?rangeClass .
            ?individual rdf:type ?rangeClass .
            OPTIONAL {{ ?individual rdfs:label ?label . }}
        }}
        ORDER BY ?label
        """.format(property_uri=property_uri)
        
        try:
            results = self.sparql.execute_query(query)
            values = []
            for result in results:
                label = result.get('label') or self._extract_name_from_uri(result['individual'])
                values.append(label)
            return values
        except:
            return []
    
    def _is_functional_property(self, property_uri: str) -> bool:
        """Check if property is functional."""
        query = """
        ASK {{
            <{property_uri}> rdf:type owl:FunctionalProperty .
        }}
        """.format(property_uri=property_uri)
        
        try:
            return self.sparql.execute_ask_query(query)
        except:
            return False
    
    def _get_compatible_units(self, default_unit_uri: str) -> List[UnitInfo]:
        """Get compatible units for a measurement property."""
        # This is a simplified implementation
        # In a full implementation, you'd query QUDT for compatible units
        return [
            UnitInfo(
                symbol="mm",
                uri=str(self.ns.UNIT.MilliM),
                name="Millimeter", 
                quantity_kind=str(self.ns.QKDV.Length),
                is_default=True
            )
        ]
    
    def _organize_properties_into_groups(self, properties: List[PropertyMetadata]) -> Dict[str, List[PropertyMetadata]]:
        """Organize properties into form groups."""
        groups = {}
        
        for prop in properties:
            group_name = prop.form_group or "General"
            if group_name not in groups:
                groups[group_name] = []
            groups[group_name].append(prop)
        
        # Sort properties within each group by display order
        for group_props in groups.values():
            group_props.sort(key=lambda p: p.display_order)
        
        return groups
    
    def get_selector_data(self, class_uri: str) -> Dict[str, List[str]]:
        """Get data for selector widgets (combo boxes)."""
        # This method provides data for object property combo boxes
        # Implementation would query for available individuals of range classes
        return {}
    
    def get_measurement_schema(self, class_uri: str) -> Dict[str, Dict[str, Any]]:
        """Get measurement schema for a class."""
        # This method provides measurement-specific information
        # Implementation would extract measurement properties and their units
        return {}