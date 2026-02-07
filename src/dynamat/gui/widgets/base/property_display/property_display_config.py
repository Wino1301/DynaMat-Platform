"""
DynaMat Platform - Property Display Configuration
Configuration dataclass for PropertyDisplayWidget.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class PropertyDisplayConfig:
    """
    Configuration for PropertyDisplayWidget.

    Defines which properties to display, how to label them, and how to
    resolve nested properties via object property links.

    Attributes:
        title: Title for the property display group box
        properties: List of property URIs to display (e.g., ['dyn:hasWaveSpeed', 'dyn:hasElasticModulus'])
        property_labels: Optional custom label overrides {property_uri: custom_label}
        follow_links: Optional mapping for nested property resolution
                      e.g., {'dyn:hasMaterial': ['dyn:hasWaveSpeed']} means
                      "follow the hasMaterial link to get hasWaveSpeed"
        show_empty: If True, show properties even when they have no value (as N/A)

    Example:
        >>> config = PropertyDisplayConfig(
        ...     title="Bar Material Properties",
        ...     properties=["dyn:hasWaveSpeed", "dyn:hasElasticModulus", "dyn:hasDensity"],
        ...     follow_links={"dyn:hasMaterial": ["dyn:hasWaveSpeed", "dyn:hasElasticModulus", "dyn:hasDensity"]}
        ... )
        >>> widget = PropertyDisplayWidget(config=config, ontology_manager=manager)
        >>> widget.setIndividual("dyn:IncidentBar_C350")
    """

    # Required
    title: str
    properties: List[str]

    # Optional
    property_labels: Optional[Dict[str, str]] = None
    follow_links: Optional[Dict[str, List[str]]] = None
    show_empty: bool = False

    def get_label(self, property_uri: str, default: Optional[str] = None) -> Optional[str]:
        """
        Get the display label for a property.

        Checks custom labels first, falls back to default if provided.

        Args:
            property_uri: URI of the property
            default: Default label if no custom label defined

        Returns:
            Custom label if defined, otherwise the default
        """
        if self.property_labels:
            # Check both prefixed and non-prefixed forms
            normalized = self.normalize_uri(property_uri)
            if property_uri in self.property_labels:
                return self.property_labels[property_uri]
            if normalized in self.property_labels:
                return self.property_labels[normalized]
        return default

    def normalize_uri(self, uri: str) -> str:
        """
        Normalize a URI to prefixed form (dyn:propertyName).

        Args:
            uri: Full or prefixed URI

        Returns:
            Prefixed URI (e.g., 'dyn:hasWaveSpeed')
        """
        if uri.startswith('https://dynamat.utep.edu/ontology#'):
            return f"dyn:{uri.split('#')[-1]}"
        elif '#' in uri:
            local_name = uri.split('#')[-1]
            return f"dyn:{local_name}"
        return uri

    def get_normalized_properties(self) -> List[str]:
        """
        Get the list of properties with normalized URIs.

        Returns:
            List of property URIs in dyn: prefixed form
        """
        return [self.normalize_uri(p) for p in self.properties]
