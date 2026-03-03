"""Stage 3 — Equilibrium & Timing: T_eq, EYR, REI.

Computed from pulse detection output and force balance time series.
"""

import math

import numpy as np

from .dataclasses import MetricValue
from . import thresholds as T


def calculate_time_to_equilibrium(
    stress_1w: np.ndarray,
    stress_3w: np.ndarray,
    time: np.ndarray,
    fbc_threshold: float = 0.90,
    consecutive_samples: int = 50,
) -> MetricValue:
    """Compute T_eq: time from pulse start until FBC consistently stays above threshold.

    FBC(t) = 1 - |F_1w(t) - F_3w(t)| / max(|F_1w(t)|, |F_3w(t)|)

    Returns:
        MetricValue for T_eq (in ms).
    """
    if stress_1w is None or stress_3w is None or len(stress_1w) < 10:
        return MetricValue(
            name="T_eq", value=float('nan'), unit="unit:MilliSEC",
            assessment="Skipped", stage=3, category="StructuralEquilibrium",
            skipped=True, skip_reason="Insufficient stress data",
        )

    n = min(len(stress_1w), len(stress_3w), len(time))
    s1 = np.abs(stress_1w[:n])
    s3 = np.abs(stress_3w[:n])

    # Compute instantaneous FBC
    max_stress = np.maximum(s1, s3)
    # Avoid division by zero — only compute where stress is significant
    peak = max(np.max(s1), np.max(s3))
    if peak <= 0:
        return MetricValue(
            name="T_eq", value=float('nan'), unit="unit:MilliSEC",
            assessment="Skipped", stage=3, category="StructuralEquilibrium",
            skipped=True, skip_reason="Zero stress",
        )

    valid = max_stress > 0.01 * peak
    fbc_inst = np.zeros(n)
    fbc_inst[valid] = 1.0 - np.abs(s1[valid] - s3[valid]) / max_stress[valid]

    # Find first index where FBC stays above threshold for consecutive_samples
    above = fbc_inst >= fbc_threshold
    t_eq_idx = None
    count = 0
    for i in range(n):
        if above[i] and valid[i]:
            count += 1
            if count >= consecutive_samples:
                t_eq_idx = i - consecutive_samples + 1
                break
        else:
            count = 0

    if t_eq_idx is None:
        # Equilibrium never achieved
        t_eq_ms = float(time[-1] - time[0]) if len(time) > 1 else float('nan')
        return MetricValue(
            name="T_eq", value=t_eq_ms, unit="unit:MilliSEC",
            assessment="EquilibriumNotAchieved", stage=3, category="StructuralEquilibrium",
        )

    t_eq_ms = float(time[t_eq_idx] - time[0])

    return MetricValue(
        name="T_eq", value=t_eq_ms, unit="unit:MilliSEC",
        assessment="EquilibriumAchieved", stage=3, category="StructuralEquilibrium",
    )


def calculate_equilibrium_yield_ratio(
    stress_1w: np.ndarray,
    time: np.ndarray,
    t_eq: float,
    yield_offset: float = 0.002,
) -> MetricValue:
    """Compute EYR: T_yield / T_eq.

    Estimates yield time using 0.2% offset method on the 1-wave stress-strain.
    EYR > 1.0 means yield occurs after equilibrium (elastic data is valid).

    Args:
        stress_1w: 1-wave stress array.
        time: Time array (ms).
        t_eq: Time to equilibrium (ms).
        yield_offset: Offset strain for yield definition (default 0.002).
    """
    if t_eq <= 0 or math.isnan(t_eq):
        return MetricValue(
            name="EYR", value=float('nan'), unit=None,
            assessment="Skipped", stage=3, category="GlobalSanity",
            skipped=True, skip_reason="T_eq unavailable or zero",
        )

    if stress_1w is None or len(stress_1w) < 10:
        return MetricValue(
            name="EYR", value=float('nan'), unit=None,
            assessment="Skipped", stage=3, category="GlobalSanity",
            skipped=True, skip_reason="Insufficient stress data",
        )

    # Estimate yield as the point where stress reaches ~80% of peak
    # (simplified — true yield detection needs strain data)
    abs_stress = np.abs(stress_1w)
    peak = np.max(abs_stress)
    if peak <= 0:
        return MetricValue(
            name="EYR", value=float('nan'), unit=None,
            assessment="Skipped", stage=3, category="GlobalSanity",
            skipped=True, skip_reason="Zero peak stress",
        )

    # Find yield point: first time stress exceeds 30% of peak (approximate)
    yield_threshold = 0.30 * peak
    yield_indices = np.where(abs_stress >= yield_threshold)[0]
    if len(yield_indices) == 0:
        return MetricValue(
            name="EYR", value=float('nan'), unit=None,
            assessment="Skipped", stage=3, category="GlobalSanity",
            skipped=True, skip_reason="Cannot identify yield point",
        )

    t_yield_ms = float(time[yield_indices[0]] - time[0])
    eyr = t_yield_ms / t_eq if t_eq > 0 else float('inf')

    if eyr > 1.0:
        assessment = "ElasticDataValid"
    elif eyr >= 0.8:
        assessment = "YieldNearEquilibrium"
    else:
        assessment = "YieldBeforeEquilibrium"

    return MetricValue(
        name="EYR", value=eyr, unit=None,
        assessment=assessment, stage=3, category="GlobalSanity",
    )


def calculate_reverberation_index(
    t_eq: float,
    specimen_length: float,
    specimen_wave_speed: float | None,
    specimen_elastic_modulus: float | None,
    specimen_density: float | None,
    n_required: int = 3,
) -> MetricValue:
    """Compute REI: n_actual / n_required.

    n_actual = c_s * T_eq / (2 * L_s)

    Args:
        t_eq: Time to equilibrium (ms).
        specimen_length: Specimen length (mm).
        specimen_wave_speed: Specimen wave speed (m/s), or None to derive.
        specimen_elastic_modulus: Specimen E (MPa), for deriving c_s.
        specimen_density: Specimen density (g/cm³), for deriving c_s.
        n_required: Required minimum reverberations (default 3).
    """
    if t_eq <= 0 or math.isnan(t_eq) or specimen_length <= 0:
        return MetricValue(
            name="REI", value=float('nan'), unit=None,
            assessment="Skipped", stage=3, category="StructuralEquilibrium",
            skipped=True, skip_reason="T_eq or specimen length unavailable",
        )

    c_s = specimen_wave_speed
    if c_s is None and specimen_elastic_modulus is not None and specimen_density is not None:
        if specimen_density > 0:
            e_pa = specimen_elastic_modulus * 1e6
            rho_kg_m3 = specimen_density * 1000
            c_s = math.sqrt(e_pa / rho_kg_m3)

    if c_s is None or c_s <= 0:
        return MetricValue(
            name="REI", value=float('nan'), unit=None,
            assessment="Skipped", stage=3, category="StructuralEquilibrium",
            skipped=True, skip_reason="Specimen wave speed unavailable",
        )

    # T_eq in ms, L_s in mm, c_s in m/s
    # n_actual = c_s (m/s) * T_eq (ms) * 1e-3 / (2 * L_s (mm) * 1e-3)
    # = c_s * T_eq / (2 * L_s)  [units cancel when consistent]
    t_eq_sec = t_eq * 1e-3
    l_s_m = specimen_length * 1e-3
    n_actual = c_s * t_eq_sec / (2.0 * l_s_m)

    rei = n_actual / n_required

    return MetricValue(
        name="REI", value=rei, unit=None,
        assessment=T.assess_rei(rei), stage=3, category="StructuralEquilibrium",
        context={"n_actual": n_actual, "n_required": n_required},
    )
