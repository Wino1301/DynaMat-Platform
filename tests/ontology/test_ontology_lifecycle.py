import pytest
import time

class TestOntologyLifecycle:
    """Tests for reloading, caching, and statistics integrity."""

    def test_reload_ontology(self, ontology_manager):
        """Test that reloading clears caches and re-initializes correctly."""
        # 1. Warm up the cache
        class_uri = str(ontology_manager.DYN.Specimen)
        ontology_manager.get_class_metadata_for_form(class_uri)
        assert ontology_manager.cache.get_cached_class_metadata(class_uri) is not None
        
        # 2. Perform reload
        ontology_manager.reload_ontology()
        
        # 3. Verify cache is empty
        assert ontology_manager.cache.get_cached_class_metadata(class_uri) is None
        
        # 4. Verify graph still works
        assert len(ontology_manager.graph) > 0
        assert ontology_manager.DYN.Specimen is not None

    def test_cache_hit_ratio(self, ontology_manager):
        """Test that the cache hit ratio accurately reflects usage."""
        ontology_manager.clear_caches()
        class_uri = str(ontology_manager.DYN.Material)
        
        # First call: Miss
        ontology_manager.get_class_metadata_for_form(class_uri)
        # Second call: Hit
        ontology_manager.get_class_metadata_for_form(class_uri)
        
        stats = ontology_manager.get_statistics()
        cache_ops = stats["execution"]["cache_operations"]
        
        assert cache_ops["cache_hit_ratio"] == 50.0  # 1 hit, 1 miss

    def test_statistics_completeness(self, ontology_manager):
        """Verify the unified statistics structure is fully populated."""
        stats = ontology_manager.get_statistics()
        
        keys = ["configuration", "execution", "health", "content", "components"]
        for key in keys:
            assert key in stats
            assert stats[key] is not None
        
        # Check specific nested content
        assert "total_triples" in stats["content"]["ontology_data"]
        assert stats["content"]["ontology_data"]["total_triples"] > 0
