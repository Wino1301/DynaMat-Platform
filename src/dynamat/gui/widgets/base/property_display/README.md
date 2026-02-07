# Property Display Widget Module

This module provides a reusable, ontology-driven widget for displaying read-only properties from DynaMat ontology individuals. It supports both automatic ontology queries and manual data population for backward compatibility with the constraint system.

## Architecture Overview

```
Property Display Module
       |
       +---> Configuration
       |        +---> PropertyDisplayConfig (dataclass)
       |
       +---> Main Widget
                +---> PropertyDisplayWidget
                        +---> Ontology-driven mode (setIndividual)
                        +---> Legacy mode (setData)
```

## Module Exports

```python
from dynamat.gui.widgets.base.property_display import (
    # Configuration
    PropertyDisplayConfig,    # Configuration dataclass

    # Main Widget
    PropertyDisplayWidget,    # Reusable display widget
)

# Also available from parent modules
from dynamat.gui.widgets.base import PropertyDisplayConfig, PropertyDisplayWidget
from dynamat.gui.widgets import PropertyDisplayConfig, PropertyDisplayWidget
```

---

## Quick Start

### Ontology-Driven Mode (Recommended)

```python
from dynamat.gui.widgets.base.property_display import (
    PropertyDisplayConfig, PropertyDisplayWidget
)

# Configure the display
config = PropertyDisplayConfig(
    title="Bar Material Properties",
    properties=[
        "dyn:hasWaveSpeed",
        "dyn:hasElasticModulus",
        "dyn:hasDensity",
    ],
    follow_links={"dyn:hasMaterial": [
        "dyn:hasWaveSpeed",
        "dyn:hasElasticModulus",
        "dyn:hasDensity",
    ]}
)

# Create widget
display = PropertyDisplayWidget(
    config=config,
    ontology_manager=ontology_manager
)
layout.addWidget(display)

# When user selects a bar, display its material properties
display.setIndividual("dyn:IncidentBar_C350")
```

### Legacy Mode (Constraint System Compatibility)

```python
from dynamat.gui.widgets.base.property_display import PropertyDisplayWidget

# Create widget without config (backward compatible)
display = PropertyDisplayWidget(title="Bar Properties")

# Set data manually (used by DependencyManager)
display.setData({
    'dyn:hasWaveSpeed': {
        'value': 4953.3,
        'unit': 'unit:M-PER-SEC',
        'label': 'Wave Speed'
    },
    'dyn:hasElasticModulus': {
        'value': 199.99,
        'unit': 'unit:GigaPA',
        'label': 'Elastic Modulus'
    }
})
```

---

## PropertyDisplayConfig

Configuration dataclass that defines widget behavior for ontology-driven mode.

### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `title` | str | **required** | Title for the group box header |
| `properties` | List[str] | **required** | Property URIs to display |
| `property_labels` | Dict[str, str] | `None` | Custom label overrides |
| `follow_links` | Dict[str, List[str]] | `None` | Object properties to follow for nested values |
| `show_empty` | bool | `False` | Show properties with no value as "N/A" |

### Property URI Normalization

The config automatically normalizes property URIs. All these formats work:

```python
# Full URI
"https://dynamat.utep.edu/ontology#hasWaveSpeed"

# Prefixed name
"dyn:hasWaveSpeed"

# Local name only (assumes DynaMat namespace)
"hasWaveSpeed"
```

### Helper Methods

```python
config = PropertyDisplayConfig(
    title="Material Properties",
    properties=["dyn:hasWaveSpeed", "hasElasticModulus"],
    property_labels={"dyn:hasWaveSpeed": "Wave Speed"},
)

# Get display label (uses property_labels or returns default)
label = config.get_label("dyn:hasWaveSpeed", "Default")  # "Wave Speed"
label = config.get_label("dyn:hasDensity", "Density")    # "Density" (default)

# Normalize to prefixed URI
uri = config.normalize_uri("https://dynamat.utep.edu/ontology#hasWaveSpeed")
# "dyn:hasWaveSpeed"

# Get all normalized URIs
props = config.get_normalized_properties()
# ["dyn:hasWaveSpeed", "dyn:hasElasticModulus"]
```

### Nested Property Resolution with follow_links

When displaying properties that live on a linked individual (e.g., material properties on a bar's material), use `follow_links`:

```python
config = PropertyDisplayConfig(
    title="Bar Material Properties",
    properties=[
        "dyn:hasWaveSpeed",
        "dyn:hasElasticModulus",
        "dyn:hasDensity",
    ],
    # Follow the hasMaterial link to get these properties
    follow_links={
        "dyn:hasMaterial": [
            "dyn:hasWaveSpeed",
            "dyn:hasElasticModulus",
            "dyn:hasDensity",
        ]
    }
)

# When setIndividual is called with a Bar URI:
# 1. Widget queries the Bar for hasMaterial link
# 2. Follows link to Material individual
# 3. Queries Material for hasWaveSpeed, hasElasticModulus, hasDensity
# 4. Displays values with labels and units
```

---

## PropertyDisplayWidget

Core widget for displaying read-only ontology properties.

### Widget Structure

```
PropertyDisplayWidget(QWidget)
+-- QVBoxLayout
    +-- QGroupBox (#propertyDisplayGroupBox)
        +-- QFormLayout
            +-- [For each property:]
                +-- QLabel (#propertyLabel) - "Wave Speed:"
                +-- QLabel (#propertyValue) - "4953.300 m/s"
```

### Constructor

```python
PropertyDisplayWidget(
    config: Optional[PropertyDisplayConfig] = None,  # For ontology-driven mode
    ontology_manager: Optional[OntologyManager] = None,  # Required for setIndividual
    title: str = "Properties",  # Fallback title if no config
    parent: Optional[QWidget] = None
)
```

### Ontology-Driven API (New)

```python
from dynamat.gui.widgets.base.property_display import (
    PropertyDisplayConfig, PropertyDisplayWidget
)

config = PropertyDisplayConfig(
    title="Gauge Properties",
    properties=["dyn:hasGaugeFactor", "dyn:hasGaugeResistance"],
)

widget = PropertyDisplayWidget(config=config, ontology_manager=om)

# Display properties for an individual
widget.setIndividual("dyn:IncidentGauge_SG1")

# Get currently displayed individual
uri = widget.getIndividual()  # "dyn:IncidentGauge_SG1"

# Clear display
widget.clear()
```

### Legacy API (Backward Compatible)

```python
widget = PropertyDisplayWidget(title="Properties")

# Set data manually (for constraint system)
widget.setData({
    'dyn:hasGaugeFactor': {
        'value': 2.1,
        'label': 'Gauge Factor'
    },
    'dyn:hasGaugeResistance': {
        'value': 350,
        'unit': 'unit:OHM',
        'label': 'Resistance'
    }
})

# Get current display values
data = widget.getData()
# {'dyn:hasGaugeFactor': '2.100', 'dyn:hasGaugeResistance': '350.000 OHM'}

# Clear display
widget.clear()
```

### Value Formatting

The widget automatically formats values for human-readable display:

| Value Type | Example Input | Displayed As |
|------------|---------------|--------------|
| Float | `4953.3` | `4953.300` |
| Float + Unit | `4953.3` + `unit:M-PER-SEC` | `4953.300 m/s` |
| Integer | `350` | `350.000` |
| String | `"Test Value"` | `Test Value` |
| URI | `"dyn:SS316_C350"` | `SS316 C350` |
| None | `None` | `N/A` |

**Unit Symbol Conversion:**

| Unit URI | Symbol |
|----------|--------|
| `unit:M-PER-SEC` | `m/s` |
| `unit:GigaPA` | `GPa` |
| `unit:MegaPA` | `MPa` |
| `unit:KiloGM-PER-M3` | `kg/m³` |
| `unit:MilliM` | `mm` |
| `unit:SEC` | `s` |
| `unit:PER-SEC` | `1/s` |

---

## Styling

The widget uses object names for stylesheet targeting (no hardcoded colors):

```css
/* In styles.qss */

/* Property Display Widget */
#propertyDisplayGroupBox {
    font-weight: bold;
    color: #ffffff;
    border: 1px solid #666;
    border-radius: 4px;
    margin-top: 10px;
    padding-top: 10px;
}

#propertyDisplayGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding-left: 10px;
    padding-right: 10px;
    background-color: #2b2b2b;
}

#propertyLabel {
    font-weight: normal;
    color: #ffffff;
}

#propertyValue {
    background-color: #3a3a3a;
    border: 1px solid #666;
    border-radius: 3px;
    padding: 5px 8px;
    color: #ffffff;
    font-weight: normal;
    min-height: 20px;
}
```

---

## Integration with DependencyManager

The widget integrates automatically with the constraint system through `DependencyManager`:

### Constraint Definition (TTL)

```turtle
gui:IncidentBarMaterialPopulation a gui:Constraint ;
    gui:hasTrigger dyn:hasIncidentBar ;
    gui:targetWidget "IncidentBarMaterialProperties" ;
    gui:populateField ( dyn:hasWaveSpeed "Wave Speed" ) ;
    gui:populateField ( dyn:hasElasticModulus "Elastic Modulus" ) ;
    gui:populateField ( dyn:hasDensity "Density" ) .
```

### Automatic Widget Creation

When `DependencyManager.setup_dependencies()` is called:

1. Finds constraints with `gui:targetWidget`
2. Builds `PropertyDisplayConfig` from constraint definition
3. Infers `follow_links` for material properties automatically
4. Creates `PropertyDisplayWidget` with ontology-driven config
5. Inserts widget into form layout below trigger field's group

### Automatic Population

When user selects an equipment item:

1. `DependencyManager._action_populate()` is called
2. For display widget constraints, calls `widget.setIndividual(selected_uri)`
3. Widget queries ontology and displays properties automatically
4. When selection cleared, calls `widget.clear()`

---

## Integration Examples

### SHPB Equipment Page - Bar Material Properties

The equipment page uses PropertyDisplayWidget through constraints to show bar material properties when a bar is selected:

```python
# In equipment_page.py - widget is created automatically by DependencyManager

class EquipmentPage(BaseSHPBPage):
    def _setup_ui(self):
        # Build form from ontology
        self.form_widget = self.form_builder.build_form(
            "https://dynamat.utep.edu/ontology#SHPBCompression"
        )

        # Setup dependency manager - this creates PropertyDisplayWidgets
        # for any constraints with gui:targetWidget
        self.dependency_manager = DependencyManager(self.ontology_manager)
        self.dependency_manager.setup_dependencies(
            self.form_widget,
            "https://dynamat.utep.edu/ontology#SHPBCompression"
        )
```

### Standalone Usage - Specimen Details

```python
from dynamat.gui.widgets.base.property_display import (
    PropertyDisplayConfig, PropertyDisplayWidget
)

class SpecimenDetailsPanel(QWidget):
    def __init__(self, ontology_manager, parent=None):
        super().__init__(parent)

        layout = QVBoxLayout(self)

        # Material properties display
        self.material_display = PropertyDisplayWidget(
            config=PropertyDisplayConfig(
                title="Material Properties",
                properties=[
                    "dyn:hasElasticModulus",
                    "dyn:hasDensity",
                    "dyn:hasPoissonRatio",
                ],
            ),
            ontology_manager=ontology_manager
        )
        layout.addWidget(self.material_display)

        # Dimensions display
        self.dimensions_display = PropertyDisplayWidget(
            config=PropertyDisplayConfig(
                title="Specimen Dimensions",
                properties=[
                    "dyn:hasOriginalHeight",
                    "dyn:hasOriginalDiameter",
                    "dyn:hasMass",
                ],
            ),
            ontology_manager=ontology_manager
        )
        layout.addWidget(self.dimensions_display)

    def set_specimen(self, specimen_uri: str):
        """Display properties for a specimen."""
        # Get material URI from specimen
        material_uri = self.ontology_manager.get_individual_property_values(
            specimen_uri, ["dyn:hasMaterial"]
        ).get("dyn:hasMaterial")

        if material_uri:
            self.material_display.setIndividual(material_uri)

        self.dimensions_display.setIndividual(specimen_uri)

    def clear(self):
        """Clear all displays."""
        self.material_display.clear()
        self.dimensions_display.clear()
```

### Custom Equipment Selector with Details

```python
from dynamat.gui.widgets.base.property_display import (
    PropertyDisplayConfig, PropertyDisplayWidget
)
from dynamat.gui.widgets.base.entity_selector import (
    EntitySelectorConfig, EntitySelectorWidget
)

class EquipmentSelectorWithDetails(QWidget):
    def __init__(self, ontology_manager, query_builder, parent=None):
        super().__init__(parent)

        layout = QHBoxLayout(self)

        # Left: Equipment selector
        selector_config = EntitySelectorConfig(
            class_uri="dyn:Bar",
            display_properties=["dyn:hasName", "dyn:hasMaterial"],
        )
        self.selector = EntitySelectorWidget(
            selector_config,
            query_builder=query_builder,
            ontology_manager=ontology_manager
        )
        self.selector.selection_changed.connect(self._on_selection)
        layout.addWidget(self.selector)

        # Right: Property display
        display_config = PropertyDisplayConfig(
            title="Bar Properties",
            properties=[
                "dyn:hasLength",
                "dyn:hasDiameter",
                "dyn:hasWaveSpeed",
                "dyn:hasElasticModulus",
            ],
            follow_links={
                "dyn:hasMaterial": ["dyn:hasWaveSpeed", "dyn:hasElasticModulus"]
            }
        )
        self.details = PropertyDisplayWidget(
            config=display_config,
            ontology_manager=ontology_manager
        )
        layout.addWidget(self.details)

    def _on_selection(self, data: dict):
        uri = data.get('uri')
        if uri:
            self.details.setIndividual(uri)
        else:
            self.details.clear()
```

---

## Domain Query Support

The widget uses `DomainQueries.get_individual_properties_with_labels()` for rich property queries:

```python
from dynamat.ontology.query.domain_queries import DomainQueries

# Query properties with labels and units
props = domain_queries.get_individual_properties_with_labels(
    individual_uri="dyn:IncidentBar_C350",
    property_uris=["dyn:hasWaveSpeed", "dyn:hasElasticModulus"],
    follow_links={"dyn:hasMaterial": ["dyn:hasWaveSpeed", "dyn:hasElasticModulus"]}
)

# Returns:
# {
#     "dyn:hasWaveSpeed": {
#         "value": 4953.3,
#         "label": "Wave Speed",
#         "unit": "http://qudt.org/vocab/unit/M-PER-SEC",
#         "unit_symbol": "m/s"
#     },
#     "dyn:hasElasticModulus": {
#         "value": 199.99,
#         "label": "Elastic Modulus",
#         "unit": "http://qudt.org/vocab/unit/GigaPA",
#         "unit_symbol": "GPa"
#     }
# }
```

---

## Data Flow

```
User Action                    Widget Response
-----------                    ---------------
Widget created with config -->  PropertyDisplayWidget initialized
                               +-> Config stored
                               +-> Empty form layout created

setIndividual(uri) called  -->  Query ontology
                               |
                               +-> domain_queries.get_individual_properties_with_labels()
                               |   (follows links if configured)
                               |
                               +-> For each property:
                               |   +-> Create label widget
                               |   +-> Create value widget (formatted)
                               |   +-> Add to form layout
                               |
                               +-> Store current individual URI

clear() called             -->  Remove all rows from form layout
                               +-> Clear widget references
                               +-> Set current individual to None

setData(dict) called       -->  (Legacy mode)
                               +-> clear() first
                               +-> For each property in dict:
                                   +-> Extract value, unit, label
                                   +-> Format and display
```

---

## Error Handling

The widget handles errors gracefully:

```python
# Missing config for ontology mode
widget = PropertyDisplayWidget(title="Test")
widget.setIndividual("dyn:Test")  # Logs warning, no crash

# Missing ontology manager
widget = PropertyDisplayWidget(config=config)
widget.setIndividual("dyn:Test")  # Logs warning, no crash

# Invalid individual URI
widget = PropertyDisplayWidget(config=config, ontology_manager=om)
widget.setIndividual("dyn:NonExistent")  # Shows empty (no properties found)

# None/empty URI
widget.setIndividual(None)  # Equivalent to clear()
widget.setIndividual("")    # Equivalent to clear()
```

---

## Logging

The widget uses Python's standard logging:

```python
import logging

# Enable debug logging
logging.getLogger('dynamat.gui.widgets.base.property_display').setLevel(logging.DEBUG)

# Log output includes:
# - Widget initialization
# - Property queries
# - Value formatting
# - Clear operations
# - Error details
```

---

## Migration from Old API

If you were using the old `PropertyDisplayWidget` directly:

```python
# OLD (still works - backward compatible)
widget = PropertyDisplayWidget(title="Properties")
widget.setData({
    'dyn:hasWaveSpeed': {'value': 4953.3, 'label': 'Wave Speed'}
})

# NEW (recommended for new code)
config = PropertyDisplayConfig(
    title="Properties",
    properties=["dyn:hasWaveSpeed"],
    property_labels={"dyn:hasWaveSpeed": "Wave Speed"}
)
widget = PropertyDisplayWidget(config=config, ontology_manager=om)
widget.setIndividual("dyn:SomeIndividual")
```

---

## References

1. PyQt6 Widgets: https://doc.qt.io/qtforpython-6/
2. RDFLib SPARQL: https://rdflib.readthedocs.io/en/stable/intro_to_sparql.html
3. DynaMat Ontology: See `dynamat/ontology/core/DynaMat_core.ttl`
4. GUI Constraints: See `dynamat/ontology/constraints/gui_shpb_rules.ttl`
5. Entity Selector Module: See `dynamat/gui/widgets/base/entity_selector/README.md`
