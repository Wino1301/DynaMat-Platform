"""
DynaMat Platform - Entity Selector Configuration
Configuration dataclass for the EntitySelectorWidget
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional
from pathlib import Path


class SelectionMode(Enum):
    """Selection mode for entity selector."""
    SINGLE = "single"
    MULTIPLE = "multiple"


@dataclass
class EntitySelectorConfig:
    """
    Configuration for EntitySelectorWidget.

    Defines how the entity selector behaves, what properties to display,
    and what filtering options are available.

    Attributes:
        class_uri: Full URI of the ontology class to select from (required)
        display_properties: List of property URIs to show as table columns
        property_labels: Optional mapping of property URIs to column header labels
        filter_properties: List of property URIs to create filter dropdowns for
        filter_labels: Optional mapping of filter property URIs to dropdown labels
        details_properties: List of property URIs to show in details panel
        details_labels: Optional mapping of details property URIs to labels
        selection_mode: Single or multiple selection mode
        show_details_panel: Whether to show the details panel
        show_search_box: Whether to show the search box
        show_refresh_button: Whether to show the refresh button
        data_directory: Optional directory to scan for instances
        file_pattern: Glob pattern for TTL files (default: "*.ttl")
        id_property: Property URI used as the primary identifier

    Example:
        config = EntitySelectorConfig(
            class_uri="https://dynamat.utep.edu/ontology#Specimen",
            display_properties=[
                "https://dynamat.utep.edu/ontology#hasSpecimenID",
                "https://dynamat.utep.edu/ontology#hasMaterial",
                "https://dynamat.utep.edu/ontology#hasShape",
            ],
            property_labels={
                "https://dynamat.utep.edu/ontology#hasSpecimenID": "Specimen ID",
                "https://dynamat.utep.edu/ontology#hasMaterial": "Material",
            },
            filter_properties=["https://dynamat.utep.edu/ontology#hasMaterial"],
            show_details_panel=True,
        )
    """

    # Required
    class_uri: str

    # Table display
    display_properties: List[str] = field(default_factory=list)
    property_labels: Optional[Dict[str, str]] = None

    # Filtering
    filter_properties: Optional[List[str]] = None
    filter_labels: Optional[Dict[str, str]] = None

    # Details panel
    details_properties: Optional[List[str]] = None
    details_labels: Optional[Dict[str, str]] = None

    # Behavior
    selection_mode: SelectionMode = SelectionMode.SINGLE
    show_details_panel: bool = True
    show_search_box: bool = True
    show_refresh_button: bool = True

    # Data source
    data_directory: Optional[Path] = None
    file_pattern: str = "*.ttl"

    # Identity
    id_property: Optional[str] = None

    def __post_init__(self):
        """Validate configuration after initialization."""
        if not self.class_uri:
            raise ValueError("class_uri is required")

        # Convert data_directory to Path if string
        if isinstance(self.data_directory, str):
            self.data_directory = Path(self.data_directory)

        # Initialize empty dicts if None
        if self.property_labels is None:
            self.property_labels = {}
        if self.filter_labels is None:
            self.filter_labels = {}
        if self.details_labels is None:
            self.details_labels = {}

    def get_property_label(self, prop_uri: str) -> str:
        """
        Get display label for a property URI.

        Args:
            prop_uri: Property URI

        Returns:
            Human-readable label
        """
        # Check explicit mapping first
        if self.property_labels and prop_uri in self.property_labels:
            return self.property_labels[prop_uri]

        # Extract name from URI and format
        if '#' in prop_uri:
            name = prop_uri.split('#')[-1]
        elif '/' in prop_uri:
            name = prop_uri.split('/')[-1]
        else:
            name = prop_uri

        # Remove common prefixes
        if name.startswith('has'):
            name = name[3:]

        # Add spaces before capitals (camelCase to Title Case)
        import re
        label = re.sub(r'([a-z])([A-Z])', r'\1 \2', name)

        return label

    def get_filter_label(self, prop_uri: str) -> str:
        """
        Get display label for a filter property.

        Args:
            prop_uri: Filter property URI

        Returns:
            Human-readable label for filter dropdown
        """
        if self.filter_labels and prop_uri in self.filter_labels:
            return self.filter_labels[prop_uri]
        return self.get_property_label(prop_uri)

    def get_details_label(self, prop_uri: str) -> str:
        """
        Get display label for a details property.

        Args:
            prop_uri: Details property URI

        Returns:
            Human-readable label for details panel
        """
        if self.details_labels and prop_uri in self.details_labels:
            return self.details_labels[prop_uri]
        return self.get_property_label(prop_uri)

    def normalize_property_uri(self, prop: str, default_namespace: str = "https://dynamat.utep.edu/ontology#") -> str:
        """
        Normalize a property name to full URI.

        Args:
            prop: Property name (short or full URI)
            default_namespace: Namespace to prepend if not a full URI

        Returns:
            Full property URI
        """
        if prop.startswith('http://') or prop.startswith('https://'):
            return prop

        # Handle prefixed names like "dyn:hasSpecimenID"
        if ':' in prop:
            prefix, local = prop.split(':', 1)
            if prefix == 'dyn':
                return f"{default_namespace}{local}"

        return f"{default_namespace}{prop}"

    def get_normalized_display_properties(self) -> List[str]:
        """Get display properties as full URIs."""
        return [self.normalize_property_uri(p) for p in self.display_properties]

    def get_normalized_filter_properties(self) -> List[str]:
        """Get filter properties as full URIs."""
        if not self.filter_properties:
            return []
        return [self.normalize_property_uri(p) for p in self.filter_properties]

    def get_normalized_details_properties(self) -> List[str]:
        """Get details properties as full URIs."""
        if not self.details_properties:
            return []
        return [self.normalize_property_uri(p) for p in self.details_properties]
