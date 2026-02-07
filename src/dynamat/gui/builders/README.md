# GUI Builders Module

This module provides high-level form building orchestration components that coordinate widget creation, layout management, and dependency handling to create complete ontology-driven forms.

## Architecture Overview

### Standard Form Building

```
OntologyFormBuilder (Facade)
       |
       +---> FormManager (widget creation)
       |
       +---> LayoutManager (layout organization)
       |
       +---> DependencyManager (field dependencies)
```

### Customizable Form Building (NEW)

```
CustomizableFormBuilder
       |
       +---> FormManager (widget creation)
       |
       +---> GroupBuilder (per-group rendering)
       |       |
       |       +---> DefaultGroupBuilder (standard QGroupBox)
       |       |
       |       +---> Custom GroupBuilders (specialized rendering)
       |
       +---> DependencyManager (field dependencies)
```

The **Group Builder Architecture** allows custom rendering of individual form groups, enabling:
- Intermediate display widgets (derived/calculated values)
- Custom layouts (multi-column, grid, collapsible)
- Group-specific behavior and dynamic content

## Module Exports

```python
from dynamat.gui.builders import (
    # Standard form building
    OntologyFormBuilder,         # High-level form building facade
    LayoutManager,               # Layout creation and grouping
    LayoutStyle,                 # Layout style enumeration

    # Customizable form building (v2.0)
    CustomizableFormBuilder,     # Form builder with custom group support
    GroupBuilder,                # Abstract base for custom group builders
    DefaultGroupBuilder,         # Default QGroupBox + QFormLayout rendering
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

### CustomizableFormBuilder (NEW)

Extended form builder that supports custom group builders, enabling specialized rendering of form groups with intermediate widgets and custom layouts.

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `ontology_manager` | OntologyManager | required | Ontology manager for class metadata |

**Key Methods:**

- `register_group_builder(group_name, builder)` - Register custom builder for specific group
- `unregister_group_builder(group_name)` - Remove custom builder registration
- `build_form(class_uri, parent)` - Build form with custom group builders
- `get_form_data(form_widget)` - Extract data from form (delegates to FormManager)
- `set_form_data(form_widget, data)` - Populate form with data (delegates to FormManager)

**Example:**

```python
from dynamat.gui.builders import CustomizableFormBuilder
from dynamat.gui.widgets.shpb.builders import EquipmentPropertiesGroupBuilder

# Initialize customizable builder
builder = CustomizableFormBuilder(ontology_manager)

# Register custom builder for specific group
builder.register_group_builder(
    "EquipmentConfiguration",  # Must match gui:hasFormGroup value
    EquipmentPropertiesGroupBuilder(builder.widget_factory)
)

# Build form (custom rendering applied to registered groups)
form = builder.build_form("dyn:SHPBTestingConfiguration")

# Other groups use default QGroupBox + QFormLayout rendering
# Data operations work the same as OntologyFormBuilder
data = builder.get_form_data(form)
builder.set_form_data(form, existing_data)
```

---

### GroupBuilder (Abstract Base Class)

Abstract interface for building custom form groups from property metadata. Subclass this to create specialized group rendering.

**Key Methods:**

- `build_group(group_name, properties, parent)` - Build complete group widget (abstract, must implement)
- `create_widgets_for_group(properties, parent)` - Helper to create widgets for properties

**Returns:**

`build_group()` must return a tuple: `(group_widget, form_fields_dict)` where:
- `group_widget`: QWidget containing the complete group
- `form_fields_dict`: Dict mapping property URIs to FormField objects

**Example Implementation:**

```python
from dynamat.gui.builders import GroupBuilder
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QGroupBox, QFormLayout, QLabel
from dynamat.gui.core.form_manager import FormField

class MyCustomGroupBuilder(GroupBuilder):
    """Custom builder with intermediate display widget."""

    def build_group(self, group_name, properties, parent=None):
        # Create container
        container = QWidget(parent)
        layout = QVBoxLayout(container)

        # 1. Create standard form section
        form_group, form_fields = self._create_standard_form(
            group_name, properties, container
        )
        layout.addWidget(form_group)

        # 2. Add intermediate display widget
        display_widget = self._create_display_section(container)
        layout.addWidget(display_widget)

        # 3. Store references for external access
        container.display_label = self.display_label

        return container, form_fields

    def _create_standard_form(self, group_name, properties, parent):
        """Create standard QGroupBox with form layout."""
        group_box = QGroupBox(group_name, parent)
        form_layout = QFormLayout(group_box)

        # Use helper to create widgets
        widgets = self.create_widgets_for_group(properties)

        form_fields = {}
        for prop in sorted(properties, key=lambda p: p.display_order or 0):
            if prop.uri not in widgets:
                continue

            widget = widgets[prop.uri]
            label_text = prop.display_name or prop.name
            if prop.is_required:
                label_text += " *"

            label = QLabel(label_text)
            form_layout.addRow(label, widget)

            form_fields[prop.uri] = FormField(
                widget=widget,
                property_uri=prop.uri,
                property_metadata=prop,
                group_name=group_name,
                required=prop.is_required,
                label=label_text,
                label_widget=label
            )

        return group_box, form_fields

    def _create_display_section(self, parent):
        """Create intermediate display widget."""
        display_group = QGroupBox("Calculated Values", parent)
        layout = QFormLayout(display_group)

        layout.addRow("Result:", QLabel("--"))
        self.display_label = layout.itemAt(0, QFormLayout.ItemRole.FieldRole).widget()

        return display_group
```

---

### DefaultGroupBuilder

Default group builder that preserves the standard QGroupBox + QFormLayout pattern. Used automatically for groups without custom builders.

**Behavior:**

- Creates QGroupBox with formatted group name as title
- Uses QFormLayout with label-widget pairs
- Marks required fields with asterisk (*)
- Sorts properties by display_order

This builder maintains backward compatibility with the original form generation system.

**Example:**

```python
from dynamat.gui.builders import DefaultGroupBuilder

# Typically created internally, but can be used directly
builder = DefaultGroupBuilder(widget_factory)
group_widget, form_fields = builder.build_group("TestGroup", properties)

# group_widget is a QGroupBox with QFormLayout
# form_fields is dict of property URIs to FormField objects
```

---

## Group Builder Use Cases

### When to Use Custom Group Builders

Create a custom GroupBuilder when you need:

1. **Intermediate Display Widgets**: Show derived/calculated values between form fields
   - Example: Equipment properties display showing bar wave speed, gauge factors
   - Example: Real-time calculation results

2. **Custom Layouts**: Non-standard layouts beyond QFormLayout
   - Example: Multi-column layouts for compact display
   - Example: Grid layouts for grouped properties

3. **Dynamic Content**: Content that changes based on selections
   - Example: Conditional display panels
   - Example: Progressive disclosure

4. **Specialized Rendering**: Unique visualization needs
   - Example: Collapsible sections
   - Example: Tabbed content within a group
   - Example: Progress indicators or status displays

### When to Use Default Builder

Use the default builder (via `OntologyFormBuilder`) when:

- Standard label-widget pairs are sufficient
- No intermediate displays needed
- QGroupBox + QFormLayout layout works well
- Form is straightforward with no special rendering needs

**Most forms don't need custom builders** - the default rendering handles typical use cases.

---

## Advanced Group Builder Patterns

### Multi-Column Layout

```python
class MultiColumnGroupBuilder(GroupBuilder):
    def build_group(self, group_name, properties, parent=None):
        container = QWidget(parent)
        grid_layout = QGridLayout(container)

        widgets = self.create_widgets_for_group(properties)
        form_fields = {}

        # Arrange in 2 columns
        for i, prop in enumerate(sorted(properties, key=lambda p: p.display_order or 0)):
            if prop.uri not in widgets:
                continue

            row = i // 2
            col = (i % 2) * 2

            label = QLabel(prop.display_name or prop.name)
            grid_layout.addWidget(label, row, col)
            grid_layout.addWidget(widgets[prop.uri], row, col + 1)

            form_fields[prop.uri] = FormField(...)

        return container, form_fields
```

### Real-Time Calculations

```python
class CalculatingGroupBuilder(GroupBuilder):
    def build_group(self, group_name, properties, parent=None):
        container = QWidget(parent)
        layout = QVBoxLayout(container)

        # Standard form
        form_group, form_fields = self._create_standard_form(
            group_name, properties, container
        )
        layout.addWidget(form_group)

        # Calculation display
        calc_display = QLabel("Calculated: --")
        layout.addWidget(calc_display)
        container.calc_display = calc_display

        # Connect widgets to update calculation
        for field in form_fields.values():
            if hasattr(field.widget, 'valueChanged'):
                field.widget.valueChanged.connect(
                    lambda: self._update_calc(form_fields, calc_display)
                )

        return container, form_fields

    def _update_calc(self, form_fields, display):
        # Get values, calculate, update display
        pass
```

### Collapsible Sections

```python
from PyQt6.QtWidgets import QToolButton, QFrame

class CollapsibleGroupBuilder(GroupBuilder):
    def build_group(self, group_name, properties, parent=None):
        container = QWidget(parent)
        layout = QVBoxLayout(container)

        # Toggle button
        toggle = QToolButton()
        toggle.setText(f"▼ {group_name}")
        toggle.setCheckable(True)
        toggle.setChecked(True)
        layout.addWidget(toggle)

        # Collapsible content
        content = QFrame()
        content_layout = QVBoxLayout(content)
        # ... add form widgets to content_layout ...
        layout.addWidget(content)

        toggle.toggled.connect(content.setVisible)

        return container, form_fields
```

---

## Migration Guide

### From OntologyFormBuilder to CustomizableFormBuilder

**Existing code (no changes needed):**

```python
# This continues to work unchanged
builder = OntologyFormBuilder(ontology_manager)
form = builder.build_form("dyn:Specimen")
```

**Migrating to custom groups:**

```python
# 1. Change builder class
from dynamat.gui.builders import CustomizableFormBuilder
builder = CustomizableFormBuilder(ontology_manager)

# 2. Create and register custom builder
from my_app.builders import MyCustomGroupBuilder
custom_builder = MyCustomGroupBuilder(builder.widget_factory)
builder.register_group_builder("MyGroupName", custom_builder)

# 3. Build form (custom rendering applied automatically)
form = builder.build_form("dyn:MyClass")

# 4. Data operations work the same
data = builder.get_form_data(form)
```

**Checklist:**

- [ ] Create custom GroupBuilder subclass
- [ ] Move display creation logic to `_create_custom_display()` method
- [ ] Implement `build_group()` combining form + displays
- [ ] Register builder with group name matching `gui:hasFormGroup`
- [ ] Update page to use `CustomizableFormBuilder`
- [ ] Remove manual display creation code
- [ ] Test form creation and data operations
- [ ] Verify display updates work correctly

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

## Real-World Example: Equipment Properties Builder

The SHPB Equipment Page demonstrates the group builder pattern in production. See:
- **Implementation**: `dynamat/gui/widgets/shpb/pages/equipment_page.py` (nested `_EquipmentPropertiesBuilder` class)

### What It Does

The `EquipmentPropertiesGroupBuilder` creates an equipment configuration form with an intermediate display showing derived properties from selected equipment:

**Form Section** (standard):
- Incident Bar (combo box)
- Transmission Bar (combo box)
- Incident Strain Gauge (combo box)
- Transmission Strain Gauge (combo box)
- Momentum Trap Distance (unit value widget)

**Properties Display** (intermediate widget):
- Bar Wave Speed: Derived from selected bar's material
- Bar Cross Section: From selected bar geometry
- Bar Elastic Modulus: From selected bar's material
- Gauge Factors: From selected strain gauges
- Gauge Distances: From selected strain gauges

### Implementation Highlights

The equipment page defines a **nested builder class** that's only used by this page:

```python
class EquipmentPage(BaseSHPBPage):
    """Equipment configuration page with custom group rendering."""

    class _EquipmentPropertiesBuilder(GroupBuilder):
        """Nested builder for equipment group with properties display."""

        def build_group(self, group_name, properties, parent=None):
            container = QWidget(parent)
            layout = QVBoxLayout(container)

            # 1. Standard equipment selection form
            equipment_group, form_fields = self._create_equipment_form(
                group_name, properties, container
            )
            layout.addWidget(equipment_group)

            # 2. Intermediate display showing derived properties
            properties_display = self._create_properties_display(container)
            layout.addWidget(properties_display)

            # 3. Store label references for external updates
            container.wave_speed_label = self.wave_speed_label
            container.cross_section_label = self.cross_section_label
            # ... more labels ...

            return container, form_fields

    def _setup_ui(self):
        # Initialize customizable builder
        self.form_builder = CustomizableFormBuilder(self.ontology_manager)

        # Register nested builder for equipment group
        self.form_builder.register_group_builder(
            "EquipmentConfiguration",
            self._EquipmentPropertiesBuilder(self.form_builder.widget_factory)
        )

        # Build form (properties display automatically included)
        self.form_widget = self.form_builder.build_form(
            "dyn:SHPBTestingConfiguration"
        )

        # Find container and connect update handlers
        self._find_equipment_container()
        self._connect_equipment_handlers()
```

**Why nested class?** The builder is page-specific and tightly coupled to the page's update logic. Keeping it as a nested class:
- Clearly shows the builder is only for this page
- Reduces file complexity (no separate builder file needed)
- Makes the code easier to maintain in one place

### Update Mechanism

When equipment selections change, the page updates the display:

```python
def _update_properties_display(self):
    """Update display from selected equipment."""
    # Get selected incident bar
    bar_uri = self.get_form_field_value("hasIncidentBar")

    # Query bar properties from ontology
    bar_props = self.specimen_loader.get_multiple_properties(
        bar_uri, ['hasCrossSection', 'hasMaterial']
    )

    # Update display labels
    if bar_props.get('hasCrossSection'):
        self.cross_section_label.setText(f"{bar_props['hasCrossSection']:.2f} mm²")

    # Get material properties and update wave speed display
    # ... etc ...
```

### Key Benefits

1. **Automatic Display Generation**: Properties display created as part of form group
2. **Ontology-Driven**: Equipment options still come from ontology individuals
3. **Clean Separation**: Display logic in builder, update logic in page
4. **Reusable**: Same pattern applies to other forms needing intermediate displays

---

## References

1. PyQt6 Widgets Documentation: https://doc.qt.io/qtforpython-6/
2. PyQt6 Layouts: https://doc.qt.io/qtforpython-6/overviews/layout.html
3. Qt Signals and Slots: https://doc.qt.io/qtforpython-6/overviews/signalsandslots.html
4. Group Builder Refactor Summary: `../../REFACTOR_SUMMARY.md`
5. Equipment Page with Nested Builder: `../widgets/shpb/pages/equipment_page.py`
