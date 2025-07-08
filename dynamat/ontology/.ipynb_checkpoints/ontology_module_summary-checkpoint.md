# DynaMat Ontology Module - Complete System Guide

## File Structure
```
dynamat/ontology/
├── __init__.py
├── manager.py               # OntologyManager - core ontology interface
├── parsers.py               # ImprovedRDFParser - experimental data handling
├── query_builder.py         # DomainQueryBuilder - domain-specific queries  
├── experiment_builder.py    # ExperimentalRDFBuilder - new data creation
└── core/
    └── DynaMat_core.ttl     # Core ontology definition
```

## Core System Architecture

### **Multi-File Experiment Support** 🗂️
The system handles experiments that span multiple TTL files:
- Specimen metadata files (`SPN-AL001_specimen.ttl`)
- Activity files (`SPN-AL001_TEST_2025-01-15.ttl`) 
- Characterization files (`SPN-AL001_characterization.ttl`)
- Automatic correlation and loading of related files

```python
# Load all files for an experiment
parser = ImprovedRDFParser()
experiment_id = parser.load_experiment_files([
    "SPN-AL001_specimen.ttl",
    "SPN-AL001_TEST_2025-01-15.ttl", 
    "SPN-AL001_characterization.ttl"
])

# Get complete experimental data across all files
data = parser.get_experimental_data("SPN-AL001_TEST_001")
```

### **Unique URI Management** 🏷️
Automatic URI generation prevents conflicts when loading multiple experiments:
- **Specimens**: `{base_uri}SPN-{MaterialCode}-{SerialNumber}`
- **Tests**: `{base_uri}SPN-{MaterialCode}-{SerialNumber}_{TestType}_{Date}`
- **Measurements**: `{parent_uri}_{MeasurementName}`
- **Collision Detection**: Automatic handling of duplicate names

```python
# URI generation with collision avoidance
builder = ExperimentalRDFBuilder(experiment_id="SPN-AL001")
specimen_uri = builder.start_specimen_session("SPN-AL001", "Al6061")
# Generates: https://dynamat.utep.edu/specimens/SPN-AL001

test_uri = builder.start_test_session("TEST_001", "SHPBTest", "SPN-AL001")  
# Generates: https://dynamat.utep.edu/specimens/SPN-AL001_TEST_001_2025-01-15
```

### **Single-Call Data Extraction** ⚡
Extract complete measurement sets without nested traversals:

```python
# Get all specimen measurements in one call
measurements = parser.get_specimen_measurements("SPN-AL001")
original_length = measurements['OriginalLength']  # Has value + unit + description

# Get all test results in one call  
results = parser.get_test_results("TEST-001")
stress_data = results['Engineering Stress']  # Complete stress information
```

### **GUI-Agnostic Schema Generation** 📋
Raw schema generation that any GUI framework can interpret:

```python
# Get structured schema (not GUI-specific)
schema = manager.get_class_schema("Specimen")

# Schema organized by property types:
schema = {
    'object_properties': [      # Links to other classes/individuals
        {'name': 'hasMaterial', 'range_class': 'Material', 'available_values': ['Al6061', 'SS316']}
    ],
    'measurement_properties': [ # Value + unit pairs
        {'name': 'OriginalLength', 'available_units': ['mm', 'inch', 'm'], 'data_type': 'float'}
    ],
    'data_properties': [        # Simple data fields
        {'name': 'hasDate', 'data_type': 'date'}
    ]
}

# Get specific data for selectors
selectors = manager.get_selector_data("Specimen")
# Returns: {'hasMaterial': ['Al6061', 'SS316', ...], 'hasSpecimenRole': [...]}

# Get measurement schema
measurements = manager.get_measurement_schema("Specimen")
# Returns: {"OriginalLength": {"property_path": ["hasDimension"], "units": [...]}}
```

**Note**: The actual PyQt6 widget creation happens in `dynamat/gui/forms.py` using the `OntologyFormGenerator` class, which interprets these schemas for PyQt6 widgets.

## Specialized System Components

### **1. OntologyManager (`manager.py`)**
Central interface to the core ontology definition:

```python
manager = get_ontology_manager()

# Get all available materials for ComboBox
materials = manager.get_materials()  # Returns Dict[str, IndividualInfo]

# Get measurement paths for a class (handles nested relationships)
measurements = manager.get_measurement_paths("Specimen")
# Returns: {"OriginalLength": {"property_path": ["hasDimension"], "units": ["mm", "inch"]}}

# Get form schema for automatic GUI generation
schema = manager.get_form_schema("MechanicalTest")
```

### **2. ImprovedRDFParser (`parsers.py`)**
Handles experimental TTL files with multi-file correlation:

```python
parser = ImprovedRDFParser()

# Load multiple related files
experiment_id = parser.load_experiment_files([
    "specimen.ttl", "test.ttl", "characterization.ttl"
])

# Extract complete experimental data
data = parser.get_experimental_data("TEST-001")
print(f"Specimen: {data.specimen_id}")
print(f"Measurements: {data.measurements}")

# Export structured summaries
specimen_summary = parser.export_specimen_summary("SPN-AL001")
test_summary = parser.export_test_summary("TEST-001")
```

### **3. DomainQueryBuilder (`query_builder.py`)**
Domain-specific queries without SPARQL knowledge:

```python
builder = DomainQueryBuilder(graph)

# Find tests with specific criteria
tests = builder.find_tests(
    material="Al6061", 
    strain_rate_min=1000,
    test_type="SHPBTest"
)

# Compare materials across measurements
comparison = builder.compare_materials(
    materials=["Al6061", "SS316"],
    measurement_name="Engineering Stress"
)

# Get complete specimen history
history = builder.get_specimen_history("SPN-AL001")
# Returns: material, structure, processing_steps, tests_performed, measurements
```

### **4. ExperimentalRDFBuilder (`experiment_builder.py`)**
Creates new experimental data with temporal RDF workflow:

```python
# Start experiment session
builder = ExperimentalRDFBuilder(experiment_id="SPN-AL001")
specimen_uri = builder.start_specimen_session("SPN-AL001", "Al6061")

# Add measurements from GUI input
builder.add_measurement(
    MeasurementEntry(
        name="OriginalLength", 
        value=10.0, 
        unit="mm",
        property_path=["hasDimension"]
    ),
    target_id="SPN-AL001"
)

# Add test session
test_uri = builder.start_test_session("TEST-001", "SHPBTest", "SPN-AL001")

# Validate and finalize
validation = builder.validate_completeness()
if validation['is_complete']:
    builder.finalize_experiment(Path("experiment.ttl"))
```

## Advanced System Features

### **Backward Compatibility & Gap Filling** 🔄
Handle ontology evolution and update existing files:

```python
# Detect missing properties in existing experiments
missing = parser.detect_missing_properties(ontology_manager)
# Returns: {experiment_id: {entity_id: [missing_properties]}}

# Get suggestions for updates
suggestions = parser.suggest_property_updates("SPN-AL001", ontology_manager)
# Returns: {'critical': [...], 'recommended': [...], 'optional': [...]}

# Update experiments with new properties
updates = {
    "SPN-AL001": {"hasProcessingTemperature": 450, "hasUnits": "dyn:DegreesCelsius"}
}
success = parser.update_experiment_with_missing_properties("SPN-AL001", updates)
```

### **Data Validation Workflow** ✅
Structured validation approach supporting the GUI workflow:

```python
# 1. During data entry: Basic completeness
validation = builder.validate_completeness()
if not validation['is_complete']:
    show_warning(validation['missing_fields'])

# 2. Before finalization: Full validation
if validation['is_complete']:
    # SHACL validation would happen here
    builder.finalize_experiment(output_path)

# 3. Data quality checks
completeness = query_builder.get_data_completeness("TEST-001")
invalid_tests = query_builder.find_invalid_tests()
```

### **Template Integration** 📄
Reusable configuration management:

```python
# Templates stored separately and referenced
template = load_template("SHPB_setup_steel_bars.ttl")
builder.apply_template(template)

# Templates for common setups:
# - Equipment configurations
# - Material definitions  
# - Standard testing procedures
# - Processing histories
```

## System Workflow Integration

### **Complete GUI → TTL Workflow**
```python
# 1. Start experiment (GUI initialization)
builder = ExperimentalRDFBuilder()
specimen_uri = builder.start_specimen_session("SPN-AL001", "Al6061")

# 2. Schema generation (ontology module)
schema = manager.get_class_schema("Specimen")

# 3. Form generation (GUI module) 
from dynamat.gui.forms import OntologyFormGenerator
form_generator = OntologyFormGenerator()
specimen_form = form_generator.create_class_form("Specimen", on_change_callback)

# 4. Data entry (user fills forms, callbacks update builder)
def on_form_change(widget_type, property_name, value):
    if widget_type == 'measurement':
        builder.add_measurement(
            MeasurementEntry(property_name, value['value'], value['unit'], ["hasDimension"]),
            "SPN-AL001"
        )
    elif widget_type == 'selector':
        builder.add_selector_choice("SPN-AL001", property_name, value)

# 5. Test session
test_uri = builder.start_test_session("TEST-001", "SHPBTest", "SPN-AL001")
builder.add_test_condition("StrikerVelocity", 15.5)

# 6. Validation and finalization
if builder.validate_completeness()['is_complete']:
    builder.finalize_experiment(Path("SPN-AL001_TEST_001.ttl"))
```

### **Multi-Experiment Analysis**
```python
# Load multiple experiments
parser = ImprovedRDFParser()
for exp_files in experiment_file_groups:
    parser.load_experiment_files(exp_files)

# Query across all loaded experiments
all_al6061_tests = query_builder.find_tests(material="Al6061")
strength_comparison = query_builder.compare_materials(
    materials=["Al6061", "SS316"], 
    measurement_name="Engineering Stress"
)
```

## Key System Benefits

✅ **Multi-file experiment handling** - Correlates specimen + activity + data files  
✅ **Unique URI management** - Prevents conflicts when loading multiple experiments  
✅ **Single-call data extraction** - No nested traversals required  
✅ **GUI-agnostic schemas** - Supports any GUI framework (PyQt6, Tkinter, web, etc.)  
✅ **Domain-specific queries** - No SPARQL knowledge required  
✅ **Temporal RDF building** - GUI → validation → final TTL workflow  
✅ **Backward compatibility** - Handle ontology evolution gracefully  
✅ **Template support** - Reusable configurations for common setups  
✅ **Validation workflow** - Structured approach supporting GUI development  
✅ **Modular architecture** - Clean separation between ontology and GUI concerns  

## Implementation Notes

The system provides clean separation between:
- **Ontology Module**: Core ontology operations (reading, querying, schema generation)
- **GUI Module**: Widget creation and form generation (`dynamat/gui/forms.py`)
- **Data Module**: Experimental data creation and management
- **Analysis Module**: Domain-specific queries and comparisons

**Module Responsibilities:**
- `ontology/manager.py`: Provides GUI-agnostic schemas and ontology access
- `gui/forms.py`: Converts schemas to PyQt6 widgets and forms  
- `ontology/parsers.py`: Reads experimental TTL files with multi-file support
- `ontology/query_builder.py`: Domain queries without SPARQL exposure
- `ontology/experiment_builder.py`: Creates new experimental data with validation

This architecture supports both single-experiment focused work and multi-experiment comparative analysis while maintaining data integrity and framework-agnostic design.