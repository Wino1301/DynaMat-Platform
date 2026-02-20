"""Migrate existing user_data/ TTL files from flat xsd:double literals to qudt:QuantityValue.

Usage:
    python tools/migrate_to_quantity_value.py                      # dry-run (default)
    python tools/migrate_to_quantity_value.py --apply               # apply changes in-place
    python tools/migrate_to_quantity_value.py --apply --backup      # apply + keep .bak copies
    python tools/migrate_to_quantity_value.py --dir user_data/specimens/DYNML-A356-0001

The script:
1. Loads the DynaMat ontology to discover measurement properties
   (owl:ObjectProperty with rdfs:range qudt:QuantityValue).
2. For each matching property, reads its dyn:hasUnit and qudt:hasQuantityKind annotations.
3. Scans TTL files in user_data/ for flat xsd:double triples on those properties.
4. Replaces each flat triple with a qudt:QuantityValue blank node containing
   qudt:numericValue, qudt:unit, and qudt:hasQuantityKind.
"""

import argparse
import logging
import shutil
import sys
from pathlib import Path

from rdflib import Graph, Namespace, URIRef, Literal, BNode
from rdflib.namespace import RDF, RDFS, OWL, XSD

# Standard namespaces
DYN = Namespace("https://dynamat.utep.edu/ontology#")
QUDT = Namespace("http://qudt.org/schema/qudt/")
UNIT = Namespace("http://qudt.org/vocab/unit/")
QKDV = Namespace("http://qudt.org/vocab/quantitykind/")

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def discover_measurement_properties(ontology_dir: Path) -> dict:
    """Load the ontology and find properties with range qudt:QuantityValue.

    Returns:
        Dict mapping property URI (str) to {'unit': str, 'quantity_kind': str}.
    """
    g = Graph()

    # Load all class_properties TTL files
    props_dir = ontology_dir / "class_properties"
    if not props_dir.exists():
        logger.error(f"class_properties directory not found at {props_dir}")
        sys.exit(1)

    for ttl_file in sorted(props_dir.glob("*.ttl")):
        g.parse(str(ttl_file), format="turtle")
        logger.debug(f"Loaded {ttl_file.name}")

    # Find all properties with range qudt:QuantityValue
    measurement_props = {}
    for prop in g.subjects(RDFS.range, QUDT.QuantityValue):
        prop_uri = str(prop)

        # Get default unit
        unit = None
        for u in g.objects(prop, DYN.hasUnit):
            unit = str(u).strip('"').strip("'")
            break

        # Get quantity kind
        qk = None
        for q in g.objects(prop, QUDT.hasQuantityKind):
            qk = str(q)
            break

        measurement_props[prop_uri] = {
            'unit': unit,
            'quantity_kind': qk,
        }

    logger.info(f"Discovered {len(measurement_props)} measurement properties")
    return measurement_props


def resolve_unit_uri(unit_str: str) -> URIRef:
    """Convert a unit string (prefixed or full) to a URIRef."""
    if not unit_str:
        return None
    unit_str = unit_str.strip().strip('"').strip("'")
    if unit_str.startswith("http"):
        return URIRef(unit_str)
    if unit_str.startswith("unit:"):
        return URIRef(UNIT[unit_str.replace("unit:", "")])
    return URIRef(UNIT[unit_str])


def resolve_qk_uri(qk_str: str) -> URIRef:
    """Convert a quantity kind string (prefixed or full) to a URIRef."""
    if not qk_str:
        return None
    if qk_str.startswith("http"):
        return URIRef(qk_str)
    if qk_str.startswith("qkdv:"):
        return URIRef(QKDV[qk_str.replace("qkdv:", "")])
    return URIRef(QKDV[qk_str])


def migrate_file(
    ttl_path: Path,
    measurement_props: dict,
    apply: bool = False,
    backup: bool = False,
) -> int:
    """Migrate a single TTL file from flat literals to QuantityValue blank nodes.

    Returns:
        Number of properties migrated.
    """
    g = Graph()
    try:
        g.parse(str(ttl_path), format="turtle")
    except Exception as e:
        logger.warning(f"  Skipping {ttl_path}: parse error: {e}")
        return 0

    migrated = 0

    for prop_uri_str, meta in measurement_props.items():
        prop_ref = URIRef(prop_uri_str)

        # Find flat literal triples for this property
        for subj, _, obj in list(g.triples((None, prop_ref, None))):
            # Only migrate flat literals (xsd:double or plain numeric)
            if not isinstance(obj, Literal):
                continue
            # Skip if already a BNode (already migrated)
            if isinstance(obj, BNode):
                continue

            try:
                numeric_value = float(obj.toPython())
            except (TypeError, ValueError):
                continue

            # Build QuantityValue blank node
            bnode = BNode()
            g.remove((subj, prop_ref, obj))
            g.add((subj, prop_ref, bnode))
            g.add((bnode, RDF.type, QUDT.QuantityValue))
            g.add((bnode, QUDT.numericValue,
                   Literal(numeric_value, datatype=XSD.double)))

            unit_ref = resolve_unit_uri(meta.get('unit'))
            if unit_ref:
                g.add((bnode, QUDT.unit, unit_ref))

            qk_ref = resolve_qk_uri(meta.get('quantity_kind'))
            if qk_ref:
                g.add((bnode, QUDT.hasQuantityKind, qk_ref))

            prop_local = prop_uri_str.split('#')[-1] if '#' in prop_uri_str else prop_uri_str
            logger.info(f"  {prop_local}: {numeric_value} -> QuantityValue "
                        f"(unit={meta.get('unit')}, qk={meta.get('quantity_kind')})")
            migrated += 1

    if migrated > 0 and apply:
        if backup:
            bak_path = ttl_path.with_suffix('.ttl.bak')
            shutil.copy2(ttl_path, bak_path)
            logger.info(f"  Backup: {bak_path}")

        # Bind common prefixes for clean output
        g.bind("dyn", DYN)
        g.bind("qudt", QUDT)
        g.bind("unit", UNIT)
        g.bind("qkdv", QKDV)
        g.bind("xsd", XSD)

        g.serialize(destination=str(ttl_path), format="turtle")
        logger.info(f"  Saved: {ttl_path}")

    return migrated


def main():
    parser = argparse.ArgumentParser(
        description="Migrate user_data TTL files to qudt:QuantityValue pattern."
    )
    parser.add_argument(
        "--apply", action="store_true",
        help="Apply changes in-place (default is dry-run)."
    )
    parser.add_argument(
        "--backup", action="store_true",
        help="Keep .bak copies of modified files (only with --apply)."
    )
    parser.add_argument(
        "--dir", type=str, default=None,
        help="Specific directory to migrate (default: user_data/)."
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true",
        help="Enable debug logging."
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

    # Find all TTL files
    ttl_files = sorted(target_dir.rglob("*.ttl"))
    logger.info(f"Found {len(ttl_files)} TTL files in {target_dir}")

    if not args.apply:
        logger.info("DRY RUN - no files will be modified. Use --apply to write changes.")

    total_migrated = 0
    files_changed = 0

    for ttl_path in ttl_files:
        logger.info(f"\n{ttl_path.relative_to(project_root)}:")
        count = migrate_file(ttl_path, measurement_props, args.apply, args.backup)
        if count > 0:
            total_migrated += count
            files_changed += 1

    # Summary
    mode = "APPLIED" if args.apply else "DRY RUN"
    logger.info(f"\n{'='*60}")
    logger.info(f"Migration complete ({mode})")
    logger.info(f"  Files scanned:  {len(ttl_files)}")
    logger.info(f"  Files changed:  {files_changed}")
    logger.info(f"  Props migrated: {total_migrated}")
    if not args.apply and total_migrated > 0:
        logger.info("  Run with --apply to write changes.")


if __name__ == "__main__":
    main()
