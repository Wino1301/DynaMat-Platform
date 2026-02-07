"""
DynaMat Platform - Entity Selector Dialog
Modal dialog wrapper around EntitySelectorWidget
"""

import logging
from typing import Dict, Optional, Any

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QMessageBox
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

from .entity_selector_config import EntitySelectorConfig
from .entity_selector_widget import EntitySelectorWidget

logger = logging.getLogger(__name__)


class EntitySelectorDialog(QDialog):
    """
    Modal dialog for entity selection.

    Wraps EntitySelectorWidget in a dialog with OK/Cancel buttons
    and provides a convenient static method for quick selection.

    Example:
        # Static method for quick selection
        data = EntitySelectorDialog.select_entity(
            config=EntitySelectorConfig(
                class_uri="https://dynamat.utep.edu/ontology#Specimen",
                display_properties=["dyn:hasSpecimenID", "dyn:hasMaterial"],
            ),
            query_builder=qb,
            title="Select Specimen",
            parent=self
        )
        if data:
            print(f"Selected: {data}")

        # Or create dialog instance for more control
        dialog = EntitySelectorDialog(config, query_builder=qb, title="Select")
        if dialog.exec() == QDialog.DialogCode.Accepted:
            data = dialog.get_selected_data()
    """

    def __init__(
        self,
        config: EntitySelectorConfig,
        query_builder=None,
        ontology_manager=None,
        title: str = "Select Entity",
        parent=None
    ):
        """
        Initialize the entity selector dialog.

        Args:
            config: EntitySelectorConfig defining widget behavior
            query_builder: InstanceQueryBuilder for SPARQL queries
            ontology_manager: OntologyManager for loading individuals
            title: Dialog window title
            parent: Parent widget
        """
        super().__init__(parent)

        self.config = config
        self.logger = logging.getLogger(__name__)

        # Selected data
        self._selected_data: Optional[Dict[str, Any]] = None

        # Setup dialog
        self.setWindowTitle(title)
        self.setModal(True)
        self.resize(900, 600)

        self._setup_ui(config, query_builder, ontology_manager)

    def _setup_ui(
        self,
        config: EntitySelectorConfig,
        query_builder,
        ontology_manager
    ):
        """Setup the dialog UI."""
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        # Title/instruction label
        title_label = QLabel("Select an entity:")
        title_font = QFont()
        title_font.setPointSize(10)
        title_font.setBold(True)
        title_label.setFont(title_font)
        layout.addWidget(title_label)

        # Entity selector widget
        self._selector = EntitySelectorWidget(
            config=config,
            query_builder=query_builder,
            ontology_manager=ontology_manager,
            parent=self
        )

        # Connect double-click to accept
        self._selector.entity_selected.connect(self._on_entity_selected)
        self._selector.selection_changed.connect(self._on_selection_changed)
        self._selector.error_occurred.connect(self._on_error)

        layout.addWidget(self._selector)

        # Button row
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        # Load button (disabled until selection)
        self._load_button = QPushButton("Load")
        self._load_button.setDefault(True)
        self._load_button.setEnabled(False)
        self._load_button.clicked.connect(self._on_load_clicked)
        button_layout.addWidget(self._load_button)

        # Cancel button
        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(cancel_button)

        layout.addLayout(button_layout)

    def _on_selection_changed(self, data: Dict[str, Any]):
        """Handle selection change - enable load button."""
        self._load_button.setEnabled(True)

    def _on_entity_selected(self, data: Dict[str, Any]):
        """Handle double-click selection - accept dialog."""
        self._selected_data = data
        self.accept()

    def _on_load_clicked(self):
        """Handle Load button click."""
        # Get selected entity
        entity = self._selector.get_selected_entity()

        if not entity:
            QMessageBox.warning(
                self,
                "No Selection",
                "Please select an entity first."
            )
            return

        # Load full data
        uri = entity.get('uri')
        if uri:
            full_data = self._selector.load_full_entity_data(uri)
            if full_data:
                full_data['file_path'] = entity.get('file_path', '')
                self._selected_data = full_data
                self.accept()
                return

        # Fallback to metadata
        self._selected_data = entity
        self.accept()

    def _on_error(self, error: str):
        """Handle errors from selector."""
        QMessageBox.warning(
            self,
            "Error",
            f"An error occurred:\n\n{error}"
        )

    # ============================================================================
    # PUBLIC METHODS
    # ============================================================================

    def get_selected_data(self) -> Optional[Dict[str, Any]]:
        """
        Get the selected entity data.

        Returns:
            Dictionary with full entity data, or None if cancelled
        """
        return self._selected_data

    def get_selector(self) -> EntitySelectorWidget:
        """
        Get the embedded EntitySelectorWidget.

        Useful for advanced customization.

        Returns:
            The EntitySelectorWidget instance
        """
        return self._selector

    def refresh(self):
        """Refresh the entity list."""
        self._selector.refresh()

    # ============================================================================
    # STATIC CONVENIENCE METHOD
    # ============================================================================

    @staticmethod
    def select_entity(
        config: EntitySelectorConfig,
        query_builder=None,
        ontology_manager=None,
        title: str = "Select Entity",
        parent=None
    ) -> Optional[Dict[str, Any]]:
        """
        Show a modal dialog and return selected entity data.

        This is a convenience method for quick entity selection.
        Returns None if the dialog is cancelled.

        Args:
            config: EntitySelectorConfig defining widget behavior
            query_builder: InstanceQueryBuilder for SPARQL queries
            ontology_manager: OntologyManager for loading individuals
            title: Dialog window title
            parent: Parent widget

        Returns:
            Dictionary with entity data, or None if cancelled

        Example:
            data = EntitySelectorDialog.select_entity(
                config=EntitySelectorConfig(
                    class_uri="https://dynamat.utep.edu/ontology#Specimen",
                    display_properties=["dyn:hasSpecimenID"],
                ),
                query_builder=qb,
                title="Load Specimen",
                parent=self
            )
            if data:
                self.load_specimen(data)
        """
        dialog = EntitySelectorDialog(
            config=config,
            query_builder=query_builder,
            ontology_manager=ontology_manager,
            title=title,
            parent=parent
        )

        if dialog.exec() == QDialog.DialogCode.Accepted:
            return dialog.get_selected_data()

        return None
