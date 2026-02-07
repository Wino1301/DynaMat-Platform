"""
DynaMat Platform - GUI Base Widgets Module
Base widget components used throughout the application
"""

from .unit_value_widget import UnitValueWidget
from .property_display import PropertyDisplayConfig, PropertyDisplayWidget
from .raw_data_loader import RawDataLoaderConfig, RawDataLoaderWidget

# Plot widgets (from plotting submodule)
from .plotting import (
    PlottingConfig,
    BasePlotWidget,
    MatplotlibPlotWidget,
    DataSeriesPlotWidget,
    PlotlyPlotWidget,
    create_plot_widget,
    get_available_backends,
    is_backend_available,
    SeriesMetadataResolver,
    DataSeriesWidget,
)

# Entity selector components
from .entity_selector import (
    EntitySelectorConfig,
    SelectionMode,
    FilterPanel,
    DetailsPanel,
    EntitySelectorWidget,
    EntitySelectorDialog,
)

__all__ = [
    'UnitValueWidget',
    'SeriesMetadataResolver',
    'DataSeriesWidget',
    'PropertyDisplayConfig',
    'PropertyDisplayWidget',
    'RawDataLoaderConfig',
    'RawDataLoaderWidget',
    # Plot widgets
    'PlottingConfig',
    'BasePlotWidget',
    'MatplotlibPlotWidget',
    'DataSeriesPlotWidget',  # Backwards compatibility alias
    'PlotlyPlotWidget',
    'create_plot_widget',
    'get_available_backends',
    'is_backend_available',
    # Entity selector
    'EntitySelectorConfig',
    'SelectionMode',
    'FilterPanel',
    'DetailsPanel',
    'EntitySelectorWidget',
    'EntitySelectorDialog',
]
