"""TestTTLLoader - Parse a previously exported SHPB test TTL and populate analysis state.

Reads an SHPB test TTL file and extracts all metadata into the
SHPBAnalysisState form-data dicts so that wizard pages can restore
previous parameter values via their existing ``_restore_*()`` patterns.
"""

import logging
from pathlib import Path
from typing import Optional, Dict, Any

import pandas as pd
from rdflib import Graph, Namespace, Literal, URIRef, BNode
from rdflib.namespace import RDF

from .analysis_state import SHPBAnalysisState

logger = logging.getLogger(__name__)

DYN_NS = "https://dynamat.utep.edu/ontology#"
DYN = Namespace(DYN_NS)
QUDT = Namespace("http://qudt.org/schema/qudt/")
DQV = Namespace("http://www.w3.org/ns/dqv#")
OA = Namespace("http://www.w3.org/ns/oa#")

# Properties on SHPBCompression that link to sub-instances (not equipment form data)
_SUB_INSTANCE_PREDICATES = {
    f"{DYN_NS}hasAlignmentParams",
    f"{DYN_NS}hasScienceTrustCard",
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
            self._load_trust_card_form_data(state)
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
                # Legacy validity fields (kept for backward compat with old TTL files)
                f"{DYN_NS}hasTestValidity",
                f"{DYN_NS}hasValidityCriteria",
                f"{DYN_NS}hasValidityNotes",
                f"{DYN_NS}hasValidityOverrideReason",
                f"{DYN_NS}isValidityOverridden",
                # New DQV fields
                f"{DYN_NS}isAssessmentOverridden",
                f"{DYN_NS}hasOverrideReason",
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

    def _load_trust_card_form_data(self, state: SHPBAnalysisState) -> None:
        """Extract ScienceTrustCard into state.metrics_form_data.

        For backward compat, also checks for legacy EquilibriumMetrics.
        """
        # New DQV format
        for tc_uri in self._graph.subjects(RDF.type, DYN.ScienceTrustCard):
            state.metrics_form_data = self._extract_properties(tc_uri)
            return
        # Legacy format — load into equilibrium_form_data for old files
        for eq_uri in self._graph.subjects(RDF.type, DYN.EquilibriumMetrics):
            state.equilibrium_form_data = self._extract_properties(eq_uri)
            return

    def _load_tukey_form_data(self, state: SHPBAnalysisState) -> None:
        """Extract hasTukeyAlphaParam from main test instance into state.tukey_form_data."""
        alpha = self._get_literal(self._test_uri, DYN.hasTukeyAlphaParam)
        if alpha is not None:
            state.tukey_form_data = {
                f"{DYN_NS}isTukeyEnabled": True,
                f"{DYN_NS}hasTukeyAlphaParam": float(alpha),
            }

    def _load_export_form_data(self, state: SHPBAnalysisState) -> None:
        """Extract export metadata into state.export_form_data.

        Handles both new DQV fields and legacy validity fields for backward compat.
        """
        form_data = {}

        test_type = self._get_object(self._test_uri, DYN.hasTestType)
        if test_type:
            form_data[f"{DYN_NS}hasTestType"] = str(test_type)

        # New DQV override fields
        override_flag = self._get_literal(self._test_uri, DYN.isAssessmentOverridden)
        if override_flag is not None:
            form_data[f"{DYN_NS}isAssessmentOverridden"] = bool(override_flag)

        override_reason = self._get_literal(self._test_uri, DYN.hasOverrideReason)
        if override_reason is not None:
            form_data[f"{DYN_NS}hasOverrideReason"] = str(override_reason)

        # Legacy validity fields (backward compat with old TTL files)
        if not override_flag:
            old_flag = self._get_literal(self._test_uri, DYN.isValidityOverridden)
            if old_flag is not None:
                form_data[f"{DYN_NS}isAssessmentOverridden"] = bool(old_flag)
            old_reason = self._get_literal(self._test_uri, DYN.hasValidityOverrideReason)
            if old_reason is not None:
                form_data[f"{DYN_NS}hasOverrideReason"] = str(old_reason)

        if form_data:
            state.export_form_data = form_data

    # ------------------------------------------------------------------
    # RDF helpers
    # ------------------------------------------------------------------

    def _extract_properties(self, subject: URIRef) -> Dict[str, Any]:
        """Extract all properties of a subject into a URI-keyed dict.

        Skips rdf:type triples.  For QuantityValue/DQV BNodes, returns
        measurement dicts compatible with InstanceWriter patterns.
        Multi-valued predicates (e.g. dqv:hasQualityMeasurement) are
        collected into lists.
        """
        props = {}
        for pred, obj in self._graph.predicate_objects(subject):
            if pred == RDF.type:
                continue
            key = str(pred)
            value = self._python_value(obj)
            if key in props:
                # Convert to list for multi-valued predicates
                existing = props[key]
                if isinstance(existing, list):
                    existing.append(value)
                else:
                    props[key] = [existing, value]
            else:
                props[key] = value
        return props

    def _get_literal(self, subject: URIRef, predicate: URIRef) -> Any:
        """Get a single literal value for subject+predicate.

        For QuantityValue BNodes, extracts and returns the numeric value.
        """
        for obj in self._graph.objects(subject, predicate):
            if isinstance(obj, Literal):
                return obj.toPython()
            if self._is_quantity_value(obj):
                qv = self._extract_quantity_value(obj)
                return qv.get('value')
        return None

    def _get_object(self, subject: URIRef, predicate: URIRef) -> Optional[URIRef]:
        """Get a single object (URI or Literal) for subject+predicate."""
        for obj in self._graph.objects(subject, predicate):
            return obj
        return None

    def _python_value(self, obj) -> Any:
        """Convert an RDF term to a Python value.

        Handles QuantityValue and DQV BNodes by returning appropriate dicts.
        """
        if isinstance(obj, Literal):
            return obj.toPython()
        if self._is_quantity_value(obj):
            return self._extract_quantity_value(obj)
        if self._is_quality_measurement(obj):
            return self._extract_quality_measurement(obj)
        if self._is_quality_annotation(obj):
            return self._extract_quality_annotation(obj)
        return str(obj)

    def _is_quantity_value(self, node) -> bool:
        """Check if an RDF node is a qudt:QuantityValue blank node."""
        if not isinstance(node, BNode):
            return False
        return (node, RDF.type, QUDT.QuantityValue) in self._graph

    def _extract_quantity_value(self, bnode: BNode) -> Dict[str, Any]:
        """Extract measurement dict from a QuantityValue BNode.

        Returns dict compatible with QuantityValueWidget.getData() format:
        {'value': float, 'unit': str, 'quantity_kind': str}
        """
        result = {}

        for obj in self._graph.objects(bnode, QUDT.numericValue):
            if isinstance(obj, Literal):
                result['value'] = float(obj.toPython())
                break

        for obj in self._graph.objects(bnode, QUDT.unit):
            result['unit'] = str(obj)
            result['reference_unit'] = str(obj)
            break

        for obj in self._graph.objects(bnode, QUDT.hasQuantityKind):
            result['quantity_kind'] = str(obj)
            break

        for obj in self._graph.objects(bnode, QUDT.standardUncertainty):
            if isinstance(obj, Literal):
                result['uncertainty'] = float(obj.toPython())
                break

        return result

    # -- DQV BNode helpers -------------------------------------------------

    def _is_quality_measurement(self, node) -> bool:
        """Check if an RDF node is a dqv:QualityMeasurement blank node."""
        if not isinstance(node, BNode):
            return False
        return (node, RDF.type, DQV.QualityMeasurement) in self._graph

    def _extract_quality_measurement(self, bnode: BNode) -> Dict[str, Any]:
        """Extract dict from a dqv:QualityMeasurement BNode.

        Returns dict compatible with InstanceWriter's quality_measurement pattern.
        """
        result: Dict[str, Any] = {'pattern': 'quality_measurement'}

        for obj in self._graph.objects(bnode, DQV.isMeasurementOf):
            result['metric'] = str(obj)
            break

        for obj in self._graph.objects(bnode, DQV.value):
            if isinstance(obj, Literal):
                result['value'] = float(obj.toPython())
            break

        for obj in self._graph.objects(bnode, DQV.computedOn):
            result['computed_on'] = str(obj)
            break

        for obj in self._graph.objects(bnode, DYN.assessment):
            if isinstance(obj, Literal):
                result['assessment'] = str(obj)
            break

        for obj in self._graph.objects(bnode, QUDT.unit):
            result['unit'] = str(obj)
            break

        for obj in self._graph.objects(bnode, QUDT.standardUncertainty):
            if isinstance(obj, Literal):
                result['uncertainty'] = float(obj.toPython())
            break

        for obj in self._graph.objects(bnode, DYN.windowSpec):
            if isinstance(obj, Literal):
                result['window'] = str(obj)
            break

        return result

    def _is_quality_annotation(self, node) -> bool:
        """Check if an RDF node is a dqv:QualityCertificate blank node."""
        if not isinstance(node, BNode):
            return False
        return (node, RDF.type, DQV.QualityCertificate) in self._graph

    def _extract_quality_annotation(self, bnode: BNode) -> Dict[str, Any]:
        """Extract dict from a dqv:QualityCertificate BNode.

        Returns dict compatible with InstanceWriter's quality_annotation pattern.
        """
        result: Dict[str, Any] = {'pattern': 'quality_annotation'}

        for obj in self._graph.objects(bnode, OA.hasTarget):
            result['target'] = str(obj)
            break

        for obj in self._graph.objects(bnode, OA.hasBody):
            result['body'] = str(obj)
            break

        for obj in self._graph.objects(bnode, OA.motivatedBy):
            result['motivation'] = str(obj)
            break

        return result
