"""Round-trip tests for QuantityValue serialization and deserialization.

Verifies that measurement values survive a write → read cycle via
InstanceWriter (serialization) and InstanceQueryBuilder (deserialization).
"""

import pytest
from pathlib import Path

from rdflib import Graph, Namespace, BNode, URIRef
from rdflib.namespace import RDF, XSD

from dynamat.gui.parsers.instance_writer import InstanceWriter
from dynamat.ontology.instance_query_builder import InstanceQueryBuilder

QUDT = Namespace("http://qudt.org/schema/qudt/")
DYN = Namespace("https://dynamat.utep.edu/ontology#")
UNIT = Namespace("http://qudt.org/vocab/unit/")
QKDV = Namespace("http://qudt.org/vocab/quantitykind/")


class TestQuantityValueRoundTrip:
    """Verify QuantityValue write → read round-trip preserves data."""

    @pytest.fixture
    def writer(self, ontology_manager):
        return InstanceWriter(ontology_manager)

    @pytest.fixture
    def query_builder(self, ontology_manager):
        return InstanceQueryBuilder(ontology_manager)

    # ------------------------------------------------------------------
    # Serialization tests
    # ------------------------------------------------------------------

    def test_serialize_basic_quantity_value(self, writer):
        """A basic measurement produces a valid QuantityValue blank node."""
        graph = Graph()
        writer._setup_namespaces(graph)

        value_dict = {
            'value': 6.35,
            'unit': 'unit:MilliM',

            'quantity_kind': 'qkdv:Length',
        }
        bnode = writer._create_quantity_value(graph, value_dict)

        # Check blank node type
        assert (bnode, RDF.type, QUDT.QuantityValue) in graph

        # Check numeric value
        values = list(graph.objects(bnode, QUDT.numericValue))
        assert len(values) == 1
        assert float(values[0]) == pytest.approx(6.35)

        # Check unit
        units = list(graph.objects(bnode, QUDT.unit))
        assert len(units) == 1
        assert str(units[0]).endswith("MilliM")

        # Check quantity kind
        qks = list(graph.objects(bnode, QUDT.hasQuantityKind))
        assert len(qks) == 1
        assert "Length" in str(qks[0])

    def test_serialize_with_uncertainty(self, writer):
        """Uncertainty is serialized when provided."""
        graph = Graph()
        writer._setup_namespaces(graph)

        value_dict = {
            'value': 6.35,
            'unit': 'unit:MilliM',

            'quantity_kind': 'qkdv:Length',
            'uncertainty': 0.01,
        }
        bnode = writer._create_quantity_value(graph, value_dict)

        unc_values = list(graph.objects(bnode, QUDT.standardUncertainty))
        assert len(unc_values) == 1
        assert float(unc_values[0]) == pytest.approx(0.01)

    def test_serialize_without_uncertainty(self, writer):
        """No uncertainty triple when uncertainty is None."""
        graph = Graph()
        writer._setup_namespaces(graph)

        value_dict = {
            'value': 10.0,
            'unit': 'unit:MilliM',

        }
        bnode = writer._create_quantity_value(graph, value_dict)

        unc_values = list(graph.objects(bnode, QUDT.standardUncertainty))
        assert len(unc_values) == 0

    def test_create_single_instance_routes_measurement_dict(self, writer):
        """create_single_instance correctly detects measurement dicts."""
        graph = Graph()
        writer._setup_namespaces(graph)

        form_data = {
            'dyn:hasOriginalDiameter': {
                'value': 6.35,
                'unit': 'unit:MilliM',
    
                'quantity_kind': 'qkdv:Length',
                'uncertainty': 0.02,
            },
            'dyn:hasSpecimenID': 'TEST-001',
        }

        instance_ref = writer.create_single_instance(
            graph, form_data, 'dyn:Specimen', 'TEST-001'
        )

        # String property
        ids = list(graph.objects(instance_ref, DYN.hasSpecimenID))
        assert len(ids) == 1
        assert str(ids[0]) == 'TEST-001'

        # QuantityValue property
        diameter_objs = list(graph.objects(instance_ref, DYN.hasOriginalDiameter))
        assert len(diameter_objs) == 1
        bnode = diameter_objs[0]
        assert isinstance(bnode, BNode)
        assert (bnode, RDF.type, QUDT.QuantityValue) in graph

    # ------------------------------------------------------------------
    # Deserialization tests
    # ------------------------------------------------------------------

    def test_extract_quantity_value_basic(self):
        """_extract_quantity_value reads numericValue, unit, and quantityKind."""
        graph = Graph()
        bnode = BNode()
        graph.add((bnode, RDF.type, QUDT.QuantityValue))
        graph.add((bnode, QUDT.numericValue,
                   graph.namespace_manager.store.value(6.35, XSD.double)
                   if False else __import__('rdflib').Literal(6.35, datatype=XSD.double)))
        graph.add((bnode, QUDT.unit, UNIT.MilliM))
        graph.add((bnode, QUDT.hasQuantityKind, QKDV.Length))

        result = InstanceQueryBuilder._extract_quantity_value(graph, bnode)

        assert result['value'] == pytest.approx(6.35)
        assert 'MilliM' in result['unit']
        assert 'Length' in result['quantity_kind']
        assert result['pattern'] == 'quantity_value'

    def test_extract_quantity_value_with_uncertainty(self):
        """_extract_quantity_value reads standardUncertainty."""
        from rdflib import Literal
        graph = Graph()
        bnode = BNode()
        graph.add((bnode, RDF.type, QUDT.QuantityValue))
        graph.add((bnode, QUDT.numericValue, Literal(6.35, datatype=XSD.double)))
        graph.add((bnode, QUDT.unit, UNIT.MilliM))
        graph.add((bnode, QUDT.standardUncertainty, Literal(0.01, datatype=XSD.double)))

        result = InstanceQueryBuilder._extract_quantity_value(graph, bnode)

        assert result.get('uncertainty') == pytest.approx(0.01)

    def test_extract_quantity_value_with_provenance(self):
        """_extract_quantity_value reads dc:source and prov:wasGeneratedBy."""
        from rdflib import Literal
        PROV = Namespace("http://www.w3.org/ns/prov#")
        DC = Namespace("http://purl.org/dc/elements/1.1/")

        graph = Graph()
        bnode = BNode()
        graph.add((bnode, RDF.type, QUDT.QuantityValue))
        graph.add((bnode, QUDT.numericValue, Literal(68.9, datatype=XSD.double)))
        graph.add((bnode, QUDT.unit, UNIT.GigaPA))
        graph.add((bnode, DC.source, Literal("ASM Handbook Vol 2")))
        graph.add((bnode, PROV.wasGeneratedBy, DYN.SHPBTest_AL6061_2024))

        result = InstanceQueryBuilder._extract_quantity_value(graph, bnode)

        assert result.get('source') == "ASM Handbook Vol 2"
        assert 'SHPBTest_AL6061_2024' in result.get('activity', '')

    # ------------------------------------------------------------------
    # Full round-trip: write → serialize → parse → extract
    # ------------------------------------------------------------------

    def test_full_round_trip(self, writer, query_builder, tmp_path):
        """Write a specimen, save to TTL, reload, and verify values."""
        form_data = {
            'dyn:hasSpecimenID': 'ROUND-TRIP-001',
            'dyn:hasOriginalDiameter': {
                'value': 6.35,
                'unit': 'unit:MilliM',
    
                'quantity_kind': 'qkdv:Length',
                'uncertainty': 0.02,
            },
            'dyn:hasOriginalHeight': {
                'value': 4.5,
                'unit': 'unit:MilliM',
    
                'quantity_kind': 'qkdv:Length',
            },
        }

        # Write
        output = tmp_path / "round_trip_specimen.ttl"
        saved_path, result = writer.write_instance(
            form_data, 'dyn:Specimen', 'ROUND_TRIP_001', output,
            skip_validation=True,
        )
        assert saved_path is not None

        # Read back
        specimen_dir = tmp_path
        query_builder.scan_and_index(
            specimen_dir,
            "https://dynamat.utep.edu/ontology#Specimen",
            file_pattern="round_trip_specimen.ttl",
        )

        instances = query_builder.find_all_instances(
            "https://dynamat.utep.edu/ontology#Specimen"
        )
        assert len(instances) >= 1

        # Load full data
        instance_uri = instances[0].get('uri')
        data = query_builder.load_full_instance_data(instance_uri)

        # Verify QuantityValue round-trip
        diameter = data.get(str(DYN.hasOriginalDiameter))
        assert diameter is not None
        assert isinstance(diameter, dict)
        assert diameter['value'] == pytest.approx(6.35)
        assert 'MilliM' in diameter.get('unit', '')
        assert diameter.get('pattern') == 'quantity_value'

        # Uncertainty round-trip
        assert diameter.get('uncertainty') == pytest.approx(0.02)

        # Height (no uncertainty)
        height = data.get(str(DYN.hasOriginalHeight))
        assert height is not None
        assert height['value'] == pytest.approx(4.5)


class TestExtractNumericValue:
    """Tests for the extract_numeric_value utility."""

    def test_dict_input(self):
        from dynamat.mechanical.shpb.io.rdf_helpers import extract_numeric_value
        assert extract_numeric_value({'value': 6.35, 'unit': 'mm'}) == pytest.approx(6.35)

    def test_float_input(self):
        from dynamat.mechanical.shpb.io.rdf_helpers import extract_numeric_value
        assert extract_numeric_value(6.35) == pytest.approx(6.35)

    def test_int_input(self):
        from dynamat.mechanical.shpb.io.rdf_helpers import extract_numeric_value
        assert extract_numeric_value(10) == pytest.approx(10.0)

    def test_string_number(self):
        from dynamat.mechanical.shpb.io.rdf_helpers import extract_numeric_value
        assert extract_numeric_value("6.35") == pytest.approx(6.35)

    def test_none_input(self):
        from dynamat.mechanical.shpb.io.rdf_helpers import extract_numeric_value
        assert extract_numeric_value(None) is None

    def test_non_numeric_string(self):
        from dynamat.mechanical.shpb.io.rdf_helpers import extract_numeric_value
        assert extract_numeric_value("not a number") is None

    def test_dict_without_value_key(self):
        from dynamat.mechanical.shpb.io.rdf_helpers import extract_numeric_value
        assert extract_numeric_value({'unit': 'mm'}) is None
