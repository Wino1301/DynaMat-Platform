"""Stage 6 — Global Sanity: SNR_trs, Tail Truncation, ATR.

Broad sanity checks including transmitted signal quality, signal completeness,
and adiabatic temperature rise estimation.
"""

import math

import numpy as np

from .dataclasses import MetricValue
from . import thresholds as T


def calculate_transmitted_snr(
    raw_signals: dict[str, np.ndarray],
    pulse_start_idx: int,
    pulse_end_idx: int,
) -> MetricValue:
    """Compute SNR_trs: Transmitted signal-to-noise ratio in dB.

    SNR = 10 * log10(signal_power / noise_power)
    Noise is measured from the pre-trigger region.
    """
    signal = raw_signals.get('transmitted')
    if signal is None or len(signal) == 0:
        return MetricValue(
            name="SNR_trs", value=float('nan'), unit="unit:DeciB",
            assessment="Skipped", stage=6, category="GlobalSanity",
            skipped=True, skip_reason="No transmitted signal",
        )

    # Pre-trigger noise
    pre_trigger = signal[:max(pulse_start_idx, 100)]
    if len(pre_trigger) < 10:
        return MetricValue(
            name="SNR_trs", value=float('nan'), unit="unit:DeciB",
            assessment="Skipped", stage=6, category="GlobalSanity",
            skipped=True, skip_reason="Insufficient pre-trigger data",
        )

    noise_rms = np.sqrt(np.mean(pre_trigger**2))
    if noise_rms <= 0:
        # No noise detected — infinite SNR
        return MetricValue(
            name="SNR_trs", value=100.0, unit="unit:DeciB",
            assessment="GoodSNR", stage=6, category="GlobalSanity",
        )

    # Signal power in pulse region
    pulse_signal = signal[pulse_start_idx:pulse_end_idx]
    if len(pulse_signal) < 10:
        return MetricValue(
            name="SNR_trs", value=float('nan'), unit="unit:DeciB",
            assessment="Skipped", stage=6, category="GlobalSanity",
            skipped=True, skip_reason="Insufficient pulse data",
        )

    signal_power = np.mean(pulse_signal**2)
    noise_power = noise_rms**2

    if noise_power <= 0:
        snr_db = 100.0
    else:
        snr_db = 10.0 * math.log10(signal_power / noise_power)

    return MetricValue(
        name="SNR_trs", value=snr_db, unit="unit:DeciB",
        assessment=T.assess_snr(snr_db), stage=6, category="GlobalSanity",
    )


def check_tail_truncation(
    aligned_transmitted: np.ndarray,
    pulse_end_idx: int,
) -> MetricValue:
    """Check for incomplete strain integration due to signal truncation.

    Measures residual amplitude at the end of the detected pulse window
    as a fraction of peak amplitude.
    """
    if aligned_transmitted is None or len(aligned_transmitted) == 0:
        return MetricValue(
            name="TailTruncation", value=float('nan'), unit=None,
            assessment="Skipped", stage=6, category="GlobalSanity",
            skipped=True, skip_reason="No transmitted pulse data",
        )

    peak = np.max(np.abs(aligned_transmitted))
    if peak <= 0:
        return MetricValue(
            name="TailTruncation", value=0.0, unit=None,
            assessment="NoResidual", stage=6, category="GlobalSanity",
        )

    # Check amplitude at end of pulse window
    end_idx = min(pulse_end_idx, len(aligned_transmitted) - 1)
    # Average over last few points for robustness
    tail_region = aligned_transmitted[max(0, end_idx - 20):end_idx + 1]
    residual = np.mean(np.abs(tail_region)) / peak

    if residual < T.TAIL_TRUNCATION_THRESHOLD:
        assessment = "NoResidual"
    else:
        assessment = "TailTruncated"

    return MetricValue(
        name="TailTruncation", value=residual, unit=None,
        assessment=assessment, stage=6, category="GlobalSanity",
    )


def calculate_adiabatic_temperature_rise(
    stress_1w: np.ndarray,
    strain_1w: np.ndarray,
    specimen_density: float | None,
    specimen_specific_heat: float | None,
    taylor_quinney_beta: float = T.TAYLOR_QUINNEY_BETA,
) -> MetricValue:
    """Compute ATR: estimated adiabatic temperature rise (K).

    dT = beta / (rho * Cp) * integral(sigma * d_epsilon)

    Args:
        stress_1w: 1-wave stress (MPa).
        strain_1w: 1-wave strain (dimensionless).
        specimen_density: Density (g/cm³).
        specimen_specific_heat: Specific heat capacity (J/kg·K).
        taylor_quinney_beta: Taylor-Quinney coefficient (default 0.9).
    """
    if specimen_density is None or specimen_specific_heat is None:
        return MetricValue(
            name="ATR", value=float('nan'), unit="unit:K",
            assessment="Skipped", stage=6, category="DeformationMode",
            skipped=True, skip_reason="Specimen density or specific heat unavailable",
        )

    if specimen_density <= 0 or specimen_specific_heat <= 0:
        return MetricValue(
            name="ATR", value=float('nan'), unit="unit:K",
            assessment="Skipped", stage=6, category="DeformationMode",
            skipped=True, skip_reason="Invalid density or specific heat",
        )

    if stress_1w is None or strain_1w is None or len(stress_1w) < 10:
        return MetricValue(
            name="ATR", value=float('nan'), unit="unit:K",
            assessment="Skipped", stage=6, category="DeformationMode",
            skipped=True, skip_reason="Insufficient stress-strain data",
        )

    # integral(sigma * d_epsilon) in MPa (= N/mm² = 1e6 Pa)
    # rho in g/cm³ = 1000 kg/m³
    # Cp in J/(kg·K)
    # dT = beta * integral(sigma_Pa * d_eps) / (rho_kg_m3 * Cp)
    plastic_work = np.trapz(np.abs(stress_1w), strain_1w)  # MPa * dimensionless = MPa
    plastic_work_pa = plastic_work * 1e6  # Pa

    rho_kg_m3 = specimen_density * 1000.0
    delta_t = taylor_quinney_beta * plastic_work_pa / (rho_kg_m3 * specimen_specific_heat)

    return MetricValue(
        name="ATR", value=delta_t, unit="unit:K",
        assessment=T.assess_atr(delta_t), stage=6, category="DeformationMode",
        uncertainty=delta_t * 0.1,  # ~10% uncertainty from beta assumption
    )
