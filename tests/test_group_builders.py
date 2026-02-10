"""
Tests for group builder architecture.

This module tests the new group-level widget creation architecture,
including GroupBuilder interface, DefaultGroupBuilder, and CustomizableFormBuilder.
"""

import pytest
from PyQt6.QtWidgets import QApplication, QGroupBox, QWidget, QLabel
import sys

from dynamat.ontology import OntologyManager, PropertyMetadata
from dynamat.gui.builders import (
    GroupBuilder, DefaultGroupBuilder, CustomizableFormBuilder
)
from dynamat.gui.core import WidgetFactory


# Ensure QApplication exists for widget tests
@pytest.fixture(scope="module")
def qapp():
    """Create QApplication for tests."""
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    yield app


@pytest.fixture
def ontology_manager():
    """Create OntologyManager for tests."""
    return OntologyManager()


@pytest.fixture
def widget_factory(ontology_manager):
    """Create WidgetFactory for tests."""
    return WidgetFactory(ontology_manager)


@pytest.fixture
def sample_properties():
    """Create sample PropertyMetadata for testing."""
    return [
        PropertyMetadata(
            uri="http://example.org#prop1",
            name="property1",
            display_name="Property 1",
            form_group="Test Group",
            display_order=1,
            group_order=1,
            data_type="http://www.w3.org/2001/XMLSchema#string",
            is_functional=False,
            is_required=True,
            valid_values=[],
            default_unit=None,
            range_class=None,
            domain_class="http://example.org#TestClass",
            description="A sample property for testing."
        ),
        PropertyMetadata(
            uri="http://example.org#prop2",
            name="property2",
            display_name="Property 2",
            form_group="Test Group",
            display_order=2,
            group_order=1,
            data_type="http://www.w3.org/2001/XMLSchema#double",
            is_functional=False,
            is_required=False,
            valid_values=[],
            default_unit=None,
            range_class=None,
            domain_class="http://example.org#TestClass",
            description="Another sample property for testing."
        ),
    ]


class TestDefaultGroupBuilder:
    """Tests for DefaultGroupBuilder."""

    def test_creates_qgroupbox(self, qapp, widget_factory, sample_properties):
        """Verify DefaultGroupBuilder creates QGroupBox with QFormLayout."""
        builder = DefaultGroupBuilder(widget_factory)
        group_widget, form_fields = builder.build_group(
            "TestGroup", sample_properties
        )

        assert isinstance(group_widget, QGroupBox)
        assert group_widget.title() == "Test Group"

    def test_creates_form_fields(self, qapp, widget_factory, sample_properties):
        """Verify DefaultGroupBuilder creates FormField for each property."""
        builder = DefaultGroupBuilder(widget_factory)
        group_widget, form_fields = builder.build_group(
            "TestGroup", sample_properties
        )

        assert len(form_fields) == len(sample_properties)
        for prop in sample_properties:
            assert prop.uri in form_fields

    def test_required_fields_marked(self, qapp, widget_factory, sample_properties):
        """Verify required fields are marked with asterisk."""
        builder = DefaultGroupBuilder(widget_factory)
        group_widget, form_fields = builder.build_group(
            "TestGroup", sample_properties
        )

        # First property is required
        required_field = form_fields["http://example.org#prop1"]
        assert "*" in required_field.label

        # Second property is not required
        optional_field = form_fields["http://example.org#prop2"]
        assert "*" not in optional_field.label

    def test_format_group_name(self, widget_factory):
        """Test group name formatting."""
        builder = DefaultGroupBuilder(widget_factory)

        assert builder._format_group_name("TestGroup") == "Test Group"
        assert builder._format_group_name("test_group") == "Test Group"
        assert builder._format_group_name("testGroup") == "Test Group"


class TestCustomizableFormBuilder:
    """Tests for CustomizableFormBuilder."""

    def test_builder_initialization(self, qapp, ontology_manager):
        """Verify CustomizableFormBuilder initializes correctly."""
        builder = CustomizableFormBuilder(ontology_manager)

        assert builder.ontology_manager is not None
        assert builder.form_manager is not None
        assert builder.widget_factory is not None

    def test_register_custom_builder(self, qapp, ontology_manager, widget_factory):
        """Verify custom builder registration."""
        builder = CustomizableFormBuilder(ontology_manager)
        custom_builder = DefaultGroupBuilder(widget_factory)

        builder.register_group_builder("CustomGroup", custom_builder)
        assert "CustomGroup" in builder._group_builders

    def test_unregister_custom_builder(self, qapp, ontology_manager, widget_factory):
        """Verify custom builder unregistration."""
        builder = CustomizableFormBuilder(ontology_manager)
        custom_builder = DefaultGroupBuilder(widget_factory)

        builder.register_group_builder("CustomGroup", custom_builder)
        builder.unregister_group_builder("CustomGroup")
        assert "CustomGroup" not in builder._group_builders


class CustomTestGroupBuilder(GroupBuilder):
    """Custom group builder for testing intermediate widget injection."""

    def build_group(self, group_name, properties, parent=None):
        """Build group with intermediate display widget."""
        container = QWidget(parent)

        # Create standard form
        widgets = self.create_widgets_for_group(properties, container)

        # Add intermediate display widget
        display_label = QLabel("Intermediate Display", container)
        container.display_label = display_label

        form_fields = {}
        for prop in properties:
            if prop.uri in widgets:
                from dynamat.gui.core.form_manager import FormField
                form_fields[prop.uri] = FormField(
                    widget=widgets[prop.uri],
                    property_uri=prop.uri,
                    property_metadata=prop,
                    group_name=group_name,
                    required=prop.is_required,
                    label=prop.display_name or prop.name
                )

        return container, form_fields


class TestCustomGroupBuilder:
    """Tests for custom GroupBuilder implementations."""

    def test_custom_builder_injects_widget(self, qapp, widget_factory, sample_properties):
        """Verify custom builder can inject intermediate widgets."""
        builder = CustomTestGroupBuilder(widget_factory)
        group_widget, form_fields = builder.build_group(
            "CustomGroup", sample_properties
        )

        # Verify intermediate display widget exists
        assert hasattr(group_widget, 'display_label')
        assert isinstance(group_widget.display_label, QLabel)
        assert group_widget.display_label.text() == "Intermediate Display"

        # Verify form fields still created
        assert len(form_fields) == len(sample_properties)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
