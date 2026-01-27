"""
DynaMat Platform - Data Series Plot Widget
Matplotlib-based plotting widget with ontology-driven axis labels.
"""

import logging
from typing import Dict, List, Optional, Any, Union, Tuple
import uuid

import numpy as np

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QToolBar, QSizePolicy
)
from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtGui import QAction

# Matplotlib imports with Qt6 backend
import matplotlib
matplotlib.use('QtAgg')  # Set backend before importing pyplot
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg, NavigationToolbar2QT
from matplotlib.figure import Figure
from matplotlib.axes import Axes

from rdflib import URIRef

from .base_plot_widget import BasePlotWidget
from .series_metadata_resolver import SeriesMetadataResolver
from .data_series_widget import DataSeriesWidget

logger = logging.getLogger(__name__)


class MatplotlibPlotWidget(BasePlotWidget):
    """
    Matplotlib-based plotting widget with ontology-driven axis labels.

    Embeds a matplotlib canvas in PyQt6 and uses ontology queries to determine
    axis labels from SeriesType URIs. Supports single and multi-panel layouts.

    Signals:
        traceClicked(str, float, float): Emitted when a trace is clicked (uri, x, y)
        rangeSelected(float, float): Emitted when a range is selected (x0, x1)
        plotUpdated(): Emitted after plot is refreshed
        cursorMoved(float, float): Emitted when cursor moves over plot (x, y)

    Widget Structure:
        MatplotlibPlotWidget(QWidget)
        +-- QVBoxLayout
            +-- QToolBar (optional: save, zoom, pan)
            +-- FigureCanvasQTAgg
                +-- matplotlib.figure.Figure
                    +-- Axes (or list of Axes for subplots)

    Example:
        >>> plot = MatplotlibPlotWidget(ontology_manager, qudt_manager)
        >>> plot.set_axis_series('dyn:Strain', 'dyn:Stress')
        >>> plot.add_trace(strain_data, stress_data, label="1-wave", color="blue")
        >>> plot.enable_legend()
        >>> plot.refresh()
    """

    def __init__(
        self,
        ontology_manager,
        qudt_manager,
        figsize: Tuple[float, float] = None,
        show_toolbar: bool = True,
        parent=None
    ):
        """
        Initialize the plot widget.

        Args:
            ontology_manager: OntologyManager for SeriesType queries
            qudt_manager: QUDTManager for unit symbol resolution
            figsize: Figure size tuple (width, height) in inches
            show_toolbar: Whether to show the matplotlib navigation toolbar
            parent: Parent widget
        """
        super().__init__(ontology_manager, qudt_manager, figsize, show_toolbar, parent)

        # Create metadata resolver for axis labels
        self.resolver = SeriesMetadataResolver(ontology_manager, qudt_manager)

        # Axes list for subplots
        self._axes: List[Axes] = []

        # Setup UI
        self._setup_ui(show_toolbar)

        logger.debug("MatplotlibPlotWidget initialized")

    def _setup_ui(self, show_toolbar: bool):
        """Setup the widget UI with matplotlib canvas."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Create matplotlib figure and canvas
        self.figure = Figure(figsize=self.figsize, dpi=self.DEFAULT_DPI)
        self.canvas = FigureCanvasQTAgg(self.figure)
        self.canvas.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        # Create initial axes
        self._create_subplots(1, 1)

        # Add navigation toolbar if requested
        if show_toolbar:
            self.toolbar = NavigationToolbar2QT(self.canvas, self)
            layout.addWidget(self.toolbar)
        else:
            self.toolbar = None

        # Add canvas
        layout.addWidget(self.canvas)

        # Connect mouse events
        self.canvas.mpl_connect('motion_notify_event', self._on_mouse_move)
        self.canvas.mpl_connect('button_press_event', self._on_mouse_click)

    def _create_subplots(self, rows: int, cols: int):
        """Create subplot axes."""
        self.figure.clear()
        self._axes = []

        for i in range(rows * cols):
            ax = self.figure.add_subplot(rows, cols, i + 1)
            self._axes.append(ax)

        self._subplot_rows = rows
        self._subplot_cols = cols
        self._active_subplot = 0

    def _get_active_ax(self) -> Axes:
        """Get the currently active axes."""
        if 0 <= self._active_subplot < len(self._axes):
            return self._axes[self._active_subplot]
        return self._axes[0]

    def _get_ax(self, subplot_idx: Optional[int] = None) -> Axes:
        """Get axes by index or active axes if None."""
        if subplot_idx is None:
            return self._get_active_ax()
        if 0 <= subplot_idx < len(self._axes):
            return self._axes[subplot_idx]
        return self._axes[0]

    # =========================================================================
    # Axis Configuration (Ontology-Driven)
    # =========================================================================

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

        Queries the ontology for quantity kind and unit symbol to build
        axis labels automatically.

        Args:
            x_series_type: SeriesType URI for x-axis (e.g., 'dyn:Strain', 'dyn:Time')
            y_series_type: SeriesType URI for y-axis (e.g., 'dyn:Stress')
            x_unit: Override x-axis unit URI (optional)
            y_unit: Override y-axis unit URI (optional)
            subplot_idx: Subplot index, or None for active subplot

        Example:
            >>> plot.set_axis_series('dyn:Strain', 'dyn:Stress')
            # Sets x-axis: "Strain", y-axis: "Stress (MPa)"

            >>> plot.set_axis_series('dyn:Time', 'dyn:IncidentPulse')
            # Sets x-axis: "Time (ms)", y-axis: "Incident Pulse (V)"
        """
        idx = subplot_idx if subplot_idx is not None else self._active_subplot

        # Store configuration
        self._axis_config[idx] = {
            'x_series': x_series_type,
            'y_series': y_series_type,
            'x_unit': x_unit,
            'y_unit': y_unit
        }

        # Get axis labels from resolver
        if x_unit:
            x_label = self.resolver.get_axis_label_with_custom_unit(x_series_type, x_unit)
        else:
            x_label = self.resolver.get_axis_label(x_series_type)

        if y_unit:
            y_label = self.resolver.get_axis_label_with_custom_unit(y_series_type, y_unit)
        else:
            y_label = self.resolver.get_axis_label(y_series_type)

        # Apply to axes
        ax = self._get_ax(subplot_idx)
        ax.set_xlabel(x_label)
        ax.set_ylabel(y_label)

        logger.debug(f"Set axis labels: x='{x_label}', y='{y_label}' for subplot {idx}")

    def set_xlabel(self, label: str, subplot_idx: int = None):
        """Set x-axis label directly."""
        ax = self._get_ax(subplot_idx)
        ax.set_xlabel(label)

    def set_ylabel(self, label: str, subplot_idx: int = None):
        """Set y-axis label directly."""
        ax = self._get_ax(subplot_idx)
        ax.set_ylabel(label)

    # =========================================================================
    # Trace Management
    # =========================================================================

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
            color: Line color (matplotlib color spec)
            linestyle: Line style ('-', '--', '-.', ':')
            linewidth: Line width in points
            alpha: Opacity (0.0 to 1.0)
            marker: Marker style (None, 'o', 's', etc.)
            subplot_idx: Subplot index, or None for active subplot

        Returns:
            Trace ID string for later reference

        Example:
            >>> trace_id = plot.add_trace(strain, stress, label="1-wave", color="blue")
            >>> plot.remove_trace(trace_id)
        """
        ax = self._get_ax(subplot_idx)
        lw = linewidth if linewidth is not None else self.DEFAULT_LINE_WIDTH

        # Plot the data
        plot_kwargs = {
            'linestyle': linestyle,
            'linewidth': lw,
            'alpha': alpha,
        }
        if color:
            plot_kwargs['color'] = color
        if label:
            plot_kwargs['label'] = label
        if marker:
            plot_kwargs['marker'] = marker

        line, = ax.plot(x_data, y_data, **plot_kwargs)

        # Generate trace ID
        trace_id = str(uuid.uuid4())[:8]

        # Store trace info
        self._traces[trace_id] = {
            'line': line,
            'uri': uri,
            'label': label,
            'subplot_idx': subplot_idx if subplot_idx is not None else self._active_subplot,
            'x_data': x_data,
            'y_data': y_data
        }

        logger.debug(f"Added trace {trace_id}: {label or 'unlabeled'}")
        return trace_id

    def add_trace_from_container(
        self,
        data_container: DataSeriesWidget,
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

        Retrieves x and y data from the container by URI and plots them.
        If no label is provided, uses the legend from the y-series metadata.

        Args:
            data_container: DataSeriesWidget containing the data
            x_uri: URI of the x-axis series
            y_uri: URI of the y-axis series
            label: Legend label (optional, uses y-series legend if not provided)
            color: Line color
            linestyle: Line style
            linewidth: Line width
            alpha: Opacity
            marker: Marker style
            subplot_idx: Subplot index

        Returns:
            Trace ID string, or None if series not found

        Example:
            >>> plot.add_trace_from_container(
            ...     container,
            ...     x_uri=URIRef("dyn:Strain"),
            ...     y_uri=URIRef("dyn:Stress"),
            ...     label="1-wave", color="blue"
            ... )
        """
        # Get data from container
        x_series = data_container.get_series(x_uri)
        y_series = data_container.get_series(y_uri)

        if x_series is None:
            logger.warning(f"X series not found in container: {x_uri}")
            return None
        if y_series is None:
            logger.warning(f"Y series not found in container: {y_uri}")
            return None

        # Use y-series legend if no label provided
        if label is None:
            label = y_series.get('legend', '')

        return self.add_trace(
            x_data=x_series['array'],
            y_data=y_series['array'],
            uri=str(y_uri),
            label=label,
            color=color,
            linestyle=linestyle,
            linewidth=linewidth,
            alpha=alpha,
            marker=marker,
            subplot_idx=subplot_idx
        )

    def remove_trace(self, trace_id: str) -> bool:
        """
        Remove a trace from the plot.

        Args:
            trace_id: ID returned by add_trace

        Returns:
            True if trace was removed, False if not found
        """
        if trace_id not in self._traces:
            logger.warning(f"Trace not found: {trace_id}")
            return False

        trace_info = self._traces[trace_id]
        line = trace_info['line']
        line.remove()

        del self._traces[trace_id]
        logger.debug(f"Removed trace: {trace_id}")
        return True

    def clear_traces(self, subplot_idx: int = None):
        """
        Clear all traces from a subplot (or all subplots).

        Args:
            subplot_idx: Specific subplot to clear, or None for all
        """
        to_remove = []

        for trace_id, trace_info in self._traces.items():
            if subplot_idx is None or trace_info['subplot_idx'] == subplot_idx:
                trace_info['line'].remove()
                to_remove.append(trace_id)

        for trace_id in to_remove:
            del self._traces[trace_id]

        logger.debug(f"Cleared {len(to_remove)} traces")

    # =========================================================================
    # Reference Lines
    # =========================================================================

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
            orientation: 'h' or 'horizontal' for horizontal, 'v' or 'vertical' for vertical
            value: Position of the line
            color: Line color
            linestyle: Line style
            linewidth: Line width
            alpha: Opacity
            label: Legend label (optional)
            subplot_idx: Subplot index

        Example:
            >>> plot.add_reference_line('v', 0, label="t=0")  # Vertical at x=0
            >>> plot.add_reference_line('h', 100, color='r')  # Horizontal at y=100
        """
        ax = self._get_ax(subplot_idx)

        if orientation.lower() in ('h', 'horizontal'):
            ax.axhline(y=value, color=color, linestyle=linestyle,
                      linewidth=linewidth, alpha=alpha, label=label)
        elif orientation.lower() in ('v', 'vertical'):
            ax.axvline(x=value, color=color, linestyle=linestyle,
                      linewidth=linewidth, alpha=alpha, label=label)
        else:
            logger.warning(f"Unknown orientation: {orientation}")

    def add_horizontal_span(
        self,
        ymin: float,
        ymax: float,
        color: str = 'yellow',
        alpha: float = 0.2,
        subplot_idx: int = None
    ):
        """Add a horizontal span (shaded region)."""
        ax = self._get_ax(subplot_idx)
        ax.axhspan(ymin, ymax, color=color, alpha=alpha)

    def add_vertical_span(
        self,
        xmin: float,
        xmax: float,
        color: str = 'yellow',
        alpha: float = 0.2,
        subplot_idx: int = None
    ):
        """Add a vertical span (shaded region)."""
        ax = self._get_ax(subplot_idx)
        ax.axvspan(xmin, xmax, color=color, alpha=alpha)

    # =========================================================================
    # Multi-Panel Support
    # =========================================================================

    def configure_subplot(self, rows: int, cols: int):
        """
        Configure subplot layout.

        Args:
            rows: Number of rows
            cols: Number of columns

        Note:
            This clears all existing traces and creates new axes.
        """
        self._traces.clear()
        self._axis_config.clear()
        self._create_subplots(rows, cols)
        logger.debug(f"Configured {rows}x{cols} subplot layout")

    def set_active_subplot(self, idx: int):
        """
        Set the active subplot for subsequent operations.

        Args:
            idx: Subplot index (0-based, row-major order)
        """
        if 0 <= idx < len(self._axes):
            self._active_subplot = idx
            logger.debug(f"Active subplot set to {idx}")
        else:
            logger.warning(f"Invalid subplot index: {idx}")

    def get_subplot_count(self) -> int:
        """Get total number of subplots."""
        return len(self._axes)

    # =========================================================================
    # Styling
    # =========================================================================

    def set_title(self, title: str, subplot_idx: int = None):
        """Set the title for a subplot."""
        ax = self._get_ax(subplot_idx)
        ax.set_title(title)

    def set_xlim(self, xmin: float = None, xmax: float = None, subplot_idx: int = None):
        """Set x-axis limits."""
        ax = self._get_ax(subplot_idx)
        ax.set_xlim(xmin, xmax)

    def set_ylim(self, ymin: float = None, ymax: float = None, subplot_idx: int = None):
        """Set y-axis limits."""
        ax = self._get_ax(subplot_idx)
        ax.set_ylim(ymin, ymax)

    def enable_legend(self, visible: bool = True, loc: str = 'best', subplot_idx: int = None):
        """
        Enable or disable the legend.

        Args:
            visible: Whether to show legend
            loc: Legend location ('best', 'upper right', 'lower left', etc.)
            subplot_idx: Subplot index
        """
        ax = self._get_ax(subplot_idx)
        if visible:
            ax.legend(loc=loc)
        else:
            legend = ax.get_legend()
            if legend:
                legend.remove()

    def enable_grid(self, visible: bool = True, alpha: float = None, subplot_idx: int = None):
        """
        Enable or disable grid lines.

        Args:
            visible: Whether to show grid
            alpha: Grid line opacity
            subplot_idx: Subplot index
        """
        ax = self._get_ax(subplot_idx)
        ax.grid(visible, alpha=alpha if alpha is not None else self.DEFAULT_GRID_ALPHA)

    def set_style(self, style: str = 'seaborn-v0_8-whitegrid'):
        """
        Apply a matplotlib style.

        Args:
            style: Style name (e.g., 'seaborn-v0_8-whitegrid', 'ggplot', 'bmh')
        """
        try:
            import matplotlib.pyplot as plt
            plt.style.use(style)
            logger.debug(f"Applied style: {style}")
        except Exception as e:
            logger.warning(f"Could not apply style '{style}': {e}")

    # =========================================================================
    # Canvas Operations
    # =========================================================================

    def refresh(self):
        """
        Refresh the plot canvas.

        Call this after making changes to update the display.
        """
        self.figure.tight_layout()
        self.canvas.draw()
        self.plotUpdated.emit()

    def save_figure(self, filepath: str, dpi: int = 150, **kwargs):
        """
        Save the figure to a file.

        Args:
            filepath: Output file path (extension determines format)
            dpi: Resolution in dots per inch
            **kwargs: Additional arguments passed to Figure.savefig()
        """
        self.figure.savefig(filepath, dpi=dpi, **kwargs)
        logger.info(f"Saved figure to: {filepath}")

    def get_figure(self) -> Figure:
        """Get the matplotlib Figure object for direct manipulation."""
        return self.figure

    def get_axes(self, subplot_idx: int = None) -> Axes:
        """Get the matplotlib Axes object."""
        return self._get_ax(subplot_idx)

    def clear(self):
        """Clear all content from all subplots."""
        self._traces.clear()
        for ax in self._axes:
            ax.clear()
        self._axis_config.clear()

    # =========================================================================
    # Event Handlers
    # =========================================================================

    def _on_mouse_move(self, event):
        """Handle mouse movement over the canvas."""
        if event.inaxes:
            self.cursorMoved.emit(event.xdata, event.ydata)

    def _on_mouse_click(self, event):
        """Handle mouse clicks on the canvas."""
        if event.inaxes and event.button == 1:  # Left click
            # Find closest trace
            closest_trace = None
            min_dist = float('inf')

            for trace_id, trace_info in self._traces.items():
                if trace_info['subplot_idx'] != self._axes.index(event.inaxes):
                    continue

                x_data = trace_info['x_data']
                y_data = trace_info['y_data']

                # Simple distance calculation (could be improved)
                for x, y in zip(x_data, y_data):
                    dist = abs(x - event.xdata) + abs(y - event.ydata)
                    if dist < min_dist:
                        min_dist = dist
                        closest_trace = (trace_info.get('uri', trace_id), x, y)

            if closest_trace:
                self.traceClicked.emit(*closest_trace)


# Backwards compatibility alias
DataSeriesPlotWidget = MatplotlibPlotWidget
