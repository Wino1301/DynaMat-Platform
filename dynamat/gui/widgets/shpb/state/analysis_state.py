"""SHPB Analysis State - Shared state across wizard pages.

This dataclass holds all intermediate data during SHPB analysis workflow,
enabling data flow between wizard pages without tight coupling.
"""

from dataclasses import dataclass, field
from typing import Dict, Any, Optional, Tuple, List
from pathlib import Path

import numpy as np
import pandas as pd


@dataclass
class SHPBAnalysisState:
    """Shared state for SHPB analysis wizard.

    Organized by analysis stage to match the wizard workflow:
    1. Specimen selection
    2. Raw data loading
    3. Equipment configuration
    4-5. Pulse detection
    6. Segmentation
    7. Alignment
    8-9. Results calculation
    10. Tukey windowing
    11-12. Export

    All fields default to None/empty to support progressive population
    as the user advances through wizard pages.
    """

    # ==================== STAGE 1: SPECIMEN ====================
    specimen_uri: Optional[str] = None
    specimen_data: Optional[Dict[str, Any]] = None
    specimen_id: Optional[str] = None

    # ==================== STAGE 2: RAW DATA ====================
    raw_df: Optional[pd.DataFrame] = None
    csv_file_path: Optional[Path] = None
    csv_separator: str = ","
    column_mapping: Dict[str, str] = field(default_factory=dict)
    # Column mapping: {'time': 'col_name', 'incident': 'col_name', 'transmitted': 'col_name'}
    unit_mapping: Dict[str, Dict[str, str]] = field(default_factory=dict)
    # Unit mapping: {'time': {'unit': 'uri', 'symbol': 'ms'}, ...}

    # Sampling information
    sampling_interval: Optional[float] = None  # ms
    total_samples: Optional[int] = None

    # ==================== STAGE 3: EQUIPMENT ====================
    # Equipment URIs
    striker_bar_uri: Optional[str] = None
    incident_bar_uri: Optional[str] = None
    transmission_bar_uri: Optional[str] = None
    incident_gauge_uri: Optional[str] = None
    transmission_gauge_uri: Optional[str] = None
    momentum_trap_uri: Optional[str] = None
    pulse_shaper_uri: Optional[str] = None

    # Test conditions
    striker_velocity: Optional[Dict[str, Any]] = None  # {'value': X, 'unit': '...'}
    striker_launch_pressure: Optional[Dict[str, Any]] = None
    barrel_offset: Optional[Dict[str, Any]] = None
    momentum_trap_distance: Optional[Dict[str, Any]] = None
    test_date: Optional[str] = None  # YYYY-MM-DD
    user_uri: Optional[str] = None

    # Extracted equipment properties (cached from ontology)
    equipment_properties: Optional[Dict[str, Any]] = None
    # Structure: {
    #   'striker_bar': {'uri', 'length', 'diameter', 'cross_section', 'material_uri', 'wave_speed'},
    #   'incident_bar': {...},
    #   'transmission_bar': {...},
    #   'incident_gauge': {'uri', 'gauge_factor', 'gauge_resistance', 'distance_from_specimen'},
    #   'transmission_gauge': {...}
    # }

    # ==================== STAGES 4-5: PULSE DETECTION ====================
    # Detection parameters (per pulse type)
    detection_params: Dict[str, Dict[str, Any]] = field(default_factory=lambda: {
        'incident': {
            'pulse_points': 15000,
            'k_trials': '6000,4000,2000',
            'polarity': 'compressive',
            'min_separation': None,
            'lower_bound': None,
            'upper_bound': None,
            'detection_metric': 'median'
        },
        'transmitted': {
            'pulse_points': 15000,
            'k_trials': '6000,4000,2000',
            'polarity': 'compressive',
            'min_separation': None,
            'lower_bound': None,
            'upper_bound': None,
            'detection_metric': 'median'
        },
        'reflected': {
            'pulse_points': 15000,
            'k_trials': '6000,4000,2000',
            'polarity': 'tensile',
            'min_separation': None,
            'lower_bound': None,
            'upper_bound': None,
            'detection_metric': 'median'
        }
    })

    # Detected windows: {'incident': (start, end), 'transmitted': (start, end), 'reflected': (start, end)}
    pulse_windows: Dict[str, Tuple[int, int]] = field(default_factory=dict)

    # ==================== STAGE 6: SEGMENTATION ====================
    segment_n_points: int = 25000
    segment_thresh_ratio: float = 0.01

    # Segmented and centered pulses: {'incident': array, 'transmitted': array, 'reflected': array}
    segmented_pulses: Dict[str, np.ndarray] = field(default_factory=dict)

    # Centering shifts applied during segmentation
    centering_shifts: Dict[str, int] = field(default_factory=dict)

    # ==================== STAGE 7: ALIGNMENT ====================
    k_linear: float = 0.35
    alignment_weights: Dict[str, float] = field(default_factory=lambda: {
        'corr': 0.3, 'u': 0.3, 'sr': 0.3, 'e': 0.1
    })
    search_bounds_t: Optional[Tuple[int, int]] = None  # (min, max) for transmitted shift
    search_bounds_r: Optional[Tuple[int, int]] = None  # (min, max) for reflected shift

    # Aligned pulses: {'incident': array, 'transmitted': array, 'reflected': array}
    aligned_pulses: Dict[str, np.ndarray] = field(default_factory=dict)

    # Alignment results
    shift_transmitted: Optional[int] = None
    shift_reflected: Optional[int] = None
    alignment_front_idx: Optional[int] = None
    linear_region: Optional[Tuple[int, int]] = None  # (start_idx, end_idx)

    # Time vector for aligned pulses
    time_vector: Optional[np.ndarray] = None

    # ==================== STAGES 8-9: RESULTS ====================
    # Calculation results from StressStrainCalculator
    calculation_results: Optional[Dict[str, np.ndarray]] = None
    # Keys: 'time', 'stress_1w', 'strain_1w', 'strain_rate_1w', 'true_stress_1w', 'true_strain_1w',
    #       'stress_3w', 'strain_3w', 'strain_rate_3w', 'true_stress_3w', 'true_strain_3w', etc.

    # Equilibrium metrics
    equilibrium_metrics: Optional[Dict[str, float]] = None
    # Keys: 'FBC', 'SEQI', 'SOI', 'DSUF', 'windowed_FBC_loading', etc.

    # Calculated characteristics
    pulse_duration: Optional[Dict[str, Any]] = None
    pulse_length: Optional[Dict[str, Any]] = None
    pulse_stress_amplitude: Optional[Dict[str, Any]] = None
    pulse_strain_amplitude: Optional[float] = None
    incident_rise_time: Optional[Dict[str, Any]] = None

    # ==================== STAGE 10: TUKEY WINDOW ====================
    tukey_alpha: float = 0.5

    # Tapered pulses for ML applications
    tapered_pulses: Dict[str, np.ndarray] = field(default_factory=dict)

    # ==================== STAGES 11-12: EXPORT ====================
    test_id: Optional[str] = None
    test_type: str = "specimen"  # "specimen", "calibration", or "elastic"

    # Validity assessment
    test_validity: Optional[str] = None  # "dyn:ValidTest", "dyn:QuestionableTest", "dyn:InvalidTest"
    validity_notes: Optional[str] = None
    validity_criteria: Optional[List[str]] = None

    # Override flags
    validity_override: bool = False
    validity_override_reason: Optional[str] = None

    # Export results
    exported_file_path: Optional[Path] = None

    # ==================== HELPER METHODS ====================

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
        return self.calculation_results is not None

    def has_equilibrium_metrics(self) -> bool:
        """Check if equilibrium metrics have been calculated."""
        return self.equilibrium_metrics is not None

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

    def reset_from_stage(self, stage: int) -> None:
        """Reset state from a specific stage onwards (for re-analysis).

        Args:
            stage: Stage number (1-12) to reset from
        """
        if stage <= 2:
            self.raw_df = None
            self.csv_file_path = None
            self.column_mapping = {}

        if stage <= 3:
            self.equipment_properties = None

        if stage <= 5:
            self.pulse_windows = {}

        if stage <= 6:
            self.segmented_pulses = {}
            self.centering_shifts = {}

        if stage <= 7:
            self.aligned_pulses = {}
            self.shift_transmitted = None
            self.shift_reflected = None
            self.time_vector = None

        if stage <= 9:
            self.calculation_results = None
            self.equilibrium_metrics = None

        if stage <= 10:
            self.tapered_pulses = {}

        if stage <= 12:
            self.test_validity = None
            self.validity_notes = None
            self.exported_file_path = None

    def to_test_metadata_kwargs(self) -> Dict[str, Any]:
        """Convert state to SHPBTestMetadata constructor kwargs.

        Returns:
            Dictionary suitable for SHPBTestMetadata(**kwargs)
        """
        # Build kwargs from state
        kwargs = {
            'test_id': self.test_id,
            'specimen_uri': self.specimen_uri,
            'test_date': self.test_date,
            'user': self.user_uri,

            # Equipment
            'striker_bar_uri': self.striker_bar_uri,
            'incident_bar_uri': self.incident_bar_uri,
            'transmission_bar_uri': self.transmission_bar_uri,
            'incident_strain_gauge_uri': self.incident_gauge_uri,
            'transmission_strain_gauge_uri': self.transmission_gauge_uri,
            'momentum_trap_uri': self.momentum_trap_uri,
            'pulse_shaper_uri': self.pulse_shaper_uri,

            # Test conditions
            'striker_velocity': self.striker_velocity,
            'striker_launch_pressure': self.striker_launch_pressure,
            'barrel_offset': self.barrel_offset,
            'momentum_trap_distance': self.momentum_trap_distance,

            # Detection params - incident
            'incident_pulse_points': self.detection_params.get('incident', {}).get('pulse_points'),
            'incident_k_trials': self.detection_params.get('incident', {}).get('k_trials'),
            'incident_polarity': self.detection_params.get('incident', {}).get('polarity'),
            'incident_min_separation': self.detection_params.get('incident', {}).get('min_separation'),
            'incident_lower_bound': self.detection_params.get('incident', {}).get('lower_bound'),
            'incident_upper_bound': self.detection_params.get('incident', {}).get('upper_bound'),
            'incident_detection_metric': self.detection_params.get('incident', {}).get('detection_metric'),

            # Detection params - transmitted
            'transmitted_pulse_points': self.detection_params.get('transmitted', {}).get('pulse_points'),
            'transmitted_k_trials': self.detection_params.get('transmitted', {}).get('k_trials'),
            'transmitted_polarity': self.detection_params.get('transmitted', {}).get('polarity'),
            'transmitted_min_separation': self.detection_params.get('transmitted', {}).get('min_separation'),
            'transmitted_lower_bound': self.detection_params.get('transmitted', {}).get('lower_bound'),
            'transmitted_upper_bound': self.detection_params.get('transmitted', {}).get('upper_bound'),
            'transmitted_detection_metric': self.detection_params.get('transmitted', {}).get('detection_metric'),

            # Detection params - reflected
            'reflected_pulse_points': self.detection_params.get('reflected', {}).get('pulse_points'),
            'reflected_k_trials': self.detection_params.get('reflected', {}).get('k_trials'),
            'reflected_polarity': self.detection_params.get('reflected', {}).get('polarity'),
            'reflected_min_separation': self.detection_params.get('reflected', {}).get('min_separation'),
            'reflected_lower_bound': self.detection_params.get('reflected', {}).get('lower_bound'),
            'reflected_upper_bound': self.detection_params.get('reflected', {}).get('upper_bound'),
            'reflected_detection_metric': self.detection_params.get('reflected', {}).get('detection_metric'),

            # Windows
            'incident_window_start': self.pulse_windows.get('incident', (None, None))[0],
            'incident_window_end': self.pulse_windows.get('incident', (None, None))[1],
            'transmitted_window_start': self.pulse_windows.get('transmitted', (None, None))[0],
            'transmitted_window_end': self.pulse_windows.get('transmitted', (None, None))[1],
            'reflected_window_start': self.pulse_windows.get('reflected', (None, None))[0],
            'reflected_window_end': self.pulse_windows.get('reflected', (None, None))[1],

            # Segmentation
            'segment_n_points': self.segment_n_points,
            'segment_thresh_ratio': self.segment_thresh_ratio,
            'incident_centering_shift': self.centering_shifts.get('incident'),
            'transmitted_centering_shift': self.centering_shifts.get('transmitted'),
            'reflected_centering_shift': self.centering_shifts.get('reflected'),

            # Alignment
            'k_linear': self.k_linear,
            'alignment_weight_corr': self.alignment_weights.get('corr'),
            'alignment_weight_u': self.alignment_weights.get('u'),
            'alignment_weight_sr': self.alignment_weights.get('sr'),
            'alignment_weight_e': self.alignment_weights.get('e'),
            'search_bounds_t_min': self.search_bounds_t[0] if self.search_bounds_t else None,
            'search_bounds_t_max': self.search_bounds_t[1] if self.search_bounds_t else None,
            'search_bounds_r_min': self.search_bounds_r[0] if self.search_bounds_r else None,
            'search_bounds_r_max': self.search_bounds_r[1] if self.search_bounds_r else None,
            'shift_transmitted': self.shift_transmitted,
            'shift_reflected': self.shift_reflected,
            'alignment_front_idx': self.alignment_front_idx,
            'linear_region_start': self.linear_region[0] if self.linear_region else None,
            'linear_region_end': self.linear_region[1] if self.linear_region else None,

            # Metrics
            'fbc': self.equilibrium_metrics.get('FBC') if self.equilibrium_metrics else None,
            'seqi': self.equilibrium_metrics.get('SEQI') if self.equilibrium_metrics else None,
            'soi': self.equilibrium_metrics.get('SOI') if self.equilibrium_metrics else None,
            'dsuf': self.equilibrium_metrics.get('DSUF') if self.equilibrium_metrics else None,
            'fbc_loading': self.equilibrium_metrics.get('windowed_FBC_loading') if self.equilibrium_metrics else None,
            'dsuf_loading': self.equilibrium_metrics.get('windowed_DSUF_loading') if self.equilibrium_metrics else None,
            'fbc_plateau': self.equilibrium_metrics.get('windowed_FBC_plateau') if self.equilibrium_metrics else None,
            'dsuf_plateau': self.equilibrium_metrics.get('windowed_DSUF_plateau') if self.equilibrium_metrics else None,
            'fbc_unloading': self.equilibrium_metrics.get('windowed_FBC_unloading') if self.equilibrium_metrics else None,
            'dsuf_unloading': self.equilibrium_metrics.get('windowed_DSUF_unloading') if self.equilibrium_metrics else None,

            # Tukey
            'tukey_alpha': self.tukey_alpha,

            # Validity
            'test_type': self.test_type,
            'test_validity': self.test_validity,
            'validity_notes': self.validity_notes,
            'validity_criteria': self.validity_criteria,

            # Calculated characteristics
            'pulse_duration': self.pulse_duration,
            'pulse_length': self.pulse_length,
            'pulse_stress_amplitude': self.pulse_stress_amplitude,
            'pulse_strain_amplitude': self.pulse_strain_amplitude,
            'incident_rise_time': self.incident_rise_time,
            'sampling_interval': {'value': self.sampling_interval, 'unit': 'unit:MilliSEC', 'reference_unit': 'unit:MilliSEC'} if self.sampling_interval else None,
        }

        # Filter out None values for cleaner kwargs
        return {k: v for k, v in kwargs.items() if v is not None}
