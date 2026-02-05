"""
Extended form builder supporting custom group builders.

This module provides CustomizableFormBuilder, which extends the standard
form building with the ability to register custom GroupBuilder instances
for specific form groups, enabling group-specific rendering logic.
"""

from typing import Dict, Optional
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QScrollArea

from ...ontology import OntologyManager
from ..core.form_manager import FormManager
from .group_builder import GroupBuilder
from .default_group_builder import DefaultGroupBuilder


class CustomizableFormBuilder:
    """
    Extended form builder supporting custom group builders.

    This builder allows registering custom GroupBuilder instances for specific
    form groups, enabling custom rendering, intermediate widget injection, and
    group-specific behavior while maintaining ontology-driven form generation.

    Example:
        >>> builder = CustomizableFormBuilder(ontology_manager)
        >>> builder.register_group_builder(
        ...     "EquipmentConfiguration",
        ...     EquipmentPropertiesGroupBuilder(builder.widget_factory)
        ... )
        >>> form = builder.build_form("dyn:SHPBTestingConfiguration")

    Attributes:
        ontology_manager: OntologyManager instance
        form_manager: FormManager instance for widget creation
    """

    def __init__(self, ontology_manager: OntologyManager):
        """
        Initialize the customizable form builder.

        Args:
            ontology_manager: OntologyManager instance
        """
        self.ontology_manager = ontology_manager
        self.form_manager = FormManager(ontology_manager)
        self._group_builders: Dict[str, GroupBuilder] = {}
        self._default_builder: Optional[GroupBuilder] = None

    @property
    def widget_factory(self):
        """Get the widget factory from the form manager."""
        return self.form_manager.widget_factory

    def register_group_builder(self, group_name: str, builder: GroupBuilder):
        """
        Register a custom builder for a specific form group.

        When building a form, if a custom builder is registered for a group,
        it will be used instead of the default builder.

        Args:
            group_name: Name of the form group (must match gui:hasFormGroup value)
            builder: GroupBuilder instance to use for this group
        """
        self._group_builders[group_name] = builder

    def unregister_group_builder(self, group_name: str):
        """
        Remove a custom builder registration.

        Args:
            group_name: Name of the form group to unregister
        """
        self._group_builders.pop(group_name, None)

    def build_form(self, class_uri: str, parent: Optional[QWidget] = None) -> QWidget:
        """
        Build a form with custom group builders where registered.

        This method:
        1. Gets metadata from ontology manager
        2. Creates default builder if needed
        3. For each form group, uses custom builder if registered, else default
        4. Returns complete form widget

        Args:
            class_uri: URI of the class to build form for
            parent: Optional parent widget

        Returns:
            QWidget containing the complete form with all groups
        """
        # Get class metadata from ontology
        metadata = self.ontology_manager.get_class_metadata_for_form(class_uri)

        # Create default builder if needed
        if self._default_builder is None:
            self._default_builder = DefaultGroupBuilder(self.widget_factory)

        # Build form with custom builders
        return self._build_grouped_form(metadata.form_groups, parent)

    def _build_grouped_form(
        self,
        form_groups: Dict[str, list],
        parent: Optional[QWidget] = None
    ) -> QWidget:
        """
        Build grouped form using custom builders where registered.

        Args:
            form_groups: Dict mapping group names to property lists
            parent: Optional parent widget

        Returns:
            QWidget containing the complete form
        """
        # Create main form widget
        form_widget = QWidget(parent)
        layout = QVBoxLayout(form_widget)
        layout.setContentsMargins(0, 0, 0, 0)

        # Create scroll area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        content_layout = QVBoxLayout(content)

        # Track all form fields
        all_form_fields = {}

        # Get ordered groups (by group_order from first property in each group)
        ordered_groups = self._get_ordered_groups(form_groups)

        # Build each group with appropriate builder
        for group_name in ordered_groups:
            properties = form_groups[group_name]

            # Get custom builder if registered, else use default
            builder = self._group_builders.get(group_name, self._default_builder)

            # Build group
            group_widget, group_form_fields = builder.build_group(
                group_name, properties, content
            )

            # Add to layout
            content_layout.addWidget(group_widget)
            all_form_fields.update(group_form_fields)

        # Add stretch at bottom
        content_layout.addStretch()

        # Set up scroll area
        scroll.setWidget(content)
        layout.addWidget(scroll)

        # Attach form fields to widget for data extraction
        form_widget.form_fields = all_form_fields

        return form_widget

    def _get_ordered_groups(self, form_groups: Dict[str, list]) -> list:
        """
        Get form groups ordered by group_order.

        Args:
            form_groups: Dict mapping group names to property lists

        Returns:
            List of group names in display order
        """
        # Get group order from first property in each group
        group_orders = {}
        for group_name, properties in form_groups.items():
            if properties:
                # Use group_order from first property
                group_orders[group_name] = properties[0].group_order or 0

        # Sort by group order
        return sorted(form_groups.keys(), key=lambda g: group_orders.get(g, 0))

    def get_form_data(self, form_widget: QWidget) -> Dict[str, any]:
        """
        Extract data from form widget.

        This is a convenience method that delegates to FormManager.

        Args:
            form_widget: Form widget created by build_form()

        Returns:
            Dict mapping property URIs to values
        """
        return self.form_manager.get_form_data(form_widget)

    def set_form_data(self, form_widget: QWidget, data: Dict[str, any]):
        """
        Populate form with data.

        This is a convenience method that delegates to FormManager.

        Args:
            form_widget: Form widget created by build_form()
            data: Dict mapping property URIs to values
        """
        self.form_manager.set_form_data(form_widget, data)

    def validate_form(self, form_widget: QWidget) -> Dict[str, list]:
        """
        Validate form data and return errors.

        This is a convenience method that delegates to FormManager.

        Args:
            form_widget: Form widget created by build_form()

        Returns:
            Dictionary mapping property URIs to lists of error messages
        """
        return self.form_manager.validate_form(form_widget)
