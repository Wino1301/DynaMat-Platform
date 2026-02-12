"""Base class for SHPB Analysis Wizard pages.

Provides common functionality for all wizard pages including state access,
logging, and standard UI patterns.
"""

import logging
from typing import Optional, TYPE_CHECKING, Dict, Any, Set, List, Tuple

from PyQt6.QtWidgets import (
    QWizardPage, QVBoxLayout, QHBoxLayout, QLabel,
    QGroupBox, QFrame, QProgressBar, QMessageBox, QDialog
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont

from rdflib import Graph, Namespace, URIRef
from rdflib.namespace import RDF

if TYPE_CHECKING:
    from ..state.analysis_state import SHPBAnalysisState
    from ....ontology import OntologyManager
    from ....ontology.qudt import QUDTManager
    from ....core.form_validator import SHACLValidator
    from ....parsers.instance_writer import InstanceWriter


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

    # ==================== INSTANCE WRITER HELPERS ====================

    DYN_NS = "https://dynamat.utep.edu/ontology#"

    @property
    def _instance_writer(self) -> "InstanceWriter":
        """Lazy-loaded InstanceWriter for building validation graphs."""
        if not hasattr(self, '_writer_cache'):
            from ....parsers.instance_writer import InstanceWriter
            self._writer_cache = InstanceWriter(self.ontology_manager, self.qudt_manager)
        return self._writer_cache

    def _get_range_class(self, class_uri: str, property_local_name: str) -> Optional[str]:
        """Get rdfs:range class URI for an object property from cached metadata.

        Args:
            class_uri: Full URI of the OWL class (e.g. "https://dynamat.utep.edu/ontology#SHPBCompression")
            property_local_name: Local name of the property (e.g. "hasStrikerBar")

        Returns:
            Full range class URI, or None if not found.
        """
        if not hasattr(self, '_metadata_cache'):
            self._metadata_cache: Dict[str, Any] = {}
        if class_uri not in self._metadata_cache:
            self._metadata_cache[class_uri] = self.ontology_manager.get_class_metadata_for_form(class_uri)
        metadata = self._metadata_cache[class_uri]
        for prop in metadata.properties:
            if prop.name == property_local_name and prop.range_class:
                return prop.range_class
        return None

    def _build_graph_from_form_data(
        self,
        form_data: Dict[str, Any],
        class_uri: str,
        instance_id: str,
        exclude_properties: Optional[Set[str]] = None,
        extra_triples: Optional[List[Tuple]] = None,
        skip_range_types: Optional[Set[str]] = None,
    ) -> Graph:
        """Build an RDF graph from form data using InstanceWriter.

        This delegates type conversion, URI resolution, and unit conversion
        to InstanceWriter.create_single_instance(), then post-processes
        object property targets to add rdf:type triples needed by SHACL.

        Args:
            form_data: Property URI -> value dict (from FormDataHandler).
            class_uri: Full OWL class URI for the instance.
            instance_id: Instance identifier (e.g. "_val_equipment").
            exclude_properties: Set of property local names to skip.
            extra_triples: Additional (s, p, o) triples to inject.
            skip_range_types: Property local names whose object targets
                should NOT get an rdf:type triple (e.g. externally validated).

        Returns:
            Populated RDF Graph.
        """
        exclude_properties = exclude_properties or set()
        skip_range_types = skip_range_types or set()

        # Filter form data by excluded property local names
        filtered_data: Dict[str, Any] = {}
        for uri, value in form_data.items():
            prop_name = uri.split("#")[-1] if "#" in uri else uri.split("/")[-1]
            if prop_name not in exclude_properties:
                filtered_data[uri] = value

        # Build graph via InstanceWriter
        graph = Graph()
        self._instance_writer._setup_namespaces(graph)
        instance_ref = self._instance_writer.create_single_instance(
            graph, filtered_data, class_uri, instance_id
        )

        # Post-process: add rdf:type for object property targets
        DYN = Namespace(self.DYN_NS)
        for uri, value in filtered_data.items():
            if value is None or value == "":
                continue
            prop_name = uri.split("#")[-1] if "#" in uri else uri.split("/")[-1]
            if prop_name in skip_range_types:
                continue

            # Check if the value was resolved to a URIRef (object property)
            rdf_value = self._instance_writer._convert_to_rdf_value(value)
            if isinstance(rdf_value, URIRef) and rdf_value != instance_ref:
                range_class = self._get_range_class(class_uri, prop_name)
                if range_class:
                    range_ref = self._instance_writer._resolve_uri(range_class)
                    graph.add((rdf_value, RDF.type, range_ref))

        # Add extra triples
        if extra_triples:
            for triple in extra_triples:
                graph.add(triple)

        self.logger.debug(
            f"Built graph from form data: {len(graph)} triples, "
            f"class={class_uri}, instance={instance_id}"
        )
        return graph

    # ==================== SHACL VALIDATION HELPERS ====================

    def _validate_page_data(
        self, data_graph: Graph, page_key: Optional[str] = None
    ) -> bool:
        """Validate page data against SHACL shapes using cumulative context.

        Merges all previously stored page graphs (from ``state.page_graphs``)
        with the current page's *data_graph* to give SHACL a full view of
        cross-page references (e.g. DataSeries nodes created by the raw-data
        page can satisfy ``appliedToSeries`` constraints on the pulse-detection
        page).

        On successful validation the current page's graph is stored on state
        under *page_key* so that subsequent pages benefit from it.

        Args:
            data_graph: RDF graph containing this page's instance data.
            page_key: Optional key under which to store *data_graph* in
                ``state.page_graphs`` after a successful validation.

        Returns:
            True if navigation should proceed, False to block.
        """
        from ...validation_results_dialog import ValidationResultsDialog

        # Build cumulative graph: all stored page graphs + current page
        merged = Graph()
        for key, stored_graph in self.state.page_graphs.items():
            # Skip the current page's stale graph (will be replaced)
            if key == page_key:
                continue
            for triple in stored_graph:
                merged.add(triple)
        for triple in data_graph:
            merged.add(triple)

        validator = self._get_cached_validator()
        result = validator.validate(merged)

        if result.has_blocking_issues():
            dialog = ValidationResultsDialog(result, parent=self)
            dialog.exec()
            return False
        elif result.has_any_issues():
            dialog = ValidationResultsDialog(result, parent=self)
            if dialog.exec() != QDialog.DialogCode.Accepted:
                return False

        # Validation passed (or warnings accepted) — store this page's graph
        if page_key is not None:
            self.state.page_graphs[page_key] = data_graph

        return True

    def _get_cached_validator(self) -> "SHACLValidator":
        """Get or create cached SHACL validator from wizard.

        Caches a single SHACLValidator instance on the wizard to avoid
        reloading shapes on every page transition.

        Returns:
            SHACLValidator instance
        """
        from ....core.form_validator import SHACLValidator

        wizard = self.get_wizard()
        if wizard is not None:
            if not hasattr(wizard, '_shacl_validator') or wizard._shacl_validator is None:
                wizard._shacl_validator = SHACLValidator(self.ontology_manager)
            return wizard._shacl_validator

        # Fallback if no wizard (e.g., testing)
        return SHACLValidator(self.ontology_manager)

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
