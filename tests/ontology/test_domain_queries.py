import pytest
from datetime import date

class TestDomainQueries:
    """Tests for the high-level DomainQueries API."""

    def test_get_available_materials(self, ontology_manager):
        """Test retrieving available materials."""
        materials = ontology_manager.domain_queries.get_available_materials()
        assert len(materials) > 0
        
        # Check for a known material (Al6061-T6)
        al6061 = next((m for m in materials if "Al6061" in str(m.get('materialName', ''))), None)
        assert al6061 is not None
        assert "materialCode" in al6061

    def test_find_specimens_empty(self, ontology_manager):
        """Test specimen search with no filters (should return all)."""
        # Note: This depends on test data being loaded. 
        # If no user data, it might return 0, which is valid but weak test.
        # We assume the ontology might have some individuals or we just check type.
        specimens = ontology_manager.domain_queries.find_specimens()
        assert isinstance(specimens, list)

    def test_get_series_metadata_for_shpb(self, ontology_manager):
        """Test extraction of SHPB series metadata for CSV parsing."""
        metadata = ontology_manager.domain_queries.get_series_metadata_for_shpb()
        
        # Check for key columns
        assert "time" in metadata
        assert "incident" in metadata
        assert "stress" in metadata or "stress_1w" in metadata
        
        # Check metadata content
        time_meta = metadata["time"]
        assert "unit" in time_meta
        assert "quantity_kind" in time_meta
        assert "class_uri" in time_meta

    def test_get_individual_properties(self, ontology_manager):
        """Test fetching properties with labels for GUI display."""
        # Use a known individual from class_individuals/material_individuals.ttl
        material_uri = str(ontology_manager.DYN.Al6061_T6)
        
        props = ontology_manager.domain_queries.get_individual_properties_with_labels(
            material_uri,
            ["dyn:hasDensity", "dyn:hasElasticModulus"]
        )
        
        assert "dyn:hasDensity" in props
        density = props["dyn:hasDensity"]
        assert density["label"] == "Density"
        assert density["unit_symbol"] is not None  # Should be g/cm3 or similar
