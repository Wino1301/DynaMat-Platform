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

from .rdf_helpers import ensure_typed_literal, apply_type_conversion_to_dict
from .validity_assessment import ValidityAssessor
from .series_config import SERIES_METADATA as _SERIES_METADATA, DataSeriesBuilder
from .form_conversion import FormDataConverter

logger = logging.getLogger(__name__)

# Module-level assessor instance for convenience
_validity_assessor = ValidityAssessor()


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
    # Re-exported from series_config for backwards compatibility
    SERIES_METADATA = _SERIES_METADATA

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

        Delegates to rdf_helpers.ensure_typed_literal() for implementation.
        Retained for backwards compatibility.

        See Also:
            rdf_helpers.ensure_typed_literal: Full implementation and documentation
        """
        return ensure_typed_literal(value)

    @classmethod
    def _apply_type_conversion_to_dict(cls, form_dict: Dict[str, Any]) -> Dict[str, Any]:
        """
        Apply type conversion to all values in a form dictionary.

        Delegates to rdf_helpers.apply_type_conversion_to_dict() for implementation.
        Retained for backwards compatibility.

        See Also:
            rdf_helpers.apply_type_conversion_to_dict: Full implementation and documentation
        """
        return apply_type_conversion_to_dict(form_dict)

    def to_form_data(self) -> Dict[str, Any]:
        """
        Convert metadata fields to form data dictionary for InstanceWriter.

        Delegates to FormDataConverter for implementation.

        See Also:
            form_conversion.FormDataConverter.to_form_data: Full implementation
        """
        converter = FormDataConverter(self)
        return converter.to_form_data()

    def get_processing_instances(self) -> Dict[str, List[tuple]]:
        """
        Extract all processing object instances for batch creation.

        Delegates to FormDataConverter for implementation.

        See Also:
            form_conversion.FormDataConverter.get_processing_instances: Full implementation
        """
        converter = FormDataConverter(self)
        return converter.get_processing_instances()

    def prepare_raw_data_series(
        self,
        raw_df: pd.DataFrame,
        file_uri: str,
        gauge_params: Dict[str, str]
    ) -> List[Tuple[Dict[str, Any], str, str]]:
        """
        Convert raw DataFrame columns to DataSeries instances.

        Delegates to DataSeriesBuilder for implementation.

        See Also:
            series_config.DataSeriesBuilder.prepare_raw_data_series: Full implementation
        """
        builder = DataSeriesBuilder(self)
        return builder.prepare_raw_data_series(raw_df, file_uri, gauge_params)

    def prepare_processed_data_series(
        self,
        results: Dict[str, np.ndarray],
        file_uri: str,
        windowed_series_uris: Dict[str, str]
    ) -> List[Tuple[Dict[str, Any], str, str]]:
        """
        Convert processed results dictionary to DataSeries instances.

        Delegates to DataSeriesBuilder for implementation.

        See Also:
            series_config.DataSeriesBuilder.prepare_processed_data_series: Full implementation
        """
        builder = DataSeriesBuilder(self)
        return builder.prepare_processed_data_series(results, file_uri, windowed_series_uris)

    def prepare_windowed_data_series(
        self,
        raw_series_uris: Dict[str, str],
        window_length: int,
        file_uri: str
    ) -> List[Tuple[Dict[str, Any], str, str]]:
        """
        Create DataSeries instances for windowed/segmented signals.

        Delegates to DataSeriesBuilder for implementation.

        See Also:
            series_config.DataSeriesBuilder.prepare_windowed_data_series: Full implementation
        """
        builder = DataSeriesBuilder(self)
        return builder.prepare_windowed_data_series(raw_series_uris, window_length, file_uri)

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

        Delegates to ValidityAssessor for implementation.

        Args:
            metrics: Dictionary from StressStrainCalculator.calculate_equilibrium_metrics()
                     Must contain keys: 'FBC', 'SEQI', 'SOI', 'DSUF'

        Sets:
            test_validity: URI of validity status
            validity_notes: Human-readable description
            validity_criteria: List of criteria URIs achieved

        See Also:
            validity_assessment.ValidityAssessor: Full implementation and thresholds
        """
        result = _validity_assessor.assess_validity_from_metrics(metrics)
        self.test_validity = result['test_validity']
        self.validity_notes = result['validity_notes']
        self.validity_criteria = result['validity_criteria']

    def get_validity_criteria(self, metrics: Dict[str, float]) -> List[str]:
        """
        Get list of specific validity criteria URIs that were achieved.

        Delegates to ValidityAssessor for implementation.

        See Also:
            validity_assessment.ValidityAssessor.get_validity_criteria: Full implementation
        """
        return _validity_assessor.get_validity_criteria(metrics)

    def is_valid(self) -> bool:
        """Check if test is valid. Returns True if test_validity is 'dyn:ValidTest'."""
        return self.test_validity == 'dyn:ValidTest'

    def is_questionable(self) -> bool:
        """Check if test is questionable. Returns True if test_validity is 'dyn:QuestionableTest'."""
        return self.test_validity == 'dyn:QuestionableTest'

    def is_invalid(self) -> bool:
        """Check if test is invalid. Returns True if test_validity is 'dyn:InvalidTest'."""
        return self.test_validity == 'dyn:InvalidTest'

    @staticmethod
    def _assess_force_equilibrium(fbc: float, dsuf: float) -> str:
        """Assess force equilibrium. Delegates to ValidityAssessor."""
        return _validity_assessor.assess_force_equilibrium(fbc, dsuf)

    @staticmethod
    def _assess_strain_rate(soi: float) -> str:
        """Assess strain rate. Delegates to ValidityAssessor."""
        return _validity_assessor.assess_strain_rate(soi)

    @staticmethod
    def _determine_overall_validity(fbc: float, seqi: float, soi: float, dsuf: float) -> str:
        """Determine overall validity. Delegates to ValidityAssessor."""
        return _validity_assessor.determine_overall_validity(
            {'FBC': fbc, 'SEQI': seqi, 'SOI': soi, 'DSUF': dsuf}
        )

    @staticmethod
    def _generate_validity_notes(
        fbc: float, seqi: float, soi: float, dsuf: float,
        force_eq: str, const_sr: str
    ) -> str:
        """Generate validity notes. Delegates to ValidityAssessor."""
        return _validity_assessor.generate_validity_notes(
            fbc, seqi, soi, dsuf, force_eq, const_sr
        )
