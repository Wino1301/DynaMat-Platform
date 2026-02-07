# GUI Core Module

This module provides the core components for ontology-driven form generation in the DynaMat Platform. It implements the ontology-first design philosophy where the GUI reads RDF ontology definitions and automatically generates appropriate form interfaces.

## Architecture Overview

```
Ontology Metadata
       |
       v
+-------------------+     +-------------------+
|   WidgetFactory   | --> |   FormManager     |
|  (Widget Creation)|     |  (Orchestration)  |
+-------------------+     +-------------------+
                                  |
                                  v
                          +-------------------+     +-------------------+
                          |  FormDataHandler  | --> |  SHACLValidator   |
                          |  (Data I/O)       |     |  (Validation)     |
                          +-------------------+     +-------------------+
```

## Module Exports

```python
from dynamat.gui.core import (
    WidgetFactory,         # Widget creation from metadata
    FormManager,           # Form creation orchestration
    FormStyle,             # Form layout styles enum
    FormField,             # Form field dataclass
    FormDataHandler,       # Data extraction/population
    SHACLValidator,        # SHACL-based validation
    ValidationResult,      # Validation result container
    ValidationIssue,       # Single validation issue
)
```

---

## Classes

### FormManager

Coordinates form creation using specialized components. Main entry point for creating complete forms from ontology class definitions.

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `ontology_manager` | OntologyManager | The ontology manager instance |

**Key Methods:**

- `create_form(class_uri, style, parent, use_cache)` - Create complete form for a class
- `get_form_data(form_widget)` - Extract data from form
- `set_form_data(form_widget, data)` - Populate form with data
- `validate_form(form_widget)` - Validate form data
- `clear_form(form_widget)` - Clear all form fields
- `reload_form(form_widget)` - Reload form from ontology

**Example:**

```python
from dynamat.ontology import OntologyManager
from dynamat.gui.core import FormManager, FormStyle

# Initialize
ontology = OntologyManager()
manager = FormManager(ontology)

# Create a grouped form
form = manager.create_form(
    class_uri="dyn:Specimen",
    style=FormStyle.GROUPED,
    use_cache=True
)

# Extract data from filled form
data = manager.get_form_data(form)

# Populate form with existing data
manager.set_form_data(form, existing_data)

# Validate before save
errors = manager.validate_form(form)
if errors:
    print(f"Validation errors: {errors}")
```

**Form Widget Attributes:**

The returned form widget has these attributes attached:

| Attribute | Type | Description |
|-----------|------|-------------|
| `class_uri` | str | The ontology class URI |
| `class_metadata` | ClassMetadata | Metadata from ontology |
| `form_style` | FormStyle | Layout style used |
| `form_fields` | Dict[str, FormField] | Property URI to FormField mapping |
| `widgets_created` | int | Number of widgets created |
| `creation_timestamp` | datetime | When form was created |

---

### FormStyle

Enumeration of available form layout styles.

| Value | Description |
|-------|-------------|
| `GROUPED` | Fields organized into collapsible group boxes |
| `SIMPLE` | Single-column layout without grouping |
| `TWO_COLUMN` | Two-column layout for wider displays |
| `TABBED` | Groups displayed as tabs |

**Example:**

```python
from dynamat.gui.core import FormStyle

# Create different layout styles
grouped_form = manager.create_form("dyn:Specimen", style=FormStyle.GROUPED)
tabbed_form = manager.create_form("dyn:Specimen", style=FormStyle.TABBED)
simple_form = manager.create_form("dyn:Specimen", style=FormStyle.SIMPLE)
```

---

### FormField

Dataclass representing a form field with its widget and metadata.

**Attributes:**

| Attribute | Type | Description |
|-----------|------|-------------|
| `widget` | QWidget | The PyQt6 widget |
| `property_uri` | str | Full URI of the property |
| `property_metadata` | PropertyMetadata | Ontology property metadata |
| `group_name` | str | Form group this field belongs to |
| `required` | bool | Whether field is required |
| `label` | str | Display label |
| `label_widget` | QWidget | Reference to label for visibility control |

---

### WidgetFactory

Centralized factory for creating form widgets from ontology metadata.

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `ontology_manager` | OntologyManager | The ontology manager instance |

**Widget Type Determination:**

The factory determines widget types in priority order:

1. Read-only string properties -> QLabel
2. Measurement properties (has compatible_units) -> UnitValueWidget
3. Object properties (data_type=object) -> QComboBox or QListWidget
4. Suggested widget type from metadata
5. Fallback based on data_type

**Widget Type Mapping:**

| Data Type | Widget | Notes |
|-----------|--------|-------|
| string | QLineEdit | Default for text |
| string (read-only) | QLabel | Display only |
| integer | QSpinBox | Integer values |
| double | QDoubleSpinBox | Floating-point values |
| boolean | QCheckBox | True/false values |
| date | QDateEdit | Date picker with calendar |
| object | QComboBox | Dropdown for individuals |
| object (non-functional) | QListWidget | Multi-select list |
| measurement | UnitValueWidget | Value + unit selection |

**Example:**

```python
from dynamat.gui.core import WidgetFactory

factory = WidgetFactory(ontology_manager)

# Create single widget
widget = factory.create_widget(property_metadata)

# Create widgets for all properties
widgets = factory.create_widgets_for_properties(properties)

# Get statistics
stats = factory.get_statistics()
print(f"Created {stats['execution']['total_widgets']} widgets")
```

---

### FormDataHandler

Handles data extraction and population for form widgets.

**Key Methods:**

- `extract_form_data(form_widget)` - Extract all visible field values
- `populate_form_data(form_widget, data)` - Set form field values
- `validate_form_data(form_widget)` - Validate required fields
- `get_widget_value(widget)` - Get value from any widget type
- `set_widget_value(widget, value)` - Set value on any widget type
- `get_form_summary(form_widget)` - Get form statistics

**Visibility-Based Extraction:**

Data extraction automatically excludes hidden widgets (e.g., fields hidden by dependency rules):

```python
handler = FormDataHandler()

# Only visible fields are included
data = handler.extract_form_data(form)

# Placeholder values are also excluded
# e.g., "(Select...)", empty strings, zero values
```

**Supported Value Types:**

| Widget Type | Extracted Type |
|-------------|----------------|
| QLineEdit | str |
| QTextEdit | str |
| QComboBox | str (data or text) |
| QListWidget | List[str] or str |
| QSpinBox | int |
| QDoubleSpinBox | float |
| QDateEdit | str (yyyy-MM-dd) |
| QCheckBox | bool |
| UnitValueWidget | Dict[value, unit, unit_symbol] |

---

### SHACLValidator

SHACL validator for RDF instance data.

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `ontology_manager` | OntologyManager | None | Optional ontology manager for shapes directory |

**Key Methods:**

- `validate(data_graph)` - Validate RDF graph against SHACL shapes
- `validate_form_data(form_data, class_uri, instance_id)` - Validate form data (placeholder)

**Example:**

```python
from dynamat.gui.core import SHACLValidator
from rdflib import Graph

validator = SHACLValidator(ontology_manager)

# Create or load RDF graph
data_graph = Graph()
data_graph.parse("specimen.ttl", format="turtle")

# Validate
result = validator.validate(data_graph)

if result.has_blocking_issues():
    for issue in result.violations:
        print(f"ERROR: {issue.get_display_message()}")
else:
    print(f"Validation passed: {result.get_summary()}")
```

---

### ValidationResult

Container for SHACL validation results.

**Attributes:**

| Attribute | Type | Description |
|-----------|------|-------------|
| `conforms` | bool | True if no violations exist |
| `violations` | List[ValidationIssue] | Critical errors (block save) |
| `warnings` | List[ValidationIssue] | Contextual issues |
| `infos` | List[ValidationIssue] | Informational suggestions |
| `raw_report` | str | Raw SHACL validation text |

**Methods:**

- `has_blocking_issues()` - True if violations exist
- `has_any_issues()` - True if any issues exist
- `get_all_issues()` - Get all issues sorted by severity
- `get_summary()` - Get summary string

---

### ValidationIssue

Represents a single SHACL validation issue.

**Attributes:**

| Attribute | Type | Description |
|-----------|------|-------------|
| `severity` | ValidationSeverity | Violation, Warning, or Info |
| `message` | str | Human-readable error message |
| `focus_node` | str | Subject that failed validation |
| `result_path` | str | Property that failed |
| `value` | str | Problematic value |
| `source_shape` | str | SHACL shape that generated issue |

---

## Typical Workflow

```python
from dynamat.ontology import OntologyManager
from dynamat.gui.core import (
    FormManager,
    FormStyle,
    FormDataHandler,
    SHACLValidator
)

# 1. Initialize components
ontology = OntologyManager()
form_manager = FormManager(ontology)
validator = SHACLValidator(ontology)

# 2. Create form for ontology class
form = form_manager.create_form(
    class_uri="dyn:Specimen",
    style=FormStyle.GROUPED
)

# Display form in your application...

# 3. Extract data when user submits
data = form_manager.get_form_data(form)

# 4. Basic validation (required fields)
errors = form_manager.validate_form(form)
if errors:
    # Show errors to user
    for field, messages in errors.items():
        print(f"{field}: {', '.join(messages)}")
    return

# 5. Create RDF graph and validate with SHACL
# (typically done in instance_writer module)
data_graph = create_rdf_graph(data)  # Your graph creation logic
result = validator.validate(data_graph)

if result.has_blocking_issues():
    # Show validation errors
    for issue in result.violations:
        print(f"ERROR: {issue.get_display_message()}")
    return

# 6. Save data
save_specimen(data)
```

---

## Form Field Dependencies

The form system supports field dependencies where some fields are shown/hidden based on other field values. This is managed by the DependencyManager in the `gui/dependencies/` module.

**How it works:**

1. Dependencies are defined in the ontology (or code)
2. DependencyManager watches for value changes
3. Hidden fields are excluded from data extraction
4. Label widgets are hidden along with their fields

---

## Caching

Form creation supports caching for performance:

```python
# Enable caching (default)
form = manager.create_form("dyn:Specimen", use_cache=True)

# Disable caching for fresh form
form = manager.create_form("dyn:Specimen", use_cache=False)

# Clear all caches
manager.clear_cache()

# Get cache information
info = manager.get_cache_info()
print(f"Cached forms: {info['cached_forms']}")
```

**Cache Control:**

Caching is controlled by `Config.USE_FORM_CACHE` and `Config.USE_METADATA_CACHE` in the application configuration.

---

## Logging Configuration

All classes use Python's standard logging module. Configure logging to see debug output:

```python
import logging

# Enable debug logging for the core module
logging.getLogger('dynamat.gui.core').setLevel(logging.DEBUG)

# Or enable globally with detailed format
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(funcName)s:%(lineno)d - %(levelname)s - %(message)s'
)
```

Log messages include:
- Form creation progress and widget counts
- Widget type determination decisions
- Data extraction/population results
- Validation results and errors

---

## Error Handling

All methods handle errors gracefully:

```python
# Form creation returns error widget on failure
form = manager.create_form("invalid:Class")
# Returns QLabel with error message, not exception

# Data operations return empty/False on failure
data = manager.get_form_data(invalid_form)  # Returns {}
success = manager.set_form_data(form, bad_data)  # Returns False

# Validation returns error dict on failure
errors = manager.validate_form(form)
# {"form": ["Validation error: ..."]}
```

---

## References

1. PyQt6 Widgets Documentation: https://doc.qt.io/qtforpython-6/
2. RDFLib Documentation: https://rdflib.readthedocs.io/
3. SHACL Specification: https://www.w3.org/TR/shacl/
4. pySHACL Library: https://github.com/RDFLib/pySHACL
