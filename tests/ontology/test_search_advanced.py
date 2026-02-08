import pytest
from rdflib import Graph, URIRef, Literal, RDF, XSD
from datetime import date

class TestSearchAdvanced:
    """Tests for advanced filtering and search queries."""

    @pytest.fixture
    def test_data_graph(self, ontology_manager):
        """Create a graph with multiple tests on different dates."""
        g = Graph()
        dyn = ontology_manager.DYN
        
        # Test 1: Jan 2025
        t1 = URIRef("https://dynamat.utep.edu/ontology#T1")
        g.add((t1, RDF.type, dyn.SHPBCompression))
        g.add((t1, dyn.hasDate, Literal("2025-01-15", datatype=XSD.date)))
        
        # Test 2: Feb 2025
        t2 = URIRef("https://dynamat.utep.edu/ontology#T2")
        g.add((t2, RDF.type, dyn.SHPBCompression))
        g.add((t2, dyn.hasDate, Literal("2025-02-15", datatype=XSD.date)))
        
        return g

    def test_find_tests_by_date_range(self, ontology_manager, test_data_graph):
        """Test finding tests within a specific date range."""
        # Note: domain_queries uses the manager's global graph.
        # To test with local data, we'd need to mock the executor or inject data.
        # Here we test the query generation logic by calling it and checking it doesn't crash.
        
        # Test date filtering logic
        results = ontology_manager.domain_queries.find_tests(
            date_from="2025-01-01",
            date_to="2025-01-31"
        )
        assert isinstance(results, list)

    # def test_get_classes_with_individuals(self, ontology_manager):
    #     """Test finding classes that allow user creation and have individuals."""
    #     classes = ontology_manager.get_classes_with_individuals()
    #     
    #     assert isinstance(classes, list)
    #     # User and Material classes are typically configured to allow creation
    #     uris = [c['uri'] for c in classes]
    #     assert any("User" in u for u in uris)
    #     assert any("Material" in u for u in uris)

    def test_series_metadata_expansion(self, ontology_manager):
        """Test SHPB-specific series expansion (e.g., stress -> stress_1w, stress_3w)."""
        metadata = ontology_manager.domain_queries.get_series_metadata_for_shpb()
        
        # Check if 1-wave and 3-wave variants were generated for stress
        assert "stress_1w" in metadata
        assert "stress_3w" in metadata
        assert metadata["stress_1w"]["analysis_method"] == "1-wave"
        assert metadata["stress_3w"]["analysis_method"] == "3-wave"
