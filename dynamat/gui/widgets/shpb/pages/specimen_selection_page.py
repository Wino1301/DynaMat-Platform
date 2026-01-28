"""Specimen Selection Page - First page of SHPB Analysis Wizard.

Allows user to select a specimen from the database using SPARQL queries.
"""

import logging
from typing import Optional, Dict, Any

from PyQt6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QGroupBox, QGridLayout, QComboBox, QTableWidget,
    QTableWidgetItem, QHeaderView, QLineEdit
)
from PyQt6.QtCore import Qt

from .base_page import BaseSHPBPage
from .....ontology.instance_query_builder import InstanceQueryBuilder
from .....config import config

logger = logging.getLogger(__name__)


class SpecimenSelectionPage(BaseSHPBPage):
    """Specimen selection page for SHPB analysis.

    Features:
    - Filter by material
    - Table view of available specimens
    - Selected specimen properties display
    """

    def __init__(self, state, ontology_manager, qudt_manager=None, parent=None):
        super().__init__(state, ontology_manager, qudt_manager, parent)

        self.setTitle("Select Specimen")
        self.setSubTitle("Choose a specimen from the database to analyze.")

        # Query builder for specimen lookup
        self.query_builder: Optional[InstanceQueryBuilder] = None
        self.specimens_cache = []

    def _setup_ui(self) -> None:
        """Setup page UI."""
        layout = self._create_base_layout()

        # Filter section
        filter_group = self._create_group_box("Filter Specimens")
        filter_layout = QHBoxLayout(filter_group)

        filter_layout.addWidget(QLabel("Material:"))
        self.material_filter = QComboBox()
        self.material_filter.setMinimumWidth(200)
        self.material_filter.addItem("All Materials", None)
        self.material_filter.currentIndexChanged.connect(self._on_filter_changed)
        filter_layout.addWidget(self.material_filter)

        filter_layout.addWidget(QLabel("Search:"))
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Filter by ID...")
        self.search_box.textChanged.connect(self._filter_table)
        filter_layout.addWidget(self.search_box)

        filter_layout.addStretch()

        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self._load_specimens)
        filter_layout.addWidget(refresh_btn)

        layout.addWidget(filter_group)

        # Specimen table
        table_group = self._create_group_box("Available Specimens")
        table_layout = QVBoxLayout(table_group)

        self.specimen_table = QTableWidget()
        self.specimen_table.setColumnCount(5)
        self.specimen_table.setHorizontalHeaderLabels([
            "Specimen ID", "Material", "Shape", "Structure", "Batch"
        ])
        self.specimen_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.specimen_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.specimen_table.setAlternatingRowColors(True)
        self.specimen_table.setSortingEnabled(True)
        self.specimen_table.itemSelectionChanged.connect(self._on_selection_changed)
        self.specimen_table.doubleClicked.connect(self._on_double_click)

        # Auto-resize columns
        header = self.specimen_table.horizontalHeader()
        for i in range(5):
            header.setSectionResizeMode(i, QHeaderView.ResizeMode.Stretch)

        table_layout.addWidget(self.specimen_table)
        layout.addWidget(table_group)

        # Selected specimen details
        details_group = self._create_group_box("Selected Specimen Details")
        details_layout = QGridLayout(details_group)

        # Property labels
        self.detail_labels = {}
        properties = [
            ("Specimen ID:", "specimen_id"),
            ("Material:", "material"),
            ("Shape:", "shape"),
            ("Structure:", "structure"),
            ("Original Height:", "height"),
            ("Original Diameter:", "diameter"),
            ("Mass:", "mass"),
        ]

        for row, (label_text, key) in enumerate(properties):
            label = QLabel(label_text)
            label.setStyleSheet("font-weight: bold;")
            details_layout.addWidget(label, row, 0)

            value_label = QLabel("--")
            self.detail_labels[key] = value_label
            details_layout.addWidget(value_label, row, 1)

            # Add second column for more properties
            if row < len(properties) // 2:
                details_layout.setColumnStretch(2, 1)

        layout.addWidget(details_group)

        self._add_status_area()

    def initializePage(self) -> None:
        """Initialize page when it becomes current."""
        super().initializePage()

        # Initialize query builder if needed
        if self.query_builder is None:
            self._initialize_query_builder()

        # Load materials for filter
        self._load_materials()

        # Load specimens
        self._load_specimens()

        # If specimen already selected, show it
        if self.state.specimen_uri:
            self._highlight_selected_specimen()

    def validatePage(self) -> bool:
        """Validate before allowing Next."""
        if not self.state.specimen_uri:
            self.show_warning("Selection Required", "Please select a specimen before continuing.")
            return False

        if not self.state.specimen_data:
            self.show_warning("Data Error", "Failed to load specimen data. Please try selecting again.")
            return False

        return True

    def _initialize_query_builder(self) -> None:
        """Initialize the instance query builder."""
        try:
            self.query_builder = InstanceQueryBuilder(self.ontology_manager)

            # Scan specimens directory
            if config.SPECIMENS_DIR.exists():
                indexed = self.query_builder.scan_and_index(
                    config.SPECIMENS_DIR,
                    "https://dynamat.utep.edu/ontology#Specimen",
                    "*_specimen.ttl"
                )
                self.logger.info(f"Indexed {indexed} specimens")
            else:
                self.logger.warning("Specimens directory not found")

        except Exception as e:
            self.logger.error(f"Failed to initialize query builder: {e}")
            self.set_status(f"Error: {e}", is_error=True)

    def _load_materials(self) -> None:
        """Load available materials for filter dropdown."""
        try:
            # Get materials from ontology
            materials = self.ontology_manager.get_available_individuals(
                "https://dynamat.utep.edu/ontology#Material"
            )

            self.material_filter.clear()
            self.material_filter.addItem("All Materials", None)

            for mat_uri, mat_label in materials:
                # Extract display name
                if '#' in mat_uri:
                    display_name = mat_label or mat_uri.split('#')[-1]
                else:
                    display_name = mat_label or mat_uri

                self.material_filter.addItem(display_name, mat_uri)

        except Exception as e:
            self.logger.warning(f"Failed to load materials: {e}")

    def _load_specimens(self) -> None:
        """Load specimens from database."""
        try:
            self.set_status("Loading specimens...")
            self.show_progress()

            if not self.query_builder:
                self._initialize_query_builder()

            if not self.query_builder:
                raise RuntimeError("Query builder not available")

            # Get filter value
            material_filter = self.material_filter.currentData()

            # Query specimens
            full_props = [
                "https://dynamat.utep.edu/ontology#hasSpecimenID",
                "https://dynamat.utep.edu/ontology#hasMaterial",
                "https://dynamat.utep.edu/ontology#hasShape",
                "https://dynamat.utep.edu/ontology#hasStructure",
                "https://dynamat.utep.edu/ontology#hasBatchID",
            ]

            self.specimens_cache = self.query_builder.find_all_instances(
                "https://dynamat.utep.edu/ontology#Specimen",
                display_properties=full_props
            )

            # Apply material filter
            if material_filter:
                self.specimens_cache = [
                    s for s in self.specimens_cache
                    if s.get("https://dynamat.utep.edu/ontology#hasMaterial") == material_filter
                ]

            # Populate table
            self._populate_table()

            self.set_status(f"Found {len(self.specimens_cache)} specimen(s)")
            self.hide_progress()

        except Exception as e:
            self.logger.error(f"Failed to load specimens: {e}")
            self.set_status(f"Error loading specimens: {e}", is_error=True)
            self.hide_progress()

    def _populate_table(self) -> None:
        """Populate specimen table from cache."""
        self.specimen_table.setRowCount(len(self.specimens_cache))
        self.specimen_table.setSortingEnabled(False)

        for row, specimen in enumerate(self.specimens_cache):
            # Extract values
            specimen_id = specimen.get("https://dynamat.utep.edu/ontology#hasSpecimenID", "")
            material = specimen.get("https://dynamat.utep.edu/ontology#hasMaterial", "")
            shape = specimen.get("https://dynamat.utep.edu/ontology#hasShape", "")
            structure = specimen.get("https://dynamat.utep.edu/ontology#hasStructure", "")
            batch = specimen.get("https://dynamat.utep.edu/ontology#hasBatchID", "")

            # Format URI values to display names
            def format_uri(uri):
                if isinstance(uri, str) and '#' in uri:
                    return uri.split('#')[-1]
                return str(uri) if uri else ""

            items = [
                specimen_id,
                format_uri(material),
                format_uri(shape),
                format_uri(structure),
                batch
            ]

            for col, value in enumerate(items):
                item = QTableWidgetItem(str(value) if value else "")
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)

                # Store full specimen data in first column
                if col == 0:
                    item.setData(Qt.ItemDataRole.UserRole, specimen)

                self.specimen_table.setItem(row, col, item)

        self.specimen_table.setSortingEnabled(True)

    def _filter_table(self) -> None:
        """Filter table based on search text."""
        search_text = self.search_box.text().lower()

        for row in range(self.specimen_table.rowCount()):
            match = False
            for col in range(self.specimen_table.columnCount()):
                item = self.specimen_table.item(row, col)
                if item and search_text in item.text().lower():
                    match = True
                    break

            self.specimen_table.setRowHidden(row, not match)

    def _on_filter_changed(self) -> None:
        """Handle material filter change."""
        self._load_specimens()

    def _on_selection_changed(self) -> None:
        """Handle table selection change."""
        selected_rows = self.specimen_table.selectionModel().selectedRows()
        if not selected_rows:
            self._clear_details()
            return

        row = selected_rows[0].row()
        first_item = self.specimen_table.item(row, 0)
        specimen_data = first_item.data(Qt.ItemDataRole.UserRole)

        if specimen_data:
            self._load_specimen_details(specimen_data)

    def _on_double_click(self) -> None:
        """Handle double-click on table row."""
        # Just select the specimen, validation happens on Next
        pass

    def _load_specimen_details(self, specimen_metadata: Dict[str, Any]) -> None:
        """Load full specimen details and update state.

        Args:
            specimen_metadata: Basic specimen metadata from table
        """
        try:
            specimen_uri = specimen_metadata.get('uri')
            if not specimen_uri:
                self.logger.warning("No URI in specimen metadata")
                return

            # Load full specimen data
            full_data = self.query_builder.load_full_instance_data(specimen_uri)

            if not full_data:
                self.logger.warning(f"Could not load full data for {specimen_uri}")
                return

            # Update state
            self.state.specimen_uri = specimen_uri
            self.state.specimen_data = full_data
            self.state.specimen_id = full_data.get(
                "https://dynamat.utep.edu/ontology#hasSpecimenID",
                specimen_uri.split('#')[-1] if '#' in specimen_uri else specimen_uri
            )

            # Update details display
            self._update_details_display(full_data)

            self.set_status(f"Selected: {self.state.specimen_id}")
            self.logger.info(f"Selected specimen: {self.state.specimen_id}")

        except Exception as e:
            self.logger.error(f"Failed to load specimen details: {e}")
            self.set_status(f"Error: {e}", is_error=True)

    def _update_details_display(self, data: Dict[str, Any]) -> None:
        """Update details labels from specimen data.

        Args:
            data: Full specimen data dictionary
        """
        # Helper to extract value
        def get_value(key: str, format_uri: bool = True) -> str:
            full_key = f"https://dynamat.utep.edu/ontology#{key}"
            value = data.get(full_key, "")

            if not value:
                return "--"

            if format_uri and isinstance(value, str) and '#' in value:
                return value.split('#')[-1]

            # Handle measurement dictionaries
            if isinstance(value, dict) and 'value' in value:
                unit = value.get('unit', '')
                if unit:
                    unit_symbol = unit.split(':')[-1] if ':' in unit else unit
                    return f"{value['value']} {unit_symbol}"
                return str(value['value'])

            return str(value)

        # Update labels
        self.detail_labels["specimen_id"].setText(get_value("hasSpecimenID", False))
        self.detail_labels["material"].setText(get_value("hasMaterial"))
        self.detail_labels["shape"].setText(get_value("hasShape"))
        self.detail_labels["structure"].setText(get_value("hasStructure"))
        self.detail_labels["height"].setText(get_value("hasOriginalHeight"))
        self.detail_labels["diameter"].setText(get_value("hasOriginalDiameter"))
        self.detail_labels["mass"].setText(get_value("hasMass"))

    def _clear_details(self) -> None:
        """Clear details display."""
        for label in self.detail_labels.values():
            label.setText("--")

    def _highlight_selected_specimen(self) -> None:
        """Highlight previously selected specimen in table."""
        if not self.state.specimen_uri:
            return

        for row in range(self.specimen_table.rowCount()):
            item = self.specimen_table.item(row, 0)
            if item:
                data = item.data(Qt.ItemDataRole.UserRole)
                if data and data.get('uri') == self.state.specimen_uri:
                    self.specimen_table.selectRow(row)
                    break
