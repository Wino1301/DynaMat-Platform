import pytest

class TestOntologyInheritance:
    """Tests for property inheritance in form metadata."""

    def test_shpb_inheritance(self, ontology_manager):
        """Verify SHPBCompression inherits properties from parent classes."""
        class_uri = str(ontology_manager.DYN.SHPBCompression)
        metadata = ontology_manager.get_class_metadata_for_form(class_uri)
        
        prop_names = [p.name for p in metadata.properties]
        
        # 1. Properties from Entity (Base)
        # Note: hasName is abstract, check hasTestID instead (subPropertyOf hasName)
        assert "hasTestID" in prop_names
        
        # 2. Properties from Activity
        assert "hasUser" in prop_names
        assert "performedOn" in prop_names
        
        # 3. Properties from MechanicalTest
        assert "hasTestDate" in prop_names
        
        # 4. Properties from SHPBCompression (Specific)
        assert "hasStrikerVelocity" in prop_names
        assert "hasStrikerBar" in prop_names

    def test_specimen_inheritance(self, ontology_manager):
        """Verify Specimen inherits properties from PhysicalObject."""
        class_uri = str(ontology_manager.DYN.Specimen)
        metadata = ontology_manager.get_class_metadata_for_form(class_uri)
        
        prop_names = [p.name for p in metadata.properties]
        
        # hasMaterial is defined on Specimen/Batch
        assert "hasMaterial" in prop_names
        # hasSpecimenID is defined on Specimen
        assert "hasSpecimenID" in prop_names
