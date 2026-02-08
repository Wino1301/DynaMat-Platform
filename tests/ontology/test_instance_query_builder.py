import pytest
from pathlib import Path
from dynamat.ontology.instance_query_builder import InstanceQueryBuilder

class TestInstanceQueryBuilder:
    """Tests for InstanceQueryBuilder indexing and searching."""

    @pytest.fixture
    def query_builder(self, ontology_manager):
        return InstanceQueryBuilder(ontology_manager)

    @pytest.fixture
    def sample_data_dir(self, tmp_path):
        """Create a temporary directory with sample TTL files."""
        # Create a specimen directory
        specimen_dir = tmp_path / "specimens" / "SPN-TEST-001"
        specimen_dir.mkdir(parents=True)
        
        # Create a dummy specimen TTL
        ttl_content = """
        @prefix dyn: <https://dynamat.utep.edu/ontology#> .
        @prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
        @prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

        dyn:SPN-TEST-001 rdf:type dyn:Specimen ;
            dyn:hasSpecimenID "SPN-TEST-001" ;
            dyn:hasMaterialName "Test Material" ;
            dyn:hasOriginalDiameter "10.0"^^xsd:double .
        """
        (specimen_dir / "specimen.ttl").write_text(ttl_content)
        
        return tmp_path / "specimens"

    def test_scan_and_index(self, query_builder, sample_data_dir):
        """Test scanning a directory and indexing instances."""
        count = query_builder.scan_and_index(
            sample_data_dir, 
            "https://dynamat.utep.edu/ontology#Specimen"
        )
        assert count == 1

    def test_find_instances(self, query_builder, sample_data_dir):
        """Test finding indexed instances."""
        query_builder.scan_and_index(
            sample_data_dir, 
            "https://dynamat.utep.edu/ontology#Specimen"
        )
        
        instances = query_builder.find_all_instances(
            "https://dynamat.utep.edu/ontology#Specimen",
            display_properties=["https://dynamat.utep.edu/ontology#hasSpecimenID"]
        )
        
        assert len(instances) == 1
        assert instances[0]["https://dynamat.utep.edu/ontology#hasSpecimenID"] == "SPN-TEST-001"

    def test_lazy_loading(self, query_builder, sample_data_dir):
        """Test lazy loading of full instance data."""
        query_builder.scan_and_index(
            sample_data_dir, 
            "https://dynamat.utep.edu/ontology#Specimen"
        )
        
        # Find URI
        instances = query_builder.find_all_instances("https://dynamat.utep.edu/ontology#Specimen")
        uri = instances[0]["uri"]
        
        # Load full data
        data = query_builder.load_full_instance_data(uri)
        
        # Check property not in index but in file
        has_diameter_prop = "https://dynamat.utep.edu/ontology#hasOriginalDiameter"
        assert has_diameter_prop in data
        assert float(data[has_diameter_prop]) == 10.0
