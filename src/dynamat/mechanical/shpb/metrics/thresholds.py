"""All threshold constants and assessment string mappings for SHPB metrics.

Centralizes the decision logic from Section 7.3 of the refactoring spec.
"""

# =============================================================================
# Stage 0: Critical Pre-Check
# =============================================================================
SCD_CRITICAL = 0          # Any clipping = critical fail
PSC_CRITICAL = 1.0        # PSC < 1.0 = pulse overlap = critical fail

# =============================================================================
# Stage 1: Signal Quality
# =============================================================================
BQI_GOOD = 0.001          # Both offset and drift should be < 0.1% of full scale
BQI_ACCEPTABLE = 0.005

# =============================================================================
# Stage 2: Pre-Conditions
# =============================================================================
GDI_OPTIMAL_LOW = 0.5     # Below = friction risk
GDI_OPTIMAL_HIGH = 1.5    # Above = inertia risk
DSI_NEGLIGIBLE = 0.05
DSI_CORRECTION_REQUIRED = 0.10
SRI_SAFE = 1.5
SRI_OVERLAP = 1.0

# =============================================================================
# Stage 3: Equilibrium & Timing
# =============================================================================
REI_ADEQUATE = 1.0
REI_REVERBERATIONS_REQUIRED = 3  # conservative minimum

# =============================================================================
# Stage 4: Science Window Metrics
# =============================================================================
FBC_HIGH_TRUST = 0.95
FBC_ACCEPTABLE = 0.90
FBC_POOR = 0.85

SRCV_EXCELLENT = 0.05
SRCV_ACCEPTABLE = 0.10
SRCV_PROBLEMATIC = 0.15

RPFI_GOOD = 0.05
RPFI_ACCEPTABLE = 0.08

CCC_HIGH_TRUST = 0.97
CCC_ACCEPTABLE = 0.93

NRMSE_GOOD = 0.03
NRMSE_ACCEPTABLE = 0.05

ISC_NEGLIGIBLE = 0.03
ISC_SIGNIFICANT = 0.05

# =============================================================================
# Stage 5: Conservation
# =============================================================================
E_BAL_LOW = 0.9
E_BAL_HIGH = 1.1
MCI_LOW = 0.95
MCI_HIGH = 1.05
EAE_RANGES = {
    'metal': (0.05, 0.15),
    'ceramic': (0.01, 0.03),
    'polymer': (0.10, 0.40),
    'composite': (0.03, 0.10),
}
KEI_COMPLETE = 0.01
KEI_MINOR = 0.05
KEI_INCOMPLETE = 0.10
SPC_STRICT_LOW = 0.95
SPC_STRICT_HIGH = 1.05
SPC_RELAXED_LOW = 0.90
SPC_RELAXED_HIGH = 1.10

# =============================================================================
# Stage 6: Global Sanity
# =============================================================================
SNR_TRS_GOOD = 30.0       # dB
SNR_TRS_ACCEPTABLE = 20.0
TAIL_TRUNCATION_THRESHOLD = 0.02  # fraction of peak
ATR_NEGLIGIBLE = 20.0     # K
ATR_MODERATE = 50.0       # K (triggers SignificantThermalSoftening above this)
ATR_SIGNIFICANT = 80.0

# =============================================================================
# Stage 7: Post-Test Validation
# =============================================================================
VCI_TOLERANCE = 0.05      # |VCI - 1.0| < 0.05 for metals
BI_UNIFORM = 1.05         # BI < 1.05 = uniform deformation
SVC_LOW = 0.90
SVC_HIGH = 1.10

# =============================================================================
# Taylor-Quinney coefficient
# =============================================================================
TAYLOR_QUINNEY_BETA = 0.9


def assess_fbc(value: float) -> str:
    if value >= FBC_HIGH_TRUST:
        return "HighTrust"
    elif value >= FBC_ACCEPTABLE:
        return "Acceptable"
    elif value >= FBC_POOR:
        return "Marginal"
    else:
        return "Poor"


def assess_srcv(value: float) -> str:
    if value <= SRCV_EXCELLENT:
        return "Excellent"
    elif value <= SRCV_ACCEPTABLE:
        return "Acceptable"
    elif value <= SRCV_PROBLEMATIC:
        return "Marginal"
    else:
        return "Poor"


def assess_ccc(value: float) -> str:
    if value >= CCC_HIGH_TRUST:
        return "HighTrust"
    elif value >= CCC_ACCEPTABLE:
        return "Acceptable"
    else:
        return "Poor"


def assess_gdi(value: float) -> str:
    if value < GDI_OPTIMAL_LOW:
        return "FrictionRisk"
    elif value > GDI_OPTIMAL_HIGH:
        return "InertiaRisk"
    else:
        return "NearOptimalGeometry"


def assess_isc(value: float) -> str:
    if value <= ISC_NEGLIGIBLE:
        return "NegligibleInertia"
    elif value <= ISC_SIGNIFICANT:
        return "ModerateInertia"
    else:
        return "SignificantInertia"


def assess_e_bal(value: float) -> str:
    if E_BAL_LOW <= value <= E_BAL_HIGH:
        return "EnergyConserved"
    else:
        return "EnergyImbalance"


def assess_mci(value: float) -> str:
    if MCI_LOW <= value <= MCI_HIGH:
        return "MomentumConserved"
    else:
        return "MomentumImbalance"


def assess_kei(value: float) -> str:
    if value <= KEI_COMPLETE:
        return "TestComplete"
    elif value <= KEI_MINOR:
        return "MinorResidualMotion"
    elif value <= KEI_INCOMPLETE:
        return "IncompleteDeformation"
    else:
        return "SignificantResidualMotion"


def assess_bi(value: float) -> str:
    if abs(value - 1.0) < 0.02:
        return "UniformDeformation"
    elif value > BI_UNIFORM:
        return "BarrelingDetected"
    elif value < 0.95:
        return "AnomalousContraction"
    else:
        return "MinorNonUniformity"


def assess_svc(value: float) -> str:
    if SVC_LOW <= value <= SVC_HIGH:
        return "AcceptableStrainAgreement"
    elif value > SVC_HIGH:
        return "SignalOverestimates"
    else:
        return "SignalUnderestimates"


def assess_vci(value: float) -> str:
    if abs(value - 1.0) <= VCI_TOLERANCE:
        return "VolumeConserved"
    else:
        return "VolumeDeviation"


def assess_psc(value: float) -> str:
    if value >= 1.0:
        return "PulsesSeparated"
    else:
        return "CriticalFail"


def assess_rei(value: float) -> str:
    if value > REI_ADEQUATE:
        return "AdequateReverberations"
    elif value >= 0.8:
        return "Borderline"
    else:
        return "InsufficientReverberations"


def assess_snr(value: float) -> str:
    if value >= SNR_TRS_GOOD:
        return "GoodSNR"
    elif value >= SNR_TRS_ACCEPTABLE:
        return "AcceptableSNR"
    else:
        return "LowSNR"


def assess_atr(value: float) -> str:
    if value < ATR_NEGLIGIBLE:
        return "NegligibleThermalEffect"
    elif value < ATR_MODERATE:
        return "ModerateThermalSoftening"
    else:
        return "SignificantThermalSoftening"


def assess_spc(value: float) -> str:
    if SPC_STRICT_LOW <= value <= SPC_STRICT_HIGH:
        return "InternallyConsistent"
    elif SPC_RELAXED_LOW <= value <= SPC_RELAXED_HIGH:
        return "AcceptableConsistency"
    else:
        return "Inconsistent"


def assess_imr(value: float) -> str:
    if value < 0.1:
        return "HighlyMismatched"
    elif value < 0.5:
        return "ModeratelyMismatched"
    elif value < 2.0:
        return "WellMatched"
    else:
        return "SpecimenDominant"


def assess_dsi(value: float) -> str:
    if value < DSI_NEGLIGIBLE:
        return "DispersionNegligible"
    elif value < DSI_CORRECTION_REQUIRED:
        return "DispersionCorrectionRecommended"
    else:
        return "DispersionCorrectionRequired"


def assess_sri(value: float) -> str:
    if value > SRI_SAFE:
        return "NoSecondaryReflectionRisk"
    elif value > SRI_OVERLAP:
        return "LatePulseContaminationRisk"
    else:
        return "SecondaryReflectionOverlap"
