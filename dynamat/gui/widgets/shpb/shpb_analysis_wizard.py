"""SHPB Analysis Wizard - Main container for SHPB test analysis workflow.

This wizard provides a multi-page interface for Split Hopkinson Pressure Bar
analysis, implementing the 12-stage workflow from the analysis notebook.
"""

import logging
from typing import Optional
from pathlib import Path

from PyQt6.QtWidgets import QWizard, QMessageBox
from PyQt6.QtCore import pyqtSignal

from ....ontology import OntologyManager
from ....ontology.qudt import QUDTManager
from .state.analysis_state import SHPBAnalysisState
from .pages import (
    SpecimenSelectionPage,
    RawDataPage,
    EquipmentPage,
    PulseDetectionPage,
    SegmentationPage,
    AlignmentPage,
    ResultsPage,
    TukeyWindowPage,
    ExportPage,
)

logger = logging.getLogger(__name__)


class SHPBAnalysisWizard(QWizard):
    """Multi-page wizard for SHPB test analysis.

    Implements a sequential workflow for:
    1. Specimen selection from database
    2. Raw data loading and column mapping
    3. Equipment configuration
    4-5. Pulse detection
    6. Pulse segmentation
    7. Pulse alignment
    8-9. Stress-strain calculation and metrics
    10. Tukey window application
    11-12. Test export to RDF

    Signals:
        analysis_completed: Emitted with Path when analysis is saved
        analysis_cancelled: Emitted when user cancels wizard
    """

    # Page IDs
    PAGE_SPECIMEN = 0
    PAGE_RAW_DATA = 1
    PAGE_EQUIPMENT = 2
    PAGE_DETECTION = 3
    PAGE_SEGMENTATION = 4
    PAGE_ALIGNMENT = 5
    PAGE_RESULTS = 6
    PAGE_TUKEY = 7
    PAGE_EXPORT = 8

    # Signals
    analysis_completed = pyqtSignal(Path)
    analysis_cancelled = pyqtSignal()

    def __init__(
        self,
        ontology_manager: OntologyManager,
        qudt_manager: Optional[QUDTManager] = None,
        main_window=None,
        parent=None
    ):
        super().__init__(parent)

        self.ontology_manager = ontology_manager
        self.main_window = main_window
        self.logger = logging.getLogger(__name__)

        # Initialize QUDT manager if not provided
        if qudt_manager is None:
            try:
                self.qudt_manager = QUDTManager()
                self.qudt_manager.load()
                self.logger.info("QUDT manager initialized")
            except Exception as e:
                self.logger.warning(f"Failed to initialize QUDT manager: {e}")
                self.qudt_manager = None
        else:
            self.qudt_manager = qudt_manager

        # Shared analysis state
        self.state = SHPBAnalysisState()

        # Setup wizard
        self._setup_wizard()
        self._create_pages()
        self._connect_signals()

        self.logger.info("SHPB Analysis Wizard initialized")

    def _setup_wizard(self) -> None:
        """Configure wizard appearance and behavior."""
        self.setWindowTitle("SHPB Analysis Wizard")
        self.setWizardStyle(QWizard.WizardStyle.ModernStyle)

        # Set minimum size for comfortable viewing
        self.setMinimumSize(900, 700)
        self.resize(1000, 750)

        # Configure buttons
        self.setOption(QWizard.WizardOption.NoBackButtonOnStartPage, True)
        self.setOption(QWizard.WizardOption.HaveHelpButton, False)
        self.setOption(QWizard.WizardOption.HaveCustomButton1, False)

        # Set button text
        self.setButtonText(QWizard.WizardButton.NextButton, "Next >")
        self.setButtonText(QWizard.WizardButton.BackButton, "< Back")
        self.setButtonText(QWizard.WizardButton.FinishButton, "Export Test")
        self.setButtonText(QWizard.WizardButton.CancelButton, "Cancel")

    def _create_pages(self) -> None:
        """Create and register wizard pages."""
        # Page 1: Specimen Selection
        self.specimen_page = SpecimenSelectionPage(
            self.state, self.ontology_manager, self.qudt_manager, self
        )
        self.setPage(self.PAGE_SPECIMEN, self.specimen_page)

        # Page 2: Raw Data Loading
        self.raw_data_page = RawDataPage(
            self.state, self.ontology_manager, self.qudt_manager, self
        )
        self.setPage(self.PAGE_RAW_DATA, self.raw_data_page)

        # Page 3: Equipment Configuration
        self.equipment_page = EquipmentPage(
            self.state, self.ontology_manager, self.qudt_manager, self
        )
        self.setPage(self.PAGE_EQUIPMENT, self.equipment_page)

        # Page 4: Pulse Detection
        self.detection_page = PulseDetectionPage(
            self.state, self.ontology_manager, self.qudt_manager, self
        )
        self.setPage(self.PAGE_DETECTION, self.detection_page)

        # Page 5: Segmentation
        self.segmentation_page = SegmentationPage(
            self.state, self.ontology_manager, self.qudt_manager, self
        )
        self.setPage(self.PAGE_SEGMENTATION, self.segmentation_page)

        # Page 6: Alignment
        self.alignment_page = AlignmentPage(
            self.state, self.ontology_manager, self.qudt_manager, self
        )
        self.setPage(self.PAGE_ALIGNMENT, self.alignment_page)

        # Page 7: Results
        self.results_page = ResultsPage(
            self.state, self.ontology_manager, self.qudt_manager, self
        )
        self.setPage(self.PAGE_RESULTS, self.results_page)

        # Page 8: Tukey Window
        self.tukey_page = TukeyWindowPage(
            self.state, self.ontology_manager, self.qudt_manager, self
        )
        self.setPage(self.PAGE_TUKEY, self.tukey_page)

        # Page 9: Export
        self.export_page = ExportPage(
            self.state, self.ontology_manager, self.qudt_manager, self
        )
        self.setPage(self.PAGE_EXPORT, self.export_page)

        self.logger.info(f"Created {self.pageIds().__len__()} wizard pages")

    def _connect_signals(self) -> None:
        """Connect wizard signals."""
        self.finished.connect(self._on_wizard_finished)
        self.currentIdChanged.connect(self._on_page_changed)

    def _on_wizard_finished(self, result: int) -> None:
        """Handle wizard completion or cancellation.

        Args:
            result: QDialog.Accepted or QDialog.Rejected
        """
        if result == QWizard.DialogCode.Accepted:
            if self.state.exported_file_path:
                self.logger.info(f"Analysis completed: {self.state.exported_file_path}")
                self.analysis_completed.emit(self.state.exported_file_path)
            else:
                self.logger.warning("Wizard accepted but no file was exported")
        else:
            self.logger.info("Analysis cancelled by user")
            self.analysis_cancelled.emit()

    def _on_page_changed(self, page_id: int) -> None:
        """Handle page navigation.

        Args:
            page_id: ID of the new current page
        """
        page_names = {
            self.PAGE_SPECIMEN: "Specimen Selection",
            self.PAGE_RAW_DATA: "Raw Data",
            self.PAGE_EQUIPMENT: "Equipment",
            self.PAGE_DETECTION: "Pulse Detection",
            self.PAGE_SEGMENTATION: "Segmentation",
            self.PAGE_ALIGNMENT: "Alignment",
            self.PAGE_RESULTS: "Results",
            self.PAGE_TUKEY: "Tukey Window",
            self.PAGE_EXPORT: "Export",
        }
        self.logger.info(f"Navigated to page: {page_names.get(page_id, page_id)}")

    def reset_analysis(self) -> None:
        """Reset wizard to initial state for new analysis."""
        # Confirm reset if analysis is in progress
        if self.state.has_raw_data():
            reply = QMessageBox.question(
                self, "Reset Analysis",
                "This will clear all analysis data. Continue?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply != QMessageBox.StandardButton.Yes:
                return

        # Reset state
        self.state = SHPBAnalysisState()

        # Update all pages with new state
        for page_id in self.pageIds():
            page = self.page(page_id)
            if hasattr(page, 'state'):
                page.state = self.state

        # Restart wizard
        self.restart()

        self.logger.info("Analysis reset to initial state")

    def get_current_user(self) -> Optional[str]:
        """Get currently selected user from main window.

        Returns:
            User URI or None
        """
        if self.main_window and hasattr(self.main_window, 'get_current_user'):
            return self.main_window.get_current_user()
        return None

    def log_message(self, message: str, level: str = "info") -> None:
        """Log message to main window terminal if available.

        Args:
            message: Message to log
            level: Log level ('info', 'warning', 'error')
        """
        if self.main_window and hasattr(self.main_window, 'log_message'):
            self.main_window.log_message(message, level)
        else:
            if level == "error":
                self.logger.error(message)
            elif level == "warning":
                self.logger.warning(message)
            else:
                self.logger.info(message)
