"""Specimen Selection Page - First page of SHPB Analysis Wizard.

Allows user to select a specimen from the database using the EntitySelectorWidget.
"""

import logging
from pathlib import Path
from typing import Optional, Dict, Any

from PyQt6.QtWidgets import QVBoxLayout, QGroupBox, QMessageBox

from .base_page import BaseSHPBPage
from ...base.entity_selector import EntitySelectorConfig, EntitySelectorWidget
from .....ontology.instance_query_builder import InstanceQueryBuilder
from .....config import config
from ..state.test_ttl_loader import TestTTLLoader

logger = logging.getLogger(__name__)


# DynaMat ontology namespace
DYN_NS = "https://dynamat.utep.edu/ontology#"


class SpecimenSelectionPage(BaseSHPBPage):
    """Specimen selection page for SHPB analysis.

    Uses EntitySelectorWidget for:
    - Material filter dropdown (SPARQL-based filtering)
    - Table view of available specimens
    - Selected specimen details display
    """

    def __init__(self, state, ontology_manager, qudt_manager=None, parent=None):
        super().__init__(state, ontology_manager, qudt_manager, parent)

        self.setTitle("Select Specimen")
        self.setSubTitle("Choose a specimen from the database to analyze.")

        # Query builder for specimen lookup
        self.query_builder: Optional[InstanceQueryBuilder] = None

        # Entity selector widget
        self._entity_selector: Optional[EntitySelectorWidget] = None

    def _setup_ui(self) -> None:
        """Setup page UI."""
        layout = self._create_base_layout()

        # Create entity selector configuration
        selector_config = EntitySelectorConfig(
            class_uri=f"{DYN_NS}Specimen",
            display_properties=[
                f"{DYN_NS}hasSpecimenID",
                f"{DYN_NS}hasMaterial",
                f"{DYN_NS}hasShape",
                f"{DYN_NS}hasStructure",
                f"{DYN_NS}hasBatchID",
            ],
            property_labels={
                f"{DYN_NS}hasSpecimenID": "Specimen ID",
                f"{DYN_NS}hasMaterial": "Material",
                f"{DYN_NS}hasShape": "Shape",
                f"{DYN_NS}hasStructure": "Structure",
                f"{DYN_NS}hasBatchID": "Batch",
            },
            filter_properties=[f"{DYN_NS}hasMaterial"],
            filter_labels={
                f"{DYN_NS}hasMaterial": "Material",
            },
            details_properties=[
                f"{DYN_NS}hasSpecimenID",
                f"{DYN_NS}hasMaterial",
                f"{DYN_NS}hasShape",
                f"{DYN_NS}hasStructure",
                f"{DYN_NS}hasOriginalHeight",
                f"{DYN_NS}hasOriginalDiameter",
                f"{DYN_NS}hasMass",
            ],
            details_labels={
                f"{DYN_NS}hasSpecimenID": "Specimen ID",
                f"{DYN_NS}hasMaterial": "Material",
                f"{DYN_NS}hasShape": "Shape",
                f"{DYN_NS}hasStructure": "Structure",
                f"{DYN_NS}hasOriginalHeight": "Original Height",
                f"{DYN_NS}hasOriginalDiameter": "Original Diameter",
                f"{DYN_NS}hasMass": "Mass",
            },
            show_details_panel=True,
            show_search_box=True,
            show_refresh_button=True,
        )

        # Create group box for selector
        selector_group = self._create_group_box("Select Specimen")
        selector_layout = QVBoxLayout(selector_group)

        # Create entity selector widget (query builder set in initializePage)
        self._entity_selector = EntitySelectorWidget(
            config=selector_config,
            ontology_manager=self.ontology_manager,
            parent=self
        )

        # Connect signals
        self._entity_selector.selection_changed.connect(self._on_selection_changed)
        self._entity_selector.entity_selected.connect(self._on_entity_selected)
        self._entity_selector.loading_started.connect(self._on_loading_started)
        self._entity_selector.loading_finished.connect(self._on_loading_finished)
        self._entity_selector.error_occurred.connect(self._on_error)

        selector_layout.addWidget(self._entity_selector)
        layout.addWidget(selector_group)

        self._add_status_area()

    def initializePage(self) -> None:
        """Initialize page when it becomes current."""
        super().initializePage()

        # Initialize query builder if needed
        if self.query_builder is None:
            self._initialize_query_builder()

        # Set query builder on entity selector
        if self._entity_selector and self.query_builder:
            self._entity_selector.set_query_builder(self.query_builder)

            # Load filter options from ontology
            if self._entity_selector._filter_panel:
                self._entity_selector._filter_panel.load_filter_options_from_ontology()

        # If specimen already selected, highlight it
        if self.state.specimen_uri and self._entity_selector:
            self._entity_selector.set_selected_entity(self.state.specimen_uri)

    def validatePage(self) -> bool:
        """Validate before allowing Next.

        If the selected specimen has a linked SHPBCompression test and the
        user hasn't already loaded it, offer to prefill the wizard state
        from the previous test TTL.
        """
        if not self.state.specimen_uri:
            self.show_warning("Selection Required", "Please select a specimen before continuing.")
            return False

        if not self.state.specimen_data:
            self.show_warning("Data Error", "Failed to load specimen data. Please try selecting again.")
            return False

        # Check for existing SHPB test on this specimen
        if not self.state._loaded_from_previous:
            test_ref = self.state.specimen_data.get(f"{DYN_NS}hasSHPBCompressionTest")
            if test_ref:
                self._offer_load_previous(test_ref)

        return True

    # ------------------------------------------------------------------
    # Previous-test loading
    # ------------------------------------------------------------------

    def _offer_load_previous(self, test_ref) -> None:
        """Show dialog asking whether to load a previous test.

        Args:
            test_ref: URI string (or list) of the linked SHPBCompression test.
        """
        # Normalize to single URI string
        if isinstance(test_ref, list):
            test_ref = test_ref[0]
        test_uri = str(test_ref)

        msg = QMessageBox(self)
        msg.setIcon(QMessageBox.Icon.Question)
        msg.setWindowTitle("Previous Test Found")
        msg.setText(
            "This specimen has a previously completed SHPB test.\n\n"
            "Would you like to load the previous test parameters?"
        )
        load_btn = msg.addButton("Load Previous Test", QMessageBox.ButtonRole.AcceptRole)
        msg.addButton("Start New Analysis", QMessageBox.ButtonRole.RejectRole)
        msg.exec()

        if msg.clickedButton() != load_btn:
            # User chose new analysis — mark as handled so we don't ask again
            self.state._loaded_from_previous = True
            return

        # Discover the TTL file
        ttl_path = self._find_test_ttl(test_uri)
        if ttl_path is None:
            self.show_warning(
                "File Not Found",
                "Could not locate the test TTL file for the previous analysis."
            )
            return

        # Load TTL into state
        loader = TestTTLLoader()
        success = loader.load(ttl_path, self.state)

        if success:
            self.set_status("Loaded previous test parameters")
            self.logger.info(f"Loaded previous test from {ttl_path}")
        else:
            self.show_warning(
                "Load Failed",
                "Failed to parse the previous test TTL. Starting with empty state."
            )
            self.state._loaded_from_previous = True

    def _find_test_ttl(self, test_uri: str) -> Optional[Path]:
        """Locate the TTL file for a test URI.

        Tries:
        1. Exact match: specimen_dir / {test_local_name}.ttl
        2. Hyphen/underscore variants
        3. Glob fallback: *SHPBTest*.ttl

        Args:
            test_uri: Full URI of the test individual.

        Returns:
            Path to TTL file, or None if not found.
        """
        if not self.state.specimen_id:
            return None

        specimen_dir = config.SPECIMENS_DIR / self.state.specimen_id

        # Also try underscore variant of specimen ID for folder name
        specimen_id_underscore = self.state.specimen_id.replace("-", "_")
        alt_specimen_dir = config.SPECIMENS_DIR / specimen_id_underscore

        for sdir in (specimen_dir, alt_specimen_dir):
            if not sdir.exists():
                continue

            # Extract local name from URI
            test_local = test_uri.split("#")[-1] if "#" in test_uri else test_uri.split("/")[-1]

            # Try exact match
            ttl_path = sdir / f"{test_local}.ttl"
            if ttl_path.exists():
                return ttl_path

            # Try hyphen/underscore variants
            for variant in (
                test_local.replace("-", "_"),
                test_local.replace("_", "-"),
            ):
                ttl_path = sdir / f"{variant}.ttl"
                if ttl_path.exists():
                    return ttl_path

            # Glob fallback
            matches = list(sdir.glob("*SHPBTest*.ttl"))
            if matches:
                return matches[0]

        return None

    def _initialize_query_builder(self) -> None:
        """Initialize the instance query builder."""
        try:
            self.query_builder = InstanceQueryBuilder(self.ontology_manager)

            # Scan specimens directory
            if config.SPECIMENS_DIR.exists():
                indexed = self.query_builder.scan_and_index(
                    config.SPECIMENS_DIR,
                    f"{DYN_NS}Specimen",
                    "*_specimen.ttl"
                )
                self.logger.info(f"Indexed {indexed} specimens")
            else:
                self.logger.warning("Specimens directory not found")

        except Exception as e:
            self.logger.error(f"Failed to initialize query builder: {e}")
            self.set_status(f"Error: {e}", is_error=True)

    def _on_selection_changed(self, data: Dict[str, Any]) -> None:
        """Handle selection change - load full specimen details."""
        self._load_specimen_details(data)

    def _on_entity_selected(self, data: Dict[str, Any]) -> None:
        """Handle double-click selection - same as selection change."""
        self._load_specimen_details(data)

    def _on_loading_started(self) -> None:
        """Handle loading started."""
        self.show_progress()

    def _on_loading_finished(self, count: int) -> None:
        """Handle loading finished."""
        self.hide_progress()
        self.set_status(f"Found {count} specimen(s)")

    def _on_error(self, error: str) -> None:
        """Handle error from entity selector."""
        self.set_status(f"Error: {error}", is_error=True)

    def _load_specimen_details(self, specimen_metadata: Dict[str, Any]) -> None:
        """Load full specimen details and update state.

        Args:
            specimen_metadata: Basic specimen metadata from selector
        """
        try:
            specimen_uri = specimen_metadata.get('uri')
            if not specimen_uri:
                self.logger.warning("No URI in specimen metadata")
                return

            # Load full specimen data if not already loaded
            if 'file_path' not in specimen_metadata or len(specimen_metadata) < 10:
                # Need to load full data
                if self.query_builder:
                    full_data = self.query_builder.load_full_instance_data(specimen_uri)
                    if full_data:
                        full_data['uri'] = specimen_uri
                        full_data['file_path'] = specimen_metadata.get('file_path', '')
                        specimen_metadata = full_data

            # Update state
            self.state.specimen_uri = specimen_uri
            self.state.specimen_data = specimen_metadata
            self.state.specimen_id = specimen_metadata.get(
                f"{DYN_NS}hasSpecimenID",
                specimen_uri.split('#')[-1] if '#' in specimen_uri else specimen_uri
            )

            self.set_status(f"Selected: {self.state.specimen_id}")
            self.logger.info(f"Selected specimen: {self.state.specimen_id}")

        except Exception as e:
            self.logger.error(f"Failed to load specimen details: {e}")
            self.set_status(f"Error: {e}", is_error=True)
