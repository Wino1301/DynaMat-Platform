"""
DynaMat Platform - QUDT Cache Rebuild Tool
Forces a fresh download of the QUDT ontology and rebuilds the local cache.

Use this tool when:
- The cache has incorrect or missing units
- QUDT ontology has been updated online
- Cache files are corrupted
- You want to force a refresh of unit definitions

Usage:
    python tools/rebuild_qudt_cache.py
    python tools/rebuild_qudt_cache.py --verbose
    python tools/rebuild_qudt_cache.py --show-info
    python tools/rebuild_qudt_cache.py --clear-only
"""

import sys
import argparse
from pathlib import Path

# Add project root to Python path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dynamat.ontology.qudt import QUDTManager


def show_cache_info(manager: QUDTManager, verbose: bool = False):
    """Display current cache information."""
    cache_info = manager.get_cache_info()

    print("\nQUDT Cache Information:")
    print("=" * 70)
    print(f"  Cache exists:        {cache_info['cache_exists']}")
    print(f"  Cache fresh:         {cache_info['cache_fresh']}")
    print(f"  Data loaded:         {cache_info['is_loaded']}")
    print(f"  Unit count:          {cache_info['unit_count']}")
    print(f"  Quantity kinds:      {cache_info['quantity_kind_count']}")
    print(f"  Cache location:      {cache_info['cache_file']}")

    if verbose and cache_info['unit_count'] > 0:
        print("\nSample units by quantity kind:")
        # Show a few examples
        for qk in list(manager.units_by_quantity_kind.keys())[:5]:
            units = manager.units_by_quantity_kind[qk][:3]
            print(f"\n  {qk}:")
            for unit in units:
                print(f"    - {unit.symbol:10s} ({unit.label})")

        if len(manager.units_by_quantity_kind) > 5:
            print(f"\n  ... and {len(manager.units_by_quantity_kind) - 5} more quantity kinds")

    print()


def rebuild_cache(verbose: bool = False) -> bool:
    """
    Rebuild the QUDT cache from online source.

    Args:
        verbose: Show detailed progress information

    Returns:
        True if successful, False otherwise
    """
    print("\nRebuilding QUDT cache...")
    print("=" * 70)

    # Create QUDT manager
    manager = QUDTManager()

    if verbose:
        print("\nBefore rebuild:")
        show_cache_info(manager, verbose=False)

    # Perform rebuild
    print("\nDownloading QUDT ontology from online source...")
    print("This may take a moment...\n")

    success = manager.rebuild_cache()

    if success:
        print("\n[SUCCESS] Cache rebuild successful!")

        if verbose:
            print("\nAfter rebuild:")
            show_cache_info(manager, verbose=True)
        else:
            cache_info = manager.get_cache_info()
            print(f"  - Loaded {cache_info['unit_count']} units")
            print(f"  - Organized into {cache_info['quantity_kind_count']} quantity kinds")
            print(f"  - Cache saved to: {cache_info['cache_file']}")
    else:
        print("\n[FAILED] Cache rebuild failed!")
        print("Possible causes:")
        print("  - No internet connection")
        print("  - QUDT service unavailable")
        print("  - Permission issues writing to cache directory")

        if verbose:
            print("\nTry running with --verbose for more details")

    print()
    return success


def clear_cache(verbose: bool = False) -> bool:
    """
    Clear the QUDT cache without rebuilding.

    Args:
        verbose: Show detailed information

    Returns:
        True if successful, False otherwise
    """
    print("\nClearing QUDT cache...")
    print("=" * 70)

    manager = QUDTManager()

    if verbose:
        print("\nBefore clearing:")
        show_cache_info(manager, verbose=False)

    manager.clear_cache()

    print("\n[SUCCESS] Cache cleared")

    if verbose:
        print("\nAfter clearing:")
        show_cache_info(manager, verbose=False)

    print()
    return True


def main():
    """Main entry point for the QUDT cache rebuild tool."""
    parser = argparse.ArgumentParser(
        description='Rebuild QUDT unit cache from online source',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Rebuild cache (standard)
  python tools/rebuild_qudt_cache.py

  # Rebuild with detailed progress
  python tools/rebuild_qudt_cache.py --verbose

  # Show cache info without rebuilding
  python tools/rebuild_qudt_cache.py --show-info

  # Show detailed cache info
  python tools/rebuild_qudt_cache.py --show-info --verbose

  # Clear cache without rebuilding
  python tools/rebuild_qudt_cache.py --clear-only

When to use this tool:
  - Cache has incorrect or missing units
  - QUDT ontology updated online
  - Cache files corrupted
  - Force refresh of unit definitions
        """
    )

    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Show detailed progress and information')
    parser.add_argument('--show-info', action='store_true',
                       help='Show cache information without rebuilding')
    parser.add_argument('--clear-only', action='store_true',
                       help='Clear cache without rebuilding')

    args = parser.parse_args()

    # Handle show-info mode
    if args.show_info:
        manager = QUDTManager()
        manager.load()  # Load current cache if available
        show_cache_info(manager, verbose=args.verbose)
        sys.exit(0)

    # Handle clear-only mode
    if args.clear_only:
        success = clear_cache(verbose=args.verbose)
        sys.exit(0 if success else 1)

    # Default: rebuild cache
    success = rebuild_cache(verbose=args.verbose)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
