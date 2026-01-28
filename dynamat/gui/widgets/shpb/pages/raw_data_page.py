"""Raw Data Page - Load and map CSV columns for SHPB analysis."""

import logging
from pathlib import Path
from typing import Optional, List

import pandas as pd
import numpy as np

from PyQt6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QGroupBox, QGridLayout, QComboBox, QLineEdit,
    QFileDialog, QTableWidget, QTableWidgetItem, QHeaderView,
    QSpinBox
)
from PyQt6.QtCore import Qt

from .base_page import BaseSHPBPage
from .....config import config

logger = logging.getLogger(__name__)


class RawDataPage(BaseSHPBPage):
    """Raw data loading page for SHPB analysis.

    Features:
    - CSV file selection
    - Column mapping for time, incident, transmitted
    - Data preview
    - Sampling interval detection
    """

    def __init__(self, state, ontology_manager, qudt_manager=None, parent=None):
        super().__init__(state, ontology_manager, qudt_manager, parent)

        self.setTitle("Load Raw Data")
        self.setSubTitle("Select a CSV file and map the data columns.")

        self.preview_df: Optional[pd.DataFrame] = None

    def _setup_ui(self) -> None:
        """Setup page UI."""
        layout = self._create_base_layout()

        # File selection section
        file_group = self._create_group_box("Data File")
        file_layout = QGridLayout(file_group)

        file_layout.addWidget(QLabel("CSV File:"), 0, 0)

        self.file_path_edit = QLineEdit()
        self.file_path_edit.setReadOnly(True)
        self.file_path_edit.setPlaceholderText("Select a CSV file...")
        file_layout.addWidget(self.file_path_edit, 0, 1)

        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self._browse_file)
        file_layout.addWidget(browse_btn, 0, 2)

        file_layout.addWidget(QLabel("Separator:"), 1, 0)

        self.separator_combo = QComboBox()
        self.separator_combo.addItem("Comma (,)", ",")
        self.separator_combo.addItem("Tab (\\t)", "\t")
        self.separator_combo.addItem("Semicolon (;)", ";")
        self.separator_combo.addItem("Space", " ")
        self.separator_combo.currentIndexChanged.connect(self._on_separator_changed)
        file_layout.addWidget(self.separator_combo, 1, 1)

        file_layout.addWidget(QLabel("Skip Rows:"), 2, 0)

        self.skip_rows_spin = QSpinBox()
        self.skip_rows_spin.setRange(0, 100)
        self.skip_rows_spin.setValue(0)
        self.skip_rows_spin.valueChanged.connect(self._reload_preview)
        file_layout.addWidget(self.skip_rows_spin, 2, 1)

        layout.addWidget(file_group)

        # Column mapping section
        mapping_group = self._create_group_box("Column Mapping")
        mapping_layout = QGridLayout(mapping_group)

        mapping_layout.addWidget(QLabel("Time Column:"), 0, 0)
        self.time_combo = QComboBox()
        self.time_combo.currentIndexChanged.connect(self._on_mapping_changed)
        mapping_layout.addWidget(self.time_combo, 0, 1)

        mapping_layout.addWidget(QLabel("Incident Column:"), 1, 0)
        self.incident_combo = QComboBox()
        self.incident_combo.currentIndexChanged.connect(self._on_mapping_changed)
        mapping_layout.addWidget(self.incident_combo, 1, 1)

        mapping_layout.addWidget(QLabel("Transmitted Column:"), 2, 0)
        self.transmitted_combo = QComboBox()
        self.transmitted_combo.currentIndexChanged.connect(self._on_mapping_changed)
        mapping_layout.addWidget(self.transmitted_combo, 2, 1)

        # Sampling info
        mapping_layout.addWidget(QLabel(""), 3, 0)  # Spacer

        mapping_layout.addWidget(QLabel("Sampling Interval:"), 4, 0)
        self.sampling_label = QLabel("-- ms")
        mapping_layout.addWidget(self.sampling_label, 4, 1)

        mapping_layout.addWidget(QLabel("Total Samples:"), 5, 0)
        self.samples_label = QLabel("--")
        mapping_layout.addWidget(self.samples_label, 5, 1)

        layout.addWidget(mapping_group)

        # Data preview section
        preview_group = self._create_group_box("Data Preview")
        preview_layout = QVBoxLayout(preview_group)

        self.preview_table = QTableWidget()
        self.preview_table.setMaximumHeight(200)
        self.preview_table.setAlternatingRowColors(True)

        header = self.preview_table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)

        preview_layout.addWidget(self.preview_table)

        preview_info_layout = QHBoxLayout()
        self.preview_info_label = QLabel("")
        self.preview_info_label.setStyleSheet("color: gray;")
        preview_info_layout.addWidget(self.preview_info_label)
        preview_layout.addLayout(preview_info_layout)

        layout.addWidget(preview_group)

        self._add_status_area()

    def initializePage(self) -> None:
        """Initialize page when it becomes current."""
        super().initializePage()

        # Set default path to specimen's raw folder if available
        if self.state.specimen_id:
            default_dir = config.SPECIMENS_DIR / self.state.specimen_id / "raw"
            if default_dir.exists():
                self._default_dir = default_dir
            else:
                self._default_dir = config.SPECIMENS_DIR
        else:
            self._default_dir = config.SPECIMENS_DIR

        # If data already loaded, show it
        if self.state.csv_file_path:
            self.file_path_edit.setText(str(self.state.csv_file_path))
            self._reload_preview()

    def validatePage(self) -> bool:
        """Validate before allowing Next."""
        if self.state.raw_df is None or self.state.raw_df.empty:
            self.show_warning("Data Required", "Please load a CSV file before continuing.")
            return False

        # Check column mappings
        mapping = self.state.column_mapping
        required = ['time', 'incident', 'transmitted']
        missing = [r for r in required if r not in mapping or not mapping[r]]

        if missing:
            self.show_warning(
                "Mapping Required",
                f"Please map the following columns: {', '.join(missing)}"
            )
            return False

        # Verify columns exist in data
        for key, col_name in mapping.items():
            if col_name not in self.state.raw_df.columns:
                self.show_warning(
                    "Invalid Column",
                    f"Column '{col_name}' not found in data."
                )
                return False

        return True

    def _browse_file(self) -> None:
        """Open file browser for CSV selection."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Raw Data File",
            str(self._default_dir) if hasattr(self, '_default_dir') else "",
            "CSV Files (*.csv);;All Files (*)"
        )

        if file_path:
            self.file_path_edit.setText(file_path)
            self.state.csv_file_path = Path(file_path)
            self._load_csv()

    def _on_separator_changed(self) -> None:
        """Handle separator change."""
        self.state.csv_separator = self.separator_combo.currentData()
        if self.state.csv_file_path:
            self._load_csv()

    def _reload_preview(self) -> None:
        """Reload CSV with current settings."""
        if self.state.csv_file_path:
            self._load_csv()

    def _load_csv(self) -> None:
        """Load CSV file and update preview."""
        try:
            self.set_status("Loading CSV file...")
            self.show_progress()

            separator = self.separator_combo.currentData()
            skip_rows = self.skip_rows_spin.value()

            # Load CSV
            df = pd.read_csv(
                self.state.csv_file_path,
                sep=separator,
                skiprows=skip_rows
            )

            if df.empty:
                raise ValueError("CSV file is empty")

            # Store in state
            self.state.raw_df = df
            self.state.total_samples = len(df)
            self.preview_df = df

            # Update column combos
            self._update_column_combos(df.columns.tolist())

            # Update preview table
            self._update_preview_table(df)

            # Auto-detect column mappings
            self._auto_detect_mappings(df.columns.tolist())

            self.set_status(f"Loaded {len(df)} rows, {len(df.columns)} columns")
            self.hide_progress()

        except Exception as e:
            self.logger.error(f"Failed to load CSV: {e}")
            self.set_status(f"Error: {e}", is_error=True)
            self.hide_progress()

            # Clear state on error
            self.state.raw_df = None
            self.preview_df = None

    def _update_column_combos(self, columns: List[str]) -> None:
        """Update column mapping dropdowns.

        Args:
            columns: List of column names from CSV
        """
        combos = [self.time_combo, self.incident_combo, self.transmitted_combo]

        for combo in combos:
            combo.blockSignals(True)
            combo.clear()
            combo.addItem("-- Select Column --", None)
            for col in columns:
                combo.addItem(col, col)
            combo.blockSignals(False)

    def _auto_detect_mappings(self, columns: List[str]) -> None:
        """Try to auto-detect column mappings.

        Args:
            columns: List of column names
        """
        # Common patterns for each column type
        time_patterns = ['time', 't', 'time_s', 'time_ms', 'timestamp']
        incident_patterns = ['incident', 'inc', 'i_bar', 'incident_bar', 'ch1', 'channel1']
        transmitted_patterns = ['transmitted', 'trans', 't_bar', 'transmission', 'ch2', 'channel2']

        columns_lower = [c.lower() for c in columns]

        def find_match(patterns: List[str]) -> Optional[int]:
            for pattern in patterns:
                for i, col in enumerate(columns_lower):
                    if pattern in col:
                        return i
            return None

        # Try to auto-select
        time_idx = find_match(time_patterns)
        incident_idx = find_match(incident_patterns)
        transmitted_idx = find_match(transmitted_patterns)

        # If no exact match, use column order as fallback
        # Assuming: time, incident, transmitted (or time, ch1, ch2)
        if len(columns) >= 3:
            if time_idx is None:
                time_idx = 0
            if incident_idx is None:
                incident_idx = 1
            if transmitted_idx is None:
                transmitted_idx = 2

        # Update combos
        if time_idx is not None:
            self.time_combo.setCurrentIndex(time_idx + 1)  # +1 for "Select" item
        if incident_idx is not None:
            self.incident_combo.setCurrentIndex(incident_idx + 1)
        if transmitted_idx is not None:
            self.transmitted_combo.setCurrentIndex(transmitted_idx + 1)

        # Trigger mapping update
        self._on_mapping_changed()

    def _on_mapping_changed(self) -> None:
        """Handle column mapping changes."""
        time_col = self.time_combo.currentData()
        incident_col = self.incident_combo.currentData()
        transmitted_col = self.transmitted_combo.currentData()

        # Update state
        self.state.column_mapping = {
            'time': time_col,
            'incident': incident_col,
            'transmitted': transmitted_col
        }

        # Calculate sampling interval
        if time_col and self.state.raw_df is not None:
            try:
                time_data = self.state.raw_df[time_col].values
                if len(time_data) > 1:
                    # Calculate median interval
                    intervals = np.diff(time_data)
                    sampling_interval = np.median(intervals)

                    # Detect if time is in seconds or milliseconds
                    if sampling_interval < 0.01:  # Likely seconds, very small
                        sampling_interval *= 1000  # Convert to ms
                        self.state.sampling_interval = sampling_interval
                    else:
                        self.state.sampling_interval = sampling_interval

                    self.sampling_label.setText(f"{sampling_interval:.6f} ms")
                    self.samples_label.setText(f"{len(time_data):,}")
            except Exception as e:
                self.logger.warning(f"Could not calculate sampling interval: {e}")
                self.sampling_label.setText("-- ms")

    def _update_preview_table(self, df: pd.DataFrame) -> None:
        """Update preview table with data.

        Args:
            df: DataFrame to preview
        """
        # Show first 10 rows
        preview_rows = min(10, len(df))

        self.preview_table.setRowCount(preview_rows)
        self.preview_table.setColumnCount(len(df.columns))
        self.preview_table.setHorizontalHeaderLabels(df.columns.tolist())

        for row in range(preview_rows):
            for col, col_name in enumerate(df.columns):
                value = df.iloc[row, col]

                # Format numeric values
                if isinstance(value, float):
                    text = f"{value:.6g}"
                else:
                    text = str(value)

                item = QTableWidgetItem(text)
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.preview_table.setItem(row, col, item)

        self.preview_info_label.setText(
            f"Showing {preview_rows} of {len(df)} rows"
        )
