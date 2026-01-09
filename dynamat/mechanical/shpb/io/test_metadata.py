"""
SHPB Test Metadata - Complete Analysis Provenance

Complete metadata container capturing all SHPB analysis parameters for full reproducibility.

Design philosophy:
- Store ALL analysis parameters (120+) for complete provenance
- Use widget factory format for consistency: field values, not tuples
- Map field names to RDF property URIs in to_form_data()
- Support unit dictionaries: {'value': X, 'unit': user_unit, 'reference_unit': storage_unit}
- Enable automatic re-analysis when material properties change

Key format:
- Simple values: test_id = "TEST_001" → 'dyn:hasTestID': "TEST_001"
- URIs: incident_bar_uri = "dyn:IncidentBar_..." → 'dyn:hasIncidentBar': "dyn:IncidentBar_..."
- Measurements: striker_velocity = {'value': 10.0, 'unit': '...', 'reference_unit': '...'} → 'dyn:hasStrikerVelocity': dict
"""

from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List, Tuple
import logging
from datetime import datetime
import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class SHPBTestMetadata:
    """
    Complete SHPB test metadata with full analysis provenance (120+ parameters).

    Captures everything needed to reproduce the analysis: pulse detection configuration,
    segmentation parameters, alignment settings, equilibrium metrics, calculated characteristics,
    and data provenance.

    Value formats (following widget factory convention):
    - Simple values: "TEST_001", 32881, 0.35, True
    - URIs: "dyn:IncidentBar_C350_8ft_0375in"
    - Measurements with units: {'value': 10.0, 'unit': 'unit:M-PER-SEC', 'reference_unit': 'unit:M-PER-SEC'}
    - Lists: ["dyn:SG1", "dyn:SG2"]

    The to_form_data() method maps field names → RDF property URIs for InstanceWriter.
    """

    # ==================== SERIES METADATA LOOKUP TABLE ====================
    SERIES_METADATA = {
        # ===== RAW SIGNALS =====
        'time': {
            'series_type': 'Time',
            'quantity_kind': 'qkdv:Time',
            'unit': 'unit:MilliSEC',
            'legend_name': 'Time',
            'class_uri': 'dyn:RawSignal'
        },
        'incident': {
            'series_type': 'IncidentPulse',
            'quantity_kind': 'qkdv:Voltage',
            'unit': 'unit:V',
            'legend_name': 'Incident Pulse',
            'class_uri': 'dyn:RawSignal',
            'requires_gauge': True
        },
        'transmitted': {
            'series_type': 'TransmittedPulse',
            'quantity_kind': 'qkdv:Voltage',
            'unit': 'unit:V',
            'legend_name': 'Transmitted Pulse',
            'class_uri': 'dyn:RawSignal',
            'requires_gauge': True
        },

        # ===== 1-WAVE PROCESSED DATA =====
        'bar_displacement_1w': {
            'series_type': 'Displacement',
            'quantity_kind': 'qkdv:Length',
            'unit': 'unit:MilliM',
            'legend_name': 'Bar Displacement (1-wave)',
            'analysis_method': '1-wave',
            'class_uri': 'dyn:ProcessedData',
            'derived_from': ['transmitted']
        },
        'bar_force_1w': {
            'series_type': 'Force',
            'quantity_kind': 'qkdv:Force',
            'unit': 'unit:N',
            'legend_name': 'Bar Force (1-wave)',
            'analysis_method': '1-wave',
            'class_uri': 'dyn:ProcessedData',
            'derived_from': ['transmitted']
        },
        'strain_rate_1w': {
            'series_type': 'StrainRate',
            'quantity_kind': 'qkdv:StrainRate',
            'unit': 'unit:PER-SEC',
            'legend_name': 'Strain Rate (1-wave)',
            'analysis_method': '1-wave',
            'class_uri': 'dyn:ProcessedData',
            'derived_from': ['incident']
        },
        'strain_1w': {
            'series_type': 'Strain',
            'quantity_kind': None,  # Unitless
            'unit': None,
            'legend_name': 'Engineering Strain (1-wave)',
            'analysis_method': '1-wave',
            'class_uri': 'dyn:ProcessedData',
            'derived_from': ['incident']
        },
        'stress_1w': {
            'series_type': 'Stress',
            'quantity_kind': 'qkdv:Stress',
            'unit': 'unit:MegaPA',
            'legend_name': 'Engineering Stress (1-wave)',
            'analysis_method': '1-wave',
            'class_uri': 'dyn:ProcessedData',
            'derived_from': ['transmitted']
        },
        'true_strain_rate_1w': {
            'series_type': 'StrainRate',
            'quantity_kind': 'qkdv:StrainRate',
            'unit': 'unit:PER-SEC',
            'legend_name': 'True Strain Rate (1-wave)',
            'analysis_method': '1-wave',
            'class_uri': 'dyn:ProcessedData',
            'derived_from': ['incident']
        },
        'true_strain_1w': {
            'series_type': 'Strain',
            'quantity_kind': None,
            'unit': None,
            'legend_name': 'True Strain (1-wave)',
            'analysis_method': '1-wave',
            'class_uri': 'dyn:ProcessedData',
            'derived_from': ['incident']
        },
        'true_stress_1w': {
            'series_type': 'Stress',
            'quantity_kind': 'qkdv:Stress',
            'unit': 'unit:MegaPA',
            'legend_name': 'True Stress (1-wave)',
            'analysis_method': '1-wave',
            'class_uri': 'dyn:ProcessedData',
            'derived_from': ['transmitted']
        },

        # ===== 3-WAVE PROCESSED DATA =====
        'bar_displacement_3w': {
            'series_type': 'Displacement',
            'quantity_kind': 'qkdv:Length',
            'unit': 'unit:MilliM',
            'legend_name': 'Bar Displacement (3-wave)',
            'analysis_method': '3-wave',
            'class_uri': 'dyn:ProcessedData',
            'derived_from': ['incident', 'transmitted']
        },
        'bar_force_3w': {
            'series_type': 'Force',
            'quantity_kind': 'qkdv:Force',
            'unit': 'unit:N',
            'legend_name': 'Bar Force (3-wave)',
            'analysis_method': '3-wave',
            'class_uri': 'dyn:ProcessedData',
            'derived_from': ['incident', 'transmitted']
        },
        'strain_rate_3w': {
            'series_type': 'StrainRate',
            'quantity_kind': 'qkdv:StrainRate',
            'unit': 'unit:PER-SEC',
            'legend_name': 'Strain Rate (3-wave)',
            'analysis_method': '3-wave',
            'class_uri': 'dyn:ProcessedData',
            'derived_from': ['incident', 'transmitted']
        },
        'strain_3w': {
            'series_type': 'Strain',
            'quantity_kind': None,
            'unit': None,
            'legend_name': 'Engineering Strain (3-wave)',
            'analysis_method': '3-wave',
            'class_uri': 'dyn:ProcessedData',
            'derived_from': ['incident', 'transmitted']
        },
        'stress_3w': {
            'series_type': 'Stress',
            'quantity_kind': 'qkdv:Stress',
            'unit': 'unit:MegaPA',
            'legend_name': 'Engineering Stress (3-wave)',
            'analysis_method': '3-wave',
            'class_uri': 'dyn:ProcessedData',
            'derived_from': ['incident', 'transmitted']
        },
        'true_strain_rate_3w': {
            'series_type': 'StrainRate',
            'quantity_kind': 'qkdv:StrainRate',
            'unit': 'unit:PER-SEC',
            'legend_name': 'True Strain Rate (3-wave)',
            'analysis_method': '3-wave',
            'class_uri': 'dyn:ProcessedData',
            'derived_from': ['incident', 'transmitted']
        },
        'true_strain_3w': {
            'series_type': 'Strain',
            'quantity_kind': None,
            'unit': None,
            'legend_name': 'True Strain (3-wave)',
            'analysis_method': '3-wave',
            'class_uri': 'dyn:ProcessedData',
            'derived_from': ['incident', 'transmitted']
        },
        'true_stress_3w': {
            'series_type': 'Stress',
            'quantity_kind': 'qkdv:Stress',
            'unit': 'unit:MegaPA',
            'legend_name': 'True Stress (3-wave)',
            'analysis_method': '3-wave',
            'class_uri': 'dyn:ProcessedData',
            'derived_from': ['incident', 'transmitted']
        }
    }

    # ==================== CORE IDENTIFICATION ====================
    test_id: str  # Unique test identifier
    specimen_uri: str  # URI of specimen being tested
    test_date: str  # Date in YYYY-MM-DD format
    user: str  # Operator name (converted to dyn:User_X URI)

    # ==================== EQUIPMENT CONFIGURATION ====================
    striker_bar_uri: str  # dyn:StrikerBar_...
    incident_bar_uri: str  # dyn:IncidentBar_...
    transmission_bar_uri: str  # dyn:TransmissionBar_...
    incident_strain_gauge_uri: str  # dyn:StrainGauge_...
    transmission_strain_gauge_uri: str  # dyn:StrainGauge_...
    momentum_trap_uri: Optional[str] = None  # dyn:MomentumTrap_... (optional)
    pulse_shaper_uri: Optional[str] = None  # dyn:PulseShaper_... (optional)

    # ==================== INITIAL TEST CONDITIONS ====================
    # Measurements with units: {'value': X, 'unit': user_unit, 'reference_unit': storage_unit}
    striker_velocity: Optional[Dict[str, Any]] = None  # Impact velocity
    momentum_trap_distance: Optional[Dict[str, Any]] = None  # Distance to trap

    # ==================== PULSE DETECTION - INCIDENT ====================
    incident_pulse_points: Optional[int] = None  # Expected pulse duration in samples
    incident_k_trials: Optional[str] = None  # Comma-separated k values (e.g., "5000,2000,1000")
    incident_polarity: Optional[str] = None  # "compressive" or "tensile"
    incident_min_separation: Optional[int] = None  # Minimum separation between pulses (samples)
    incident_lower_bound: Optional[int] = None  # Search window lower bound (sample index)
    incident_upper_bound: Optional[int] = None  # Search window upper bound (sample index)
    incident_detection_metric: Optional[str] = None  # "median" or "peak"
    incident_window_start: Optional[int] = None  # Detected window start index
    incident_window_end: Optional[int] = None  # Detected window end index
    incident_window_length: Optional[int] = None  # Window length (samples)

    # ==================== PULSE DETECTION - TRANSMITTED ====================
    transmitted_pulse_points: Optional[int] = None
    transmitted_k_trials: Optional[str] = None
    transmitted_polarity: Optional[str] = None
    transmitted_min_separation: Optional[int] = None
    transmitted_lower_bound: Optional[int] = None
    transmitted_upper_bound: Optional[int] = None
    transmitted_detection_metric: Optional[str] = None
    transmitted_window_start: Optional[int] = None
    transmitted_window_end: Optional[int] = None
    transmitted_window_length: Optional[int] = None

    # ==================== PULSE DETECTION - REFLECTED ====================
    reflected_pulse_points: Optional[int] = None
    reflected_k_trials: Optional[str] = None
    reflected_polarity: Optional[str] = None
    reflected_min_separation: Optional[int] = None
    reflected_lower_bound: Optional[int] = None
    reflected_upper_bound: Optional[int] = None
    reflected_detection_metric: Optional[str] = None
    reflected_window_start: Optional[int] = None
    reflected_window_end: Optional[int] = None
    reflected_window_length: Optional[int] = None

    # ==================== SEGMENTATION ====================
    segment_n_points: Optional[int] = None  # n_pts for centered segment
    segment_thresh_ratio: Optional[float] = None  # Noise suppression threshold (0.0-1.0)
    incident_centering_shift: Optional[int] = None  # Shift during segment_and_center (samples)
    transmitted_centering_shift: Optional[int] = None
    reflected_centering_shift: Optional[int] = None

    # ==================== ALIGNMENT CONFIGURATION ====================
    k_linear: Optional[float] = None  # Linear region fraction (e.g., 0.35)
    alignment_weight_corr: Optional[float] = None  # Correlation weight in fitness function
    alignment_weight_u: Optional[float] = None  # Displacement weight
    alignment_weight_sr: Optional[float] = None  # Strain rate weight
    alignment_weight_e: Optional[float] = None  # Strain weight
    search_bounds_t_min: Optional[int] = None  # Transmitted shift search min (samples)
    search_bounds_t_max: Optional[int] = None  # Transmitted shift search max (samples)
    search_bounds_r_min: Optional[int] = None  # Reflected shift search min (samples)
    search_bounds_r_max: Optional[int] = None  # Reflected shift search max (samples)

    # ==================== ALIGNMENT RESULTS ====================
    shift_transmitted: Optional[int] = None  # Applied transmitted shift (samples)
    shift_reflected: Optional[int] = None  # Applied reflected shift (samples)
    alignment_front_idx: Optional[int] = None  # Front face index after alignment
    linear_region_start: Optional[int] = None  # Start of linear region (sample index)
    linear_region_end: Optional[int] = None  # End of linear region (sample index)

    # ==================== EQUILIBRIUM METRICS ====================
    fbc: Optional[float] = None  # Force Balance Coefficient (0-1)
    seqi: Optional[float] = None  # Stress Equilibrium Index
    soi: Optional[float] = None  # Strain Offset Index
    dsuf: Optional[float] = None  # Dynamic Stress Uniformity Factor
    fbc_loading: Optional[float] = None  # FBC during loading phase
    dsuf_loading: Optional[float] = None  # DSUF during loading phase
    fbc_plateau: Optional[float] = None  # FBC during plateau phase
    dsuf_plateau: Optional[float] = None  # DSUF during plateau phase
    fbc_unloading: Optional[float] = None  # FBC during unloading phase
    dsuf_unloading: Optional[float] = None  # DSUF during unloading phase

    # ==================== TUKEY WINDOW ====================
    tukey_alpha: Optional[float] = None  # Tukey window alpha parameter (0.0-1.0)

    # ==================== CALCULATED CHARACTERISTICS ====================
    # Measurements with units
    pulse_duration: Optional[Dict[str, Any]] = None  # Pulse duration
    pulse_length: Optional[Dict[str, Any]] = None  # Physical pulse length
    pulse_stress_amplitude: Optional[Dict[str, Any]] = None  # Stress amplitude
    pulse_strain_amplitude: Optional[float] = None  # Strain amplitude (unitless)
    incident_rise_time: Optional[Dict[str, Any]] = None  # Rise time

    # ==================== ANALYSIS METADATA ====================
    analysis_timestamp: Optional[str] = None  # ISO datetime of analysis
    sampling_interval: Optional[Dict[str, Any]] = None  # Time between samples

    # ==================== DATA FILE REFERENCES ====================
    raw_data_file_uri: Optional[str] = None  # URI of AnalysisFile instance for raw CSV
    processed_data_file_uri: Optional[str] = None  # URI of processed data file (future)

    # ==================== DATA SERIES REFERENCES ====================
    # URIs created during ingestion
    data_series_time_uri: Optional[str] = None  # dyn:TEST_001_time
    data_series_incident_uri: Optional[str] = None  # dyn:TEST_001_incident
    data_series_transmitted_uri: Optional[str] = None  # dyn:TEST_001_transmitted

    # ==================== PROCESSING OBJECT REFERENCES ====================
    # URIs of processing instances created during ingestion
    incident_window_uri: Optional[str] = None  # dyn:TEST_001_incident_window
    transmitted_window_uri: Optional[str] = None  # dyn:TEST_001_transmitted_window
    reflected_window_uri: Optional[str] = None  # dyn:TEST_001_reflected_window
    transmitted_shift_uri: Optional[str] = None  # dyn:TEST_001_transmitted_shift
    reflected_shift_uri: Optional[str] = None  # dyn:TEST_001_reflected_shift
    incident_detection_params_uri: Optional[str] = None  # dyn:TEST_001_incident_detect
    transmitted_detection_params_uri: Optional[str] = None  # dyn:TEST_001_transmitted_detect
    reflected_detection_params_uri: Optional[str] = None  # dyn:TEST_001_reflected_detect
    alignment_params_uri: Optional[str] = None  # dyn:TEST_001_alignment
    equilibrium_metrics_uri: Optional[str] = None  # dyn:TEST_001_equilibrium

    def extract_bar_properties(self, specimen_loader, bar_type: str) -> Dict[str, Any]:
        """
        Extract bar properties from ontology including material characteristics.

        Args:
            specimen_loader: SpecimenLoader instance with loaded ontology
            bar_type: 'striker', 'incident', or 'transmission'

        Returns:
            Dictionary with bar properties:
            {
                'uri': 'dyn:IncidentBar_C350_6ft',
                'length': 1828.8,          # mm
                'diameter': 19.05,         # mm
                'cross_section': 285.024,  # mm²
                'material_uri': 'dyn:C530_Maraging',
                'wave_speed': 5000.0,      # m/s
                'elastic_modulus': None    # GPa (if available)
            }

        Example:
            >>> striker_props = metadata.extract_bar_properties(specimen_loader, 'striker')
            >>> print(f"Wave speed: {striker_props['wave_speed']} m/s")
            >>> print(f"Cross-section: {striker_props['cross_section']} mm²")
        """
        # Map bar type to URI attribute
        bar_uri_map = {
            'striker': self.striker_bar_uri,
            'incident': self.incident_bar_uri,
            'transmission': self.transmission_bar_uri
        }

        if bar_type not in bar_uri_map:
            raise ValueError(f"Invalid bar_type '{bar_type}'. Must be 'striker', 'incident', or 'transmission'")

        bar_uri = bar_uri_map[bar_type]

        # Extract bar properties
        bar_props = specimen_loader.get_multiple_properties(
            bar_uri,
            ['hasLength', 'hasDiameter', 'hasCrossSection', 'hasMaterial']
        )

        # Extract material properties
        material_uri = bar_props.get('hasMaterial')
        wave_speed = None
        elastic_modulus = None
        density = None

        if material_uri:
            material_props = specimen_loader.get_multiple_properties(
                material_uri,
                ['hasWaveSpeed', 'hasElasticModulus', 'hasDensity']
            )
            wave_speed = material_props.get('hasWaveSpeed', None)
            elastic_modulus = material_props.get('hasElasticModulus', None)
            density = material_props.get('hasDensity', None)

        result = {
            'uri': bar_uri,
            'length': bar_props.get('hasLength'),
            'diameter': bar_props.get('hasDiameter'),
            'cross_section': bar_props.get('hasCrossSection'),
            'material_uri': material_uri,
            'wave_speed': wave_speed,
            'elastic_modulus': elastic_modulus,
            'density': density
        }

        logger.debug(f"Extracted {bar_type} bar properties: {result}")
        return result

    def extract_gauge_properties(self, specimen_loader, gauge_type: str) -> Dict[str, Any]:
        """
        Extract strain gauge properties from ontology.

        Args:
            specimen_loader: SpecimenLoader instance with loaded ontology
            gauge_type: 'incident' or 'transmission'

        Returns:
            Dictionary with gauge properties:
            {
                'uri': 'dyn:StrainGauge_INC_SG1',
                'gauge_factor': 2.12,
                'gauge_resistance': 350.0,    # Ω
                'distance_from_specimen': None  # mm (if defined on gauge)
            }

        Example:
            >>> incident_gauge = metadata.extract_gauge_properties(specimen_loader, 'incident')
            >>> print(f"Gauge factor: {incident_gauge['gauge_factor']}")
            >>> print(f"Resistance: {incident_gauge['gauge_resistance']} Ω")
        """
        # Map gauge type to URI attribute
        gauge_uri_map = {
            'incident': self.incident_strain_gauge_uri,
            'transmission': self.transmission_strain_gauge_uri
        }

        if gauge_type not in gauge_uri_map:
            raise ValueError(f"Invalid gauge_type '{gauge_type}'. Must be 'incident' or 'transmission'")

        gauge_uri = gauge_uri_map[gauge_type]

        # Extract gauge properties
        gauge_props = specimen_loader.get_multiple_properties(
            gauge_uri,
            ['hasGaugeFactor', 'hasGaugeResistance', 'hasCalibrationVoltage',
             'hasCalibrationResistance', 'hasDistanceFromSpecimen']
        )

        result = {
            'uri': gauge_uri,
            'gauge_factor': gauge_props.get('hasGaugeFactor'),
            'gauge_resistance': gauge_props.get('hasGaugeResistance'),
            'calibration_voltage': gauge_props.get('hasCalibrationVoltage'),
            'calibration_resistance': gauge_props.get('hasCalibrationResistance'),
            'distance_from_specimen': gauge_props.get('hasDistanceFromSpecimen')
        }

        logger.debug(f"Extracted {gauge_type} gauge properties: {result}")
        return result

    def extract_all_equipment_properties(self, specimen_loader) -> Dict[str, Any]:
        """
        Extract all equipment properties in one call.

        Args:
            specimen_loader: SpecimenLoader instance with loaded ontology

        Returns:
            Dictionary with all equipment properties:
            {
                'striker_bar': {...},
                'incident_bar': {...},
                'transmission_bar': {...},
                'incident_gauge': {...},
                'transmission_gauge': {...}
            }

        Example:
            >>> equipment = metadata.extract_all_equipment_properties(specimen_loader)
            >>> bar_cross_section = equipment['incident_bar']['cross_section']
            >>> bar_wave_speed = equipment['incident_bar']['wave_speed']
            >>> gauge_factor = equipment['incident_gauge']['gauge_factor']
        """
        equipment = {
            'striker_bar': self.extract_bar_properties(specimen_loader, 'striker'),
            'incident_bar': self.extract_bar_properties(specimen_loader, 'incident'),
            'transmission_bar': self.extract_bar_properties(specimen_loader, 'transmission'),
            'incident_gauge': self.extract_gauge_properties(specimen_loader, 'incident'),
            'transmission_gauge': self.extract_gauge_properties(specimen_loader, 'transmission')
        }

        logger.info(f"Extracted all equipment properties for test {self.test_id}")
        return equipment

    def to_form_data(self) -> Dict[str, Any]:
        """
        Convert all metadata fields to form data dictionary for InstanceWriter.

        Maps field names → RDF property URIs, following widget factory format.
        Only includes non-None values (skips optional fields that weren't set).

        Returns:
            Dict with property URIs as keys, values in widget format:
            {
                'dyn:hasTestID': 'TEST_001',
                'dyn:hasStrikerVelocity': {'value': 10.0, 'unit': '...', 'reference_unit': '...'},
                'dyn:hasIncidentBar': 'dyn:IncidentBar_...',
                ...
            }

        Example:
            >>> form_data = metadata.to_form_data()
            >>> # Pass directly to InstanceWriter
            >>> writer.write_instance(form_data, 'dyn:SHPBCompression', test_id, output_path)
        """
        # Build comprehensive field → property URI mapping
        field_mapping = {
            # Core identification
            'test_id': 'dyn:hasTestID',
            'specimen_uri': 'dyn:performedOn',
            'test_date': 'dyn:hasTestDate',
            'user': 'dyn:hasUser',  # Will be converted to User URI below

            # Equipment configuration
            'striker_bar_uri': 'dyn:hasStrikerBar',
            'incident_bar_uri': 'dyn:hasIncidentBar',
            'transmission_bar_uri': 'dyn:hasTransmissionBar',
            'momentum_trap_uri': 'dyn:hasMomentumTrap',
            'pulse_shaper_uri': 'dyn:hasPulseShaper',
            # Note: strain gauges handled separately as multi-valued property

            # Initial test conditions
            'striker_velocity': 'dyn:hasStrikerVelocity',
            'momentum_trap_distance': 'dyn:hasMomentumTrapTailoredDistance',

            # Pulse detection - incident
            'incident_pulse_points': 'dyn:hasPulsePoints',
            'incident_k_trials': 'dyn:hasKTrials',
            'incident_polarity': 'dyn:hasDetectionPolarity',
            'incident_min_separation': 'dyn:hasMinSeparation',
            'incident_lower_bound': 'dyn:hasDetectionLowerBound',
            'incident_upper_bound': 'dyn:hasDetectionUpperBound',
            'incident_detection_metric': 'dyn:hasSelectionMetric',

            # Pulse detection - transmitted
            'transmitted_pulse_points': 'dyn:hasPulsePoints',
            'transmitted_k_trials': 'dyn:hasKTrials',
            'transmitted_polarity': 'dyn:hasDetectionPolarity',
            'transmitted_min_separation': 'dyn:hasMinSeparation',
            'transmitted_lower_bound': 'dyn:hasDetectionLowerBound',
            'transmitted_upper_bound': 'dyn:hasDetectionUpperBound',
            'transmitted_detection_metric': 'dyn:hasSelectionMetric',

            # Pulse detection - reflected
            'reflected_pulse_points': 'dyn:hasPulsePoints',
            'reflected_k_trials': 'dyn:hasKTrials',
            'reflected_polarity': 'dyn:hasDetectionPolarity',
            'reflected_min_separation': 'dyn:hasMinSeparation',
            'reflected_lower_bound': 'dyn:hasDetectionLowerBound',
            'reflected_upper_bound': 'dyn:hasDetectionUpperBound',
            'reflected_detection_metric': 'dyn:hasSelectionMetric',

            # Detected windows (stored as references to PulseWindow instances)
            'incident_window_uri': 'dyn:hasDetectedWindow',
            'transmitted_window_uri': 'dyn:hasDetectedWindow',
            'reflected_window_uri': 'dyn:hasDetectedWindow',

            # Segmentation
            'segment_n_points': 'dyn:hasCenteredSegmentPoints',
            'segment_thresh_ratio': 'dyn:hasThresholdRatio',

            # Pulse shifts (stored as references to PulseShift instances)
            'transmitted_shift_uri': 'dyn:hasAppliedShift',
            'reflected_shift_uri': 'dyn:hasAppliedShift',

            # Alignment configuration (reference to AlignmentParams instance)
            'alignment_params_uri': 'dyn:hasAlignmentParams',
            'k_linear': 'dyn:hasKLinear',

            # Alignment results
            'shift_transmitted': 'dyn:hasShiftValue',
            'shift_reflected': 'dyn:hasShiftValue',
            'alignment_front_idx': 'dyn:hasFrontIndex',
            'linear_region_start': 'dyn:hasLinearRegionStart',
            'linear_region_end': 'dyn:hasLinearRegionEnd',

            # Processing parameters (references to instances)
            'incident_detection_params_uri': 'dyn:hasPulseDetectionParams',
            'transmitted_detection_params_uri': 'dyn:hasPulseDetectionParams',
            'reflected_detection_params_uri': 'dyn:hasPulseDetectionParams',

            # Equilibrium metrics (reference to instance)
            'equilibrium_metrics_uri': 'dyn:hasEquilibriumMetrics',
            'fbc': 'dyn:hasFBC',
            'seqi': 'dyn:hasSEQI',
            'soi': 'dyn:hasSOI',
            'dsuf': 'dyn:hasDSUF',

            # Tukey window
            'tukey_alpha': 'dyn:hasTukeyAlpha',

            # Calculated characteristics
            'pulse_duration': 'dyn:hasPulseDuration',
            'pulse_length': 'dyn:hasPulseLength',
            'pulse_stress_amplitude': 'dyn:hasPulseStressAmplitude',
            'pulse_strain_amplitude': 'dyn:hasPulseStrainAmplitude',
            'incident_rise_time': 'dyn:hasPulseRiseTime',

            # Analysis metadata
            'analysis_timestamp': 'dyn:hasAnalysisTimestamp',
            'sampling_interval': 'dyn:hasSamplingInterval',

            # Data file references
            'raw_data_file_uri': 'dyn:hasRawDataFile',
            'processed_data_file_uri': 'dyn:hasProcessedDataFile',

            # Data series references
            'data_series_time_uri': 'dyn:hasDataSeries',
            'data_series_incident_uri': 'dyn:hasDataSeries',
            'data_series_transmitted_uri': 'dyn:hasDataSeries',
        }

        form_data = {}

        # Process all fields using mapping
        for field_name, property_uri in field_mapping.items():
            value = getattr(self, field_name, None)
            if value is not None:
                # Special handling for user field (convert to User URI)
                if field_name == 'user':
                    if value.startswith('dyn:User_'):
                        form_data[property_uri] = value
                    else:
                        form_data[property_uri] = f"dyn:User_{value}"
                else:
                    form_data[property_uri] = value

        # Handle strain gauges as multi-valued property
        gauges = []
        if self.incident_strain_gauge_uri:
            gauges.append(self.incident_strain_gauge_uri)
        if self.transmission_strain_gauge_uri:
            gauges.append(self.transmission_strain_gauge_uri)
        if gauges:
            form_data['dyn:hasStrainGauge'] = gauges

        logger.debug(f"Created form_data with {len(form_data)} properties")
        return form_data

    def get_processing_instances(self) -> Dict[str, List[tuple]]:
        """
        Extract all processing object instances for batch creation.

        Returns instances grouped by type:
        - windows: PulseWindow instances (incident, transmitted, reflected)
        - shifts: PulseShift instances (transmitted, reflected)
        - detection_params: PulseDetectionParams instances (incident, transmitted, reflected)
        - alignment_params: AlignmentParams instance
        - equilibrium_metrics: EquilibriumMetrics instance

        Returns:
            Dict with instance type as key, list of (form_data, class_uri, instance_id) tuples as value

        Example:
            >>> processing_instances = metadata.get_processing_instances()
            >>> windows = processing_instances['windows']
            >>> # Pass to InstanceWriter.create_instances_batch()
        """
        instances = {
            'windows': [],
            'shifts': [],
            'detection_params': [],
            'alignment_params': [],
            'equilibrium_metrics': []
        }

        # ===== PULSE WINDOWS =====
        if self.incident_window_uri and self.incident_window_start is not None:
            incident_window_form = {
                'dyn:hasStartIndex': self.incident_window_start,
                'dyn:hasEndIndex': self.incident_window_end,
                'dyn:hasWindowLength': self.incident_window_length,
                'dyn:appliedToSeries': self.data_series_incident_uri
            }
            instance_id = self.incident_window_uri.replace('dyn:', '')
            instances['windows'].append((incident_window_form, 'dyn:PulseWindow', instance_id))

        if self.transmitted_window_uri and self.transmitted_window_start is not None:
            transmitted_window_form = {
                'dyn:hasStartIndex': self.transmitted_window_start,
                'dyn:hasEndIndex': self.transmitted_window_end,
                'dyn:hasWindowLength': self.transmitted_window_length,
                'dyn:appliedToSeries': self.data_series_transmitted_uri
            }
            instance_id = self.transmitted_window_uri.replace('dyn:', '')
            instances['windows'].append((transmitted_window_form, 'dyn:PulseWindow', instance_id))

        if self.reflected_window_uri and self.reflected_window_start is not None:
            reflected_window_form = {
                'dyn:hasStartIndex': self.reflected_window_start,
                'dyn:hasEndIndex': self.reflected_window_end,
                'dyn:hasWindowLength': self.reflected_window_length,
                'dyn:appliedToSeries': self.data_series_incident_uri  # Reflected is on incident bar
            }
            instance_id = self.reflected_window_uri.replace('dyn:', '')
            instances['windows'].append((reflected_window_form, 'dyn:PulseWindow', instance_id))

        # ===== PULSE SHIFTS =====
        if self.transmitted_shift_uri and self.shift_transmitted is not None:
            transmitted_shift_form = {
                'dyn:hasShiftValue': self.shift_transmitted,
                'dyn:appliedToSeries': self.data_series_transmitted_uri
            }
            instance_id = self.transmitted_shift_uri.replace('dyn:', '')
            instances['shifts'].append((transmitted_shift_form, 'dyn:PulseShift', instance_id))

        if self.reflected_shift_uri and self.shift_reflected is not None:
            reflected_shift_form = {
                'dyn:hasShiftValue': self.shift_reflected,
                'dyn:appliedToSeries': self.data_series_incident_uri  # Reflected is on incident bar
            }
            instance_id = self.reflected_shift_uri.replace('dyn:', '')
            instances['shifts'].append((reflected_shift_form, 'dyn:PulseShift', instance_id))

        # ===== PULSE DETECTION PARAMS =====
        if self.incident_detection_params_uri and self.incident_pulse_points is not None:
            incident_detect_form = {
                'dyn:hasPulsePoints': self.incident_pulse_points,
                'dyn:hasKTrials': self.incident_k_trials,
                'dyn:hasDetectionPolarity': self.incident_polarity,
                'dyn:hasMinSeparation': self.incident_min_separation,
                'dyn:hasDetectionLowerBound': self.incident_lower_bound,
                'dyn:hasDetectionUpperBound': self.incident_upper_bound,
                'dyn:hasSelectionMetric': self.incident_detection_metric,
                'dyn:appliedToSeries': self.data_series_incident_uri
            }
            instance_id = self.incident_detection_params_uri.replace('dyn:', '')
            instances['detection_params'].append((incident_detect_form, 'dyn:PulseDetectionParams', instance_id))

        if self.transmitted_detection_params_uri and self.transmitted_pulse_points is not None:
            transmitted_detect_form = {
                'dyn:hasPulsePoints': self.transmitted_pulse_points,
                'dyn:hasKTrials': self.transmitted_k_trials,
                'dyn:hasDetectionPolarity': self.transmitted_polarity,
                'dyn:hasMinSeparation': self.transmitted_min_separation,
                'dyn:hasDetectionLowerBound': self.transmitted_lower_bound,
                'dyn:hasDetectionUpperBound': self.transmitted_upper_bound,
                'dyn:hasSelectionMetric': self.transmitted_detection_metric,
                'dyn:appliedToSeries': self.data_series_transmitted_uri
            }
            instance_id = self.transmitted_detection_params_uri.replace('dyn:', '')
            instances['detection_params'].append((transmitted_detect_form, 'dyn:PulseDetectionParams', instance_id))

        if self.reflected_detection_params_uri and self.reflected_pulse_points is not None:
            reflected_detect_form = {
                'dyn:hasPulsePoints': self.reflected_pulse_points,
                'dyn:hasKTrials': self.reflected_k_trials,
                'dyn:hasDetectionPolarity': self.reflected_polarity,
                'dyn:hasMinSeparation': self.reflected_min_separation,
                'dyn:hasDetectionLowerBound': self.reflected_lower_bound,
                'dyn:hasDetectionUpperBound': self.reflected_upper_bound,
                'dyn:hasSelectionMetric': self.reflected_detection_metric,
                'dyn:appliedToSeries': self.data_series_incident_uri  # Reflected is on incident bar
            }
            instance_id = self.reflected_detection_params_uri.replace('dyn:', '')
            instances['detection_params'].append((reflected_detect_form, 'dyn:PulseDetectionParams', instance_id))

        # ===== ALIGNMENT PARAMS =====
        if self.alignment_params_uri and self.k_linear is not None:
            alignment_form = {
                'dyn:hasKLinear': self.k_linear,
                'dyn:hasCorrelationWeight': self.alignment_weight_corr,
                'dyn:hasDisplacementWeight': self.alignment_weight_u,
                'dyn:hasStrainRateWeight': self.alignment_weight_sr,
                'dyn:hasStrainWeight': self.alignment_weight_e,
                'dyn:hasTransmittedSearchMin': self.search_bounds_t_min,
                'dyn:hasTransmittedSearchMax': self.search_bounds_t_max,
                'dyn:hasReflectedSearchMin': self.search_bounds_r_min,
                'dyn:hasReflectedSearchMax': self.search_bounds_r_max,
            }
            instance_id = self.alignment_params_uri.replace('dyn:', '')
            instances['alignment_params'].append((alignment_form, 'dyn:AlignmentParams', instance_id))

        # ===== EQUILIBRIUM METRICS =====
        if self.equilibrium_metrics_uri and self.fbc is not None:
            equilibrium_form = {
                'dyn:hasFBC': self.fbc,
                'dyn:hasSEQI': self.seqi,
                'dyn:hasSOI': self.soi,
                'dyn:hasDSUF': self.dsuf,
                'dyn:hasFBCLoading': self.fbc_loading,
                'dyn:hasDSUFLoading': self.dsuf_loading,
                'dyn:hasFBCPlateau': self.fbc_plateau,
                'dyn:hasDSUFPlateau': self.dsuf_plateau,
                'dyn:hasFBCUnloading': self.fbc_unloading,
                'dyn:hasDSUFUnloading': self.dsuf_unloading,
            }
            instance_id = self.equilibrium_metrics_uri.replace('dyn:', '')
            instances['equilibrium_metrics'].append((equilibrium_form, 'dyn:EquilibriumMetrics', instance_id))

        total_instances = sum(len(v) for v in instances.values())
        logger.debug(f"Extracted {total_instances} processing instances")
        return instances

    def prepare_raw_data_series(
        self,
        raw_df: pd.DataFrame,
        file_uri: str,
        gauge_params: Dict[str, str]
    ) -> List[Tuple[Dict[str, Any], str, str]]:
        """
        Convert raw DataFrame columns to DataSeries instances.

        Creates 3 RawSignal instances (time, incident, transmitted) with full metadata:
        - Column name and index
        - QUDT unit and quantity kind
        - Equipment reference (measuredBy)
        - Data point count
        - Processing metadata (Tukey, alignment flags)

        Args:
            raw_df: DataFrame with columns ['time', 'incident', 'transmitted']
            file_uri: URI of the AnalysisFile instance (e.g., 'dyn:TEST_001_raw_csv')
            gauge_params: Dict mapping column names to equipment URIs:
                {
                    'incident': 'dyn:StrainGauge_SHPB_001',
                    'transmitted': 'dyn:StrainGauge_SHPB_002'
                }

        Returns:
            List of (form_data, class_uri, instance_id) tuples for InstanceWriter.
            Each tuple represents one DataSeries instance.

        Example:
            >>> gauge_params = {
            ...     'incident': metadata.incident_strain_gauge_uri,
            ...     'transmitted': metadata.transmission_strain_gauge_uri
            ... }
            >>> raw_series = metadata.prepare_raw_data_series(
            ...     raw_df, 'dyn:TEST_001_raw_csv', gauge_params
            ... )
            >>> # Returns 3 instances: time, incident, transmitted
        """
        instances = []
        data_point_count = len(raw_df)

        for column_name in ['time', 'incident', 'transmitted']:
            # Get metadata from lookup table
            metadata = self.SERIES_METADATA[column_name]

            # Build form data
            form_data = {
                # File reference
                'dyn:hasDataFile': file_uri,
                'dyn:hasColumnName': column_name,
                'dyn:hasColumnIndex': raw_df.columns.get_loc(column_name),
                'dyn:hasLegendName': metadata['legend_name'],

                # Series metadata
                'dyn:hasSeriesType': metadata['series_type'],
                'dyn:hasDataPointCount': data_point_count,
            }

            # Add unit and quantity kind if specified
            if metadata['unit']:
                form_data['dyn:hasSeriesUnit'] = metadata['unit']
            if metadata['quantity_kind']:
                form_data['dyn:hasQuantityKind'] = metadata['quantity_kind']

            # Add equipment reference for signals that require it
            if metadata.get('requires_gauge', False) and column_name in gauge_params:
                form_data['dyn:measuredBy'] = gauge_params[column_name]

            # Add processing metadata from test metadata
            if self.tukey_alpha is not None:
                form_data['dyn:hasTukeyAlpha'] = self.tukey_alpha

            if self.sampling_interval is not None:
                form_data['dyn:hasSamplingInterval'] = self.sampling_interval

            # Add window/shift references if created
            if column_name == 'incident' and self.incident_window_uri:
                form_data['dyn:hasDetectedWindow'] = self.incident_window_uri
            elif column_name == 'transmitted' and self.transmitted_window_uri:
                form_data['dyn:hasDetectedWindow'] = self.transmitted_window_uri

            # Create instance tuple
            instance_id = f"{self.test_id.replace('-', '_')}_{column_name}"
            instances.append((form_data, metadata['class_uri'], instance_id))

            logger.debug(f"Prepared {column_name} DataSeries: {instance_id}")

        logger.info(f"Prepared {len(instances)} raw DataSeries instances")
        return instances

    def prepare_processed_data_series(
        self,
        results: Dict[str, np.ndarray],
        file_uri: str,
        raw_series_uris: Dict[str, str]
    ) -> List[Tuple[Dict[str, Any], str, str]]:
        """
        Convert processed results dictionary to DataSeries instances.

        Creates 17 ProcessedData instances (1 time + 16 calculated quantities) with:
        - Analysis method (1-wave, 3-wave)
        - Derivation chain (derivedFrom links to raw signals)
        - QUDT units and quantity kinds
        - Processing method

        Args:
            results: Dictionary from StressStrainCalculator.calculate() with keys:
                - 'time' (ms)
                - '1-wave': bar_displacement_1w, bar_force_1w, strain_rate_1w,
                           strain_1w, stress_1w, true_strain_rate_1w,
                           true_strain_1w, true_stress_1w
                - '3-wave': bar_displacement_3w, bar_force_3w, strain_rate_3w,
                           strain_3w, stress_3w, true_strain_rate_3w,
                           true_strain_3w, true_stress_3w
            file_uri: URI of processed data AnalysisFile
            raw_series_uris: URIs of raw DataSeries for derivation chain:
                {
                    'time': 'dyn:TEST_001_time',
                    'incident': 'dyn:TEST_001_incident',
                    'transmitted': 'dyn:TEST_001_transmitted'
                }

        Returns:
            List of (form_data, class_uri, instance_id) tuples.
            Returns 17 instances (1 time + 16 processed quantities).

        Example:
            >>> calculator = StressStrainCalculator(...)
            >>> results = calculator.calculate(inc, trs, ref, time)
            >>> raw_uris = {
            ...     'time': 'dyn:TEST_001_time',
            ...     'incident': 'dyn:TEST_001_incident',
            ...     'transmitted': 'dyn:TEST_001_transmitted'
            ... }
            >>> processed_series = metadata.prepare_processed_data_series(
            ...     results, 'dyn:TEST_001_processed_csv', raw_uris
            ... )
        """
        instances = []

        # Create temporary DataFrame to get column indices
        processed_df = pd.DataFrame(results)
        data_point_count = len(processed_df)

        for column_name in results.keys():
            # Skip if not in metadata (shouldn't happen)
            if column_name not in self.SERIES_METADATA:
                logger.warning(f"Column '{column_name}' not in SERIES_METADATA, skipping")
                continue

            # Get metadata from lookup table
            metadata = self.SERIES_METADATA[column_name]

            # Build form data
            form_data = {
                # File reference
                'dyn:hasDataFile': file_uri,
                'dyn:hasColumnName': column_name,
                'dyn:hasColumnIndex': processed_df.columns.get_loc(column_name),
                'dyn:hasLegendName': metadata['legend_name'],

                # Series metadata
                'dyn:hasSeriesType': metadata['series_type'],
                'dyn:hasDataPointCount': data_point_count,

                # Processing info
                'dyn:hasProcessingMethod': 'SHPB stress-strain calculation',
                'dyn:hasFilterApplied': False,
            }

            # Add unit and quantity kind if specified
            if metadata['unit']:
                form_data['dyn:hasSeriesUnit'] = metadata['unit']
            if metadata['quantity_kind']:
                form_data['dyn:hasQuantityKind'] = metadata['quantity_kind']

            # Add analysis method for processed data
            if 'analysis_method' in metadata:
                form_data['dyn:hasAnalysisMethod'] = metadata['analysis_method']

            # Add derivation chain (link to source raw signals)
            if 'derived_from' in metadata:
                # For now, link to first source (typically transmitted or incident)
                # Future: could link to multiple sources
                source_column = metadata['derived_from'][0]
                if source_column in raw_series_uris:
                    form_data['dyn:derivedFrom'] = raw_series_uris[source_column]

            # Create instance tuple
            instance_id = f"{self.test_id.replace('-', '_')}_{column_name}"
            instances.append((form_data, metadata['class_uri'], instance_id))

            logger.debug(f"Prepared {column_name} DataSeries: {instance_id}")

        logger.info(f"Prepared {len(instances)} processed DataSeries instances")
        return instances

    def validate(self):
        """
        Validate required fields.

        Raises:
            ValueError: If any required field is missing or invalid

        Example:
            >>> metadata = SHPBTestMetadata(...)
            >>> metadata.validate()
        """
        # Check required fields are not empty
        required_fields = [
            ('test_id', self.test_id),
            ('specimen_uri', self.specimen_uri),
            ('test_date', self.test_date),
            ('user', self.user),
            ('striker_bar_uri', self.striker_bar_uri),
            ('incident_bar_uri', self.incident_bar_uri),
            ('transmission_bar_uri', self.transmission_bar_uri),
            ('incident_strain_gauge_uri', self.incident_strain_gauge_uri),
            ('transmission_strain_gauge_uri', self.transmission_strain_gauge_uri),
        ]

        for field_name, value in required_fields:
            if not value:
                raise ValueError(f"Required field '{field_name}' is missing or empty")

        # Validate date format
        try:
            datetime.strptime(self.test_date, "%Y-%m-%d")
        except ValueError:
            raise ValueError(f"test_date must be in YYYY-MM-DD format, got: {self.test_date}")

        # Validate URIs
        uri_fields = [
            ('specimen_uri', self.specimen_uri),
            ('striker_bar_uri', self.striker_bar_uri),
            ('incident_bar_uri', self.incident_bar_uri),
            ('transmission_bar_uri', self.transmission_bar_uri),
            ('incident_strain_gauge_uri', self.incident_strain_gauge_uri),
            ('transmission_strain_gauge_uri', self.transmission_strain_gauge_uri),
        ]

        for field_name, uri in uri_fields:
            if not (uri.startswith('dyn:') or uri.startswith('http')):
                raise ValueError(f"{field_name} must be a valid URI (dyn: or http), got: {uri}")

        # Validate optional URIs if provided
        optional_uri_fields = [
            ('momentum_trap_uri', self.momentum_trap_uri),
            ('pulse_shaper_uri', self.pulse_shaper_uri),
        ]

        for field_name, uri in optional_uri_fields:
            if uri and not (uri.startswith('dyn:') or uri.startswith('http')):
                raise ValueError(f"{field_name} must be a valid URI (dyn: or http), got: {uri}")

        # Validate test conditions if provided
        if self.striker_velocity is not None:
            if self.striker_velocity <= 0:
                raise ValueError(f"striker_velocity must be positive, got: {self.striker_velocity}")

        if self.momentum_trap_distance is not None:
            if self.momentum_trap_distance <= 0:
                raise ValueError(f"momentum_trap_distance must be positive, got: {self.momentum_trap_distance}")

        logger.info(f"SHPBTestMetadata validation passed for test_id: {self.test_id}")
