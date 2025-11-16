# DynaMat Ontology Module

The `dynamat.ontology` module is the semantic foundation of the DynaMat Platform. It manages RDF ontology data, provides form-building metadata for the GUI, executes SPARQL queries, validates data against SHACL shapes, and handles configuration templates—all while maintaining FAIR data principles.

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Key Components](#key-components)
- [Quick Start](#quick-start)
- [TTL File Organization](#ttl-file-organization)
- [API Reference](#api-reference)
- [Design Patterns](#design-patterns)
- [Working with the Module](#working-with-the-module)

---

## Overview

### Purpose

The ontology module enables **ontology-driven GUI design**: instead of hard-coding forms and data structures, the GUI reads RDF ontology definitions and automatically generates appropriate interfaces. Change the ontology, and the GUI adapts.

### Core Capabilities

- **Form Metadata Generation**: Extract GUI schemas from ontology annotations
- **SPARQL Querying**: High-level domain queries without writing SPARQL
- **SHACL Validation**: Ensure data quality and consistency
- **Template Management**: Reusable configuration templates
- **QUDT Integration**: Units of measurement support
- **Performance Caching**: Multi-layer caching for fast operations

### FAIR Data Principles

The module is designed around FAIR principles:

- **Findable**: Semantic metadata makes all data queryable via SPARQL
- **Accessible**: Standard RDF formats (Turtle/TTL) readable by any RDF tool
- **Interoperable**: Uses standard vocabularies (QUDT, OWL, SHACL)
- **Reusable**: Templates and clear provenance enable data reuse

---

## Architecture

### Directory Structure

```
dynamat/ontology/
├── __init__.py                      # Public API exports
├── manager.py                       # OntologyManager (main entry point)
├── query_builder.py                 # Domain-specific query API
├── validator.py                     # SHACL validation
├── template_manager.py              # Configuration templates
├── temp_handler.py                  # Temporary instance editing
│
├── core/                            # Core ontology loading
│   ├── ontology_loader.py           # TTL file loading with dependency ordering
│   ├── namespace_manager.py         # RDF namespace management
│   └── DynaMat_core.ttl            # Core ontology definition
│
├── query/                           # Query infrastructure
│   ├── sparql_executor.py           # SPARQL execution engine
│   └── domain_queries.py            # High-level domain queries
│
├── schema/                          # GUI schema generation
│   └── gui_schema_builder.py       # Form metadata extraction
│
├── cache/                           # Performance caching
│   └── metadata_cache.py            # Multi-layer caching
│
├── qudt/                            # Units of measurement
│   └── qudt_manager.py              # QUDT ontology integration
│
├── class_properties/                # Property definitions by class
│   ├── specimen_class.ttl
│   ├── mechanical_testing_class.ttl
│   ├── material_class.ttl
│   ├── simulation_class.ttl
│   └── information_object_class.ttl
│
├── class_individuals/               # Predefined instances
│   ├── material_individuals.ttl     # Al6061-T6, SS316L, etc.
│   ├── mechanical_testing_individuals.ttl
│   ├── specimen_individuals.ttl
│   ├── simulation_individuals.ttl
│   ├── information_object_individuals.ttl
│   └── strain_guages_individuals.ttl
│
├── shapes/                          # SHACL validation shapes
│   ├── core_shapes.ttl
│   ├── specimen_shapes.ttl
│   ├── mechanical_testing_shapes.ttl
│   ├── material_shapes.ttl
│   ├── simulation_shapes.ttl
│   └── information_object_shapes.ttl
│
├── constraints/                     # GUI behavior constraints
│   ├── gui_constraint_vocabulary.ttl
│   └── gui_specimen_rules.ttl
│
└── templates/                       # Reusable configurations
    ├── equipment/
    │   └── SHPB_compression_C350.ttl
    ├── materials/
    ├── structures/
    ├── processes/
    └── tests/
```

### Component Relationships

```
┌─────────────────────────────────────────────────────────────────┐
│                      OntologyManager                            │
│           (Central coordinator and public API)                  │
└──────────┬──────────────────────────────────┬──────────────────┘
           │                                  │
           ▼                                  ▼
┌──────────────────────┐          ┌──────────────────────┐
│  OntologyLoader      │          │ GUISchemaBuilder     │
│  (TTL file loading)  │          │ (Form metadata)      │
└──────────────────────┘          └──────────────────────┘
           │                                  │
           ▼                                  ▼
┌──────────────────────┐          ┌──────────────────────┐
│  NamespaceManager    │          │  QUDTManager         │
│  (RDF namespaces)    │          │  (Units)             │
└──────────────────────┘          └──────────────────────┘
           │
           ▼
┌──────────────────────┐          ┌──────────────────────┐
│  SPARQLExecutor      │◄─────────│  DomainQueries       │
│  (Query engine)      │          │  (High-level API)    │
└──────────────────────┘          └──────────────────────┘
           │
           ▼
┌──────────────────────┐
│  MetadataCache       │
│  (Performance)       │
└──────────────────────┘

Specialized Components (created via factory methods):
┌──────────────────────┐  ┌──────────────────────┐  ┌──────────────────────┐
│  SHACLValidator      │  │  TemplateManager     │  │  TempInstanceHandler │
└──────────────────────┘  └──────────────────────┘  └──────────────────────┘
```

---

## Key Components

### 1. OntologyManager

**The central hub for all ontology operations.**

```python
from dynamat.ontology import OntologyManager

manager = OntologyManager()
```

**Primary Responsibilities:**
- Coordinates all specialized components
- Provides main API for GUI form building
- Manages ontology loading and reloading
- Offers factory methods for dependent components

**Main Methods:**
```python
# Form building (primary GUI entry point)
class_metadata = manager.get_class_metadata_for_form("dyn:Specimen")

# Instance queries
materials = manager.get_all_individuals("dyn:Material")

# Statistics
stats = manager.get_statistics()

# Maintenance
manager.reload_ontology()
manager.clear_caches()

# Factory methods
validator = manager.create_validator()
template_mgr = manager.create_template_manager()
query_builder = manager.create_query_builder()
temp_handler = manager.create_temp_handler()
```

---

### 2. GUISchemaBuilder

**Generates GUI form schemas from ontology annotations.**

**Data Classes:**

```python
@dataclass
class PropertyMetadata:
    """Enhanced metadata for a single property"""
    uri: str                        # Property URI
    name: str                       # Property name
    display_name: str               # Human-readable label
    description: str                # Help text
    data_type: str                  # xsd:string, xsd:double, etc.
    range_class: Optional[str]      # For object properties
    form_group: str                 # Section grouping
    display_order: int              # Order within section
    group_order: int                # Section ordering
    is_required: bool               # Required field?
    widget_type: Optional[str]      # Explicit widget type
    quantity_kind: Optional[str]    # QUDT quantity kind
    compatible_units: List[UnitInfo]  # Available units
    default_unit: Optional[str]     # Default unit
    # ... validation fields ...

@dataclass
class ClassMetadata:
    """Metadata for a class with organized properties"""
    uri: str                        # Class URI
    name: str                       # Class name
    label: str                      # Human-readable label
    description: str                # Description
    parent_classes: List[str]       # Inheritance hierarchy
    properties: List[PropertyMetadata]  # All properties
    form_groups: Dict[str, List[PropertyMetadata]]  # Grouped properties

    def get_required_properties(self) -> List[PropertyMetadata]
    def get_ordered_groups(self) -> List[Tuple[str, int, List[PropertyMetadata]]]
```

**Widget Type Inference:**

The builder automatically determines widget types from property definitions:

| Property Definition | Widget Type |
|---------------------|-------------|
| `xsd:string` | `line_edit` |
| `xsd:string` + `hasValidValues` | `combo` |
| `xsd:integer` | `spinbox` |
| `xsd:double` | `double_spinbox` |
| `xsd:double` + `qudt:hasQuantityKind` | `unit_value` |
| `xsd:boolean` | `checkbox` |
| `xsd:date` | `date` |
| `owl:ObjectProperty` + `owl:FunctionalProperty` | `object_combo` |
| `owl:ObjectProperty` (non-functional) | `object_multi_select` |

---

### 3. DynaMatQueryBuilder

**High-level query API that hides SPARQL complexity.**

```python
from dynamat.ontology import create_query_builder

query_builder = create_query_builder(manager)
```

**Search Criteria Classes:**

```python
@dataclass
class SpecimenSearchCriteria:
    material_name: Optional[str] = None
    structure_type: Optional[str] = None
    shape: Optional[str] = None
    batch_id: Optional[str] = None
    creation_date_from: Optional[str] = None
    creation_date_to: Optional[str] = None
    diameter_min: Optional[float] = None
    diameter_max: Optional[float] = None
    length_min: Optional[float] = None
    length_max: Optional[float] = None

@dataclass
class TestSearchCriteria:
    specimen_id: Optional[str] = None
    material_name: Optional[str] = None
    test_type: Optional[str] = None
    date_from: Optional[str] = None
    date_to: Optional[str] = None
    strain_rate_min: Optional[float] = None
    strain_rate_max: Optional[float] = None
    temperature_min: Optional[float] = None
    temperature_max: Optional[float] = None
    operator: Optional[str] = None
```

**Query Methods:**

```python
# Material queries
materials = query_builder.get_available_materials()
material = query_builder.find_material_by_property("hasName", "Al6061-T6")

# Specimen queries
specimens = query_builder.find_specimens(
    SpecimenSearchCriteria(
        material_name="Al6061-T6",
        shape="Cylindrical",
        diameter_min=5.0,
        diameter_max=10.0
    )
)

# Test queries
tests = query_builder.find_tests(
    TestSearchCriteria(
        specimen_id="SPN-AL6061-001",
        test_type="SHPBCompression",
        date_from="2025-01-01"
    )
)

# Analysis queries
comparison = query_builder.compare_materials(
    materials=["Al6061-T6", "SS316L"],
    measurement_name="hasYieldStress"
)

completeness = query_builder.get_data_completeness("dyn:SPN_AL6061_001")
```

---

### 4. SHACLValidator

**Validates RDF data against SHACL shapes for quality assurance.**

```python
from dynamat.ontology import create_validator

validator = create_validator(manager)
```

**Validation Workflow:**

```python
# Validate entire graph
report = validator.validate_graph(data_graph)

# Validate specific instance
report = validator.validate_instance("dyn:SPN_AL6061_001", data_graph)

# Validate TTL file
report = validator.validate_file("specimens/SPN-AL6061-001/specimen.ttl")

# Check results
if not report.conforms:
    for result in report.results:
        print(f"{result.severity}: {result.message}")
        print(f"  Focus: {result.focus_node}")
        print(f"  Path: {result.result_path}")
```

**Validation Result Data:**

```python
@dataclass
class ValidationResult:
    severity: ValidationSeverity  # INFO, WARNING, VIOLATION, ERROR
    focus_node: str               # Node that failed validation
    result_path: str              # Property path
    value: Optional[str]          # Value that failed
    message: str                  # Human-readable message
    source_constraint: str        # Which constraint failed
    source_shape: str             # Which SHACL shape

@dataclass
class ValidationReport:
    conforms: bool                # Overall pass/fail
    results: List[ValidationResult]
    total_results: int
    violations: int
    warnings: int
    infos: int
    graph_valid: bool
```

---

### 5. TemplateManager

**Manages reusable configuration templates.**

```python
from dynamat.ontology import create_template_manager

template_mgr = create_template_manager(manager)
```

**Template Operations:**

```python
# List available templates
templates = template_mgr.get_available_templates(category="equipment")

# Load template
metadata, values = template_mgr.load_template("SHPB Standard Setup")

# Apply template to instance
template_mgr.apply_template(
    template_name="SHPB Standard Setup",
    instance_uri="dyn:Test_001",
    overrides={"hasStrikerVelocity": 18.5}
)

# Save new template
template_mgr.save_template(
    name="My Custom Setup",
    category="equipment",
    target_class="dyn:SHPBCompression",
    values=configuration_dict
)
```

---

### 6. QUDTManager

**Manages QUDT units of measurement with persistent caching.**

```python
# Integrated into OntologyManager, accessed via GUISchemaBuilder
units = qudt_manager.get_units_for_quantity_kind("http://qudt.org/vocab/quantitykind/Length")
unit_info = qudt_manager.get_unit_by_uri("http://qudt.org/vocab/unit/MilliM")
```

**Features:**
- Downloads QUDT ontology from online source
- Caches to disk (~/.dynamat/qudt_cache/)
- 7-day cache freshness
- Provides sorted, deduplicated unit lists

---

## Quick Start

### Basic Usage

```python
from dynamat.ontology import OntologyManager

# Initialize
manager = OntologyManager()

# Get form metadata for GUI building
class_metadata = manager.get_class_metadata_for_form("dyn:Specimen")

# Access properties
for prop in class_metadata.properties:
    print(f"{prop.display_name}: {prop.data_type}")

# Get organized groups
for group_name, order, properties in class_metadata.get_ordered_groups():
    print(f"\n{group_name}:")
    for prop in properties:
        print(f"  - {prop.display_name}")

# Query individuals
materials = manager.get_all_individuals("dyn:Material")
for material in materials:
    print(material)
```

### Querying Data

```python
from dynamat.ontology import OntologyManager, create_query_builder, SpecimenSearchCriteria

manager = OntologyManager()
query_builder = create_query_builder(manager)

# Search specimens
criteria = SpecimenSearchCriteria(
    material_name="Al6061-T6",
    shape="Cylindrical"
)
specimens = query_builder.find_specimens(criteria)

# Get specimen details
for specimen in specimens:
    details = query_builder.get_specimen_details(specimen['uri'])
    print(f"{details['specimen_id']}: {details['material']}")
```

### Validation

```python
from dynamat.ontology import OntologyManager, create_validator
from rdflib import Graph

manager = OntologyManager()
validator = create_validator(manager)

# Load specimen data
data_graph = Graph()
data_graph.parse("specimens/SPN-AL6061-001/specimen.ttl", format="turtle")

# Validate
report = validator.validate_graph(data_graph)

if report.conforms:
    print("✓ All validation passed")
else:
    print(f"✗ {report.violations} violations found:")
    for result in report.results:
        if result.severity == ValidationSeverity.VIOLATION:
            print(f"  - {result.message}")
```

---

## TTL File Organization

### Core Ontology (`core/DynaMat_core.ttl`)

Defines base classes and annotation properties:

```turtle
dyn:Specimen rdf:type owl:Class ;
    rdfs:subClassOf dyn:PhysicalObject ;
    rdfs:label "Specimen"@en ;
    rdfs:comment "Physical sample prepared for testing"@en .

# GUI annotation properties
dyn:hasDisplayName rdf:type owl:AnnotationProperty .
dyn:hasFormGroup rdf:type owl:AnnotationProperty .
dyn:hasDisplayOrder rdf:type owl:AnnotationProperty .
```

### Class Properties (`class_properties/*.ttl`)

One file per major class with all property definitions:

```turtle
# specimen_class.ttl
dyn:hasOriginalLength rdf:type owl:DatatypeProperty, owl:FunctionalProperty ;
    rdfs:domain dyn:Specimen ;
    rdfs:range xsd:double ;
    qudt:hasQuantityKind qkdv:Length ;

    # GUI annotations
    dyn:hasDisplayName "Original Length (mm)" ;
    dyn:hasFormGroup "GeometryDimensions" ;
    dyn:hasGroupOrder 2 ;
    dyn:hasDisplayOrder 3 ;
    dyn:hasDefaultUnit "unit:MilliM" ;

    rdfs:label "Original Length"@en ;
    rdfs:comment "Initial length of specimen before testing"@en .
```

### Class Individuals (`class_individuals/*.ttl`)

Predefined instances users can reference:

**Material Individuals:**
```turtle
# material_individuals.ttl
dyn:Al6061_T6 rdf:type owl:NamedIndividual, dyn:AluminumAlloy ;
    rdfs:label "Al6061-T6"@en ;
    dyn:hasName "Aluminum 6061-T6"@en ;
    dyn:hasMaterialCode "AL6061"@en ;
    dyn:hasNominalDensity 2700.0 ;  # kg/m³
    dyn:hasYoungsModulus 68.9 ;     # GPa
    dyn:hasPoissonsRatio 0.33 .
```

**Batch Individuals (Nested Population Pattern):**

Batch individuals can store manufacturing data that auto-populates specimen forms:

```turtle
# specimen_individuals.ttl
dyn:Batch_AL001_CastMachined rdf:type owl:NamedIndividual, dyn:SpecimenBatchID ;
    rdfs:label "Batch AL001-2024-01 (Cast + Machined)"@en ;
    dyn:hasName "Aluminum A356 Batch 2024-01 (Cast then Machined)"@en ;
    dyn:hasBatchID "BATCH-AL001-2024-01"@en ;

    # Core manufacturing data
    dyn:hasMaterial dyn:A356 ;
    dyn:hasCreationDate "2024-01-15"^^xsd:date ;

    # Multi-select manufacturing methods
    dyn:hasManufacturingMethod dyn:Casting, dyn:Machining ;

    # Process-specific parameters
    dyn:hasMetalTemperature 700.0 ;
    dyn:hasMoldTemperature 200.0 ;
    dyn:hasCastCoolingDuration 30.0 ;
    dyn:hasMachiningTolerance 0.1 .
```

When a user selects this batch, all manufacturing fields auto-populate and become read-only.

### SHACL Shapes (`shapes/*.ttl`)

Validation rules:

```turtle
# specimen_shapes.ttl
dyn:SpecimenShape a sh:NodeShape ;
    sh:targetClass dyn:Specimen ;

    sh:property [
        sh:path dyn:hasSpecimenID ;
        sh:minCount 1 ;              # Required
        sh:maxCount 1 ;              # Single value
        sh:datatype xsd:string ;
        sh:pattern "^SPN-[A-Z0-9]+-[0-9]{3}$" ;  # Format validation
    ] ;

    sh:property [
        sh:path dyn:hasOriginalDiameter ;
        sh:datatype xsd:double ;
        sh:minExclusive 0.0 ;        # Must be positive
    ] .
```

### Templates (`templates/*/*.ttl`)

Reusable configurations:

```turtle
# templates/equipment/SHPB_compression_C350.ttl
template:shpb_standard_setup rdf:type dyn:Template ;
    dyn:hasName "SHPB Standard C350 Setup" ;
    dyn:hasCategory "equipment" ;
    dyn:hasTargetClass dyn:SHPBCompression .

template:shpb_c350_example rdf:type dyn:SHPBCompression ;
    dyn:hasStrikerBar dyn:StrikerBar_C350_2ft ;
    dyn:hasIncidentBar dyn:IncidentBar_C350_6ft ;
    dyn:hasStrikerVelocity 15.0 ;
    dyn:hasSamplingRate 2000000.0 .
```

---

## API Reference

### Public API (`__init__.py`)

```python
from dynamat.ontology import (
    # Main entry point
    OntologyManager,

    # Factory functions
    create_query_builder,
    create_validator,
    create_template_manager,

    # Data classes
    PropertyMetadata,
    ClassMetadata,
    UnitInfo,
    ValidationReport,
    ValidationResult,
    SpecimenSearchCriteria,
    TestSearchCriteria,

    # Enums
    ValidationSeverity,
)
```

### OntologyManager API

```python
class OntologyManager:
    def __init__(self):
        """Initialize with automatic ontology loading"""

    # Primary API for GUI
    def get_class_metadata_for_form(self, class_uri: str) -> ClassMetadata:
        """Get complete form metadata for a class"""

    def get_all_individuals(self, class_uri: str) -> List[str]:
        """Get all instances of a class"""

    # Ontology management
    def reload_ontology(self) -> None:
        """Reload ontology from disk"""

    def clear_caches(self) -> None:
        """Clear all caches"""

    def get_statistics(self) -> Dict[str, Any]:
        """Get manager statistics"""

    # Factory methods
    def create_validator(self) -> SHACLValidator
    def create_template_manager(self) -> TemplateManager
    def create_query_builder(self) -> DynaMatQueryBuilder
    def create_temp_handler(self) -> TempInstanceHandler
```

### DynaMatQueryBuilder API

```python
class DynaMatQueryBuilder:
    # Materials
    def get_available_materials(self) -> List[Dict]
    def find_material_by_property(self, property_name: str, value: str) -> Optional[Dict]

    # Specimens
    def find_specimens(self, criteria: SpecimenSearchCriteria) -> List[Dict]
    def get_specimen_details(self, specimen_uri: str) -> Dict

    # Tests
    def find_tests(self, criteria: TestSearchCriteria) -> List[Dict]
    def get_test_results(self, test_uri: str) -> Dict

    # Analysis
    def compare_materials(self, materials: List[str], measurement_name: str) -> Dict
    def get_data_completeness(self, entity_uri: str) -> Dict
    def find_invalid_tests(self) -> List[Dict]
```

### SHACLValidator API

```python
class SHACLValidator:
    def validate_graph(self, data_graph: Graph) -> ValidationReport
    def validate_instance(self, instance_uri: str, data_graph: Graph) -> ValidationReport
    def validate_file(self, file_path: str) -> ValidationReport
    def add_custom_rule(self, name: str, validation_function: Callable) -> None
    def reload_shapes(self) -> None
```

---

## Design Patterns

### 1. Dependency Injection

Components receive dependencies via constructor:

```python
class GUISchemaBuilder:
    def __init__(self, sparql_executor, namespace_manager, cache, qudt_manager):
        self.sparql = sparql_executor
        self.ns = namespace_manager
        self.cache = cache
        self.qudt = qudt_manager
```

### 2. Factory Pattern

OntologyManager provides factory methods:

```python
validator = manager.create_validator()
query_builder = manager.create_query_builder()
```

### 3. Caching Pattern

Multi-layer caching for performance:
- Class/property metadata (in-memory)
- SPARQL query results (in-memory)
- QUDT units (disk-based, 7-day freshness)

### 4. Builder Pattern

GUISchemaBuilder builds complex metadata:

```python
metadata = ClassMetadata(
    uri=class_uri,
    properties=properties,
    form_groups=organized_groups
)
```

---

## Working with the Module

### Adding New Properties

1. Decide which class it belongs to
2. Add to appropriate file in `class_properties/`
3. Choose single-value or multi-value behavior
4. Include GUI annotations:

**Single-Value Property (Functional):**
```turtle
dyn:hasSurfaceRoughness rdf:type owl:DatatypeProperty, owl:FunctionalProperty ;
    rdfs:domain dyn:Specimen ;
    rdfs:range xsd:double ;
    qudt:hasQuantityKind qkdv:Length ;
    dyn:hasDisplayName "Surface Roughness (Ra)" ;
    dyn:hasFormGroup "Manufacturing" ;
    dyn:hasGroupOrder 4 ;
    dyn:hasDisplayOrder 2 ;
    dyn:hasDefaultUnit "unit:MicroM" ;
    rdfs:label "Surface Roughness"@en .
```

**Multi-Value Property (Non-Functional):**

For properties that should allow multiple selections (e.g., sequential manufacturing processes), omit `owl:FunctionalProperty`:

```turtle
dyn:hasManufacturingMethod rdf:type owl:ObjectProperty ;
    rdfs:domain dyn:Specimen ;
    rdfs:range dyn:ManufacturingMethod ;
    dyn:hasDisplayName "Manufacturing Method" ;
    dyn:hasFormGroup "Manufacturing" ;
    dyn:hasGroupOrder 4 ;
    dyn:hasDisplayOrder 1 ;
    rdfs:label "Manufacturing Method"@en ;
    rdfs:comment "Manufacturing method(s) used to create the specimen. Multiple methods can be selected for specimens with sequential processing steps (e.g., casting followed by machining)."@en .
```

The GUI automatically creates a multi-select widget (QListWidget) for non-functional ObjectProperties.

5. Update SHACL shapes if validation needed:

```turtle
sh:property [
    sh:path dyn:hasSurfaceRoughness ;
    sh:datatype xsd:double ;
    sh:minExclusive 0.0 ;
] .
```

6. Reload ontology: `manager.reload_ontology()`

### Creating Templates

1. Create TTL file in `templates/{category}/`
2. Define template metadata and example:

```turtle
template:my_setup rdf:type dyn:Template ;
    dyn:hasName "My Setup" ;
    dyn:hasCategory "equipment" ;
    dyn:hasTargetClass dyn:QuasistaticTest .

template:my_setup_example rdf:type dyn:QuasistaticTest ;
    # ... property values ...
```

3. Template becomes available via TemplateManager

### Custom Validation Rules

Add custom validation beyond SHACL:

```python
def validate_diameter_length_ratio(instance_uri, graph):
    """Custom rule: diameter/length should be < 0.8"""
    # Extract values
    diameter = get_property_value(graph, instance_uri, "hasOriginalDiameter")
    length = get_property_value(graph, instance_uri, "hasOriginalLength")

    if diameter and length:
        ratio = diameter / length
        if ratio >= 0.8:
            return ValidationResult(
                severity=ValidationSeverity.WARNING,
                focus_node=instance_uri,
                message=f"Diameter/length ratio {ratio:.2f} is high"
            )
    return None

validator.add_custom_rule("diameter_length_ratio", validate_diameter_length_ratio)
```

---

## Performance Considerations

### Caching Strategy

The module uses three cache layers:

1. **Metadata Cache** (in-memory): Class and property metadata
2. **Query Cache** (in-memory): SPARQL query results
3. **QUDT Cache** (disk): Units ontology (~/.dynamat/qudt_cache/)

**Cache Management:**

```python
# Clear all caches
manager.clear_caches()

# Get cache statistics
stats = manager.get_statistics()
print(f"Cache hit ratio: {stats['cache_hit_ratio']:.2%}")
```

### Best Practices

1. **Reuse OntologyManager**: Create once, use throughout application lifetime
2. **Use Query Builder**: Higher-level API is optimized and cached
3. **Batch Queries**: Query multiple entities at once when possible
4. **Clear Caches Selectively**: Only reload/clear when ontology changes

---

## Troubleshooting

### Common Issues

**Issue**: Forms not updating after ontology changes
**Solution**: Call `manager.reload_ontology()` and `manager.clear_caches()`

**Issue**: QUDT units not loading
**Solution**: Check internet connection, or force rebuild: `qudt_manager.rebuild_cache()`

**Issue**: Validation failing unexpectedly
**Solution**: Check SHACL shapes in `shapes/` directory, ensure PyShacl is installed

**Issue**: Query returning no results
**Solution**: Check URIs (use full URIs or proper prefixes), verify data is loaded

---

## Dependencies

- **rdflib**: RDF graph handling
- **pyshacl** (optional but recommended): Full SHACL validation support

---

## Further Reading

- [QUDT Units](http://www.qudt.org/)
- [W3C SHACL Specification](https://www.w3.org/TR/shacl/)
- [RDFLib Documentation](https://rdflib.readthedocs.io/)
- [OWL 2 Primer](https://www.w3.org/TR/owl2-primer/)
