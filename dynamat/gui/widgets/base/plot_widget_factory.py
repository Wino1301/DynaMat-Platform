"""
DynaMat Platform - Plot Widget Factory
Factory function to create plot widgets based on configuration.
"""

import logging
from typing import Tuple, Optional

from dynamat.config import Config
from .base_plot_widget import BasePlotWidget

logger = logging.getLogger(__name__)


def create_plot_widget(
    ontology_manager,
    qudt_manager,
    figsize: Tuple[float, float] = None,
    show_toolbar: bool = True,
    backend: str = None,
    parent=None
) -> BasePlotWidget:
    """
    Create a plot widget based on configuration or explicit backend selection.

    This factory function creates either a Plotly-based or Matplotlib-based
    plotting widget depending on:
    1. The explicit `backend` parameter (if provided)
    2. The `Config.PLOT_BACKEND` setting
    3. Availability of required dependencies (falls back to Matplotlib)

    Args:
        ontology_manager: OntologyManager for SeriesType queries
        qudt_manager: QUDTManager for unit symbol resolution
        figsize: Figure size tuple (width, height) in inches
        show_toolbar: Whether to show the navigation toolbar
        backend: Explicit backend selection ('plotly' or 'matplotlib').
                 If None, uses Config.PLOT_BACKEND.
        parent: Parent widget

    Returns:
        BasePlotWidget: Either PlotlyPlotWidget or MatplotlibPlotWidget

    Example:
        >>> plot = create_plot_widget(ontology_manager, qudt_manager)
        >>> plot.set_axis_series('dyn:Strain', 'dyn:Stress')
        >>> plot.add_trace(strain, stress, label="1-wave", color="blue")
        >>> plot.refresh()

        >>> # Force Matplotlib backend
        >>> mpl_plot = create_plot_widget(ontology_manager, qudt_manager, backend='matplotlib')

        >>> # Force Plotly backend
        >>> plotly_plot = create_plot_widget(ontology_manager, qudt_manager, backend='plotly')
    """
    # Determine backend to use
    selected_backend = backend if backend else Config.PLOT_BACKEND
    selected_backend = selected_backend.lower()

    if selected_backend == "plotly":
        try:
            from .plotly_plot_widget import PlotlyPlotWidget, PLOTLY_AVAILABLE, WEBENGINE_AVAILABLE

            if not PLOTLY_AVAILABLE:
                logger.warning("Plotly not available. Install with: pip install plotly")
                logger.info("Falling back to Matplotlib backend")
                selected_backend = "matplotlib"
            elif not WEBENGINE_AVAILABLE:
                logger.warning("PyQtWebEngine not available. Install with: pip install PyQtWebEngine")
                logger.info("Falling back to Matplotlib backend")
                selected_backend = "matplotlib"
            else:
                logger.debug("Creating PlotlyPlotWidget")
                return PlotlyPlotWidget(
                    ontology_manager,
                    qudt_manager,
                    figsize=figsize,
                    show_toolbar=show_toolbar,
                    parent=parent
                )
        except ImportError as e:
            logger.warning(f"Failed to import Plotly components: {e}")
            logger.info("Falling back to Matplotlib backend")
            selected_backend = "matplotlib"

    # Default: Matplotlib backend
    from .data_series_plot_widget import MatplotlibPlotWidget

    logger.debug("Creating MatplotlibPlotWidget")
    return MatplotlibPlotWidget(
        ontology_manager,
        qudt_manager,
        figsize=figsize,
        show_toolbar=show_toolbar,
        parent=parent
    )


def get_available_backends() -> list:
    """
    Get list of available plotting backends.

    Returns:
        List of backend names that can be used (always includes 'matplotlib')
    """
    backends = ['matplotlib']  # Always available

    try:
        from .plotly_plot_widget import PLOTLY_AVAILABLE, WEBENGINE_AVAILABLE
        if PLOTLY_AVAILABLE and WEBENGINE_AVAILABLE:
            backends.append('plotly')
    except ImportError:
        pass

    return backends


def is_backend_available(backend: str) -> bool:
    """
    Check if a specific backend is available.

    Args:
        backend: Backend name ('plotly' or 'matplotlib')

    Returns:
        True if the backend is available and can be used
    """
    backend = backend.lower()

    if backend == 'matplotlib':
        return True  # Always available

    if backend == 'plotly':
        try:
            from .plotly_plot_widget import PLOTLY_AVAILABLE, WEBENGINE_AVAILABLE
            return PLOTLY_AVAILABLE and WEBENGINE_AVAILABLE
        except ImportError:
            return False

    return False
