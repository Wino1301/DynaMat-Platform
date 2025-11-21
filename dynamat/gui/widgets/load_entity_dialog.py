"""
DynaMat Platform - Load Entity Dialog
Generic dialog for loading existing entity instances using SPARQL queries
"""

import logging
from typing import Dict, List, Optional, Any
from pathlib import Path

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton,
    QTableWidget, QTableWidgetItem, QLabel, QHeaderView,
    QLineEdit, QMessageBox
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont

logger = logging.getLogger(__name__)


class LoadEntityDialog(QDialog):
    """
    Generic dialog for loading existing entity instances.

    Features:
    - SPARQL-based instance discovery
    - Table view with sortable columns
    - Double-click or button selection
    - Lazy loading of full data
    - Reusable across entity types (Specimen, Test, etc.)

    Signals:
        entity_selected: Emitted when entity is selected with full data dict
    """

    entity_selected = pyqtSignal(dict)

    def __init__(
        self,
        query_builder,
        class_uri: str,
        display_properties: List[str],
        property_labels: Optional[Dict[str, str]] = None,
        title: str = "Load Entity",
        parent=None
    ):
        """
        Initialize the load entity dialog.

        Args:
            query_builder: InstanceQueryBuilder for querying instances
            class_uri: Full URI of the ontology class (e.g., "https://dynamat.utep.edu/ontology#Specimen")
            display_properties: List of property URIs to show in table (short names like "hasSpecimenID")
            property_labels: Optional dict mapping property URIs to display labels
            title: Dialog window title
            parent: Parent widget
        """
        super().__init__(parent)

        self.query_builder = query_builder
        self.class_uri = class_uri
        self.display_properties = display_properties
        self.property_labels = property_labels or {}
        self.logger = logging.getLogger(__name__)

        # Selected instance data
        self.selected_data = None
        self.instances_cache = []  # Cache of instance metadata from query

        # Setup UI
        self.setWindowTitle(title)
        self.setModal(True)
        self.resize(800, 600)

        self._setup_ui()
        self._load_instances()

    # ============================================================================
    # UI SETUP
    # ============================================================================

    def _setup_ui(self):
        """Setup the dialog UI."""
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        # Title label
        title_label = QLabel(f"Select an entity to load:")
        title_font = QFont()
        title_font.setPointSize(10)
        title_font.setBold(True)
        title_label.setFont(title_font)
        layout.addWidget(title_label)

        # Search box (future enhancement - placeholder for now)
        search_layout = QHBoxLayout()
        search_label = QLabel("Search:")
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Filter by ID or property...")
        self.search_box.textChanged.connect(self._filter_table)
        search_layout.addWidget(search_label)
        search_layout.addWidget(self.search_box)
        layout.addLayout(search_layout)

        # Table for displaying instances
        self.table = QTableWidget()
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setAlternatingRowColors(True)
        self.table.setSortingEnabled(True)
        self.table.doubleClicked.connect(self._on_double_click)

        # Set column count based on display properties
        self.table.setColumnCount(len(self.display_properties))

        # Set column headers
        headers = []
        for prop_uri in self.display_properties:
            # Use provided label or extract from URI
            if prop_uri in self.property_labels:
                label = self.property_labels[prop_uri]
            else:
                # Extract property name from URI (e.g., "hasSpecimenID" -> "Specimen ID")
                if '#' in prop_uri:
                    label = prop_uri.split('#')[-1]
                elif '/' in prop_uri:
                    label = prop_uri.split('/')[-1]
                else:
                    label = prop_uri

                # Convert camelCase to Title Case with spaces
                # "hasSpecimenID" -> "Specimen ID"
                if label.startswith('has'):
                    label = label[3:]  # Remove "has" prefix

                # Add spaces before capitals
                import re
                label = re.sub(r'([a-z])([A-Z])', r'\1 \2', label)

            headers.append(label)

        self.table.setHorizontalHeaderLabels(headers)

        # Auto-resize columns
        header = self.table.horizontalHeader()
        for i in range(len(self.display_properties)):
            header.setSectionResizeMode(i, QHeaderView.ResizeMode.Stretch)

        layout.addWidget(self.table)

        # Status label
        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: gray; font-style: italic;")
        layout.addWidget(self.status_label)

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        self.load_button = QPushButton("Load")
        self.load_button.setDefault(True)
        self.load_button.clicked.connect(self._on_load_clicked)
        self.load_button.setEnabled(False)  # Disabled until selection
        button_layout.addWidget(self.load_button)

        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(cancel_button)

        layout.addLayout(button_layout)

        # Connect table selection change
        self.table.itemSelectionChanged.connect(self._on_selection_changed)

    # ============================================================================
    # DATA LOADING
    # ============================================================================

    def _load_instances(self):
        """Load instances from query builder and populate table."""
        try:
            self.status_label.setText("Loading instances...")

            # Convert short property names to full URIs
            full_property_uris = []
            for prop in self.display_properties:
                if not prop.startswith('http'):
                    # Assume DynaMat namespace
                    full_uri = f"https://dynamat.utep.edu/ontology#{prop}"
                else:
                    full_uri = prop
                full_property_uris.append(full_uri)

            # Query instances
            self.instances_cache = self.query_builder.find_all_instances(
                self.class_uri,
                display_properties=full_property_uris
            )

            if not self.instances_cache:
                self.status_label.setText("No instances found.")
                QMessageBox.information(
                    self,
                    "No Instances",
                    "No instances of this type were found.\n\n"
                    "Please create a new instance or check the data directory."
                )
                return

            # Populate table
            self._populate_table(self.instances_cache)

            self.status_label.setText(f"Found {len(self.instances_cache)} instance(s)")
            self.logger.info(f"Loaded {len(self.instances_cache)} instances")

        except Exception as e:
            self.logger.error(f"Failed to load instances: {e}", exc_info=True)
            self.status_label.setText("Error loading instances")
            QMessageBox.critical(
                self,
                "Load Error",
                f"Failed to load instances:\n\n{str(e)}\n\n"
                f"See log for details."
            )

    def _populate_table(self, instances: List[Dict[str, Any]]):
        """
        Populate table with instance data.

        Args:
            instances: List of instance metadata dicts
        """
        self.table.setRowCount(len(instances))
        self.table.setSortingEnabled(False)  # Disable while populating

        for row, instance in enumerate(instances):
            # Populate columns
            for col, prop_uri in enumerate(self.display_properties):
                # Handle both short and full URIs
                full_uri = prop_uri if prop_uri.startswith('http') else f"https://dynamat.utep.edu/ontology#{prop_uri}"

                # Get value from instance data
                value = instance.get(full_uri, "")

                # Format value for display
                if isinstance(value, str):
                    # Extract just the name from URIs for display
                    if value.startswith('http'):
                        if '#' in value:
                            display_value = value.split('#')[-1]
                        elif '/' in value:
                            display_value = value.split('/')[-1]
                        else:
                            display_value = value
                    else:
                        display_value = value
                else:
                    display_value = str(value) if value else ""

                item = QTableWidgetItem(display_value)
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)  # Read-only

                # Store full instance metadata in first column for later retrieval
                if col == 0:
                    item.setData(Qt.ItemDataRole.UserRole, instance)

                self.table.setItem(row, col, item)

        self.table.setSortingEnabled(True)  # Re-enable sorting

    def _filter_table(self):
        """Filter table based on search box text."""
        search_text = self.search_box.text().lower()

        for row in range(self.table.rowCount()):
            # Check if any column contains search text
            match = False
            for col in range(self.table.columnCount()):
                item = self.table.item(row, col)
                if item and search_text in item.text().lower():
                    match = True
                    break

            # Show/hide row based on match
            self.table.setRowHidden(row, not match)

    # ============================================================================
    # EVENT HANDLERS
    # ============================================================================

    def _on_selection_changed(self):
        """Handle table selection change."""
        has_selection = len(self.table.selectedItems()) > 0
        self.load_button.setEnabled(has_selection)

    def _on_double_click(self):
        """Handle double-click on table row."""
        self._on_load_clicked()

    def _on_load_clicked(self):
        """Handle Load button click."""
        try:
            # Get selected row
            selected_rows = self.table.selectionModel().selectedRows()
            if not selected_rows:
                return

            row = selected_rows[0].row()

            # Get instance metadata from first column
            first_item = self.table.item(row, 0)
            instance_metadata = first_item.data(Qt.ItemDataRole.UserRole)

            if not instance_metadata:
                QMessageBox.warning(self, "Load Error", "Could not retrieve instance data.")
                return

            instance_uri = instance_metadata.get('uri')
            if not instance_uri:
                QMessageBox.warning(self, "Load Error", "Instance URI not found.")
                return

            # Update status
            self.status_label.setText("Loading full instance data...")

            # Lazy load full instance data
            self.selected_data = self.query_builder.load_full_instance_data(instance_uri)

            if not self.selected_data:
                QMessageBox.critical(
                    self,
                    "Load Error",
                    "Failed to load full instance data.\n\n"
                    "The file may be missing or corrupted."
                )
                return

            # Add URI to data for reference
            self.selected_data['uri'] = instance_uri
            self.selected_data['file_path'] = instance_metadata.get('file_path', '')

            self.logger.info(f"Loaded instance: {instance_uri}")

            # Emit signal and accept dialog
            self.entity_selected.emit(self.selected_data)
            self.accept()

        except Exception as e:
            self.logger.error(f"Failed to load instance: {e}", exc_info=True)
            QMessageBox.critical(
                self,
                "Load Error",
                f"Failed to load instance:\n\n{str(e)}\n\n"
                f"See log for details."
            )

    # ============================================================================
    # PUBLIC METHODS
    # ============================================================================

    def get_selected_data(self) -> Optional[Dict[str, Any]]:
        """
        Get the selected instance data.

        Returns:
            Dictionary with full instance data, or None if no selection
        """
        return self.selected_data

    def refresh(self):
        """Refresh the instance list."""
        self._load_instances()
