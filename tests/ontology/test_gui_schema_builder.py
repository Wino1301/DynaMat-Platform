import pytest
from dynamat.ontology.schema.gui_schema_builder import PropertyMetadata, ClassMetadata

class TestGUISchemaBuilder:
    """Tests for the GUISchemaBuilder and form metadata generation."""

    def test_get_class_metadata(self, ontology_manager):
        """Test retrieving metadata for a specific class (Specimen)."""
        # Use the namespaced URI
        class_uri = str(ontology_manager.DYN.Specimen)
        metadata = ontology_manager.get_class_metadata_for_form(class_uri)

        assert isinstance(metadata, ClassMetadata)
        assert metadata.uri == class_uri
        assert metadata.label == "Specimen"
        assert len(metadata.properties) > 0
        assert len(metadata.form_groups) > 0

    def test_property_metadata_inference(self, ontology_manager):
        """Test that property metadata (widgets, types) is inferred correctly."""
        class_uri = str(ontology_manager.DYN.Specimen)
        metadata = ontology_manager.get_class_metadata_for_form(class_uri)

        # Find a measurement property (e.g., Original Length)
        length_prop = next((p for p in metadata.properties if "OriginalLength" in p.name), None)
        assert length_prop is not None
        assert length_prop.data_type == "double"
        assert length_prop.is_measurement_property is True
        assert length_prop.default_unit is not None
        assert "unit:MilliM" in length_prop.default_unit

    def test_form_grouping(self, ontology_manager):
        """Test that properties are correctly organized into groups."""
        class_uri = str(ontology_manager.DYN.Specimen)
        metadata = ontology_manager.get_class_metadata_for_form(class_uri)

        # Check for standard groups defined in specimen_class.ttl
        group_names = metadata.form_groups.keys()
        assert "Identification" in group_names
        assert "GeometryDimensions" in group_names
        
        # Check ordering
        groups = metadata.get_ordered_groups()
        # Identification should generally be first or near top
        assert "Identification" in groups[:2]
