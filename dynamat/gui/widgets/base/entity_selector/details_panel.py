"""
DynaMat Platform - Details Panel Component
Composable details display panel for EntitySelectorWidget
"""

import logging
from typing import Dict, List, Optional, Any

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QGridLayout, QLabel, QFrame, QScrollArea
)
from PyQt6.QtCore import Qt

from .entity_selector_config import EntitySelectorConfig

logger = logging.getLogger(__name__)


class DetailsPanel(QWidget):
    """
    Composable details panel for displaying selected entity properties.

    Shows a grid of property labels and values for the currently
    selected entity. Configurable via details_properties in config.

    Example:
        panel = DetailsPanel(config)
        panel.update_details(entity_data)
        panel.clear()
    """

    def __init__(
        self,
        config: EntitySelectorConfig,
        parent: Optional[QWidget] = None
    ):
        """
        Initialize the details panel.

        Args:
            config: EntitySelectorConfig with details configuration
            parent: Parent widget
        """
        super().__init__(parent)

        self.config = config
        self.logger = logging.getLogger(__name__)

        # Value labels keyed by property URI
        self._value_labels: Dict[str, QLabel] = {}

        self._setup_ui()

    def _setup_ui(self):
        """Setup the details panel UI."""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # Create frame with border
        frame = QFrame()
        frame.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Sunken)

        # Grid layout for property labels and values
        grid = QGridLayout(frame)
        grid.setSpacing(8)
        grid.setContentsMargins(10, 10, 10, 10)

        # Get properties to display
        properties = self.config.get_normalized_details_properties()

        if not properties:
            # Default to display properties if details not specified
            properties = self.config.get_normalized_display_properties()

        if not properties:
            # Show placeholder if no properties configured
            placeholder = QLabel("No details properties configured")
            placeholder.setStyleSheet("color: gray; font-style: italic;")
            grid.addWidget(placeholder, 0, 0)
        else:
            # Create rows for each property
            for row, prop_uri in enumerate(properties):
                # Property label
                label_text = self.config.get_details_label(prop_uri)
                label = QLabel(f"{label_text}:")
                label.setStyleSheet("font-weight: bold;")
                label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                grid.addWidget(label, row, 0)

                # Value label
                value_label = QLabel("--")
                value_label.setWordWrap(True)
                value_label.setTextInteractionFlags(
                    Qt.TextInteractionFlag.TextSelectableByMouse
                )
                grid.addWidget(value_label, row, 1)

                # Store reference
                self._value_labels[prop_uri] = value_label

            # Make value column stretch
            grid.setColumnStretch(1, 1)

        main_layout.addWidget(frame)

    def update_details(self, data: Dict[str, Any]):
        """
        Update the details panel with entity data.

        Args:
            data: Dictionary of property_uri -> value
        """
        for prop_uri, label in self._value_labels.items():
            value = data.get(prop_uri, "")
            display_value = self._format_value(value)
            label.setText(display_value)

        self.logger.debug(f"Updated details panel with {len(data)} properties")

    def clear(self):
        """Clear all values to placeholders."""
        for label in self._value_labels.values():
            label.setText("--")

    def _format_value(self, value: Any) -> str:
        """
        Format a value for display.

        Handles URIs, measurements, and other value types.

        Args:
            value: Value to format

        Returns:
            Formatted string for display
        """
        if value is None or value == "":
            return "--"

        # Handle URI values (extract local name)
        if isinstance(value, str):
            if value.startswith('http://') or value.startswith('https://'):
                if '#' in value:
                    return value.split('#')[-1]
                elif '/' in value:
                    return value.split('/')[-1]
            return str(value)

        # Handle measurement dictionaries
        if isinstance(value, dict):
            if 'value' in value:
                val = value['value']
                unit = value.get('unit', '')
                if unit:
                    # Extract unit symbol from URI if needed
                    if ':' in unit:
                        unit = unit.split(':')[-1]
                    elif '#' in unit:
                        unit = unit.split('#')[-1]
                    return f"{val} {unit}"
                return str(val)

            # Generic dict - show key:value pairs
            return ", ".join(f"{k}: {v}" for k, v in value.items())

        # Handle lists
        if isinstance(value, (list, tuple)):
            return ", ".join(self._format_value(v) for v in value)

        return str(value)

    def set_properties(self, properties: List[str]):
        """
        Dynamically set which properties to display.

        This recreates the UI with new properties. Use sparingly
        as it clears all current values.

        Args:
            properties: List of property URIs to display
        """
        # Update config
        self.config.details_properties = properties

        # Clear existing labels
        self._value_labels.clear()

        # Remove existing layout
        old_layout = self.layout()
        if old_layout:
            # Clear widgets
            while old_layout.count():
                child = old_layout.takeAt(0)
                if child.widget():
                    child.widget().deleteLater()

        # Rebuild UI
        self._setup_ui()
