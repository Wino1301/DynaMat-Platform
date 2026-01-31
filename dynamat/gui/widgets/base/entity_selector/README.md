# Entity Selector Module

This module provides reusable components for selecting ontology entity instances from the DynaMat database. It supports both embedded widgets and modal dialogs with SPARQL-based filtering, configurable display properties, and composable UI components.

## Architecture Overview

```
Entity Selector Module
       |
       +---> Configuration
       |        +---> EntitySelectorConfig (dataclass)
       |        +---> SelectionMode (enum)
       |
       +---> Composable Components
       |        +---> FilterPanel (dropdowns + search)
       |        +---> DetailsPanel (property display)
       |
       +---> Main Widgets
                +---> EntitySelectorWidget (embeddable)
                +---> EntitySelectorDialog (modal)
```

## Module Exports

```python
from dynamat.gui.widgets.base.entity_selector import (
    # Configuration
    EntitySelectorConfig,     # Configuration dataclass
    SelectionMode,            # SINGLE or MULTIPLE

    # Composable Components
    FilterPanel,              # Filter dropdowns + search
    DetailsPanel,             # Selected entity details

    # Main Widgets
    EntitySelectorWidget,     # Embeddable selection widget
    EntitySelectorDialog,     # Modal dialog wrapper
)

# Also available from parent modules
from dynamat.gui.widgets.base import EntitySelectorWidget, EntitySelectorDialog
from dynamat.gui.widgets import EntitySelectorWidget, EntitySelectorDialog
```

---

## Quick Start

### Embedded Widget (e.g., in Wizard Page)

```python
from dynamat.gui.widgets.base.entity_selector import (
    EntitySelectorConfig, EntitySelectorWidget
)

# Configure the selector
config = EntitySelectorConfig(
    class_uri="https://dynamat.utep.edu/ontology#Specimen",
    display_properties=[
        "https://dynamat.utep.edu/ontology#hasSpecimenID",
        "https://dynamat.utep.edu/ontology#hasMaterial",
    ],
    filter_properties=["https://dynamat.utep.edu/ontology#hasMaterial"],
    show_details_panel=True,
)

# Create widget
selector = EntitySelectorWidget(config, query_builder=qb, ontology_manager=om)
selector.entity_selected.connect(self._on_entity_selected)
layout.addWidget(selector)
```

### Modal Dialog (e.g., "Load Existing" Button)

```python
from dynamat.gui.widgets.base.entity_selector import (
    EntitySelectorConfig, EntitySelectorDialog
)

# Use static method for quick selection
data = EntitySelectorDialog.select_entity(
    config=EntitySelectorConfig(
        class_uri="https://dynamat.utep.edu/ontology#Specimen",
        display_properties=["dyn:hasSpecimenID", "dyn:hasMaterial"],
    ),
    query_builder=self.query_builder,
    title="Load Existing Specimen",
    parent=self
)

if data:
    self.load_specimen(data)
```

---

## EntitySelectorConfig

Configuration dataclass that defines all widget behavior.

### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `class_uri` | str | **required** | Full URI of ontology class to select from |
| `display_properties` | List[str] | `[]` | Property URIs for table columns |
| `property_labels` | Dict[str, str] | `None` | Column header labels |
| `filter_properties` | List[str] | `None` | Properties with filter dropdowns |
| `filter_labels` | Dict[str, str] | `None` | Filter dropdown labels |
| `details_properties` | List[str] | `None` | Properties shown in details panel |
| `details_labels` | Dict[str, str] | `None` | Details panel labels |
| `selection_mode` | SelectionMode | `SINGLE` | Single or multiple selection |
| `show_details_panel` | bool | `True` | Show details panel below table |
| `show_search_box` | bool | `True` | Show text search box |
| `show_refresh_button` | bool | `True` | Show refresh button |
| `data_directory` | Path | `None` | Directory to scan for instances |
| `file_pattern` | str | `"*.ttl"` | Glob pattern for TTL files |
| `id_property` | str | `None` | Property URI used as primary ID |

### Property URI Normalization

The config automatically normalizes property URIs. All these formats work:

```python
# Full URI
"https://dynamat.utep.edu/ontology#hasSpecimenID"

# Prefixed name
"dyn:hasSpecimenID"

# Local name only (assumes DynaMat namespace)
"hasSpecimenID"
```

### Helper Methods

```python
config = EntitySelectorConfig(
    class_uri="https://dynamat.utep.edu/ontology#Specimen",
    display_properties=["dyn:hasSpecimenID", "hasMaterial"],
    property_labels={"dyn:hasSpecimenID": "Specimen ID"},
)

# Get display label (uses property_labels or auto-generates)
label = config.get_property_label("dyn:hasSpecimenID")  # "Specimen ID"
label = config.get_property_label("dyn:hasMaterial")    # "Material" (auto)

# Normalize to full URI
uri = config.normalize_property_uri("hasSpecimenID")
# "https://dynamat.utep.edu/ontology#hasSpecimenID"

# Get all normalized URIs
props = config.get_normalized_display_properties()
# ["https://dynamat.utep.edu/ontology#hasSpecimenID",
#  "https://dynamat.utep.edu/ontology#hasMaterial"]
```

### Complete Example

```python
DYN_NS = "https://dynamat.utep.edu/ontology#"

config = EntitySelectorConfig(
    class_uri=f"{DYN_NS}Specimen",

    # Table columns
    display_properties=[
        f"{DYN_NS}hasSpecimenID",
        f"{DYN_NS}hasMaterial",
        f"{DYN_NS}hasShape",
        f"{DYN_NS}hasStructure",
        f"{DYN_NS}hasBatchID",
    ],
    property_labels={
        f"{DYN_NS}hasSpecimenID": "Specimen ID",
        f"{DYN_NS}hasMaterial": "Material",
        f"{DYN_NS}hasShape": "Shape",
        f"{DYN_NS}hasStructure": "Structure",
        f"{DYN_NS}hasBatchID": "Batch",
    },

    # Filter dropdowns
    filter_properties=[f"{DYN_NS}hasMaterial"],
    filter_labels={f"{DYN_NS}hasMaterial": "Material"},

    # Details panel
    details_properties=[
        f"{DYN_NS}hasSpecimenID",
        f"{DYN_NS}hasMaterial",
        f"{DYN_NS}hasOriginalHeight",
        f"{DYN_NS}hasOriginalDiameter",
        f"{DYN_NS}hasMass",
    ],
    details_labels={
        f"{DYN_NS}hasOriginalHeight": "Original Height",
        f"{DYN_NS}hasOriginalDiameter": "Original Diameter",
        f"{DYN_NS}hasMass": "Mass",
    },

    # Behavior
    show_details_panel=True,
    show_search_box=True,
    show_refresh_button=True,
    selection_mode=SelectionMode.SINGLE,
)
```

---

## FilterPanel

Composable filter dropdown panel with search box and refresh button.

### Widget Structure

```
FilterPanel(QWidget)
+-- QHBoxLayout
    +-- [For each filter_property:]
    |   +-- QLabel (filter label)
    |   +-- QComboBox (filter dropdown)
    +-- QLabel ("Search:")
    +-- QLineEdit (search box)
    +-- [stretch]
    +-- QPushButton ("Refresh")
```

### Signals

| Signal | Parameters | Description |
|--------|------------|-------------|
| `filters_changed` | dict | Emitted when any filter dropdown changes |
| `search_changed` | str | Emitted when search text changes |
| `refresh_requested` | - | Emitted when refresh button clicked |

### Methods

```python
from dynamat.gui.widgets.base.entity_selector import FilterPanel

panel = FilterPanel(config, ontology_manager=om)

# Get current filter values (property_uri -> selected_value)
filters = panel.get_filter_values()
# {"https://dynamat.utep.edu/ontology#hasMaterial": "https://...#SS316"}

# Set filter values programmatically
panel.set_filter_values({
    "dyn:hasMaterial": "https://dynamat.utep.edu/ontology#SS316"
})

# Clear all filters (reset to "All")
panel.clear_filters()

# Populate filter options manually
panel.populate_filter_options(
    "dyn:hasMaterial",
    [
        ("https://dynamat.utep.edu/ontology#SS316", "SS316"),
        ("https://dynamat.utep.edu/ontology#Al6061", "Al6061"),
    ]
)

# Load options from ontology individuals
panel.load_filter_options_from_ontology()

# Search text
panel.set_search_text("SPN-001")
text = panel.get_search_text()  # "SPN-001"
```

### Standalone Usage

```python
# Use FilterPanel independently
filter_panel = FilterPanel(config, ontology_manager=om)
filter_panel.filters_changed.connect(self._reload_with_filters)
filter_panel.search_changed.connect(self._filter_table_rows)
filter_panel.refresh_requested.connect(self._refresh_data)
layout.addWidget(filter_panel)
```

---

## DetailsPanel

Composable details display panel showing selected entity properties.

### Widget Structure

```
DetailsPanel(QWidget)
+-- QVBoxLayout
    +-- QFrame (styled panel)
        +-- QGridLayout
            +-- [For each details_property:]
                +-- QLabel (property name, bold, right-aligned)
                +-- QLabel (property value, selectable)
```

### Methods

```python
from dynamat.gui.widgets.base.entity_selector import DetailsPanel

panel = DetailsPanel(config)

# Update with entity data
panel.update_details({
    "https://dynamat.utep.edu/ontology#hasSpecimenID": "SPN-001",
    "https://dynamat.utep.edu/ontology#hasMaterial": "https://...#SS316",
    "https://dynamat.utep.edu/ontology#hasOriginalHeight": {
        "value": 10.5,
        "unit": "unit:MilliM"
    },
})

# Clear to placeholders
panel.clear()

# Dynamically change displayed properties
panel.set_properties([
    "dyn:hasSpecimenID",
    "dyn:hasMaterial",
])
```

### Value Formatting

DetailsPanel automatically formats different value types:

| Value Type | Example Input | Displayed As |
|------------|---------------|--------------|
| String | `"SPN-001"` | `SPN-001` |
| URI | `"https://...#SS316"` | `SS316` |
| Measurement dict | `{"value": 10.5, "unit": "unit:MilliM"}` | `10.5 MilliM` |
| Empty/None | `None` or `""` | `--` |

---

## EntitySelectorWidget

Core embeddable widget combining FilterPanel, sortable table, and DetailsPanel.

### Widget Structure

```
EntitySelectorWidget(QWidget)
+-- QVBoxLayout
    +-- FilterPanel (if filters/search/refresh configured)
    +-- QSplitter (vertical, if details_panel enabled)
    |   +-- QTableWidget (sortable, selectable)
    |   +-- DetailsPanel
    +-- QLabel (status message)
```

### Signals

| Signal | Parameters | Description |
|--------|------------|-------------|
| `selection_changed` | dict | Emitted when selection changes (preview data) |
| `entity_selected` | dict | Emitted on double-click (full data loaded) |
| `filter_changed` | dict | Emitted when filter values change |
| `loading_started` | - | Emitted when data loading begins |
| `loading_finished` | int | Emitted when loading completes (item count) |
| `error_occurred` | str | Emitted on errors |

### Constructor

```python
EntitySelectorWidget(
    config: EntitySelectorConfig,
    query_builder=None,        # InstanceQueryBuilder for SPARQL queries
    ontology_manager=None,     # OntologyManager for loading individuals
    parent=None
)
```

### Methods

```python
from dynamat.gui.widgets.base.entity_selector import EntitySelectorWidget

widget = EntitySelectorWidget(config, query_builder=qb, ontology_manager=om)

# Selection
entity = widget.get_selected_entity()      # Single selection mode
entities = widget.get_selected_entities()  # Multiple selection mode
widget.set_selected_entity(uri)            # Select by URI
widget.clear_selection()

# Filtering
widget.set_filters({"dyn:hasMaterial": material_uri})
filters = widget.get_filters()
widget.clear_filters()

# Data
widget.refresh()                           # Reload from query builder
widget.set_query_builder(new_qb)           # Change query builder
widget.set_ontology_manager(new_om)        # Change ontology manager

# Load full data for an entity
full_data = widget.load_full_entity_data(uri)
```

### SPARQL Filtering vs Python Filtering

The widget uses efficient SPARQL-based filtering:

```python
# OLD approach (inefficient - loads all, filters in Python)
all_instances = query_builder.find_all_instances(class_uri)
filtered = [i for i in all_instances if i.get("hasMaterial") == material_uri]

# NEW approach (efficient - SPARQL filters at query time)
if filters:
    instances = query_builder.filter_instances(class_uri, filters)
else:
    instances = query_builder.find_all_instances(class_uri)
```

### Complete Example

```python
from dynamat.gui.widgets.base.entity_selector import (
    EntitySelectorConfig, EntitySelectorWidget
)
from dynamat.ontology.instance_query_builder import InstanceQueryBuilder

# Setup
query_builder = InstanceQueryBuilder(ontology_manager)
query_builder.scan_and_index(specimens_dir, class_uri, "*_specimen.ttl")

# Configure
config = EntitySelectorConfig(
    class_uri="https://dynamat.utep.edu/ontology#Specimen",
    display_properties=[
        "https://dynamat.utep.edu/ontology#hasSpecimenID",
        "https://dynamat.utep.edu/ontology#hasMaterial",
    ],
    filter_properties=["https://dynamat.utep.edu/ontology#hasMaterial"],
    show_details_panel=True,
)

# Create widget
selector = EntitySelectorWidget(
    config=config,
    query_builder=query_builder,
    ontology_manager=ontology_manager
)

# Connect signals
selector.selection_changed.connect(self._on_selection_preview)
selector.entity_selected.connect(self._on_entity_confirmed)
selector.loading_finished.connect(lambda n: print(f"Loaded {n} items"))
selector.error_occurred.connect(lambda e: print(f"Error: {e}"))

# Add to layout
layout.addWidget(selector)
```

---

## EntitySelectorDialog

Modal dialog wrapper around EntitySelectorWidget with OK/Cancel buttons.

### Widget Structure

```
EntitySelectorDialog(QDialog)
+-- QVBoxLayout
    +-- QLabel ("Select an entity:")
    +-- EntitySelectorWidget
    +-- QHBoxLayout
        +-- [stretch]
        +-- QPushButton ("Load")
        +-- QPushButton ("Cancel")
```

### Constructor

```python
EntitySelectorDialog(
    config: EntitySelectorConfig,
    query_builder=None,
    ontology_manager=None,
    title: str = "Select Entity",
    parent=None
)
```

### Methods

```python
from dynamat.gui.widgets.base.entity_selector import EntitySelectorDialog

# Create dialog
dialog = EntitySelectorDialog(config, query_builder=qb, title="Load Specimen")

# Show dialog
if dialog.exec() == QDialog.DialogCode.Accepted:
    data = dialog.get_selected_data()
    if data:
        process_entity(data)

# Access embedded selector for customization
selector = dialog.get_selector()
selector.set_filters({"dyn:hasMaterial": material_uri})

# Refresh data
dialog.refresh()
```

### Static Convenience Method

The easiest way to use the dialog:

```python
from dynamat.gui.widgets.base.entity_selector import (
    EntitySelectorConfig, EntitySelectorDialog
)

# One-liner entity selection
data = EntitySelectorDialog.select_entity(
    config=EntitySelectorConfig(
        class_uri="https://dynamat.utep.edu/ontology#Specimen",
        display_properties=["dyn:hasSpecimenID", "dyn:hasMaterial"],
        filter_properties=["dyn:hasMaterial"],
        show_details_panel=True,
    ),
    query_builder=self.query_builder,
    ontology_manager=self.ontology_manager,
    title="Load Existing Specimen",
    parent=self
)

if data:
    # User selected an entity
    specimen_id = data.get("https://dynamat.utep.edu/ontology#hasSpecimenID")
    self.load_specimen(data)
else:
    # User cancelled
    pass
```

---

## Integration Examples

### SHPB Wizard - Specimen Selection Page

```python
class SpecimenSelectionPage(BaseSHPBPage):
    def _setup_ui(self):
        layout = self._create_base_layout()

        config = EntitySelectorConfig(
            class_uri="https://dynamat.utep.edu/ontology#Specimen",
            display_properties=[
                "dyn:hasSpecimenID", "dyn:hasMaterial",
                "dyn:hasShape", "dyn:hasStructure", "dyn:hasBatchID"
            ],
            filter_properties=["dyn:hasMaterial"],
            details_properties=[
                "dyn:hasSpecimenID", "dyn:hasMaterial",
                "dyn:hasOriginalHeight", "dyn:hasOriginalDiameter"
            ],
            show_details_panel=True,
        )

        self._selector = EntitySelectorWidget(config, ontology_manager=self.om)
        self._selector.selection_changed.connect(self._on_selection)
        layout.addWidget(self._selector)

    def initializePage(self):
        super().initializePage()
        if self.query_builder:
            self._selector.set_query_builder(self.query_builder)

    def _on_selection(self, data):
        self.state.specimen_uri = data.get('uri')
        self.state.specimen_data = data
```

### Specimen Form - Load Existing Button

```python
class SpecimenFormWidget(QWidget):
    def load_existing_specimen(self):
        if self.is_modified:
            reply = QMessageBox.question(...)
            if reply != QMessageBox.StandardButton.Yes:
                return

        data = EntitySelectorDialog.select_entity(
            config=EntitySelectorConfig(
                class_uri="https://dynamat.utep.edu/ontology#Specimen",
                display_properties=["dyn:hasSpecimenID", "dyn:hasMaterial"],
                filter_properties=["dyn:hasMaterial"],
                show_details_panel=True,
            ),
            query_builder=self.instance_query_builder,
            ontology_manager=self.ontology_manager,
            title="Load Existing Specimen",
            parent=self
        )

        if data:
            self.load_specimen_data(data)
            self.current_specimen_uri = data.get('uri')
```

### Custom Entity Type - Equipment Selection

```python
def select_equipment(self):
    config = EntitySelectorConfig(
        class_uri="https://dynamat.utep.edu/ontology#SHPBEquipment",
        display_properties=[
            "dyn:hasEquipmentID",
            "dyn:hasBarMaterial",
            "dyn:hasBarDiameter",
        ],
        filter_properties=["dyn:hasBarMaterial"],
        details_properties=[
            "dyn:hasEquipmentID",
            "dyn:hasBarMaterial",
            "dyn:hasBarDiameter",
            "dyn:hasBarLength",
            "dyn:hasWaveSpeed",
        ],
        show_details_panel=True,
    )

    return EntitySelectorDialog.select_entity(
        config=config,
        query_builder=self.equipment_query_builder,
        title="Select SHPB Equipment",
        parent=self
    )
```

---

## Data Flow

```
User Action                    Widget Response
-----------                    ---------------
Opens page/dialog         -->  EntitySelectorWidget created
                               |
                               +-> FilterPanel.load_filter_options_from_ontology()
                               |   (populates dropdowns from ontology individuals)
                               |
                               +-> refresh() called
                                   |
                                   +-> query_builder.find_all_instances()
                                   +-> _populate_table()
                                   +-> loading_finished.emit(count)

User selects filter       -->  FilterPanel.filters_changed.emit(filters)
                               |
                               +-> _on_filters_changed()
                                   |
                                   +-> query_builder.filter_instances(filters)
                                   +-> _populate_table()

User types in search      -->  FilterPanel.search_changed.emit(text)
                               |
                               +-> _filter_table_rows(text)
                                   (hides non-matching rows, no re-query)

User clicks table row     -->  _on_selection_changed()
                               |
                               +-> DetailsPanel.update_details(preview_data)
                               +-> selection_changed.emit(preview_data)

User double-clicks row    -->  _on_double_click()
                               |
                               +-> query_builder.load_full_instance_data(uri)
                               +-> entity_selected.emit(full_data)

User clicks Load button   -->  Dialog._on_load_clicked()
(in dialog)                    |
                               +-> load_full_instance_data(uri)
                               +-> dialog.accept()
```

---

## Error Handling

All components handle errors gracefully:

```python
# Widget handles missing query builder
widget = EntitySelectorWidget(config)  # No query builder
widget.refresh()  # Shows "No query builder configured" in status

# Dialog handles missing selection
dialog = EntitySelectorDialog(config)
dialog._on_load_clicked()  # Shows warning if nothing selected

# Config validates required fields
try:
    config = EntitySelectorConfig(class_uri="")  # Empty URI
except ValueError as e:
    print(e)  # "class_uri is required"

# FilterPanel handles missing ontology manager
panel = FilterPanel(config)  # No ontology manager
panel.load_filter_options_from_ontology()  # Logs warning, no crash
```

---

## Testing

Run the test suite:

```bash
python tools/test_entity_selector.py
```

Tests cover:
- EntitySelectorConfig validation and normalization
- FilterPanel filter value management
- DetailsPanel value formatting
- EntitySelectorWidget table population
- EntitySelectorDialog creation
- Integration with InstanceQueryBuilder

---

## Logging

All components use Python's standard logging:

```python
import logging

# Enable debug logging
logging.getLogger('dynamat.gui.widgets.base.entity_selector').setLevel(logging.DEBUG)

# Log output includes:
# - Widget initialization
# - Filter option population
# - Query execution
# - Selection changes
# - Error details
```

---

## Migration from LoadEntityDialog

The old `LoadEntityDialog` has been replaced. Here's how to migrate:

### Before

```python
from dynamat.gui.widgets.load_entity_dialog import LoadEntityDialog

dialog = LoadEntityDialog(
    query_builder=self.query_builder,
    class_uri="https://dynamat.utep.edu/ontology#Specimen",
    display_properties=["hasSpecimenID", "hasMaterial"],
    property_labels={"hasSpecimenID": "Specimen ID"},
    title="Load Specimen",
    parent=self
)

if dialog.exec() == QDialog.DialogCode.Accepted:
    data = dialog.get_selected_data()
```

### After

```python
from dynamat.gui.widgets.base.entity_selector import (
    EntitySelectorConfig, EntitySelectorDialog
)

data = EntitySelectorDialog.select_entity(
    config=EntitySelectorConfig(
        class_uri="https://dynamat.utep.edu/ontology#Specimen",
        display_properties=["dyn:hasSpecimenID", "dyn:hasMaterial"],
        property_labels={"dyn:hasSpecimenID": "Specimen ID"},
        filter_properties=["dyn:hasMaterial"],  # NEW: SPARQL filtering
        show_details_panel=True,                 # NEW: Details panel
    ),
    query_builder=self.query_builder,
    title="Load Specimen",
    parent=self
)
```

### Key Improvements

1. **SPARQL Filtering**: Filter dropdowns query at database level (efficient)
2. **Composable**: FilterPanel and DetailsPanel can be used independently
3. **Embeddable**: EntitySelectorWidget works in any layout, not just dialogs
4. **Configurable**: All behavior controlled via EntitySelectorConfig
5. **Better UX**: Details panel shows preview, search filters visible rows

---

## References

1. PyQt6 Widgets: https://doc.qt.io/qtforpython-6/
2. RDFLib SPARQL: https://rdflib.readthedocs.io/en/stable/intro_to_sparql.html
3. DynaMat Ontology: See `dynamat/ontology/core/DynaMat_core.ttl`
