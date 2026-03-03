"""Stage 4 — Science Window Metrics: FBC_30_85, SRCV, RPFI, CCC, NRMSE, ISC.

All metrics computed within the 30%-85% peak stress science window.
"""

import math

import numpy as np

from .dataclasses import MetricValue, ScienceWindow
from . import thresholds as T


def calculate_plateau_fbc(
    stress_1w: np.ndarray,
    stress_3w: np.ndarray,
    science_window: ScienceWindow,
) -> MetricValue:
    """Compute FBC within the 30%-85% peak stress window.

    FBC = 1 - mean(|F_1w - F_3w|) / mean(max(|F_1w|, |F_3w|))
    """
    if science_window is None:
        return MetricValue(
            name="FBC_Plateau", value=float('nan'), unit=None,
            assessment="Skipped", stage=4, category="StructuralEquilibrium",
            skipped=True, skip_reason="No science window",
        )

    s1 = np.abs(stress_1w[science_window.start_idx:science_window.end_idx])
    s3 = np.abs(stress_3w[science_window.start_idx:science_window.end_idx])

    if len(s1) == 0 or len(s3) == 0:
        return MetricValue(
            name="FBC_Plateau", value=float('nan'), unit=None,
            assessment="Skipped", stage=4, category="StructuralEquilibrium",
            skipped=True, skip_reason="Empty science window",
        )

    max_stress = np.maximum(s1, s3)
    denominator = np.mean(max_stress)
    if denominator <= 0:
        return MetricValue(
            name="FBC_Plateau", value=float('nan'), unit=None,
            assessment="Skipped", stage=4, category="StructuralEquilibrium",
            skipped=True, skip_reason="Zero stress in window",
        )

    fbc = 1.0 - np.mean(np.abs(s1 - s3)) / denominator
    fbc = max(0.0, min(1.0, fbc))

    return MetricValue(
        name="FBC_Plateau", value=fbc, unit=None,
        assessment=T.assess_fbc(fbc), stage=4, category="StructuralEquilibrium",
    )


def calculate_strain_rate_cv(
    strain_rate_1w: np.ndarray,
    science_window: ScienceWindow,
) -> MetricValue:
    """Compute SRCV: Strain Rate Coefficient of Variation within science window."""
    if science_window is None or strain_rate_1w is None:
        return MetricValue(
            name="SRCV", value=float('nan'), unit=None,
            assessment="Skipped", stage=4, category="ProcessStability",
            skipped=True, skip_reason="No science window or strain rate data",
        )

    sr = strain_rate_1w[science_window.start_idx:science_window.end_idx]
    if len(sr) < 10:
        return MetricValue(
            name="SRCV", value=float('nan'), unit=None,
            assessment="Skipped", stage=4, category="ProcessStability",
            skipped=True, skip_reason="Insufficient data in window",
        )

    mean_sr = np.mean(np.abs(sr))
    if mean_sr <= 0:
        return MetricValue(
            name="SRCV", value=float('nan'), unit=None,
            assessment="Skipped", stage=4, category="ProcessStability",
            skipped=True, skip_reason="Zero mean strain rate",
        )

    srcv = np.std(sr) / mean_sr

    return MetricValue(
        name="SRCV", value=srcv, unit=None,
        assessment=T.assess_srcv(srcv), stage=4, category="ProcessStability",
    )


def calculate_reflected_flatness(
    aligned_reflected: np.ndarray,
    science_window: ScienceWindow,
) -> list[MetricValue]:
    """Compute RPFI_trend and RPFI_noise within science window.

    RPFI_trend = |m_linear| / mean(eps_r)
    RPFI_noise = std(residuals) / mean(eps_r)
    """
    if science_window is None or aligned_reflected is None:
        return [
            MetricValue(name="RPFI_trend", value=float('nan'), unit=None,
                        assessment="Skipped", stage=4, category="ProcessStability",
                        skipped=True, skip_reason="No data"),
            MetricValue(name="RPFI_noise", value=float('nan'), unit=None,
                        assessment="Skipped", stage=4, category="ProcessStability",
                        skipped=True, skip_reason="No data"),
        ]

    ref = aligned_reflected[science_window.start_idx:science_window.end_idx]
    if len(ref) < 10:
        return [
            MetricValue(name="RPFI_trend", value=float('nan'), unit=None,
                        assessment="Skipped", stage=4, category="ProcessStability",
                        skipped=True, skip_reason="Insufficient data"),
            MetricValue(name="RPFI_noise", value=float('nan'), unit=None,
                        assessment="Skipped", stage=4, category="ProcessStability",
                        skipped=True, skip_reason="Insufficient data"),
        ]

    mean_ref = np.mean(np.abs(ref))
    if mean_ref <= 0:
        return [
            MetricValue(name="RPFI_trend", value=float('nan'), unit=None,
                        assessment="Skipped", stage=4, category="ProcessStability",
                        skipped=True, skip_reason="Zero mean reflected strain"),
            MetricValue(name="RPFI_noise", value=float('nan'), unit=None,
                        assessment="Skipped", stage=4, category="ProcessStability",
                        skipped=True, skip_reason="Zero mean reflected strain"),
        ]

    x = np.arange(len(ref))
    coeffs = np.polyfit(x, ref, 1)
    slope = coeffs[0]
    trend = abs(slope) * len(ref) / mean_ref  # normalized trend over window
    residuals = ref - np.polyval(coeffs, x)
    noise = np.std(residuals) / mean_ref

    trend_assessment = "Good" if trend < T.RPFI_GOOD else (
        "Acceptable" if trend < T.RPFI_ACCEPTABLE else "SignificantTrend")
    noise_assessment = "Good" if noise < T.RPFI_GOOD else (
        "Acceptable" if noise < T.RPFI_ACCEPTABLE else "SignificantNoise")

    return [
        MetricValue(name="RPFI_trend", value=trend, unit=None,
                    assessment=trend_assessment, stage=4, category="ProcessStability"),
        MetricValue(name="RPFI_noise", value=noise, unit=None,
                    assessment=noise_assessment, stage=4, category="ProcessStability"),
    ]


def calculate_concordance(
    stress_1w: np.ndarray,
    stress_3w: np.ndarray,
    science_window: ScienceWindow,
) -> list[MetricValue]:
    """Compute CCC (Lin's Concordance) and NRMSE within science window.

    CCC = 2*r*s1*s3 / (s1² + s3² + (mu1 - mu3)²)
    NRMSE = sqrt(mean((s1 - s3)²)) / mean(s3)
    """
    if science_window is None:
        return [
            MetricValue(name="CCC", value=float('nan'), unit=None,
                        assessment="Skipped", stage=4, category="ProcessStability",
                        skipped=True, skip_reason="No science window"),
            MetricValue(name="NRMSE", value=float('nan'), unit=None,
                        assessment="Skipped", stage=4, category="ProcessStability",
                        skipped=True, skip_reason="No science window"),
        ]

    s1 = stress_1w[science_window.start_idx:science_window.end_idx]
    s3 = stress_3w[science_window.start_idx:science_window.end_idx]

    if len(s1) < 10 or len(s3) < 10:
        return [
            MetricValue(name="CCC", value=float('nan'), unit=None,
                        assessment="Skipped", stage=4, category="ProcessStability",
                        skipped=True, skip_reason="Insufficient data"),
            MetricValue(name="NRMSE", value=float('nan'), unit=None,
                        assessment="Skipped", stage=4, category="ProcessStability",
                        skipped=True, skip_reason="Insufficient data"),
        ]

    mu1, mu3 = np.mean(s1), np.mean(s3)
    sd1, sd3 = np.std(s1), np.std(s3)

    if sd1 <= 0 or sd3 <= 0:
        ccc_val = 0.0
    else:
        r = np.corrcoef(s1, s3)[0, 1]
        if math.isnan(r):
            r = 0.0
        ccc_val = (2.0 * r * sd1 * sd3) / (sd1**2 + sd3**2 + (mu1 - mu3)**2)

    mean_s3 = np.mean(np.abs(s3))
    if mean_s3 > 0:
        nrmse_val = math.sqrt(np.mean((s1 - s3)**2)) / mean_s3
    else:
        nrmse_val = float('nan')

    nrmse_assessment = "Good" if nrmse_val < T.NRMSE_GOOD else (
        "Acceptable" if nrmse_val < T.NRMSE_ACCEPTABLE else "SignificantDisagreement")

    return [
        MetricValue(name="CCC", value=ccc_val, unit=None,
                    assessment=T.assess_ccc(ccc_val), stage=4, category="ProcessStability"),
        MetricValue(name="NRMSE", value=nrmse_val, unit=None,
                    assessment=nrmse_assessment, stage=4, category="ProcessStability"),
    ]


def calculate_inertia_contribution(
    strain_rate_1w: np.ndarray,
    stress_1w: np.ndarray,
    time: np.ndarray,
    science_window: ScienceWindow,
    specimen_density: float | None,
    specimen_diameter: float,
    specimen_length: float,
) -> MetricValue:
    """Compute ISC: max inertia stress contribution within science window.

    sigma_inertia(t) = rho_s * a² * eps_ddot / 8 + rho_s * L² * eps_ddot / 6
    ISC = max(sigma_inertia / sigma_measured) within window
    """
    if (science_window is None or specimen_density is None or
            strain_rate_1w is None or stress_1w is None):
        return MetricValue(
            name="ISC", value=float('nan'), unit=None,
            assessment="Skipped", stage=4, category="Conservation",
            skipped=True, skip_reason="Missing required data",
        )

    if specimen_density <= 0 or specimen_diameter <= 0 or specimen_length <= 0:
        return MetricValue(
            name="ISC", value=float('nan'), unit=None,
            assessment="Skipped", stage=4, category="Conservation",
            skipped=True, skip_reason="Invalid specimen geometry",
        )

    sr = strain_rate_1w[science_window.start_idx:science_window.end_idx]
    stress = np.abs(stress_1w[science_window.start_idx:science_window.end_idx])

    if len(sr) < 10:
        return MetricValue(
            name="ISC", value=float('nan'), unit=None,
            assessment="Skipped", stage=4, category="Conservation",
            skipped=True, skip_reason="Insufficient data in window",
        )

    # Compute strain acceleration (d(strain_rate)/dt)
    dt = time[1] - time[0] if len(time) > 1 else 1.0
    dt_sec = dt * 1e-3  # ms -> s
    eps_ddot = np.gradient(sr, dt_sec)  # 1/s²

    # rho in g/cm³ -> kg/m³ = rho * 1000
    # a (radius) in mm -> m = a * 1e-3
    # L in mm -> m = L * 1e-3
    rho_kg_m3 = specimen_density * 1000.0
    a_m = (specimen_diameter / 2.0) * 1e-3
    l_m = specimen_length * 1e-3

    # sigma_inertia in Pa, stress is in MPa
    sigma_inertia_pa = rho_kg_m3 * a_m**2 * eps_ddot / 8.0 + rho_kg_m3 * l_m**2 * eps_ddot / 6.0
    sigma_inertia_mpa = np.abs(sigma_inertia_pa) * 1e-6

    # ISC = max ratio where stress is significant
    peak_stress = np.max(stress)
    if peak_stress <= 0:
        return MetricValue(
            name="ISC", value=float('nan'), unit=None,
            assessment="Skipped", stage=4, category="Conservation",
            skipped=True, skip_reason="Zero stress in window",
        )

    valid = stress > 0.1 * peak_stress
    if not np.any(valid):
        return MetricValue(
            name="ISC", value=0.0, unit=None,
            assessment="NegligibleInertia", stage=4, category="Conservation",
        )

    isc_ratio = sigma_inertia_mpa[valid] / stress[valid]
    isc_max = float(np.max(isc_ratio))

    return MetricValue(
        name="ISC", value=isc_max, unit=None,
        assessment=T.assess_isc(isc_max), stage=4, category="Conservation",
    )
