# GUI Builders Module

This module provides high-level form building orchestration components that coordinate widget creation, layout management, and dependency handling to create complete ontology-driven forms.

## Architecture Overview

```
OntologyFormBuilder (Facade)
       |
       +---> FormManager (widget creation)
       |
       +---> LayoutManager (layout organization)
       |
       +---> DependencyManager (field dependencies)
```

## Module Exports

```python
from dynamat.gui.builders import (
    OntologyFormBuilder,    # High-level form building facade
    LayoutManager,          # Layout creation and grouping
    LayoutStyle,            # Layout style enumeration
)
```

---

## Classes

### OntologyFormBuilder

Simplified facade for building forms from ontology definitions. Coordinates specialized components to provide a clean API for creating ontology-based forms.

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `ontology_manager` | OntologyManager | required | Ontology manager for class metadata |
| `default_layout` | LayoutStyle | GROUPED_FORM | Default layout style |
| `constraint_dir` | Path | None | Directory with constraint TTL files |

**Signals:**

| Signal | Parameters | Description |
|--------|------------|-------------|
| `form_created` | str (class_uri) | Emitted on successful form creation |
| `form_error` | str, str (class_uri, error) | Emitted on form creation failure |

**Key Methods:**

- `build_form(class_uri, parent, layout_style)` - Build complete form
- `build_form_with_layout(class_uri, layout_style, parent)` - Build with specific layout
- `get_form_data(form_widget)` - Extract data from form
- `set_form_data(form_widget, data)` - Populate form with data
- `validate_form(form_widget)` - Validate form data
- `clear_form(form_widget)` - Clear all form fields
- `enable_dependencies(config_path)` - Enable dependency management
- `disable_dependencies()` - Disable dependency management

**Example:**

```python
from dynamat.ontology import OntologyManager
from dynamat.gui.builders import OntologyFormBuilder, LayoutStyle

# Initialize
ontology = OntologyManager()
builder = OntologyFormBuilder(ontology)

# Connect to signals
builder.form_created.connect(lambda uri: print(f"Created: {uri}"))
builder.form_error.connect(lambda uri, err: print(f"Error: {err}"))

# Build form with default layout
form = builder.build_form("dyn:Specimen")

# Build with specific layout
form = builder.build_form_with_layout(
    "dyn:Specimen",
    LayoutStyle.TABBED_FORM
)

# Extract data
data = builder.get_form_data(form)

# Populate form
builder.set_form_data(form, existing_data)

# Validate
errors = builder.validate_form(form)
if errors:
    for field, messages in errors.items():
        print(f"{field}: {', '.join(messages)}")
```

**Loading Mode:**

When populating forms with existing data, the builder automatically enables "loading mode" which suppresses generation constraints (like auto-generated IDs) to preserve loaded values:

```python
# This automatically handles loading mode
builder.set_form_data(form, existing_data)

# Manual control if needed
builder.set_loading_mode(True)
# ... manual operations ...
builder.set_loading_mode(False)
```

---

### LayoutManager

Manages form layout creation and widget organization. Creates grouped, tabbed, or simple layouts from property metadata.

**Key Methods:**

- `create_grouped_form(form_groups, widgets, parent)` - Create grouped layout
- `create_simple_form(properties, widgets, parent)` - Create simple layout
- `create_two_column_form(form_groups, widgets, parent)` - Create two-column layout
- `create_tabbed_form(form_groups, widgets, parent)` - Create tabbed layout

**Example:**

```python
from dynamat.gui.builders import LayoutManager

layout_manager = LayoutManager()

# Create grouped form
form = layout_manager.create_grouped_form(
    form_groups=class_metadata.form_groups,
    widgets=created_widgets,
    parent=parent_widget
)

# Create tabbed form
form = layout_manager.create_tabbed_form(
    form_groups=class_metadata.form_groups,
    widgets=created_widgets
)
```

**Form Widget Attributes:**

Forms created by LayoutManager have these attributes:

| Attribute | Type | Description |
|-----------|------|-------------|
| `form_fields` | Dict[str, FormField] | Property URI to FormField mapping |
| `groups_created` | int | Number of groups created |
| `widgets_added` | int | Number of widgets added to layout |

---

### LayoutStyle

Enumeration of available layout styles for forms.

| Value | Description |
|-------|-------------|
| `GROUPED_FORM` | Groups with form layouts inside QGroupBox (default) |
| `TABBED_FORM` | Each group becomes a tab in QTabWidget |
| `SINGLE_COLUMN` | Single column layout without grouping |
| `TWO_COLUMN` | Groups split across two columns |
| `GRID_LAYOUT` | Grid-based layout for compact display |

**Example:**

```python
from dynamat.gui.builders import LayoutStyle

# Use in form building
form = builder.build_form_with_layout("dyn:Specimen", LayoutStyle.TABBED_FORM)

# Check available styles
for style in LayoutStyle:
    print(f"{style.name}: {style.value}")
```

---

## Typical Workflow

```python
from dynamat.ontology import OntologyManager
from dynamat.gui.builders import OntologyFormBuilder, LayoutStyle

# 1. Initialize components
ontology = OntologyManager()
builder = OntologyFormBuilder(ontology)

# 2. Build form for ontology class
form = builder.build_form("dyn:Specimen")

# Display form in your application window...
# my_window.layout().addWidget(form)

# 3. Connect to form signals (optional)
def on_form_created(class_uri):
    print(f"Form created for {class_uri}")

def on_form_error(class_uri, error):
    print(f"Error creating form for {class_uri}: {error}")

builder.form_created.connect(on_form_created)
builder.form_error.connect(on_form_error)

# 4. User fills form...

# 5. Extract and validate data
data = builder.get_form_data(form)
errors = builder.validate_form(form)

if errors:
    # Show errors to user
    for field, messages in errors.items():
        print(f"{field}: {', '.join(messages)}")
else:
    # Save data
    save_specimen(data)
```

---

## Dependency Management

The builder supports constraint-based field dependencies loaded from TTL files.

**Enabling Dependencies:**

```python
from pathlib import Path

# Initialize with constraint directory
constraint_dir = Path("dynamat/ontology/constraints")
builder = OntologyFormBuilder(ontology, constraint_dir=constraint_dir)

# Or enable later
builder.enable_dependencies("path/to/constraints")

# Reload constraints after changes
builder.reload_constraints()

# Get constraint statistics
stats = builder.get_constraint_statistics()
print(f"Loaded constraints: {stats}")
```

**Constraint Types:**

- **Visibility**: Show/hide fields based on other field values
- **Population**: Auto-populate dropdowns based on selections
- **Calculation**: Auto-calculate derived values
- **Generation**: Auto-generate IDs or timestamps

---

## Form Complexity Analysis

Analyze form complexity before building:

```python
# Get complexity analysis
analysis = builder.analyze_form_complexity("dyn:Specimen")

print(f"Total properties: {analysis['total_properties']}")
print(f"Form groups: {analysis['form_groups']}")
print(f"Complexity score: {analysis['complexity_score']}")
# Output: "Simple", "Moderate", or "Complex"

# Get layout suggestion based on complexity
suggested_layout = builder.get_layout_suggestion("dyn:Specimen")
print(f"Suggested layout: {suggested_layout}")
```

---

## Statistics and Debugging

Get comprehensive statistics for testing and debugging:

```python
# Get builder statistics
stats = builder.get_statistics()

print(f"Forms created: {stats['execution']['total_forms_created']}")
print(f"Errors: {stats['execution']['total_errors']}")
print(f"Layout usage: {stats['execution']['layout_usage']}")

# Get form-specific statistics
form_stats = builder.get_form_statistics()
for class_uri, count in form_stats['forms_by_class'].items():
    print(f"{class_uri}: {count} forms")
```

---

## Logging Configuration

All classes use Python's standard logging module:

```python
import logging

# Enable debug logging for builders
logging.getLogger('dynamat.gui.builders').setLevel(logging.DEBUG)

# Detailed format with function names
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(funcName)s:%(lineno)d - %(levelname)s - %(message)s'
)
```

Log messages include:
- Form building progress
- Layout creation details
- Dependency setup status
- Widget organization
- Error details with stack traces

---

## Error Handling

All methods handle errors gracefully:

```python
# Form building returns error widget on failure
form = builder.build_form("invalid:Class")
# Returns QLabel with error message, emits form_error signal

# Data operations return empty/False on failure
data = builder.get_form_data(invalid_form)  # Returns {}
success = builder.set_form_data(form, bad_data)  # Returns False

# Layout manager returns error label on failure
form = layout_manager.create_grouped_form(groups, widgets)
# Returns QLabel with error if layout fails
```

**Error Widget Attributes:**

Error widgets have standard attributes for compatibility:

```python
error_widget.form_fields = {}
error_widget.class_uri = class_uri
error_widget.form_style = None
error_widget.class_metadata = None
```

---

## References

1. PyQt6 Widgets Documentation: https://doc.qt.io/qtforpython-6/
2. PyQt6 Layouts: https://doc.qt.io/qtforpython-6/overviews/layout.html
3. Qt Signals and Slots: https://doc.qt.io/qtforpython-6/overviews/signalsandslots.html
