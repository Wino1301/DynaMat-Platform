# GUI Base Widgets Module

This module provides fundamental widget components for the DynaMat Platform, including plotting widgets with configurable backends, data containers for processing results, and specialized input widgets for unit-aware values.

## Architecture Overview

```
Base Widgets Module
       |
       +---> Plotting Widgets (configurable backend)
       |        |
       |        +---> BasePlotWidget (interface)
       |        +---> MatplotlibPlotWidget
       |        +---> PlotlyPlotWidget
       |        +---> PlotWidgetFactory
       |
       +---> Data Containers
       |        +---> DataSeriesWidget (result storage)
       |
       +---> Metadata Resolution
       |        +---> SeriesMetadataResolver (axis labels)
       |
       +---> Input Widgets
                +---> UnitValueWidget (value + unit)
```

## Module Exports

```python
from dynamat.gui.widgets.base import (
    # Plot Widgets
    BasePlotWidget,           # Base interface for plot widgets
    MatplotlibPlotWidget,     # Matplotlib-based plotting
    PlotlyPlotWidget,         # Plotly-based plotting (optional)
    DataSeriesPlotWidget,     # Alias for MatplotlibPlotWidget
    create_plot_widget,       # Factory function
    get_available_backends,   # List available backends
    is_backend_available,     # Check backend availability

    # Data Management
    DataSeriesWidget,         # Processing result container
    SeriesMetadataResolver,   # Axis label resolution

    # Input Widgets
    UnitValueWidget,          # Value with unit selection
)
```

---

## Plotting Widgets

### Backend Selection

The module supports configurable plotting backends. Set the backend in `Config` or pass explicitly:

```python
from dynamat.config import Config

# Global configuration
Config.PLOT_BACKEND = "plotly"  # or "matplotlib"

# Or use factory with explicit backend
from dynamat.gui.widgets.base import create_plot_widget

plot = create_plot_widget(ontology_manager, qudt_manager)  # Uses Config
plot = create_plot_widget(ontology_manager, qudt_manager, backend='plotly')
plot = create_plot_widget(ontology_manager, qudt_manager, backend='matplotlib')
```

### create_plot_widget (Factory Function)

Creates the appropriate plot widget based on configuration or explicit selection.

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `ontology_manager` | OntologyManager | required | For SeriesType queries |
| `qudt_manager` | QUDTManager | required | For unit symbol resolution |
| `figsize` | Tuple[float, float] | (10, 6) | Figure size in inches |
| `show_toolbar` | bool | True | Show navigation toolbar |
| `backend` | str | None | 'plotly' or 'matplotlib' (uses Config if None) |
| `parent` | QWidget | None | Parent widget |

**Returns:** BasePlotWidget (either PlotlyPlotWidget or MatplotlibPlotWidget)

**Example:**

```python
from dynamat.gui.widgets.base import create_plot_widget, get_available_backends

# Check what's available
backends = get_available_backends()
print(f"Available backends: {backends}")  # ['matplotlib', 'plotly']

# Create with automatic backend selection
plot = create_plot_widget(ontology_manager, qudt_manager)

# Force specific backend
mpl_plot = create_plot_widget(ontology_manager, qudt_manager, backend='matplotlib')
plotly_plot = create_plot_widget(ontology_manager, qudt_manager, backend='plotly')
```

---

### BasePlotWidget

Base class defining the common interface for all plotting backends.

**Signals:**

| Signal | Parameters | Description |
|--------|------------|-------------|
| `traceClicked` | str, float, float | Emitted when trace clicked (uri, x, y) |
| `rangeSelected` | float, float | Emitted when range selected (x0, x1) |
| `plotUpdated` | - | Emitted after plot is refreshed |
| `cursorMoved` | float, float | Emitted when cursor moves (x, y) |

**Key Methods:**

All methods work identically across backends:

- `set_axis_series(x_type, y_type, ...)` - Set axis labels from ontology
- `add_trace(x, y, label, color, ...)` - Add data trace
- `add_trace_from_container(container, x_uri, y_uri, ...)` - Add from DataSeriesWidget
- `add_reference_line(orientation, value, ...)` - Add h/v reference line
- `configure_subplot(rows, cols)` - Set up multi-panel layout
- `set_active_subplot(idx)` - Switch active panel
- `refresh()` - Update the display
- `save_figure(filepath, dpi)` - Export to file
- `clear()` - Clear all content

---

### MatplotlibPlotWidget

Matplotlib-based plotting widget with ontology-driven axis labels.

**Widget Structure:**

```
MatplotlibPlotWidget(QWidget)
+-- QVBoxLayout
    +-- NavigationToolbar2QT (optional)
    +-- FigureCanvasQTAgg
        +-- matplotlib.figure.Figure
            +-- Axes (or list for subplots)
```

**Example:**

```python
from dynamat.gui.widgets.base import MatplotlibPlotWidget
import numpy as np

# Create widget
plot = MatplotlibPlotWidget(ontology_manager, qudt_manager)

# Configure axes from ontology (auto-resolves labels and units)
plot.set_axis_series('dyn:Strain', 'dyn:Stress')
# Result: x-axis="Strain", y-axis="Stress (MPa)"

# Add data traces
strain = np.linspace(0, 0.3, 100)
stress = 500 * strain

trace_id = plot.add_trace(
    strain, stress,
    label="1-wave",
    color="blue",
    linestyle='-',
    linewidth=1.5
)

# Add reference lines
plot.add_reference_line('h', 300, color='red', linestyle='--', label="Yield")
plot.add_reference_line('v', 0.1, color='green', linestyle=':')

# Configure display
plot.set_title("Stress-Strain Curve")
plot.enable_legend()
plot.enable_grid()
plot.refresh()

# Save figure
plot.save_figure("stress_strain.png", dpi=150)

# Access matplotlib objects directly
fig = plot.get_figure()
ax = plot.get_axes()
```

**Multi-Panel Layout:**

```python
# Configure 1x3 subplot layout
plot.configure_subplot(1, 3)

# Panel 1: Raw signals
plot.set_active_subplot(0)
plot.set_axis_series('dyn:Time', 'dyn:Voltage')
plot.add_trace(time, incident, label="Incident", color="blue")
plot.add_trace(time, transmitted, label="Transmitted", color="red")
plot.enable_legend()

# Panel 2: Stress-Strain
plot.set_active_subplot(1)
plot.set_axis_series('dyn:Strain', 'dyn:Stress')
plot.add_trace(strain, stress, label="1-wave")

# Panel 3: Strain Rate
plot.set_active_subplot(2)
plot.set_axis_series('dyn:Strain', 'dyn:StrainRate')
plot.add_trace(strain, strain_rate, label="Strain Rate")

plot.refresh()
```

---

### PlotlyPlotWidget

Plotly-based interactive plotting widget with built-in interactivity.

**Requirements:**

```bash
pip install plotly PyQtWebEngine kaleido
```

**Built-in Interactivity (no extra code needed):**

- **Zoom**: Drag to zoom, double-click to reset
- **Pan**: Shift+drag to pan
- **Hover**: Automatic tooltips with data values
- **Box/Lasso Select**: Built-in selection tools
- **Export**: Download as PNG button built-in

**Widget Structure:**

```
PlotlyPlotWidget(QWidget)
+-- QVBoxLayout
    +-- QWebEngineView
        +-- Plotly HTML/JS
```

**Example:**

```python
from dynamat.gui.widgets.base import PlotlyPlotWidget
import numpy as np

# Create widget
plot = PlotlyPlotWidget(ontology_manager, qudt_manager)

# API is identical to MatplotlibPlotWidget
plot.set_axis_series('dyn:Strain', 'dyn:Stress')
plot.add_trace(strain, stress, label="1-wave", color="blue")
plot.add_reference_line('h', 300, color='red', linestyle='--')
plot.enable_legend()
plot.enable_grid()
plot.refresh()

# Plotly-specific: template styling
plot.set_template('plotly_dark')  # or 'plotly_white', 'ggplot2', 'seaborn'

# Save as HTML (preserves interactivity)
plot.save_figure("stress_strain.html")

# Save as static image (requires kaleido)
plot.save_figure("stress_strain.png", dpi=150)
```

---

## DataSeriesWidget

Backend storage container for processing results. Maps numpy arrays to URIs with unit/legend metadata.

**Signals:**

| Signal | Parameters | Description |
|--------|------------|-------------|
| `dataChanged` | str (uri) | Emitted when data is updated |
| `dataCleared` | - | Emitted when all data cleared |
| `seriesAdded` | str (uri) | Emitted when new series added |
| `seriesRemoved` | str (uri) | Emitted when series removed |

**Container Structure:**

Each series is stored as a dict:
```python
{
    'array': np.ndarray,           # Data values
    'unit': str,                   # Current display unit URI
    'ref_unit': str,               # Reference/storage unit URI
    'legend': str,                 # Display legend text
    'metadata': Dict[str, Any]     # Additional metadata
}
```

**Example:**

```python
from dynamat.gui.widgets.base import DataSeriesWidget
import numpy as np

# Create container
container = DataSeriesWidget()

# Add series manually
container.add_series(
    uri='dyn:Stress',
    array=stress_array,
    unit='http://qudt.org/vocab/unit/MegaPA',
    legend='Engineering Stress (1-wave)',
    metadata={'series_type': 'dyn:Stress', 'analysis_method': '1-wave'}
)

# Get series
series = container.get_series('dyn:Stress')
array = container.get_array('dyn:Stress')

# Check existence
if container.has_series('dyn:Stress'):
    print(f"Stress series has {len(container.get_array('dyn:Stress'))} points")

# List all URIs
uris = container.get_all_uris()

# Remove series
container.remove_series('dyn:Stress')

# Clear all
container.clear()
```

**Bulk Capture from Processing Results:**

```python
# After SHPB analysis
results = {
    'stress_1w': stress_array,
    'strain_1w': strain_array,
    'strain_rate_1w': strain_rate_array,
}

# Metadata from ontology (loaded via OntologyManager)
series_metadata = ontology_manager.domain_queries.get_series_type_metadata()

# Capture all at once
count = container.capture_from_results(results, series_metadata)
print(f"Captured {count} series")

# Or with suffix for multiple datasets
container.capture_from_results_with_suffix(results, series_metadata, uri_suffix='_test1')
```

**Integration with Plot Widgets:**

```python
# Create container with results
container = DataSeriesWidget()
container.capture_from_results(results, series_metadata)

# Create plot and add traces from container
plot = create_plot_widget(ontology_manager, qudt_manager)
plot.set_axis_series('dyn:Strain', 'dyn:Stress')

# Add trace directly from container
trace_id = plot.add_trace_from_container(
    container,
    x_uri='dyn:Strain',
    y_uri='dyn:Stress',
    color='blue',
    linewidth=2.0
)

plot.refresh()
```

**Serialization:**

```python
# Save state
data = container.getData()
# {'series': [{'uri': '...', 'array': [...], 'unit': '...', ...}, ...]}

# Restore state
container.setData(data)
```

---

## SeriesMetadataResolver

Resolves SeriesType URIs to display-friendly axis labels and legend text using ontology queries.

**Data Flow:**

```
series_type_uri (e.g., 'dyn:Stress')
    |
    +---> OntologyManager.get_series_type_metadata()
    |        Returns: {quantity_kind, unit, legend_template}
    |
    +---> QUDTManager.get_unit_by_uri(unit_uri)
             Returns: QUDTUnit with .symbol (e.g., 'MPa')
    |
    v
Axis label: "Stress (MPa)"
```

**Example:**

```python
from dynamat.gui.widgets.base import SeriesMetadataResolver

resolver = SeriesMetadataResolver(ontology_manager, qudt_manager)

# Get axis label (includes unit if applicable)
label = resolver.get_axis_label('dyn:Stress')
# Returns: "Stress (MPa)"

label = resolver.get_axis_label('dyn:Strain')
# Returns: "Strain" (unitless, no parentheses)

# With custom unit override
label = resolver.get_axis_label_with_custom_unit('dyn:Stress', 'unit:PA')
# Returns: "Stress (Pa)"

# Get legend text with analysis method
legend = resolver.get_legend_text('dyn:Stress', '1-wave')
# Returns: "Engineering Stress (1-wave)"

# Get unit symbol
symbol = resolver.resolve_unit_symbol('http://qudt.org/vocab/unit/MegaPA')
# Returns: "MPa"

# Get quantity kind
qk = resolver.get_quantity_kind('dyn:Stress')
# Returns: "http://qudt.org/vocab/quantitykind/Stress"

# Get default unit
unit = resolver.get_default_unit('dyn:Stress')
# Returns: "http://qudt.org/vocab/unit/MegaPA"

# Clear cache if ontology changes
resolver.clear_cache()
```

---

## UnitValueWidget

Custom widget for entering dimensional values with QUDT unit selection.

**Signals:**

| Signal | Parameters | Description |
|--------|------------|-------------|
| `valueChanged` | float | Emitted when value changes |
| `unitChanged` | str | Emitted when unit changes |
| `dataChanged` | - | Emitted on any change |

**Widget Structure:**

```
UnitValueWidget(QWidget)
+-- QHBoxLayout
    +-- QDoubleSpinBox (value)
    +-- QComboBox (unit selector)
```

**Example:**

```python
from dynamat.gui.widgets.base import UnitValueWidget

# Create with available units
widget = UnitValueWidget(
    default_unit='http://qudt.org/vocab/unit/MilliM',
    available_units=length_units,  # List of UnitInfo objects
    property_uri='dyn:hasOriginalLength',
    reference_unit_uri='http://qudt.org/vocab/unit/MilliM'
)

# Get/set value
widget.setValue(10.5)
value = widget.getValue()  # 10.5

# Get/set unit
widget.setUnit('http://qudt.org/vocab/unit/M')
unit_uri = widget.getUnit()
unit_symbol = widget.getUnitSymbol()  # "m"

# Get complete data
data = widget.getData()
# {
#     'value': 10.5,
#     'unit': 'http://qudt.org/vocab/unit/MilliM',
#     'unit_symbol': 'mm',
#     'reference_unit': 'http://qudt.org/vocab/unit/MilliM'
# }

# Set from data
widget.setData({'value': 25.0, 'unit': 'http://qudt.org/vocab/unit/M'})

# Configure spinbox
widget.setRange(0.0, 1000.0)
widget.setDecimals(3)
widget.setSingleStep(0.1)
widget.setReadOnly(True)

# Connect to signals
widget.valueChanged.connect(lambda v: print(f"Value: {v}"))
widget.unitChanged.connect(lambda u: print(f"Unit: {u}"))
```

---

## Complete Workflow Example

```python
from dynamat.ontology import OntologyManager
from dynamat.ontology.qudt import QUDTManager
from dynamat.gui.widgets.base import (
    create_plot_widget, DataSeriesWidget, SeriesMetadataResolver
)
from dynamat.config import Config
import numpy as np

# Initialize managers
ontology_manager = OntologyManager()
qudt_manager = QUDTManager()
qudt_manager.load()

# Configure backend preference
Config.PLOT_BACKEND = "matplotlib"  # or "plotly"

# Create data container
container = DataSeriesWidget()

# Simulate SHPB analysis results
results = {
    'stress_1w': np.random.rand(100) * 500,
    'strain_1w': np.linspace(0, 0.3, 100),
    'strain_rate_1w': np.random.rand(100) * 1000,
}

# Capture results with metadata from ontology
series_metadata = ontology_manager.domain_queries.get_series_type_metadata()
container.capture_from_results(results, series_metadata)

# Create plot widget via factory
plot = create_plot_widget(ontology_manager, qudt_manager, figsize=(12, 4))

# Configure 3-panel layout
plot.configure_subplot(1, 3)

# Panel 1: Stress-Strain
plot.set_active_subplot(0)
plot.set_axis_series('dyn:Strain', 'dyn:Stress')
plot.add_trace_from_container(container, 'dyn:Strain', 'dyn:Stress',
                               label="1-wave", color="blue")
plot.enable_grid()

# Panel 2: Strain Rate vs Strain
plot.set_active_subplot(1)
plot.set_axis_series('dyn:Strain', 'dyn:StrainRate')
plot.add_trace_from_container(container, 'dyn:Strain', 'dyn:StrainRate',
                               label="Strain Rate", color="red")
plot.enable_grid()

# Panel 3: Stress vs Strain Rate
plot.set_active_subplot(2)
plot.set_axis_series('dyn:StrainRate', 'dyn:Stress')
plot.add_trace_from_container(container, 'dyn:StrainRate', 'dyn:Stress',
                               label="Flow Stress", color="green")
plot.enable_grid()

# Update display
plot.refresh()

# Save results
plot.save_figure("shpb_analysis.png", dpi=150)
```

---

## Backend Comparison

| Feature | Matplotlib | Plotly |
|---------|------------|--------|
| Zoom/Pan | Toolbar buttons | Drag/shift-drag |
| Hover tooltips | Manual implementation | Built-in |
| Box selection | Manual | Built-in |
| Export formats | PNG, PDF, SVG | PNG, HTML, SVG |
| Interactivity | Limited | Rich |
| Performance (large data) | Better | Slower |
| Offline support | Full | Needs CDN or bundled |
| Dependencies | PyQt6 only | plotly, PyQtWebEngine |

---

## Error Handling

All widgets handle errors gracefully:

```python
# Factory falls back to matplotlib if plotly unavailable
plot = create_plot_widget(ontology_manager, qudt_manager, backend='plotly')
# If plotly not installed, returns MatplotlibPlotWidget with warning

# Container returns None for missing series
series = container.get_series('dyn:NonExistent')  # Returns None
array = container.get_array('dyn:NonExistent')    # Returns None

# Resolver returns fallback labels
label = resolver.get_axis_label('dyn:UnknownType')  # Returns "Unknown Type"
```

---

## Logging Configuration

All classes use Python's standard logging module:

```python
import logging

# Enable debug logging for base widgets
logging.getLogger('dynamat.gui.widgets.base').setLevel(logging.DEBUG)

# Detailed format
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(funcName)s:%(lineno)d - %(levelname)s - %(message)s'
)
```

Log messages include:
- Widget initialization
- Series additions/removals
- Axis label resolution
- Backend selection
- Error details with stack traces

---

## References

1. Matplotlib Documentation: https://matplotlib.org/stable/
2. Plotly Python Documentation: https://plotly.com/python/
3. PyQt6 Widgets: https://doc.qt.io/qtforpython-6/
4. QUDT Ontology: http://www.qudt.org/
