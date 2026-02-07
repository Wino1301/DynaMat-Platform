"""Core SHPB signal processing utilities.

This module provides the core signal processing pipeline for Split Hopkinson
Pressure Bar (SHPB) analysis. It handles the complete workflow from raw
oscilloscope signals to stress-strain curves.

Processing Pipeline
-------------------
1. PulseDetector: Locate and segment pulses from raw gauge traces
2. TukeyWindow: Apply signal tapering for frequency-domain processing
3. PulseAligner: Align transmitted/reflected pulses using equilibrium optimization
4. StressStrainCalculator: Compute stress-strain curves using 1-wave and 3-wave analysis

Classes
-------
PulseDetector : Matched-filter pulse detection and segmentation
PulseAligner : Multi-criteria pulse alignment optimization
StressStrainCalculator : 1-wave and 3-wave stress-strain calculation
TukeyWindow : Tukey window generation for signal tapering

References
----------
Gray, G. T. (2000). Classic Split-Hopkinson Pressure Bar Testing.
ASM Handbook, Vol. 8: Mechanical Testing and Evaluation.

Kolsky, H. (1949). An Investigation of the Mechanical Properties of
Materials at very High Rates of Loading. Proceedings of the Physical
Society. Section B, 62(11), 676.

Chen, W. W., & Song, B. (2011). Split Hopkinson (Kolsky) Bar: Design,
Testing and Applications. Springer.
"""

from dynamat.mechanical.shpb.core.pulse_windows import PulseDetector
from dynamat.mechanical.shpb.core.pulse_alignment import PulseAligner
from dynamat.mechanical.shpb.core.stress_strain import StressStrainCalculator
from dynamat.mechanical.shpb.core.tukey_window import TukeyWindow

__all__ = [
    'PulseDetector',
    'PulseAligner',
    'StressStrainCalculator',
    'TukeyWindow',
]
