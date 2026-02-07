# GUI Dependencies Module

This module provides a constraint-based dependency system for ontology-driven forms. It manages field visibility, calculations, value generation, and population based on TTL-defined constraints.

## Architecture Overview

```
TTL Constraint Files
       |
       v
+-------------------+
| ConstraintManager |  (loads & parses TTL constraints)
+-------------------+
       |
       v
+-------------------+     +-------------------+     +-------------------+
| DependencyManager | --> | CalculationEngine | --> | GenerationEngine  |
|  (orchestration)  |     |  (math functions) |     |  (ID generation)  |
+-------------------+     +-------------------+     +-------------------+
```

## Module Exports

```python
from dynamat.gui.dependencies import (
    # Main orchestrator
    DependencyManager,

    # Calculation engine
    CalculationEngine,
    CalculationType,

    # Generation engine
    GenerationEngine,

    # Constraint system
    ConstraintManager,
    Constraint,
    TriggerLogic,
)
```

---

## Classes

### DependencyManager

Main orchestrator that connects form widgets to constraints. Handles signal connections, constraint evaluation, and operation execution.

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `ontology_manager` | OntologyManager | required | Ontology manager for queries |
| `constraint_dir` | Path | None | Directory with constraint TTL files |

**Signals:**

| Signal | Parameters | Description |
|--------|------------|-------------|
| `constraint_triggered` | str, list | Emitted when constraint fires (uri, operations) |
| `calculation_performed` | str, float | Emitted after calculation (property_uri, result) |
| `generation_performed` | str, str | Emitted after generation (property_uri, result) |
| `error_occurred` | str, str | Emitted on error (constraint_uri, message) |

**Key Methods:**

- `setup_dependencies(form_widget, class_uri)` - Set up all dependencies for a form
- `set_loading_mode(enabled)` - Enable/disable loading mode (suppresses generation)
- `is_loading_mode()` - Check if currently in loading mode
- `reload_constraints()` - Reload constraints from TTL files
- `get_statistics()` - Get comprehensive statistics for debugging
- `get_constraint_activity()` - Get detailed constraint activity report

**Example:**

```python
from dynamat.ontology import OntologyManager
from dynamat.gui.dependencies import DependencyManager
from pathlib import Path

# Initialize
ontology = OntologyManager()
constraint_dir = Path("dynamat/ontology/constraints")
dep_manager = DependencyManager(ontology, constraint_dir)

# Connect to signals
dep_manager.calculation_performed.connect(
    lambda uri, result: print(f"Calculated {uri} = {result}")
)
dep_manager.generation_performed.connect(
    lambda uri, result: print(f"Generated {uri} = {result}")
)
dep_manager.error_occurred.connect(
    lambda uri, msg: print(f"Error in {uri}: {msg}")
)

# Set up dependencies for a form
dep_manager.setup_dependencies(form_widget, "dyn:Specimen")

# Enable loading mode when populating existing data
dep_manager.set_loading_mode(True)
# ... load data into form ...
dep_manager.set_loading_mode(False)
```

**Loading Mode:**

When loading existing data into forms, enable loading mode to suppress generation constraints (e.g., auto-generated specimen IDs). Other constraints (visibility, calculation, population) continue to work normally.

```python
# Automatically handled by OntologyFormBuilder.set_form_data()
# Or manually control:
dep_manager.set_loading_mode(True)
# ... populate form fields ...
dep_manager.set_loading_mode(False)
```

---

### ConstraintManager

Loads and parses constraint definitions from TTL files. Provides structured access to constraint properties and operations.

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `constraint_dir` | Path | None | Directory containing constraint TTL files |

**Key Methods:**

- `get_constraints_for_class(class_uri)` - Get all constraints for a class (sorted by priority)
- `get_constraint(constraint_uri)` - Get specific constraint by URI
- `get_constraints_by_trigger(class_uri, trigger_property)` - Get constraints triggered by property
- `get_generation_constraints(class_uri)` - Get constraints with generation operations
- `get_calculation_constraints(class_uri)` - Get constraints with calculation operations
- `get_visibility_constraints(class_uri)` - Get constraints with visibility operations
- `reload()` - Reload all constraints from files
- `get_statistics()` - Get constraint statistics

**Example:**

```python
from dynamat.gui.dependencies import ConstraintManager
from pathlib import Path

# Initialize
constraint_dir = Path("dynamat/ontology/constraints")
manager = ConstraintManager(constraint_dir)

# Get constraints for a class
constraints = manager.get_constraints_for_class("dyn:Specimen")
print(f"Found {len(constraints)} constraints")

# Get specific constraint types
visibility = manager.get_visibility_constraints("dyn:Specimen")
calculations = manager.get_calculation_constraints("dyn:Specimen")
generations = manager.get_generation_constraints("dyn:Specimen")

# Get statistics
stats = manager.get_statistics()
print(f"Total constraints: {stats['configuration']['total_constraints']}")
print(f"Operations breakdown: {stats['content']['operations']}")
```

---

### Constraint

Dataclass representing a unified UI constraint with multiple possible operations.

**Attributes:**

| Attribute | Type | Description |
|-----------|------|-------------|
| `uri` | str | Constraint URI |
| `label` | str | Human-readable label |
| `comment` | str | Description |
| `for_class` | str | Target class URI |
| `triggers` | List[str] | Properties that trigger this constraint |
| `trigger_logic` | TriggerLogic | Logic gate (ANY, ALL, XOR) |
| `when_values` | List[str] | Expected trigger values |
| `priority` | int | Execution priority (higher runs first) |
| `show_fields` | List[str] | Fields to show when condition met |
| `hide_fields` | List[str] | Fields to hide when condition met |
| `calculation_function` | str | Name of calculation function |
| `calculation_target` | str | Property to store result |
| `calculation_inputs` | List[str] | Input properties for calculation |
| `generation_template` | str | Template string for generation |
| `generation_target` | str | Property to store generated value |
| `generation_inputs` | List[str] | Input properties for generation |
| `populate_fields` | List[tuple] | Fields to populate from individual |
| `make_read_only` | bool | Make populated fields read-only |
| `apply_to_fields` | List[str] | Fields to apply filtering to |
| `exclude_classes` | List[str] | Classes to exclude in filtering |
| `filter_by_classes` | List[str] | Classes to include in filtering |

**Helper Methods:**

- `has_visibility_ops()` - Check if constraint has visibility operations
- `has_calculation_op()` - Check if constraint has calculation operation
- `has_generation_op()` - Check if constraint has generation operation
- `has_population_op()` - Check if constraint has population operation
- `has_filter_op()` - Check if constraint has filtering operations

---

### TriggerLogic

Enumeration of logic gates for multiple triggers.

| Value | Description |
|-------|-------------|
| `ANY` | Condition met if ANY trigger matches |
| `ALL` | Condition met if ALL triggers match |
| `XOR` | Condition met if exactly ONE trigger matches |

**Example:**

```python
from dynamat.gui.dependencies import TriggerLogic

# Check constraint logic
if constraint.trigger_logic == TriggerLogic.ANY:
    print("Fires when any trigger matches")
elif constraint.trigger_logic == TriggerLogic.ALL:
    print("Fires when all triggers match")
```

---

### CalculationEngine

Performs mathematical calculations for derived field values. Supports area, volume, density, stress calculations and unit conversions.

**Key Methods:**

- `calculate(function_name, **kwargs)` - Perform a calculation
- `get_available_calculations()` - List available calculation functions
- `validate_calculation_inputs(function_name, **kwargs)` - Validate inputs
- `get_calculation_info(function_name)` - Get function information
- `get_supported_units()` - Get supported unit categories
- `is_unit_compatible(unit1, unit2)` - Check unit compatibility
- `format_result(value, decimal_places)` - Format result for display

**Available Calculations:**

| Category | Functions |
|----------|-----------|
| Area | `circular_area_from_diameter`, `circular_area_from_radius`, `rectangular_area`, `square_area` |
| Volume | `volume_cube`, `volume_cylinder`, `volume_rectangular`, `volume_sphere` |
| Mass/Density | `density_from_mass_volume`, `mass_from_density_volume`, `volume_from_mass_density` |
| Engineering | `strain_rate_from_velocity_length`, `stress_from_force_area`, `force_from_stress_area` |
| Conversion | `convert_units` |

**Example:**

```python
from dynamat.gui.dependencies import CalculationEngine

engine = CalculationEngine()

# Calculate circular area from diameter
area = engine.calculate(
    "circular_area_from_diameter",
    **{"dyn:hasOriginalDiameter": 10.0}  # diameter in mm
)
print(f"Area: {area} mm^2")  # ~78.54 mm^2

# Calculate rectangular area
area = engine.calculate(
    "rectangular_area",
    **{"dyn:hasWidth": 5.0, "dyn:hasThickness": 3.0}
)
print(f"Area: {area} mm^2")  # 15.0 mm^2

# Unit conversion
value_m = engine.calculate(
    "convert_units",
    value=25.4, from_unit="mm", to_unit="in"
)
print(f"Value: {value_m} in")  # 1.0 in

# Validate inputs
errors = engine.validate_calculation_inputs(
    "circular_area_from_diameter",
    diameter=-5.0
)
if errors:
    print(f"Validation errors: {errors}")
```

**Supported Units:**

| Category | Units |
|----------|-------|
| Length | mm, cm, m, in, ft |
| Area | mm^2, cm^2, m^2, in^2 |
| Volume | mm^3, cm^3, m^3, in^3 |
| Mass | g, kg, lb |
| Force | N, kN, lbf |
| Pressure | Pa, kPa, MPa, GPa, psi, ksi |

---

### GenerationEngine

Generates formatted values from templates (specimen IDs, batch IDs, etc.). Supports sequence numbering and material code extraction.

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `ontology_manager` | OntologyManager | Reference for ontology queries |

**Key Methods:**

- `generate(template, inputs)` - Generate value from template
- `register_generator(name, func)` - Register custom generator
- `get_available_generators()` - List available generators
- `call_generator(name, **kwargs)` - Call specific generator
- `test_template(template, sample_inputs)` - Test template with samples
- `validate_template(template)` - Validate template syntax

**Built-in Generators:**

| Generator | Description |
|-----------|-------------|
| `specimen_id` | Generate specimen ID (DYNML-{code}-{seq}) |
| `material_code` | Extract/generate material code |
| `batch_id` | Generate batch ID |
| `test_id` | Generate test ID |
| `timestamp` | Generate ISO timestamp |

**Example:**

```python
from dynamat.gui.dependencies import GenerationEngine

engine = GenerationEngine(ontology_manager)

# Generate specimen ID from template
specimen_id = engine.generate(
    template="DYNML-{materialCode}-{sequence}",
    inputs={
        "materialCode": "AL6061",
        "sequence": 42
    }
)
print(f"Generated ID: {specimen_id}")  # DYNML-AL6061-0042

# Call built-in generator
batch_id = engine.call_generator(
    "batch_id",
    material_code="AL6061"
)
print(f"Batch ID: {batch_id}")  # BATCH-AL6061-20240115

# Register custom generator
def custom_code_generator(prefix: str, number: int) -> str:
    return f"{prefix}-{number:06d}"

engine.register_generator("custom_code", custom_code_generator)

# Validate template
is_valid, message = engine.validate_template("TEST-{code}-{num}")
print(f"Valid: {is_valid}, Message: {message}")
```

**Template Placeholders:**

| Placeholder | Processing |
|-------------|------------|
| `{materialCode}` | Extracted from material URI or passed directly |
| `{sequence}` | Formatted as 4-digit padded number |
| `{date}` | Formatted as YYYYMMDD |
| Other | Passed through as-is |

---

## Constraint Types

### Visibility Constraints

Show or hide fields based on trigger field values.

```turtle
gui:ShapeCircularConstraint a gui:Constraint ;
    rdfs:label "Circular Shape Fields" ;
    gui:forClass dyn:Specimen ;
    gui:triggers dyn:hasSpecimenShape ;
    gui:whenValue dyn:CircularCrossSection ;
    gui:showFields ( dyn:hasOriginalDiameter ) ;
    gui:hideFields ( dyn:hasWidth dyn:hasThickness ) ;
    gui:priority 100 .
```

### Calculation Constraints

Compute derived values from input fields.

```turtle
gui:CircularAreaCalculation a gui:Constraint ;
    rdfs:label "Calculate Circular Area" ;
    gui:forClass dyn:Specimen ;
    gui:triggers dyn:hasOriginalDiameter ;
    gui:whenValue gui:anyValue ;
    gui:calculationFunction "circular_area_from_diameter" ;
    gui:calculationTarget dyn:hasOriginalCrossSectionalArea ;
    gui:calculationInputs ( dyn:hasOriginalDiameter ) ;
    gui:priority 50 .
```

### Generation Constraints

Generate IDs and codes from templates.

```turtle
gui:SpecimenIDGeneration a gui:Constraint ;
    rdfs:label "Generate Specimen ID" ;
    gui:forClass dyn:Specimen ;
    gui:triggers dyn:hasMaterial ;
    gui:whenValue gui:anyValue ;
    gui:generationTemplate "DYNML-{materialCode}-{sequence}" ;
    gui:generationTarget dyn:hasSpecimenID ;
    gui:generationInputs ( dyn:hasMaterial ) ;
    gui:priority 200 .
```

### Population Constraints

Auto-populate fields from selected ontology individuals.

```turtle
gui:BatchPopulation a gui:Constraint ;
    rdfs:label "Populate from Batch" ;
    gui:forClass dyn:Specimen ;
    gui:triggers dyn:hasSpecimenBatch ;
    gui:whenValue gui:anyValue ;
    gui:populateFields (
        ( dyn:hasMaterial "Material" )
        ( dyn:hasSpecimenShape "Shape" )
    ) ;
    gui:makeReadOnly true ;
    gui:priority 150 .
```

### Filtering Constraints

Filter dropdown choices based on class membership.

```turtle
gui:MaterialFilterConstraint a gui:Constraint ;
    rdfs:label "Filter Composite Materials" ;
    gui:forClass dyn:Specimen ;
    gui:triggers dyn:hasSpecimenRole ;
    gui:whenValue dyn:CompositeSpecimen ;
    gui:applyToFields ( dyn:hasMaterial ) ;
    gui:filterByClass dyn:CompositeMaterial ;
    gui:priority 75 .
```

---

## Special Trigger Values

| Value | Description |
|-------|-------------|
| `gui:anyValue` | Matches any non-empty value |
| `gui:noValue` | Matches empty/null values |

---

## Priority System

Constraints are evaluated in priority order (higher values run first). Lower priority constraints can override earlier ones.

| Priority Range | Typical Use |
|----------------|-------------|
| 500+ | Critical constraints (ID generation) |
| 200-499 | High priority (population) |
| 100-199 | Normal visibility constraints |
| 50-99 | Calculations |
| 1-49 | Low priority / defaults |

---

## Typical Workflow

```python
from dynamat.ontology import OntologyManager
from dynamat.gui.dependencies import DependencyManager
from pathlib import Path

# 1. Initialize components
ontology = OntologyManager()
constraint_dir = Path("dynamat/ontology/constraints")
dep_manager = DependencyManager(ontology, constraint_dir)

# 2. Connect to signals for monitoring
dep_manager.constraint_triggered.connect(
    lambda uri, ops: print(f"Constraint {uri} fired: {ops}")
)

# 3. Set up dependencies for form
dep_manager.setup_dependencies(form_widget, "dyn:Specimen")

# 4. User interacts with form...
#    - Selecting material triggers ID generation
#    - Changing shape triggers visibility updates
#    - Entering diameter triggers area calculation

# 5. Get activity statistics
stats = dep_manager.get_statistics()
print(f"Total evaluations: {stats['execution']['total_evaluations']}")
print(f"Operations: {stats['execution']['operation_executions']}")
```

---

## Statistics and Debugging

Get comprehensive statistics for testing and debugging:

```python
# DependencyManager statistics
stats = dep_manager.get_statistics()

print(f"Configuration:")
print(f"  Available calculations: {stats['configuration']['available_calculations']}")
print(f"  Available generators: {stats['configuration']['available_generators']}")

print(f"Execution:")
print(f"  Total evaluations: {stats['execution']['total_evaluations']}")
print(f"  Operations by type: {stats['execution']['operation_executions']['by_type']}")
print(f"  Most active trigger: {stats['execution']['most_active_trigger']}")

print(f"Health:")
print(f"  Active form: {stats['health']['active_state']['has_active_form']}")
print(f"  Connected signals: {stats['health']['active_state']['connected_signals']}")

print(f"Errors:")
print(f"  Recent errors: {stats['errors']['recent_errors']}")

# ConstraintManager statistics
cm_stats = dep_manager.constraint_manager.get_statistics()
print(f"Constraint content:")
print(f"  Operations: {cm_stats['content']['operations']}")
print(f"  Priority distribution: {cm_stats['content']['priority_distribution']}")
```

---

## Logging Configuration

All classes use Python's standard logging module:

```python
import logging

# Enable debug logging for dependencies
logging.getLogger('dynamat.gui.dependencies').setLevel(logging.DEBUG)

# Detailed format with function names
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(funcName)s:%(lineno)d - %(levelname)s - %(message)s'
)
```

Log messages include:
- Constraint loading and parsing
- Trigger signal connections
- Constraint evaluation (condition checks, operations)
- Calculation inputs and results
- Generation template processing
- Error details with stack traces

---

## Error Handling

All methods handle errors gracefully:

```python
# DependencyManager emits error_occurred signal
dep_manager.error_occurred.connect(
    lambda uri, msg: handle_error(uri, msg)
)

# CalculationEngine returns None on failure
result = engine.calculate("invalid_function")  # Returns None

# GenerationEngine returns empty string on failure
result = engine.generate("bad template {missing}", {})  # Returns ""

# ConstraintManager logs warnings for missing files
manager = ConstraintManager(Path("nonexistent"))  # Logs warning, continues
```

---

## References

1. RDFLib Documentation: https://rdflib.readthedocs.io/
2. RDFLib Collections: https://rdflib.readthedocs.io/en/stable/utilities.html
3. PyQt6 Signals and Slots: https://doc.qt.io/qtforpython-6/overviews/signalsandslots.html
4. QUDT Units Ontology: http://www.qudt.org/
