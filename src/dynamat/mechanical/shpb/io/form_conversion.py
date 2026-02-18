"""
SHPB Form Data Conversion

Converts SHPBTestMetadata to form data dictionaries for RDF instance writing.
Extracted from SHPBTestMetadata for single responsibility.
"""

import logging
from typing import Dict, Any, List

from .rdf_helpers import ensure_typed_literal, apply_type_conversion_to_dict

logger = logging.getLogger(__name__)


# Field name → RDF property URI mapping for SHPBCompression test instances
FIELD_MAPPING = {
    # Core identification
    'test_id': 'dyn:hasTestID',
    'specimen_uri': 'dyn:performedOn',
    'test_date': 'dyn:hasTestDate',
    'user': 'dyn:hasUser',
    'test_type': 'dyn:hasTestType',
    'test_validity': 'dyn:hasTestValidity',
    'validity_notes': 'dyn:hasValidityNotes',

    # Equipment configuration
    'striker_bar_uri': 'dyn:hasStrikerBar',
    'incident_bar_uri': 'dyn:hasIncidentBar',
    'transmission_bar_uri': 'dyn:hasTransmissionBar',
    'momentum_trap_uri': 'dyn:hasMomentumTrap',
    'pulse_shaper_uri': 'dyn:hasPulseShaper',

    # Initial test conditions
    'striker_velocity': 'dyn:hasStrikerVelocity',
    'striker_launch_pressure': 'dyn:hasStrikerLaunchPressure',
    'momentum_trap_distance': 'dyn:hasMomentumTrapTailoredDistance',
    'barrel_offset': 'dyn:hasBarrelOffset',
    'lubrication_applied': 'dyn:hasLubrication',

    # Alignment configuration (reference to AlignmentParams instance only)
    'alignment_params_uri': 'dyn:hasAlignmentParams',

    # Alignment results
    'linear_region_start': 'dyn:hasLinearRegionStart',
    'linear_region_end': 'dyn:hasLinearRegionEnd',

    # Equilibrium metrics (reference to instance only)
    'equilibrium_metrics_uri': 'dyn:hasEquilibriumMetrics',

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

    # Data series references
    'data_series_time_uri': 'dyn:hasDataSeries',
    'data_series_incident_uri': 'dyn:hasDataSeries',
    'data_series_transmitted_uri': 'dyn:hasDataSeries',
}


class FormDataConverter:
    """
    Converts SHPBTestMetadata to form data dictionaries for RDF instance writing.

    Handles the mapping of Python field names to RDF property URIs and
    conversion of values to appropriate RDF literal types.

    Args:
        test_metadata: SHPBTestMetadata instance to convert

    Example:
        >>> converter = FormDataConverter(metadata)
        >>> form_data = converter.to_form_data()
        >>> processing = converter.get_processing_instances()
    """

    def __init__(self, test_metadata):
        """
        Initialize converter with metadata.

        Args:
            test_metadata: SHPBTestMetadata instance with test parameters
        """
        self.metadata = test_metadata

    def to_form_data(self) -> Dict[str, Any]:
        """
        Convert metadata fields to form data dictionary for InstanceWriter.

        Maps field names to RDF property URIs, following widget factory format.
        Only includes non-None values (skips optional fields that weren't set).

        Returns:
            Dict with property URIs as keys, values in widget format

        Example:
            >>> converter = FormDataConverter(metadata)
            >>> form_data = converter.to_form_data()
            >>> writer.write_instance(form_data, 'dyn:SHPBCompression', test_id, output_path)
        """
        form_data = {}

        # Process all fields using mapping
        for field_name, property_uri in FIELD_MAPPING.items():
            value = getattr(self.metadata, field_name, None)
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
                    form_data[property_uri] = ensure_typed_literal(value)

        # Handle strain gauges as multi-valued property
        gauges = []
        if self.metadata.incident_strain_gauge_uri:
            gauges.append(self.metadata.incident_strain_gauge_uri)
        if self.metadata.transmission_strain_gauge_uri:
            gauges.append(self.metadata.transmission_strain_gauge_uri)
        if gauges:
            form_data['dyn:hasStrainGauge'] = gauges

        # Handle validity criteria as multi-valued property
        if self.metadata.validity_criteria:
            form_data['dyn:hasValidityCriteria'] = self.metadata.validity_criteria

        logger.debug(f"Created form_data with {len(form_data)} properties (with typed literals)")
        return form_data

    def get_processing_instances(self) -> Dict[str, List[tuple]]:
        """
        Extract all processing object instances for batch creation.

        Returns instances grouped by type:
        - windows: DEPRECATED - merged into detection_params
        - shifts: DEPRECATED - values now stored in AlignmentParams
        - detection_params: PulseDetectionParams instances
        - alignment_params: AlignmentParams instance
        - equilibrium_metrics: EquilibriumMetrics instance

        Returns:
            Dict with instance type as key, list of (form_data, class_uri, instance_id) tuples

        Example:
            >>> converter = FormDataConverter(metadata)
            >>> processing = converter.get_processing_instances()
            >>> detection_params = processing['detection_params']
        """
        instances = {
            'windows': [],
            'shifts': [],
            'detection_params': [],
            'alignment_params': [],
            'equilibrium_metrics': []
        }

        # ===== PULSE DETECTION PARAMS (includes window boundaries) =====
        self._add_detection_params(instances)

        # ===== ALIGNMENT PARAMS =====
        self._add_alignment_params(instances)

        # ===== EQUILIBRIUM METRICS =====
        self._add_equilibrium_metrics(instances)

        total_instances = sum(len(v) for v in instances.values())
        logger.debug(f"Extracted {total_instances} processing instances")
        return instances

    def _add_detection_params(self, instances: Dict[str, List[tuple]]) -> None:
        """Add pulse detection params instances for all three pulses."""
        m = self.metadata  # Shorthand

        # Incident detection params
        if m.incident_detection_params_uri and m.incident_pulse_points is not None:
            form = apply_type_conversion_to_dict({
                'dyn:hasPulsePoints': int(m.incident_pulse_points) if m.incident_pulse_points is not None else None,
                'dyn:hasKTrials': m.incident_k_trials,
                'dyn:hasDetectionPolarity': m.incident_polarity,
                'dyn:hasMinSeparation': int(m.incident_min_separation) if m.incident_min_separation is not None else None,
                'dyn:hasDetectionLowerBound': int(m.incident_lower_bound) if m.incident_lower_bound is not None else None,
                'dyn:hasDetectionUpperBound': int(m.incident_upper_bound) if m.incident_upper_bound is not None else None,
                'dyn:hasSelectionMetric': m.incident_detection_metric,
                'dyn:hasStartIndex': int(m.incident_window_start) if m.incident_window_start is not None else None,
                'dyn:hasEndIndex': int(m.incident_window_end) if m.incident_window_end is not None else None,
                'dyn:hasWindowLength': int(m.incident_window_length) if m.incident_window_length is not None else None,
                'dyn:appliedToSeries': m.data_series_incident_uri
            })
            instance_id = m.incident_detection_params_uri.replace('dyn:', '')
            instances['detection_params'].append((form, 'dyn:PulseDetectionParams', instance_id))

        # Transmitted detection params
        if m.transmitted_detection_params_uri and m.transmitted_pulse_points is not None:
            form = apply_type_conversion_to_dict({
                'dyn:hasPulsePoints': int(m.transmitted_pulse_points) if m.transmitted_pulse_points is not None else None,
                'dyn:hasKTrials': m.transmitted_k_trials,
                'dyn:hasDetectionPolarity': m.transmitted_polarity,
                'dyn:hasMinSeparation': int(m.transmitted_min_separation) if m.transmitted_min_separation is not None else None,
                'dyn:hasDetectionLowerBound': int(m.transmitted_lower_bound) if m.transmitted_lower_bound is not None else None,
                'dyn:hasDetectionUpperBound': int(m.transmitted_upper_bound) if m.transmitted_upper_bound is not None else None,
                'dyn:hasSelectionMetric': m.transmitted_detection_metric,
                'dyn:hasStartIndex': int(m.transmitted_window_start) if m.transmitted_window_start is not None else None,
                'dyn:hasEndIndex': int(m.transmitted_window_end) if m.transmitted_window_end is not None else None,
                'dyn:hasWindowLength': int(m.transmitted_window_length) if m.transmitted_window_length is not None else None,
                'dyn:appliedToSeries': m.data_series_transmitted_uri
            })
            instance_id = m.transmitted_detection_params_uri.replace('dyn:', '')
            instances['detection_params'].append((form, 'dyn:PulseDetectionParams', instance_id))

        # Reflected detection params
        if m.reflected_detection_params_uri and m.reflected_pulse_points is not None:
            form = apply_type_conversion_to_dict({
                'dyn:hasPulsePoints': int(m.reflected_pulse_points) if m.reflected_pulse_points is not None else None,
                'dyn:hasKTrials': m.reflected_k_trials,
                'dyn:hasDetectionPolarity': m.reflected_polarity,
                'dyn:hasMinSeparation': int(m.reflected_min_separation) if m.reflected_min_separation is not None else None,
                'dyn:hasDetectionLowerBound': int(m.reflected_lower_bound) if m.reflected_lower_bound is not None else None,
                'dyn:hasDetectionUpperBound': int(m.reflected_upper_bound) if m.reflected_upper_bound is not None else None,
                'dyn:hasSelectionMetric': m.reflected_detection_metric,
                'dyn:hasStartIndex': int(m.reflected_window_start) if m.reflected_window_start is not None else None,
                'dyn:hasEndIndex': int(m.reflected_window_end) if m.reflected_window_end is not None else None,
                'dyn:hasWindowLength': int(m.reflected_window_length) if m.reflected_window_length is not None else None,
                'dyn:appliedToSeries': m.data_series_incident_uri  # Reflected is on incident bar
            })
            instance_id = m.reflected_detection_params_uri.replace('dyn:', '')
            instances['detection_params'].append((form, 'dyn:PulseDetectionParams', instance_id))

    def _add_alignment_params(self, instances: Dict[str, List[tuple]]) -> None:
        """Add alignment params instance."""
        m = self.metadata

        if m.alignment_params_uri and m.k_linear is not None:
            form = apply_type_conversion_to_dict({
                'dyn:hasKLinear': m.k_linear,
                'dyn:hasCorrelationWeight': m.alignment_weight_corr,
                'dyn:hasDisplacementWeight': m.alignment_weight_u,
                'dyn:hasStrainRateWeight': m.alignment_weight_sr,
                'dyn:hasStrainWeight': m.alignment_weight_e,
                'dyn:hasTransmittedSearchMin': int(m.search_bounds_t_min) if m.search_bounds_t_min is not None else None,
                'dyn:hasTransmittedSearchMax': int(m.search_bounds_t_max) if m.search_bounds_t_max is not None else None,
                'dyn:hasReflectedSearchMin': int(m.search_bounds_r_min) if m.search_bounds_r_min is not None else None,
                'dyn:hasReflectedSearchMax': int(m.search_bounds_r_max) if m.search_bounds_r_max is not None else None,
                'dyn:hasTransmittedShiftValue': int(m.shift_transmitted) if m.shift_transmitted is not None else None,
                'dyn:hasReflectedShiftValue': int(m.shift_reflected) if m.shift_reflected is not None else None,
                'dyn:hasCenteredSegmentPoints': int(m.segment_n_points) if m.segment_n_points is not None else None,
                'dyn:hasFrontIndex': int(m.alignment_front_idx) if m.alignment_front_idx is not None else None,
            })
            instance_id = m.alignment_params_uri.replace('dyn:', '')
            instances['alignment_params'].append((form, 'dyn:AlignmentParams', instance_id))

    def _add_equilibrium_metrics(self, instances: Dict[str, List[tuple]]) -> None:
        """Add equilibrium metrics instance."""
        m = self.metadata

        if m.equilibrium_metrics_uri and m.fbc is not None:
            form = apply_type_conversion_to_dict({
                'dyn:hasFBC': m.fbc,
                'dyn:hasSEQI': m.seqi,
                'dyn:hasSOI': m.soi,
                'dyn:hasDSUF': m.dsuf,
                'dyn:hasFBCLoading': m.fbc_loading,
                'dyn:hasDSUFLoading': m.dsuf_loading,
                'dyn:hasFBCPlateau': m.fbc_plateau,
                'dyn:hasDSUFPlateau': m.dsuf_plateau,
                'dyn:hasFBCUnloading': m.fbc_unloading,
                'dyn:hasDSUFUnloading': m.dsuf_unloading,
            })
            instance_id = m.equilibrium_metrics_uri.replace('dyn:', '')
            instances['equilibrium_metrics'].append((form, 'dyn:EquilibriumMetrics', instance_id))
