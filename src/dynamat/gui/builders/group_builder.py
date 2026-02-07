"""
Abstract base class for building form groups from property metadata.

This module provides the GroupBuilder interface that allows custom rendering
of form groups, enabling intermediate widget injection and group-specific
customization while maintaining ontology-driven form generation.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Tuple, Optional
from PyQt6.QtWidgets import QWidget

from ...ontology import PropertyMetadata
from ..core.form_manager import FormField


class GroupBuilder(ABC):
    """
    Abstract base class for building form groups from property metadata.

    GroupBuilders control how a form group is rendered, allowing custom layouts,
    intermediate display widgets, and group-specific behavior while still using
    the ontology-defined properties as the source of truth.

    Attributes:
        widget_factory: Factory for creating widgets from property metadata
    """

    def __init__(self, widget_factory):
        """
        Initialize the group builder.

        Args:
            widget_factory: WidgetFactory instance for creating widgets
        """
        self.widget_factory = widget_factory

    @abstractmethod
    def build_group(
        self,
        group_name: str,
        properties: List[PropertyMetadata],
        parent: Optional[QWidget] = None
    ) -> Tuple[QWidget, Dict[str, FormField]]:
        """
        Build complete group widget with fields and any intermediate displays.

        This method must:
        1. Create a container widget for the group
        2. Create widgets for the provided properties using the widget factory
        3. Arrange widgets in the desired layout
        4. Optionally add intermediate display widgets (calculations, derived values, etc.)
        5. Return the complete group widget and a dict of FormFields

        Args:
            group_name: Name of the form group (from gui:hasFormGroup)
            properties: List of PropertyMetadata for this group
            parent: Optional parent widget

        Returns:
            Tuple of (group_widget, form_fields_dict) where:
                - group_widget: Complete QWidget containing the group
                - form_fields_dict: Dict mapping property URIs to FormField objects
        """
        pass

    def create_widgets_for_group(
        self,
        properties: List[PropertyMetadata],
        parent: Optional[QWidget] = None
    ) -> Dict[str, QWidget]:
        """
        Helper method to create widgets for group properties.

        This is a convenience method that subclasses can use to create widgets
        for all properties in a group using the widget factory.

        Args:
            properties: List of PropertyMetadata to create widgets for
            parent: Optional parent widget

        Returns:
            Dict mapping property URIs to created widgets
        """
        widgets = {}
        for prop in properties:
            widget = self.widget_factory.create_widget(prop)
            if widget is not None:
                widgets[prop.uri] = widget
        return widgets
