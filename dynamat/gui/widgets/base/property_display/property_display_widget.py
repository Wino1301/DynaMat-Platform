"""
DynaMat Platform - Property Display Widget
Reusable widget for displaying read-only ontology properties.

Supports both ontology-driven mode (using setIndividual) and legacy mode
(using setData for backward compatibility with constraint system).
"""

import logging
from typing import TYPE_CHECKING, Dict, Any, Optional

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QFormLayout, QGroupBox, QLabel
)
from PyQt6.QtCore import Qt

from .property_display_config import PropertyDisplayConfig

if TYPE_CHECKING:
    from dynamat.ontology import OntologyManager

logger = logging.getLogger(__name__)


class PropertyDisplayWidget(QWidget):
    """
    Reusable widget for displaying read-only derived properties.

    Features:
    - Ontology-driven property display with setIndividual()
    - Automatic label and unit resolution from ontology
    - Nested property support (e.g., bar → material → wave speed)
    - Backward compatible setData() API for constraint system
    - Application stylesheet styling (no hardcoded colors)

    Usage (Ontology-Driven Mode):
        >>> config = PropertyDisplayConfig(
        ...     title="Bar Material Properties",
        ...     properties=["dyn:hasWaveSpeed", "dyn:hasElasticModulus"],
        ...     follow_links={"dyn:hasMaterial": ["dyn:hasWaveSpeed", "dyn:hasElasticModulus"]}
        ... )
        >>> widget = PropertyDisplayWidget(config=config, ontology_manager=manager)
        >>> widget.setIndividual("dyn:IncidentBar_C350")

    Usage (Legacy Mode - Constraint System):
        >>> widget = PropertyDisplayWidget(title="Bar Properties")
        >>> widget.setData({
        ...     'dyn:hasWaveSpeed': {'value': 4953.3, 'label': 'Wave Speed', 'unit': 'unit:M-PER-SEC'}
        ... })
    """

    def __init__(
        self,
        config: Optional[PropertyDisplayConfig] = None,
        ontology_manager: Optional['OntologyManager'] = None,
        title: str = "Properties",
        parent: Optional[QWidget] = None
    ):
        """
        Initialize PropertyDisplayWidget.

        Args:
            config: PropertyDisplayConfig for ontology-driven mode
            ontology_manager: OntologyManager instance for querying properties
            title: Title for the group box (used if config not provided)
            parent: Parent widget
        """
        super().__init__(parent)

        self.config = config
        self.ontology_manager = ontology_manager
        self.title = config.title if config else title
        self.property_widgets: Dict[str, QLabel] = {}  # {property_uri: QLabel}
        self._current_individual: Optional[str] = None

        self._setup_ui()

    def _setup_ui(self):
        """Setup the widget UI structure."""
        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Group box for properties - uses object name for stylesheet targeting
        self.group_box = QGroupBox(self.title)
        self.group_box.setObjectName("propertyDisplayGroupBox")

        # Form layout for label/value pairs
        self.form_layout = QFormLayout()
        self.form_layout.setSpacing(4)
        self.form_layout.setContentsMargins(10, 5, 10, 10)
        self.form_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.form_layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)

        self.group_box.setLayout(self.form_layout)
        main_layout.addWidget(self.group_box)

    # ============================================================================
    # ONTOLOGY-DRIVEN API (New)
    # ============================================================================

    def setIndividual(self, individual_uri: str) -> None:
        """
        Query ontology and display properties for an individual.

        This is the preferred API for ontology-driven property display.
        Requires config and ontology_manager to be set during construction.

        Args:
            individual_uri: URI of the individual to display properties for
        """
        if not self.config:
            logger.warning("setIndividual called without PropertyDisplayConfig - use setData instead")
            return

        if not self.ontology_manager:
            logger.warning("setIndividual called without OntologyManager - use setData instead")
            return

        self._current_individual = individual_uri
        self.clear()

        if not individual_uri:
            return

        try:
            # Query properties from ontology with labels
            property_data = self.ontology_manager.domain_queries.get_individual_properties_with_labels(
                individual_uri,
                self.config.get_normalized_properties(),
                follow_links=self.config.follow_links
            )

            # Display each property
            for prop_uri in self.config.properties:
                normalized_uri = self.config.normalize_uri(prop_uri)
                prop_info = property_data.get(prop_uri) or property_data.get(normalized_uri)

                if prop_info:
                    value = prop_info.get('value')
                    # Use config label override, fall back to ontology label
                    label = self.config.get_label(prop_uri, prop_info.get('label'))
                    unit_symbol = prop_info.get('unit_symbol')

                    self._add_property_row(prop_uri, value, label, unit_symbol)
                elif self.config.show_empty:
                    label = self.config.get_label(prop_uri, self._extract_label_from_uri(prop_uri))
                    self._add_property_row(prop_uri, None, label, None)

            logger.debug(
                f"PropertyDisplayWidget '{self.title}': Displayed {len(self.property_widgets)} "
                f"properties for {individual_uri}"
            )

        except Exception as e:
            logger.error(f"Failed to query properties for {individual_uri}: {e}", exc_info=True)

    def getIndividual(self) -> Optional[str]:
        """
        Get the currently displayed individual URI.

        Returns:
            URI of the currently displayed individual, or None if cleared
        """
        return self._current_individual

    # ============================================================================
    # LEGACY API (Backward Compatible)
    # ============================================================================

    def setData(self, data: Dict[str, Any]) -> None:
        """
        Set property values to display (legacy API for constraint system).

        Args:
            data: Dictionary mapping property URIs to value dicts.
                  Each value dict can contain:
                  - 'value': The value to display (required)
                  - 'unit': Unit URI (optional, for unit values)
                  - 'label': Display label (optional, defaults to property URI fragment)

                  Example:
                  {
                      'dyn:hasWaveSpeed': {
                          'value': 4953.3,
                          'unit': 'unit:M-PER-SEC',
                          'label': 'Wave Speed'
                      }
                  }
        """
        # Clear existing widgets
        self.clear()

        if not data:
            logger.debug(f"PropertyDisplayWidget '{self.title}': No data provided")
            return

        logger.debug(f"PropertyDisplayWidget '{self.title}': Setting data with {len(data)} properties")

        # Create label for each property
        for property_uri, value_dict in data.items():
            if not isinstance(value_dict, dict):
                # Handle simple values (convert to dict format)
                value_dict = {'value': value_dict}

            # Extract components
            value = value_dict.get('value')
            unit = value_dict.get('unit')
            label = value_dict.get('label', self._extract_label_from_uri(property_uri))

            # Extract unit symbol if we have a unit URI
            unit_symbol = self._extract_unit_symbol(unit) if unit else None

            self._add_property_row(property_uri, value, label, unit_symbol)

        logger.debug(f"PropertyDisplayWidget '{self.title}': Displayed {len(self.property_widgets)} properties")

    def getData(self) -> Dict[str, Any]:
        """
        Get current property values.

        Returns:
            Dictionary mapping property URIs to displayed values.
            Maintains widget pattern consistency.
        """
        data = {}
        for property_uri, value_label in self.property_widgets.items():
            # Return the raw text (formatted value)
            data[property_uri] = value_label.text()
        return data

    # ============================================================================
    # COMMON METHODS
    # ============================================================================

    def clear(self) -> None:
        """Clear all property displays and reset to empty state."""
        # Remove all rows from form layout
        while self.form_layout.rowCount() > 0:
            self.form_layout.removeRow(0)

        # Clear widget references
        self.property_widgets.clear()
        self._current_individual = None

        logger.debug(f"PropertyDisplayWidget '{self.title}': Cleared all properties")

    def _add_property_row(
        self,
        property_uri: str,
        value: Any,
        label: str,
        unit_symbol: Optional[str]
    ) -> None:
        """
        Add a property row to the form layout.

        Args:
            property_uri: URI of the property
            value: Value to display
            label: Display label
            unit_symbol: Optional unit symbol (e.g., 'm/s')
        """
        # Format value
        formatted_value = self._format_value(value, unit_symbol)

        # Create label widgets with object names for stylesheet targeting
        label_widget = QLabel(f"{label}:")
        label_widget.setObjectName("propertyLabel")

        value_label = QLabel(formatted_value)
        value_label.setObjectName("propertyValue")
        value_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        # Add to form layout
        self.form_layout.addRow(label_widget, value_label)

        # Store widget reference
        self.property_widgets[property_uri] = value_label

    def _format_value(self, value: Any, unit_symbol: Optional[str] = None) -> str:
        """
        Format value for display.

        Args:
            value: The value to format
            unit_symbol: Optional unit symbol

        Returns:
            Formatted string representation
        """
        if value is None:
            return "N/A"

        # Handle numeric values with units
        if isinstance(value, (int, float)):
            if unit_symbol:
                return f"{value:.3f} {unit_symbol}"
            else:
                return f"{value:.3f}"

        # Handle string values
        if isinstance(value, str):
            # Check if it's a URI
            if '#' in value or '/' in value:
                return self._extract_label_from_uri(value)
            return value

        # Fallback to string representation
        return str(value)

    def _extract_unit_symbol(self, unit_uri: str) -> str:
        """
        Extract unit symbol from unit URI.

        Args:
            unit_uri: Full unit URI (e.g., 'unit:M-PER-SEC')

        Returns:
            Unit symbol (e.g., 'm/s')
        """
        # Common unit mappings
        unit_symbols = {
            'M-PER-SEC': 'm/s',
            'GigaPA': 'GPa',
            'MegaPA': 'MPa',
            'KiloGM-PER-M3': 'kg/m³',
            'GM-PER-CentiM3': 'g/cm³',
            'MilliM': 'mm',
            'M': 'm',
            'SEC': 's',
            'PER-SEC': '1/s',
            'OHM': 'Ω',
            'V': 'V',
        }

        # Extract local name
        if ':' in unit_uri:
            local_name = unit_uri.split(':')[-1]
        elif '/' in unit_uri:
            local_name = unit_uri.split('/')[-1]
        elif '#' in unit_uri:
            local_name = unit_uri.split('#')[-1]
        else:
            local_name = unit_uri

        return unit_symbols.get(local_name, local_name)

    def _extract_label_from_uri(self, uri: str) -> str:
        """
        Extract human-readable label from property URI.

        Args:
            uri: Property URI (e.g., 'dyn:hasWaveSpeed')

        Returns:
            Label (e.g., 'Wave Speed')
        """
        # Extract local name
        if ':' in uri:
            local_name = uri.split(':')[-1]
        elif '/' in uri:
            local_name = uri.split('/')[-1]
        elif '#' in uri:
            local_name = uri.split('#')[-1]
        else:
            local_name = uri

        # Convert camelCase/PascalCase to space-separated
        # Remove 'has' prefix if present
        if local_name.startswith('has'):
            local_name = local_name[3:]

        # Insert spaces before capital letters
        result = []
        for i, char in enumerate(local_name):
            if i > 0 and char.isupper():
                result.append(' ')
            result.append(char)

        return ''.join(result).strip()
