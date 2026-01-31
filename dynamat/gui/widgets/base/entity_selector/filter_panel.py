"""
DynaMat Platform - Filter Panel Component
Composable filter dropdown panel for EntitySelectorWidget
"""

import logging
from typing import Dict, List, Optional, Any, Tuple

from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel, QComboBox,
    QLineEdit, QPushButton, QFrame
)
from PyQt6.QtCore import pyqtSignal

from .entity_selector_config import EntitySelectorConfig

logger = logging.getLogger(__name__)


class FilterPanel(QWidget):
    """
    Composable filter panel with dropdowns and search box.

    Dynamically creates filter dropdowns based on configuration.
    Populates dropdown options from ontology individuals.

    Signals:
        filters_changed(dict): Emitted when any filter value changes.
            Dict contains property_uri -> selected_value mappings.
        search_changed(str): Emitted when search text changes.
        refresh_requested(): Emitted when refresh button is clicked.

    Example:
        panel = FilterPanel(config, ontology_manager)
        panel.filters_changed.connect(self._on_filters_changed)

        # Get current filter values
        filters = panel.get_filter_values()

        # Set filter values programmatically
        panel.set_filter_values({"dyn:hasMaterial": "dyn:SS316"})
    """

    filters_changed = pyqtSignal(dict)
    search_changed = pyqtSignal(str)
    refresh_requested = pyqtSignal()

    def __init__(
        self,
        config: EntitySelectorConfig,
        ontology_manager=None,
        parent: Optional[QWidget] = None
    ):
        """
        Initialize the filter panel.

        Args:
            config: EntitySelectorConfig with filter configuration
            ontology_manager: OntologyManager for loading individuals
            parent: Parent widget
        """
        super().__init__(parent)

        self.config = config
        self.ontology_manager = ontology_manager
        self.logger = logging.getLogger(__name__)

        # Filter dropdowns keyed by property URI
        self._filter_combos: Dict[str, QComboBox] = {}
        self._search_box: Optional[QLineEdit] = None
        self._refresh_button: Optional[QPushButton] = None

        self._setup_ui()

    def _setup_ui(self):
        """Setup the filter panel UI."""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        # Create filter dropdowns
        if self.config.filter_properties:
            for prop_uri in self.config.filter_properties:
                self._create_filter_dropdown(layout, prop_uri)

        # Search box
        if self.config.show_search_box:
            layout.addWidget(QLabel("Search:"))
            self._search_box = QLineEdit()
            self._search_box.setPlaceholderText("Filter by text...")
            self._search_box.setMinimumWidth(150)
            self._search_box.textChanged.connect(self._on_search_changed)
            layout.addWidget(self._search_box)

        layout.addStretch()

        # Refresh button
        if self.config.show_refresh_button:
            self._refresh_button = QPushButton("Refresh")
            self._refresh_button.clicked.connect(self.refresh_requested.emit)
            layout.addWidget(self._refresh_button)

    def _create_filter_dropdown(self, layout: QHBoxLayout, prop_uri: str):
        """
        Create a filter dropdown for a property.

        Args:
            layout: Parent layout to add widgets to
            prop_uri: Property URI for the filter
        """
        # Get label
        normalized_uri = self.config.normalize_property_uri(prop_uri)
        label = self.config.get_filter_label(prop_uri)

        # Create label widget
        label_widget = QLabel(f"{label}:")
        layout.addWidget(label_widget)

        # Create combo box
        combo = QComboBox()
        combo.setMinimumWidth(150)

        # Add "All" option
        combo.addItem(f"All {label}s", None)

        # Store reference
        self._filter_combos[normalized_uri] = combo

        # Connect signal
        combo.currentIndexChanged.connect(
            lambda idx, uri=normalized_uri: self._on_filter_changed(uri)
        )

        layout.addWidget(combo)

    def populate_filter_options(self, prop_uri: str, options: List[Tuple[str, str]]):
        """
        Populate a filter dropdown with options.

        Args:
            prop_uri: Property URI of the filter
            options: List of (value_uri, display_label) tuples
        """
        normalized_uri = self.config.normalize_property_uri(prop_uri)

        if normalized_uri not in self._filter_combos:
            self.logger.warning(f"No filter combo for property: {prop_uri}")
            return

        combo = self._filter_combos[normalized_uri]

        # Store current value to restore after repopulating
        current_data = combo.currentData()

        # Block signals during update
        combo.blockSignals(True)

        # Clear existing items except "All" option
        while combo.count() > 1:
            combo.removeItem(1)

        # Add options
        for value_uri, display_label in options:
            combo.addItem(display_label, value_uri)

        # Restore previous selection if still valid
        if current_data:
            idx = combo.findData(current_data)
            if idx >= 0:
                combo.setCurrentIndex(idx)

        combo.blockSignals(False)

        self.logger.debug(f"Populated filter {prop_uri} with {len(options)} options")

    def load_filter_options_from_ontology(self):
        """
        Load filter options from ontology individuals.

        Requires ontology_manager to be set.
        """
        if not self.ontology_manager:
            self.logger.warning("No ontology manager available for loading filter options")
            return

        for prop_uri in (self.config.filter_properties or []):
            normalized_uri = self.config.normalize_property_uri(prop_uri)

            # Determine the class of individuals to load
            # For object properties, get the range class
            # For now, we infer from the property name (e.g., hasMaterial -> Material)
            range_class = self._infer_range_class(normalized_uri)

            if range_class:
                try:
                    individuals = self.ontology_manager.get_available_individuals(range_class)

                    # Convert to (uri, label) tuples
                    options = []
                    for ind_uri, ind_label in individuals:
                        # Use label if available, otherwise extract from URI
                        if ind_label:
                            display = ind_label
                        elif '#' in ind_uri:
                            display = ind_uri.split('#')[-1]
                        else:
                            display = ind_uri.split('/')[-1]

                        options.append((ind_uri, display))

                    self.populate_filter_options(prop_uri, options)

                except Exception as e:
                    self.logger.error(f"Failed to load individuals for {prop_uri}: {e}")

    def _infer_range_class(self, prop_uri: str) -> Optional[str]:
        """
        Infer the range class from a property URI.

        For properties like "hasX", infers class "X".

        Args:
            prop_uri: Property URI

        Returns:
            Inferred class URI or None
        """
        # Extract property name
        if '#' in prop_uri:
            prop_name = prop_uri.split('#')[-1]
            namespace = prop_uri.rsplit('#', 1)[0] + '#'
        else:
            return None

        # Common patterns: hasX -> X
        if prop_name.startswith('has'):
            class_name = prop_name[3:]
            return f"{namespace}{class_name}"

        return None

    def _on_filter_changed(self, prop_uri: str):
        """Handle filter dropdown value change."""
        self.filters_changed.emit(self.get_filter_values())

    def _on_search_changed(self, text: str):
        """Handle search text change."""
        self.search_changed.emit(text)

    # ============================================================================
    # PUBLIC METHODS
    # ============================================================================

    def get_filter_values(self) -> Dict[str, Any]:
        """
        Get current filter values.

        Returns:
            Dictionary of property_uri -> selected_value.
            Values are None if "All" is selected.
        """
        filters = {}
        for prop_uri, combo in self._filter_combos.items():
            value = combo.currentData()
            if value is not None:
                filters[prop_uri] = value
        return filters

    def set_filter_values(self, filters: Dict[str, Any]):
        """
        Set filter values programmatically.

        Args:
            filters: Dictionary of property_uri -> value
        """
        for prop_uri, value in filters.items():
            normalized_uri = self.config.normalize_property_uri(prop_uri)

            if normalized_uri in self._filter_combos:
                combo = self._filter_combos[normalized_uri]
                idx = combo.findData(value)
                if idx >= 0:
                    combo.setCurrentIndex(idx)

    def clear_filters(self):
        """Reset all filters to "All" (index 0)."""
        for combo in self._filter_combos.values():
            combo.setCurrentIndex(0)

        if self._search_box:
            self._search_box.clear()

    def get_search_text(self) -> str:
        """Get current search text."""
        if self._search_box:
            return self._search_box.text()
        return ""

    def set_search_text(self, text: str):
        """Set search text."""
        if self._search_box:
            self._search_box.setText(text)

    def set_ontology_manager(self, ontology_manager):
        """
        Set or update the ontology manager.

        Args:
            ontology_manager: OntologyManager instance
        """
        self.ontology_manager = ontology_manager
        self.load_filter_options_from_ontology()
