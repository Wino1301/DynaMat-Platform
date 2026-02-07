"""
Default group builder that preserves current QGroupBox + QFormLayout behavior.

This builder maintains backward compatibility with existing form generation,
creating the standard QGroupBox with QFormLayout pattern that was previously
hardcoded in LayoutManager.
"""

from typing import List, Dict, Tuple, Optional
from PyQt6.QtWidgets import QWidget, QGroupBox, QFormLayout, QLabel

from ...ontology import PropertyMetadata
from ..core.form_manager import FormField
from .group_builder import GroupBuilder


class DefaultGroupBuilder(GroupBuilder):
    """
    Default group builder that creates QGroupBox with QFormLayout.

    This builder preserves the exact behavior of the original form generation
    system, creating a QGroupBox container with a QFormLayout that contains
    label-widget pairs for each property.
    """

    def build_group(
        self,
        group_name: str,
        properties: List[PropertyMetadata],
        parent: Optional[QWidget] = None
    ) -> Tuple[QWidget, Dict[str, FormField]]:
        """
        Build a standard form group with QGroupBox and QFormLayout.

        Creates the traditional form group structure:
        - QGroupBox with formatted group name as title
        - QFormLayout with label-widget pairs for each property
        - Required fields marked with asterisk (*)

        Args:
            group_name: Name of the form group
            properties: List of PropertyMetadata for this group
            parent: Optional parent widget

        Returns:
            Tuple of (group_box, form_fields_dict)
        """
        # Create QGroupBox with formatted title
        group_box = QGroupBox(self._format_group_name(group_name), parent)
        form_layout = QFormLayout(group_box)

        # Create widgets for all properties in this group
        widgets = self.create_widgets_for_group(properties)

        # Add label-widget pairs to form layout
        form_fields = {}
        sorted_properties = sorted(properties, key=lambda p: p.display_order or 0)

        for prop in sorted_properties:
            # Skip if widget creation failed
            if prop.uri not in widgets:
                continue

            widget = widgets[prop.uri]

            # Create label
            label_text = prop.display_name or prop.name
            if prop.is_required:
                label_text += " *"

            label = QLabel(label_text)

            # Add to form layout
            form_layout.addRow(label, widget)

            # Create FormField
            form_fields[prop.uri] = FormField(
                widget=widget,
                property_uri=prop.uri,
                property_metadata=prop,
                group_name=group_name,
                required=prop.is_required,
                label=label_text,
                label_widget=label
            )

        return group_box, form_fields

    def _format_group_name(self, group_name: str) -> str:
        """
        Format group name for display.

        Converts camelCase or snake_case to Title Case with spaces.

        Args:
            group_name: Raw group name

        Returns:
            Formatted group name
        """
        # Handle camelCase
        import re
        formatted = re.sub(r'([a-z])([A-Z])', r'\1 \2', group_name)

        # Handle snake_case
        formatted = formatted.replace('_', ' ')

        # Title case
        return formatted.title()
