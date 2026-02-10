"""TestTTLLoader - Parse a previously exported SHPB test TTL and populate analysis state.

Reads an SHPB test TTL file and extracts all metadata into the
SHPBAnalysisState form-data dicts so that wizard pages can restore
previous parameter values via their existing ``_restore_*()`` patterns.
"""

import logging
from pathlib import Path
from typing import Optional, Dict, Any

import pandas as pd
from rdflib import Graph, Namespace, Literal, URIRef
from rdflib.namespace import RDF

from .analysis_state import SHPBAnalysisState

logger = logging.getLogger(__name__)

DYN_NS = "https://dynamat.utep.edu/ontology#"
DYN = Namespace(DYN_NS)

# Properties on SHPBCompression that link to sub-instances (not equipment form data)
_SUB_INSTANCE_PREDICATES = {
    f"{DYN_NS}hasAlignmentParams",
    f"{DYN_NS}hasEquilibriumMetrics",
    f"{DYN_NS}hasDataSeries",
    f"{DYN_NS}hasPulseDetectionParams",
    f"{DYN_NS}performedOn",
}

# Series type local names → column_mapping keys
_SERIES_TYPE_TO_KEY = {
    "Time": "time",
    "IncidentPulse": "incident",
    "TransmittedPulse": "transmitted",
}


class TestTTLLoader:
    """Parses a test TTL file and populates SHPBAnalysisState fields."""

    def __init__(self):
        self._graph: Optional[Graph] = None
        self._test_uri: Optional[URIRef] = None
        self._specimen_dir: Optional[Path] = None

    def load(self, ttl_path: Path, state: SHPBAnalysisState) -> bool:
        """Load a test TTL file into analysis state.

        Args:
            ttl_path: Path to the test TTL file.
            state: SHPBAnalysisState to populate.

        Returns:
            True if loading succeeded, False otherwise.
        """
        try:
            self._graph = Graph()
            self._graph.parse(str(ttl_path), format="turtle")
            self._specimen_dir = ttl_path.parent

            if not self._find_test_uri():
                logger.error("No SHPBCompression instance found in TTL")
                return False

            self._load_test_id(state)
            self._load_raw_data(state)
            self._load_equipment_form_data(state)
            self._load_detection_form_data(state)
            self._load_alignment_form_data(state)
            self._load_equilibrium_form_data(state)
            self._load_tukey_form_data(state)
            self._load_export_form_data(state)

            state._loaded_from_previous = True
            logger.info(f"Loaded previous test from {ttl_path}")
            return True

        except Exception as e:
            logger.error(f"Failed to load test TTL: {e}", exc_info=True)
            return False

    # ------------------------------------------------------------------
    # Internal extraction methods
    # ------------------------------------------------------------------

    def _find_test_uri(self) -> bool:
        """Find the SHPBCompression instance URI in the graph."""
        for s in self._graph.subjects(RDF.type, DYN.SHPBCompression):
            self._test_uri = s
            return True
        return False

    def _load_test_id(self, state: SHPBAnalysisState) -> None:
        """Extract hasTestID → state.test_id."""
        test_id = self._get_literal(self._test_uri, DYN.hasTestID)
        if test_id is not None:
            state.test_id = str(test_id)

    def _load_raw_data(self, state: SHPBAnalysisState) -> None:
        """Find raw AnalysisFile, load CSV, build column_mapping and gauge_mapping."""
        # Find the raw AnalysisFile (file path containing "raw")
        raw_file_uri = None
        raw_file_path_str = None

        for file_uri in self._graph.subjects(RDF.type, DYN.AnalysisFile):
            fp = self._get_literal(file_uri, DYN.hasFilePath)
            if fp and "raw" in str(fp).lower():
                raw_file_uri = file_uri
                raw_file_path_str = str(fp)
                break

        if not raw_file_path_str:
            logger.warning("No raw AnalysisFile found in TTL")
            return

        # Resolve relative path against specimen directory
        csv_path = self._specimen_dir / raw_file_path_str
        if not csv_path.exists():
            # Try normalizing path separators
            csv_path = self._specimen_dir / raw_file_path_str.replace("\\", "/")
        if not csv_path.exists():
            logger.warning(f"Raw CSV not found at {csv_path}")
            return

        # Load CSV
        try:
            state.raw_df = pd.read_csv(csv_path)
            state.csv_file_path = csv_path
            state.total_samples = len(state.raw_df)
        except Exception as e:
            logger.warning(f"Failed to load raw CSV: {e}")
            return

        # Build column_mapping and gauge_mapping from RawSignal nodes
        state.column_mapping = {}
        state.gauge_mapping = {}

        for signal_uri in self._graph.subjects(RDF.type, DYN.RawSignal):
            series_type = self._get_object(signal_uri, DYN.hasSeriesType)
            col_name = self._get_literal(signal_uri, DYN.hasColumnName)

            if series_type is None or col_name is None:
                continue

            # Map series type to column_mapping key
            type_local = str(series_type).split("#")[-1]
            key = _SERIES_TYPE_TO_KEY.get(type_local)
            if key:
                state.column_mapping[key] = str(col_name)

            # Extract gauge mapping
            gauge_uri = self._get_object(signal_uri, DYN.measuredBy)
            if gauge_uri and key and key != "time":
                state.gauge_mapping[key] = str(gauge_uri)

            # Extract sampling interval from time signal
            if key == "time":
                si = self._get_literal(signal_uri, DYN.hasSamplingInterval)
                if si is not None:
                    state.sampling_interval = float(si)

        # Build raw file metadata
        if raw_file_uri:
            state.raw_file_metadata = self._extract_properties(raw_file_uri)

    def _load_equipment_form_data(self, state: SHPBAnalysisState) -> None:
        """Extract direct properties of SHPBCompression as equipment form data.

        Excludes sub-instance link predicates and rdf:type.
        """
        form_data = {}
        for pred, obj in self._graph.predicate_objects(self._test_uri):
            pred_str = str(pred)

            # Skip rdf:type and sub-instance links
            if pred == RDF.type:
                continue
            if pred_str in _SUB_INSTANCE_PREDICATES:
                continue
            # Skip hasDataSeries, hasPulseDetectionParams links
            if pred_str.startswith(DYN_NS) and any(
                pred_str.endswith(suffix)
                for suffix in ("hasDataSeries", "hasPulseDetectionParams")
            ):
                continue

            # Also skip hasTestID, hasTukeyAlpha, export-related fields
            # (they go into their own form data dicts)
            if pred_str in (
                f"{DYN_NS}hasTestID",
                f"{DYN_NS}hasTukeyAlpha",
                f"{DYN_NS}hasTestValidity",
                f"{DYN_NS}hasValidityCriteria",
                f"{DYN_NS}hasValidityNotes",
                f"{DYN_NS}hasTestType",
            ):
                continue

            form_data[pred_str] = self._python_value(obj)

        if form_data:
            state.equipment_form_data = form_data

    def _load_detection_form_data(self, state: SHPBAnalysisState) -> None:
        """Extract 3x PulseDetectionParams into state.detection_form_data."""
        state.detection_form_data = {}

        for det_uri in self._graph.subjects(RDF.type, DYN.PulseDetectionParams):
            uri_str = str(det_uri)
            props = self._extract_properties(det_uri)

            # Classify by URI suffix
            if uri_str.endswith("_inc_detect"):
                state.detection_form_data["incident"] = props
            elif uri_str.endswith("_trs_detect"):
                state.detection_form_data["transmitted"] = props
            elif uri_str.endswith("_ref_detect"):
                state.detection_form_data["reflected"] = props
            else:
                # Fallback: try to classify by polarity
                polarity = props.get(f"{DYN_NS}hasDetectionPolarity", "")
                applied = props.get(f"{DYN_NS}appliedToSeries", "")
                if "incident" in str(applied).lower() and polarity == "compressive":
                    state.detection_form_data["incident"] = props
                elif "transmitted" in str(applied).lower():
                    state.detection_form_data["transmitted"] = props
                elif polarity == "tensile":
                    state.detection_form_data["reflected"] = props

    def _load_alignment_form_data(self, state: SHPBAnalysisState) -> None:
        """Extract AlignmentParams into state.alignment_form_data."""
        for align_uri in self._graph.subjects(RDF.type, DYN.AlignmentParams):
            state.alignment_form_data = self._extract_properties(align_uri)
            break  # Only one expected

    def _load_equilibrium_form_data(self, state: SHPBAnalysisState) -> None:
        """Extract EquilibriumMetrics into state.equilibrium_form_data."""
        for eq_uri in self._graph.subjects(RDF.type, DYN.EquilibriumMetrics):
            state.equilibrium_form_data = self._extract_properties(eq_uri)
            break  # Only one expected

    def _load_tukey_form_data(self, state: SHPBAnalysisState) -> None:
        """Extract hasTukeyAlpha from main test instance into state.tukey_form_data."""
        alpha = self._get_literal(self._test_uri, DYN.hasTukeyAlpha)
        if alpha is not None:
            state.tukey_form_data = {
                f"{DYN_NS}isTukeyEnabled": True,
                f"{DYN_NS}hasTukeyAlphaParam": float(alpha),
            }

    def _load_export_form_data(self, state: SHPBAnalysisState) -> None:
        """Extract validity/test type into state.export_form_data."""
        form_data = {}

        validity = self._get_object(self._test_uri, DYN.hasTestValidity)
        if validity:
            form_data[f"{DYN_NS}hasTestValidity"] = str(validity)

        criteria = self._get_object(self._test_uri, DYN.hasValidityCriteria)
        if criteria:
            form_data[f"{DYN_NS}hasValidityCriteria"] = str(criteria)

        notes = self._get_literal(self._test_uri, DYN.hasValidityNotes)
        if notes is not None:
            form_data[f"{DYN_NS}hasValidityNotes"] = str(notes)

        test_type = self._get_object(self._test_uri, DYN.hasTestType)
        if test_type:
            form_data[f"{DYN_NS}hasTestType"] = str(test_type)

        if form_data:
            state.export_form_data = form_data

    # ------------------------------------------------------------------
    # RDF helpers
    # ------------------------------------------------------------------

    def _extract_properties(self, subject: URIRef) -> Dict[str, Any]:
        """Extract all properties of a subject into a URI-keyed dict.

        Skips rdf:type triples.
        """
        props = {}
        for pred, obj in self._graph.predicate_objects(subject):
            if pred == RDF.type:
                continue
            props[str(pred)] = self._python_value(obj)
        return props

    def _get_literal(self, subject: URIRef, predicate: URIRef) -> Any:
        """Get a single literal value for subject+predicate."""
        for obj in self._graph.objects(subject, predicate):
            if isinstance(obj, Literal):
                return obj.toPython()
        return None

    def _get_object(self, subject: URIRef, predicate: URIRef) -> Optional[URIRef]:
        """Get a single object (URI or Literal) for subject+predicate."""
        for obj in self._graph.objects(subject, predicate):
            return obj
        return None

    @staticmethod
    def _python_value(obj) -> Any:
        """Convert an RDF term to a Python value."""
        if isinstance(obj, Literal):
            return obj.toPython()
        return str(obj)
