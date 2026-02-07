"""
DynaMat Platform - QUDT Unit Lookup Tool
Look up unit information in the QUDT cache and check quantity kind associations.

This tool helps diagnose unit-related issues by showing:
- Unit details (symbol, label, conversion factors)
- Which quantity kinds a unit is associated with
- Whether a unit exists under a specific quantity kind

Usage:
    python tools/lookup_qudt_unit.py unit:MilliM2
    python tools/lookup_qudt_unit.py unit:MilliM2 --verbose
    python tools/lookup_qudt_unit.py unit:MilliM2 --check-qk qkdv:Area
    python tools/lookup_qudt_unit.py --list-area-units
"""

import sys
import argparse
import json
from pathlib import Path

# Add project root to Python path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dynamat.ontology.qudt import QUDTManager


def normalize_unit_uri(unit_string: str) -> str:
    """Normalize unit URI from prefixed to full form."""
    if unit_string.startswith("http"):
        return unit_string
    elif unit_string.startswith("unit:"):
        return unit_string.replace("unit:", "http://qudt.org/vocab/unit/")
    elif unit_string.startswith("qkdv:"):
        return unit_string.replace("qkdv:", "http://qudt.org/vocab/quantitykind/")
    else:
        # Assume it's a unit if no prefix
        return f"http://qudt.org/vocab/unit/{unit_string}"


def lookup_unit(
    unit_uri: str,
    check_qk: str = None,
    verbose: bool = False,
    json_output: bool = False
):
    """
    Look up a unit in the QUDT cache.

    Args:
        unit_uri: Unit URI to look up (e.g., 'unit:MilliM2')
        check_qk: Optional quantity kind to check association with
        verbose: Show detailed information
        json_output: Output as JSON
    """
    try:
        # Initialize QUDT manager
        qm = QUDTManager()
        qm.load()

        # Normalize URI
        unit_uri_full = normalize_unit_uri(unit_uri)

        # Look up unit
        unit = qm.get_unit_by_uri(unit_uri_full)

        if json_output:
            result = {
                "unit_uri": unit_uri,
                "unit_uri_full": unit_uri_full,
                "found": unit is not None
            }

            if unit:
                result["unit"] = {
                    "uri": unit.uri,
                    "symbol": unit.symbol,
                    "label": unit.label,
                    "quantity_kinds": unit.quantity_kinds,
                    "conversion_multiplier": unit.conversion_multiplier,
                    "conversion_offset": unit.conversion_offset
                }

                # Check specific quantity kind if requested
                if check_qk:
                    check_qk_full = normalize_unit_uri(check_qk)
                    in_qk = check_qk_full in unit.quantity_kinds
                    result["in_requested_quantity_kind"] = in_qk
                    result["requested_quantity_kind"] = check_qk_full

            print(json.dumps(result, indent=2))

        else:
            print(f"\nQUDT Unit Lookup: {unit_uri}")
            print("=" * 70)

            if not unit:
                print("\n[NOT FOUND] Unit not found in QUDT cache!")
                print(f"  Searched for: {unit_uri_full}")
                print("\nPossible reasons:")
                print("  - Unit URI is incorrect")
                print("  - Unit not in QUDT ontology")
                print("  - Cache needs to be rebuilt")
                return

            print(f"\n[FOUND] Unit exists in cache")
            print(f"\nBasic Information:")
            print(f"  URI:    {unit.uri}")
            print(f"  Symbol: {unit.symbol}")
            print(f"  Label:  {unit.label}")

            if verbose:
                print(f"\nConversion Information:")
                print(f"  Multiplier: {unit.conversion_multiplier}")
                print(f"  Offset:     {unit.conversion_offset}")
                print(f"  Formula:    SI_value = (value * {unit.conversion_multiplier}) + {unit.conversion_offset}")

            # Show all quantity kinds from the unit
            print(f"\nQuantity Kind Associations:")
            if unit.quantity_kinds:
                print(f"  This unit is defined for {len(unit.quantity_kinds)} quantity kind(s):")
                for qk in unit.quantity_kinds:
                    qk_short = qk.replace("http://qudt.org/vocab/quantitykind/", "qkdv:")
                    print(f"    - {qk_short}")
            else:
                print("  [WARNING] Unit has no quantity kinds!")

            # Also verify indexing
            indexed_qks = []
            for qk, units in qm.units_by_quantity_kind.items():
                if any(u.uri == unit_uri_full for u in units):
                    indexed_qks.append(qk)

            missing_from_index = set(unit.quantity_kinds) - set(indexed_qks)
            if missing_from_index:
                print(f"\n  [WARNING] Unit not indexed under some quantity kinds:")
                for qk in missing_from_index:
                    qk_short = qk.replace("http://qudt.org/vocab/quantitykind/", "qkdv:")
                    print(f"    - {qk_short}")

            # Check specific quantity kind if requested
            if check_qk:
                check_qk_full = normalize_unit_uri(check_qk)
                print(f"\nChecking association with {check_qk}:")
                in_qk = check_qk_full in unit.quantity_kinds
                if in_qk:
                    print(f"  [OK] Unit IS defined for this quantity kind")
                else:
                    print(f"  [PROBLEM] Unit is NOT defined for this quantity kind")
                    print(f"\n  This means the unit won't be appropriate for {check_qk}")
                    print(f"  The unit is defined for:")
                    for qk in unit.quantity_kinds:
                        qk_short = qk.replace("http://qudt.org/vocab/quantitykind/", "qkdv:")
                        print(f"    - {qk_short}")

            print()

    except Exception as e:
        if json_output:
            print(json.dumps({"error": str(e), "success": False}, indent=2))
        else:
            print(f"\n[ERROR] {e}")
            if verbose:
                import traceback
                traceback.print_exc()


def list_units_for_qk(quantity_kind: str, verbose: bool = False, json_output: bool = False):
    """List all units for a quantity kind."""
    try:
        qm = QUDTManager()
        qm.load()

        qk_full = normalize_unit_uri(quantity_kind)
        units = qm.get_units_for_quantity_kind(qk_full)

        if json_output:
            unit_list = [
                {
                    "uri": u.uri,
                    "symbol": u.symbol,
                    "label": u.label,
                    "multiplier": u.conversion_multiplier if verbose else None,
                    "offset": u.conversion_offset if verbose else None
                }
                for u in units
            ]
            # Remove None values if not verbose
            if not verbose:
                unit_list = [{k: v for k, v in u.items() if v is not None} for u in unit_list]

            print(json.dumps({
                "quantity_kind": qk_full,
                "count": len(units),
                "units": unit_list
            }, indent=2))
        else:
            print(f"\nUnits for {quantity_kind}:")
            print("=" * 70)
            print(f"Found {len(units)} units\n")

            for unit in units:
                print(f"  {unit.symbol:15s} - {unit.label}")
                if verbose:
                    print(f"      URI: {unit.uri}")
                    print(f"      Multiplier: {unit.conversion_multiplier}")
                    print()

    except Exception as e:
        if json_output:
            print(json.dumps({"error": str(e)}, indent=2))
        else:
            print(f"\n[ERROR] {e}")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Look up QUDT unit information',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Look up a specific unit
  python tools/lookup_qudt_unit.py unit:MilliM2

  # Look up with verbose details
  python tools/lookup_qudt_unit.py unit:MilliM2 --verbose

  # Check if unit is associated with a specific quantity kind
  python tools/lookup_qudt_unit.py unit:MilliM2 --check-qk qkdv:Area

  # List all units for a quantity kind
  python tools/lookup_qudt_unit.py --list-qk qkdv:Area

  # List with verbose details
  python tools/lookup_qudt_unit.py --list-qk qkdv:Length --verbose

  # JSON output for scripting
  python tools/lookup_qudt_unit.py unit:MilliM2 --json

Common quantity kinds:
  qkdv:Length, qkdv:Area, qkdv:Volume, qkdv:Mass, qkdv:Force,
  qkdv:Pressure, qkdv:ThermodynamicTemperature, qkdv:Time
        """
    )

    parser.add_argument('unit', nargs='?',
                       help='Unit to look up (e.g., unit:MilliM2)')
    parser.add_argument('--check-qk', metavar='QUANTITY_KIND',
                       help='Check if unit is associated with this quantity kind')
    parser.add_argument('--list-qk', metavar='QUANTITY_KIND',
                       help='List all units for a quantity kind')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Show detailed information')
    parser.add_argument('--json', action='store_true',
                       help='Output as JSON')

    args = parser.parse_args()

    # List mode
    if args.list_qk:
        list_units_for_qk(args.list_qk, args.verbose, args.json)
        return

    # Lookup mode
    if not args.unit:
        parser.error("unit argument required (or use --list-qk)")

    lookup_unit(args.unit, args.check_qk, args.verbose, args.json)


if __name__ == "__main__":
    main()
