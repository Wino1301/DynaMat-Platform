"""Raw Data Page - Load and map CSV columns for SHPB analysis.

Thin wrapper around the reusable RawDataLoaderWidget, bridging
widget signals to the SHPB analysis state.
"""

import logging
import os
from pathlib import Path
from typing import Optional, Dict, List

import numpy as np

from PyQt6.QtWidgets import QGroupBox, QGridLayout, QLabel, QComboBox, QScrollArea, QWidget, QVBoxLayout
from rdflib import Graph, Namespace, URIRef
from rdflib.namespace import RDF

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
        """Setup scrollable page: Data File → Strain Gauge → Column Mapping → Preview."""
        layout = self._create_base_layout()

        # Wrap everything in a scroll area for comfortable viewing
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)

        # --- Raw Data Loader (provides Data File, Column Mapping, Preview) ---
        cfg = RawDataLoaderConfig(test_class_uri=_SHPB_CLASS_URI)
        self._loader = RawDataLoaderWidget(
            cfg, self.ontology_manager, self.qudt_manager, content
        )

        # Connect signals
        self._loader.data_loaded.connect(self._on_data_loaded)
        self._loader.data_cleared.connect(self._on_data_cleared)
        self._loader.error_occurred.connect(
            lambda msg: self.set_status(msg, is_error=True)
        )

        # --- Strain Gauge group (inject between Data File and Column Mapping) ---
        gauge_group = self._create_group_box("Strain Gauge Configuration")
        gauge_layout = QGridLayout(gauge_group)

        gauge_layout.addWidget(QLabel("Incident Bar Gauge:"), 0, 0)
        self._incident_gauge_combo = QComboBox()
        gauge_layout.addWidget(self._incident_gauge_combo, 0, 1)

        gauge_layout.addWidget(QLabel("Transmission Bar Gauge:"), 1, 0)
        self._transmission_gauge_combo = QComboBox()
        gauge_layout.addWidget(self._transmission_gauge_combo, 1, 1)

        gauge_layout.setColumnStretch(1, 1)
        self._populate_gauge_combos()

        # Insert gauge group into the loader's internal layout at index 1
        # (between Data File [0] and Column Mapping [1→2])
        loader_layout = self._loader.layout()
        if loader_layout is not None:
            loader_layout.insertWidget(1, gauge_group)

        content_layout.addWidget(self._loader)

        scroll.setWidget(content)
        layout.addWidget(scroll)
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

        # Restore gauge selections from state
        self._restore_gauge_selection()

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

        # Run SHACL validation on partial graph
        validation_graph = self._build_validation_graph()
        if validation_graph and not self._validate_page_data(
            validation_graph, page_key="raw_data"
        ):
            return False

        return True

    # ------------------------------------------------------------------
    # Strain gauge helpers
    # ------------------------------------------------------------------

    def _populate_gauge_combos(self) -> None:
        """Populate strain gauge combo boxes from ontology individuals."""
        try:
            query = """
            PREFIX dyn: <https://dynamat.utep.edu/ontology#>
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
            SELECT ?uri ?label WHERE {
                ?uri a dyn:StrainGauge .
                OPTIONAL { ?uri rdfs:label ?label }
            } ORDER BY ?label
            """
            results = self.ontology_manager.sparql_executor.execute_query(query)

            for combo in (self._incident_gauge_combo, self._transmission_gauge_combo):
                combo.clear()
                combo.addItem("-- Select gauge --", "")
                for row in results:
                    uri = str(row['uri'])
                    label = str(row.get('label', uri.split('#')[-1]))
                    combo.addItem(label, uri)

        except Exception as e:
            self.logger.warning(f"Could not load strain gauges: {e}")

    def _restore_gauge_selection(self) -> None:
        """Restore gauge combo selections from state."""
        inc_uri = self.state.gauge_mapping.get('incident', '')
        tra_uri = self.state.gauge_mapping.get('transmitted', '')

        for combo, uri in [
            (self._incident_gauge_combo, inc_uri),
            (self._transmission_gauge_combo, tra_uri),
        ]:
            if uri:
                idx = combo.findData(uri)
                if idx >= 0:
                    combo.setCurrentIndex(idx)

    def _save_gauge_selection(self) -> None:
        """Save gauge combo selections to state."""
        self.state.gauge_mapping = {
            'incident': self._incident_gauge_combo.currentData() or None,
            'transmitted': self._transmission_gauge_combo.currentData() or None,
        }

    # ------------------------------------------------------------------
    # Validation graph
    # ------------------------------------------------------------------

    def _build_validation_graph(self) -> Optional[Graph]:
        """Build partial RDF graph for SHACL validation of raw data.

        Creates:
        - An AnalysisFile node with file metadata (via InstanceWriter)
        - A RawSignal + DataSeries node per mapped column with
          hasSamplingRate and measuredBy
        - SeriesType individual type declarations
        - Strain gauge links on the equipment node

        Returns:
            RDF graph, or None on error.
        """
        try:
            DYN = Namespace(DYN_NS)
            writer = self._instance_writer
            g = Graph()
            writer._setup_namespaces(g)

            test_id = (
                f"{self.state.specimen_id}_SHPBTest"
                if self.state.specimen_id
                else "_val"
            )

            # AnalysisFile node
            file_path = (
                str(self.state.csv_file_path)
                if self.state.csv_file_path
                else "raw_data.csv"
            )
            file_form_data = {
                f"{DYN_NS}hasFilePath": file_path,
                f"{DYN_NS}hasFileFormat": "csv",
            }
            if self.state.total_samples is not None:
                file_form_data[f"{DYN_NS}hasDataPointCount"] = self.state.total_samples
            if self.state.raw_df is not None:
                file_form_data[f"{DYN_NS}hasColumnCount"] = len(self.state.raw_df.columns)

            raw_file_ref = writer.create_single_instance(
                g, file_form_data, f"{DYN_NS}AnalysisFile", f"{test_id}_raw_csv"
            )

            # Compute sampling rate from time column
            sampling_rate = self._compute_sampling_rate()

            # Gauge URI mapping
            inc_gauge = self.state.gauge_mapping.get("incident")
            tra_gauge = self.state.gauge_mapping.get("transmitted")
            gauge_for_signal: Dict[str, list] = {
                "time": [u for u in (inc_gauge, tra_gauge) if u],
                "incident": [inc_gauge] if inc_gauge else [],
                "transmitted": [tra_gauge] if tra_gauge else [],
            }

            # Load ontology-driven series metadata
            from .....mechanical.shpb.io.series_config import get_series_metadata
            series_metadata = get_series_metadata()

            for key, col_name in self.state.column_mapping.items():
                meta = series_metadata.get(key, {})

                series_form_data: Dict = {
                    f"{DYN_NS}hasColumnName": col_name,
                    f"{DYN_NS}hasDataFile": str(raw_file_ref),
                }

                # Add column index from raw_df column position
                if self.state.raw_df is not None and col_name in self.state.raw_df.columns:
                    col_idx = list(self.state.raw_df.columns).index(col_name)
                    series_form_data[f"{DYN_NS}hasColumnIndex"] = col_idx

                # Ontology-driven metadata
                if meta.get('series_type'):
                    series_form_data[f"{DYN_NS}hasSeriesType"] = meta['series_type']
                if meta.get('unit'):
                    series_form_data[f"{DYN_NS}hasSeriesUnit"] = meta['unit']
                if meta.get('quantity_kind'):
                    series_form_data[f"{DYN_NS}hasQuantityKind"] = meta['quantity_kind']
                if meta.get('legend_name'):
                    series_form_data[f"{DYN_NS}hasLegendName"] = meta['legend_name']

                if self.state.total_samples is not None:
                    series_form_data[f"{DYN_NS}hasDataPointCount"] = self.state.total_samples

                if sampling_rate is not None:
                    series_form_data[f"{DYN_NS}hasSamplingRate"] = sampling_rate

                # measuredBy → strain gauge(s) as list
                gauges = gauge_for_signal.get(key, [])
                if gauges:
                    series_form_data[f"{DYN_NS}measuredBy"] = gauges if len(gauges) > 1 else gauges[0]

                series_ref = writer.create_single_instance(
                    g, series_form_data, f"{DYN_NS}RawSignal", f"{test_id}_{key}"
                )
                # Also declare as DataSeries
                g.add((series_ref, RDF.type, DYN.DataSeries))

                # Store URI in state for cross-page linking
                self.state.raw_series_uris[key] = str(series_ref)

                # Declare SeriesType individual
                series_type_uri = meta.get('series_type')
                if series_type_uri:
                    st_ref = URIRef(series_type_uri)
                    g.add((st_ref, RDF.type, DYN.SeriesType))

                # Declare gauge types
                for gauge_uri in gauges:
                    gauge_ref = URIRef(gauge_uri)
                    g.add((gauge_ref, RDF.type, DYN.StrainGauge))
                    g.add((gauge_ref, RDF.type, DYN.MeasurementEquipment))

            # Strain gauge → SHPBCompression link triples
            # Same subject URI as equipment page, without rdf:type
            equipment_node = DYN["_val_equipment"]
            if inc_gauge:
                gauge_ref = URIRef(inc_gauge)
                g.add((equipment_node, DYN.hasIncidentStrainGauge, gauge_ref))
                g.add((gauge_ref, RDF.type, DYN.StrainGauge))
            if tra_gauge:
                gauge_ref = URIRef(tra_gauge)
                g.add((equipment_node, DYN.hasTransmissionStrainGauge, gauge_ref))
                g.add((gauge_ref, RDF.type, DYN.StrainGauge))

            return g

        except Exception as e:
            self.logger.error(f"Failed to build validation graph: {e}")
            return None

    def _compute_sampling_rate(self) -> Optional[float]:
        """Compute sampling rate in Hz from the time column.

        Uses the first two time values to determine the sampling interval,
        then converts to Hz.  Falls back to ``state.sampling_interval``
        if the time column is unavailable.

        Returns:
            Sampling rate in Hz, or None if undetermined.
        """
        try:
            time_arr = self.state.get_raw_signal("time")
            if time_arr is not None and len(time_arr) >= 2:
                dt = float(time_arr[1] - time_arr[0])
                if dt > 0:
                    # time column is typically in seconds or milliseconds
                    # if dt < 1e-3, it's likely in seconds already
                    return 1.0 / dt

            # Fallback: sampling_interval is in ms
            if self.state.sampling_interval is not None and self.state.sampling_interval > 0:
                return 1000.0 / self.state.sampling_interval

        except Exception as e:
            self.logger.warning(f"Could not compute sampling rate: {e}")

        return None

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
        self._save_gauge_selection()
