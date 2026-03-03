"""Extended TTL migration tool for DynaMat Platform.

Migrates old-format specimen and test TTL files to the new format with:
  1.  qudt:QuantityValue BNodes (replaces flat xsd:double literals)
  2.  qudt:standardUncertainty on measurement BNodes
  3.  Proper rdf:type (fixes broken ns1:type from @prefix ns1: <rdf:>)
  4-5. Individual URIs for polarity/metric (replaces string literals)
  6.  URIRef quantity kinds (replaces "qkdv:X"^^xsd:string)
  7.  Split strain gauges (hasStrainGauge → incident + transmission)
  8.  Renamed hasTukeyAlpha → hasTukeyAlphaParam
  9.  Converted hasSamplingInterval (ms) → hasSamplingRate (Hz)
  10. Renamed hasThresholdRatio → hasFrontThreshold
  11. Fixed windowed series types (IncidentPulse → WindowedIncidentPulse etc.)
  12. Moved detection params from series to test node
  13. Added hasAnalysisFile links on test node
  14. Created SegmentationParams from alignment data
  15. Added column metadata on windowed series
  16. Added hasFileName from hasFilePath on AnalysisFile nodes
  17. Fixed hasAnalysisTimestamp xsd:date → xsd:dateTime
  18. Added qudt:relativeStandardUncertainty on processed series

Usage:
    python tools/migrate_to_quantity_value.py                      # dry-run
    python tools/migrate_to_quantity_value.py --apply               # apply in-place
    python tools/migrate_to_quantity_value.py --apply --backup      # apply + .bak
    python tools/migrate_to_quantity_value.py --dir user_data/specimens/DYNML-A356-0001
"""

import argparse
import logging
import math
import shutil
import sys
from pathlib import Path

from rdflib import Graph, Namespace, URIRef, Literal, BNode
from rdflib.namespace import RDF, RDFS, OWL, XSD

# ═══════════════════════════ Namespaces ═══════════════════════════

DYN = Namespace("https://dynamat.utep.edu/ontology#")
QUDT = Namespace("http://qudt.org/schema/qudt/")
UNIT = Namespace("http://qudt.org/vocab/unit/")
QKDV = Namespace("http://qudt.org/vocab/quantitykind/")

# The broken URI produced by  @prefix ns1: <rdf:> .  →  ns1:type
NS1_TYPE = URIRef("rdf:type")

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

# ═══════════════════════════ Configuration ═══════════════════════════

UNCERTAINTY_CONFIG = {
    # Specimen dimensions — all ±0.01 mm
    str(DYN.hasOriginalDiameter): 0.01,
    str(DYN.hasOriginalHeight): 0.01,
    str(DYN.hasFinalDiameter): 0.01,
    str(DYN.hasFinalHeight): 0.01,
    str(DYN.hasOriginalLength): 0.01,
    str(DYN.hasFinalLength): 0.01,
    str(DYN.hasOriginalWidth): 0.01,
    str(DYN.hasFinalWidth): 0.01,
    str(DYN.hasOriginalThickness): 0.01,
    str(DYN.hasFinalThickness): 0.01,
    # Cross-section: COMPUTED separately
    # Casting temperatures ±5 °C
    str(DYN.hasMoltenMetalTemperature): 5.0,
    str(DYN.hasMoldTemperature): 5.0,
    # Cast cooling duration ±2 min
    str(DYN.hasCastCoolingDuration): 2.0,
    # Volume fractions ±0.01
    str(DYN.hasMatrixVolumeFraction): 0.01,
    str(DYN.hasReinforcementVolumeFraction): 0.01,
    # Test properties
    str(DYN.hasStrikerVelocity): 0.01,
    str(DYN.hasStrikerLaunchPressure): 0.1,
    str(DYN.hasBarrelOffset): 0.1,
    str(DYN.hasMomentumTrapTailoredDistance): 0.1,
    # PulseStressAmplitude: COMPUTED separately
    # Lattice/AM properties: NO uncertainty
}

STRING_TO_INDIVIDUAL = {
    str(DYN.hasDetectionPolarity): {
        "compressive": DYN.CompressivePolarity,
        "tensile": DYN.TensilePolarity,
    },
    str(DYN.hasSelectionMetric): {
        "median": DYN.MedianMetric,
        "peak": DYN.PeakMetric,
    },
}

WINDOWED_TYPE_MAP = {
    str(DYN.IncidentPulse): DYN.WindowedIncidentPulse,
    str(DYN.TransmittedPulse): DYN.WindowedTransmittedPulse,
    str(DYN.ReflectedPulse): DYN.WindowedReflectedPulse,
    str(DYN.Time): DYN.WindowedTime,
}

WINDOWED_COLUMN_META = {
    "time_windowed": (0, "time_windowed"),
    "incident_windowed": (1, "incident_windowed"),
    "transmitted_windowed": (2, "transmitted_windowed"),
    "reflected_windowed": (3, "reflected_windowed"),
}

SERIES_UNCERTAINTY_MAP = {
    str(DYN.Strain): "strain",
    str(DYN.TrueStrain): "strain",
    str(DYN.StrainRate): "strain",
    str(DYN.TrueStrainRate): "strain",
    str(DYN.Stress): "stress",
    str(DYN.TrueStress): "stress",
}

# Mapping old "qkdv:X"^^xsd:string values to proper QKDV URIRefs
QKDV_STRING_MAP = {
    "qkdv:Length": QKDV.Length,
    "qkdv:Dimensionless": QKDV.Dimensionless,
    "qkdv:Force": QKDV.Force,
    "qkdv:Voltage": QKDV.Voltage,
    "qkdv:Time": QKDV.Time,
    "qkdv:StrainRate": QKDV.StrainRate,
    "qkdv:Stress": QKDV.ForcePerArea,  # old non-standard → proper QUDT
    "qkdv:ForcePerArea": QKDV.ForcePerArea,
    "qkdv:Velocity": QKDV.Velocity,
    "qkdv:Area": QKDV.Area,
    "qkdv:Mass": QKDV.Mass,
}

# Cross-section ↔ diameter mapping for uncertainty computation
CROSS_SECTION_DIAMETER_MAP = {
    str(DYN.hasOriginalCrossSection): str(DYN.hasOriginalDiameter),
    str(DYN.hasFinalCrossSection): str(DYN.hasFinalDiameter),
}


# ═══════════════════════════ Helpers ═══════════════════════════

def discover_measurement_properties(ontology_dir: Path) -> dict:
    """Load the ontology and find properties with range qudt:QuantityValue.

    Returns dict mapping property URI (str) to {'unit': str, 'quantity_kind': str}.
    """
    g = Graph()
    props_dir = ontology_dir / "class_properties"
    if not props_dir.exists():
        logger.error(f"class_properties directory not found at {props_dir}")
        sys.exit(1)

    for ttl_file in sorted(props_dir.glob("*.ttl")):
        g.parse(str(ttl_file), format="turtle")
        logger.debug(f"Loaded {ttl_file.name}")

    measurement_props = {}
    for prop in g.subjects(RDFS.range, QUDT.QuantityValue):
        prop_uri = str(prop)
        unit = None
        for u in g.objects(prop, DYN.hasUnit):
            unit = str(u).strip('"').strip("'")
            break
        qk = None
        for q in g.objects(prop, QUDT.hasQuantityKind):
            qk = str(q)
            break
        measurement_props[prop_uri] = {"unit": unit, "quantity_kind": qk}

    logger.info(f"Discovered {len(measurement_props)} measurement properties")
    return measurement_props


def resolve_unit_uri(unit_str: str) -> URIRef | None:
    """Convert a unit string (prefixed or full) to a URIRef."""
    if not unit_str:
        return None
    unit_str = unit_str.strip().strip('"').strip("'")
    if unit_str.startswith("http"):
        return URIRef(unit_str)
    if unit_str.startswith("unit:"):
        return URIRef(UNIT[unit_str.replace("unit:", "")])
    return URIRef(UNIT[unit_str])


def resolve_qk_uri(qk_str: str) -> URIRef | None:
    """Convert a quantity kind string (prefixed or full) to a URIRef."""
    if not qk_str:
        return None
    if qk_str.startswith("http"):
        return URIRef(qk_str)
    if qk_str.startswith("qkdv:"):
        return URIRef(QKDV[qk_str.replace("qkdv:", "")])
    return URIRef(QKDV[qk_str])


def get_qv_numeric(g: Graph, subject: URIRef, predicate: URIRef) -> float | None:
    """Extract numeric value from a QuantityValue BNode."""
    for obj in g.objects(subject, predicate):
        if isinstance(obj, BNode):
            for val in g.objects(obj, QUDT.numericValue):
                try:
                    return float(val.toPython())
                except (TypeError, ValueError):
                    pass
    return None


def get_any_numeric(g: Graph, subject: URIRef, predicate: URIRef) -> float | None:
    """Extract numeric value — works for both QV BNodes and flat literals."""
    for obj in g.objects(subject, predicate):
        if isinstance(obj, BNode):
            for val in g.objects(obj, QUDT.numericValue):
                try:
                    return float(val.toPython())
                except (TypeError, ValueError):
                    pass
        elif isinstance(obj, Literal):
            try:
                return float(obj.toPython())
            except (TypeError, ValueError):
                pass
    return None


def find_test_node(g: Graph) -> URIRef | None:
    """Find the SHPBCompression test node in the graph."""
    for s in g.subjects(RDF.type, DYN.SHPBCompression):
        return s
    return None


def find_specimen_node(g: Graph) -> URIRef | None:
    """Find the Specimen node in the graph."""
    for s in g.subjects(RDF.type, DYN.Specimen):
        return s
    return None


def local_name(uri: URIRef | str) -> str:
    """Extract local name after # or /."""
    s = str(uri)
    if "#" in s:
        return s.split("#")[-1]
    return s.rsplit("/", 1)[-1]


def bind_prefixes(g: Graph) -> None:
    """Bind common prefixes for clean serialization."""
    g.bind("dyn", DYN)
    g.bind("qudt", QUDT)
    g.bind("unit", UNIT)
    g.bind("qkdv", QKDV)
    g.bind("xsd", XSD)
    g.bind("rdf", RDF)
    g.bind("rdfs", RDFS)
    g.bind("owl", OWL)


def compute_cross_section_uncertainty(diameter: float, dim_unc: float = 0.01) -> float:
    """Compute cross-section uncertainty: ΔA = (π·d/2)·Δd."""
    return math.pi * diameter / 2.0 * dim_unc


def compute_pulse_stress_uncertainty(
    amplitude: float, velocity: float, velocity_unc: float = 0.01
) -> float:
    """Compute pulse stress amplitude uncertainty: σ·(Δv/v)."""
    if velocity == 0:
        return 0.0
    return amplitude * (velocity_unc / velocity)


# ═══════════════════════════ Transformations ═══════════════════════════

# ─── (1) Flat double → QuantityValue BNode ───

def migrate_to_quantity_value(g: Graph, measurement_props: dict) -> int:
    """Replace flat xsd:double literals with qudt:QuantityValue BNodes."""
    count = 0
    for prop_uri_str, meta in measurement_props.items():
        prop_ref = URIRef(prop_uri_str)
        for subj, _, obj in list(g.triples((None, prop_ref, None))):
            if not isinstance(obj, Literal):
                continue
            try:
                numeric_value = float(obj.toPython())
            except (TypeError, ValueError):
                continue

            bnode = BNode()
            g.remove((subj, prop_ref, obj))
            g.add((subj, prop_ref, bnode))
            g.add((bnode, RDF.type, QUDT.QuantityValue))
            g.add((bnode, QUDT.numericValue, Literal(numeric_value, datatype=XSD.double)))

            unit_ref = resolve_unit_uri(meta.get("unit"))
            if unit_ref:
                g.add((bnode, QUDT.unit, unit_ref))

            qk_ref = resolve_qk_uri(meta.get("quantity_kind"))
            if qk_ref:
                g.add((bnode, QUDT.hasQuantityKind, qk_ref))

            logger.debug(
                f"  QV: {local_name(prop_uri_str)}: {numeric_value} "
                f"(unit={meta.get('unit')}, qk={meta.get('quantity_kind')})"
            )
            count += 1
    return count


# ─── (2) Inject uncertainty into QV BNodes ───

def inject_uncertainty(g: Graph, uncertainty_map: dict) -> int:
    """Add qudt:standardUncertainty to QV BNodes for properties in uncertainty_map."""
    count = 0
    for prop_uri_str, unc_value in uncertainty_map.items():
        prop_ref = URIRef(prop_uri_str)
        for subj, _, obj in list(g.triples((None, prop_ref, None))):
            if not isinstance(obj, BNode):
                continue
            # Idempotency: skip if already has uncertainty
            if list(g.objects(obj, QUDT.standardUncertainty)):
                continue
            g.add((obj, QUDT.standardUncertainty,
                   Literal(unc_value, datatype=XSD.double)))
            logger.debug(f"  Uncertainty: {local_name(prop_uri_str)} ± {unc_value}")
            count += 1
    return count


def inject_cross_section_uncertainty(g: Graph) -> int:
    """Compute and inject uncertainty for cross-section QV BNodes."""
    count = 0
    for cs_prop_str, diam_prop_str in CROSS_SECTION_DIAMETER_MAP.items():
        cs_prop = URIRef(cs_prop_str)
        diam_prop = URIRef(diam_prop_str)
        for subj in set(g.subjects(cs_prop, None)):
            # Get the diameter value
            diameter = get_qv_numeric(g, subj, diam_prop)
            if diameter is None:
                continue
            # Get the cross-section BNode
            for cs_bnode in g.objects(subj, cs_prop):
                if not isinstance(cs_bnode, BNode):
                    continue
                if list(g.objects(cs_bnode, QUDT.standardUncertainty)):
                    continue
                unc = compute_cross_section_uncertainty(diameter)
                g.add((cs_bnode, QUDT.standardUncertainty,
                       Literal(round(unc, 6), datatype=XSD.double)))
                logger.debug(
                    f"  Cross-section unc: {local_name(cs_prop_str)} "
                    f"± {round(unc, 6)} (d={diameter})"
                )
                count += 1
    return count


def inject_pulse_stress_uncertainty(g: Graph) -> int:
    """Compute and inject uncertainty for PulseStressAmplitude QV BNodes."""
    count = 0
    test_node = find_test_node(g)
    if test_node is None:
        return 0

    amplitude = get_qv_numeric(g, test_node, DYN.hasPulseStressAmplitude)
    velocity = get_qv_numeric(g, test_node, DYN.hasStrikerVelocity)
    if amplitude is None or velocity is None:
        return 0

    for bnode in g.objects(test_node, DYN.hasPulseStressAmplitude):
        if not isinstance(bnode, BNode):
            continue
        if list(g.objects(bnode, QUDT.standardUncertainty)):
            continue
        unc = compute_pulse_stress_uncertainty(amplitude, velocity)
        g.add((bnode, QUDT.standardUncertainty,
               Literal(round(unc, 6), datatype=XSD.double)))
        logger.debug(f"  PulseStress unc: ± {round(unc, 6)} (σ={amplitude}, v={velocity})")
        count += 1
    return count


# ─── (3) Fix broken ns1:type → rdf:type ───

def fix_ns1_type(g: Graph) -> int:
    """Replace broken URIRef('rdf:type') predicates with proper RDF.type."""
    count = 0
    for subj, _, obj in list(g.triples((None, NS1_TYPE, None))):
        g.remove((subj, NS1_TYPE, obj))
        g.add((subj, RDF.type, obj))
        logger.debug(f"  Fixed ns1:type on {local_name(subj)}")
        count += 1
    return count


# ─── (4-5) String literals → Individual URIRefs ───

def string_to_individuals(g: Graph) -> int:
    """Replace string literals with individual URIRefs for polarity and metric."""
    count = 0
    for prop_uri_str, mapping in STRING_TO_INDIVIDUAL.items():
        prop_ref = URIRef(prop_uri_str)
        for subj, _, obj in list(g.triples((None, prop_ref, None))):
            if not isinstance(obj, Literal):
                continue
            val = str(obj).strip().lower()
            if val in mapping:
                g.remove((subj, prop_ref, obj))
                g.add((subj, prop_ref, mapping[val]))
                logger.debug(
                    f"  Individual: {local_name(prop_uri_str)}: "
                    f'"{val}" → {local_name(mapping[val])}'
                )
                count += 1
    return count


# ─── (6) Fix quantity kind string literals → URIRefs ───

def fix_quantity_kind_urirefs(g: Graph) -> int:
    """Replace 'qkdv:X'^^xsd:string with proper qkdv:X URIRefs on dyn:hasQuantityKind."""
    count = 0
    prop_ref = DYN.hasQuantityKind
    for subj, _, obj in list(g.triples((None, prop_ref, None))):
        if not isinstance(obj, Literal):
            continue
        val = str(obj).strip()
        if val in QKDV_STRING_MAP:
            g.remove((subj, prop_ref, obj))
            g.add((subj, prop_ref, QKDV_STRING_MAP[val]))
            logger.debug(f"  QK URIRef: {local_name(subj)}: \"{val}\" → {val}")
            count += 1
        elif val.startswith("qkdv:"):
            # Handle any unmapped prefixed values
            local = val.replace("qkdv:", "")
            g.remove((subj, prop_ref, obj))
            g.add((subj, prop_ref, QKDV[local]))
            logger.debug(f"  QK URIRef (generic): {local_name(subj)}: \"{val}\" → qkdv:{local}")
            count += 1
    return count


# ─── (7) Split hasStrainGauge → hasIncident/TransmissionStrainGauge ───

def split_strain_gauges(g: Graph) -> int:
    """Split hasStrainGauge into hasIncidentStrainGauge + hasTransmissionStrainGauge."""
    count = 0
    test_node = find_test_node(g)
    if test_node is None:
        return 0

    # Idempotency: skip if already split
    if list(g.objects(test_node, DYN.hasIncidentStrainGauge)):
        return 0

    gauges = sorted(g.objects(test_node, DYN.hasStrainGauge), key=str)
    if len(gauges) < 2:
        return 0

    # Convention: _001 = incident, _002 = transmission
    incident_gauge = None
    transmission_gauge = None
    for gauge in gauges:
        name = local_name(gauge)
        if "001" in name:
            incident_gauge = gauge
        elif "002" in name:
            transmission_gauge = gauge

    if incident_gauge is None or transmission_gauge is None:
        # Fallback: first = incident, second = transmission
        gauge_list = list(gauges)
        incident_gauge = gauge_list[0]
        transmission_gauge = gauge_list[1]

    # Remove old hasStrainGauge triples
    for gauge in list(g.objects(test_node, DYN.hasStrainGauge)):
        g.remove((test_node, DYN.hasStrainGauge, gauge))

    # Add new split properties
    g.add((test_node, DYN.hasIncidentStrainGauge, incident_gauge))
    g.add((test_node, DYN.hasTransmissionStrainGauge, transmission_gauge))
    logger.debug(
        f"  Split gauges: incident={local_name(incident_gauge)}, "
        f"transmission={local_name(transmission_gauge)}"
    )
    count = 1
    return count


# ─── (8) Rename hasTukeyAlpha → hasTukeyAlphaParam ───

def rename_tukey_alpha(g: Graph) -> int:
    """Rename hasTukeyAlpha → hasTukeyAlphaParam on the test node."""
    count = 0
    test_node = find_test_node(g)
    if test_node is None:
        return 0

    for subj, _, obj in list(g.triples((test_node, DYN.hasTukeyAlpha, None))):
        # Idempotency: skip if new property already exists
        if list(g.objects(test_node, DYN.hasTukeyAlphaParam)):
            continue
        g.remove((subj, DYN.hasTukeyAlpha, obj))
        g.add((subj, DYN.hasTukeyAlphaParam, obj))
        logger.debug(f"  Renamed hasTukeyAlpha → hasTukeyAlphaParam: {obj}")
        count += 1
    return count


# ─── (9) Convert hasSamplingInterval (ms) → hasSamplingRate (Hz) ───

def convert_sampling_interval(g: Graph) -> int:
    """Convert hasSamplingInterval to hasSamplingRate on raw DataSeries."""
    count = 0
    for subj, _, obj in list(g.triples((None, DYN.hasSamplingInterval, None))):
        if not isinstance(obj, Literal):
            continue
        # Idempotency: skip if hasSamplingRate already exists
        if list(g.objects(subj, DYN.hasSamplingRate)):
            continue
        try:
            interval_ms = float(obj.toPython())
        except (TypeError, ValueError):
            continue
        if interval_ms <= 0:
            continue

        rate_hz = round(1000.0 / interval_ms, 2)
        g.remove((subj, DYN.hasSamplingInterval, obj))
        g.add((subj, DYN.hasSamplingRate, Literal(rate_hz, datatype=XSD.double)))
        logger.debug(
            f"  SamplingRate: {local_name(subj)}: "
            f"{interval_ms} ms → {rate_hz} Hz"
        )
        count += 1
    return count


# ─── (10) Rename hasThresholdRatio → hasFrontThreshold ───

def rename_threshold_ratio(g: Graph) -> int:
    """Rename hasThresholdRatio → hasFrontThreshold on AlignmentParams."""
    count = 0
    for subj, _, obj in list(g.triples((None, DYN.hasThresholdRatio, None))):
        # Idempotency
        if list(g.objects(subj, DYN.hasFrontThreshold)):
            continue
        g.remove((subj, DYN.hasThresholdRatio, obj))
        g.add((subj, DYN.hasFrontThreshold, obj))
        logger.debug(f"  Renamed hasThresholdRatio → hasFrontThreshold: {obj}")
        count += 1
    return count


# ─── (11) Fix windowed series types ───

def fix_windowed_series_types(g: Graph) -> int:
    """Change series type on windowed series (IncidentPulse → WindowedIncidentPulse etc.)."""
    count = 0
    for subj, _, obj in list(g.triples((None, DYN.hasSeriesType, None))):
        if not isinstance(obj, URIRef):
            continue
        obj_str = str(obj)
        if obj_str not in WINDOWED_TYPE_MAP:
            continue

        # Only apply to windowed series (identified by URI suffix)
        subj_name = local_name(subj)
        if "_windowed" not in subj_name:
            continue

        new_type = WINDOWED_TYPE_MAP[obj_str]
        g.remove((subj, DYN.hasSeriesType, obj))
        g.add((subj, DYN.hasSeriesType, new_type))
        logger.debug(
            f"  Windowed type: {subj_name}: "
            f"{local_name(obj)} → {local_name(new_type)}"
        )
        count += 1
    return count


# ─── (12) Move detection params from series to test node ───

def move_detection_params_to_test(g: Graph) -> int:
    """Move hasPulseDetectionParams from series nodes to the test node."""
    count = 0
    test_node = find_test_node(g)
    if test_node is None:
        return 0

    # Idempotency: skip if test node already has detection params
    if list(g.objects(test_node, DYN.hasPulseDetectionParams)):
        return 0

    # Collect all detection params from series
    all_detect_params = set()
    series_with_detect = []
    for subj, _, obj in list(g.triples((None, DYN.hasPulseDetectionParams, None))):
        if subj == test_node:
            continue
        all_detect_params.add(obj)
        series_with_detect.append((subj, obj))

    if not all_detect_params:
        return 0

    # Remove from series
    for subj, obj in series_with_detect:
        g.remove((subj, DYN.hasPulseDetectionParams, obj))

    # Add to test node
    for detect_param in sorted(all_detect_params, key=str):
        g.add((test_node, DYN.hasPulseDetectionParams, detect_param))
        count += 1

    logger.debug(f"  Moved {count} detection params to test node")
    return count


# ─── (13) Add hasAnalysisFile links on test node ───

def add_analysis_file_links(g: Graph) -> int:
    """Add hasAnalysisFile on the test node for all referenced AnalysisFiles."""
    count = 0
    test_node = find_test_node(g)
    if test_node is None:
        return 0

    # Idempotency: skip if already has analysis file links
    if list(g.objects(test_node, DYN.hasAnalysisFile)):
        return 0

    # Collect all AnalysisFile URIs referenced via hasDataFile from series
    analysis_files = set()
    for series in g.objects(test_node, DYN.hasDataSeries):
        for af in g.objects(series, DYN.hasDataFile):
            analysis_files.add(af)

    for af in sorted(analysis_files, key=str):
        g.add((test_node, DYN.hasAnalysisFile, af))
        logger.debug(f"  AnalysisFile link: {local_name(af)}")
        count += 1
    return count


# ─── (14) Create SegmentationParams instance ───

def create_segmentation_params(g: Graph) -> int:
    """Create SegmentationParams from alignment data."""
    count = 0
    test_node = find_test_node(g)
    if test_node is None:
        return 0

    # Idempotency: skip if already has segmentation params
    if list(g.objects(test_node, DYN.hasSegmentationParams)):
        return 0

    # Find alignment params
    alignment_node = None
    for node in g.objects(test_node, DYN.hasAlignmentParams):
        alignment_node = node
        break
    if alignment_node is None:
        return 0

    # Read centered segment points from alignment
    segment_points = None
    for val in g.objects(alignment_node, DYN.hasCenteredSegmentPoints):
        try:
            segment_points = int(val.toPython())
        except (TypeError, ValueError):
            pass
        break

    if segment_points is None:
        return 0

    # Build segmentation params URI: {testId}_segmentation
    test_id = local_name(test_node)
    seg_uri = DYN[f"{test_id}_segmentation"]

    g.add((seg_uri, RDF.type, DYN.SegmentationParams))
    g.add((seg_uri, DYN.hasSegmentPoints,
           Literal(segment_points, datatype=XSD.integer)))
    g.add((seg_uri, DYN.hasSegmentThreshold,
           Literal(0.01, datatype=XSD.double)))
    g.add((test_node, DYN.hasSegmentationParams, seg_uri))

    logger.debug(
        f"  SegmentationParams: {local_name(seg_uri)} "
        f"(points={segment_points}, threshold=0.01)"
    )
    count = 1
    return count


# ─── (15) Add column metadata on windowed series ───

def add_windowed_column_metadata(g: Graph) -> int:
    """Add hasColumnIndex and hasColumnName to windowed series."""
    count = 0
    # Iterate over all ProcessedData subjects
    for series_node in set(g.subjects(RDF.type, DYN.ProcessedData)):
        name = local_name(series_node)
        for suffix, (col_idx, col_name) in WINDOWED_COLUMN_META.items():
            if not name.endswith(suffix):
                continue
            # Idempotency: skip if already has column index
            if list(g.objects(series_node, DYN.hasColumnIndex)):
                break
            g.add((series_node, DYN.hasColumnIndex,
                   Literal(col_idx, datatype=XSD.integer)))
            if not list(g.objects(series_node, DYN.hasColumnName)):
                g.add((series_node, DYN.hasColumnName,
                       Literal(col_name, datatype=XSD.string)))
            logger.debug(
                f"  Windowed meta: {name}: index={col_idx}, name={col_name}"
            )
            count += 1
            break
    return count


# ─── (16) Add hasFileName from hasFilePath on AnalysisFile nodes ───

def add_filename_to_analysis_files(g: Graph) -> int:
    """Extract filename from hasFilePath and add as hasFileName."""
    count = 0
    for subj in set(g.subjects(RDF.type, DYN.AnalysisFile)):
        # Idempotency
        if list(g.objects(subj, DYN.hasFileName)):
            continue
        for obj in g.objects(subj, DYN.hasFilePath):
            if not isinstance(obj, Literal):
                continue
            filepath = str(obj)
            # Handle both forward and backslash separators
            filename = filepath.replace("\\", "/").rsplit("/", 1)[-1]
            g.add((subj, DYN.hasFileName,
                   Literal(filename, datatype=XSD.string)))
            logger.debug(f"  FileName: {local_name(subj)}: {filename}")
            count += 1
            break
    return count


# ─── (17) Fix hasAnalysisTimestamp xsd:date → xsd:dateTime ───

def fix_analysis_timestamp_type(g: Graph) -> int:
    """Convert hasAnalysisTimestamp from xsd:date to xsd:dateTime."""
    count = 0
    for subj, _, obj in list(g.triples((None, DYN.hasAnalysisTimestamp, None))):
        if not isinstance(obj, Literal):
            continue
        if obj.datatype == XSD.dateTime:
            continue  # already correct
        if obj.datatype == XSD.date:
            date_str = str(obj)
            datetime_str = f"{date_str}T00:00:00"
            g.remove((subj, DYN.hasAnalysisTimestamp, obj))
            g.add((subj, DYN.hasAnalysisTimestamp,
                   Literal(datetime_str, datatype=XSD.dateTime)))
            logger.debug(f"  Timestamp: {date_str} → {datetime_str}")
            count += 1
    return count


# ─── (18) Add relativeStandardUncertainty on processed series ───

def add_series_uncertainty(g: Graph, specimen_cache: dict) -> int:
    """Add qudt:relativeStandardUncertainty on stress/strain series."""
    count = 0
    test_node = find_test_node(g)
    if test_node is None:
        return 0

    # Find specimen via performedOn
    specimen_uri = None
    for obj in g.objects(test_node, DYN.performedOn):
        specimen_uri = str(obj)
        break
    if specimen_uri is None or specimen_uri not in specimen_cache:
        return 0

    dims = specimen_cache[specimen_uri]
    diameter = dims.get("diameter")
    height = dims.get("height")
    if diameter is None or height is None:
        return 0

    dim_unc = 0.01  # mm
    strain_rel_unc = dim_unc / height
    stress_rel_unc = 2.0 * dim_unc / diameter

    unc_values = {
        "strain": round(strain_rel_unc, 7),
        "stress": round(stress_rel_unc, 7),
    }

    # Find all data series in this test
    for series_node in g.objects(test_node, DYN.hasDataSeries):
        # Idempotency
        if list(g.objects(series_node, QUDT.relativeStandardUncertainty)):
            continue

        # Check series type
        for st in g.objects(series_node, DYN.hasSeriesType):
            st_str = str(st)
            if st_str in SERIES_UNCERTAINTY_MAP:
                bucket = SERIES_UNCERTAINTY_MAP[st_str]
                unc = unc_values[bucket]
                g.add((series_node, QUDT.relativeStandardUncertainty,
                       Literal(unc, datatype=XSD.double)))
                logger.debug(
                    f"  Series unc: {local_name(series_node)}: "
                    f"{bucket}={unc}"
                )
                count += 1
            break

    return count


# ═══════════════════════════ Orchestrators ═══════════════════════════

def migrate_specimen_file(
    g: Graph,
    measurement_props: dict,
    specimen_cache: dict,
) -> int:
    """Apply all specimen-file transformations. Returns total change count."""
    total = 0

    # (1) Flat doubles → QV BNodes
    n = migrate_to_quantity_value(g, measurement_props)
    if n:
        logger.info(f"    [1] QV migration: {n} properties")
    total += n

    # (2) Inject uncertainty on QV BNodes
    # Filter UNCERTAINTY_CONFIG to specimen-relevant properties only
    specimen_unc = {k: v for k, v in UNCERTAINTY_CONFIG.items()
                    if "Striker" not in k and "Barrel" not in k
                    and "MomentumTrap" not in k}
    n = inject_uncertainty(g, specimen_unc)
    if n:
        logger.info(f"    [2] Uncertainty: {n} BNodes")
    total += n

    # (2b) Cross-section uncertainty (computed)
    n = inject_cross_section_uncertainty(g)
    if n:
        logger.info(f"    [2b] Cross-section unc: {n}")
    total += n

    # Cache specimen dimensions for Phase 2
    specimen_node = find_specimen_node(g)
    if specimen_node:
        diameter = get_qv_numeric(g, specimen_node, DYN.hasOriginalDiameter)
        height = get_qv_numeric(g, specimen_node, DYN.hasOriginalHeight)
        # Fallback: try flat values (if QV migration didn't happen for these)
        if diameter is None:
            diameter = get_any_numeric(g, specimen_node, DYN.hasOriginalDiameter)
        if height is None:
            height = get_any_numeric(g, specimen_node, DYN.hasOriginalHeight)

        if diameter is not None and height is not None:
            specimen_cache[str(specimen_node)] = {
                "diameter": diameter,
                "height": height,
            }
            logger.debug(
                f"    Cached: d={diameter}, h={height} for {local_name(specimen_node)}"
            )

    return total


def migrate_test_file(
    g: Graph,
    measurement_props: dict,
    specimen_cache: dict,
) -> int:
    """Apply all test-file transformations. Returns total change count."""
    total = 0

    # (3) Fix ns1:type FIRST — must precede other transforms
    n = fix_ns1_type(g)
    if n:
        logger.info(f"    [3] ns1:type fix: {n} triples")
    total += n

    # (9) Convert hasSamplingInterval → hasSamplingRate BEFORE QV migration
    #     (otherwise QV migration wraps the interval in a BNode)
    n = convert_sampling_interval(g)
    if n:
        logger.info(f"    [9] Sampling conversion: {n}")
    total += n

    # (1) Flat doubles → QV BNodes
    n = migrate_to_quantity_value(g, measurement_props)
    if n:
        logger.info(f"    [1] QV migration: {n} properties")
    total += n

    # (2) Inject uncertainty
    test_unc = {k: v for k, v in UNCERTAINTY_CONFIG.items()
                if "Striker" in k or "Barrel" in k
                or "MomentumTrap" in k}
    n = inject_uncertainty(g, test_unc)
    if n:
        logger.info(f"    [2] Uncertainty: {n} BNodes")
    total += n

    # (2b) Pulse stress amplitude uncertainty (computed)
    n = inject_pulse_stress_uncertainty(g)
    if n:
        logger.info(f"    [2b] PulseStress unc: {n}")
    total += n

    # (4-5) String → Individual URIs
    n = string_to_individuals(g)
    if n:
        logger.info(f"    [4-5] String→Individual: {n}")
    total += n

    # (6) Fix quantity kind string → URIRef
    n = fix_quantity_kind_urirefs(g)
    if n:
        logger.info(f"    [6] QK URIRef: {n}")
    total += n

    # (7) Split strain gauges
    n = split_strain_gauges(g)
    if n:
        logger.info(f"    [7] Split strain gauges: {n}")
    total += n

    # (8) Rename hasTukeyAlpha → hasTukeyAlphaParam
    n = rename_tukey_alpha(g)
    if n:
        logger.info(f"    [8] Tukey rename: {n}")
    total += n

    # (10) Rename hasThresholdRatio → hasFrontThreshold
    n = rename_threshold_ratio(g)
    if n:
        logger.info(f"    [10] Threshold rename: {n}")
    total += n

    # (11) Fix windowed series types
    n = fix_windowed_series_types(g)
    if n:
        logger.info(f"    [11] Windowed types: {n}")
    total += n

    # (12) Move detection params to test node
    n = move_detection_params_to_test(g)
    if n:
        logger.info(f"    [12] Detection params moved: {n}")
    total += n

    # (13) Add analysis file links
    n = add_analysis_file_links(g)
    if n:
        logger.info(f"    [13] Analysis file links: {n}")
    total += n

    # (14) Create segmentation params
    n = create_segmentation_params(g)
    if n:
        logger.info(f"    [14] SegmentationParams: {n}")
    total += n

    # (15) Windowed column metadata
    n = add_windowed_column_metadata(g)
    if n:
        logger.info(f"    [15] Windowed columns: {n}")
    total += n

    # (16) Add hasFileName
    n = add_filename_to_analysis_files(g)
    if n:
        logger.info(f"    [16] FileName: {n}")
    total += n

    # (17) Fix analysis timestamp type
    n = fix_analysis_timestamp_type(g)
    if n:
        logger.info(f"    [17] Timestamp fix: {n}")
    total += n

    # (18) Series uncertainty
    n = add_series_uncertainty(g, specimen_cache)
    if n:
        logger.info(f"    [18] Series uncertainty: {n}")
    total += n

    return total


# ═══════════════════════════ File I/O ═══════════════════════════

def process_file(
    ttl_path: Path,
    measurement_props: dict,
    specimen_cache: dict,
    file_type: str,
    apply: bool,
    backup: bool,
) -> int:
    """Parse, migrate, and optionally save a single TTL file.

    file_type: 'specimen' or 'test'
    Returns total change count.
    """
    g = Graph()
    try:
        g.parse(str(ttl_path), format="turtle")
    except Exception as e:
        logger.warning(f"  Skipping {ttl_path.name}: parse error: {e}")
        return 0

    if file_type == "specimen":
        total = migrate_specimen_file(g, measurement_props, specimen_cache)
    else:
        total = migrate_test_file(g, measurement_props, specimen_cache)

    if total > 0 and apply:
        if backup:
            bak_path = ttl_path.with_suffix(".ttl.bak")
            shutil.copy2(ttl_path, bak_path)
            logger.debug(f"  Backup: {bak_path}")

        bind_prefixes(g)
        g.serialize(destination=str(ttl_path), format="turtle")
        logger.info(f"    Saved: {ttl_path.name}")

    return total


# ═══════════════════════════ Main ═══════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="Extended TTL migration tool for DynaMat Platform."
    )
    parser.add_argument(
        "--apply", action="store_true",
        help="Apply changes in-place (default is dry-run).",
    )
    parser.add_argument(
        "--backup", action="store_true",
        help="Keep .bak copies of modified files (only with --apply).",
    )
    parser.add_argument(
        "--dir", type=str, default=None,
        help="Specific directory to migrate (default: user_data/).",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true",
        help="Enable debug logging.",
    )
    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Locate project root
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    ontology_dir = project_root / "src" / "dynamat" / "ontology"

    # Discover measurement properties from ontology
    measurement_props = discover_measurement_properties(ontology_dir)
    if not measurement_props:
        logger.error("No measurement properties found. Check ontology files.")
        sys.exit(1)

    # Determine target directory
    if args.dir:
        target_dir = Path(args.dir)
        if not target_dir.is_absolute():
            target_dir = project_root / target_dir
    else:
        target_dir = project_root / "user_data"

    if not target_dir.exists():
        logger.error(f"Target directory not found: {target_dir}")
        sys.exit(1)

    # Classify TTL files
    all_ttl = sorted(target_dir.rglob("*.ttl"))
    specimen_files = [f for f in all_ttl if f.name.endswith("_specimen.ttl")]
    test_files = [f for f in all_ttl if "SHPBTest" in f.name]
    other_files = [f for f in all_ttl
                   if f not in specimen_files and f not in test_files]

    logger.info(f"Found {len(all_ttl)} TTL files in {target_dir}")
    logger.info(f"  Specimen files: {len(specimen_files)}")
    logger.info(f"  Test files:     {len(test_files)}")
    logger.info(f"  Other files:    {len(other_files)}")

    if not args.apply:
        logger.info("DRY RUN — no files will be modified. Use --apply to write.")

    specimen_cache: dict[str, dict[str, float]] = {}

    # ── Phase 1: Specimen files ──
    logger.info(f"\n{'='*60}")
    logger.info("Phase 1: Specimen files")
    logger.info(f"{'='*60}")

    phase1_total = 0
    phase1_changed = 0

    for ttl_path in specimen_files:
        rel = ttl_path.relative_to(project_root)
        logger.info(f"\n  {rel}:")
        n = process_file(
            ttl_path, measurement_props, specimen_cache,
            "specimen", args.apply, args.backup,
        )
        phase1_total += n
        if n > 0:
            phase1_changed += 1

    logger.info(f"\nPhase 1 complete: {phase1_changed}/{len(specimen_files)} files, "
                f"{phase1_total} changes")
    logger.info(f"Specimen cache: {len(specimen_cache)} specimens cached")

    # ── Phase 2: Test files ──
    logger.info(f"\n{'='*60}")
    logger.info("Phase 2: Test files")
    logger.info(f"{'='*60}")

    phase2_total = 0
    phase2_changed = 0

    for ttl_path in test_files:
        rel = ttl_path.relative_to(project_root)
        logger.info(f"\n  {rel}:")
        n = process_file(
            ttl_path, measurement_props, specimen_cache,
            "test", args.apply, args.backup,
        )
        phase2_total += n
        if n > 0:
            phase2_changed += 1

    logger.info(f"\nPhase 2 complete: {phase2_changed}/{len(test_files)} files, "
                f"{phase2_total} changes")

    # ── Summary ──
    mode = "APPLIED" if args.apply else "DRY RUN"
    total_changes = phase1_total + phase2_total
    total_changed = phase1_changed + phase2_changed

    logger.info(f"\n{'='*60}")
    logger.info(f"Migration complete ({mode})")
    logger.info(f"{'='*60}")
    logger.info(f"  Files scanned:      {len(all_ttl)}")
    logger.info(f"  Specimen files:     {phase1_changed}/{len(specimen_files)} changed")
    logger.info(f"  Test files:         {phase2_changed}/{len(test_files)} changed")
    logger.info(f"  Total files changed:{total_changed}")
    logger.info(f"  Total changes:      {total_changes}")
    logger.info(f"  Specimens cached:   {len(specimen_cache)}")
    if not args.apply and total_changes > 0:
        logger.info("  Run with --apply to write changes.")


if __name__ == "__main__":
    main()
