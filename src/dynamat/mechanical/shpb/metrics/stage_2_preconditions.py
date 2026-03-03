"""Stage 2 — Pre-Conditions: GDI, IMR, DSI, SRI.

Geometric and impedance checks derived from test setup metadata.
Always computable regardless of Stage 0 status.
"""

import math

import numpy as np

from .dataclasses import MetricValue
from . import thresholds as T


def calculate_geometry_deviation(
    specimen_length: float,
    specimen_diameter: float,
    specimen_poissons_ratio: float | None,
) -> MetricValue:
    """Compute Geometry Deviation Index (GDI).

    GDI = (L/D)_actual / (L/D)_optimal
    where (L/D)_optimal = sqrt(3*nu/4)

    Args:
        specimen_length: Specimen length (mm).
        specimen_diameter: Specimen diameter (mm).
        specimen_poissons_ratio: Poisson's ratio (dimensionless). Defaults to 0.33 if None.
    """
    if specimen_diameter <= 0 or specimen_length <= 0:
        return MetricValue(
            name="GDI", value=float('nan'), unit=None,
            assessment="Skipped", stage=2, category="SetupValidation",
            skipped=True, skip_reason="Invalid specimen dimensions",
        )

    nu = specimen_poissons_ratio if specimen_poissons_ratio is not None else 0.33
    ld_actual = specimen_length / specimen_diameter
    ld_optimal = math.sqrt(3.0 * nu / 4.0)

    if ld_optimal <= 0:
        return MetricValue(
            name="GDI", value=float('nan'), unit=None,
            assessment="Skipped", stage=2, category="SetupValidation",
            skipped=True, skip_reason="Invalid Poisson's ratio",
        )

    gdi = ld_actual / ld_optimal

    return MetricValue(
        name="GDI", value=gdi, unit=None,
        assessment=T.assess_gdi(gdi), stage=2, category="SetupValidation",
        context={"poissons_ratio_used": nu, "ld_actual": ld_actual, "ld_optimal": ld_optimal},
    )


def calculate_impedance_ratio(
    specimen_density: float | None,
    specimen_wave_speed: float | None,
    specimen_area: float,
    specimen_elastic_modulus: float | None,
    bar_density: float,
    bar_wave_speed: float,
    bar_area: float,
) -> MetricValue:
    """Compute Impedance Mismatch Ratio (IMR).

    beta = (rho_s * c_s * A_s) / (rho_b * c_b * A_b)

    If specimen_wave_speed is not provided, derives from E/rho.
    """
    # Derive specimen wave speed if not directly available
    c_s = specimen_wave_speed
    rho_s = specimen_density

    if c_s is None and specimen_elastic_modulus is not None and rho_s is not None and rho_s > 0:
        # c = sqrt(E / rho), E in MPa, rho in g/cm³
        # Convert: E (MPa) = E (N/mm²), rho (g/cm³) = rho * 1e-3 (kg/mm³)...
        # Actually: c (m/s) = sqrt(E_Pa / rho_kg_m3)
        # E_Pa = E_MPa * 1e6, rho_kg_m3 = rho_g_cm3 * 1000
        e_pa = specimen_elastic_modulus * 1e6
        rho_kg_m3 = rho_s * 1000
        c_s = math.sqrt(e_pa / rho_kg_m3)

    if c_s is None or rho_s is None or rho_s <= 0 or c_s <= 0:
        return MetricValue(
            name="IMR", value=float('nan'), unit=None,
            assessment="Skipped", stage=2, category="SetupValidation",
            skipped=True, skip_reason="Specimen density or wave speed unavailable",
        )

    if bar_density <= 0 or bar_wave_speed <= 0 or bar_area <= 0:
        return MetricValue(
            name="IMR", value=float('nan'), unit=None,
            assessment="Skipped", stage=2, category="SetupValidation",
            skipped=True, skip_reason="Invalid bar properties",
        )

    z_specimen = rho_s * c_s * specimen_area
    z_bar = bar_density * bar_wave_speed * bar_area

    # Unit reconciliation: rho in g/cm³, c in m/s, A in mm²
    # Z = rho * c * A -> the units don't matter for the ratio since both use same units
    imr = z_specimen / z_bar

    return MetricValue(
        name="IMR", value=imr, unit=None,
        assessment=T.assess_imr(imr), stage=2, category="SetupValidation",
    )


def calculate_dispersion_severity(
    bar_diameter: float,
    bar_wave_speed: float,
    aligned_incident: np.ndarray,
    time: np.ndarray,
) -> MetricValue:
    """Compute Dispersion Severity Index (DSI).

    DSI = d_bar / lambda_dominant
    where lambda_dominant = c_bar * t_rise
    t_rise = time from 10% to 90% of peak incident pulse.
    """
    if bar_diameter <= 0 or bar_wave_speed <= 0:
        return MetricValue(
            name="DSI", value=float('nan'), unit=None,
            assessment="Skipped", stage=2, category="SetupValidation",
            skipped=True, skip_reason="Invalid bar diameter or wave speed",
        )

    if aligned_incident is None or len(aligned_incident) < 10:
        return MetricValue(
            name="DSI", value=float('nan'), unit=None,
            assessment="Skipped", stage=2, category="SetupValidation",
            skipped=True, skip_reason="No incident pulse data",
        )

    # Compute rise time (10% to 90% of peak)
    abs_inc = np.abs(aligned_incident)
    peak = np.max(abs_inc)
    if peak <= 0:
        return MetricValue(
            name="DSI", value=float('nan'), unit=None,
            assessment="Skipped", stage=2, category="SetupValidation",
            skipped=True, skip_reason="Zero incident pulse amplitude",
        )

    threshold_10 = 0.10 * peak
    threshold_90 = 0.90 * peak

    idx_10 = np.argmax(abs_inc >= threshold_10)
    idx_90 = np.argmax(abs_inc >= threshold_90)

    if idx_90 <= idx_10 or idx_90 >= len(time):
        return MetricValue(
            name="DSI", value=float('nan'), unit=None,
            assessment="Skipped", stage=2, category="SetupValidation",
            skipped=True, skip_reason="Cannot determine pulse rise time",
        )

    # Rise time in the same time units as the time vector
    dt = time[1] - time[0] if len(time) > 1 else 1.0
    t_rise = (idx_90 - idx_10) * dt  # in ms (assuming time in ms)
    t_rise_sec = t_rise * 1e-3  # convert to seconds

    if t_rise_sec <= 0:
        return MetricValue(
            name="DSI", value=float('nan'), unit=None,
            assessment="Skipped", stage=2, category="SetupValidation",
            skipped=True, skip_reason="Zero rise time",
        )

    # lambda_dominant = c_bar (m/s) * t_rise (s) -> meters
    lambda_dom = bar_wave_speed * t_rise_sec  # meters
    # bar_diameter in mm -> convert to meters
    d_bar_m = bar_diameter / 1000.0
    dsi = d_bar_m / lambda_dom

    return MetricValue(
        name="DSI", value=dsi, unit=None,
        assessment=T.assess_dsi(dsi), stage=2, category="SetupValidation",
        context={"rise_time_ms": t_rise, "lambda_dominant_m": lambda_dom},
    )


def calculate_secondary_reflection(
    gauge_to_free_end: float | None,
    bar_wave_speed: float,
    striker_length: float,
) -> MetricValue:
    """Compute Secondary Reflection Index (SRI).

    SRI = t_secondary / t_pulse
    where t_secondary = 2 * d_free / c_bar, t_pulse = 2 * L_striker / c_bar

    Simplifies to: SRI = d_free / L_striker
    """
    if gauge_to_free_end is None:
        return MetricValue(
            name="SRI", value=float('nan'), unit=None,
            assessment="Skipped", stage=2, category="SetupValidation",
            skipped=True, skip_reason="Gauge-to-free-end distance unavailable",
        )

    if striker_length <= 0:
        return MetricValue(
            name="SRI", value=float('nan'), unit=None,
            assessment="Skipped", stage=2, category="SetupValidation",
            skipped=True, skip_reason="Invalid striker length",
        )

    sri = gauge_to_free_end / striker_length

    return MetricValue(
        name="SRI", value=sri, unit=None,
        assessment=T.assess_sri(sri), stage=2, category="SetupValidation",
    )
