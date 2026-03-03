"""Core dataclasses for the SHPB contextual validity metrics system.

All computation receives pre-extracted numpy arrays and scalar parameters.
No RDF imports — pure Python computation layer.
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class MetricValue:
    """Single metric result."""
    name: str           # e.g. "FBC_Plateau"
    value: float        # Computed numeric value
    unit: Optional[str]  # QUDT unit URI or None for dimensionless
    assessment: str     # e.g. "HighTrust", "Acceptable", "CriticalFail"
    stage: int          # 0-7
    category: str       # e.g. "SignalQuality", "StructuralEquilibrium"
    uncertainty: Optional[float] = None  # Propagated uncertainty
    context: Optional[dict] = None      # Extra info (e.g. per-channel FSR)
    skipped: bool = False               # True if dependency failed
    skip_reason: Optional[str] = None


@dataclass
class ScienceWindow:
    """30%-85% peak stress window indices relative to pulse start."""
    start_idx: int
    end_idx: int
    stress_threshold_low: float   # 30% of peak
    stress_threshold_high: float  # 85% of peak


@dataclass
class MetricsResult:
    """Complete evaluation result for one test."""
    metrics: dict  # name -> MetricValue (dict[str, MetricValue])
    fitness_annotations: list  # e.g. ["ValidForPlasticFlow", "HighConfidenceForJC"]
    diagnostic_annotations: list  # e.g. ["BarrelingDetected", "InertiaRisk"]
    critical_failure: bool  # True if Stage 0 failed
    science_window: Optional[ScienceWindow]
    evaluation_stages_completed: int  # 0-8
