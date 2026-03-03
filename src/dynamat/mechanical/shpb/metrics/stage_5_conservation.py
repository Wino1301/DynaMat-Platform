"""Stage 5 — Conservation: E_bal, MCI, EAE, KEI, DOR (from EPR), SPC.

Full-pulse integration metrics for energy and momentum conservation.
"""

import math

import numpy as np

from .dataclasses import MetricValue
from . import thresholds as T


def _wave_energy(strain: np.ndarray, bar_area: float, bar_wave_speed: float,
                 bar_elastic_modulus: float, dt_sec: float) -> float:
    """Compute wave energy: E = A_b * c_b * E_b * integral(eps²) * dt.

    Args:
        strain: Strain array (dimensionless).
        bar_area: Bar cross-section (mm²).
        bar_wave_speed: Bar wave speed (m/s).
        bar_elastic_modulus: Bar elastic modulus (MPa).
        dt_sec: Time step (seconds).

    Returns:
        Energy in Joules.
    """
    # E_b in MPa = N/mm², A_b in mm², c_b in m/s = 1000 mm/s
    # E = A_b (mm²) * c_b (mm/s) * E_b (N/mm²) * integral(eps²) * dt (s)
    # = A_b * c_b * E_b * sum(eps²) * dt (with c_b in mm/s)
    c_b_mm = bar_wave_speed * 1000.0  # m/s -> mm/s
    return bar_area * c_b_mm * bar_elastic_modulus * np.sum(strain**2) * dt_sec


def calculate_energy_balance(
    aligned_incident: np.ndarray,
    aligned_reflected: np.ndarray,
    aligned_transmitted: np.ndarray,
    stress_1w: np.ndarray,
    strain_1w: np.ndarray,
    specimen_area: float,
    specimen_length: float,
    bar_area: float,
    bar_wave_speed: float,
    bar_elastic_modulus: float,
    time: np.ndarray,
) -> MetricValue:
    """Compute E_bal: (E_ref + E_trs + W_spec) / E_inc.

    Should be ~1.0 ± 0.1.
    """
    if (aligned_incident is None or aligned_reflected is None or
            aligned_transmitted is None):
        return MetricValue(
            name="E_bal", value=float('nan'), unit=None,
            assessment="Skipped", stage=5, category="Conservation",
            skipped=True, skip_reason="Missing pulse data",
        )

    dt = (time[1] - time[0]) * 1e-3 if len(time) > 1 else 1e-6  # ms -> s

    e_inc = _wave_energy(aligned_incident, bar_area, bar_wave_speed, bar_elastic_modulus, dt)
    e_ref = _wave_energy(aligned_reflected, bar_area, bar_wave_speed, bar_elastic_modulus, dt)
    e_trs = _wave_energy(aligned_transmitted, bar_area, bar_wave_speed, bar_elastic_modulus, dt)

    # Specimen work: W = V_s * integral(sigma * d_epsilon)
    # V_s in mm³, sigma in MPa = N/mm² -> W in N·mm = mJ -> convert to J
    v_s = specimen_area * specimen_length  # mm³
    if stress_1w is not None and strain_1w is not None and len(stress_1w) > 1:
        w_spec = v_s * np.trapz(np.abs(stress_1w), strain_1w) * 1e-3  # mJ -> J... actually N*mm -> mJ
        # N/mm² * mm³ * dimensionless = N*mm = 1e-3 J
        w_spec = v_s * np.trapz(np.abs(stress_1w), strain_1w) * 1e-3
    else:
        w_spec = 0.0

    if e_inc <= 0:
        return MetricValue(
            name="E_bal", value=float('nan'), unit=None,
            assessment="Skipped", stage=5, category="Conservation",
            skipped=True, skip_reason="Zero incident energy",
        )

    e_bal = (e_ref + e_trs + w_spec) / e_inc

    return MetricValue(
        name="E_bal", value=e_bal, unit=None,
        assessment=T.assess_e_bal(e_bal), stage=5, category="Conservation",
        context={"E_inc": e_inc, "E_ref": e_ref, "E_trs": e_trs, "W_spec": w_spec},
    )


def calculate_momentum_conservation(
    aligned_incident: np.ndarray,
    aligned_reflected: np.ndarray,
    aligned_transmitted: np.ndarray,
    bar_elastic_modulus: float,
    bar_area: float,
    specimen_density: float | None,
    specimen_area: float,
    specimen_length: float,
    bar_wave_speed: float,
    time: np.ndarray,
) -> MetricValue:
    """Compute MCI: J_out / (J_in - p_s).

    J_in = E_b * A_b * integral(eps_inc + eps_ref) dt
    J_out = E_b * A_b * integral(eps_trs) dt
    """
    if (aligned_incident is None or aligned_reflected is None or
            aligned_transmitted is None):
        return MetricValue(
            name="MCI", value=float('nan'), unit=None,
            assessment="Skipped", stage=5, category="Conservation",
            skipped=True, skip_reason="Missing pulse data",
        )

    dt = (time[1] - time[0]) * 1e-3 if len(time) > 1 else 1e-6

    # J = E_b (MPa=N/mm²) * A_b (mm²) * integral(eps) * dt (s)
    # = N * integral(eps) * dt -> N*s
    j_in_integrand = aligned_incident + aligned_reflected
    j_in = bar_elastic_modulus * bar_area * np.sum(j_in_integrand) * dt
    j_out = bar_elastic_modulus * bar_area * np.sum(aligned_transmitted) * dt

    # Residual specimen momentum
    # v_s(t_end) = c_b * [eps_inc - eps_ref - eps_trs] at end
    v_residual = bar_wave_speed * (aligned_incident[-1] - aligned_reflected[-1] - aligned_transmitted[-1])
    if specimen_density is not None and specimen_density > 0:
        # mass = rho (g/cm³) * A (mm²) * L (mm) * 1e-3 (cm³/mm³) * 1e-3 (kg/g) = kg
        mass = specimen_density * specimen_area * specimen_length * 1e-6
        p_s = mass * v_residual
    else:
        p_s = 0.0

    denominator = j_in - p_s
    if abs(denominator) < 1e-20:
        return MetricValue(
            name="MCI", value=float('nan'), unit=None,
            assessment="Skipped", stage=5, category="Conservation",
            skipped=True, skip_reason="Zero input impulse",
        )

    mci = j_out / denominator

    return MetricValue(
        name="MCI", value=mci, unit=None,
        assessment=T.assess_mci(mci), stage=5, category="Conservation",
    )


def calculate_energy_absorption(
    e_inc: float,
    w_spec: float,
    material_class: str | None = None,
) -> MetricValue:
    """Compute EAE: W_specimen / E_incident.

    Material-class dependent expected ranges.
    """
    if e_inc <= 0:
        return MetricValue(
            name="EAE", value=float('nan'), unit=None,
            assessment="Skipped", stage=5, category="Conservation",
            skipped=True, skip_reason="Zero incident energy",
        )

    eae = w_spec / e_inc

    # Assess based on material class
    if material_class and material_class.lower() in T.EAE_RANGES:
        low, high = T.EAE_RANGES[material_class.lower()]
        if low <= eae <= high:
            assessment = "ExpectedRange"
        else:
            assessment = "OutsideExpectedRange"
    else:
        assessment = "NoReferenceRange"

    return MetricValue(
        name="EAE", value=eae, unit=None,
        assessment=assessment, stage=5, category="Conservation",
        context={"material_class": material_class},
    )


def calculate_kinetic_energy_index(
    aligned_incident: np.ndarray,
    aligned_reflected: np.ndarray,
    aligned_transmitted: np.ndarray,
    bar_wave_speed: float,
    specimen_density: float | None,
    specimen_area: float,
    specimen_length: float,
    w_spec: float,
) -> MetricValue:
    """Compute KEI: KE_residual / W_specimen.

    KE = 0.5 * m_s * v_s(t_end)²
    v_s = c_b * [eps_inc - eps_ref - eps_trs]
    """
    if (aligned_incident is None or aligned_reflected is None or
            aligned_transmitted is None or specimen_density is None):
        return MetricValue(
            name="KEI", value=float('nan'), unit=None,
            assessment="Skipped", stage=5, category="Conservation",
            skipped=True, skip_reason="Missing data",
        )

    if w_spec <= 0:
        return MetricValue(
            name="KEI", value=float('nan'), unit=None,
            assessment="Skipped", stage=5, category="Conservation",
            skipped=True, skip_reason="Zero specimen work",
        )

    v_residual = bar_wave_speed * (aligned_incident[-1] - aligned_reflected[-1] - aligned_transmitted[-1])
    mass = specimen_density * specimen_area * specimen_length * 1e-6  # kg
    ke = 0.5 * mass * v_residual**2

    kei = abs(ke / w_spec) if w_spec != 0 else float('nan')

    return MetricValue(
        name="KEI", value=kei, unit=None,
        assessment=T.assess_kei(kei), stage=5, category="Conservation",
    )


def calculate_damage_onset(
    aligned_incident: np.ndarray,
    aligned_reflected: np.ndarray,
    aligned_transmitted: np.ndarray,
    strain_1w: np.ndarray,
    bar_area: float,
    bar_wave_speed: float,
    bar_elastic_modulus: float,
    time: np.ndarray,
) -> MetricValue:
    """Compute DOR (Damage Onset Ratio) from EPR analysis.

    DOR = strain at which d(r_abs)/d(epsilon) deviates by >2sigma.
    Returns NaN/skipped if no damage onset detected.
    """
    if (aligned_incident is None or aligned_reflected is None or
            aligned_transmitted is None or strain_1w is None):
        return MetricValue(
            name="DOR", value=float('nan'), unit=None,
            assessment="NoDamageDetected", stage=5, category="Conservation",
            skipped=True, skip_reason="Missing data",
        )

    n = min(len(aligned_incident), len(aligned_reflected),
            len(aligned_transmitted), len(strain_1w))
    if n < 100:
        return MetricValue(
            name="DOR", value=float('nan'), unit=None,
            assessment="Skipped", stage=5, category="Conservation",
            skipped=True, skip_reason="Insufficient data",
        )

    dt = (time[1] - time[0]) * 1e-3 if len(time) > 1 else 1e-6

    # Cumulative energy fractions
    inc2 = np.cumsum(aligned_incident[:n]**2) * dt
    ref2 = np.cumsum(aligned_reflected[:n]**2) * dt
    trs2 = np.cumsum(aligned_transmitted[:n]**2) * dt

    e_inc_cum = inc2 * bar_area * bar_wave_speed * 1000 * bar_elastic_modulus
    e_ref_cum = ref2 * bar_area * bar_wave_speed * 1000 * bar_elastic_modulus
    e_trs_cum = trs2 * bar_area * bar_wave_speed * 1000 * bar_elastic_modulus

    # Absorption ratio
    valid = e_inc_cum > 0
    if not np.any(valid):
        return MetricValue(
            name="DOR", value=float('nan'), unit=None,
            assessment="NoDamageDetected", stage=5, category="Conservation",
        )

    r_abs = np.zeros(n)
    r_abs[valid] = (e_inc_cum[valid] - e_ref_cum[valid] - e_trs_cum[valid]) / e_inc_cum[valid]

    # Compute d(r_abs)/d(strain) and look for 2-sigma deviation
    strain = strain_1w[:n]
    dr = np.gradient(r_abs)
    ds = np.gradient(strain)
    ds[ds == 0] = 1e-20
    dr_ds = dr / ds

    # Running mean and std (window of 200 points)
    window = min(200, n // 5)
    if window < 20:
        return MetricValue(
            name="DOR", value=float('nan'), unit=None,
            assessment="NoDamageDetected", stage=5, category="Conservation",
        )

    running_mean = np.convolve(dr_ds, np.ones(window)/window, mode='valid')
    running_std = np.array([np.std(dr_ds[max(0,i-window):i+1])
                           for i in range(window-1, n)])

    if len(running_std) < 10:
        return MetricValue(
            name="DOR", value=float('nan'), unit=None,
            assessment="NoDamageDetected", stage=5, category="Conservation",
        )

    # Find deviation point
    for i in range(len(running_mean)):
        if running_std[i] > 0 and abs(dr_ds[i + window - 1] - running_mean[i]) > 2 * running_std[i]:
            dor_idx = i + window - 1
            dor_strain = float(strain[dor_idx])
            return MetricValue(
                name="DOR", value=dor_strain, unit=None,
                assessment="DamageOnsetDetected", stage=5, category="Conservation",
            )

    return MetricValue(
        name="DOR", value=float('nan'), unit=None,
        assessment="NoDamageDetected", stage=5, category="Conservation",
    )


def calculate_stress_power_consistency(
    stress_1w: np.ndarray,
    strain_1w: np.ndarray,
    specimen_area: float,
    specimen_length: float,
    e_inc: float,
    e_ref: float,
    e_trs: float,
    ke_residual: float,
) -> MetricValue:
    """Compute SPC: W_A / W_B.

    W_A = V_s * integral(sigma * d_epsilon)
    W_B = E_inc - E_ref - E_trs - KE_residual
    """
    if stress_1w is None or strain_1w is None:
        return MetricValue(
            name="SPC", value=float('nan'), unit=None,
            assessment="Skipped", stage=5, category="Conservation",
            skipped=True, skip_reason="Missing stress-strain data",
        )

    v_s = specimen_area * specimen_length  # mm³
    w_a = v_s * np.trapz(np.abs(stress_1w), strain_1w) * 1e-3  # N*mm -> mJ... simplified

    w_b = e_inc - e_ref - e_trs - ke_residual

    if abs(w_b) < 1e-20:
        return MetricValue(
            name="SPC", value=float('nan'), unit=None,
            assessment="Skipped", stage=5, category="Conservation",
            skipped=True, skip_reason="Zero wave-energy-derived work",
        )

    spc = w_a / w_b

    return MetricValue(
        name="SPC", value=spc, unit=None,
        assessment=T.assess_spc(spc), stage=5, category="Conservation",
    )
