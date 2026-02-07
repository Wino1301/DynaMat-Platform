"""Raw Data Page - Load and map CSV columns for SHPB analysis.

Thin wrapper around the reusable RawDataLoaderWidget, bridging
widget signals to the SHPB analysis state.
"""

import logging
import os
from pathlib import Path
from typing import Optional

from .base_page import BaseSHPBPage
from .....config import config
from ...base.raw_data_loader import RawDataLoaderConfig, RawDataLoaderWidget

logger = logging.getLogger(__name__)

# Full URI constant used by the ontology
_SHPB_CLASS_URI = "https://dynamat.utep.edu/ontology#SHPBCompression"
DYN_NS = "https://dynamat.utep.edu/ontology#"


class RawDataPage(BaseSHPBPage):
    """Raw data loading page for SHPB analysis.

    Delegates all file loading, column mapping, and preview to
    RawDataLoaderWidget configured for dyn:SHPBCompression.
    """

    def __init__(self, state, ontology_manager, qudt_manager=None, parent=None):
        super().__init__(state, ontology_manager, qudt_manager, parent)

        self.setTitle("Load Raw Data")
        self.setSubTitle("Select a CSV file and map the data columns.")

    def _setup_ui(self) -> None:
        """Setup page UI with embedded RawDataLoaderWidget."""
        layout = self._create_base_layout()

        cfg = RawDataLoaderConfig(test_class_uri=_SHPB_CLASS_URI)
        self._loader = RawDataLoaderWidget(
            cfg, self.ontology_manager, self.qudt_manager, self
        )

        # Connect signals
        self._loader.data_loaded.connect(self._on_data_loaded)
        self._loader.data_cleared.connect(self._on_data_cleared)
        self._loader.error_occurred.connect(
            lambda msg: self.set_status(msg, is_error=True)
        )

        layout.addWidget(self._loader)
        self._add_status_area()

    def initializePage(self) -> None:
        """Initialize page when it becomes current."""
        super().initializePage()

        # Set default directory to specimen's raw folder
        if self.state.specimen_id:
            raw_dir = config.SPECIMENS_DIR / self.state.specimen_id / "raw"
            if raw_dir.exists():
                self._loader.set_default_directory(raw_dir)
            else:
                self._loader.set_default_directory(config.SPECIMENS_DIR)
        else:
            self._loader.set_default_directory(config.SPECIMENS_DIR)

        # If data was previously loaded, reload it
        if self.state.csv_file_path:
            self._loader.load_file(self.state.csv_file_path)

    def validatePage(self) -> bool:
        """Validate before allowing Next."""
        if self._loader.get_dataframe() is None:
            self.show_warning("Data Required", "Please load a data file.")
            return False

        if not self._loader.is_mapping_complete():
            self.show_warning("Mapping Required", "Please map all required columns.")
            return False

        # Ensure state is up to date
        self._save_to_state()
        return True

    # ------------------------------------------------------------------
    # Signal handlers
    # ------------------------------------------------------------------

    def _on_data_loaded(self, data: dict) -> None:
        """Bridge RawDataLoaderWidget data_loaded signal to analysis state."""
        self.state.raw_df = data['dataframe']
        self.state.csv_file_path = data['file_path']
        self.state.column_mapping = data['column_mapping']
        self.state.unit_mapping = data.get('unit_mapping', {})
        self.state.sampling_interval = data.get('sampling_interval')
        self.state.total_samples = data['total_samples']

        # Compute file metadata for RDF export
        file_path = data['file_path']
        df = data['dataframe']
        self.state.raw_file_metadata = {
            f"{DYN_NS}hasFilePath": str(file_path),
            f"{DYN_NS}hasFileFormat": Path(file_path).suffix.lstrip('.'),
            f"{DYN_NS}hasFileSize": os.path.getsize(file_path),
            f"{DYN_NS}hasDataPointCount": len(df),
            f"{DYN_NS}hasColumnCount": len(df.columns),
        }

        self.set_status(
            f"Loaded {data['total_samples']} rows, "
            f"{len(data['dataframe'].columns)} columns"
        )

    def _on_data_cleared(self) -> None:
        """Handle data cleared from widget."""
        self.state.raw_df = None
        self.state.csv_file_path = None
        self.state.column_mapping = {}
        self.state.unit_mapping = {}
        self.state.sampling_interval = None
        self.state.total_samples = None

    def _save_to_state(self) -> None:
        """Ensure all widget data is synced to state before navigation."""
        data = self._loader.get_data()
        if data:
            self.state.raw_df = data['dataframe']
            self.state.csv_file_path = data['file_path']
            self.state.column_mapping = data['column_mapping']
            self.state.unit_mapping = data.get('unit_mapping', {})
            self.state.sampling_interval = data.get('sampling_interval')
            self.state.total_samples = data['total_samples']
