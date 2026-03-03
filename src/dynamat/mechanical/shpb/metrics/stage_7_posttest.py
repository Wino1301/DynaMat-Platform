"""Stage 7 — Post-Test Validation: VCI, BI, SVC.

Requires physical post-test measurements (final length/diameter).
Always computable if dimensions provided, regardless of Stage 0 status.
"""

import math

import numpy as np

from .dataclasses import MetricValue
from . import thresholds as T


def calculate_volume_conservation(
    specimen_length: float,
    specimen_diameter: float,
    final_length: float | None,
    final_diameter: float | None,
    specimen_length_unc: float | None = None,
    specimen_diameter_unc: float | None = None,
    final_length_unc: float | None = None,
    final_diameter_unc: float | None = None,
) -> MetricValue:
    """Compute VCI: (A_final * L_final) / (A_initial * L_initial).

    For incompressible metals, VCI should be ~1.0.
    """
    if final_length is None or final_diameter is None:
        return MetricValue(
            name="VCI", value=float('nan'), unit=None,
            assessment="Skipped", stage=7, category="PipelineValidation",
            skipped=True, skip_reason="Post-test dimensions unavailable",
        )

    if (specimen_length <= 0 or specimen_diameter <= 0 or
            final_length <= 0 or final_diameter <= 0):
        return MetricValue(
            name="VCI", value=float('nan'), unit=None,
            assessment="Skipped", stage=7, category="PipelineValidation",
            skipped=True, skip_reason="Invalid dimensions",
        )

    a_initial = math.pi * (specimen_diameter / 2)**2
    a_final = math.pi * (final_diameter / 2)**2
    v_initial = a_initial * specimen_length
    v_final = a_final * final_length

    vci = v_final / v_initial

    # Uncertainty propagation (first-order Taylor)
    uncertainty = None
    if any(u is not None for u in [specimen_length_unc, specimen_diameter_unc,
                                     final_length_unc, final_diameter_unc]):
        # VCI = (D_f² * L_f) / (D_i² * L_i)
        # Partial derivatives for relative uncertainty
        rel_unc_sq = 0.0
        if final_diameter_unc is not None and final_diameter > 0:
            rel_unc_sq += (2 * final_diameter_unc / final_diameter)**2
        if final_length_unc is not None and final_length > 0:
            rel_unc_sq += (final_length_unc / final_length)**2
        if specimen_diameter_unc is not None and specimen_diameter > 0:
            rel_unc_sq += (2 * specimen_diameter_unc / specimen_diameter)**2
        if specimen_length_unc is not None and specimen_length > 0:
            rel_unc_sq += (specimen_length_unc / specimen_length)**2
        uncertainty = vci * math.sqrt(rel_unc_sq)

    return MetricValue(
        name="VCI", value=vci, unit=None,
        assessment=T.assess_vci(vci), stage=7, category="PipelineValidation",
        uncertainty=uncertainty,
    )


def calculate_barreling_index(
    specimen_length: float,
    specimen_diameter: float,
    final_length: float | None,
    final_diameter: float | None,
    final_diameter_unc: float | None = None,
    final_length_unc: float | None = None,
) -> MetricValue:
    """Compute BI: D_final_measured / D_final_predicted.

    D_predicted = D_initial * sqrt(L_initial / L_final)
    BI ~1.0 = uniform deformation, BI > 1.05 = barreling detected.
    """
    if final_length is None or final_diameter is None:
        return MetricValue(
            name="BI", value=float('nan'), unit=None,
            assessment="Skipped", stage=7, category="DeformationMode",
            skipped=True, skip_reason="Post-test dimensions unavailable",
        )

    if (specimen_length <= 0 or specimen_diameter <= 0 or
            final_length <= 0 or final_diameter <= 0):
        return MetricValue(
            name="BI", value=float('nan'), unit=None,
            assessment="Skipped", stage=7, category="DeformationMode",
            skipped=True, skip_reason="Invalid dimensions",
        )

    d_predicted = specimen_diameter * math.sqrt(specimen_length / final_length)
    if d_predicted <= 0:
        return MetricValue(
            name="BI", value=float('nan'), unit=None,
            assessment="Skipped", stage=7, category="DeformationMode",
            skipped=True, skip_reason="Cannot compute predicted diameter",
        )

    bi = final_diameter / d_predicted

    # Uncertainty propagation
    uncertainty = None
    if final_diameter_unc is not None or final_length_unc is not None:
        rel_unc_sq = 0.0
        if final_diameter_unc is not None and final_diameter > 0:
            rel_unc_sq += (final_diameter_unc / final_diameter)**2
        if final_length_unc is not None and final_length > 0:
            rel_unc_sq += (0.5 * final_length_unc / final_length)**2
        uncertainty = bi * math.sqrt(rel_unc_sq)

    return MetricValue(
        name="BI", value=bi, unit=None,
        assessment=T.assess_bi(bi), stage=7, category="DeformationMode",
        uncertainty=uncertainty,
    )


def calculate_strain_verification(
    strain_1w: np.ndarray,
    specimen_length: float,
    final_length: float | None,
    final_length_unc: float | None = None,
    specimen_length_unc: float | None = None,
) -> MetricValue:
    """Compute SVC: epsilon_signal / epsilon_measured.

    epsilon_signal = final value of integrated strain from signal.
    epsilon_measured = (L_final - L_initial) / L_initial
    """
    if final_length is None:
        return MetricValue(
            name="SVC", value=float('nan'), unit=None,
            assessment="Skipped", stage=7, category="PipelineValidation",
            skipped=True, skip_reason="Post-test length unavailable",
        )

    if specimen_length <= 0 or final_length <= 0:
        return MetricValue(
            name="SVC", value=float('nan'), unit=None,
            assessment="Skipped", stage=7, category="PipelineValidation",
            skipped=True, skip_reason="Invalid dimensions",
        )

    if strain_1w is None or len(strain_1w) == 0:
        return MetricValue(
            name="SVC", value=float('nan'), unit=None,
            assessment="Skipped", stage=7, category="PipelineValidation",
            skipped=True, skip_reason="No strain data",
        )

    # Signal-derived strain (final value of integrated strain)
    eps_signal = abs(float(strain_1w[-1]))

    # Caliper-measured strain
    eps_measured = abs((final_length - specimen_length) / specimen_length)

    if eps_measured <= 0:
        return MetricValue(
            name="SVC", value=float('nan'), unit=None,
            assessment="Skipped", stage=7, category="PipelineValidation",
            skipped=True, skip_reason="Zero measured strain",
        )

    svc = eps_signal / eps_measured

    # Uncertainty
    uncertainty = None
    if final_length_unc is not None or specimen_length_unc is not None:
        # Propagate through eps_measured = |L_f - L_i| / L_i
        rel_unc_sq = 0.0
        delta_l = abs(final_length - specimen_length)
        if delta_l > 0:
            if final_length_unc is not None:
                rel_unc_sq += (final_length_unc / delta_l)**2
            if specimen_length_unc is not None:
                rel_unc_sq += (specimen_length_unc / delta_l)**2
                rel_unc_sq += (specimen_length_unc / specimen_length)**2
        uncertainty = svc * math.sqrt(rel_unc_sq)

    return MetricValue(
        name="SVC", value=svc, unit=None,
        assessment=T.assess_svc(svc), stage=7, category="PipelineValidation",
        uncertainty=uncertainty,
    )
