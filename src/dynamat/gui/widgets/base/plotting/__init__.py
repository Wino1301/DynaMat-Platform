"""
DynaMat Platform - Plotting Submodule
Reusable plotting widgets with ontology-driven axis labels, fill_between support,
configurable font sizes, and multiple backend support (Matplotlib, Plotly).
"""

from .plotting_config import PlottingConfig
from .base_plot_widget import BasePlotWidget
from .matplotlib_plot_widget import MatplotlibPlotWidget, DataSeriesPlotWidget
from .plot_widget_factory import create_plot_widget, get_available_backends, is_backend_available
from .series_metadata_resolver import SeriesMetadataResolver
from .data_series_widget import DataSeriesWidget

# Plotly widget is optional (requires plotly and PyQtWebEngine)
try:
    from .plotly_plot_widget import PlotlyPlotWidget
except ImportError:
    PlotlyPlotWidget = None

__all__ = [
    'PlottingConfig',
    'BasePlotWidget',
    'MatplotlibPlotWidget',
    'DataSeriesPlotWidget',
    'PlotlyPlotWidget',
    'create_plot_widget',
    'get_available_backends',
    'is_backend_available',
    'SeriesMetadataResolver',
    'DataSeriesWidget',
]
