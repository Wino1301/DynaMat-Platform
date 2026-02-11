"""SHPB Analysis State - Form-data-only shared state across wizard pages.

This dataclass holds all intermediate data during the SHPB analysis workflow.
Instead of 50+ individual scalar fields, metadata is stored as ontology
form-data dicts (property_uri -> value) per analysis stage. Only runtime
array data (DataFrames, numpy arrays) remain as typed fields.

Pages store form data via ``form_builder.get_form_data()`` and restore via
``form_builder.set_form_data()``. Accessor helpers read values from the
stored form dicts.
"""

from dataclasses import dataclass, field
from typing import Dict, Any, Optional, Tuple, List
from pathlib import Path

import numpy as np
import pandas as pd

# DynaMat ontology namespace
DYN_NS = "https://dynamat.utep.edu/ontology#"


@dataclass
class SHPBAnalysisState:
    """Shared state for SHPB analysis wizard (form-data-only design).

    Organized by analysis stage to match the wizard workflow.
    Metadata is stored as form-data dicts (property_uri -> value) per
    ontology class. Only runtime arrays and DataFrames are stored as
    typed fields.

    All fields default to None/empty to support progressive population
    as the user advances through wizard pages.
    """

    # ==================== SPECIMEN (from EntitySelectorWidget) ====================
    specimen_uri: Optional[str] = None
    specimen_id: Optional[str] = None
    specimen_data: Optional[Dict[str, Any]] = None  # Full specimen properties

    # ==================== RAW DATA (from RawDataLoaderWidget) ====================
    raw_df: Optional[pd.DataFrame] = None
    csv_file_path: Optional[Path] = None
    csv_separator: str = ","
    column_mapping: Dict[str, str] = field(default_factory=dict)
    unit_mapping: Dict[str, Dict[str, str]] = field(default_factory=dict)
    sampling_interval: Optional[float] = None  # ms
    total_samples: Optional[int] = None
    # Auto-computed file metadata (property_uri -> value)
    raw_file_metadata: Optional[Dict[str, Any]] = None
    # Strain gauge URIs per signal  {'incident': uri, 'transmitted': uri}
    gauge_mapping: Dict[str, Optional[str]] = field(default_factory=dict)

    # ==================== EQUIPMENT (dyn:SHPBCompression form) ====================
    equipment_form_data: Optional[Dict[str, Any]] = None
    equipment_properties: Optional[Dict[str, Any]] = None  # Cached bar/gauge props

    # ==================== PULSE CHARACTERISTICS (computed from equipment) ====================
    # Keys: pulse_duration, pulse_length, pulse_speed, pulse_strain_amplitude,
    #        pulse_stress_amplitude, pulse_points
    pulse_characteristics: Optional[Dict[str, Any]] = None

    # ==================== PULSE DETECTION (3x dyn:PulseDetectionParams forms) ====================
    detection_form_data: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    # {'incident': {prop_uri->val}, 'transmitted': {...}, 'reflected': {...}}
    pulse_windows: Dict[str, Tuple[int, int]] = field(default_factory=dict)

    # ==================== SEGMENTATION (dyn:SegmentationParams form) ====================
    segmentation_form_data: Optional[Dict[str, Any]] = None
    segmented_pulses: Dict[str, np.ndarray] = field(default_factory=dict)
    centering_shifts: Dict[str, int] = field(default_factory=dict)

    # ==================== ALIGNMENT (dyn:AlignmentParams form) ====================
    alignment_form_data: Optional[Dict[str, Any]] = None
    aligned_pulses: Dict[str, np.ndarray] = field(default_factory=dict)
    time_vector: Optional[np.ndarray] = None

    # ==================== RESULTS (enriched calculation output) ====================
    # {key: {'data': array, 'series_type': uri, 'unit': uri, 'derived_from': [uris], ...}}
    enriched_results: Optional[Dict[str, Dict[str, Any]]] = None
    # Flat results dict for backward compat (key -> np.ndarray)
    calculation_results: Optional[Dict[str, np.ndarray]] = None
    equilibrium_form_data: Optional[Dict[str, Any]] = None  # dyn:EquilibriumMetrics

    # ==================== TUKEY (dyn:TukeyWindowParams form) ====================
    tukey_form_data: Optional[Dict[str, Any]] = None
    tapered_pulses: Dict[str, np.ndarray] = field(default_factory=dict)

    # ==================== CUMULATIVE VALIDATION GRAPHS ====================
    # Each wizard page stores its partial RDF graph here under a key
    # (e.g., "raw_data", "equipment", "pulse_detection").  The base-page
    # validation merges all stored graphs to give each step a cumulative view.
    page_graphs: Dict[str, Any] = field(default_factory=dict)

    # ==================== LOAD STATE ====================
    _loaded_from_previous: bool = False

    # ==================== EXPORT ====================
    test_id: Optional[str] = None
    export_form_data: Optional[Dict[str, Any]] = None  # validity, test_type
    exported_file_path: Optional[Path] = None

    # ==================== ACCESSOR HELPERS ====================

    def get_equipment_value(self, property_name: str) -> Any:
        """Read a value from equipment form data.

        Args:
            property_name: Local name without namespace, e.g. 'hasStrikerBar'

        Returns:
            The value or None if not found
        """
        if not self.equipment_form_data:
            return None
        return self.equipment_form_data.get(f"{DYN_NS}{property_name}")

    def get_detection_param(self, pulse_type: str, property_name: str) -> Any:
        """Read detection param from form data.

        Args:
            pulse_type: 'incident', 'transmitted', or 'reflected'
            property_name: Local name without namespace
        """
        form = self.detection_form_data.get(pulse_type, {})
        return form.get(f"{DYN_NS}{property_name}")

    def get_segmentation_param(self, property_name: str) -> Any:
        """Read segmentation param from form data."""
        if not self.segmentation_form_data:
            return None
        return self.segmentation_form_data.get(f"{DYN_NS}{property_name}")

    def get_alignment_param(self, property_name: str) -> Any:
        """Read alignment param from form data."""
        if not self.alignment_form_data:
            return None
        return self.alignment_form_data.get(f"{DYN_NS}{property_name}")

    def get_equilibrium_metric(self, property_name: str) -> Any:
        """Read equilibrium metric from form data."""
        if not self.equilibrium_form_data:
            return None
        return self.equilibrium_form_data.get(f"{DYN_NS}{property_name}")

    def get_tukey_param(self, property_name: str) -> Any:
        """Read Tukey window param from form data."""
        if not self.tukey_form_data:
            return None
        return self.tukey_form_data.get(f"{DYN_NS}{property_name}")

    # ==================== CHECK METHODS ====================

    def has_raw_data(self) -> bool:
        """Check if raw data has been loaded."""
        return self.raw_df is not None and not self.raw_df.empty

    def has_detected_pulses(self) -> bool:
        """Check if all pulse windows have been detected."""
        required = {'incident', 'transmitted', 'reflected'}
        return required <= set(self.pulse_windows.keys())

    def has_segmented_pulses(self) -> bool:
        """Check if all pulses have been segmented."""
        required = {'incident', 'transmitted', 'reflected'}
        return required <= set(self.segmented_pulses.keys())

    def has_aligned_pulses(self) -> bool:
        """Check if pulses have been aligned."""
        required = {'incident', 'transmitted', 'reflected'}
        return required <= set(self.aligned_pulses.keys())

    def has_results(self) -> bool:
        """Check if stress-strain results have been calculated."""
        return self.enriched_results is not None or self.calculation_results is not None

    def has_equilibrium_metrics(self) -> bool:
        """Check if equilibrium metrics have been calculated."""
        return self.equilibrium_form_data is not None

    def get_raw_signal(self, signal_type: str) -> Optional[np.ndarray]:
        """Get raw signal array by type.

        Args:
            signal_type: 'time', 'incident', or 'transmitted'

        Returns:
            Signal array or None if not available
        """
        if self.raw_df is None:
            return None

        col_name = self.column_mapping.get(signal_type)
        if col_name and col_name in self.raw_df.columns:
            return self.raw_df[col_name].values

        return None

    def get_equipment_property(self, component: str, property_name: str) -> Any:
        """Get equipment property by component and property name.

        Args:
            component: 'striker_bar', 'incident_bar', 'transmission_bar',
                      'incident_gauge', 'transmission_gauge'
            property_name: Property to retrieve (e.g., 'wave_speed', 'gauge_factor')

        Returns:
            Property value or None
        """
        if self.equipment_properties is None:
            return None

        component_props = self.equipment_properties.get(component, {})
        return component_props.get(property_name)

    # ==================== STATE MANAGEMENT ====================

    def reset_from_stage(self, stage: int) -> None:
        """Reset state from a specific stage onwards (for re-analysis).

        Args:
            stage: Stage number (1-12) to reset from
        """
        if stage <= 1:
            self._loaded_from_previous = False

        if stage <= 2:
            self.raw_df = None
            self.csv_file_path = None
            self.column_mapping = {}
            self.raw_file_metadata = None

        if stage <= 3:
            self.equipment_form_data = None
            self.equipment_properties = None
            self.pulse_characteristics = None

        if stage <= 5:
            self.detection_form_data = {}
            self.pulse_windows = {}

        if stage <= 6:
            self.segmentation_form_data = None
            self.segmented_pulses = {}
            self.centering_shifts = {}

        if stage <= 7:
            self.alignment_form_data = None
            self.aligned_pulses = {}
            self.time_vector = None

        if stage <= 9:
            self.enriched_results = None
            self.calculation_results = None
            self.equilibrium_form_data = None

        if stage <= 10:
            self.tukey_form_data = None
            self.tapered_pulses = {}

        if stage <= 12:
            self.export_form_data = None
            self.exported_file_path = None
