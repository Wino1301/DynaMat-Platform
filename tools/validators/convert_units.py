"""
DynaMat Platform - Unit Conversion Tool
Convert values between different QUDT units using the platform's unit conversion engine.

This tool provides command-line access to the QUDT-based unit conversion system,
supporting both ratio scales (length, mass, force) and interval scales (temperature).

Usage:
    python tools/convert_units.py 10 unit:IN unit:MilliM
    python tools/convert_units.py 100 unit:DEG_C unit:K
    python tools/convert_units.py 5.5 unit:LB_F unit:N --verbose
    python tools/convert_units.py --list-units qkdv:Length
"""

import sys
import argparse
import json
from pathlib import Path
from typing import Optional

# Add project root to Python path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dynamat.ontology import OntologyManager


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


def convert_units(
    value: float,
    from_unit: str,
    to_unit: str,
    verbose: bool = False,
    json_output: bool = False
) -> Optional[float]:
    """
    Convert value between units using QUDT.

    Args:
        value: Numeric value to convert
        from_unit: Source unit (e.g., 'unit:IN', 'unit:DEG_C')
        to_unit: Target unit (e.g., 'unit:MilliM', 'unit:K')
        verbose: Show conversion details (multipliers, offsets)
        json_output: Output as JSON

    Returns:
        Converted value or None on error
    """
    try:
        # Initialize ontology manager and QUDT
        om = OntologyManager()
        qudt_manager = om.qudt_manager

        # Ensure QUDT data is loaded
        if not qudt_manager._is_loaded:
            if not json_output and verbose:
                print("Loading QUDT units database...")
            qudt_manager.load()

        # Perform conversion
        result = qudt_manager.convert_value(value, from_unit, to_unit)

        # Output results
        if json_output:
            output = {
                "input_value": value,
                "from_unit": from_unit,
                "to_unit": to_unit,
                "result": result,
                "success": True
            }

            if verbose:
                # Normalize URIs for lookup
                from_unit_norm = normalize_unit_uri(from_unit)
                to_unit_norm = normalize_unit_uri(to_unit)

                from_unit_obj = qudt_manager.get_unit_by_uri(from_unit_norm)
                to_unit_obj = qudt_manager.get_unit_by_uri(to_unit_norm)
                output["conversion_details"] = {
                    "from_unit": {
                        "label": from_unit_obj.label,
                        "symbol": from_unit_obj.symbol,
                        "multiplier": from_unit_obj.conversion_multiplier,
                        "offset": from_unit_obj.conversion_offset
                    },
                    "to_unit": {
                        "label": to_unit_obj.label,
                        "symbol": to_unit_obj.symbol,
                        "multiplier": to_unit_obj.conversion_multiplier,
                        "offset": to_unit_obj.conversion_offset
                    }
                }

            print(json.dumps(output, indent=2))

        else:
            print(f"\n{value} {from_unit} = {result} {to_unit}")

            if verbose:
                # Normalize URIs for lookup
                from_unit_norm = normalize_unit_uri(from_unit)
                to_unit_norm = normalize_unit_uri(to_unit)

                from_unit_obj = qudt_manager.get_unit_by_uri(from_unit_norm)
                to_unit_obj = qudt_manager.get_unit_by_uri(to_unit_norm)

                if not from_unit_obj or not to_unit_obj:
                    if not json_output:
                        print(f"\nWarning: Could not retrieve unit details for verbose output")
                else:
                    print(f"\nConversion Details:")
                    print(f"  From: {from_unit_obj.label} ({from_unit_obj.symbol})")
                    print(f"    URI: {from_unit_obj.uri}")
                    print(f"    Multiplier: {from_unit_obj.conversion_multiplier}")
                    print(f"    Offset: {from_unit_obj.conversion_offset}")
                    print(f"    Quantity Kind: {from_unit_obj.quantity_kind}")

                    print(f"\n  To: {to_unit_obj.label} ({to_unit_obj.symbol})")
                    print(f"    URI: {to_unit_obj.uri}")
                    print(f"    Multiplier: {to_unit_obj.conversion_multiplier}")
                    print(f"    Offset: {to_unit_obj.conversion_offset}")
                    print(f"    Quantity Kind: {to_unit_obj.quantity_kind}")

                    print(f"\n  Formula:")
                    print(f"    SI value = ({value} × {from_unit_obj.conversion_multiplier}) + {from_unit_obj.conversion_offset}")
                    si_value = (value * from_unit_obj.conversion_multiplier) + from_unit_obj.conversion_offset
                    print(f"            = {si_value}")
                    print(f"    Result = ({si_value} - {to_unit_obj.conversion_offset}) / {to_unit_obj.conversion_multiplier}")
                    print(f"           = {result}")

        return result

    except ValueError as e:
        if json_output:
            error_output = {
                "input_value": value,
                "from_unit": from_unit,
                "to_unit": to_unit,
                "error": str(e),
                "success": False
            }
            print(json.dumps(error_output, indent=2))
        else:
            print(f"\nERROR: {e}")
        return None

    except Exception as e:
        if json_output:
            error_output = {
                "error": str(e),
                "success": False
            }
            print(json.dumps(error_output, indent=2))
        else:
            print(f"\nERROR: Conversion failed: {e}")
            if verbose:
                import traceback
                traceback.print_exc()
        return None


def list_units(
    quantity_kind: Optional[str] = None,
    json_output: bool = False,
    verbose: bool = False
):
    """
    List available units, optionally filtered by quantity kind.

    Args:
        quantity_kind: Optional quantity kind to filter by (e.g., 'qkdv:Length')
        json_output: Output as JSON
        verbose: Show additional unit details
    """
    try:
        # Initialize ontology manager and QUDT
        om = OntologyManager()
        qudt_manager = om.qudt_manager

        # Ensure QUDT data is loaded
        if not qudt_manager._is_loaded:
            if not json_output and verbose:
                print("Loading QUDT units database...")
            qudt_manager.load()

        if quantity_kind:
            # List units for specific quantity kind
            units = qudt_manager.get_units_for_quantity_kind(quantity_kind)

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
                    "quantity_kind": quantity_kind,
                    "count": len(units),
                    "units": unit_list
                }, indent=2))

            else:
                print(f"\nUnits for {quantity_kind}:")
                print("=" * 70)
                print(f"Found {len(units)} units\n")

                for unit in sorted(units, key=lambda u: u.symbol):
                    print(f"  {unit.symbol:12s} - {unit.label}")
                    if verbose:
                        print(f"      URI: {unit.uri}")
                        print(f"      Multiplier: {unit.conversion_multiplier}")
                        print(f"      Offset: {unit.conversion_offset}")
                        print()

        else:
            # List all quantity kinds
            quantity_kinds = sorted(qudt_manager.units_by_quantity_kind.keys())

            if json_output:
                qk_list = []
                for qk in quantity_kinds:
                    count = len(qudt_manager.units_by_quantity_kind[qk])
                    qk_list.append({
                        "quantity_kind": qk,
                        "unit_count": count
                    })

                print(json.dumps({
                    "total_quantity_kinds": len(quantity_kinds),
                    "quantity_kinds": qk_list
                }, indent=2))

            else:
                print("\nAvailable Quantity Kinds:")
                print("=" * 70)
                print(f"Found {len(quantity_kinds)} quantity kinds\n")

                for qk in quantity_kinds:
                    count = len(qudt_manager.units_by_quantity_kind[qk])
                    print(f"  {qk:40s} ({count} units)")

                print(f"\nUse --list-units <quantity_kind> to see units for a specific kind")

    except Exception as e:
        if json_output:
            print(json.dumps({"error": str(e)}, indent=2))
        else:
            print(f"\nERROR: {e}")
            if verbose:
                import traceback
                traceback.print_exc()


def main():
    """Main entry point for the unit conversion tool."""
    parser = argparse.ArgumentParser(
        description='Convert values between QUDT units',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Convert length units
  python tools/convert_units.py 10 unit:IN unit:MilliM

  # Convert temperature (interval scale with offsets)
  python tools/convert_units.py 100 unit:DEG_C unit:K
  python tools/convert_units.py 32 unit:DEG_F unit:DEG_C

  # Convert force with detailed conversion formula
  python tools/convert_units.py 5.5 unit:LB_F unit:N --verbose

  # Convert mass
  python tools/convert_units.py 150 unit:LB unit:KiloGM

  # List available units for a quantity kind
  python tools/convert_units.py --list-units qkdv:Length
  python tools/convert_units.py --list-units qkdv:Mass
  python tools/convert_units.py --list-units qkdv:ThermodynamicTemperature

  # List all quantity kinds
  python tools/convert_units.py --list-units

  # JSON output for scripting
  python tools/convert_units.py 100 unit:IN unit:CentiM --json
  python tools/convert_units.py --list-units qkdv:Length --json

Unit URI Format:
  - Use QUDT unit namespace: unit:MilliM, unit:IN, unit:DEG_C, unit:K
  - Quantity kind namespace: qkdv:Length, qkdv:Mass, qkdv:Force
  - Full URIs also supported: http://qudt.org/vocab/unit/MilliM
        """
    )

    # Positional arguments for conversion
    parser.add_argument('value', nargs='?', type=float,
                       help='Value to convert')
    parser.add_argument('from_unit', nargs='?',
                       help='Source unit (e.g., unit:IN)')
    parser.add_argument('to_unit', nargs='?',
                       help='Target unit (e.g., unit:MilliM)')

    # Optional arguments
    parser.add_argument('--list-units', nargs='?', const=True, metavar='QUANTITY_KIND',
                       help='List available units (optionally for a quantity kind)')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Show detailed conversion formula and unit information')
    parser.add_argument('--json', action='store_true',
                       help='Output as JSON for scripting/automation')

    args = parser.parse_args()

    # Handle list mode
    if args.list_units is not None:
        qk = args.list_units if isinstance(args.list_units, str) else None
        list_units(qk, args.json, args.verbose)
        sys.exit(0)

    # Validate conversion arguments
    if not all([args.value is not None, args.from_unit, args.to_unit]):
        parser.error("value, from_unit, and to_unit are required for conversion")

    # Perform conversion
    result = convert_units(
        args.value,
        args.from_unit,
        args.to_unit,
        args.verbose,
        args.json
    )

    # Exit with appropriate code
    sys.exit(0 if result is not None else 1)


if __name__ == "__main__":
    main()
