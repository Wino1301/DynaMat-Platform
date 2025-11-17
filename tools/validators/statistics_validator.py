"""
DynaMat Platform - Statistics Validator
Reusable validation functions for manager statistics dictionaries.
"""

from typing import Dict, Any, List, Tuple, Optional, Set
import json


def validate_statistics_structure(
    stats: Dict[str, Any],
    expected_categories: Optional[Set[str]] = None,
    manager_name: str = "Unknown"
) -> Tuple[bool, List[str]]:
    """
    Validate that statistics dictionary has expected structure.

    Args:
        stats: Statistics dictionary from manager
        expected_categories: Set of expected top-level keys (default: common categories)
        manager_name: Name of manager for error messages

    Returns:
        Tuple of (passed: bool, errors: List[str])
    """
    errors = []

    # Check stats is a dictionary
    if not isinstance(stats, dict):
        errors.append(f"{manager_name}: statistics is not a dict, got {type(stats).__name__}")
        return False, errors

    # Default expected categories (most managers have these)
    if expected_categories is None:
        expected_categories = {'configuration', 'execution', 'health'}

    # Check for expected categories
    missing_categories = expected_categories - set(stats.keys())
    if missing_categories:
        errors.append(
            f"{manager_name}: missing expected categories: {', '.join(sorted(missing_categories))}"
        )

    # Check each category is a dictionary
    for category, value in stats.items():
        if not isinstance(value, dict):
            errors.append(
                f"{manager_name}: category '{category}' is not a dict, got {type(value).__name__}"
            )

    passed = len(errors) == 0
    return passed, errors


def validate_json_serializable(
    stats: Dict[str, Any],
    manager_name: str = "Unknown"
) -> Tuple[bool, List[str]]:
    """
    Validate that statistics dictionary is JSON-serializable.

    Args:
        stats: Statistics dictionary from manager
        manager_name: Name of manager for error messages

    Returns:
        Tuple of (passed: bool, errors: List[str])
    """
    errors = []

    try:
        json.dumps(stats)
    except (TypeError, ValueError) as e:
        errors.append(f"{manager_name}: statistics not JSON-serializable: {e}")
        return False, errors

    return True, errors


def validate_counter_types(
    stats: Dict[str, Any],
    manager_name: str = "Unknown",
    verbose: bool = False
) -> Tuple[bool, List[str]]:
    """
    Validate that all counter values are appropriate types (int, float, str, list, dict).

    Args:
        stats: Statistics dictionary from manager
        manager_name: Name of manager for error messages
        verbose: Show detailed type information

    Returns:
        Tuple of (passed: bool, errors: List[str])
    """
    errors = []
    allowed_types = (int, float, str, bool, list, dict, type(None))

    def check_value(value: Any, path: str):
        """Recursively check value types."""
        if isinstance(value, dict):
            for k, v in value.items():
                check_value(v, f"{path}.{k}")
        elif isinstance(value, list):
            for i, item in enumerate(value):
                check_value(item, f"{path}[{i}]")
        elif not isinstance(value, allowed_types):
            errors.append(
                f"{manager_name}: invalid type at {path}: {type(value).__name__}"
            )

    # Check all categories
    for category, content in stats.items():
        if isinstance(content, dict):
            for key, value in content.items():
                check_value(value, f"{category}.{key}")

    passed = len(errors) == 0
    return passed, errors


def validate_category(
    stats: Dict[str, Any],
    category: str,
    required_keys: Optional[Set[str]] = None,
    manager_name: str = "Unknown"
) -> Tuple[bool, List[str]]:
    """
    Validate a specific category within statistics.

    Args:
        stats: Statistics dictionary from manager
        category: Category name to validate
        required_keys: Set of required keys within category
        manager_name: Name of manager for error messages

    Returns:
        Tuple of (passed: bool, errors: List[str])
    """
    errors = []

    # Check category exists
    if category not in stats:
        errors.append(f"{manager_name}: missing category '{category}'")
        return False, errors

    category_data = stats[category]

    # Check category is a dictionary
    if not isinstance(category_data, dict):
        errors.append(
            f"{manager_name}: category '{category}' is not a dict, got {type(category_data).__name__}"
        )
        return False, errors

    # Check required keys if specified
    if required_keys:
        missing_keys = required_keys - set(category_data.keys())
        if missing_keys:
            errors.append(
                f"{manager_name}: category '{category}' missing keys: {', '.join(sorted(missing_keys))}"
            )

    passed = len(errors) == 0
    return passed, errors


def compare_statistics(
    before_stats: Dict[str, Any],
    after_stats: Dict[str, Any],
    expected_changes: Dict[str, Any],
    manager_name: str = "Unknown"
) -> Tuple[bool, List[str], Dict[str, Any]]:
    """
    Compare statistics before and after operations to verify expected changes.

    Args:
        before_stats: Statistics before operations
        after_stats: Statistics after operations
        expected_changes: Dictionary describing expected changes
                         Format: {'category.key': expected_delta}
                         Example: {'execution.total_widgets': 1, 'execution.widget_creation_counts.unit_value': 1}
        manager_name: Name of manager for error messages

    Returns:
        Tuple of (passed: bool, errors: List[str], actual_changes: Dict[str, Any])
    """
    errors = []
    actual_changes = {}

    def get_nested_value(d: Dict[str, Any], path: str) -> Any:
        """Get value from nested dictionary using dot notation."""
        keys = path.split('.')
        value = d
        for key in keys:
            if isinstance(value, dict):
                value = value.get(key, None)
            else:
                return None
        return value

    # Check each expected change
    for path, expected_delta in expected_changes.items():
        before_value = get_nested_value(before_stats, path)
        after_value = get_nested_value(after_stats, path)

        # Handle missing values
        if before_value is None:
            errors.append(f"{manager_name}: path '{path}' not found in before_stats")
            continue

        if after_value is None:
            errors.append(f"{manager_name}: path '{path}' not found in after_stats")
            continue

        # Calculate actual delta
        try:
            if isinstance(before_value, (int, float)) and isinstance(after_value, (int, float)):
                actual_delta = after_value - before_value
            elif isinstance(before_value, dict) and isinstance(after_value, dict):
                # For dictionaries, check if new keys appeared
                actual_delta = set(after_value.keys()) - set(before_value.keys())
            elif isinstance(before_value, list) and isinstance(after_value, list):
                # For lists, check length change
                actual_delta = len(after_value) - len(before_value)
            else:
                errors.append(
                    f"{manager_name}: cannot compare {path}, incompatible types: "
                    f"{type(before_value).__name__} vs {type(after_value).__name__}"
                )
                continue

            actual_changes[path] = actual_delta

            # Validate expected delta
            if actual_delta != expected_delta:
                errors.append(
                    f"{manager_name}: {path} changed by {actual_delta}, expected {expected_delta}"
                )

        except Exception as e:
            errors.append(f"{manager_name}: error comparing {path}: {e}")

    passed = len(errors) == 0
    return passed, errors, actual_changes


def validate_error_tracking(
    stats: Dict[str, Any],
    manager_name: str = "Unknown",
    max_errors: int = 10
) -> Tuple[bool, List[str]]:
    """
    Validate error tracking in statistics.

    Args:
        stats: Statistics dictionary from manager
        manager_name: Name of manager for error messages
        max_errors: Maximum expected number of tracked errors

    Returns:
        Tuple of (passed: bool, errors: List[str])
    """
    errors = []

    # Common error tracking patterns
    error_keys = [
        'health.creation_errors',
        'health.recent_errors',
        'errors.recent_errors',
        'health.error_count'
    ]

    found_error_tracking = False

    for key_path in error_keys:
        parts = key_path.split('.')
        if len(parts) != 2:
            continue

        category, key = parts
        if category in stats and key in stats[category]:
            found_error_tracking = True
            error_data = stats[category][key]

            # Check type
            if isinstance(error_data, list):
                # Check list length is reasonable (capped)
                if len(error_data) > max_errors:
                    errors.append(
                        f"{manager_name}: {key_path} has {len(error_data)} errors, "
                        f"should be capped at {max_errors}"
                    )
            elif isinstance(error_data, int):
                # Just a count, which is fine
                pass
            else:
                errors.append(
                    f"{manager_name}: {key_path} has unexpected type {type(error_data).__name__}"
                )

    if not found_error_tracking:
        # Not all managers need error tracking, so this is just a warning
        pass

    passed = len(errors) == 0
    return passed, errors


def print_statistics_summary(
    stats: Dict[str, Any],
    manager_name: str = "Unknown",
    indent: int = 2
):
    """
    Print a formatted summary of statistics.

    Args:
        stats: Statistics dictionary from manager
        manager_name: Name of manager
        indent: Indentation level for nested items
    """
    print(f"\n{manager_name} Statistics Summary:")
    print("-" * 60)

    for category, content in stats.items():
        print(f"\n  {category.upper()}:")

        if isinstance(content, dict):
            for key, value in content.items():
                # Format value based on type
                if isinstance(value, dict):
                    print(f"    {key}:")
                    for k, v in value.items():
                        print(f"      - {k}: {v}")
                elif isinstance(value, list):
                    if len(value) == 0:
                        print(f"    {key}: (empty list)")
                    else:
                        print(f"    {key}: [{len(value)} items]")
                        if len(value) <= 3:
                            for item in value:
                                print(f"      - {item}")
                else:
                    print(f"    {key}: {value}")
        else:
            print(f"    {content}")
