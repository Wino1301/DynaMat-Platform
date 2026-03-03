"""SHPB Contextual Validity Metrics — Pure Python computation layer.

Public API: evaluate_all(), MetricsResult, MetricValue, ScienceWindow.
No RDF imports. All computation receives pre-extracted numpy arrays and scalars.
"""

import math
import logging

import numpy as np

from .dataclasses import MetricValue, MetricsResult, ScienceWindow
from .science_window import compute_science_window
from .stage_0_critical import detect_clipping, check_pulse_separation
from .stage_1_signal import assess_baseline_quality, assess_range_utilization
from .stage_2_preconditions import (
    calculate_geometry_deviation, calculate_impedance_ratio,
    calculate_dispersion_severity, calculate_secondary_reflection,
)
from .stage_3_equilibrium import (
    calculate_time_to_equilibrium, calculate_equilibrium_yield_ratio,
    calculate_reverberation_index,
)
from .stage_4_science import (
    calculate_plateau_fbc, calculate_strain_rate_cv,
    calculate_reflected_flatness, calculate_concordance,
    calculate_inertia_contribution,
)
from .stage_5_conservation import (
    calculate_energy_balance, calculate_momentum_conservation,
    calculate_energy_absorption, calculate_kinetic_energy_index,
    calculate_damage_onset, calculate_stress_power_consistency,
)
from .stage_6_sanity import (
    calculate_transmitted_snr, check_tail_truncation,
    calculate_adiabatic_temperature_rise,
)
from .stage_7_posttest import (
    calculate_volume_conservation, calculate_barreling_index,
    calculate_strain_verification,
)
from .stage_8_annotations import generate_annotations

logger = logging.getLogger(__name__)

__all__ = ['evaluate_all', 'MetricsResult', 'MetricValue', 'ScienceWindow']


def evaluate_all(
    # Stage 0-1: Raw signals (full arrays before windowing)
    raw_signals: dict[str, np.ndarray],
    time: np.ndarray,
    sampling_interval: float,
    # Stage 2: Geometry/setup (pre-extracted scalars)
    specimen_length: float,
    specimen_diameter: float,
    specimen_density: float | None,
    specimen_wave_speed: float | None,
    specimen_elastic_modulus: float | None,
    specimen_poissons_ratio: float | None,
    specimen_specific_heat: float | None,
    bar_diameter: float,
    bar_wave_speed: float,
    bar_elastic_modulus: float,
    bar_density: float,
    bar_area: float,
    specimen_area: float,
    striker_length: float,
    gauge_to_specimen: float,
    gauge_to_free_end: float | None,
    # Stage 3-6: Aligned individual pulse strains
    aligned_incident: np.ndarray,
    aligned_reflected: np.ndarray,
    aligned_transmitted: np.ndarray,
    # Combined results (from StressStrainCalculator)
    stress_1w: np.ndarray,
    stress_3w: np.ndarray,
    strain_1w: np.ndarray,
    strain_3w: np.ndarray,
    strain_rate_1w: np.ndarray,
    strain_rate_3w: np.ndarray,
    bar_force_1w: np.ndarray,
    bar_force_3w: np.ndarray,
    # Pulse boundaries from PulseDetector
    pulse_start_idx: int,
    pulse_end_idx: int,
    # Stage 7: Post-test dimensions (may be None)
    final_length: float | None = None,
    final_diameter: float | None = None,
    # Optional: ADC metadata
    adc_full_scale: float | None = None,
    adc_bits: int | None = None,
    # Optional: material class for EAE range lookup
    material_class: str | None = None,
    # Uncertainty inputs
    specimen_length_unc: float | None = None,
    specimen_diameter_unc: float | None = None,
    final_length_unc: float | None = None,
    final_diameter_unc: float | None = None,
) -> MetricsResult:
    """Evaluate all 29 contextual validity metrics for an SHPB test.

    Stages are evaluated in order with early abort on critical failures.
    Returns a MetricsResult with all computed metrics and annotations.
    """
    metrics: dict[str, MetricValue] = {}
    stages_completed = 0
    critical_failure = False

    def add(m):
        """Add a MetricValue or list of MetricValues to the results."""
        if isinstance(m, list):
            for item in m:
                metrics[item.name] = item
        else:
            metrics[m.name] = m

    # =========================================================================
    # Stage 0 — Critical Pre-Check
    # =========================================================================
    logger.debug("Stage 0: Critical pre-check")
    add(detect_clipping(raw_signals, adc_full_scale, adc_bits))
    add(check_pulse_separation(gauge_to_specimen, bar_wave_speed, striker_length))
    stages_completed = 1

    scd = metrics.get("SCD")
    psc = metrics.get("PSC")
    if (scd and scd.value > 0) or (psc and not psc.skipped and psc.value < 1.0):
        critical_failure = True
        logger.warning("Stage 0 CRITICAL FAILURE — skipping signal-derived stages")

    # =========================================================================
    # Stage 1 — Signal Quality (skip if critical failure)
    # =========================================================================
    if not critical_failure:
        logger.debug("Stage 1: Signal quality")
        add(assess_baseline_quality(raw_signals, pulse_start_idx, adc_full_scale))
        add(assess_range_utilization(raw_signals, adc_full_scale))
        stages_completed = 2

    # =========================================================================
    # Stage 2 — Pre-Conditions (always computable)
    # =========================================================================
    logger.debug("Stage 2: Pre-conditions")
    add(calculate_geometry_deviation(specimen_length, specimen_diameter, specimen_poissons_ratio))
    add(calculate_impedance_ratio(
        specimen_density, specimen_wave_speed, specimen_area,
        specimen_elastic_modulus, bar_density, bar_wave_speed, bar_area,
    ))
    if not critical_failure:
        add(calculate_dispersion_severity(bar_diameter, bar_wave_speed, aligned_incident, time))
    add(calculate_secondary_reflection(gauge_to_free_end, bar_wave_speed, striker_length))
    stages_completed = max(stages_completed, 3)

    # =========================================================================
    # Stage 3 — Equilibrium & Timing (skip if critical failure)
    # =========================================================================
    if not critical_failure:
        logger.debug("Stage 3: Equilibrium & timing")
        t_eq_metric = calculate_time_to_equilibrium(stress_1w, stress_3w, time)
        add(t_eq_metric)

        t_eq_val = t_eq_metric.value if not t_eq_metric.skipped else float('nan')

        add(calculate_equilibrium_yield_ratio(stress_1w, time, t_eq_val))
        add(calculate_reverberation_index(
            t_eq_val, specimen_length, specimen_wave_speed,
            specimen_elastic_modulus, specimen_density,
        ))
        stages_completed = 4

    # =========================================================================
    # Stage 4 — Compute Science Window, then Science Window Metrics
    # =========================================================================
    science_window = None
    if not critical_failure:
        logger.debug("Stage 4: Science window metrics")
        # Use 1-wave stress for window computation
        science_window = compute_science_window(stress_1w, pulse_start_idx, pulse_end_idx)

        add(calculate_plateau_fbc(stress_1w, stress_3w, science_window))
        add(calculate_strain_rate_cv(strain_rate_1w, science_window))
        add(calculate_reflected_flatness(aligned_reflected, science_window))
        add(calculate_concordance(stress_1w, stress_3w, science_window))
        add(calculate_inertia_contribution(
            strain_rate_1w, stress_1w, time, science_window,
            specimen_density, specimen_diameter, specimen_length,
        ))
        stages_completed = 5

    # =========================================================================
    # Stage 5 — Conservation & Energy (skip if critical failure)
    # =========================================================================
    if not critical_failure:
        logger.debug("Stage 5: Conservation")
        e_bal_metric = calculate_energy_balance(
            aligned_incident, aligned_reflected, aligned_transmitted,
            stress_1w, strain_1w, specimen_area, specimen_length,
            bar_area, bar_wave_speed, bar_elastic_modulus, time,
        )
        add(e_bal_metric)

        add(calculate_momentum_conservation(
            aligned_incident, aligned_reflected, aligned_transmitted,
            bar_elastic_modulus, bar_area,
            specimen_density, specimen_area, specimen_length,
            bar_wave_speed, time,
        ))

        # Extract energy values for dependent metrics
        e_ctx = e_bal_metric.context or {}
        e_inc = e_ctx.get('E_inc', 0.0)
        e_ref = e_ctx.get('E_ref', 0.0)
        e_trs = e_ctx.get('E_trs', 0.0)
        w_spec = e_ctx.get('W_spec', 0.0)

        add(calculate_energy_absorption(e_inc, w_spec, material_class))

        kei_metric = calculate_kinetic_energy_index(
            aligned_incident, aligned_reflected, aligned_transmitted,
            bar_wave_speed, specimen_density, specimen_area, specimen_length, w_spec,
        )
        add(kei_metric)

        add(calculate_damage_onset(
            aligned_incident, aligned_reflected, aligned_transmitted,
            strain_1w, bar_area, bar_wave_speed, bar_elastic_modulus, time,
        ))

        # KE_residual for SPC
        ke_residual = 0.0
        if specimen_density is not None and specimen_density > 0:
            v_res = bar_wave_speed * (aligned_incident[-1] - aligned_reflected[-1] - aligned_transmitted[-1])
            mass = specimen_density * specimen_area * specimen_length * 1e-6
            ke_residual = 0.5 * mass * v_res**2

        add(calculate_stress_power_consistency(
            stress_1w, strain_1w, specimen_area, specimen_length,
            e_inc, e_ref, e_trs, ke_residual,
        ))
        stages_completed = 6

    # =========================================================================
    # Stage 6 — Global Sanity (skip signal-derived if critical)
    # =========================================================================
    if not critical_failure:
        logger.debug("Stage 6: Global sanity")
        add(calculate_transmitted_snr(raw_signals, pulse_start_idx, pulse_end_idx))
        add(check_tail_truncation(aligned_transmitted, pulse_end_idx))
        add(calculate_adiabatic_temperature_rise(
            stress_1w, strain_1w, specimen_density, specimen_specific_heat,
        ))
        stages_completed = 7

    # =========================================================================
    # Stage 7 — Post-Test Validation (always computable if dims provided)
    # =========================================================================
    logger.debug("Stage 7: Post-test validation")
    add(calculate_volume_conservation(
        specimen_length, specimen_diameter, final_length, final_diameter,
        specimen_length_unc, specimen_diameter_unc,
        final_length_unc, final_diameter_unc,
    ))
    add(calculate_barreling_index(
        specimen_length, specimen_diameter, final_length, final_diameter,
        final_diameter_unc, final_length_unc,
    ))
    if not critical_failure:
        add(calculate_strain_verification(
            strain_1w, specimen_length, final_length,
            final_length_unc, specimen_length_unc,
        ))
    stages_completed = 8

    # =========================================================================
    # Stage 8 — Annotation Generation
    # =========================================================================
    logger.debug("Stage 8: Generating annotations")
    fitness_annotations, diagnostic_annotations = generate_annotations(metrics)

    return MetricsResult(
        metrics=metrics,
        fitness_annotations=fitness_annotations,
        diagnostic_annotations=diagnostic_annotations,
        critical_failure=critical_failure,
        science_window=science_window,
        evaluation_stages_completed=stages_completed,
    )
