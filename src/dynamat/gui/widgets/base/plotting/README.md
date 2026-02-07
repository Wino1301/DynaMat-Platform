# Plotting Submodule

Reusable plotting widgets with ontology-driven axis labels, fill_between support, configurable font sizes, and multiple backend support.

## Architecture

```
plotting/
├── __init__.py                    # Public exports
├── plotting_config.py             # PlottingConfig dataclass
├── base_plot_widget.py            # Abstract base class
├── matplotlib_plot_widget.py      # Matplotlib implementation
├── plotly_plot_widget.py          # Plotly implementation (optional)
├── plot_widget_factory.py         # Factory function
├── series_metadata_resolver.py    # Ontology label resolver
├── data_series_widget.py          # Data container
└── README.md
```

## Quick Start

```python
from dynamat.gui.widgets.base.plotting import create_plot_widget, PlottingConfig

# Basic usage
plot = create_plot_widget(ontology_manager, qudt_manager)
plot.add_trace(x_data, y_data, label="My Data", color="blue")
plot.set_xlabel("Time (ms)")
plot.set_ylabel("Signal")
plot.enable_grid()
plot.enable_legend()
plot.refresh()

# Ontology-driven (auto-resolves axis labels from SeriesType URIs)
plot.add_ontology_trace(
    strain, stress,
    x_series_type_uri='dyn:Strain',
    y_series_type_uri='dyn:Stress',
    analysis_method='1-wave',
    label="1-Wave", color="blue"
)
# xlabel/ylabel auto-set to "Strain", "Stress (MPa)"
```

## PlottingConfig

Controls all styling defaults via a dataclass:

```python
config = PlottingConfig(
    figsize=(12, 8),
    dpi=150,
    line_width=2.0,
    title_font_size=18.0,
    axis_label_font_size=16.0,
    tick_label_font_size=14.0,
    legend_font_size=14.0,
    grid_visible=True,
    grid_alpha=0.2,
    grid_line_width=0.5,
    matplotlib_style='default',
    plotly_template='plotly_white',
)
plot = create_plot_widget(ontology_manager, qudt_manager, config=config)
```

### Default Values

| Field | Default | Description |
|-------|---------|-------------|
| `figsize` | `(10, 6)` | Figure size in inches |
| `dpi` | `100` | Dots per inch |
| `line_width` | `1.5` | Default line width |
| `grid_alpha` | `0.3` | Grid line opacity |
| `grid_line_width` | `0.5` | Grid line width |
| `title_font_size` | `16.0` | Title font size |
| `axis_label_font_size` | `14.0` | Axis label font size |
| `tick_label_font_size` | `12.0` | Tick label font size |
| `legend_font_size` | `12.0` | Legend font size |
| `legend_title_font_size` | `13.0` | Legend title font size |
| `matplotlib_style` | `'default'` | Matplotlib style preset |
| `plotly_template` | `'plotly_white'` | Plotly template |

## API Reference

### Core Methods (all backends)

```python
# Traces
trace_id = plot.add_trace(x, y, label="...", color="...", linestyle="-", linewidth=1.5, alpha=1.0, marker=None)
trace_id = plot.add_ontology_trace(x, y, x_series_type_uri="dyn:Time", y_series_type_uri="dyn:Stress", analysis_method="1-wave")
plot.add_trace_from_container(data_container, x_uri, y_uri, label="...")
plot.remove_trace(trace_id)
plot.clear_traces(subplot_idx=None)

# Uncertainty bands
plot.fill_between(x, y_low, y_high, color="blue", alpha=0.3, label="Uncertainty")

# Axis labels
plot.set_xlabel("Label", fontsize=14)
plot.set_ylabel("Label", fontsize=14)
plot.set_axis_series("dyn:Strain", "dyn:Stress")  # Ontology-driven

# Styling
plot.set_title("Title", fontsize=16)
plot.set_xlim(xmin, xmax)
plot.set_ylim(ymin, ymax)
plot.enable_grid(visible=True, alpha=0.3, linewidth=0.5)
plot.enable_legend(visible=True, loc="best", title="Legend", fontsize=12)
plot.set_tick_params(axis="both", labelsize=12)
plot.apply_style_preset("seaborn-v0_8-whitegrid")

# Reference lines & spans
plot.add_reference_line("h", value=100, color="red", linestyle="--")
plot.add_reference_line("v", value=0, label="t=0")
plot.add_horizontal_span(ymin, ymax, color="yellow", alpha=0.2)
plot.add_vertical_span(xmin, xmax, color="yellow", alpha=0.2)

# Multi-panel
plot.configure_subplot(rows=2, cols=1)
plot.set_active_subplot(0)

# Canvas
plot.refresh()
plot.save_figure("output.png", dpi=300)
plot.clear()
```

### Backend Selection

```python
# Auto-select from Config.PLOT_BACKEND
plot = create_plot_widget(ontology_manager, qudt_manager)

# Force specific backend
plot = create_plot_widget(ontology_manager, qudt_manager, backend="matplotlib")
plot = create_plot_widget(ontology_manager, qudt_manager, backend="plotly")

# Check availability
backends = get_available_backends()  # ['matplotlib'] or ['matplotlib', 'plotly']
is_backend_available("plotly")       # True/False
```

### Ontology-Driven Labels

The `add_ontology_trace()` method auto-resolves axis labels and legend text from the ontology:

```python
# This single call:
plot.add_ontology_trace(
    strain, stress,
    x_series_type_uri='dyn:Strain',
    y_series_type_uri='dyn:Stress',
    analysis_method='1-wave'
)

# Is equivalent to:
plot.set_xlabel("Strain")           # Resolved from dyn:Strain
plot.set_ylabel("Stress (MPa)")     # Resolved from dyn:Stress + QUDT unit
plot.add_trace(strain, stress, label="Engineering Stress (1-wave)")  # From legend template
```

### Publication-Quality Example

```python
config = PlottingConfig(
    figsize=(8, 6),
    dpi=300,
    line_width=2.0,
    title_font_size=18.0,
    axis_label_font_size=16.0,
    tick_label_font_size=14.0,
    legend_font_size=14.0,
    grid_alpha=0.2,
)

plot = create_plot_widget(ontology_manager, qudt_manager, config=config)
plot.add_ontology_trace(strain, stress_mean,
    x_series_type_uri='dyn:Strain', y_series_type_uri='dyn:Stress',
    label="Mean", color="blue")
plot.fill_between(strain, stress_low, stress_high,
    color="blue", alpha=0.2, label="95% CI")
plot.set_title("Stress-Strain Response")
plot.set_tick_params(axis='both')
plot.enable_grid()
plot.enable_legend(loc='upper left')
plot.refresh()
plot.save_figure("stress_strain.png", dpi=300)
```

## Backwards Compatibility

- `DataSeriesPlotWidget` is an alias for `MatplotlibPlotWidget`
- All imports from `dynamat.gui.widgets.base` still work (re-exported)
- Existing `set_xlabel(label)` calls without `fontsize` parameter still work
- Existing `enable_legend(visible, loc)` calls without new parameters still work
