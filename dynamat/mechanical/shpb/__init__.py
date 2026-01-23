"""SHPB (Split Hopkinson Pressure Bar) Analysis Module

This module provides tools for analyzing SHPB experimental data:
- Pulse detection and segmentation
- Signal alignment
- Stress-strain calculation
- Tukey window tapering for ML applications
- Re-analysis utilities for parameter sensitivity studies

The module is designed to work standalone (without ontology) or
integrated with the DynaMat ontology via IO bridges.
"""

from dynamat.mechanical.shpb.core.pulse_windows import PulseDetector
from dynamat.mechanical.shpb.core.pulse_alignment import PulseAligner
from dynamat.mechanical.shpb.core.stress_strain import StressStrainCalculator
from dynamat.mechanical.shpb.core.tukey_window import TukeyWindow
from dynamat.mechanical.shpb.utils.reanalysis import SHPBReanalyzer

__all__ = [
    'PulseDetector',
    'PulseAligner',
    'StressStrainCalculator',
    'TukeyWindow',
    'SHPBReanalyzer',
]
