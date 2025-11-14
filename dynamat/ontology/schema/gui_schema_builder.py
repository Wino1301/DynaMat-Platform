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
from ..qudt.qudt_manager import QUDTManager

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
    is_read_only: bool = False

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
        # 1. Explicit widget_type always wins
        if self.widget_type:
            return self.widget_type

        # 2. For object properties, check if we have valid_values (enumeration-like)
        if self.data_type == "object":
            if self.valid_values and len(self.valid_values) > 0:
                # Has enumeration values - use regular combo
                return "combo"
            else:
                # No enumeration - query for instances
                return "object_combo"

        # 3. Then check for valid_values on data properties
        if self.valid_values:
            return "combo"

        # 4. Rest of the checks...
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
                 cache: MetadataCache, qudt_manager: QUDTManager):
        """
        Initialize the GUI schema builder.

        Args:
            sparql_executor: SPARQL query executor
            namespace_manager: Namespace manager
            cache: Metadata cache
            qudt_manager: QUDT unit manager
        """
        self.sparql = sparql_executor
        self.ns = namespace_manager
        self.cache = cache
        self.qudt_manager = qudt_manager

        # Statistics tracking (always-on)
        self._metadata_build_counts = {}  # class_uri -> count
        self._property_extraction_counts = {}  # class_uri -> property_count
        self._unit_lookup_stats = {
            'success': 0,
            'failed': 0,
            'no_quantity_kind': 0
        }
        self._form_group_stats = {}  # class_uri -> group_count
        self._widget_type_inferences = {}  # data_type -> {widget_type -> count}

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
        from ...config import Config

        # Check cache first (controlled by global config)
        if Config.USE_SCHEMA_CACHE:
            cached = self.cache.get_cached_class_metadata(class_uri)
            if cached:
                logger.debug(f"Returning cached class metadata for {class_uri}")
                # Track statistics even for cached results
                self._metadata_build_counts[class_uri] = self._metadata_build_counts.get(class_uri, 0) + 1
                self._property_extraction_counts[class_uri] = len(cached.properties)
                self._form_group_stats[class_uri] = len(cached.form_groups)
                return cached

        logger.info(f"Building class metadata for form: {class_uri}")

        # Get basic class info
        class_info = self._get_basic_class_info(class_uri)

        # Get all properties with metadata
        properties = self._get_class_properties_for_class(class_uri)

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

        # Cache the result (controlled by global config)
        if Config.USE_SCHEMA_CACHE:
            self.cache.cache_class_metadata(class_uri, metadata)

        logger.info(f"Generated metadata for {metadata.name} with {len(properties)} properties in {len(form_groups)} groups")

        # Track statistics
        self._metadata_build_counts[class_uri] = self._metadata_build_counts.get(class_uri, 0) + 1
        self._property_extraction_counts[class_uri] = len(properties)
        self._form_group_stats[class_uri] = len(form_groups)

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
    
    def _get_class_properties_for_class(self, class_uri: str) -> List[PropertyMetadata]:
        """Get all properties for a class with complete metadata."""

        # Make sure class_uri is a proper URI
        if not class_uri.startswith("http"):
            class_uri = f"{self.ns.DYN}{class_uri}"
        
        # SPARQL QUERY - Extracts all class properties
        query = """
        SELECT DISTINCT ?property ?propertyName ?label ?displayName ?description
                        ?formGroup ?range ?displayOrder ?groupOrder ?required ?isReadOnly
                        ?defaultUnit ?quantityKind ?minValue ?maxValue ?widgetType WHERE {{ 
            {{
                ?property rdfs:domain <{class_uri}> .
            }}
            UNION
            {{
                ?property rdfs:domain ?parentClass .
                <{class_uri}> rdfs:subClassOf* ?parentClass .
            }}
            
            OPTIONAL {{ ?property rdfs:label ?label . }}
            OPTIONAL {{ ?property rdfs:comment ?description . }}
            OPTIONAL {{ ?property rdfs:range ?range . }}
            OPTIONAL {{ ?property dyn:hasDisplayName ?displayName . }}
            OPTIONAL {{ ?property dyn:hasFormGroup ?formGroup . }}
            
            OPTIONAL {{ ?property dyn:hasGroupOrder ?groupOrder . }}
            OPTIONAL {{ ?property dyn:hasDisplayOrder ?displayOrder . }}
            OPTIONAL {{ ?property dyn:isRequired ?required . }}
            OPTIONAL {{ ?property dyn:isReadOnly ?isReadOnly . }}

            # Measurement properties
            OPTIONAL {{ ?property dyn:hasDefaultUnit ?defaultUnit . }}
            OPTIONAL {{ ?property qudt:hasQuantityKind ?quantityKind . }}
            OPTIONAL {{ ?property dyn:hasMinValue ?minValue . }}
            OPTIONAL {{ ?property dyn:hasMaxValue ?maxValue . }}

            # Widget hints
            OPTIONAL {{ ?property dyn:hasWidgetType ?widgetType . }}
            
        }}
        ORDER BY ?groupOrder ?displayOrder ?propertyName
        """.format(class_uri=class_uri)
        
        results = self.sparql.execute_query(query)

        # After the query results
        for result in results:
            prop_name = result.get('propertyName', '')
            if 'Lattice' in prop_name:  # Debug specific properties
                self.logger.debug(f"Property {prop_name}:")
                self.logger.debug(f"  range: {result.get('range')}")
                self.logger.debug(f"  defaultUnit: {result.get('defaultUnit')}")
                self.logger.debug(f"  quantityKind: {result.get('quantityKind')}")
        
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
                is_read_only=bool(result.get('isReadOnly', False)),
                valid_values=self._get_valid_values_for_property(result['property']),
                default_unit=result.get('defaultUnit'),
                quantity_kind=result.get('quantityKind'),
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
                prop_metadata.compatible_units = self._get_compatible_units(
                    prop_metadata.quantity_kind,
                    prop_metadata.default_unit
                )

            # Track widget type inference for statistics
            widget_type = prop_metadata.suggested_widget_type
            if data_type not in self._widget_type_inferences:
                self._widget_type_inferences[data_type] = {}
            self._widget_type_inferences[data_type][widget_type] = self._widget_type_inferences[data_type].get(widget_type, 0) + 1

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
         
        # Measurement properties have defaultUnit or quantityKind
        if result.get('defaultUnit') or result.get('quantityKind'):
            return 'double'
        
        # THEN: Check if we have range information
        if result.get('range'):
            range_uri = str(result['range'])
            
            # XSD data types (from W3C XML Schema)
            if 'XMLSchema#string' in range_uri or 'string' in range_uri.lower():
                return 'string'
            elif 'XMLSchema#integer' in range_uri or 'integer' in range_uri.lower():
                return 'integer'
            elif 'XMLSchema#double' in range_uri or 'XMLSchema#float' in range_uri:
                return 'double'
            elif 'XMLSchema#boolean' in range_uri:
                return 'boolean'
            elif 'XMLSchema#date' in range_uri:
                return 'date'
            elif 'XMLSchema#anyURI' in range_uri:
                return 'uri'
            # If range is NOT an XSD type, it's an object property
            elif 'XMLSchema' not in range_uri:
                return 'object'
        
        # Fallback: assume string for data properties without range
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
    
    def _get_compatible_units(self, quantity_kind_uri: str, default_unit_uri: str = None) -> List[UnitInfo]:
        """
        Get compatible units for a quantity kind from QUDT.

        Args:
            quantity_kind_uri: URI of the quantity kind (e.g., qkdv:Length)
            default_unit_uri: URI of the default unit to mark as default

        Returns:
            List of UnitInfo objects for compatible units
        """
        if not quantity_kind_uri:
            logger.warning("No quantity kind URI provided for unit lookup")
            self._unit_lookup_stats['no_quantity_kind'] += 1
            return []
        
        # Check if QUDT manager is available
        if not self.qudt_manager:
            logger.error("QUDT manager not available, cannot retrieve units")
            return []
        
        # Normalize URIs for comparison
        def normalize_uri(uri):
            """Normalize URI for comparison."""
            if not uri:
                return None
            uri = str(uri).strip()
            # Remove quotes if present
            uri = uri.strip('"\'')
            # Ensure http:// prefix
            if not uri.startswith('http://') and not uri.startswith('https://'):
                # Handle namespace prefixes like "unit:MilliM2"
                if ':' in uri:
                    prefix, local = uri.split(':', 1)
                    if prefix == 'unit':
                        uri = f'http://qudt.org/vocab/unit/{local}'
                    elif prefix == 'qkdv':
                        uri = f'http://qudt.org/vocab/quantitykind/{local}'
            return uri
        
        normalized_default = normalize_uri(default_unit_uri)
        normalized_qk = normalize_uri(quantity_kind_uri)
        
        logger.debug(f"Looking for units with quantity kind: {normalized_qk}")
        logger.debug(f"Default unit (normalized): {normalized_default}")
        
        # Get units from QUDT manager
        try:
            qudt_units = self.qudt_manager.get_units_for_quantity_kind(normalized_qk)
            
            if not qudt_units:
                logger.warning(f"No QUDT units found for quantity kind {normalized_qk}")
                available_qks = list(self.qudt_manager.units_by_quantity_kind.keys())
                logger.debug(f"Available quantity kinds ({len(available_qks)}): {available_qks[:10]}...")
                return []
            
            # Convert to UnitInfo objects
            units = []
            for qudt_unit in qudt_units:
                normalized_unit_uri = normalize_uri(qudt_unit.uri)
                is_default = (normalized_unit_uri == normalized_default)
                
                units.append(UnitInfo(
                    symbol=qudt_unit.symbol,
                    uri=qudt_unit.uri,
                    name=qudt_unit.label,
                    quantity_kind=normalized_qk,
                    is_default=is_default
                ))
                
                if is_default:
                    logger.debug(f"Marked '{str(qudt_unit.symbol)}' as default unit")
            
            logger.debug(f"Found {len(units)} units for quantity kind {normalized_qk}")
            # Track successful lookup
            self._unit_lookup_stats['success'] += 1
            return units

        except Exception as e:
            logger.error(f"Failed to get units for {normalized_qk}: {e}", exc_info=True)
            # Track failed lookup
            self._unit_lookup_stats['failed'] += 1
            return []
    
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

    # ============================================================================
    # STATISTICS METHODS
    # ============================================================================

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get comprehensive GUI schema builder statistics for testing and debugging.

        Returns:
            Dictionary with statistics categories:
            - configuration: Component setup state
            - execution: Schema building statistics
            - health: Component health indicators
            - content: Schema content statistics
        """
        from ...config import Config

        return {
            'configuration': {
                'caching_enabled': Config.USE_SCHEMA_CACHE,
                'sparql_executor_ready': self.sparql is not None,
                'namespace_manager_ready': self.ns is not None,
                'cache_ready': self.cache is not None,
                'qudt_manager_ready': self.qudt_manager is not None
            },
            'execution': {
                'metadata_builds': {
                    'by_class': dict(self._metadata_build_counts),
                    'total_builds': sum(self._metadata_build_counts.values()),
                    'unique_classes': len(self._metadata_build_counts)
                },
                'property_extraction': {
                    'by_class': dict(self._property_extraction_counts),
                    'average_properties_per_class': (
                        sum(self._property_extraction_counts.values()) / len(self._property_extraction_counts)
                        if self._property_extraction_counts else 0
                    )
                },
                'form_groups': {
                    'by_class': dict(self._form_group_stats),
                    'average_groups_per_class': (
                        sum(self._form_group_stats.values()) / len(self._form_group_stats)
                        if self._form_group_stats else 0
                    )
                }
            },
            'health': {
                'unit_lookups': dict(self._unit_lookup_stats),
                'unit_lookup_success_rate': (
                    self._unit_lookup_stats['success'] /
                    (self._unit_lookup_stats['success'] + self._unit_lookup_stats['failed'])
                    if (self._unit_lookup_stats['success'] + self._unit_lookup_stats['failed']) > 0
                    else 0.0
                )
            },
            'content': {
                'widget_type_inferences': {
                    data_type: dict(widget_types)
                    for data_type, widget_types in self._widget_type_inferences.items()
                }
            }
        }

    def get_class_metadata_summary(self) -> Dict[str, Any]:
        """
        Get summary of all class metadata built.

        Returns:
            Summary dictionary with processed classes and key metrics
        """
        return {
            'classes_processed': list(self._metadata_build_counts.keys()),
            'total_properties_extracted': sum(self._property_extraction_counts.values()),
            'total_form_groups': sum(self._form_group_stats.values()),
            'unit_lookup_success_rate': (
                self._unit_lookup_stats['success'] /
                (self._unit_lookup_stats['success'] + self._unit_lookup_stats['failed'])
                if (self._unit_lookup_stats['success'] + self._unit_lookup_stats['failed']) > 0
                else 0.0
            )
        }