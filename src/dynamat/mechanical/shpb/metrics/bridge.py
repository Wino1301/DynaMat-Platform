"""MetricsBridge: Translates between MetricsResult and DQV form data for InstanceWriter.

Also provides extract_metrics_inputs() to gather evaluate_all() kwargs from analysis state.
"""

import logging
from typing import Any

from .dataclasses import MetricsResult

logger = logging.getLogger(__name__)

DQV = "http://www.w3.org/ns/dqv#"
DYN = "https://dynamat.utep.edu/ontology#"


def metrics_result_to_form_data(result: MetricsResult, test_uri: str) -> dict[str, Any]:
    """Convert MetricsResult to DQV form_data dict for InstanceWriter.

    Returns a dict keyed by full URI strings, with DQV BNode pattern dicts
    as values for hasQualityMeasurement and hasQualityAnnotation.
    """
    form_data = {}

    # Card-level flat metadata
    form_data[f"{DYN}hasCriticalFailure"] = result.critical_failure
    form_data[f"{DYN}hasStagesCompleted"] = result.evaluation_stages_completed
    if result.science_window:
        form_data[f"{DYN}hasScienceWindowStart"] = result.science_window.start_idx
        form_data[f"{DYN}hasScienceWindowEnd"] = result.science_window.end_idx

    # DQV QualityMeasurement BNodes — one per non-skipped metric
    measurements = []
    for name, metric in result.metrics.items():
        if metric.skipped:
            continue
        m = {
            'pattern': 'quality_measurement',
            'metric': f"dyn:Metric_{name}",
            'value': metric.value,
            'computed_on': test_uri,
            'assessment': metric.assessment,
        }
        if metric.unit:
            m['unit'] = metric.unit
        if metric.uncertainty is not None:
            m['uncertainty'] = metric.uncertainty
        # Add window context for science-window metrics (Stage 4)
        if metric.stage == 4:
            m['window'] = "30%-85% peak stress"
        measurements.append(m)
    form_data[f"{DQV}hasQualityMeasurement"] = measurements

    # DQV QualityAnnotation BNodes — one per fitness/diagnostic annotation
    annotations = []
    for ann in result.fitness_annotations + result.diagnostic_annotations:
        annotations.append({
            'pattern': 'quality_annotation',
            'target': test_uri,
            'body': f"dyn:{ann}",
            'motivation': 'dqv:qualityAssessment',
        })
    form_data[f"{DQV}hasQualityAnnotation"] = annotations

    return form_data


def extract_metrics_inputs(state, ontology_manager=None) -> dict:
    """Extract all inputs needed by evaluate_all() from SHPBAnalysisState.

    Uses: state.equipment_properties, state.specimen_data,
          state.calculation_results, state.pulse_windows,
          state.aligned_pulses, state.tapered_pulses, etc.

    Returns:
        kwargs dict for evaluate_all().
    """
    from dynamat.mechanical.shpb.io.rdf_helpers import extract_numeric_value

    equipment = state.equipment_properties or {}
    specimen = state.specimen_data or {}

    # Bar properties (from incident bar — primary bar for calculations)
    inc_bar = equipment.get('incident_bar', {})
    striker = equipment.get('striker_bar', {})
    inc_gauge = equipment.get('incident_gauge', {})

    bar_wave_speed = inc_bar.get('wave_speed', 0.0) or 0.0
    bar_elastic_modulus = inc_bar.get('elastic_modulus', 0.0) or 0.0
    bar_diameter = inc_bar.get('diameter', 0.0) or 0.0
    bar_area = inc_bar.get('cross_section', 0.0) or 0.0
    striker_length = striker.get('length', 0.0) or 0.0
    gauge_to_specimen = inc_gauge.get('distance_from_specimen', 0.0) or 0.0

    # Bar density: SPARQL lookup via bar material_uri
    bar_density = _lookup_bar_density(inc_bar.get('material_uri'), ontology_manager)

    # Gauge-to-free-end: derived from incident bar length - gauge distance
    inc_bar_length = inc_bar.get('length')
    gauge_to_free_end = None
    if inc_bar_length and gauge_to_specimen:
        gauge_to_free_end = inc_bar_length - gauge_to_specimen

    # Specimen properties
    specimen_length = extract_numeric_value(specimen.get(f'{DYN}hasOriginalHeight')) or 0.0
    specimen_diameter = extract_numeric_value(specimen.get(f'{DYN}hasOriginalDiameter')) or 0.0
    specimen_area = extract_numeric_value(specimen.get(f'{DYN}hasOriginalCrossSection')) or 0.0

    # Specimen material properties (from material sub-dict or direct keys)
    material = specimen.get('material', {})
    specimen_density = _get_material_prop(material, specimen, 'hasDensity')
    specimen_wave_speed = _get_material_prop(material, specimen, 'hasWaveSpeed')
    specimen_elastic_modulus = _get_material_prop(material, specimen, 'hasElasticModulus')
    specimen_poissons_ratio = _get_material_prop(material, specimen, 'hasPoissonsRatio')
    specimen_specific_heat = _get_material_prop(material, specimen, 'hasSpecificHeat')

    # Aligned pulses (prefer tapered if available, else aligned)
    pulses = state.tapered_pulses if state.tapered_pulses else state.aligned_pulses
    aligned_incident = pulses.get('incident')
    aligned_reflected = pulses.get('reflected')
    aligned_transmitted = pulses.get('transmitted')

    # Calculation results
    results = state.calculation_results or {}
    stress_1w = results.get('stress_1w')
    stress_3w = results.get('stress_3w')
    strain_1w = results.get('strain_1w')
    strain_3w = results.get('strain_3w')
    strain_rate_1w = results.get('strain_rate_1w')
    strain_rate_3w = results.get('strain_rate_3w')
    bar_force_1w = results.get('bar_force_1w')
    bar_force_3w = results.get('bar_force_3w')
    time = results.get('time', state.time_vector)

    # Raw signals for Stage 0-1
    raw_signals = {}
    if state.raw_df is not None:
        for sig_type in ['incident', 'transmitted', 'reflected']:
            arr = state.get_raw_signal(sig_type)
            if arr is not None:
                raw_signals[sig_type] = arr

    # Pulse boundaries from detection
    pulse_start_idx = 0
    pulse_end_idx = len(stress_1w) if stress_1w is not None else 0
    # Use incident detection window as pulse boundaries
    inc_window = state.pulse_windows.get('incident')
    if inc_window:
        pulse_start_idx = inc_window[0]
        pulse_end_idx = inc_window[1]

    # Post-test dimensions (may be None)
    final_length = extract_numeric_value(specimen.get(f'{DYN}hasFinalLength'))
    final_diameter = extract_numeric_value(specimen.get(f'{DYN}hasFinalDiameter'))

    # Uncertainty extraction
    def _get_unc(key):
        val = specimen.get(key)
        if isinstance(val, dict):
            return val.get('uncertainty')
        return None

    # Determine material class from rdf:type
    material_class = _infer_material_class(material, specimen)

    import numpy as np
    return {
        'raw_signals': raw_signals,
        'time': time if time is not None else np.array([]),
        'sampling_interval': state.sampling_interval or 0.001,
        'specimen_length': specimen_length,
        'specimen_diameter': specimen_diameter,
        'specimen_density': specimen_density,
        'specimen_wave_speed': specimen_wave_speed,
        'specimen_elastic_modulus': specimen_elastic_modulus,
        'specimen_poissons_ratio': specimen_poissons_ratio,
        'specimen_specific_heat': specimen_specific_heat,
        'bar_diameter': bar_diameter,
        'bar_wave_speed': bar_wave_speed,
        'bar_elastic_modulus': bar_elastic_modulus,
        'bar_density': bar_density,
        'bar_area': bar_area,
        'specimen_area': specimen_area,
        'striker_length': striker_length,
        'gauge_to_specimen': gauge_to_specimen,
        'gauge_to_free_end': gauge_to_free_end,
        'aligned_incident': aligned_incident if aligned_incident is not None else np.array([]),
        'aligned_reflected': aligned_reflected if aligned_reflected is not None else np.array([]),
        'aligned_transmitted': aligned_transmitted if aligned_transmitted is not None else np.array([]),
        'stress_1w': stress_1w if stress_1w is not None else np.array([]),
        'stress_3w': stress_3w if stress_3w is not None else np.array([]),
        'strain_1w': strain_1w if strain_1w is not None else np.array([]),
        'strain_3w': strain_3w if strain_3w is not None else np.array([]),
        'strain_rate_1w': strain_rate_1w if strain_rate_1w is not None else np.array([]),
        'strain_rate_3w': strain_rate_3w if strain_rate_3w is not None else np.array([]),
        'bar_force_1w': bar_force_1w if bar_force_1w is not None else np.array([]),
        'bar_force_3w': bar_force_3w if bar_force_3w is not None else np.array([]),
        'pulse_start_idx': pulse_start_idx,
        'pulse_end_idx': pulse_end_idx,
        'final_length': final_length,
        'final_diameter': final_diameter,
        'material_class': material_class,
        'specimen_length_unc': _get_unc(f'{DYN}hasOriginalHeight'),
        'specimen_diameter_unc': _get_unc(f'{DYN}hasOriginalDiameter'),
        'final_length_unc': _get_unc(f'{DYN}hasFinalLength'),
        'final_diameter_unc': _get_unc(f'{DYN}hasFinalDiameter'),
    }


def _lookup_bar_density(material_uri: str | None, ontology_manager) -> float:
    """Look up bar density from material individual via SPARQL."""
    if not material_uri or not ontology_manager:
        # Fallback: C350 Maraging Steel (most common SHPB bar material)
        return 8.0825

    try:
        from dynamat.mechanical.shpb.io.specimen_loader import SpecimenLoader
        loader = SpecimenLoader(ontology_manager)
        density = loader.get_individual_property(material_uri, 'hasDensity', float)
        if density is not None:
            return density
    except Exception as e:
        logger.debug(f"Could not look up bar density: {e}")

    return 8.0825  # Default C350


def _get_material_prop(material_dict: dict, specimen_dict: dict, prop_name: str):
    """Get material property from material sub-dict or specimen dict."""
    from dynamat.mechanical.shpb.io.rdf_helpers import extract_numeric_value

    # Try material sub-dict first
    val = material_dict.get(prop_name)
    if val is not None:
        return extract_numeric_value(val)

    # Try full URI key in specimen dict
    val = specimen_dict.get(f'{DYN}{prop_name}')
    if val is not None:
        return extract_numeric_value(val)

    return None


def _infer_material_class(material_dict: dict, specimen_dict: dict) -> str | None:
    """Infer material class from rdf:type or material name."""
    # Check for rdf:type info
    types = material_dict.get('types', [])
    if isinstance(types, list):
        for t in types:
            t_lower = str(t).lower()
            if 'aluminium' in t_lower or 'aluminum' in t_lower:
                return 'metal'
            if 'steel' in t_lower:
                return 'metal'
            if 'polymer' in t_lower:
                return 'polymer'
            if 'ceramic' in t_lower:
                return 'ceramic'
            if 'composite' in t_lower:
                return 'composite'

    # Fallback: check material name/code
    for key in ['hasMaterialName', 'hasMaterialCode', 'name']:
        name = material_dict.get(key, '')
        if name:
            name_lower = str(name).lower()
            if any(kw in name_lower for kw in ['al', 'aluminum', 'aluminium']):
                return 'metal'
            if any(kw in name_lower for kw in ['steel', 'ss', 'maraging']):
                return 'metal'
            if any(kw in name_lower for kw in ['copper', 'cu']):
                return 'metal'

    return None
