# DynaMat GUI Module

The `dynamat.gui` module implements a PyQt6-based graphical user interface that automatically generates forms from RDF ontology definitions. This is version 2.0, featuring a completely refactored architecture with improved modularity, TTL-based constraint management, and enhanced extensibility.

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Key Components](#key-components)
- [How Forms are Generated](#how-forms-are-generated)
- [Quick Start](#quick-start)
- [Dependency System](#dependency-system)
- [API Reference](#api-reference)
- [Design Patterns](#design-patterns)
- [Extending the Module](#extending-the-module)

---

## Overview

### Purpose

The GUI module transforms RDF ontology definitions into interactive PyQt6 forms **without hard-coding**. Change the ontology annotations, reload the application, and forms automatically adapt to the new structure.

### Core Capabilities

- **Ontology-Driven Form Generation**: Reads ontology metadata to create forms
- **Widget Type Inference**: Automatically selects appropriate Qt widgets based on data types
- **QUDT Integration**: Measurement properties get unit selectors automatically
- **TTL-Based Constraints**: Field dependencies defined in ontology, not code
- **Multiple Layout Strategies**: Grouped, tabbed, single-column, two-column, grid
- **Real-Time Validation**: Widget-level, form-level, and SHACL validation
- **Template Support**: Pre-fill forms with configuration templates
- **Calculation Engine**: Automatic derived value calculations
- **ID Generation**: Template-based ID and code generation

### v2.0 Improvements

The v2.0 refactoring introduced:

1. **Separation of Concerns**: Specialized classes instead of monolithic builders
2. **TTL-Based Constraints**: Dependencies defined in ontology files
3. **Plugin Architecture**: Extensible widget, calculation, and generator registries
4. **Enhanced Testability**: Each component can be tested independently
5. **Performance Optimizations**: Form caching, widget reuse
6. **Better Error Handling**: Comprehensive validation and user feedback

---

## Architecture

### Directory Structure

```
dynamat/gui/
├── __init__.py                          # Public API exports
│
├── core/                                # Core functionality
│   ├── widget_factory.py                # Widget creation from metadata
│   ├── form_manager.py                  # Form creation coordination
│   ├── data_handler.py                  # Data extraction/population
│   └── form_validator.py                # Form validation
│
├── builders/                            # Form building orchestration
│   ├── ontology_form_builder.py         # Main facade for form creation
│   └── layout_manager.py                # Layout strategies
│
├── dependencies/                        # Dependency and calculation system
│   ├── dependency_manager.py            # TTL-based constraint management
│   ├── constraint_manager.py            # Loads/manages constraints
│   ├── calculation_engine.py            # Mathematical calculations
│   └── generation_engine.py             # ID/code generation
│
├── widgets/                             # UI components
│   ├── base/
│   │   └── unit_value_widget.py         # Measurement + unit selector
│   ├── forms/
│   │   └── specimen_form.py             # Example form implementation
│   ├── action_panel.py                  # Action buttons panel
│   └── terminal_widget.py               # Terminal/logging widget
│
├── app.py                               # Main QApplication
└── main_window.py                       # Main application window
```

### Component Relationships

```
                    ┌─────────────────────────────────┐
                    │   OntologyFormBuilder           │
                    │   (Facade - Simple API)         │
                    └───────────┬─────────────────────┘
                                │
                ┌───────────────┼───────────────┐
                ▼               ▼               ▼
    ┌──────────────────┐ ┌─────────────┐ ┌──────────────────┐
    │  FormManager     │ │ LayoutMgr   │ │ DependencyMgr    │
    │  (Coordination)  │ │ (Layouts)   │ │ (Constraints)    │
    └────────┬─────────┘ └─────────────┘ └──────────────────┘
             │
    ┌────────┼────────┐
    ▼        ▼        ▼
┌────────┐ ┌────────┐ ┌────────┐
│Widget  │ │Layout  │ │Data    │
│Factory │ │Manager │ │Handler │
└────────┘ └────────┘ └────────┘
    │
    ▼
┌──────────────────────────────┐
│ Widget Type Registry         │
│ - line_edit                  │
│ - combo                      │
│ - spinbox                    │
│ - double_spinbox             │
│ - unit_value ← UnitValueWidget│
│ - checkbox                   │
│ - date                       │
│ - text_area                  │
└──────────────────────────────┘

Supporting Components:
┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐
│ CalculationEngine│  │ GenerationEngine │  │ ConstraintManager│
│ (Derived values) │  │ (IDs, codes)     │  │ (Load TTL rules) │
└──────────────────┘  └──────────────────┘  └──────────────────┘
```

---

## Key Components

### 1. OntologyFormBuilder

**The main facade for form creation. Simplest API for building forms.**

```python
from dynamat.gui import OntologyFormBuilder

builder = OntologyFormBuilder(ontology_manager)
```

**Key Features:**
- High-level API that hides complexity
- Integrates FormManager, LayoutManager, DependencyManager
- Optional TTL-based constraint system
- Qt signal support for events

**Main Methods:**

```python
# Build form for any ontology class
form = builder.build_form("dyn:Specimen", style=FormStyle.GROUPED)

# Get/set data
data = builder.get_form_data(form)
builder.set_form_data(form, data_dict)

# Validate
errors = builder.validate_form(form)
is_valid = builder.is_form_valid(form)

# Refresh
builder.refresh_form(form)
```

**Qt Signals:**

```python
builder.form_created.connect(on_form_created)
builder.form_data_changed.connect(on_data_changed)
builder.form_error.connect(on_error)
```

---

### 2. WidgetFactory

**Creates appropriate Qt widgets from ontology property metadata.**

```python
from dynamat.gui import WidgetFactory

factory = WidgetFactory(ontology_manager)
widget = factory.create_widget(property_metadata)
```

**Widget Type Mapping:**

| Property Definition | Qt Widget | Widget Type |
|---------------------|-----------|-------------|
| `xsd:string` | `QLineEdit` | `line_edit` |
| `xsd:string` + valid values | `QComboBox` | `combo` |
| `xsd:integer` | `QSpinBox` | `spinbox` |
| `xsd:double` | `QDoubleSpinBox` | `double_spinbox` |
| `xsd:double` + QUDT | `UnitValueWidget` | `unit_value` |
| `xsd:boolean` | `QCheckBox` | `checkbox` |
| `xsd:date` | `QDateEdit` | `date` |
| `owl:ObjectProperty` | `QComboBox` | `object_combo` |
| String with "note" | `QTextEdit` | `text_area` |

**Plugin Architecture:**

```python
# Register custom widget type
def create_custom_widget(property_metadata):
    widget = MyCustomWidget()
    # ... configure widget ...
    return widget

factory.register_widget_type("my_custom", create_custom_widget)

# Widget metadata specifies: dyn:hasWidgetType "my_custom"
```

**Automatic Features:**
- Required field styling (orange border, asterisk)
- Dropdown population from ontology individuals
- Unit selector integration for measurements
- Tooltip from property description

---

### 3. FormManager

**Orchestrates complete form creation using specialized components.**

```python
from dynamat.gui import FormManager, FormStyle

form_manager = FormManager(ontology_manager)
```

**Form Creation:**

```python
# Create form
form = form_manager.create_form("dyn:Specimen", style=FormStyle.GROUPED)

# Form widget has special attributes:
# - form.form_fields: Dict[property_uri, FormField]
# - form.class_uri: str
# - form.form_style: FormStyle
# - form.class_metadata: ClassMetadata
```

**FormField Data Class:**

```python
@dataclass
class FormField:
    property_uri: str                # "dyn:hasOriginalLength"
    widget: QWidget                  # The actual Qt widget
    label: QLabel                    # Associated label
    property_metadata: PropertyMetadata  # From ontology
```

**Supported Form Styles:**

```python
class FormStyle(Enum):
    GROUPED = "grouped"          # Properties in QGroupBox sections (default)
    SIMPLE = "simple"            # Single column, no grouping
    TWO_COLUMN = "two_column"    # Side-by-side groups
    TABBED = "tabbed"            # Each group in a tab
```

**Form Operations:**

```python
# Data handling
data = form_manager.get_form_data(form_widget)
form_manager.set_form_data(form_widget, data)

# Validation
errors = form_manager.validate_form(form_widget)

# Maintenance
form_manager.clear_form(form_widget)
form_manager.clear_cache()
```

---

### 4. LayoutManager

**Handles form layout creation and widget organization.**

```python
from dynamat.gui import LayoutManager, LayoutStyle

layout_manager = LayoutManager()
```

**Layout Strategies:**

```python
class LayoutStyle(Enum):
    GROUPED_FORM = "grouped"      # QGroupBox sections with QFormLayout
    TABBED_FORM = "tabbed"        # QTabWidget with tabs per group
    SINGLE_COLUMN = "single"      # Simple QFormLayout
    TWO_COLUMN = "two_column"     # Two columns of groups
    GRID_LAYOUT = "grid"          # Grid arrangement
```

**Layout Creation:**

```python
# Create layout from organized groups
form_widget = layout_manager.create_grouped_form(
    form_groups={"Geometry": [prop1, prop2], "Material": [prop3]},
    widgets={"dyn:prop1": widget1, "dyn:prop2": widget2, ...}
)

# Or use specific strategies
form_widget = layout_manager.create_tabbed_form(form_groups, widgets)
form_widget = layout_manager.create_single_column_form(properties, widgets)
```

**Smart Features:**
- Automatic group ordering based on `group_order`
- Property ordering within groups by `display_order`
- Scrollable containers for large forms
- Proper label formatting (camelCase → Title Case)
- Required field visual indicators

---

### 5. FormDataHandler

**Handles data extraction and population for all widget types.**

```python
from dynamat.gui import FormDataHandler

handler = FormDataHandler()
```

**Data Operations:**

```python
# Extract all form data
data = handler.extract_form_data(form_widget)
# Returns: Dict[property_uri, value]

# Populate form with data
handler.populate_form_data(form_widget, data_dict)

# Validate form data
errors = handler.validate_form_data(form_widget)
# Returns: Dict[property_uri, List[error_message]]

# Get form summary
summary = handler.get_form_summary(form_widget)
# Returns: Dict with filled_fields, total_fields, completeness, etc.
```

**Type-Safe Value Handling:**

The handler knows how to extract/set values for each widget type:

```python
# QLineEdit → str
# QSpinBox → int
# QDoubleSpinBox → float
# QCheckBox → bool
# QDateEdit → str (ISO format)
# QComboBox → str (selected item data)
# UnitValueWidget → Dict {'value': float, 'unit': str, 'unit_symbol': str}
```

---

### 6. DependencyManager

**Manages form widget dependencies using TTL-based constraint definitions.**

```python
from dynamat.gui import DependencyManager

dep_manager = DependencyManager(
    ontology_manager=manager,
    constraint_directory="dynamat/ontology/constraints"
)
```

**Setup Dependencies:**

```python
# Apply constraints to form
dep_manager.setup_dependencies(form_widget, "dyn:Specimen")

# Constraints are loaded from TTL files and evaluated in real-time
# when form field values change
```

**Constraint Types:**

```python
class ConstraintType(Enum):
    VISIBILITY = "visibility"          # Show/hide fields
    REQUIREMENT = "requirement"        # Required/optional
    CALCULATION = "calculation"        # Calculate derived values
    GENERATION = "generation"          # Generate IDs, codes
    MUTUAL_EXCLUSION = "mutual_exclusion"  # Either/or fields
```

**Trigger Logic:**

```python
class TriggerLogic(Enum):
    ANY = "any"    # If any trigger condition is met
    ALL = "all"    # If all trigger conditions are met
    XOR = "xor"    # If exactly one trigger condition is met
```

**Actions:**

```python
class Action(Enum):
    SHOW = "show"
    HIDE = "hide"
    REQUIRE = "require"
    OPTIONAL = "optional"
    CALCULATE = "calculate"
    GENERATE = "generate"
    ENABLE = "enable"
    DISABLE = "disable"
```

**Example TTL Constraint:**

```turtle
# If material is Composite, show fiber-related fields
gui:ShowFiberFieldsWhenComposite a gui:VisibilityConstraint ;
    gui:forClass dyn:Specimen ;
    gui:triggers dyn:hasMaterial ;
    gui:whenValue dyn:CompositeMaterial ;
    gui:affects (dyn:hasFiberType dyn:hasFiberVolumeFraction dyn:hasFiberOrientation) ;
    gui:action gui:show ;
    gui:priority 100 .
```

**Constraint Evaluation Flow:**

```
User changes field value
       ↓
Qt signal emitted (valueChanged, currentTextChanged, etc.)
       ↓
DependencyManager receives signal
       ↓
Find all constraints triggered by this property
       ↓
Evaluate each constraint's whenValue condition
       ↓
If condition met, apply action to affected fields
       ↓
UI updates automatically (show/hide, enable/disable, etc.)
```

---

### 7. CalculationEngine

**Mathematical calculations for derived field values.**

```python
from dynamat.gui import CalculationEngine

calc_engine = CalculationEngine()
```

**Built-in Calculations:**

**Area Calculations:**
```python
area = calc_engine.calculate('circular_area_from_diameter', diameter=10.0)
# Returns: 78.54 mm²

area = calc_engine.calculate('circular_area_from_radius', radius=5.0)
area = calc_engine.calculate('rectangular_area', length=10.0, width=5.0)
area = calc_engine.calculate('square_area', side=10.0)
```

**Volume Calculations:**
```python
volume = calc_engine.calculate('cylinder_volume', diameter=10.0, length=50.0)
volume = calc_engine.calculate('rectangular_volume', length=10, width=5, height=3)
volume = calc_engine.calculate('cube_volume', side=10.0)
volume = calc_engine.calculate('sphere_volume', diameter=10.0)
```

**Mass/Density:**
```python
density = calc_engine.calculate('density', mass=100.0, volume=50.0)
mass = calc_engine.calculate('mass_from_density', density=2700.0, volume=50.0)
volume = calc_engine.calculate('volume_from_mass', mass=135000.0, density=2700.0)
```

**Engineering:**
```python
strain_rate = calc_engine.calculate('strain_rate', velocity=15.0, length=10.0)
stress = calc_engine.calculate('stress', force=1000.0, area=78.54)
force = calc_engine.calculate('force', stress=450.0, area=78.54)
```

**Unit Conversion:**
```python
result = calc_engine.calculate('unit_conversion',
    value=10.0,
    from_unit='unit:MilliM',
    to_unit='unit:CentiM'
)
# Returns: 1.0 cm
```

**Plugin Architecture:**

```python
# Register custom calculation
def calculate_custom(param1, param2):
    return param1 * param2 + 10

calc_engine.register_calculation('my_calculation', calculate_custom)

# Use it
result = calc_engine.calculate('my_calculation', param1=5, param2=3)
```

---

### 8. GenerationEngine

**Template-based value generation for IDs, codes, and timestamps.**

```python
from dynamat.gui import GenerationEngine

gen_engine = GenerationEngine(ontology_manager)
```

**Built-in Generators:**

**Specimen ID:**
```python
specimen_id = gen_engine.generate(
    "DYNML-{materialCode}-{sequence}",
    {"materialCode": "AL6061", "sequence": 5}
)
# Returns: "DYNML-AL6061-00005"
```

**Test ID:**
```python
test_id = gen_engine.generate(
    "{specimenID}_{testType}_{date}",
    {
        "specimenID": "DYNML-AL6061-00005",
        "testType": "SHPB",
        "date": "20250115"
    }
)
# Returns: "DYNML-AL6061-00005_SHPB_20250115"
```

**Batch ID:**
```python
batch_id = gen_engine.generate(
    "BATCH-{materialCode}-{year}-{month}",
    {"materialCode": "AL6061", "year": 2025, "month": 1}
)
# Returns: "BATCH-AL6061-2025-01"
```

**Timestamps:**
```python
timestamp = gen_engine.generate("timestamp", {})
# Returns: "2025-01-15T14:30:45"

date = gen_engine.generate("date", {})
# Returns: "2025-01-15"

time = gen_engine.generate("time", {})
# Returns: "14:30:45"
```

**Auto-Increment:**
```python
# Queries ontology for highest sequence number
next_id = gen_engine.generate_auto_increment(
    "DYNML-{materialCode}-{sequence}",
    {"materialCode": "AL6061"}
)
# If DYNML-AL6061-00005 exists, returns: "DYNML-AL6061-00006"
```

---

### 9. UnitValueWidget

**Composite widget for measurements with units.**

```python
from dynamat.gui.widgets.base import UnitValueWidget

widget = UnitValueWidget(
    default_unit="unit:MilliM",
    available_units=unit_info_list,
    property_uri="dyn:hasOriginalLength"
)
```

**Structure:**
```
┌───────────────────────────────────────┐
│  UnitValueWidget                      │
│  ┌──────────────────┬──────────────┐ │
│  │ QDoubleSpinBox   │  QComboBox   │ │
│  │  [10.0        ]  │  [mm     ▼] │ │
│  └──────────────────┴──────────────┘ │
└───────────────────────────────────────┘
```

**Features:**
- Automatic unit dropdown population from QUDT
- Default unit selection
- Unit conversion support
- Qt signals: `valueChanged`, `unitChanged`, `dataChanged`

**API:**

```python
# Get data
data = widget.getData()
# Returns: {'value': 10.0, 'unit': 'unit:MilliM', 'unit_symbol': 'mm'}

# Set data
widget.setData(value=15.0, unit='unit:CentiM')

# Get separate values
value = widget.getValue()      # 15.0
unit = widget.getUnit()        # 'unit:CentiM'
symbol = widget.getUnitSymbol()  # 'cm'

# Convert to different unit
widget.convertToUnit('unit:MilliM')  # Value becomes 150.0
```

---

## How Forms are Generated

The complete flow from ontology to interactive form:

### 1. Ontology Metadata Extraction

```python
# OntologyManager reads TTL files and extracts metadata
metadata = ontology_manager.get_class_metadata_for_form("dyn:Specimen")

# Returns ClassMetadata with:
# - properties: List[PropertyMetadata]
# - form_groups: Dict[str, List[PropertyMetadata]]
```

**Example Property Metadata:**
```python
PropertyMetadata(
    uri="dyn:hasOriginalLength",
    name="hasOriginalLength",
    display_name="Original Length (mm)",
    description="Initial length of specimen before testing",
    data_type="xsd:double",
    form_group="GeometryDimensions",
    display_order=3,
    group_order=2,
    is_required=True,
    quantity_kind="http://qudt.org/vocab/quantitykind/Length",
    default_unit="unit:MilliM",
    compatible_units=[UnitInfo(...), ...]
)
```

### 2. Widget Creation

```python
# WidgetFactory creates appropriate Qt widget for each property
widget_factory = WidgetFactory(ontology_manager)

widgets = {}
for property in metadata.properties:
    widget = widget_factory.create_widget(property)
    widgets[property.uri] = widget

# For the example above, creates:
# UnitValueWidget(default_unit="unit:MilliM", compatible_units=[...])
```

### 3. Layout Organization

```python
# LayoutManager arranges widgets into groups
layout_manager = LayoutManager()

# Properties are already grouped by GUISchemaBuilder
form_groups = {
    "Identification": [hasSpecimenID, hasMaterial, hasStructure],
    "GeometryDimensions": [hasOriginalLength, hasOriginalDiameter, hasOriginalMass],
    "Manufacturing": [hasCreationDate, hasManufacturingMethod],
    # ...
}

# Create grouped layout
form_widget = layout_manager.create_grouped_form(form_groups, widgets)
```

**Resulting Layout:**

```
┌──────────────────────────────────────────────────┐
│ Identification                                   │
│ ┌──────────────────────────────────────────────┐│
│ │ Specimen ID:     [SPN-AL6061-001         ]  ││
│ │ Material:        [Al6061-T6              ▼] ││
│ │ Structure:       [Monolithic             ▼] ││
│ └──────────────────────────────────────────────┘│
│                                                  │
│ Geometry Dimensions                              │
│ ┌──────────────────────────────────────────────┐│
│ │ Original Length:  [10.0    ] [mm         ▼] ││
│ │ Original Diameter:[6.35    ] [mm         ▼] ││
│ │ Original Mass:    [0.851   ] [g          ▼] ││
│ └──────────────────────────────────────────────┘│
│                                                  │
│ Manufacturing                                    │
│ ┌──────────────────────────────────────────────┐│
│ │ Creation Date:    [2025-01-15            📅]││
│ │ Manufacturing:    [Machining             ▼] ││
│ └──────────────────────────────────────────────┘│
└──────────────────────────────────────────────────┘
```

### 4. Dependency Setup (Optional)

```python
# DependencyManager loads constraints from TTL files
dep_manager = DependencyManager(ontology_manager, "dynamat/ontology/constraints")
dep_manager.setup_dependencies(form_widget, "dyn:Specimen")

# Now constraints are active:
# - If user selects "Composite" material → fiber fields appear
# - If user enters diameter → cross-section area auto-calculates
# - If user changes material → specimen ID auto-generates
```

### 5. Final Form Widget

```python
# FormManager coordinates everything
form_manager = FormManager(ontology_manager)
complete_form = form_manager.create_form("dyn:Specimen", FormStyle.GROUPED)

# Form has special attributes for data access:
form_fields = complete_form.form_fields  # Dict[property_uri, FormField]
class_uri = complete_form.class_uri      # "dyn:Specimen"
metadata = complete_form.class_metadata  # ClassMetadata object
```

---

## Quick Start

### Simple Form Creation

```python
from dynamat.ontology import OntologyManager
from dynamat.gui import OntologyFormBuilder

# Initialize
ontology_manager = OntologyManager()
form_builder = OntologyFormBuilder(ontology_manager)

# Build form
form = form_builder.build_form("dyn:Specimen")

# Display in window
from PyQt6.QtWidgets import QApplication, QMainWindow

app = QApplication([])
window = QMainWindow()
window.setCentralWidget(form)
window.show()
app.exec()
```

### Get/Set Form Data

```python
# Get all form data
data = form_builder.get_form_data(form)
print(data)
# {
#     'dyn:hasSpecimenID': 'SPN-AL6061-001',
#     'dyn:hasMaterial': 'dyn:Al6061_T6',
#     'dyn:hasOriginalLength': {'value': 10.0, 'unit': 'unit:MilliM', 'unit_symbol': 'mm'},
#     ...
# }

# Populate form with existing data
existing_data = {
    'dyn:hasSpecimenID': 'SPN-SS316-042',
    'dyn:hasMaterial': 'dyn:SS316L',
    'dyn:hasOriginalLength': {'value': 12.0, 'unit': 'unit:MilliM'}
}
form_builder.set_form_data(form, existing_data)
```

### Form Validation

```python
# Validate form
errors = form_builder.validate_form(form)

if errors:
    print("Validation errors:")
    for prop_uri, error_msgs in errors.items():
        print(f"{prop_uri}:")
        for msg in error_msgs:
            print(f"  - {msg}")
else:
    print("✓ Form is valid")

# Quick check
if form_builder.is_form_valid(form):
    # Save data...
    pass
```

### Custom Widget Creation

```python
from dynamat.gui import WidgetFactory

# Get property metadata
class_metadata = ontology_manager.get_class_metadata_for_form("dyn:Specimen")
length_property = next(p for p in class_metadata.properties if p.name == "hasOriginalLength")

# Create widget
factory = WidgetFactory(ontology_manager)
widget = factory.create_widget(length_property)

# Widget is a UnitValueWidget, ready to use
widget.setData(value=10.0, unit='unit:MilliM')
```

---

## Dependency System

The v2.0 dependency system uses TTL files to define form behavior, making it declarative and ontology-driven.

### Constraint Definition

Create TTL file in `dynamat/ontology/constraints/`:

```turtle
# gui_specimen_rules.ttl
@prefix gui: <https://dynamat.utep.edu/gui#> .
@prefix dyn: <https://dynamat.utep.edu/ontology#> .

# Show fiber fields when material is composite
gui:ShowFiberFieldsWhenComposite a gui:VisibilityConstraint ;
    gui:forClass dyn:Specimen ;
    gui:triggers dyn:hasMaterial ;
    gui:whenValue dyn:CompositeMaterial ;
    gui:affects (dyn:hasFiberType dyn:hasFiberVolumeFraction dyn:hasFiberOrientation) ;
    gui:action gui:show ;
    gui:priority 100 .

# Calculate cross-section from diameter
gui:CalculateCrossSection a gui:CalculationConstraint ;
    gui:forClass dyn:Specimen ;
    gui:triggers dyn:hasOriginalDiameter ;
    gui:affects dyn:hasOriginalCrossSection ;
    gui:action gui:calculate ;
    gui:calculationType "circular_area_from_diameter" ;
    gui:priority 50 .

# Generate specimen ID
gui:GenerateSpecimenID a gui:GenerationConstraint ;
    gui:forClass dyn:Specimen ;
    gui:triggers (dyn:hasMaterial dyn:hasSequenceNumber) ;
    gui:affects dyn:hasSpecimenID ;
    gui:action gui:generate ;
    gui:template "DYNML-{materialCode}-{sequence}" ;
    gui:priority 200 .
```

### Constraint Application

```python
from dynamat.gui import DependencyManager

# Initialize with constraint directory
dep_manager = DependencyManager(
    ontology_manager=ontology_manager,
    constraint_directory="dynamat/ontology/constraints"
)

# Apply to form (loads and activates all constraints for the class)
dep_manager.setup_dependencies(form_widget, "dyn:Specimen")

# Now constraints are active:
# - Select "Composite" material → fiber fields show
# - Enter diameter → cross-section calculates
# - Change material/sequence → ID regenerates
```

### Constraint Types Explained

**1. Visibility Constraints** - Show/hide fields

```turtle
gui:ShowLubricationTypeWhenUsed a gui:VisibilityConstraint ;
    gui:triggers dyn:hasLubricationUsed ;
    gui:whenValue true ;
    gui:affects dyn:hasLubricationType ;
    gui:action gui:show .
```

**2. Requirement Constraints** - Make fields required/optional

```turtle
gui:RequireOperatorNameWhenHuman a gui:RequirementConstraint ;
    gui:triggers dyn:hasOperatorType ;
    gui:whenValue "Human" ;
    gui:affects dyn:hasOperatorName ;
    gui:action gui:require .
```

**3. Calculation Constraints** - Auto-calculate values

```turtle
gui:CalculateMassFromDensity a gui:CalculationConstraint ;
    gui:triggers (dyn:hasDensity dyn:hasVolume) ;
    gui:affects dyn:hasMass ;
    gui:calculationType "mass_from_density" ;
    gui:action gui:calculate .
```

**4. Generation Constraints** - Generate IDs/codes

```turtle
gui:GenerateBatchID a gui:GenerationConstraint ;
    gui:triggers (dyn:hasMaterialCode dyn:hasYear dyn:hasMonth) ;
    gui:affects dyn:hasBatchID ;
    gui:template "BATCH-{materialCode}-{year}-{month}" ;
    gui:action gui:generate .
```

**5. Mutual Exclusion** - Either/or fields

```turtle
gui:DiameterOrWidthHeight a gui:MutualExclusionConstraint ;
    gui:affects (dyn:hasDiameter dyn:hasWidth dyn:hasHeight) ;
    gui:action gui:mutual_exclude .
```

---

## API Reference

### Public API (`__init__.py`)

```python
from dynamat.gui import (
    # Main facade
    OntologyFormBuilder,

    # Core components
    WidgetFactory,
    FormManager,
    FormDataHandler,
    LayoutManager,

    # Dependencies
    DependencyManager,
    CalculationEngine,
    GenerationEngine,

    # Widgets
    UnitValueWidget,

    # Enums
    FormStyle,
    LayoutStyle,
    ConstraintType,
    TriggerLogic,
    Action,

    # Data classes
    FormField,
)
```

### OntologyFormBuilder API

```python
class OntologyFormBuilder(QObject):
    # Signals
    form_created = pyqtSignal(QWidget)
    form_data_changed = pyqtSignal(dict)
    form_error = pyqtSignal(str)

    def __init__(self, ontology_manager, enable_dependencies=True):
        """Initialize form builder"""

    def build_form(self, class_uri: str, style: FormStyle = FormStyle.GROUPED) -> QWidget:
        """Build complete form for class"""

    def get_form_data(self, form_widget: QWidget) -> Dict[str, Any]:
        """Extract all form data"""

    def set_form_data(self, form_widget: QWidget, data: Dict[str, Any]) -> None:
        """Populate form with data"""

    def validate_form(self, form_widget: QWidget) -> Dict[str, List[str]]:
        """Validate form, return errors"""

    def is_form_valid(self, form_widget: QWidget) -> bool:
        """Quick validation check"""

    def refresh_form(self, form_widget: QWidget) -> None:
        """Refresh form (reload from ontology)"""
```

### WidgetFactory API

```python
class WidgetFactory:
    def __init__(self, ontology_manager):
        """Initialize widget factory"""

    def create_widget(self, property_metadata: PropertyMetadata) -> QWidget:
        """Create appropriate widget for property"""

    def register_widget_type(self, widget_type: str, creator_function: Callable) -> None:
        """Register custom widget type"""

    def get_supported_types(self) -> List[str]:
        """Get list of supported widget types"""
```

### FormManager API

```python
class FormManager:
    def __init__(self, ontology_manager):
        """Initialize form manager"""

    def create_form(self, class_uri: str, style: FormStyle) -> QWidget:
        """Create complete form"""

    def get_form_data(self, form_widget: QWidget) -> Dict[str, Any]:
        """Extract form data"""

    def set_form_data(self, form_widget: QWidget, data: Dict[str, Any]) -> None:
        """Populate form"""

    def validate_form(self, form_widget: QWidget) -> Dict[str, List[str]]:
        """Validate form"""

    def clear_form(self, form_widget: QWidget) -> None:
        """Clear all fields"""

    def clear_cache(self) -> None:
        """Clear form cache"""
```

---

## Design Patterns

### 1. Facade Pattern

**OntologyFormBuilder** provides simple API hiding complex subsystems:

```python
# Simple facade API
builder = OntologyFormBuilder(ontology_manager)
form = builder.build_form("dyn:Specimen")

# Behind the scenes:
# - FormManager coordinates
# - WidgetFactory creates widgets
# - LayoutManager arranges them
# - DependencyManager sets up constraints
# - FormDataHandler manages data
```

### 2. Strategy Pattern

**LayoutManager** supports different layout strategies:

```python
# Different strategies for same data
layout_mgr.create_grouped_form(groups, widgets)  # Strategy: grouped
layout_mgr.create_tabbed_form(groups, widgets)   # Strategy: tabbed
layout_mgr.create_single_column_form(props, widgets)  # Strategy: single column
```

### 3. Plugin Architecture

**WidgetFactory**, **CalculationEngine**, **GenerationEngine** are all extensible:

```python
# Register custom widget
factory.register_widget_type("my_widget", create_my_widget)

# Register custom calculation
calc_engine.register_calculation("my_calc", calculate_my_value)

# Register custom generator
gen_engine.register_generator("my_gen", generate_my_value)
```

### 4. Observer Pattern

Qt signals/slots for reactive updates:

```python
# Field change triggers constraint evaluation
widget.valueChanged.connect(dep_manager.on_value_changed)

# Constraint evaluation triggers UI updates
dep_manager.show_widget(dependent_widget)
dep_manager.calculate_value(target_widget, calculation_type)
```

### 5. Separation of Concerns

Each component has single responsibility:

- **WidgetFactory**: Creates widgets only
- **LayoutManager**: Arranges widgets only
- **FormDataHandler**: Handles data only
- **DependencyManager**: Manages constraints only
- **FormManager**: Coordinates all of the above

---

## Extending the Module

### Adding Custom Widget Type

```python
from dynamat.gui import WidgetFactory
from PyQt6.QtWidgets import QWidget, QHBoxLayout, QSlider, QLabel

def create_slider_widget(property_metadata):
    """Custom slider widget with value label"""
    container = QWidget()
    layout = QHBoxLayout()

    slider = QSlider(Qt.Orientation.Horizontal)
    slider.setMinimum(0)
    slider.setMaximum(100)

    label = QLabel("0")
    slider.valueChanged.connect(lambda v: label.setText(str(v)))

    layout.addWidget(slider)
    layout.addWidget(label)
    container.setLayout(layout)

    # Add getValue/setValue methods for FormDataHandler
    container.getValue = slider.value
    container.setValue = slider.setValue

    return container

# Register
factory = WidgetFactory(ontology_manager)
factory.register_widget_type("slider", create_slider_widget)

# Use in ontology:
# dyn:hasPropertyName dyn:hasWidgetType "slider" .
```

### Adding Custom Calculation

```python
from dynamat.gui import CalculationEngine

def calculate_custom_stress(load, diameter, safety_factor=1.0):
    """Calculate stress with safety factor"""
    import math
    area = math.pi * (diameter / 2) ** 2
    return (load / area) / safety_factor

# Register
calc_engine = CalculationEngine()
calc_engine.register_calculation("custom_stress", calculate_custom_stress)

# Use in constraint TTL:
# gui:calculationType "custom_stress" .
```

### Adding Custom Layout Strategy

```python
from dynamat.gui import LayoutManager
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout

class CustomLayoutManager(LayoutManager):
    def create_custom_layout(self, form_groups, widgets):
        """Custom three-column layout"""
        main_widget = QWidget()
        main_layout = QHBoxLayout()

        # Create three columns
        col1, col2, col3 = QVBoxLayout(), QVBoxLayout(), QVBoxLayout()

        # Distribute groups across columns...
        # (implementation details)

        main_layout.addLayout(col1)
        main_layout.addLayout(col2)
        main_layout.addLayout(col3)
        main_widget.setLayout(main_layout)

        return main_widget
```

---

## Performance Considerations

### Form Caching

FormManager caches created forms for reuse:

```python
# First call: creates form
form1 = form_manager.create_form("dyn:Specimen")

# Subsequent calls: returns cached form (fast)
form2 = form_manager.create_form("dyn:Specimen")

# Clear cache when ontology changes
form_manager.clear_cache()
```

### Widget Reuse

Avoid recreating widgets when possible:

```python
# GOOD: Reuse existing form, just update data
form_builder.set_form_data(existing_form, new_data)

# LESS GOOD: Recreate entire form
new_form = form_builder.build_form("dyn:Specimen")
```

### Lazy Loading

Load widgets only when needed:

```python
# Tabbed forms only create tab contents when tab is selected
# (reduces initial load time for large forms)
```

---

## Troubleshooting

**Issue**: Form doesn't update after ontology changes
**Solution**: Clear caches: `form_manager.clear_cache()` and `ontology_manager.clear_caches()`

**Issue**: UnitValueWidget shows no units
**Solution**: Ensure property has `qudt:hasQuantityKind` annotation and QUDT ontology is loaded

**Issue**: Constraints not working
**Solution**: Check TTL syntax in constraint files, ensure `enable_dependencies=True` in OntologyFormBuilder

**Issue**: Custom widget not appearing
**Solution**: Verify registration with `factory.register_widget_type()` before form creation

**Issue**: Form validation failing unexpectedly
**Solution**: Check SHACL shapes in ontology, ensure required fields are marked correctly

---

## Dependencies

- **PyQt6**: GUI framework
- **dynamat.ontology**: Ontology module for metadata
- **rdflib**: For parsing constraint TTL files

---

## Further Reading

- [PyQt6 Documentation](https://www.riverbankcomputing.com/static/Docs/PyQt6/)
- [Qt Designer Manual](https://doc.qt.io/qt-6/qtdesigner-manual.html)
- [Model/View Programming](https://doc.qt.io/qt-6/model-view-programming.html)
