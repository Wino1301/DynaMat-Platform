"""
DynaMat Platform - Base Plot Widget
Base class defining the common interface for plotting backends.
"""

import logging
from typing import Dict, List, Optional, Any, Union, Tuple

import numpy as np

from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import pyqtSignal

from rdflib import URIRef

from .plotting_config import PlottingConfig
from .series_metadata_resolver import SeriesMetadataResolver

logger = logging.getLogger(__name__)


class BasePlotWidget(QWidget):
    """
    Base class for plotting widgets.

    Defines the common interface that all plotting backends (Matplotlib, Plotly)
    must implement. This enables seamless switching between backends via configuration.

    Signals:
        traceClicked(str, float, float): Emitted when a trace is clicked (uri, x, y)
        rangeSelected(float, float): Emitted when a range is selected (x0, x1)
        plotUpdated(): Emitted after plot is refreshed
        cursorMoved(float, float): Emitted when cursor moves over plot (x, y)

    All subclasses must implement:
        - _setup_ui(): Set up the widget UI
        - set_axis_series(): Configure axis labels from ontology
        - add_trace(): Add data to the plot
        - add_trace_from_container(): Add data from DataSeriesWidget
        - add_reference_line(): Add horizontal/vertical reference lines
        - configure_subplot(): Set up multi-panel layouts
        - set_active_subplot(): Switch active subplot
        - refresh(): Update the display
        - save_figure(): Export to file
        - clear(): Clear all content
        - fill_between(): Add filled region between curves
        - apply_style_preset(): Apply a named style preset
        - set_tick_params(): Configure tick label sizes
    """

    # Signals
    traceClicked = pyqtSignal(str, float, float)  # uri, x, y
    rangeSelected = pyqtSignal(float, float)       # x0, x1
    plotUpdated = pyqtSignal()
    cursorMoved = pyqtSignal(float, float)         # x, y

    # Default plot styling (used when no PlottingConfig is provided)
    DEFAULT_FIGSIZE = (10, 6)
    DEFAULT_DPI = 100
    DEFAULT_LINE_WIDTH = 1.5
    DEFAULT_GRID_ALPHA = 0.3

    def __init__(
        self,
        ontology_manager,
        qudt_manager,
        figsize: Tuple[float, float] = None,
        show_toolbar: bool = True,
        parent=None,
        config: PlottingConfig = None
    ):
        """
        Initialize the plot widget.

        Args:
            ontology_manager: OntologyManager for SeriesType queries
            qudt_manager: QUDTManager for unit symbol resolution
            figsize: Figure size tuple (width, height) in inches
            show_toolbar: Whether to show the navigation toolbar
            parent: Parent widget
            config: Optional PlottingConfig for styling defaults
        """
        super().__init__(parent)

        self.ontology_manager = ontology_manager
        self.qudt_manager = qudt_manager
        self.config = config or PlottingConfig()

        # Use config values, with explicit figsize taking precedence
        self.figsize = figsize or self.config.figsize

        self.show_toolbar = show_toolbar

        # Create metadata resolver for axis labels (shared by all subclasses)
        self.resolver = SeriesMetadataResolver(ontology_manager, qudt_manager)

        # Trace management
        self._traces: Dict[str, Dict[str, Any]] = {}

        # Subplot configuration
        self._subplot_rows = 1
        self._subplot_cols = 1
        self._active_subplot = 0

        # Axis configuration per subplot
        self._axis_config: Dict[int, Dict[str, str]] = {}

    # =========================================================================
    # Methods to be implemented by subclasses
    # =========================================================================

    def _setup_ui(self, show_toolbar: bool):
        """Setup the widget UI. Must be called in subclass __init__."""
        raise NotImplementedError("Subclass must implement _setup_ui()")

    def set_axis_series(
        self,
        x_series_type: str,
        y_series_type: str,
        x_unit: str = None,
        y_unit: str = None,
        subplot_idx: int = None
    ):
        """
        Configure axis labels from SeriesType URIs.

        Args:
            x_series_type: SeriesType URI for x-axis (e.g., 'dyn:Strain')
            y_series_type: SeriesType URI for y-axis (e.g., 'dyn:Stress')
            x_unit: Override x-axis unit URI (optional)
            y_unit: Override y-axis unit URI (optional)
            subplot_idx: Subplot index, or None for active subplot
        """
        raise NotImplementedError("Subclass must implement set_axis_series()")

    def add_trace(
        self,
        x_data: np.ndarray,
        y_data: np.ndarray,
        uri: str = None,
        label: str = None,
        color: str = None,
        linestyle: str = '-',
        linewidth: float = None,
        alpha: float = 1.0,
        marker: str = None,
        subplot_idx: int = None
    ) -> str:
        """
        Add a data trace to the plot.

        Args:
            x_data: X-axis data array
            y_data: Y-axis data array
            uri: Optional URI identifying the data series
            label: Legend label for the trace
            color: Line color
            linestyle: Line style ('-', '--', '-.', ':')
            linewidth: Line width in points
            alpha: Opacity (0.0 to 1.0)
            marker: Marker style (None, 'o', 's', etc.)
            subplot_idx: Subplot index, or None for active subplot

        Returns:
            Trace ID string for later reference
        """
        raise NotImplementedError("Subclass must implement add_trace()")

    def add_trace_from_container(
        self,
        data_container,
        x_uri: Union[URIRef, str],
        y_uri: Union[URIRef, str],
        label: str = None,
        color: str = None,
        linestyle: str = '-',
        linewidth: float = None,
        alpha: float = 1.0,
        marker: str = None,
        subplot_idx: int = None
    ) -> Optional[str]:
        """
        Add a trace from a DataSeriesWidget container.

        Args:
            data_container: DataSeriesWidget containing the data
            x_uri: URI of the x-axis series
            y_uri: URI of the y-axis series
            label: Legend label (optional)
            color: Line color
            linestyle: Line style
            linewidth: Line width
            alpha: Opacity
            marker: Marker style
            subplot_idx: Subplot index

        Returns:
            Trace ID string, or None if series not found
        """
        raise NotImplementedError("Subclass must implement add_trace_from_container()")

    def remove_trace(self, trace_id: str) -> bool:
        """
        Remove a trace from the plot.

        Args:
            trace_id: ID returned by add_trace

        Returns:
            True if trace was removed, False if not found
        """
        raise NotImplementedError("Subclass must implement remove_trace()")

    def clear_traces(self, subplot_idx: int = None):
        """
        Clear all traces from a subplot (or all subplots).

        Args:
            subplot_idx: Specific subplot to clear, or None for all
        """
        raise NotImplementedError("Subclass must implement clear_traces()")

    def add_reference_line(
        self,
        orientation: str,
        value: float,
        color: str = 'k',
        linestyle: str = '--',
        linewidth: float = 0.5,
        alpha: float = 0.5,
        label: str = None,
        subplot_idx: int = None
    ):
        """
        Add a horizontal or vertical reference line.

        Args:
            orientation: 'h'/'horizontal' or 'v'/'vertical'
            value: Position of the line
            color: Line color
            linestyle: Line style
            linewidth: Line width
            alpha: Opacity
            label: Legend label (optional)
            subplot_idx: Subplot index
        """
        raise NotImplementedError("Subclass must implement add_reference_line()")

    def configure_subplot(self, rows: int, cols: int):
        """
        Configure subplot layout.

        Args:
            rows: Number of rows
            cols: Number of columns
        """
        raise NotImplementedError("Subclass must implement configure_subplot()")

    def set_active_subplot(self, idx: int):
        """
        Set the active subplot for subsequent operations.

        Args:
            idx: Subplot index (0-based, row-major order)
        """
        raise NotImplementedError("Subclass must implement set_active_subplot()")

    def refresh(self):
        """Refresh the plot canvas."""
        raise NotImplementedError("Subclass must implement refresh()")

    def save_figure(self, filepath: str, dpi: int = 150, **kwargs):
        """
        Save the figure to a file.

        Args:
            filepath: Output file path
            dpi: Resolution in dots per inch
            **kwargs: Additional backend-specific arguments
        """
        raise NotImplementedError("Subclass must implement save_figure()")

    def clear(self):
        """Clear all content from all subplots."""
        raise NotImplementedError("Subclass must implement clear()")

    def fill_between(
        self,
        x: np.ndarray,
        y_low: np.ndarray,
        y_high: np.ndarray,
        color: str = None,
        alpha: float = 0.3,
        label: str = None,
        subplot_idx: int = None
    ):
        """
        Add a filled region between two curves (e.g., uncertainty bands).

        Args:
            x: X-axis data array
            y_low: Lower bound y-data array
            y_high: Upper bound y-data array
            color: Fill color
            alpha: Fill opacity (0.0 to 1.0)
            label: Legend label (optional)
            subplot_idx: Subplot index, or None for active subplot
        """
        raise NotImplementedError("Subclass must implement fill_between()")

    def apply_style_preset(self, preset_name: str):
        """
        Apply a named style preset.

        Args:
            preset_name: Style preset name (e.g., 'seaborn-v0_8-whitegrid', 'ggplot')
        """
        raise NotImplementedError("Subclass must implement apply_style_preset()")

    def set_tick_params(self, axis: str = 'both', labelsize: float = None, subplot_idx: int = None):
        """
        Configure tick label parameters.

        Args:
            axis: Which axis to configure ('x', 'y', or 'both')
            labelsize: Font size for tick labels
            subplot_idx: Subplot index, or None for active subplot
        """
        raise NotImplementedError("Subclass must implement set_tick_params()")

    # =========================================================================
    # Concrete Methods - Shared by all implementations
    # =========================================================================

    def get_trace_ids(self, subplot_idx: int = None) -> List[str]:
        """Get list of trace IDs for a subplot (or all)."""
        if subplot_idx is None:
            return list(self._traces.keys())
        return [tid for tid, info in self._traces.items()
                if info.get('subplot_idx') == subplot_idx]

    def get_active_subplot(self) -> int:
        """Get the current active subplot index."""
        return self._active_subplot

    def get_subplot_count(self) -> int:
        """Get total number of subplots."""
        return self._subplot_rows * self._subplot_cols

    def add_ontology_trace(
        self,
        x_data: np.ndarray,
        y_data: np.ndarray,
        x_series_type_uri: str = None,
        y_series_type_uri: str = None,
        label: str = None,
        color: str = None,
        linestyle: str = '-',
        linewidth: float = None,
        alpha: float = 1.0,
        marker: str = None,
        analysis_method: str = None,
        subplot_idx: int = None
    ) -> str:
        """
        Add a trace with ontology-driven axis labels and legend text.

        Automatically resolves axis labels from SeriesType URIs and generates
        legend text using the ontology's legend templates.

        Args:
            x_data: X-axis data array
            y_data: Y-axis data array
            x_series_type_uri: SeriesType URI for x-axis (e.g., 'dyn:Time')
            y_series_type_uri: SeriesType URI for y-axis (e.g., 'dyn:Stress')
            label: Legend label override (auto-resolved if None)
            color: Line color
            linestyle: Line style ('-', '--', '-.', ':')
            linewidth: Line width in points
            alpha: Opacity (0.0 to 1.0)
            marker: Marker style (None, 'o', 's', etc.)
            analysis_method: Analysis method for legend (e.g., '1-wave', '3-wave')
            subplot_idx: Subplot index, or None for active subplot

        Returns:
            Trace ID string for later reference

        Example:
            >>> plot.add_ontology_trace(
            ...     strain, stress,
            ...     x_series_type_uri='dyn:Strain',
            ...     y_series_type_uri='dyn:Stress',
            ...     analysis_method='1-wave',
            ...     color='blue'
            ... )
            # Auto-sets xlabel="Strain", ylabel="Stress (MPa)", legend="Engineering Stress (1-wave)"
        """
        if x_series_type_uri:
            self.set_xlabel(
                self.resolver.get_axis_label(x_series_type_uri),
                subplot_idx=subplot_idx
            )
        if y_series_type_uri:
            self.set_ylabel(
                self.resolver.get_axis_label(y_series_type_uri),
                subplot_idx=subplot_idx
            )
        if label is None and y_series_type_uri:
            label = self.resolver.get_legend_text(y_series_type_uri, analysis_method)

        return self.add_trace(
            x_data, y_data,
            label=label, color=color,
            linestyle=linestyle, linewidth=linewidth,
            alpha=alpha, marker=marker,
            subplot_idx=subplot_idx
        )

    # =========================================================================
    # Optional Methods - Can be overridden by subclasses
    # =========================================================================

    def set_xlabel(self, label: str, fontsize: float = None, subplot_idx: int = None):
        """Set x-axis label directly."""
        pass

    def set_ylabel(self, label: str, fontsize: float = None, subplot_idx: int = None):
        """Set y-axis label directly."""
        pass

    def set_title(self, title: str, fontsize: float = None, subplot_idx: int = None):
        """Set the title for a subplot."""
        pass

    def set_xlim(self, xmin: float = None, xmax: float = None, subplot_idx: int = None):
        """Set x-axis limits."""
        pass

    def set_ylim(self, ymin: float = None, ymax: float = None, subplot_idx: int = None):
        """Set y-axis limits."""
        pass

    def enable_legend(
        self,
        visible: bool = True,
        loc: str = 'best',
        title: str = None,
        fontsize: float = None,
        title_fontsize: float = None,
        subplot_idx: int = None
    ):
        """Enable or disable the legend."""
        pass

    def enable_grid(
        self,
        visible: bool = True,
        alpha: float = None,
        linewidth: float = None,
        subplot_idx: int = None
    ):
        """Enable or disable grid lines."""
        pass

    def add_horizontal_span(
        self,
        ymin: float,
        ymax: float,
        color: str = 'yellow',
        alpha: float = 0.2,
        subplot_idx: int = None
    ):
        """Add a horizontal span (shaded region)."""
        pass

    def add_vertical_span(
        self,
        xmin: float,
        xmax: float,
        color: str = 'yellow',
        alpha: float = 0.2,
        subplot_idx: int = None
    ):
        """Add a vertical span (shaded region)."""
        pass
