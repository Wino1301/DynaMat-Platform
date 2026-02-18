"""
DynaMat Platform - Entity Selector Widget
Core embeddable widget for selecting entities using SPARQL queries
"""

import logging
import re
from typing import Dict, List, Optional, Any

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QHeaderView, QLabel, QGroupBox, QSplitter, QAbstractItemView
)
from PyQt6.QtCore import Qt, pyqtSignal

from .entity_selector_config import EntitySelectorConfig, SelectionMode
from .filter_panel import FilterPanel
from .details_panel import DetailsPanel

logger = logging.getLogger(__name__)


class EntitySelectorWidget(QWidget):
    """
    Embeddable widget for selecting ontology entity instances.

    Combines FilterPanel, sortable table view, and DetailsPanel into
    a reusable component that can be embedded in dialogs, wizard pages,
    or other layouts.

    Features:
        - SPARQL-based filtering (efficient server-side filtering)
        - Text search within displayed results
        - Sortable, selectable table
        - Optional details panel
        - Single or multiple selection modes
        - Configurable columns and filters

    Signals:
        selection_changed(dict): Emitted when selection changes (preview data)
        entity_selected(dict): Emitted on double-click (full data)
        filter_changed(dict): Emitted when filter values change
        loading_started(): Emitted when data loading begins
        loading_finished(int): Emitted when loading completes (count of items)
        error_occurred(str): Emitted on errors

    Example:
        config = EntitySelectorConfig(
            class_uri="https://dynamat.utep.edu/ontology#Specimen",
            display_properties=["dyn:hasSpecimenID", "dyn:hasMaterial"],
            filter_properties=["dyn:hasMaterial"],
            show_details_panel=True
        )

        selector = EntitySelectorWidget(config, query_builder=qb)
        selector.entity_selected.connect(self._on_entity_selected)
        layout.addWidget(selector)
    """

    # Signals
    selection_changed = pyqtSignal(dict)
    entity_selected = pyqtSignal(dict)
    filter_changed = pyqtSignal(dict)
    loading_started = pyqtSignal()
    loading_finished = pyqtSignal(int)
    error_occurred = pyqtSignal(str)

    def __init__(
        self,
        config: EntitySelectorConfig,
        query_builder=None,
        ontology_manager=None,
        parent: Optional[QWidget] = None
    ):
        """
        Initialize the entity selector widget.

        Args:
            config: EntitySelectorConfig defining widget behavior
            query_builder: InstanceQueryBuilder for SPARQL queries
            ontology_manager: OntologyManager for loading individuals
            parent: Parent widget
        """
        super().__init__(parent)

        self.config = config
        self.query_builder = query_builder
        self.ontology_manager = ontology_manager
        self.logger = logging.getLogger(__name__)

        # Instance cache from queries
        self._instances_cache: List[Dict[str, Any]] = []

        # UI components
        self._filter_panel: Optional[FilterPanel] = None
        self._table: Optional[QTableWidget] = None
        self._details_panel: Optional[DetailsPanel] = None
        self._status_label: Optional[QLabel] = None

        self._setup_ui()

        # Load filter options if ontology manager available
        if self.ontology_manager and self._filter_panel:
            self._filter_panel.load_filter_options_from_ontology()

        # Load data if query builder available
        if self.query_builder:
            self.refresh()

    def _setup_ui(self):
        """Setup the widget UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)

        # Filter panel
        if self.config.filter_properties or self.config.show_search_box or self.config.show_refresh_button:
            self._filter_panel = FilterPanel(
                self.config,
                ontology_manager=self.ontology_manager,
                parent=self
            )
            self._filter_panel.filters_changed.connect(self._on_filters_changed)
            self._filter_panel.search_changed.connect(self._on_search_changed)
            self._filter_panel.refresh_requested.connect(self.refresh)
            layout.addWidget(self._filter_panel)

        # Main content area - table and optional details
        if self.config.show_details_panel:
            # Use splitter for resizable table/details
            splitter = QSplitter(Qt.Orientation.Vertical)

            # Table
            self._create_table()
            splitter.addWidget(self._table)

            # Details panel
            self._details_panel = DetailsPanel(self.config, parent=self)
            splitter.addWidget(self._details_panel)

            # Set initial sizes (table larger than details)
            splitter.setSizes([300, 100])
            layout.addWidget(splitter)
        else:
            # Just table
            self._create_table()
            layout.addWidget(self._table)

        # Status label
        self._status_label = QLabel("")
        self._status_label.setStyleSheet("color: gray; font-style: italic;")
        layout.addWidget(self._status_label)

    def _create_table(self):
        """Create the entity table."""
        self._table = QTableWidget()

        # Selection behavior based on config
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        if self.config.selection_mode == SelectionMode.MULTIPLE:
            self._table.setSelectionMode(QAbstractItemView.SelectionMode.MultiSelection)
        else:
            self._table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)

        self._table.setAlternatingRowColors(True)
        self._table.setSortingEnabled(True)

        # Setup columns
        display_props = self.config.get_normalized_display_properties()
        self._table.setColumnCount(len(display_props))

        # Column headers
        headers = [self.config.get_property_label(p) for p in display_props]
        self._table.setHorizontalHeaderLabels(headers)

        # Auto-resize columns
        header = self._table.horizontalHeader()
        for i in range(len(display_props)):
            header.setSectionResizeMode(i, QHeaderView.ResizeMode.Stretch)

        # Connect signals
        self._table.itemSelectionChanged.connect(self._on_selection_changed)
        self._table.doubleClicked.connect(self._on_double_click)

    def _on_filters_changed(self, filters: Dict[str, Any]):
        """Handle filter changes - reload with SPARQL filtering."""
        self.filter_changed.emit(filters)
        self.refresh()

    def _on_search_changed(self, text: str):
        """Handle search text changes - filter table rows."""
        self._filter_table_rows(text)

    def _filter_table_rows(self, search_text: str):
        """
        Filter table rows based on search text.

        Args:
            search_text: Text to search for (case-insensitive)
        """
        search_text = search_text.lower()

        for row in range(self._table.rowCount()):
            match = False
            for col in range(self._table.columnCount()):
                item = self._table.item(row, col)
                if item and search_text in item.text().lower():
                    match = True
                    break

            self._table.setRowHidden(row, not match)

    def _on_selection_changed(self):
        """Handle table selection change."""
        selected_rows = self._table.selectionModel().selectedRows()
        if not selected_rows:
            if self._details_panel:
                self._details_panel.clear()
            return

        # Get selected instance data
        if self.config.selection_mode == SelectionMode.SINGLE:
            row = selected_rows[0].row()
            instance = self._get_instance_at_row(row)
            if instance:
                # Load full data for details panel (cached data only has display properties)
                instance_data = instance
                if self._details_panel and self.query_builder:
                    uri = instance.get('uri')
                    if uri:
                        full_data = self._load_full_data_for_details(uri, instance)
                        if full_data:
                            instance_data = full_data
                            self._details_panel.update_details(full_data)
                        else:
                            self._details_panel.update_details(instance)
                elif self._details_panel:
                    self._details_panel.update_details(instance)

                self.selection_changed.emit(instance_data)
        else:
            # Multiple selection - emit list
            instances = [
                self._get_instance_at_row(idx.row())
                for idx in selected_rows
            ]
            instances = [i for i in instances if i]  # Filter None
            if instances:
                self.selection_changed.emit({'instances': instances})

    def _on_double_click(self):
        """Handle double-click - emit entity_selected with full data."""
        selected_rows = self._table.selectionModel().selectedRows()
        if not selected_rows:
            return

        row = selected_rows[0].row()
        instance_metadata = self._get_instance_at_row(row)

        if not instance_metadata:
            return

        # Load full instance data if query builder available
        if self.query_builder:
            instance_uri = instance_metadata.get('uri')
            if instance_uri:
                try:
                    full_data = self.query_builder.load_full_instance_data(instance_uri)
                    if full_data:
                        full_data['uri'] = instance_uri
                        full_data['file_path'] = instance_metadata.get('file_path', '')
                        self.entity_selected.emit(full_data)
                        return
                except Exception as e:
                    self.logger.error(f"Failed to load full data: {e}")

        # Fallback to metadata
        self.entity_selected.emit(instance_metadata)

    def _get_instance_at_row(self, row: int) -> Optional[Dict[str, Any]]:
        """Get instance data stored in table row."""
        if row < 0 or row >= self._table.rowCount():
            return None

        first_item = self._table.item(row, 0)
        if first_item:
            return first_item.data(Qt.ItemDataRole.UserRole)
        return None

    def _load_full_data_for_details(self, uri: str, cached_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Load full instance data for details panel.

        Merges cached data with full data from query builder.

        Args:
            uri: Instance URI
            cached_data: Cached data from table

        Returns:
            Full instance data or None
        """
        if not self.query_builder:
            return None

        try:
            full_data = self.query_builder.load_full_instance_data(uri)
            if full_data:
                # Merge with cached data (preserve file_path, uri)
                merged = {**cached_data, **full_data}
                merged['uri'] = uri
                if 'file_path' in cached_data:
                    merged['file_path'] = cached_data['file_path']
                return merged
        except Exception as e:
            self.logger.debug(f"Could not load full data for {uri}: {e}")

        return None

    def _populate_table(self, instances: List[Dict[str, Any]]):
        """
        Populate table with instance data.

        Args:
            instances: List of instance metadata dicts
        """
        # Block signals during repopulation to prevent spurious
        # itemSelectionChanged events that fire with stale row data.
        self._table.blockSignals(True)
        self._table.clearSelection()
        self._table.setRowCount(len(instances))
        self._table.setSortingEnabled(False)

        display_props = self.config.get_normalized_display_properties()

        for row, instance in enumerate(instances):
            for col, prop_uri in enumerate(display_props):
                value = instance.get(prop_uri, "")
                display_value = self._format_cell_value(value)

                item = QTableWidgetItem(display_value)
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)

                # Store instance data in first column
                if col == 0:
                    item.setData(Qt.ItemDataRole.UserRole, instance)

                self._table.setItem(row, col, item)

        self._table.setSortingEnabled(True)
        self._table.blockSignals(False)

        # Clear details panel since no row is selected after repopulation
        if self._details_panel:
            self._details_panel.clear()

    def _format_cell_value(self, value: Any) -> str:
        """Format a value for table cell display."""
        if value is None or value == "":
            return ""

        if isinstance(value, str):
            # Extract local name from URIs and format for display
            if value.startswith('http://') or value.startswith('https://'):
                # Try to get label from ontology
                label = self._get_label_for_uri(value)
                if label:
                    return label

                # Fall back to extracting and formatting local name
                if '#' in value:
                    local_name = value.split('#')[-1]
                elif '/' in value:
                    local_name = value.split('/')[-1]
                else:
                    local_name = value

                # Format local name for readability (replace underscores with spaces)
                return self._format_local_name(local_name)
            return value

        if isinstance(value, dict) and 'value' in value:
            # Measurement value
            val = value['value']
            unit = value.get('unit', '')
            if unit:
                return f"{val} {unit.split(':')[-1] if ':' in unit else unit}"
            return str(val)

        return str(value)

    def _get_label_for_uri(self, uri: str) -> Optional[str]:
        """
        Get rdfs:label for a URI from ontology.

        Args:
            uri: URI to look up

        Returns:
            Label string or None if not found
        """
        if not self.ontology_manager:
            return None

        try:
            # Query for rdfs:label
            query = f"""
                SELECT ?label WHERE {{
                    <{uri}> rdfs:label ?label .
                }}
                LIMIT 1
            """
            results = self.ontology_manager.sparql_executor.execute_query(query)
            for row in results:
                return str(row['label'])
        except Exception:
            pass

        return None

    def _format_local_name(self, local_name: str) -> str:
        """
        Format a URI local name for human-readable display.

        Handles patterns like:
        - "SS316_A356" -> "SS316 A356"
        - "CylindricalShape" -> "Cylindrical Shape"
        - "LatticeStructure" -> "Lattice Structure"

        Args:
            local_name: Local name from URI

        Returns:
            Formatted display string
        """
        # Replace underscores with spaces
        result = local_name.replace('_', ' ')

        # Insert spaces before capitals in CamelCase (but not for consecutive caps like "SS316")
        # Pattern: lowercase followed by uppercase, or uppercase followed by uppercase+lowercase
        result = re.sub(r'([a-z])([A-Z])', r'\1 \2', result)
        result = re.sub(r'([A-Z]+)([A-Z][a-z])', r'\1 \2', result)

        return result

    # ============================================================================
    # PUBLIC METHODS
    # ============================================================================

    def refresh(self):
        """Reload data from query builder with current filters."""
        if not self.query_builder:
            self._status_label.setText("No query builder configured")
            return

        try:
            self.loading_started.emit()
            self._status_label.setText("Loading...")

            # Get filter values
            filters = {}
            if self._filter_panel:
                filters = self._filter_panel.get_filter_values()

            # Get display properties
            display_props = self.config.get_normalized_display_properties()

            # Query instances - use filter_instances if filters set, otherwise find_all
            if filters:
                self._instances_cache = self.query_builder.filter_instances(
                    self.config.class_uri,
                    filters
                )
            else:
                self._instances_cache = self.query_builder.find_all_instances(
                    self.config.class_uri,
                    display_properties=display_props
                )

            # Populate table
            self._populate_table(self._instances_cache)

            # Apply search filter if active
            if self._filter_panel:
                search_text = self._filter_panel.get_search_text()
                if search_text:
                    self._filter_table_rows(search_text)

            # Update status
            count = len(self._instances_cache)
            self._status_label.setText(f"Found {count} item(s)")
            self.loading_finished.emit(count)

            self.logger.info(f"Loaded {count} instances of {self.config.class_uri}")

        except Exception as e:
            self.logger.error(f"Failed to load instances: {e}")
            self._status_label.setText(f"Error: {e}")
            self.error_occurred.emit(str(e))

    def get_selected_entity(self) -> Optional[Dict[str, Any]]:
        """
        Get the currently selected entity (single selection mode).

        Returns:
            Dictionary with instance data, or None if nothing selected
        """
        selected_rows = self._table.selectionModel().selectedRows()
        if not selected_rows:
            return None

        row = selected_rows[0].row()
        return self._get_instance_at_row(row)

    def get_selected_entities(self) -> List[Dict[str, Any]]:
        """
        Get all selected entities (multiple selection mode).

        Returns:
            List of dictionaries with instance data
        """
        selected_rows = self._table.selectionModel().selectedRows()
        instances = []

        for idx in selected_rows:
            instance = self._get_instance_at_row(idx.row())
            if instance:
                instances.append(instance)

        return instances

    def set_selected_entity(self, uri: str):
        """
        Select an entity by URI.

        Args:
            uri: Instance URI to select
        """
        for row in range(self._table.rowCount()):
            instance = self._get_instance_at_row(row)
            if instance and instance.get('uri') == uri:
                self._table.selectRow(row)
                break

    def clear_selection(self):
        """Clear current selection."""
        self._table.clearSelection()
        if self._details_panel:
            self._details_panel.clear()

    def set_filters(self, filters: Dict[str, Any]):
        """
        Set filter values and reload.

        Args:
            filters: Dictionary of property_uri -> value
        """
        if self._filter_panel:
            self._filter_panel.set_filter_values(filters)
        self.refresh()

    def get_filters(self) -> Dict[str, Any]:
        """Get current filter values."""
        if self._filter_panel:
            return self._filter_panel.get_filter_values()
        return {}

    def clear_filters(self):
        """Clear all filters and reload."""
        if self._filter_panel:
            self._filter_panel.clear_filters()
        self.refresh()

    def set_query_builder(self, query_builder):
        """
        Set or update the query builder.

        Args:
            query_builder: InstanceQueryBuilder instance
        """
        self.query_builder = query_builder
        self.refresh()

    def set_ontology_manager(self, ontology_manager):
        """
        Set or update the ontology manager.

        Args:
            ontology_manager: OntologyManager instance
        """
        self.ontology_manager = ontology_manager
        if self._filter_panel:
            self._filter_panel.set_ontology_manager(ontology_manager)

    def load_full_entity_data(self, uri: str) -> Optional[Dict[str, Any]]:
        """
        Load full entity data by URI.

        Args:
            uri: Instance URI

        Returns:
            Full entity data dict or None
        """
        if not self.query_builder:
            return None

        try:
            data = self.query_builder.load_full_instance_data(uri)
            if data:
                data['uri'] = uri
            return data
        except Exception as e:
            self.logger.error(f"Failed to load entity data: {e}")
            return None
