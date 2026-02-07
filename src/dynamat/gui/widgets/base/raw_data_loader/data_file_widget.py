"""
DynaMat Platform - Data File Widget
Ontology-driven sub-widget for file selection and parsing settings.
"""

import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd

from PyQt6.QtWidgets import (
    QWidget, QGridLayout, QLabel, QPushButton,
    QComboBox, QLineEdit, QFileDialog, QSpinBox,
)
from PyQt6.QtCore import pyqtSignal

logger = logging.getLogger(__name__)


# Fallback separators when ontology query fails or returns empty
_FALLBACK_SEPARATORS: List[Tuple[str, str, str]] = [
    # (label, delimiter_char, uri)
    ("Comma (,)", ",", "https://dynamat.utep.edu/ontology#CommaSeparator"),
    ("Tab (\\t)", "\t", "https://dynamat.utep.edu/ontology#TabSeparator"),
    ("Semicolon (;)", ";", "https://dynamat.utep.edu/ontology#SemicolonSeparator"),
    ("Space", " ", "https://dynamat.utep.edu/ontology#SpaceSeparator"),
]


class DataFileWidget(QWidget):
    """
    Ontology-driven sub-widget for file selection and parsing settings.

    Components:
    - File browse (hardcoded Python, not ontology-driven)
    - Separator dropdown (ontology-driven from dyn:ColumnSeparator individuals)
    - Skip rows spinbox (driven by dyn:hasHeaderRow annotation)

    Signals:
        file_loaded(object): Emitted when file is successfully parsed, payload is pd.DataFrame
        file_cleared(): Emitted when data is cleared
        settings_changed(): Emitted when separator or skip rows change (triggers reload)
        error_occurred(str): Emitted on errors
    """

    file_loaded = pyqtSignal(object)
    file_cleared = pyqtSignal()
    settings_changed = pyqtSignal()
    error_occurred = pyqtSignal(str)

    def __init__(
        self,
        ontology_manager=None,
        parent=None,
        file_filters: str = "CSV Files (*.csv);;Text Files (*.txt);;Excel Files (*.xlsx);;All Files (*)",
    ):
        super().__init__(parent)

        self._ontology_manager = ontology_manager
        self._file_filters = file_filters

        self._file_path: Optional[Path] = None
        self._default_directory: Optional[Path] = None
        self._dataframe: Optional[pd.DataFrame] = None

        # Separator data: list of (label, delimiter_char, uri)
        self._separator_data: List[Tuple[str, str, str]] = []

        self._setup_ui()
        self._populate_separator_combo()

    # ------------------------------------------------------------------
    # UI Setup
    # ------------------------------------------------------------------

    def _setup_ui(self) -> None:
        """Build the widget UI."""
        layout = QGridLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Row 0: File path + Browse button
        layout.addWidget(QLabel("File:"), 0, 0)
        self._file_path_edit = QLineEdit()
        self._file_path_edit.setReadOnly(True)
        self._file_path_edit.setPlaceholderText("Select a data file...")
        layout.addWidget(self._file_path_edit, 0, 1)

        self._browse_btn = QPushButton("Browse...")
        self._browse_btn.clicked.connect(self._browse_file)
        layout.addWidget(self._browse_btn, 0, 2)

        # Row 1: Separator dropdown
        layout.addWidget(QLabel("Separator:"), 1, 0)
        self._separator_combo = QComboBox()
        self._separator_combo.currentIndexChanged.connect(self._on_settings_changed)
        layout.addWidget(self._separator_combo, 1, 1)

        # Row 2: Skip rows spinbox
        layout.addWidget(QLabel("Skip Rows:"), 2, 0)
        self._skip_rows_spin = QSpinBox()
        self._skip_rows_spin.setRange(0, 100)
        self._skip_rows_spin.setValue(0)
        self._skip_rows_spin.valueChanged.connect(self._on_settings_changed)
        layout.addWidget(self._skip_rows_spin, 2, 1)

    def _populate_separator_combo(self) -> None:
        """Populate separator dropdown from ontology or fallback."""
        self._separator_data = []
        self._separator_combo.clear()

        # Try to load from ontology
        if self._ontology_manager:
            try:
                separators = self._load_separators_from_ontology()
                if separators:
                    self._separator_data = separators
            except Exception as e:
                logger.warning(f"Failed to load separators from ontology: {e}")

        # Fallback if no ontology data
        if not self._separator_data:
            self._separator_data = list(_FALLBACK_SEPARATORS)

        # Populate combo
        for label, delimiter_char, uri in self._separator_data:
            self._separator_combo.addItem(label, delimiter_char)

    def _load_separators_from_ontology(self) -> List[Tuple[str, str, str]]:
        """
        Query ontology for ColumnSeparator individuals.

        Returns:
            List of (label, delimiter_char, uri) tuples, sorted by gui:hasDisplayOrder
        """
        result = []

        column_separator_uri = "https://dynamat.utep.edu/ontology#ColumnSeparator"
        delimiter_char_uri = "https://dynamat.utep.edu/ontology#hasDelimiterCharacter"
        display_order_uri = "https://dynamat.utep.edu/ontology/gui#hasDisplayOrder"

        # Get all ColumnSeparator individuals
        individuals = self._ontology_manager.domain_queries.get_instances_of_class(
            column_separator_uri
        )

        if not individuals:
            return []

        for ind in individuals:
            uri = ind.get('uri', '')
            label = ind.get('label', ind.get('name', ''))

            # Get delimiter character
            props = self._ontology_manager.get_individual_property_values(
                uri, [delimiter_char_uri, display_order_uri]
            )

            delimiter_char = props.get(delimiter_char_uri, ',')
            display_order = props.get(display_order_uri, 99)

            # Handle tab escape sequence
            if delimiter_char == '\\t':
                delimiter_char = '\t'

            result.append((label, delimiter_char, uri, display_order))

        # Sort by display order
        result.sort(key=lambda x: x[3])

        # Return without display_order
        return [(label, delim, uri) for label, delim, uri, _ in result]

    # ------------------------------------------------------------------
    # File operations
    # ------------------------------------------------------------------

    def _browse_file(self) -> None:
        """Open file browser dialog."""
        start_dir = str(self._default_directory) if self._default_directory else ""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Data File", start_dir, self._file_filters
        )
        if file_path:
            self.load_file(Path(file_path))

    def load_file(self, path: Path) -> bool:
        """
        Load a data file.

        Args:
            path: Path to the data file.

        Returns:
            True if loaded successfully.
        """
        path = Path(path)
        if not path.exists():
            self.error_occurred.emit(f"File not found: {path}")
            return False

        self._file_path = path
        self._file_path_edit.setText(str(path))
        return self._load_data()

    def _on_settings_changed(self) -> None:
        """Handle separator or skip rows change."""
        if self._file_path:
            self._load_data()
        self.settings_changed.emit()

    def _load_data(self) -> bool:
        """Load the data file with current settings."""
        if not self._file_path:
            return False

        try:
            separator = self._separator_combo.currentData()
            skip_rows = self._skip_rows_spin.value()
            path = self._file_path
            suffix = path.suffix.lower()

            if suffix in ('.csv', '.txt'):
                df = pd.read_csv(path, sep=separator, skiprows=skip_rows)
            elif suffix == '.xlsx':
                try:
                    df = pd.read_excel(path, skiprows=skip_rows)
                except ImportError:
                    self.error_occurred.emit(
                        "Excel support requires openpyxl. Install with: pip install openpyxl"
                    )
                    return False
            else:
                # Default to CSV parsing
                df = pd.read_csv(path, sep=separator, skiprows=skip_rows)

            if df.empty:
                self.error_occurred.emit("File is empty")
                return False

            self._dataframe = df
            self.file_loaded.emit(df)
            return True

        except Exception as e:
            logger.error(f"Failed to load file: {e}")
            self.error_occurred.emit(str(e))
            self._dataframe = None
            return False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_file_path(self) -> Optional[Path]:
        """Get the currently selected file path."""
        return self._file_path

    def get_separator(self) -> str:
        """Get the current delimiter character."""
        return self._separator_combo.currentData() or ","

    def get_separator_uri(self) -> Optional[str]:
        """Get the URI of the current ColumnSeparator individual."""
        index = self._separator_combo.currentIndex()
        if 0 <= index < len(self._separator_data):
            return self._separator_data[index][2]
        return None

    def get_skip_rows(self) -> int:
        """Get the current skip rows value."""
        return self._skip_rows_spin.value()

    def get_dataframe(self) -> Optional[pd.DataFrame]:
        """Get the loaded DataFrame."""
        return self._dataframe

    def set_default_directory(self, path: Path) -> None:
        """Set the default directory for the file browser."""
        self._default_directory = Path(path)

    def clear(self) -> None:
        """Clear all loaded data and reset the widget."""
        self._dataframe = None
        self._file_path = None
        self._file_path_edit.clear()
        self._skip_rows_spin.setValue(0)
        self._separator_combo.setCurrentIndex(0)
        self.file_cleared.emit()
