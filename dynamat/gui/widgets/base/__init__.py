"""
DynaMat Platform - GUI Base Widgets Module
Base widget components used throughout the application
"""

from .unit_value_widget import UnitValueWidget
from .series_metadata_resolver import SeriesMetadataResolver
from .data_series_widget import DataSeriesWidget

# Plot widgets
from .base_plot_widget import BasePlotWidget
from .data_series_plot_widget import MatplotlibPlotWidget, DataSeriesPlotWidget
from .plot_widget_factory import create_plot_widget, get_available_backends, is_backend_available

# Plotly widget is optional (requires plotly and PyQtWebEngine)
try:
    from .plotly_plot_widget import PlotlyPlotWidget
except ImportError:
    PlotlyPlotWidget = None

__all__ = [
    'UnitValueWidget',
    'SeriesMetadataResolver',
    'DataSeriesWidget',
    # Plot widgets
    'BasePlotWidget',
    'MatplotlibPlotWidget',
    'DataSeriesPlotWidget',  # Backwards compatibility alias
    'PlotlyPlotWidget',
    'create_plot_widget',
    'get_available_backends',
    'is_backend_available',
]
