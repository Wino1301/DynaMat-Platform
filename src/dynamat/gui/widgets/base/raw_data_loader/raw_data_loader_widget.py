"""
DynaMat Platform - Raw Data Loader Widget
Ontology-driven widget for loading raw data files and mapping columns to series.
"""

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Any

import numpy as np
import pandas as pd

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QGroupBox, QGridLayout, QComboBox, QLineEdit,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QFrame,
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont

from .raw_data_loader_config import RawDataLoaderConfig
from .data_file_widget import DataFileWidget

logger = logging.getLogger(__name__)


@dataclass
class _SeriesMapping:
    """Internal data structure for a required series mapping row."""
    key: str                    # dyn:hasDefaultColumnName value (e.g., "time")
    label: str                  # rdfs:label (e.g., "Time")
    series_type_uri: str        # Full URI of SeriesType individual
    quantity_kind: Optional[str]  # QUDT quantity kind URI
    default_unit: Optional[str]   # QUDT unit URI from ontology
    column_combo: Optional[QComboBox] = field(default=None, repr=False)
    unit_combo: Optional[QComboBox] = field(default=None, repr=False)


class RawDataLoaderWidget(QWidget):
    """
    Reusable, ontology-driven widget for loading raw data files.

    Reads required column types from the ontology via dyn:hasRawSeries,
    provides column mapping with name matching and order fallback,
    and includes per-series QUDT unit dropdowns.

    Signals:
        data_loaded(dict): Emitted when data is successfully loaded and mapped.
            Payload keys: dataframe, column_mapping, unit_mapping, file_path,
                         sampling_interval, total_samples, separator
        data_cleared(): Emitted when data is cleared.
        mapping_changed(dict): Emitted when column or unit mapping changes.
            Payload keys: column_mapping, unit_mapping, is_complete
        error_occurred(str): Emitted on errors.
    """

    data_loaded = pyqtSignal(dict)
    data_cleared = pyqtSignal()
    mapping_changed = pyqtSignal(dict)
    error_occurred = pyqtSignal(str)

    def __init__(
        self,
        config: RawDataLoaderConfig,
        ontology_manager,
        qudt_manager=None,
        parent=None,
    ):
        super().__init__(parent)

        self._config = config
        self._ontology_manager = ontology_manager
        self._qudt_manager = qudt_manager

        self._series_mappings: List[_SeriesMapping] = []
        self._dataframe: Optional[pd.DataFrame] = None
        self._file_path: Optional[Path] = None
        self._default_directory: Optional[Path] = config.default_directory

        self._build_series_definitions()
        self._setup_ui()

    # ------------------------------------------------------------------
    # Initialization
    # ------------------------------------------------------------------

    def _build_series_definitions(self) -> None:
        """Build the list of required series from ontology or manual config."""
        if self._config.test_class_uri:
            self._build_from_ontology()
        elif self._config.required_series:
            self._build_from_manual()

    def _build_from_ontology(self) -> None:
        """Query ontology for required raw series."""
        try:
            series_list = self._ontology_manager.domain_queries.get_raw_series_for_class(
                self._config.test_class_uri
            )

            for s in series_list:
                self._series_mappings.append(_SeriesMapping(
                    key=s.get('default_column_name', ''),
                    label=s.get('label', ''),
                    series_type_uri=s.get('series_type_uri', ''),
                    quantity_kind=s.get('quantity_kind'),
                    default_unit=s.get('unit'),
                ))

            logger.info(
                f"Built {len(self._series_mappings)} series definitions "
                f"from ontology for {self._config.test_class_uri}"
            )
        except Exception as e:
            logger.error(f"Failed to query ontology for series: {e}")
            self._series_mappings = []

    def _build_from_manual(self) -> None:
        """Build series definitions from manual config."""
        for s in self._config.required_series:
            self._series_mappings.append(_SeriesMapping(
                key=s.get('key', ''),
                label=s.get('label', ''),
                series_type_uri=s.get('series_type_uri', ''),
                quantity_kind=s.get('quantity_kind'),
                default_unit=s.get('unit'),
            ))

    # ------------------------------------------------------------------
    # UI Setup
    # ------------------------------------------------------------------

    def _setup_ui(self) -> None:
        """Build the widget UI."""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(10)

        # --- Data File section (using DataFileWidget) ---
        file_group = QGroupBox("Data File")
        file_group.setFont(self._bold_font())
        file_layout = QVBoxLayout(file_group)

        self._data_file_widget = DataFileWidget(
            ontology_manager=self._ontology_manager,
            parent=self,
            file_filters=self._config.file_filters,
        )
        if self._default_directory:
            self._data_file_widget.set_default_directory(self._default_directory)

        # Connect DataFileWidget signals
        self._data_file_widget.file_loaded.connect(self._on_file_loaded)
        self._data_file_widget.file_cleared.connect(self._on_file_cleared)
        self._data_file_widget.settings_changed.connect(self._on_settings_changed)
        self._data_file_widget.error_occurred.connect(self.error_occurred.emit)

        file_layout.addWidget(self._data_file_widget)
        main_layout.addWidget(file_group)

        # --- Column Mapping section ---
        mapping_group = QGroupBox("Column Mapping")
        mapping_group.setFont(self._bold_font())
        mapping_layout = QGridLayout(mapping_group)

        # Header row
        header_series = QLabel("Series")
        header_series.setStyleSheet("font-weight: bold;")
        mapping_layout.addWidget(header_series, 0, 0)
        header_column = QLabel("Column")
        header_column.setStyleSheet("font-weight: bold;")
        mapping_layout.addWidget(header_column, 0, 1)
        header_unit = QLabel("Unit")
        header_unit.setStyleSheet("font-weight: bold;")
        mapping_layout.addWidget(header_unit, 0, 2)

        # Create mapping rows from series definitions
        for i, sm in enumerate(self._series_mappings):
            row = i + 1

            label = QLabel(f"{sm.label}:")
            mapping_layout.addWidget(label, row, 0)

            column_combo = QComboBox()
            column_combo.addItem("-- Select Column --", None)
            column_combo.currentIndexChanged.connect(self._on_mapping_changed)
            mapping_layout.addWidget(column_combo, row, 1)
            sm.column_combo = column_combo

            unit_combo = QComboBox()
            unit_combo.setMinimumWidth(100)
            unit_combo.setMaximumWidth(120)
            self._populate_unit_combo(unit_combo, sm.quantity_kind, sm.default_unit)
            unit_combo.currentIndexChanged.connect(self._on_mapping_changed)
            mapping_layout.addWidget(unit_combo, row, 2)
            sm.unit_combo = unit_combo

        # Separator line
        separator_row = len(self._series_mappings) + 1
        sep_line = QFrame()
        sep_line.setFrameShape(QFrame.Shape.HLine)
        sep_line.setFrameShadow(QFrame.Shadow.Sunken)
        mapping_layout.addWidget(sep_line, separator_row, 0, 1, 3)

        # Sampling info
        info_row = separator_row + 1
        mapping_layout.addWidget(QLabel("Sampling Interval:"), info_row, 0)
        self._sampling_label = QLabel("-- ms")
        mapping_layout.addWidget(self._sampling_label, info_row, 1)

        mapping_layout.addWidget(QLabel("Total Samples:"), info_row + 1, 0)
        self._samples_label = QLabel("--")
        mapping_layout.addWidget(self._samples_label, info_row + 1, 1)

        main_layout.addWidget(mapping_group)

        # --- Data Preview section ---
        preview_group = QGroupBox("Data Preview")
        preview_group.setFont(self._bold_font())
        preview_layout = QVBoxLayout(preview_group)

        self._preview_table = QTableWidget()
        self._preview_table.setMaximumHeight(200)
        self._preview_table.setAlternatingRowColors(True)
        header = self._preview_table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        preview_layout.addWidget(self._preview_table)

        self._preview_info_label = QLabel("")
        self._preview_info_label.setStyleSheet("color: gray;")
        preview_layout.addWidget(self._preview_info_label)

        main_layout.addWidget(preview_group)

    def _bold_font(self) -> QFont:
        """Return a bold font for group box titles."""
        font = QFont()
        font.setBold(True)
        return font

    def _populate_unit_combo(
        self,
        combo: QComboBox,
        quantity_kind: Optional[str],
        default_unit: Optional[str],
    ) -> None:
        """Populate a unit combo box from QUDT via quantity kind."""
        combo.clear()

        if not self._qudt_manager or not quantity_kind:
            # No QUDT manager or no quantity kind — show a single default entry
            if default_unit:
                symbol = self._extract_unit_symbol(default_unit)
                combo.addItem(symbol, default_unit)
            else:
                combo.addItem("--", "")
            return

        units = self._qudt_manager.get_units_for_quantity_kind(quantity_kind)

        if not units:
            if default_unit:
                symbol = self._extract_unit_symbol(default_unit)
                combo.addItem(symbol, default_unit)
            else:
                combo.addItem("--", "")
            return

        default_index = 0
        default_normalized = self._normalize_uri(default_unit) if default_unit else ""

        for i, unit_info in enumerate(units):
            combo.addItem(unit_info.symbol, unit_info.uri)
            combo.setItemData(i, unit_info.label, Qt.ItemDataRole.ToolTipRole)

            # Match default unit
            if default_normalized and self._normalize_uri(unit_info.uri) == default_normalized:
                default_index = i

        combo.setCurrentIndex(default_index)

    # ------------------------------------------------------------------
    # File operations (delegated to DataFileWidget)
    # ------------------------------------------------------------------

    def load_file(self, path: Path) -> bool:
        """
        Load a data file programmatically.

        Args:
            path: Path to the data file.

        Returns:
            True if loaded successfully.
        """
        return self._data_file_widget.load_file(path)

    def _on_file_loaded(self, df: pd.DataFrame) -> None:
        """Handle file loaded from DataFileWidget."""
        self._dataframe = df
        self._file_path = self._data_file_widget.get_file_path()

        # Update UI
        self._update_column_combos(df.columns.tolist())
        self._update_preview_table(df)
        self._auto_map_columns(df.columns.tolist())

    def _on_file_cleared(self) -> None:
        """Handle file cleared from DataFileWidget."""
        self._dataframe = None
        self._file_path = None
        self.data_cleared.emit()

    def _on_settings_changed(self) -> None:
        """Handle settings changed (separator or skip rows) from DataFileWidget."""
        # DataFrame is updated via file_loaded signal if file was reloaded
        pass

    # ------------------------------------------------------------------
    # Column mapping
    # ------------------------------------------------------------------

    def _update_column_combos(self, columns: List[str]) -> None:
        """Populate all column mapping combos with file columns."""
        for sm in self._series_mappings:
            combo = sm.column_combo
            combo.blockSignals(True)
            combo.clear()
            combo.addItem("-- Select Column --", None)
            for col in columns:
                combo.addItem(col, col)
            combo.blockSignals(False)

    def _auto_map_columns(self, columns: List[str]) -> None:
        """
        Auto-map columns using name matching then order fallback.

        Strategy:
        1. Name match: If any column name matches dyn:hasDefaultColumnName (case-insensitive)
        2. Order fallback: Assign next unmapped column by position
        """
        columns_lower = [c.lower() for c in columns]
        used_indices = set()

        # Pass 1: name matching
        for sm in self._series_mappings:
            if not sm.key:
                continue
            key_lower = sm.key.lower()
            for i, col_lower in enumerate(columns_lower):
                if col_lower == key_lower and i not in used_indices:
                    sm.column_combo.setCurrentIndex(i + 1)  # +1 for placeholder
                    used_indices.add(i)
                    break

        # Pass 2: order fallback for unmatched series
        next_available = 0
        for sm in self._series_mappings:
            if sm.column_combo.currentData() is not None:
                continue  # Already matched

            while next_available < len(columns) and next_available in used_indices:
                next_available += 1

            if next_available < len(columns):
                sm.column_combo.setCurrentIndex(next_available + 1)
                used_indices.add(next_available)
                next_available += 1

        # Trigger mapping update
        self._on_mapping_changed()

    def _on_mapping_changed(self) -> None:
        """Handle any column or unit combo change."""
        column_mapping = self.get_column_mapping()
        unit_mapping = self.get_unit_mapping()

        # Update sampling interval
        self._update_sampling_info()

        # Emit mapping_changed
        self.mapping_changed.emit({
            'column_mapping': column_mapping,
            'unit_mapping': unit_mapping,
            'is_complete': self.is_mapping_complete(),
        })

        # If mapping is complete and data is loaded, emit data_loaded
        if self._dataframe is not None and self.is_mapping_complete():
            self.data_loaded.emit(self._build_data_payload())

    def _update_sampling_info(self) -> None:
        """Calculate and display sampling interval from time column with selected unit."""
        if self._dataframe is None:
            self._sampling_label.setText("--")
            self._samples_label.setText("--")
            return

        self._samples_label.setText(f"{len(self._dataframe):,}")

        # Find time series mapping
        time_sm = None
        for sm in self._series_mappings:
            if sm.key.lower() == 'time':
                time_sm = sm
                break

        if not time_sm:
            self._sampling_label.setText("--")
            return

        # Get time column
        time_col = time_sm.column_combo.currentData() if time_sm.column_combo else None
        if not time_col or time_col not in self._dataframe.columns:
            self._sampling_label.setText("--")
            return

        # Get selected unit symbol
        unit_symbol = "ms"  # Default fallback
        if time_sm.unit_combo:
            unit_symbol = time_sm.unit_combo.currentText() or "ms"

        # Calculate sampling interval
        try:
            time_data = self._dataframe[time_col].values
            if len(time_data) > 1:
                intervals = np.diff(time_data)
                sampling_interval = float(np.median(intervals))
                self._sampling_label.setText(f"{sampling_interval:.6f} {unit_symbol}")
                return
        except Exception as e:
            logger.warning(f"Could not calculate sampling interval: {e}")

        self._sampling_label.setText(f"-- {unit_symbol}")

    # ------------------------------------------------------------------
    # Preview table
    # ------------------------------------------------------------------

    def _update_preview_table(self, df: pd.DataFrame) -> None:
        """Update the data preview table."""
        preview_rows = min(self._config.preview_rows, len(df))

        self._preview_table.setRowCount(preview_rows)
        self._preview_table.setColumnCount(len(df.columns))
        self._preview_table.setHorizontalHeaderLabels(df.columns.tolist())

        for row in range(preview_rows):
            for col_idx, col_name in enumerate(df.columns):
                value = df.iloc[row, col_idx]
                text = f"{value:.6g}" if isinstance(value, float) else str(value)

                item = QTableWidgetItem(text)
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self._preview_table.setItem(row, col_idx, item)

        self._preview_info_label.setText(
            f"Showing {preview_rows} of {len(df)} rows"
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_data(self) -> Optional[Dict[str, Any]]:
        """Get current loaded data and mappings.

        Returns:
            Dict with keys: dataframe, column_mapping, unit_mapping, file_path,
            sampling_interval, total_samples, separator. None if no data loaded.
        """
        if self._dataframe is None:
            return None
        return self._build_data_payload()

    def get_dataframe(self) -> Optional[pd.DataFrame]:
        """Get the currently loaded DataFrame."""
        return self._dataframe

    def get_column_mapping(self) -> Dict[str, str]:
        """Get current column mapping: {series_key: column_name}."""
        mapping = {}
        for sm in self._series_mappings:
            col = sm.column_combo.currentData() if sm.column_combo else None
            if col:
                mapping[sm.key] = col
        return mapping

    def get_unit_mapping(self) -> Dict[str, Dict[str, str]]:
        """Get current unit mapping: {series_key: {unit: uri, symbol: text}}."""
        mapping = {}
        for sm in self._series_mappings:
            if sm.unit_combo:
                uri = sm.unit_combo.currentData() or ""
                symbol = sm.unit_combo.currentText() or ""
                mapping[sm.key] = {'unit': uri, 'symbol': symbol}
        return mapping

    def get_sampling_interval(self) -> Optional[float]:
        """Get calculated sampling interval, or None."""
        if self._dataframe is None:
            return None

        for sm in self._series_mappings:
            if sm.key.lower() == 'time' and sm.column_combo and sm.column_combo.currentData():
                time_col = sm.column_combo.currentData()
                if time_col in self._dataframe.columns:
                    try:
                        time_data = self._dataframe[time_col].values
                        if len(time_data) > 1:
                            return float(np.median(np.diff(time_data)))
                    except Exception:
                        pass
        return None

    def is_mapping_complete(self) -> bool:
        """Check if all required series have a mapped column."""
        for sm in self._series_mappings:
            if sm.column_combo is None or sm.column_combo.currentData() is None:
                return False
        return True

    def set_default_directory(self, path: Path) -> None:
        """Set the default directory for the file browser."""
        self._default_directory = Path(path)
        self._data_file_widget.set_default_directory(path)

    def clear(self) -> None:
        """Clear all loaded data and reset the widget."""
        self._dataframe = None
        self._file_path = None

        # Clear DataFileWidget
        self._data_file_widget.clear()

        # Clear column mapping combos
        for sm in self._series_mappings:
            if sm.column_combo:
                sm.column_combo.blockSignals(True)
                sm.column_combo.clear()
                sm.column_combo.addItem("-- Select Column --", None)
                sm.column_combo.blockSignals(False)

        # Clear preview
        self._preview_table.clearContents()
        self._preview_table.setRowCount(0)
        self._preview_table.setColumnCount(0)
        self._preview_info_label.setText("")
        self._sampling_label.setText("-- ms")
        self._samples_label.setText("--")

        self.data_cleared.emit()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_data_payload(self) -> Dict[str, Any]:
        """Build the data payload dict emitted by signals."""
        return {
            'dataframe': self._dataframe,
            'column_mapping': self.get_column_mapping(),
            'unit_mapping': self.get_unit_mapping(),
            'file_path': self._file_path,
            'sampling_interval': self.get_sampling_interval(),
            'total_samples': len(self._dataframe) if self._dataframe is not None else 0,
            'separator': self._data_file_widget.get_separator(),
            'separator_uri': self._data_file_widget.get_separator_uri(),
        }

    @staticmethod
    def _normalize_uri(uri: str) -> str:
        """Normalize a URI for comparison."""
        if not uri:
            return ""
        uri = str(uri).strip().strip('"\'')
        if ':' in uri and not uri.startswith('http'):
            prefix, local = uri.split(':', 1)
            if prefix == 'unit':
                return f'http://qudt.org/vocab/unit/{local}'
            elif prefix == 'qkdv':
                return f'http://qudt.org/vocab/quantitykind/{local}'
        return uri

    @staticmethod
    def _extract_unit_symbol(unit_uri: str) -> str:
        """Extract a unit symbol from a URI (fallback when no QUDT manager)."""
        symbols = {
            'MilliSEC': 'ms', 'SEC': 's', 'MicroSEC': 'us',
            'V': 'V', 'MilliV': 'mV',
            'MegaPA': 'MPa', 'GigaPA': 'GPa',
            'MilliM': 'mm', 'M': 'm',
            'N': 'N', 'KiloN': 'kN',
            'PER-SEC': '1/s', 'UNITLESS': '-',
            'M-PER-SEC': 'm/s',
        }
        if '/' in unit_uri:
            local = unit_uri.split('/')[-1]
        elif '#' in unit_uri:
            local = unit_uri.split('#')[-1]
        else:
            local = unit_uri
        return symbols.get(local, local)
