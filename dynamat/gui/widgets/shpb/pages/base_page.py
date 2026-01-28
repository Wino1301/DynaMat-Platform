"""Base class for SHPB Analysis Wizard pages.

Provides common functionality for all wizard pages including state access,
logging, and standard UI patterns.
"""

import logging
from typing import Optional, TYPE_CHECKING

from PyQt6.QtWidgets import (
    QWizardPage, QVBoxLayout, QHBoxLayout, QLabel,
    QGroupBox, QFrame, QProgressBar, QMessageBox
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont

if TYPE_CHECKING:
    from ..state.analysis_state import SHPBAnalysisState
    from ....ontology import OntologyManager
    from ....ontology.qudt import QUDTManager


class BaseSHPBPage(QWizardPage):
    """Base class for all SHPB analysis wizard pages.

    Provides:
    - Access to shared analysis state
    - Standard page layout helpers
    - Progress indication
    - Logging integration
    - Common validation patterns

    Subclasses should override:
    - _setup_ui(): Create page-specific UI
    - initializePage(): Update displays when page becomes current
    - validatePage(): Validate before allowing Next
    - cleanupPage(): Clean up when leaving page (optional)
    """

    # Signals
    processing_started = pyqtSignal()
    processing_finished = pyqtSignal(bool)  # success
    status_message = pyqtSignal(str)

    def __init__(
        self,
        state: "SHPBAnalysisState",
        ontology_manager: "OntologyManager",
        qudt_manager: Optional["QUDTManager"] = None,
        parent=None
    ):
        super().__init__(parent)

        self.state = state
        self.ontology_manager = ontology_manager
        self.qudt_manager = qudt_manager
        self.logger = logging.getLogger(self.__class__.__name__)

        # UI components
        self._main_layout: Optional[QVBoxLayout] = None
        self._progress_bar: Optional[QProgressBar] = None
        self._status_label: Optional[QLabel] = None

        # Track if page has been initialized
        self._initialized = False

    def _create_base_layout(self) -> QVBoxLayout:
        """Create the base page layout with status area.

        Returns:
            Main vertical layout for page content
        """
        self._main_layout = QVBoxLayout(self)
        self._main_layout.setContentsMargins(10, 10, 10, 10)
        self._main_layout.setSpacing(10)

        return self._main_layout

    def _add_status_area(self) -> None:
        """Add status bar area at bottom of page."""
        if self._main_layout is None:
            return

        # Create status frame
        status_frame = QFrame()
        status_frame.setFrameStyle(QFrame.Shape.StyledPanel)
        status_frame.setMaximumHeight(40)

        status_layout = QHBoxLayout(status_frame)
        status_layout.setContentsMargins(5, 2, 5, 2)

        # Status label
        self._status_label = QLabel("Ready")
        self._status_label.setStyleSheet("color: gray;")
        status_layout.addWidget(self._status_label)

        status_layout.addStretch()

        # Progress bar (hidden by default)
        self._progress_bar = QProgressBar()
        self._progress_bar.setMaximumWidth(200)
        self._progress_bar.setVisible(False)
        status_layout.addWidget(self._progress_bar)

        self._main_layout.addWidget(status_frame)

    def _create_group_box(self, title: str, bold_title: bool = True) -> QGroupBox:
        """Create a styled group box.

        Args:
            title: Group box title
            bold_title: Whether to make title bold

        Returns:
            Configured QGroupBox
        """
        group = QGroupBox(title)

        if bold_title:
            font = QFont()
            font.setBold(True)
            group.setFont(font)

        return group

    def _create_section_label(self, text: str) -> QLabel:
        """Create a section header label.

        Args:
            text: Label text

        Returns:
            Configured QLabel
        """
        label = QLabel(text)
        font = QFont()
        font.setPointSize(11)
        font.setBold(True)
        label.setFont(font)
        return label

    def set_status(self, message: str, is_error: bool = False) -> None:
        """Update status message.

        Args:
            message: Status text to display
            is_error: Whether this is an error message
        """
        if self._status_label:
            color = "red" if is_error else "gray"
            self._status_label.setStyleSheet(f"color: {color};")
            self._status_label.setText(message)

        self.status_message.emit(message)

        if is_error:
            self.logger.error(message)
        else:
            self.logger.info(message)

    def show_progress(self, indeterminate: bool = True, value: int = 0, maximum: int = 100) -> None:
        """Show progress bar.

        Args:
            indeterminate: Use indeterminate (bouncing) mode
            value: Current progress value
            maximum: Maximum progress value
        """
        if self._progress_bar:
            if indeterminate:
                self._progress_bar.setRange(0, 0)
            else:
                self._progress_bar.setRange(0, maximum)
                self._progress_bar.setValue(value)
            self._progress_bar.setVisible(True)

    def hide_progress(self) -> None:
        """Hide progress bar."""
        if self._progress_bar:
            self._progress_bar.setVisible(False)

    def show_error(self, title: str, message: str, details: str = None) -> None:
        """Show error message dialog.

        Args:
            title: Dialog title
            message: Error message
            details: Optional detailed information
        """
        self.set_status(message, is_error=True)

        msg_box = QMessageBox(self)
        msg_box.setIcon(QMessageBox.Icon.Critical)
        msg_box.setWindowTitle(title)
        msg_box.setText(message)

        if details:
            msg_box.setDetailedText(details)

        msg_box.exec()

    def show_warning(self, title: str, message: str) -> None:
        """Show warning message dialog.

        Args:
            title: Dialog title
            message: Warning message
        """
        QMessageBox.warning(self, title, message)

    def confirm_action(self, title: str, message: str) -> bool:
        """Show confirmation dialog.

        Args:
            title: Dialog title
            message: Confirmation message

        Returns:
            True if user confirmed, False otherwise
        """
        reply = QMessageBox.question(
            self, title, message,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        return reply == QMessageBox.StandardButton.Yes

    # ==================== WIZARD PAGE OVERRIDES ====================

    def initializePage(self) -> None:
        """Called when the page becomes the current page.

        Override in subclasses to update displays from state.
        Always call super().initializePage() first.
        """
        self.logger.debug(f"Initializing page: {self.__class__.__name__}")

        if not self._initialized:
            self._setup_ui()
            self._initialized = True

        self.hide_progress()
        self.set_status("Ready")

    def validatePage(self) -> bool:
        """Called when user clicks Next or Finish.

        Override in subclasses to validate before allowing navigation.
        Return True to allow navigation, False to stay on current page.

        Returns:
            True if validation passes
        """
        return True

    def cleanupPage(self) -> None:
        """Called when user clicks Back.

        Override in subclasses to clean up page state if needed.
        """
        self.logger.debug(f"Cleaning up page: {self.__class__.__name__}")

    def _setup_ui(self) -> None:
        """Setup page UI - override in subclasses.

        This is called once when the page is first shown.
        """
        layout = self._create_base_layout()

        placeholder = QLabel("Page not implemented")
        placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(placeholder)

        self._add_status_area()

    # ==================== HELPER METHODS FOR SUBCLASSES ====================

    def get_wizard(self):
        """Get parent wizard instance.

        Returns:
            Parent SHPBAnalysisWizard or None
        """
        return self.wizard()

    def get_main_window(self):
        """Get main window instance.

        Returns:
            MainWindow instance or None
        """
        wizard = self.get_wizard()
        if wizard and hasattr(wizard, 'main_window'):
            return wizard.main_window
        return None

    def get_current_user(self) -> Optional[str]:
        """Get currently selected user URI.

        Returns:
            User URI or None
        """
        main_window = self.get_main_window()
        if main_window and hasattr(main_window, 'get_current_user'):
            return main_window.get_current_user()
        return None

    def log_state_summary(self) -> None:
        """Log current analysis state summary for debugging."""
        self.logger.debug("=== Analysis State Summary ===")
        self.logger.debug(f"Specimen URI: {self.state.specimen_uri}")
        self.logger.debug(f"Has raw data: {self.state.has_raw_data()}")
        self.logger.debug(f"Has detected pulses: {self.state.has_detected_pulses()}")
        self.logger.debug(f"Has segmented pulses: {self.state.has_segmented_pulses()}")
        self.logger.debug(f"Has aligned pulses: {self.state.has_aligned_pulses()}")
        self.logger.debug(f"Has results: {self.state.has_results()}")
        self.logger.debug(f"Has equilibrium metrics: {self.state.has_equilibrium_metrics()}")
        self.logger.debug("==============================")
