"""
DynaMat Platform - Plotting Configuration
Dataclass for plot styling configuration with sensible defaults.
"""

from dataclasses import dataclass, field
from typing import Optional, Tuple, List


@dataclass
class PlottingConfig:
    """
    Configuration for plot styling and layout.

    Controls figure size, line styles, font sizes, grid appearance,
    legend formatting, and backend-specific settings.

    Example:
        >>> config = PlottingConfig(figsize=(12, 8), title_font_size=18.0)
        >>> plot = create_plot_widget(ontology_manager, qudt_manager, config=config)

        >>> # Publication-quality preset
        >>> pub_config = PlottingConfig(
        ...     figsize=(8, 6), dpi=300,
        ...     title_font_size=18.0, axis_label_font_size=16.0,
        ...     tick_label_font_size=14.0, legend_font_size=14.0,
        ...     line_width=2.0, grid_visible=True, grid_alpha=0.2,
        ... )
    """

    # Figure dimensions
    figsize: Tuple[float, float] = (10, 6)
    dpi: int = 100

    # Line styling
    line_width: float = 1.5
    line_style: str = '-'

    # Grid styling
    grid_visible: bool = True
    grid_alpha: float = 0.3
    grid_line_width: float = 0.5

    # Font sizes
    title_font_size: float = 16.0
    axis_label_font_size: float = 14.0
    tick_label_font_size: float = 12.0
    legend_font_size: float = 12.0
    legend_title_font_size: float = 13.0

    # Legend
    legend_visible: bool = True
    legend_location: str = 'best'
    legend_title: Optional[str] = None

    # Backend-specific
    matplotlib_style: str = 'default'
    plotly_template: str = 'plotly_white'

    # Color cycle (None = use backend default)
    color_cycle: Optional[List[str]] = None
