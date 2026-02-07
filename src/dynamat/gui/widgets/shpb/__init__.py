"""SHPB Analysis Wizard - GUI for Split Hopkinson Pressure Bar Analysis.

This module provides a multi-page wizard interface for SHPB test analysis,
mirroring the 12-stage workflow from the analysis notebook.

Main Components:
    SHPBAnalysisWizard: Main wizard container (QWizard)
    SHPBAnalysisState: Shared state dataclass

Pages (in order):
    1. SpecimenSelectionPage: Select specimen from database
    2. RawDataPage: Load and map CSV columns
    3. EquipmentPage: Configure bar/gauge equipment
    4. PulseDetectionPage: Detect I/T/R windows
    5. SegmentationPage: Extract and center pulses
    6. AlignmentPage: Optimize pulse alignment
    7. ResultsPage: View stress-strain curves and metrics
    8. TukeyWindowPage: Apply window function for ML
    9. ExportPage: Save test to RDF with validation
"""

from .shpb_analysis_wizard import SHPBAnalysisWizard
from .state.analysis_state import SHPBAnalysisState

__all__ = [
    "SHPBAnalysisWizard",
    "SHPBAnalysisState",
]
