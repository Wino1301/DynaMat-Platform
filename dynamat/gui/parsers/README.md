# GUI Parsers Module

This module handles writing RDF instances and individuals to TTL files with automatic unit conversion and SHACL validation.

## Architecture Overview

```
InstanceWriter                    IndividualWriter
    |                                    |
    +---> Unit Conversion (QUDT)         +---> Append Mode
    |                                    |
    +---> SHACL Validation               +---> Type Inference
    |                                    |
    +---> TTL Serialization              +---> TTL Serialization
```

## Module Exports

```python
from dynamat.gui.parsers import (
    InstanceWriter,      # Write instances with unit conversion and validation
    IndividualWriter,    # Write/update/delete individuals in append mode
)
```

---

## Classes

### InstanceWriter

Writes GUI form data to TTL files with automatic QUDT unit conversion and SHACL validation. This is the primary class for saving specimen, test, and analysis data.

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `ontology_manager` | OntologyManager | required | Provides namespace access |
| `qudt_manager` | QUDTManager | None | Enables unit conversion |

**Key Methods:**

- `write_instance(form_data, class_uri, instance_id, output_path, ...)` - Write single instance
- `create_single_instance(graph, form_data, class_uri, instance_id)` - Add instance to existing graph
- `create_instances_batch(instances, output_graph)` - Create multiple instances in one graph
- `write_multi_instance_file(instances, output_path, ...)` - Write batch to single TTL file
- `update_instance(instance_uri, updates, ttl_file, ...)` - Update existing instance

**Example:**

```python
from dynamat.ontology import OntologyManager
from dynamat.ontology.qudt import QUDTManager
from dynamat.gui.parsers import InstanceWriter
from pathlib import Path

# Initialize
ontology = OntologyManager()
qudt = QUDTManager()
writer = InstanceWriter(ontology, qudt)

# Write single instance
data = {
    'dyn:hasOriginalLength': {'value': 10.0, 'unit': 'unit:IN', 'reference_unit': 'unit:MilliM'},
    'dyn:hasSpecimenID': 'DYNML-AL6061-001',
    'dyn:hasMaterial': 'dyn:Al6061_T6'
}

path, validation = writer.write_instance(
    form_data=data,
    class_uri='dyn:Specimen',
    instance_id='DYNML_AL6061_001',
    output_path=Path('user_data/specimens/DYNML-AL6061-001/specimen.ttl')
)

if path:
    print(f"Saved to {path}")
if validation.has_any_issues():
    print(f"Warnings: {validation.get_summary()}")
```

---

### IndividualWriter

Writes NamedIndividuals to TTL files in append mode. Unlike InstanceWriter (which overwrites files), this appends new individuals to existing TTL files.

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `ontology_manager` | OntologyManager | required | Provides namespace access |

**Key Methods:**

- `write_individual(class_uri, individual_uri, form_data, output_path)` - Append new individual
- `update_individual(individual_uri, form_data, output_path)` - Update existing individual
- `delete_individual(individual_uri, output_path)` - Remove individual from file

**Example:**

```python
from dynamat.ontology import OntologyManager
from dynamat.gui.parsers import IndividualWriter
from pathlib import Path

# Initialize
ontology = OntologyManager()
writer = IndividualWriter(ontology)

# Write new material individual
data = {
    'rdfs:label': 'Custom Aluminum Alloy',
    'dyn:hasDensity': 2700.0,
    'dyn:hasYoungsModulus': 70e9
}

path = writer.write_individual(
    class_uri='dyn:Material',
    individual_uri='dyn:CustomAl_001',
    form_data=data,
    output_path=Path('user_data/individuals/materials.ttl')
)

# Update existing individual
writer.update_individual(
    individual_uri='dyn:CustomAl_001',
    form_data={'dyn:hasDensity': 2710.0},
    output_path=path
)

# Delete individual
writer.delete_individual(
    individual_uri='dyn:CustomAl_001',
    output_path=path
)
```

---

## Unit Conversion Strategy

InstanceWriter performs automatic unit conversion during save operations:

1. **UnitValueWidget provides**: `{'value': X, 'unit': user_unit, 'reference_unit': storage_unit}`
2. **If units differ**: Convert using QUDTManager from user's unit to ontology-defined storage unit
3. **Store**: Only the converted numeric value (xsd:double) in TTL
4. **Unit preservation**: Unit information is defined in the ontology via `dyn:hasUnit`

```python
# User enters 10.0 inches, ontology specifies storage in millimeters
input_data = {
    'dyn:hasOriginalLength': {
        'value': 10.0,
        'unit': 'unit:IN',
        'reference_unit': 'unit:MilliM'
    }
}

# Output in TTL (converted to millimeters):
# dyn:SPECIMEN_001 dyn:hasOriginalLength "254.0"^^xsd:double .
```

---

## Validation Workflow

InstanceWriter validates RDF graphs using SHACL shapes before saving:

1. **Create RDF graph** from form data (with unit conversion)
2. **Run SHACL validation** against ontology shapes
3. **Check results**:
   - **Blocking violations**: Return None, save aborted
   - **Warnings/infos**: Return path + validation result (caller shows dialog)

```python
path, validation = writer.write_instance(...)

if path is None:
    # Blocking violations - save was prevented
    for v in validation.violations:
        print(f"Error: {v.message}")
elif validation.has_any_issues():
    # Non-blocking issues - save succeeded but has warnings
    for w in validation.warnings:
        print(f"Warning: {w.message}")
```

---

## Error Handling

Both writers handle errors gracefully with logging:

```python
try:
    path = writer.write_individual(...)
except ValueError as e:
    # Individual already exists in file
    print(f"Duplicate: {e}")
except IOError as e:
    # File write failed
    print(f"Write failed: {e}")
```

IndividualWriter raises `ValueError` if attempting to write an individual that already exists in the target file. Use `update_individual()` to modify existing individuals.

---

## Logging Configuration

Both classes use Python's standard logging module:

```python
import logging

# Enable debug logging for parsers
logging.getLogger('dynamat.gui.parsers').setLevel(logging.DEBUG)

# Detailed format
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(funcName)s:%(lineno)d - %(levelname)s - %(message)s'
)
```

Log messages include:
- Unit conversion details (from/to units, values)
- SHACL validation results
- Property triple additions
- Graph serialization progress
- Error details with stack traces

---

## References

1. RDFLib Documentation: https://rdflib.readthedocs.io/
2. QUDT Ontology: http://www.qudt.org/
3. SHACL Specification: https://www.w3.org/TR/shacl/
4. Turtle Syntax: https://www.w3.org/TR/turtle/
