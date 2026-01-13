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
from typing import Dict, Any, Optional, List, Tuple, Union
import logging
from datetime import datetime
import pandas as pd
import numpy as np
from rdflib import Literal
from rdflib.namespace import XSD

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
            'series_type': 'dyn:Time',
            'quantity_kind': 'qkdv:Time',
            'unit': 'unit:MilliSEC',
            'legend_name': 'Time',
            'class_uri': 'dyn:RawSignal'
        },
        'incident': {
            'series_type': 'dyn:IncidentPulse',
            'quantity_kind': 'qkdv:Voltage',
            'unit': 'unit:V',
            'legend_name': 'Incident Pulse',
            'class_uri': 'dyn:RawSignal',
            'requires_gauge': True
        },
        'transmitted': {
            'series_type': 'dyn:TransmittedPulse',
            'quantity_kind': 'qkdv:Voltage',
            'unit': 'unit:V',
            'legend_name': 'Transmitted Pulse',
            'class_uri': 'dyn:RawSignal',
            'requires_gauge': True
        },

        # ===== 1-WAVE PROCESSED DATA =====
        'bar_displacement_1w': {
            'series_type': 'dyn:BarDisplacement',
            'quantity_kind': 'qkdv:Length',
            'unit': 'unit:MilliM',
            'legend_name': 'Bar Displacement (1-wave)',
            'analysis_method': '1-wave',
            'class_uri': 'dyn:ProcessedData',
            'derived_from': ['transmitted']
        },
        'bar_force_1w': {
            'series_type': 'dyn:BarForce',
            'quantity_kind': 'qkdv:Force',
            'unit': 'unit:N',
            'legend_name': 'Bar Force (1-wave)',
            'analysis_method': '1-wave',
            'class_uri': 'dyn:ProcessedData',
            'derived_from': ['transmitted']
        },
        'strain_rate_1w': {
            'series_type': 'dyn:StrainRate',
            'quantity_kind': 'qkdv:StrainRate',
            'unit': 'unit:PER-SEC',
            'legend_name': 'Strain Rate (1-wave)',
            'analysis_method': '1-wave',
            'class_uri': 'dyn:ProcessedData',
            'derived_from': ['incident']
        },
        'strain_1w': {
            'series_type': 'dyn:Strain',
            'quantity_kind': 'qkdv:Dimensionless',
            'unit': 'unit:UNITLESS',
            'legend_name': 'Engineering Strain (1-wave)',
            'analysis_method': '1-wave',
            'class_uri': 'dyn:ProcessedData',
            'derived_from': ['incident']
        },
        'stress_1w': {
            'series_type': 'dyn:Stress',
            'quantity_kind': 'qkdv:Stress',
            'unit': 'unit:MegaPA',
            'legend_name': 'Engineering Stress (1-wave)',
            'analysis_method': '1-wave',
            'class_uri': 'dyn:ProcessedData',
            'derived_from': ['transmitted']
        },
        'true_strain_rate_1w': {
            'series_type': 'dyn:TrueStrainRate',
            'quantity_kind': 'qkdv:StrainRate',
            'unit': 'unit:PER-SEC',
            'legend_name': 'True Strain Rate (1-wave)',
            'analysis_method': '1-wave',
            'class_uri': 'dyn:ProcessedData',
            'derived_from': ['incident']
        },
        'true_strain_1w': {
            'series_type': 'dyn:TrueStrain',
            'quantity_kind': 'qkdv:Dimensionless',
            'unit': 'unit:UNITLESS',
            'legend_name': 'True Strain (1-wave)',
            'analysis_method': '1-wave',
            'class_uri': 'dyn:ProcessedData',
            'derived_from': ['incident']
        },
        'true_stress_1w': {
            'series_type': 'dyn:TrueStress',
            'quantity_kind': 'qkdv:Stress',
            'unit': 'unit:MegaPA',
            'legend_name': 'True Stress (1-wave)',
            'analysis_method': '1-wave',
            'class_uri': 'dyn:ProcessedData',
            'derived_from': ['transmitted']
        },

        # ===== 3-WAVE PROCESSED DATA =====
        'bar_displacement_3w': {
            'series_type': 'dyn:BarDisplacement',
            'quantity_kind': 'qkdv:Length',
            'unit': 'unit:MilliM',
            'legend_name': 'Bar Displacement (3-wave)',
            'analysis_method': '3-wave',
            'class_uri': 'dyn:ProcessedData',
            'derived_from': ['incident', 'transmitted']
        },
        'bar_force_3w': {
            'series_type': 'dyn:BarForce',
            'quantity_kind': 'qkdv:Force',
            'unit': 'unit:N',
            'legend_name': 'Bar Force (3-wave)',
            'analysis_method': '3-wave',
            'class_uri': 'dyn:ProcessedData',
            'derived_from': ['incident', 'transmitted']
        },
        'strain_rate_3w': {
            'series_type': 'dyn:StrainRate',
            'quantity_kind': 'qkdv:StrainRate',
            'unit': 'unit:PER-SEC',
            'legend_name': 'Strain Rate (3-wave)',
            'analysis_method': '3-wave',
            'class_uri': 'dyn:ProcessedData',
            'derived_from': ['incident', 'transmitted']
        },
        'strain_3w': {
            'series_type': 'dyn:Strain',
            'quantity_kind': 'qkdv:Dimensionless',
            'unit': 'unit:UNITLESS',
            'legend_name': 'Engineering Strain (3-wave)',
            'analysis_method': '3-wave',
            'class_uri': 'dyn:ProcessedData',
            'derived_from': ['incident', 'transmitted']
        },
        'stress_3w': {
            'series_type': 'dyn:Stress',
            'quantity_kind': 'qkdv:Stress',
            'unit': 'unit:MegaPA',
            'legend_name': 'Engineering Stress (3-wave)',
            'analysis_method': '3-wave',
            'class_uri': 'dyn:ProcessedData',
            'derived_from': ['incident', 'transmitted']
        },
        'true_strain_rate_3w': {
            'series_type': 'dyn:TrueStrainRate',
            'quantity_kind': 'qkdv:StrainRate',
            'unit': 'unit:PER-SEC',
            'legend_name': 'True Strain Rate (3-wave)',
            'analysis_method': '3-wave',
            'class_uri': 'dyn:ProcessedData',
            'derived_from': ['incident', 'transmitted']
        },
        'true_strain_3w': {
            'series_type': 'dyn:TrueStrain',
            'quantity_kind': 'qkdv:Dimensionless',
            'unit': 'unit:UNITLESS',
            'legend_name': 'True Strain (3-wave)',
            'analysis_method': '3-wave',
            'class_uri': 'dyn:ProcessedData',
            'derived_from': ['incident', 'transmitted']
        },
        'true_stress_3w': {
            'series_type': 'dyn:TrueStress',
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
    striker_launch_pressure: Optional[Dict[str, Any]] = None  # Gas pressure used to launch striker
    momentum_trap_distance: Optional[Dict[str, Any]] = None  # Distance to trap
    barrel_offset: Optional[Dict[str, Any]] = None  # Separation distance between barrel and incident bar
    lubrication_applied: Optional[bool] = None  # Whether lubrication was used

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
    incident_centering_shift: Optional[int] = None
    transmitted_centering_shift: Optional[int] = None # Shift during segment_and_center (samples)
    reflected_centering_shift: Optional[int] = None  # Shift during segment_and_center (samples)

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
    front_thresh: Optional[float] = None # Rise front threshold for incident
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

    # ====================== Test Validation / Type ===================
    test_type: Optional[str] = None  # Type: "specimen", "calibration", or "elastic"
    test_validity: Optional[str] = None  # Validity URI: "dyn:ValidTest", "dyn:QuestionableTest", or "dyn:InvalidTest"
    validity_notes: Optional[str] = None  # Notes regarding test validity assessment
    validity_criteria: Optional[List[str]] = None  # Specific criteria URIs met: "dyn:ForceEquilibrium", "dyn:ConstantStrainRate"

    # ==================== CALCULATED CHARACTERISTICS ====================
    # Measurements with units
    pulse_duration: Optional[Dict[str, Any]] = None  # Pulse duration
    pulse_length: Optional[Dict[str, Any]] = None  # Physical pulse length
    pulse_stress_amplitude: Optional[Dict[str, Any]] = None  # Stress amplitude
    pulse_strain_amplitude: Optional[Dict[str, Any]] = None  # Strain amplitude (unitless)
    incident_rise_time: Optional[Dict[str, Any]] = None  # Rise time

    # ==================== ANALYSIS METADATA ====================
    analysis_timestamp: Optional[str] = None  # ISO datetime of analysis
    sampling_interval: Optional[Dict[str, Any]] = None  # Time between samples

    # Note: Data file references removed - files are linked via DataSeries (hasDataFile)

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

    @staticmethod
    def _ensure_typed_literal(value: Any) -> Union[Literal, Any]:
        """
        Convert Python types to RDF Literals with explicit XSD datatypes.

        Ensures all numeric values are saved with proper ^^xsd:datatype flags in TTL.
        Non-numeric types (strings, URIs, dicts) are passed through unchanged.

        Args:
            value: Python value to convert

        Returns:
            RDF Literal with explicit datatype, or original value if not a simple numeric type

        Examples:
            >>> _ensure_typed_literal(25000)           # Literal(25000, datatype=XSD.integer)
            >>> _ensure_typed_literal(0.35)            # Literal(0.35, datatype=XSD.double)
            >>> _ensure_typed_literal("TEST_001")      # "TEST_001" (unchanged)
            >>> _ensure_typed_literal(np.int64(100))   # Literal(100, datatype=XSD.integer)
            >>> _ensure_typed_literal("12345")         # "12345" (unchanged - strings stay strings)
        """
        # Handle None (pass through)
        if value is None:
            return value

        # Handle NumPy types (convert to native Python types first)
        if isinstance(value, (np.integer, np.int32, np.int64)):
            return Literal(int(value), datatype=XSD.integer)
        if isinstance(value, (np.floating, np.float32, np.float64)):
            return Literal(float(value), datatype=XSD.double)

        # Handle native Python numeric types
        if isinstance(value, bool):
            # Handle bool before int (bool is subclass of int in Python)
            return Literal(value, datatype=XSD.boolean)
        if isinstance(value, int):
            return Literal(value, datatype=XSD.integer)
        if isinstance(value, float):
            return Literal(value, datatype=XSD.double)

        # Pass through everything else (strings, URIs, dicts, lists, etc.)
        # These have their own handling in InstanceWriter
        # NOTE: We do NOT convert string representations of numbers (e.g., "123") to integers here.
        # Values should be properly typed before reaching this method.
        return value

    @classmethod
    def _apply_type_conversion_to_dict(cls, form_dict: Dict[str, Any]) -> Dict[str, Any]:
        """
        Apply type conversion to all values in a form dictionary.

        Recursively processes dictionary values to ensure numeric types have explicit XSD datatypes.

        Args:
            form_dict: Dictionary with property URIs as keys

        Returns:
            New dictionary with typed literals for all numeric values

        Examples:
            >>> form = {'dyn:hasStartIndex': 7079, 'dyn:hasEndIndex': 81301}
            >>> typed_form = _apply_type_conversion_to_dict(form)
            # Returns: {'dyn:hasStartIndex': Literal(7079, datatype=XSD.integer), ...}
        """
        typed_dict = {}
        for key, value in form_dict.items():
            if value is not None:
                typed_dict[key] = cls._ensure_typed_literal(value)
            else:
                typed_dict[key] = value
        return typed_dict

    def to_form_data(self) -> Dict[str, Any]:
        """
        Convert all metadata fields to form data dictionary for InstanceWriter.

        Maps field names → RDF property URIs, following widget factory format.
        Only includes non-None values (skips optional fields that weren't set).
        All numeric values are converted to typed RDF Literals with explicit XSD datatypes.

        Returns:
            Dict with property URIs as keys, values in widget format:
            {
                'dyn:hasTestID': 'TEST_001',
                'dyn:hasStrikerVelocity': {'value': 10.0, 'unit': '...', 'reference_unit': '...'},
                'dyn:hasIncidentBar': 'dyn:IncidentBar_...',
                'dyn:hasCenteredSegmentPoints': Literal(25000, datatype=XSD.integer),
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
            'test_type': 'dyn:hasTestType',
            'test_validity': 'dyn:hasTestValidity',
            'validity_notes': 'dyn:hasValidityNotes',
            # Note: validity_criteria handled separately as multi-valued property below

            # Equipment configuration
            'striker_bar_uri': 'dyn:hasStrikerBar',
            'incident_bar_uri': 'dyn:hasIncidentBar',
            'transmission_bar_uri': 'dyn:hasTransmissionBar',
            'momentum_trap_uri': 'dyn:hasMomentumTrap',
            'pulse_shaper_uri': 'dyn:hasPulseShaper',
            # Note: strain gauges handled separately as multi-valued property

            # Initial test conditions
            'striker_velocity': 'dyn:hasStrikerVelocity',
            'striker_launch_pressure': 'dyn:hasStrikerLaunchPressure',
            'momentum_trap_distance': 'dyn:hasMomentumTrapTailoredDistance',
            'barrel_offset': 'dyn:hasBarrelOffset',
            'lubrication_applied': 'dyn:hasLubrication',

            # Note: Window references are now associated with DataSeries, not the test instance
            # - incident_window_uri and reflected_window_uri → incident DataSeries
            # - transmitted_window_uri → transmitted DataSeries

            # Segmentation
            # Note: segment_n_points moved to AlignmentParams
            # Note: segment_thresh_ratio moved to AlignmentParams

            # Pulse shifts - stored as values in AlignmentParams, not as separate objects
            # No longer: 'transmitted_shift_uri': 'dyn:hasAppliedShift'
            # No longer: 'reflected_shift_uri': 'dyn:hasAppliedShift'

            # Alignment configuration (reference to AlignmentParams instance only)
            'alignment_params_uri': 'dyn:hasAlignmentParams',
            # Note: k_linear, weights, search bounds, shifts, segment params are in AlignmentParams

            # Alignment results (can stay on test for quick access)
            # Note: alignment_front_idx moved to AlignmentParams
            'linear_region_start': 'dyn:hasLinearRegionStart',
            'linear_region_end': 'dyn:hasLinearRegionEnd',

            # Processing parameters (references to instances)
            # Note: hasPulseDetectionParams moved to RawSignal (DataSeries level)
            # Each RawSignal has one or more detection params associated with it

            # Equilibrium metrics (reference to instance only)
            'equilibrium_metrics_uri': 'dyn:hasEquilibriumMetrics',
            # Note: FBC, SEQI, SOI, DSUF are ONLY in EquilibriumMetrics, not here

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
            # Note: sampling_interval moved to DataSeries (not test level)
            # Note: Data file references (raw/processed) removed - files are linked via DataSeries

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
                # test_type is now an ObjectProperty that expects URI format
                elif field_name == 'test_type':
                    # Keep URI format (e.g., dyn:SpecimenTest)
                    form_data[property_uri] = value
                else:
                    # Apply type conversion to ensure proper XSD datatypes
                    form_data[property_uri] = self._ensure_typed_literal(value)

        # Handle strain gauges as multi-valued property
        gauges = []
        if self.incident_strain_gauge_uri:
            gauges.append(self.incident_strain_gauge_uri)
        if self.transmission_strain_gauge_uri:
            gauges.append(self.transmission_strain_gauge_uri)
        if gauges:
            form_data['dyn:hasStrainGauge'] = gauges

        # Handle validity criteria as multi-valued property
        if self.validity_criteria:
            # Already a list of URIs
            form_data['dyn:hasValidityCriteria'] = self.validity_criteria

        logger.debug(f"Created form_data with {len(form_data)} properties (with typed literals)")
        return form_data

    def get_processing_instances(self) -> Dict[str, List[tuple]]:
        """
        Extract all processing object instances for batch creation.

        Returns instances grouped by type:
        - windows: DEPRECATED - merged into detection_params
        - shifts: DEPRECATED - values now stored in AlignmentParams
        - detection_params: PulseDetectionParams instances (incident, transmitted, reflected)
                           Now includes window boundaries (start, end, length)
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

        # ===== PULSE DETECTION PARAMS (includes window boundaries) =====
        # Note: PulseWindow has been merged into PulseDetectionParams
        # Each detection params instance includes both configuration and results (window boundaries)

        if self.incident_detection_params_uri and self.incident_pulse_points is not None:
            incident_detect_form = self._apply_type_conversion_to_dict({
                # Detection configuration (ensure integers are int type, not strings)
                'dyn:hasPulsePoints': int(self.incident_pulse_points) if self.incident_pulse_points is not None else None,
                'dyn:hasKTrials': self.incident_k_trials,  # Stays string (comma-separated list)
                'dyn:hasDetectionPolarity': self.incident_polarity,
                'dyn:hasMinSeparation': int(self.incident_min_separation) if self.incident_min_separation is not None else None,
                'dyn:hasDetectionLowerBound': int(self.incident_lower_bound) if self.incident_lower_bound is not None else None,
                'dyn:hasDetectionUpperBound': int(self.incident_upper_bound) if self.incident_upper_bound is not None else None,
                'dyn:hasSelectionMetric': self.incident_detection_metric,
                # Detected window boundaries (merged from PulseWindow)
                'dyn:hasStartIndex': int(self.incident_window_start) if self.incident_window_start is not None else None,
                'dyn:hasEndIndex': int(self.incident_window_end) if self.incident_window_end is not None else None,
                'dyn:hasWindowLength': int(self.incident_window_length) if self.incident_window_length is not None else None,
                'dyn:appliedToSeries': self.data_series_incident_uri
            })
            instance_id = self.incident_detection_params_uri.replace('dyn:', '')
            instances['detection_params'].append((incident_detect_form, 'dyn:PulseDetectionParams', instance_id))

        if self.transmitted_detection_params_uri and self.transmitted_pulse_points is not None:
            transmitted_detect_form = self._apply_type_conversion_to_dict({
                # Detection configuration (ensure integers are int type, not strings)
                'dyn:hasPulsePoints': int(self.transmitted_pulse_points) if self.transmitted_pulse_points is not None else None,
                'dyn:hasKTrials': self.transmitted_k_trials,  # Stays string (comma-separated list)
                'dyn:hasDetectionPolarity': self.transmitted_polarity,
                'dyn:hasMinSeparation': int(self.transmitted_min_separation) if self.transmitted_min_separation is not None else None,
                'dyn:hasDetectionLowerBound': int(self.transmitted_lower_bound) if self.transmitted_lower_bound is not None else None,
                'dyn:hasDetectionUpperBound': int(self.transmitted_upper_bound) if self.transmitted_upper_bound is not None else None,
                'dyn:hasSelectionMetric': self.transmitted_detection_metric,
                # Detected window boundaries (merged from PulseWindow)
                'dyn:hasStartIndex': int(self.transmitted_window_start) if self.transmitted_window_start is not None else None,
                'dyn:hasEndIndex': int(self.transmitted_window_end) if self.transmitted_window_end is not None else None,
                'dyn:hasWindowLength': int(self.transmitted_window_length) if self.transmitted_window_length is not None else None,
                'dyn:appliedToSeries': self.data_series_transmitted_uri
            })
            instance_id = self.transmitted_detection_params_uri.replace('dyn:', '')
            instances['detection_params'].append((transmitted_detect_form, 'dyn:PulseDetectionParams', instance_id))

        if self.reflected_detection_params_uri and self.reflected_pulse_points is not None:
            reflected_detect_form = self._apply_type_conversion_to_dict({
                # Detection configuration (ensure integers are int type, not strings)
                'dyn:hasPulsePoints': int(self.reflected_pulse_points) if self.reflected_pulse_points is not None else None,
                'dyn:hasKTrials': self.reflected_k_trials,  # Stays string (comma-separated list)
                'dyn:hasDetectionPolarity': self.reflected_polarity,
                'dyn:hasMinSeparation': int(self.reflected_min_separation) if self.reflected_min_separation is not None else None,
                'dyn:hasDetectionLowerBound': int(self.reflected_lower_bound) if self.reflected_lower_bound is not None else None,
                'dyn:hasDetectionUpperBound': int(self.reflected_upper_bound) if self.reflected_upper_bound is not None else None,
                'dyn:hasSelectionMetric': self.reflected_detection_metric,
                # Detected window boundaries (merged from PulseWindow)
                'dyn:hasStartIndex': int(self.reflected_window_start) if self.reflected_window_start is not None else None,
                'dyn:hasEndIndex': int(self.reflected_window_end) if self.reflected_window_end is not None else None,
                'dyn:hasWindowLength': int(self.reflected_window_length) if self.reflected_window_length is not None else None,
                'dyn:appliedToSeries': self.data_series_incident_uri  # Reflected is on incident bar
            })
            instance_id = self.reflected_detection_params_uri.replace('dyn:', '')
            instances['detection_params'].append((reflected_detect_form, 'dyn:PulseDetectionParams', instance_id))

        # ===== PULSE SHIFTS =====
        # Note: Pulse shift values are now stored directly in AlignmentParams
        # as hasTransmittedShiftValue and hasReflectedShiftValue, not as separate PulseShift objects

        # ===== ALIGNMENT PARAMS =====
        if self.alignment_params_uri and self.k_linear is not None:
            alignment_form = self._apply_type_conversion_to_dict({
                'dyn:hasKLinear': self.k_linear,  # Float
                'dyn:hasCorrelationWeight': self.alignment_weight_corr,  # Float
                'dyn:hasDisplacementWeight': self.alignment_weight_u,  # Float
                'dyn:hasStrainRateWeight': self.alignment_weight_sr,  # Float
                'dyn:hasStrainWeight': self.alignment_weight_e,  # Float
                # Search bounds (ensure integers)
                'dyn:hasTransmittedSearchMin': int(self.search_bounds_t_min) if self.search_bounds_t_min is not None else None,
                'dyn:hasTransmittedSearchMax': int(self.search_bounds_t_max) if self.search_bounds_t_max is not None else None,
                'dyn:hasReflectedSearchMin': int(self.search_bounds_r_min) if self.search_bounds_r_min is not None else None,
                'dyn:hasReflectedSearchMax': int(self.search_bounds_r_max) if self.search_bounds_r_max is not None else None,
                # Shift values (ensure integers)
                'dyn:hasTransmittedShiftValue': int(self.shift_transmitted) if self.shift_transmitted is not None else None,
                'dyn:hasReflectedShiftValue': int(self.shift_reflected) if self.shift_reflected is not None else None,
                # Segmentation parameters
                'dyn:hasCenteredSegmentPoints': int(self.segment_n_points) if self.segment_n_points is not None else None,
                'dyn:hasThresholdRatio': self.segment_thresh_ratio,  # Float
                'dyn:hasFrontIndex': int(self.alignment_front_idx) if self.alignment_front_idx is not None else None,
            })
            instance_id = self.alignment_params_uri.replace('dyn:', '')
            instances['alignment_params'].append((alignment_form, 'dyn:AlignmentParams', instance_id))

        # ===== EQUILIBRIUM METRICS =====
        if self.equilibrium_metrics_uri and self.fbc is not None:
            equilibrium_form = self._apply_type_conversion_to_dict({
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
            })
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
                # Explicit type declaration for SHACL validation (parent class)
                'rdf:type': 'dyn:DataSeries',

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

            # Add sampling interval (series-level metadata)
            if self.sampling_interval is not None:
                form_data['dyn:hasSamplingInterval'] = self.sampling_interval

            # Note: tukey_alpha is test-level parameter (in SHPBCompression), not series-level
            # Note: segment_thresh_ratio is now in AlignmentParams, not DataSeries

            # Add pulse detection params references (associate detection params with their RawSignal)
            if column_name == 'incident':
                # Incident bar has TWO detection params: incident pulse and reflected pulse
                detection_params = []
                if self.incident_detection_params_uri:
                    detection_params.append(self.incident_detection_params_uri)
                if self.reflected_detection_params_uri:
                    detection_params.append(self.reflected_detection_params_uri)
                if detection_params:
                    form_data['dyn:hasPulseDetectionParams'] = detection_params
            elif column_name == 'transmitted':
                # Transmitted bar has ONE detection params: transmitted pulse
                if self.transmitted_detection_params_uri:
                    form_data['dyn:hasPulseDetectionParams'] = self.transmitted_detection_params_uri

            # Apply type conversion to ensure proper XSD datatypes
            form_data = self._apply_type_conversion_to_dict(form_data)

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
        windowed_series_uris: Dict[str, str]
    ) -> List[Tuple[Dict[str, Any], str, str]]:
        """
        Convert processed results dictionary to DataSeries instances.

        Creates 17 ProcessedData instances (1 time + 16 calculated quantities) with:
        - Analysis method (1-wave, 3-wave)
        - Derivation chain (derivedFrom links to WINDOWED signals)
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
            windowed_series_uris: URIs of windowed DataSeries for derivation chain:
                {
                    'time_windowed': 'dyn:TEST_001_time_windowed',
                    'incident_windowed': 'dyn:TEST_001_incident_windowed',
                    'transmitted_windowed': 'dyn:TEST_001_transmitted_windowed',
                    'reflected_windowed': 'dyn:TEST_001_reflected_windowed'
                }

        Returns:
            List of (form_data, class_uri, instance_id) tuples.
            Returns 17 instances (1 time + 16 processed quantities).

        Example:
            >>> calculator = StressStrainCalculator(...)
            >>> results = calculator.calculate(inc, trs, ref, time)
            >>> windowed_uris = {
            ...     'time_windowed': 'dyn:TEST_001_time_windowed',
            ...     'incident_windowed': 'dyn:TEST_001_incident_windowed',
            ...     'transmitted_windowed': 'dyn:TEST_001_transmitted_windowed',
            ...     'reflected_windowed': 'dyn:TEST_001_reflected_windowed'
            ... }
            >>> processed_series = metadata.prepare_processed_data_series(
            ...     results, 'dyn:TEST_001_processed_csv', windowed_uris
            ... )
        """
        instances = []

        # Create temporary DataFrame to get column indices
        processed_df = pd.DataFrame(results)
        data_point_count = len(processed_df)

        for column_name in results.keys():
            # Skip time column - we already have raw time and windowed time series
            # The processed CSV time column doesn't need its own DataSeries
            if column_name == 'time':
                logger.debug("Skipping 'time' column - using windowed time series instead")
                continue

            # Skip pulse window columns - these are the windowed/normalized pulses
            # They are already represented by the windowed series (incident_windowed, etc.)
            # These first 4 columns (time, incident, transmitted, reflected) are intermediate data
            if column_name in ['incident', 'transmitted', 'reflected']:
                logger.debug(f"Skipping '{column_name}' pulse window - already represented by windowed series")
                continue

            # Skip if not in metadata (shouldn't happen)
            if column_name not in self.SERIES_METADATA:
                logger.warning(f"Column '{column_name}' not in SERIES_METADATA, skipping")
                continue

            # Get metadata from lookup table
            metadata = self.SERIES_METADATA[column_name]

            # Build form data
            form_data = {
                # Explicit type declaration for SHACL validation (parent class)
                'rdf:type': 'dyn:DataSeries',

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

            # Add derivation chain (link to source windowed signals)
            if 'derived_from' in metadata:
                # Map from metadata keys (incident/transmitted/reflected) to windowed series URIs
                source_mapping = {
                    'incident': 'incident_windowed',
                    'transmitted': 'transmitted_windowed',
                    'reflected': 'reflected_windowed'
                }

                # Collect all valid source URIs
                derived_sources = []
                for source_column in metadata['derived_from']:
                    windowed_key = source_mapping.get(source_column, source_column)
                    if windowed_key in windowed_series_uris:
                        derived_sources.append(windowed_series_uris[windowed_key])

                # Add as single value or list depending on count
                if len(derived_sources) == 1:
                    form_data['dyn:derivedFrom'] = derived_sources[0]
                elif len(derived_sources) > 1:
                    form_data['dyn:derivedFrom'] = derived_sources

            # Apply type conversion to ensure proper XSD datatypes
            form_data = self._apply_type_conversion_to_dict(form_data)

            # Create instance tuple
            instance_id = f"{self.test_id.replace('-', '_')}_{column_name}"
            instances.append((form_data, metadata['class_uri'], instance_id))

            logger.debug(f"Prepared {column_name} DataSeries: {instance_id}")

        logger.info(f"Prepared {len(instances)} processed DataSeries instances")
        return instances

    def prepare_windowed_data_series(
        self,
        raw_series_uris: Dict[str, str],
        window_length: int,
        file_uri: str
    ) -> List[Tuple[Dict[str, Any], str, str]]:
        """
        Create DataSeries instances for windowed/segmented signals.

        These are the intermediate signals between raw and processed:
        - Raw signals (full length) are captured from the oscilloscope
        - Windowed signals are extracted pulses (after pulse detection)
        - Processed signals are calculated stress-strain curves

        Creates 4 windowed DataSeries:
        1. time_windowed - time vector for the aligned window
        2. incident_windowed - extracted incident pulse
        3. transmitted_windowed - extracted transmitted pulse
        4. reflected_windowed - extracted reflected pulse (from incident bar)

        Args:
            raw_series_uris: URIs of raw DataSeries for derivation:
                {
                    'time': 'dyn:TEST_001_time',
                    'incident': 'dyn:TEST_001_incident',
                    'transmitted': 'dyn:TEST_001_transmitted'
                }
            window_length: Number of data points in windowed signals (from segment_n_points)
            file_uri: URI of windowed data file (processed CSV containing windowed pulses)

        Returns:
            List of (form_data, class_uri, instance_id) tuples for windowed series

        Example:
            >>> windowed_series = metadata.prepare_windowed_data_series(
            ...     raw_uris, window_length=25000, file_uri='dyn:TEST_001_windowed_csv'
            ... )
            >>> # Returns 4 instances: time_windowed, incident_windowed, transmitted_windowed, reflected_windowed
        """
        instances = []

        # Windowed series metadata
        # Note: window_uri removed - windows are now part of PulseDetectionParams on raw signals
        windowed_metadata = {
            'time_windowed': {
                'series_type': 'dyn:Time',
                'quantity_kind': 'qkdv:Time',
                'unit': 'unit:MilliSEC',
                'legend_name': 'Time (Windowed)',
                'derived_from': 'time'
            },
            'incident_windowed': {
                'series_type': 'dyn:IncidentPulse',
                'quantity_kind': 'qkdv:Dimensionless',
                'unit': 'unit:UNITLESS',
                'legend_name': 'Incident Pulse (Windowed & Normalized)',
                'derived_from': 'incident',
                'gauge_uri': self.incident_strain_gauge_uri
            },
            'transmitted_windowed': {
                'series_type': 'dyn:TransmittedPulse',
                'quantity_kind': 'qkdv:Dimensionless',
                'unit': 'unit:UNITLESS',
                'legend_name': 'Transmitted Pulse (Windowed & Normalized)',
                'derived_from': 'transmitted',
                'gauge_uri': self.transmission_strain_gauge_uri
            },
            'reflected_windowed': {
                'series_type': 'dyn:ReflectedPulse',
                'quantity_kind': 'qkdv:Dimensionless',
                'unit': 'unit:UNITLESS',
                'legend_name': 'Reflected Pulse (Windowed & Normalized)',
                'derived_from': 'incident',  # Reflected pulse is on incident bar
                'gauge_uri': self.incident_strain_gauge_uri
            }
        }

        for series_name, metadata in windowed_metadata.items():
            # Build form data
            form_data = {
                # Explicit type declaration
                'rdf:type': 'dyn:DataSeries',

                # File reference (windowed data CSV)
                'dyn:hasDataFile': file_uri,

                # Series metadata
                'dyn:hasLegendName': metadata['legend_name'],
                'dyn:hasSeriesType': metadata['series_type'],
                'dyn:hasDataPointCount': window_length,

                # Processing info
                'dyn:hasProcessingMethod': 'Pulse windowing and segmentation',
                'dyn:hasFilterApplied': False,

                # Derivation (from raw signal)
                'dyn:derivedFrom': raw_series_uris[metadata['derived_from']],
            }

            # Add unit and quantity kind if specified
            if metadata['unit']:
                form_data['dyn:hasSeriesUnit'] = metadata['unit']
            if metadata['quantity_kind']:
                form_data['dyn:hasQuantityKind'] = metadata['quantity_kind']

            # Note: window references removed - windows are now in PulseDetectionParams on raw signals

            # Add gauge reference for signal series
            if 'gauge_uri' in metadata and metadata['gauge_uri']:
                form_data['dyn:measuredBy'] = metadata['gauge_uri']

            # Note: tukey_alpha is test-level parameter (in SHPBCompression), not series-level
            # Note: segment_thresh_ratio is now in AlignmentParams, not ProcessedData

            # Apply type conversion
            form_data = self._apply_type_conversion_to_dict(form_data)

            # Create instance tuple
            instance_id = f"{self.test_id.replace('-', '_')}_{series_name}"
            instances.append((form_data, 'dyn:ProcessedData', instance_id))

            logger.debug(f"Prepared windowed DataSeries: {instance_id}")

        logger.info(f"Prepared {len(instances)} windowed DataSeries instances")
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

        # Validate test type if provided (accept both URIs and string values)
        if self.test_type is not None:
            valid_test_types = ['specimen', 'calibration', 'elastic']
            # Normalize URI format to lowercase string (dyn:SpecimenTest → specimen)
            test_type_normalized = self.test_type
            if self.test_type.startswith('dyn:'):
                # Extract and normalize: dyn:SpecimenTest → specimen
                test_type_normalized = self.test_type.replace('dyn:', '').replace('Test', '').lower()

            if test_type_normalized.lower() not in valid_test_types:
                raise ValueError(
                    f"test_type must be one of {valid_test_types} or corresponding URI, got: {self.test_type}"
                )

        # Validate test validity if provided (accepts both strings and URIs)
        if self.test_validity is not None:
            valid_validity_uris = [
                'dyn:ValidTest', 'dyn:QuestionableTest', 'dyn:InvalidTest',
                'valid', 'questionable', 'invalid'  # Legacy support
            ]
            # Normalize to lowercase for string comparison
            validity_check = self.test_validity.lower() if isinstance(self.test_validity, str) else self.test_validity
            if validity_check not in [v.lower() for v in valid_validity_uris]:
                raise ValueError(
                    f"test_validity must be a valid URI or one of ['valid', 'questionable', 'invalid'], got: {self.test_validity}"
                )

        # Validate test conditions if provided
        if self.striker_velocity is not None:
            # Handle both dict format (with units) and direct numeric values
            velocity_value = self.striker_velocity.get('value', self.striker_velocity) if isinstance(self.striker_velocity, dict) else self.striker_velocity
            if velocity_value <= 0:
                raise ValueError(f"striker_velocity must be positive, got: {velocity_value}")

        if self.striker_launch_pressure is not None:
            # Handle both dict format (with units) and direct numeric values
            pressure_value = self.striker_launch_pressure.get('value', self.striker_launch_pressure) if isinstance(self.striker_launch_pressure, dict) else self.striker_launch_pressure
            if pressure_value <= 0:
                raise ValueError(f"striker_launch_pressure must be positive, got: {pressure_value}")

        if self.momentum_trap_distance is not None:
            # Handle both dict format (with units) and direct numeric values
            distance_value = self.momentum_trap_distance.get('value', self.momentum_trap_distance) if isinstance(self.momentum_trap_distance, dict) else self.momentum_trap_distance
            if distance_value <= 0:
                raise ValueError(f"momentum_trap_distance must be positive, got: {distance_value}")

        if self.barrel_offset is not None:
            # Handle both dict format (with units) and direct numeric values
            offset_value = self.barrel_offset.get('value', self.barrel_offset) if isinstance(self.barrel_offset, dict) else self.barrel_offset
            if offset_value < 0:
                raise ValueError(f"barrel_offset must be non-negative, got: {offset_value}")

        logger.info(f"SHPBTestMetadata validation passed for test_id: {self.test_id}")

    def assess_validity_from_metrics(self, metrics: Dict[str, float]) -> None:
        """
        Automatically assess test validity based on equilibrium metrics.

        Sets test_validity and validity_notes based on FBC, SEQI, SOI, and DSUF values.
        Uses multi-level criteria to determine if force equilibrium and constant strain rate
        were achieved.

        Args:
            metrics: Dictionary from StressStrainCalculator.calculate_equilibrium_metrics()
                     Must contain keys: 'FBC', 'SEQI', 'SOI', 'DSUF'

        Sets:
            test_validity: URI of validity status
                - "dyn:ValidTest": 3+ metrics meet strict standards
                - "dyn:QuestionableTest": 3+ metrics meet relaxed standards
                - "dyn:InvalidTest": fewer than 3 metrics meet relaxed standards
            validity_notes: Human-readable description of validity assessment

        Example:
            >>> metrics = calculator.calculate_equilibrium_metrics(results)
            >>> metadata.assess_validity_from_metrics(metrics)
            >>> print(metadata.test_validity)  # "dyn:ValidTest", "dyn:QuestionableTest", or "dyn:InvalidTest"
            >>> print(metadata.validity_notes)
        """
        # Extract metrics
        fbc = metrics.get('FBC', 0.0)
        seqi = metrics.get('SEQI', 0.0)
        soi = metrics.get('SOI', 1.0)
        dsuf = metrics.get('DSUF', 0.0)

        # Assess force equilibrium
        force_equilibrium = self._assess_force_equilibrium(fbc, dsuf)

        # Assess constant strain rate
        constant_strain_rate = self._assess_strain_rate(soi)

        # Determine overall validity
        validity = self._determine_overall_validity(fbc, seqi, soi, dsuf)

        # Generate validity notes
        notes = self._generate_validity_notes(
            fbc, seqi, soi, dsuf,
            force_equilibrium, constant_strain_rate
        )

        # Get specific criteria URIs that were met
        criteria = self.get_validity_criteria(metrics)

        # Set metadata fields
        self.test_validity = validity
        self.validity_notes = notes
        self.validity_criteria = criteria if criteria else None

        logger.info(f"Validity assessment complete: {validity}")
        if criteria:
            logger.info(f"Specific criteria met: {', '.join(criteria)}")
        logger.debug(f"Validity notes: {notes}")

    def get_validity_criteria(self, metrics: Dict[str, float]) -> List[str]:
        """
        Get list of specific validity criteria URIs that were achieved.

        Returns URIs for specific criteria based on the metrics:
        - "dyn:ForceEquilibrium" if force equilibrium was achieved
        - "dyn:ConstantStrainRate" if constant strain rate was achieved

        Args:
            metrics: Dictionary with keys: 'FBC', 'SEQI', 'SOI', 'DSUF'

        Returns:
            List of criteria URIs that were achieved

        Example:
            >>> metrics = calculator.calculate_equilibrium_metrics(results)
            >>> criteria = metadata.get_validity_criteria(metrics)
            >>> print(criteria)  # ['dyn:ForceEquilibrium', 'dyn:ConstantStrainRate']
        """
        criteria = []

        fbc = metrics.get('FBC', 0.0)
        dsuf = metrics.get('DSUF', 0.0)
        soi = metrics.get('SOI', 1.0)

        # Check force equilibrium (strict criteria)
        if fbc >= 0.90 and dsuf >= 0.90:
            criteria.append('dyn:ForceEquilibrium')

        # Check constant strain rate (strict criteria)
        if soi <= 0.10:
            criteria.append('dyn:ConstantStrainRate')

        return criteria

    def is_valid(self) -> bool:
        """
        Convenience method to check if test is valid.

        Returns:
            True if test_validity is "dyn:ValidTest", False otherwise
        """
        return self.test_validity == 'dyn:ValidTest'

    def is_questionable(self) -> bool:
        """
        Convenience method to check if test is questionable.

        Returns:
            True if test_validity is "dyn:QuestionableTest", False otherwise
        """
        return self.test_validity == 'dyn:QuestionableTest'

    def is_invalid(self) -> bool:
        """
        Convenience method to check if test is invalid.

        Returns:
            True if test_validity is "dyn:InvalidTest", False otherwise
        """
        return self.test_validity == 'dyn:InvalidTest'

    @staticmethod
    def _assess_force_equilibrium(fbc: float, dsuf: float) -> str:
        """
        Assess if force equilibrium was achieved.

        Args:
            fbc: Force Balance Coefficient (0-1)
            dsuf: Dynamic Stress Uniformity Factor (0-1)

        Returns:
            "achieved", "partially_achieved", or "not_achieved"
        """
        if fbc >= 0.90 and dsuf >= 0.90:
            return "achieved"
        elif fbc >= 0.75 or dsuf >= 0.75:
            return "partially_achieved"
        else:
            return "not_achieved"

    @staticmethod
    def _assess_strain_rate(soi: float) -> str:
        """
        Assess if constant strain rate was maintained.

        Args:
            soi: Strain Offset Index (0-1), measures strain rate oscillations

        Returns:
            "achieved", "partially_achieved", or "not_achieved"
        """
        if soi <= 0.10:
            return "achieved"
        elif soi <= 0.20:
            return "partially_achieved"
        else:
            return "not_achieved"

    @staticmethod
    def _determine_overall_validity(fbc: float, seqi: float, soi: float, dsuf: float) -> str:
        """
        Determine overall test validity based on all equilibrium metrics.

        Uses a multi-level approach:
        - "dyn:ValidTest": ALL 4 metrics meet strict standards
        - "dyn:QuestionableTest": At least half (2/4) of relaxed standards met
        - "dyn:InvalidTest": Less than half of relaxed standards met

        Strict standards (all must pass for valid):
        - FBC ≥ 0.95
        - SEQI ≥ 0.90
        - SOI ≤ 0.05
        - DSUF ≥ 0.98

        Relaxed standards (at least 2 must pass for questionable):
        - FBC ≥ 0.85
        - SEQI ≥ 0.80
        - SOI ≤ 0.10
        - DSUF ≥ 0.90

        Args:
            fbc: Force Balance Coefficient
            seqi: Stress Equilibrium Quality Index
            soi: Strain Offset Index
            dsuf: Dynamic Stress Uniformity Factor

        Returns:
            URI of validity status: "dyn:ValidTest", "dyn:QuestionableTest", or "dyn:InvalidTest"
        """
        # Count criteria meeting strict standards
        strict_pass = 0
        if fbc >= 0.95:
            strict_pass += 1
        if seqi >= 0.90:
            strict_pass += 1
        if soi <= 0.05:
            strict_pass += 1
        if dsuf >= 0.98:
            strict_pass += 1

        # Count criteria meeting relaxed standards
        relaxed_pass = 0
        if fbc >= 0.85:
            relaxed_pass += 1
        if seqi >= 0.80:
            relaxed_pass += 1
        if soi <= 0.10:
            relaxed_pass += 1
        if dsuf >= 0.90:
            relaxed_pass += 1

        # Decision logic - return ontology URIs
        if strict_pass == 4:
            # ALL strict criteria pass → VALID
            return "dyn:ValidTest"
        elif relaxed_pass >= 2:
            # At least half of relaxed criteria pass → QUESTIONABLE
            return "dyn:QuestionableTest"
        else:
            # Less than half of relaxed criteria pass → INVALID
            return "dyn:InvalidTest"

    @staticmethod
    def _generate_validity_notes(
        fbc: float,
        seqi: float,
        soi: float,
        dsuf: float,
        force_eq: str,
        const_sr: str
    ) -> str:
        """
        Generate human-readable validity notes based on metrics.

        Args:
            fbc: Force Balance Coefficient
            seqi: Stress Equilibrium Quality Index
            soi: Strain Offset Index
            dsuf: Dynamic Stress Uniformity Factor
            force_eq: Force equilibrium assessment ("achieved", "partially_achieved", "not_achieved")
            const_sr: Constant strain rate assessment

        Returns:
            Human-readable string describing test validity
        """
        notes = []

        # Force equilibrium assessment
        if force_eq == "achieved":
            notes.append(f"Force equilibrium achieved (FBC={fbc:.3f}, DSUF={dsuf:.3f})")
        elif force_eq == "partially_achieved":
            notes.append(f"Force equilibrium partially achieved (FBC={fbc:.3f}, DSUF={dsuf:.3f})")
        else:
            notes.append(f"Force equilibrium NOT achieved (FBC={fbc:.3f}, DSUF={dsuf:.3f})")

        # Strain rate assessment
        if const_sr == "achieved":
            notes.append(f"Constant strain rate maintained (SOI={soi:.3f})")
        elif const_sr == "partially_achieved":
            notes.append(f"Strain rate oscillations detected (SOI={soi:.3f})")
        else:
            notes.append(f"Significant strain rate oscillations (SOI={soi:.3f})")

        # Stress equilibrium assessment
        if seqi >= 0.90:
            notes.append(f"Good stress equilibrium (SEQI={seqi:.3f})")
        elif seqi >= 0.80:
            notes.append(f"Acceptable stress equilibrium (SEQI={seqi:.3f})")
        else:
            notes.append(f"Poor stress equilibrium (SEQI={seqi:.3f})")

        return "; ".join(notes)
