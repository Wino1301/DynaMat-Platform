"""
DynaMat Platform - Plotly Plot Widget
Plotly-based interactive plotting widget with ontology-driven axis labels.
"""

import logging
import json
from typing import Dict, List, Optional, Any, Union, Tuple
import uuid
import tempfile
from pathlib import Path

import numpy as np

from PyQt6.QtWidgets import QVBoxLayout, QSizePolicy
from PyQt6.QtCore import QUrl

from rdflib import URIRef

from .base_plot_widget import BasePlotWidget
from .series_metadata_resolver import SeriesMetadataResolver

logger = logging.getLogger(__name__)

# Check for Plotly availability
try:
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
    PLOTLY_AVAILABLE = True
except ImportError:
    PLOTLY_AVAILABLE = False
    logger.warning("Plotly not installed. PlotlyPlotWidget will not be available.")

# Check for PyQtWebEngine availability
try:
    from PyQt6.QtWebEngineWidgets import QWebEngineView
    from PyQt6.QtWebChannel import QWebChannel
    WEBENGINE_AVAILABLE = True
except ImportError:
    WEBENGINE_AVAILABLE = False
    logger.warning("PyQtWebEngine not installed. PlotlyPlotWidget will not be available.")


class PlotlyPlotWidget(BasePlotWidget):
    """
    Plotly-based interactive plotting widget with ontology-driven axis labels.

    Embeds a Plotly chart in QWebEngineView and uses ontology queries to determine
    axis labels from SeriesType URIs. Supports single and multi-panel layouts.

    Built-in Plotly interactivity (no extra code needed):
        - Zoom: Drag to zoom, double-click to reset
        - Pan: Shift+drag to pan
        - Hover: Automatic tooltips with data values
        - Box/Lasso Select: Built-in selection tools
        - Export: Download as PNG button built-in

    Signals:
        traceClicked(str, float, float): Emitted when a trace is clicked (uri, x, y)
        rangeSelected(float, float): Emitted when a range is selected (x0, x1)
        plotUpdated(): Emitted after plot is refreshed
        cursorMoved(float, float): Emitted when cursor moves over plot (x, y)

    Widget Structure:
        PlotlyPlotWidget(QWidget)
        +-- QVBoxLayout
            +-- QWebEngineView
                +-- Plotly HTML/JS

    Example:
        >>> plot = PlotlyPlotWidget(ontology_manager, qudt_manager)
        >>> plot.set_axis_series('dyn:Strain', 'dyn:Stress')
        >>> plot.add_trace(strain_data, stress_data, label="1-wave", color="blue")
        >>> plot.enable_legend()
        >>> plot.refresh()

    Requirements:
        - plotly>=5.0.0
        - PyQtWebEngine>=6.6.0
        - kaleido>=0.2.0 (optional, for static image export)
    """

    # Line style mapping from matplotlib to Plotly
    LINESTYLE_MAP = {
        '-': 'solid',
        '--': 'dash',
        '-.': 'dashdot',
        ':': 'dot',
        'solid': 'solid',
        'dash': 'dash',
        'dashdot': 'dashdot',
        'dot': 'dot',
    }

    def __init__(
        self,
        ontology_manager,
        qudt_manager,
        figsize: Tuple[float, float] = None,
        show_toolbar: bool = True,
        parent=None
    ):
        """
        Initialize the Plotly plot widget.

        Args:
            ontology_manager: OntologyManager for SeriesType queries
            qudt_manager: QUDTManager for unit symbol resolution
            figsize: Figure size tuple (width, height) in inches
            show_toolbar: Whether to show the Plotly modebar (toolbar)
            parent: Parent widget

        Raises:
            ImportError: If Plotly or PyQtWebEngine is not installed
        """
        if not PLOTLY_AVAILABLE:
            raise ImportError("Plotly is required for PlotlyPlotWidget. Install with: pip install plotly")
        if not WEBENGINE_AVAILABLE:
            raise ImportError("PyQtWebEngine is required for PlotlyPlotWidget. Install with: pip install PyQtWebEngine")

        super().__init__(ontology_manager, qudt_manager, figsize, show_toolbar, parent)

        # Create metadata resolver for axis labels
        self.resolver = SeriesMetadataResolver(ontology_manager, qudt_manager)

        # Plotly figure - will be recreated on configure_subplot
        self.fig: go.Figure = None
        self._subplot_specs: List[Dict] = []

        # Setup UI
        self._setup_ui(show_toolbar)

        logger.debug("PlotlyPlotWidget initialized")

    def _setup_ui(self, show_toolbar: bool):
        """Setup the widget UI with QWebEngineView for Plotly."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Create web view for Plotly
        self.web_view = QWebEngineView()
        self.web_view.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout.addWidget(self.web_view)

        # Create initial figure
        self._create_figure(1, 1)

        # Store toolbar preference
        self._show_toolbar = show_toolbar

    def _create_figure(self, rows: int, cols: int):
        """Create Plotly figure with specified subplot layout."""
        if rows == 1 and cols == 1:
            self.fig = go.Figure()
        else:
            self.fig = make_subplots(rows=rows, cols=cols)

        self._subplot_rows = rows
        self._subplot_cols = cols
        self._active_subplot = 0
        self._subplot_specs = [{'row': (i // cols) + 1, 'col': (i % cols) + 1}
                               for i in range(rows * cols)]

        # Apply default layout
        width = int(self.figsize[0] * self.DEFAULT_DPI)
        height = int(self.figsize[1] * self.DEFAULT_DPI)

        self.fig.update_layout(
            width=width,
            height=height,
            template='plotly_white',
            showlegend=False,
            margin=dict(l=60, r=40, t=40, b=60),
        )

    def _get_subplot_kwargs(self, subplot_idx: Optional[int] = None) -> Dict[str, int]:
        """Get row/col kwargs for subplot operations."""
        idx = subplot_idx if subplot_idx is not None else self._active_subplot
        if idx >= len(self._subplot_specs):
            idx = 0

        spec = self._subplot_specs[idx]

        # For single plot, don't pass row/col
        if self._subplot_rows == 1 and self._subplot_cols == 1:
            return {}

        return {'row': spec['row'], 'col': spec['col']}

    def _convert_linestyle(self, linestyle: str) -> str:
        """Convert matplotlib linestyle to Plotly dash style."""
        return self.LINESTYLE_MAP.get(linestyle, 'solid')

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

        Args:
            x_series_type: SeriesType URI for x-axis (e.g., 'dyn:Strain')
            y_series_type: SeriesType URI for y-axis (e.g., 'dyn:Stress')
            x_unit: Override x-axis unit URI (optional)
            y_unit: Override y-axis unit URI (optional)
            subplot_idx: Subplot index, or None for active subplot
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

        # Apply to figure
        subplot_kwargs = self._get_subplot_kwargs(subplot_idx)

        if subplot_kwargs:
            # Multi-subplot: use axis selector
            axis_suffix = "" if idx == 0 else str(idx + 1)
            self.fig.update_layout(**{
                f'xaxis{axis_suffix}': dict(title=x_label),
                f'yaxis{axis_suffix}': dict(title=y_label),
            })
        else:
            self.fig.update_xaxes(title_text=x_label)
            self.fig.update_yaxes(title_text=y_label)

        logger.debug(f"Set axis labels: x='{x_label}', y='{y_label}' for subplot {idx}")

    def set_xlabel(self, label: str, subplot_idx: int = None):
        """Set x-axis label directly."""
        subplot_kwargs = self._get_subplot_kwargs(subplot_idx)
        self.fig.update_xaxes(title_text=label, **subplot_kwargs)

    def set_ylabel(self, label: str, subplot_idx: int = None):
        """Set y-axis label directly."""
        subplot_kwargs = self._get_subplot_kwargs(subplot_idx)
        self.fig.update_yaxes(title_text=label, **subplot_kwargs)

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
            color: Line color
            linestyle: Line style ('-', '--', '-.', ':')
            linewidth: Line width in points
            alpha: Opacity (0.0 to 1.0)
            marker: Marker style (None, 'o', 's', etc.)
            subplot_idx: Subplot index, or None for active subplot

        Returns:
            Trace ID string for later reference
        """
        lw = linewidth if linewidth is not None else self.DEFAULT_LINE_WIDTH

        # Build line style
        line_kwargs = {
            'width': lw,
            'dash': self._convert_linestyle(linestyle),
        }
        if color:
            line_kwargs['color'] = color

        # Build marker style (if requested)
        marker_kwargs = None
        mode = 'lines'
        if marker:
            mode = 'lines+markers'
            marker_kwargs = {'symbol': self._convert_marker(marker)}

        # Generate trace ID
        trace_id = str(uuid.uuid4())[:8]

        # Create scatter trace
        scatter_kwargs = {
            'x': x_data.tolist() if isinstance(x_data, np.ndarray) else x_data,
            'y': y_data.tolist() if isinstance(y_data, np.ndarray) else y_data,
            'mode': mode,
            'line': line_kwargs,
            'opacity': alpha,
            'name': label or '',
            'showlegend': bool(label),
            'customdata': [trace_id],  # Store trace ID for click handling
        }

        if marker_kwargs:
            scatter_kwargs['marker'] = marker_kwargs

        trace = go.Scatter(**scatter_kwargs)

        # Add to subplot
        subplot_kwargs = self._get_subplot_kwargs(subplot_idx)
        self.fig.add_trace(trace, **subplot_kwargs)

        # Store trace info
        self._traces[trace_id] = {
            'trace_index': len(self.fig.data) - 1,
            'uri': uri,
            'label': label,
            'subplot_idx': subplot_idx if subplot_idx is not None else self._active_subplot,
            'x_data': x_data,
            'y_data': y_data
        }

        logger.debug(f"Added trace {trace_id}: {label or 'unlabeled'}")
        return trace_id

    def _convert_marker(self, marker: str) -> str:
        """Convert matplotlib marker to Plotly symbol."""
        marker_map = {
            'o': 'circle',
            's': 'square',
            '^': 'triangle-up',
            'v': 'triangle-down',
            'd': 'diamond',
            'x': 'x',
            '+': 'cross',
            '*': 'star',
            '.': 'circle',
        }
        return marker_map.get(marker, 'circle')

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
        trace_index = trace_info['trace_index']

        # Remove from figure data
        data_list = list(self.fig.data)
        if 0 <= trace_index < len(data_list):
            data_list.pop(trace_index)
            self.fig.data = data_list

            # Update indices for remaining traces
            for tid, tinfo in self._traces.items():
                if tinfo['trace_index'] > trace_index:
                    tinfo['trace_index'] -= 1

        del self._traces[trace_id]
        logger.debug(f"Removed trace: {trace_id}")
        return True

    def clear_traces(self, subplot_idx: int = None):
        """
        Clear all traces from a subplot (or all subplots).

        Args:
            subplot_idx: Specific subplot to clear, or None for all
        """
        if subplot_idx is None:
            # Clear all traces
            self.fig.data = []
            self._traces.clear()
        else:
            # Clear only traces from specific subplot
            to_remove = [tid for tid, tinfo in self._traces.items()
                        if tinfo['subplot_idx'] == subplot_idx]
            for tid in to_remove:
                self.remove_trace(tid)

        logger.debug(f"Cleared traces from subplot {subplot_idx}")

    # =========================================================================
    # Reference Lines
    # =========================================================================

    def add_reference_line(
        self,
        orientation: str,
        value: float,
        color: str = 'black',
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
        subplot_kwargs = self._get_subplot_kwargs(subplot_idx)

        # Determine axis reference
        if subplot_kwargs:
            row = subplot_kwargs['row']
            col = subplot_kwargs['col']
            # Calculate axis index (1-indexed for first, 2+ for subsequent)
            axis_idx = (row - 1) * self._subplot_cols + col
            xref = f'x{axis_idx}' if axis_idx > 1 else 'x'
            yref = f'y{axis_idx}' if axis_idx > 1 else 'y'
        else:
            xref = 'x'
            yref = 'y'

        line_dict = dict(
            color=color,
            width=linewidth,
            dash=self._convert_linestyle(linestyle),
        )

        if orientation.lower() in ('h', 'horizontal'):
            self.fig.add_hline(
                y=value,
                line=line_dict,
                opacity=alpha,
                annotation_text=label if label else None,
                row=subplot_kwargs.get('row'),
                col=subplot_kwargs.get('col'),
            )
        elif orientation.lower() in ('v', 'vertical'):
            self.fig.add_vline(
                x=value,
                line=line_dict,
                opacity=alpha,
                annotation_text=label if label else None,
                row=subplot_kwargs.get('row'),
                col=subplot_kwargs.get('col'),
            )
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
        subplot_kwargs = self._get_subplot_kwargs(subplot_idx)
        self.fig.add_hrect(
            y0=ymin,
            y1=ymax,
            fillcolor=color,
            opacity=alpha,
            line_width=0,
            row=subplot_kwargs.get('row'),
            col=subplot_kwargs.get('col'),
        )

    def add_vertical_span(
        self,
        xmin: float,
        xmax: float,
        color: str = 'yellow',
        alpha: float = 0.2,
        subplot_idx: int = None
    ):
        """Add a vertical span (shaded region)."""
        subplot_kwargs = self._get_subplot_kwargs(subplot_idx)
        self.fig.add_vrect(
            x0=xmin,
            x1=xmax,
            fillcolor=color,
            opacity=alpha,
            line_width=0,
            row=subplot_kwargs.get('row'),
            col=subplot_kwargs.get('col'),
        )

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
            This clears all existing traces and creates new figure.
        """
        self._traces.clear()
        self._axis_config.clear()
        self._create_figure(rows, cols)
        logger.debug(f"Configured {rows}x{cols} subplot layout")

    def set_active_subplot(self, idx: int):
        """
        Set the active subplot for subsequent operations.

        Args:
            idx: Subplot index (0-based, row-major order)
        """
        total = self._subplot_rows * self._subplot_cols
        if 0 <= idx < total:
            self._active_subplot = idx
            logger.debug(f"Active subplot set to {idx}")
        else:
            logger.warning(f"Invalid subplot index: {idx}")

    # =========================================================================
    # Styling
    # =========================================================================

    def set_title(self, title: str, subplot_idx: int = None):
        """Set the title for a subplot or main figure."""
        if subplot_idx is None and self._subplot_rows == 1 and self._subplot_cols == 1:
            self.fig.update_layout(title_text=title)
        else:
            # For subplots, update annotation (Plotly doesn't have per-subplot titles by default)
            idx = subplot_idx if subplot_idx is not None else self._active_subplot
            subplot_kwargs = self._get_subplot_kwargs(idx)
            if subplot_kwargs:
                # Add annotation as subplot title
                row, col = subplot_kwargs['row'], subplot_kwargs['col']
                self.fig.add_annotation(
                    text=title,
                    xref=f'x{idx + 1} domain' if idx > 0 else 'x domain',
                    yref=f'y{idx + 1} domain' if idx > 0 else 'y domain',
                    x=0.5, y=1.1,
                    showarrow=False,
                    font=dict(size=14),
                )
            else:
                self.fig.update_layout(title_text=title)

    def set_xlim(self, xmin: float = None, xmax: float = None, subplot_idx: int = None):
        """Set x-axis limits."""
        subplot_kwargs = self._get_subplot_kwargs(subplot_idx)
        range_val = [xmin, xmax] if xmin is not None or xmax is not None else None
        self.fig.update_xaxes(range=range_val, **subplot_kwargs)

    def set_ylim(self, ymin: float = None, ymax: float = None, subplot_idx: int = None):
        """Set y-axis limits."""
        subplot_kwargs = self._get_subplot_kwargs(subplot_idx)
        range_val = [ymin, ymax] if ymin is not None or ymax is not None else None
        self.fig.update_yaxes(range=range_val, **subplot_kwargs)

    def enable_legend(self, visible: bool = True, loc: str = 'best', subplot_idx: int = None):
        """
        Enable or disable the legend.

        Args:
            visible: Whether to show legend
            loc: Legend location (mapped from matplotlib names)
            subplot_idx: Subplot index (ignored for Plotly, legend is figure-wide)
        """
        # Map matplotlib locations to Plotly
        loc_map = {
            'best': dict(x=1.02, y=1, xanchor='left'),
            'upper right': dict(x=1, y=1, xanchor='right'),
            'upper left': dict(x=0, y=1, xanchor='left'),
            'lower right': dict(x=1, y=0, xanchor='right'),
            'lower left': dict(x=0, y=0, xanchor='left'),
            'right': dict(x=1.02, y=0.5, xanchor='left'),
            'center left': dict(x=0, y=0.5, xanchor='left'),
            'center right': dict(x=1, y=0.5, xanchor='right'),
        }

        legend_kwargs = loc_map.get(loc, loc_map['best'])
        self.fig.update_layout(showlegend=visible, legend=legend_kwargs)

    def enable_grid(self, visible: bool = True, alpha: float = None, subplot_idx: int = None):
        """
        Enable or disable grid lines.

        Args:
            visible: Whether to show grid
            alpha: Grid line opacity
            subplot_idx: Subplot index
        """
        subplot_kwargs = self._get_subplot_kwargs(subplot_idx)
        grid_kwargs = {'showgrid': visible}
        if alpha is not None:
            grid_kwargs['gridcolor'] = f'rgba(128, 128, 128, {alpha})'

        self.fig.update_xaxes(**grid_kwargs, **subplot_kwargs)
        self.fig.update_yaxes(**grid_kwargs, **subplot_kwargs)

    def set_template(self, template: str = 'plotly_white'):
        """
        Apply a Plotly template (similar to matplotlib style).

        Args:
            template: Template name ('plotly', 'plotly_white', 'plotly_dark',
                     'ggplot2', 'seaborn', 'simple_white', etc.)
        """
        self.fig.update_layout(template=template)
        logger.debug(f"Applied template: {template}")

    # =========================================================================
    # Canvas Operations
    # =========================================================================

    def refresh(self):
        """
        Refresh the plot by updating the WebEngineView.

        Renders the Plotly figure to HTML and loads it in the web view.
        """
        # Generate HTML
        config = {
            'displayModeBar': self._show_toolbar,
            'responsive': True,
            'scrollZoom': True,
        }

        html = self.fig.to_html(
            include_plotlyjs='cdn',
            config=config,
            full_html=True,
        )

        # Load in web view
        self.web_view.setHtml(html)
        self.plotUpdated.emit()

    def save_figure(self, filepath: str, dpi: int = 150, **kwargs):
        """
        Save the figure to a file.

        Args:
            filepath: Output file path (supports .png, .jpg, .svg, .pdf, .html)
            dpi: Resolution in dots per inch (for raster formats)
            **kwargs: Additional arguments passed to Plotly write_image/write_html

        Note:
            For raster formats (png, jpg), requires kaleido package.
        """
        filepath = Path(filepath)
        ext = filepath.suffix.lower()

        if ext == '.html':
            self.fig.write_html(str(filepath), **kwargs)
        else:
            # Calculate size from DPI
            scale = dpi / self.DEFAULT_DPI
            try:
                self.fig.write_image(str(filepath), scale=scale, **kwargs)
            except Exception as e:
                logger.error(f"Failed to save image (kaleido may not be installed): {e}")
                # Fallback to HTML
                html_path = filepath.with_suffix('.html')
                self.fig.write_html(str(html_path))
                logger.info(f"Saved as HTML instead: {html_path}")
                return

        logger.info(f"Saved figure to: {filepath}")

    def get_figure(self) -> 'go.Figure':
        """Get the Plotly Figure object for direct manipulation."""
        return self.fig

    def clear(self):
        """Clear all content from all subplots."""
        self._traces.clear()
        self._axis_config.clear()
        self._create_figure(self._subplot_rows, self._subplot_cols)
