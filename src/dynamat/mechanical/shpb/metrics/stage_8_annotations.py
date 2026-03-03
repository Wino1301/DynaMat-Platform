"""Stage 8 — Annotation Generation: Fitness and diagnostic annotations.

Applies multi-metric decision rules from Section 7.3 of the refactoring spec
to generate per-regime fitness labels and diagnostic flags.
"""

import math

from .dataclasses import MetricValue, MetricsResult
from . import thresholds as T


def generate_annotations(metrics: dict[str, MetricValue]) -> tuple[list[str], list[str]]:
    """Apply multi-metric threshold rules to generate annotations.

    Args:
        metrics: Dict of name -> MetricValue from stages 0-7.

    Returns:
        Tuple of (fitness_annotations, diagnostic_annotations).
    """
    fitness = []
    diagnostic = []

    # Helper to safely get a metric value (returns NaN if missing/skipped)
    def v(name: str) -> float:
        m = metrics.get(name)
        if m is None or m.skipped:
            return float('nan')
        return m.value

    # =========================================================================
    # Diagnostic Annotations (flags/warnings)
    # =========================================================================

    # SignalClipped: SCD > 0
    if v("SCD") > 0:
        diagnostic.append("SignalClipped")

    # PulseOverlap: PSC < 1.0
    if v("PSC") < T.PSC_CRITICAL:
        diagnostic.append("PulseOverlap")

    # LowSNR_ExpectedFromImpedance: IMR < 0.1 AND SNR_trs < 20 dB
    imr = v("IMR")
    snr = v("SNR_trs")
    if not math.isnan(imr) and not math.isnan(snr):
        if imr < 0.1 and snr < T.SNR_TRS_ACCEPTABLE:
            diagnostic.append("LowSNR_ExpectedFromImpedance")

    # DispersionUncorrected: DSI > 0.10
    dsi = v("DSI")
    if not math.isnan(dsi) and dsi > T.DSI_CORRECTION_REQUIRED:
        diagnostic.append("DispersionUncorrected")

    # SecondaryReflectionRisk: SRI < 1.5
    sri = v("SRI")
    if not math.isnan(sri) and sri < T.SRI_SAFE:
        diagnostic.append("SecondaryReflectionRisk")

    # InertiaRisk: GDI > 1.5
    gdi = v("GDI")
    if not math.isnan(gdi) and gdi > T.GDI_OPTIMAL_HIGH:
        diagnostic.append("InertiaRisk")

    # FrictionRisk: GDI < 0.5
    if not math.isnan(gdi) and gdi < T.GDI_OPTIMAL_LOW:
        diagnostic.append("FrictionRisk")

    # InertiaContaminated: ISC > 0.05 in science window
    isc = v("ISC")
    if not math.isnan(isc) and isc > T.ISC_SIGNIFICANT:
        diagnostic.append("InertiaContaminated")

    # BarrelingDetected: BI > 1.05
    bi = v("BI")
    if not math.isnan(bi) and bi > T.BI_UNIFORM:
        diagnostic.append("BarrelingDetected")

    # IncompleteDeformation: KEI > 0.10
    kei = v("KEI")
    if not math.isnan(kei) and kei > T.KEI_INCOMPLETE:
        diagnostic.append("IncompleteDeformation")

    # BaselineDriftDetected: E_bal OK but MCI off
    e_bal = v("E_bal")
    mci = v("MCI")
    if not math.isnan(e_bal) and not math.isnan(mci):
        if T.E_BAL_LOW <= e_bal <= T.E_BAL_HIGH and not (T.MCI_LOW <= mci <= T.MCI_HIGH):
            diagnostic.append("BaselineDriftDetected")

    # DamageOnsetDetected: DOR is finite (damage detected)
    dor = v("DOR")
    if not math.isnan(dor):
        dor_metric = metrics.get("DOR")
        if dor_metric and dor_metric.assessment == "DamageOnsetDetected":
            diagnostic.append("DamageOnsetDetected")

    # SignificantThermalSoftening: ATR > 50 K
    atr = v("ATR")
    if not math.isnan(atr) and atr > T.ATR_MODERATE:
        diagnostic.append("SignificantThermalSoftening")

    # =========================================================================
    # Fitness Annotations (positive labels)
    # =========================================================================

    fbc_p = v("FBC_Plateau")
    ccc = v("CCC")
    srcv = v("SRCV")
    rpfi_t = v("RPFI_trend")
    rpfi_n = v("RPFI_noise")
    eyr = v("EYR")
    svc = v("SVC")
    spc = v("SPC")
    tail = v("TailTruncation")

    # ValidForPlasticFlow: FBC_30-85 > 0.95, CCC > 0.93
    if not math.isnan(fbc_p) and not math.isnan(ccc):
        if fbc_p > T.FBC_HIGH_TRUST and ccc > T.CCC_ACCEPTABLE:
            fitness.append("ValidForPlasticFlow")

    # ValidForRateSensitivity: SRCV < 0.10, RPFI_trend < 0.08, RPFI_noise < 0.08
    if not math.isnan(srcv) and not math.isnan(rpfi_t) and not math.isnan(rpfi_n):
        if srcv < T.SRCV_ACCEPTABLE and rpfi_t < T.RPFI_ACCEPTABLE and rpfi_n < T.RPFI_ACCEPTABLE:
            fitness.append("ValidForRateSensitivity")

    # ValidForElasticModulus: EYR > 1.0, FBC > 0.90 at yield, ISC_max < 0.05
    if not math.isnan(eyr) and not math.isnan(fbc_p) and not math.isnan(isc):
        if eyr > 1.0 and fbc_p > T.FBC_ACCEPTABLE and isc < T.ISC_SIGNIFICANT:
            fitness.append("ValidForElasticModulus")

    # ValidForYieldStress: EYR >= 0.8, FBC > 0.90
    if not math.isnan(eyr) and not math.isnan(fbc_p):
        if eyr >= 0.8 and fbc_p > T.FBC_ACCEPTABLE:
            fitness.append("ValidForYieldStress")

    # ValidForFailureStrain: Tail Truncation PASS, SVC in [0.90, 1.10], KEI < 0.05
    if not math.isnan(tail) and not math.isnan(svc) and not math.isnan(kei):
        if (tail < T.TAIL_TRUNCATION_THRESHOLD and
                T.SVC_LOW <= svc <= T.SVC_HIGH and
                kei < T.KEI_MINOR):
            fitness.append("ValidForFailureStrain")

    # ConsistentConservation: E_bal in [0.9, 1.1] AND MCI in [0.95, 1.05]
    if not math.isnan(e_bal) and not math.isnan(mci):
        if T.E_BAL_LOW <= e_bal <= T.E_BAL_HIGH and T.MCI_LOW <= mci <= T.MCI_HIGH:
            fitness.append("ConsistentConservation")

    # InternallyConsistent: SPC in [0.95, 1.05]
    if not math.isnan(spc):
        if T.SPC_STRICT_LOW <= spc <= T.SPC_STRICT_HIGH:
            fitness.append("InternallyConsistent")

    # HighConfidenceForJC: composite of multiple conditions
    has_plastic_flow = "ValidForPlasticFlow" in fitness
    has_rate = "ValidForRateSensitivity" in fitness
    gdi_ok = not math.isnan(gdi) and T.GDI_OPTIMAL_LOW <= gdi <= T.GDI_OPTIMAL_HIGH
    svc_ok = not math.isnan(svc) and T.SVC_LOW <= svc <= T.SVC_HIGH
    spc_ok = not math.isnan(spc) and T.SPC_RELAXED_LOW <= spc <= T.SPC_RELAXED_HIGH
    bi_ok = not math.isnan(bi) and bi < T.BI_UNIFORM

    if has_plastic_flow and has_rate and gdi_ok and svc_ok and spc_ok and bi_ok:
        fitness.append("HighConfidenceForJC")

    return fitness, diagnostic
