import pytest
from dynamat.ontology.manager import OntologyManager

class TestOntologyManager:
    """Tests for the central OntologyManager."""

    def test_initialization(self, ontology_manager):
        """Test that the manager initializes and loads the graph."""
        assert ontology_manager.graph is not None
        assert len(ontology_manager.graph) > 0
        assert ontology_manager.loader.is_loaded()

    def test_namespace_access(self, ontology_manager):
        """Test access to common namespaces."""
        assert str(ontology_manager.DYN) == "https://dynamat.utep.edu/ontology#"
        assert "qudt" in ontology_manager.namespaces

    def test_get_all_classes(self, ontology_manager):
        """Test retrieving all classes from the ontology."""
        classes = ontology_manager.get_all_classes()
        assert len(classes) > 0
        assert any("Specimen" in c for c in classes)

    def test_get_statistics(self, ontology_manager):
        """Test that statistics are reported correctly."""
        stats = ontology_manager.get_statistics()
        assert "configuration" in stats
        assert "execution" in stats
        assert "health" in stats
        assert stats["health"]["components"]["loader_ready"] is True
        assert stats["health"]["components"]["graph_initialized"] is True
