"""Writes class individuals (User, Material, Equipment, etc.) to TTL files."""

import logging
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime

from rdflib import Graph, Namespace, RDF, RDFS, OWL, Literal, URIRef
from rdflib.namespace import XSD

from ...ontology import OntologyManager

logger = logging.getLogger(__name__)


class IndividualWriter:
    """
    Writes NamedIndividuals to TTL files with proper RDF structure.
    Unlike InstanceWriter (which overwrites), this appends to existing files.
    """

    def __init__(self, ontology_manager: OntologyManager):
        """
        Args:
            ontology_manager: OntologyManager instance
        """
        self.ontology_manager = ontology_manager

        # Define namespaces
        self.DYN = Namespace("https://dynamat.utep.edu/ontology#")
        self.GUI = Namespace("https://dynamat.utep.edu/ontology/gui#")

    def write_individual(
        self,
        class_uri: str,
        individual_uri: str,
        form_data: Dict[str, Any],
        output_path: Path
    ) -> Path:
        """
        Write individual to TTL file (append mode).

        Args:
            class_uri: Class URI (e.g., "dyn:User", "dyn:Material")
            individual_uri: URI for the individual (e.g., "dyn:User_JohnDoe")
            form_data: Dictionary of property values from form
            output_path: Path to output file

        Returns:
            Path to saved file

        Raises:
            ValueError: If individual already exists in file
            IOError: If file write fails
        """
        try:
            logger.info(f"Writing individual {individual_uri} to {output_path}")

            # Create RDF graph for new individual
            new_graph = Graph()
            self._bind_namespaces(new_graph)

            # Convert URIs to proper format
            individual_ref = self._uri_to_ref(individual_uri)
            class_ref = self._uri_to_ref(class_uri)

            # Add core triples: individual is a NamedIndividual and instance of class
            new_graph.add((individual_ref, RDF.type, OWL.NamedIndividual))
            new_graph.add((individual_ref, RDF.type, class_ref))

            logger.debug(f"Adding {len(form_data)} properties to individual")

            # Add properties from form data
            for prop_uri, value in form_data.items():
                if value is None or value == "":
                    continue  # Skip empty values

                try:
                    self._add_property_triple(new_graph, individual_ref, prop_uri, value)
                except Exception as e:
                    logger.warning(f"Failed to add property {prop_uri}: {e}")
                    continue

            # Load existing file if it exists
            existing_graph = Graph()
            if output_path.exists():
                logger.debug(f"Loading existing file: {output_path}")
                existing_graph.parse(output_path, format='turtle')

                # Check for duplicate URI
                if (individual_ref, RDF.type, OWL.NamedIndividual) in existing_graph:
                    raise ValueError(
                        f"Individual {individual_uri} already exists in {output_path}. "
                        "Please use a different name or load and edit the existing individual."
                    )

            # Merge graphs
            for triple in new_graph:
                existing_graph.add(triple)

            # Ensure output directory exists
            output_path.parent.mkdir(parents=True, exist_ok=True)

            # Serialize entire graph back to file
            logger.debug(f"Serializing graph with {len(existing_graph)} triples")
            existing_graph.serialize(output_path, format='turtle')

            logger.info(f"Successfully wrote individual to {output_path}")
            return output_path

        except Exception as e:
            logger.error(f"Failed to write individual: {e}", exc_info=True)
            raise

    def _bind_namespaces(self, graph: Graph):
        """Bind common namespaces to graph."""
        graph.bind("dyn", self.DYN)
        graph.bind("gui", self.GUI)
        graph.bind("rdf", RDF)
        graph.bind("rdfs", RDFS)
        graph.bind("owl", OWL)
        graph.bind("xsd", XSD)

    def _uri_to_ref(self, uri: str) -> URIRef:
        """Convert URI string (prefixed or full) to RDFLib URIRef."""
        if uri.startswith("dyn:"):
            local_name = uri.replace("dyn:", "")
            return self.DYN[local_name]
        elif uri.startswith("https://dynamat.utep.edu/ontology#"):
            return URIRef(uri)
        elif ":" in uri and not uri.startswith("http"):
            # Prefixed URI, try to resolve
            prefix, local = uri.split(":", 1)
            if prefix == "rdfs":
                return RDFS[local]
            elif prefix == "rdf":
                return RDF[local]
            else:
                return URIRef(uri)
        else:
            return URIRef(uri)

    def _add_property_triple(
        self,
        graph: Graph,
        subject: URIRef,
        prop_uri: str,
        value: Any
    ):
        """Add a property triple to the graph, handling different value types."""
        prop_ref = self._uri_to_ref(prop_uri)

        if isinstance(value, str) and (value.startswith("dyn:") or value.startswith("http")):
            value_ref = self._uri_to_ref(value)
            graph.add((subject, prop_ref, value_ref))
            logger.debug(f"Added object property: {prop_uri} -> {value}")

        elif isinstance(value, bool):
            graph.add((subject, prop_ref, Literal(value, datatype=XSD.boolean)))
            logger.debug(f"Added boolean property: {prop_uri} -> {value}")

        elif isinstance(value, int):
            graph.add((subject, prop_ref, Literal(value, datatype=XSD.integer)))
            logger.debug(f"Added integer property: {prop_uri} -> {value}")

        elif isinstance(value, float):
            graph.add((subject, prop_ref, Literal(value, datatype=XSD.double)))
            logger.debug(f"Added double property: {prop_uri} -> {value}")

        elif isinstance(value, datetime):
            graph.add((subject, prop_ref, Literal(value.isoformat(), datatype=XSD.dateTime)))
            logger.debug(f"Added dateTime property: {prop_uri} -> {value}")

        else:
            graph.add((subject, prop_ref, Literal(str(value), datatype=XSD.string)))
            logger.debug(f"Added string property: {prop_uri} -> {value}")

    def update_individual(
        self,
        individual_uri: str,
        form_data: Dict[str, Any],
        output_path: Path
    ) -> Path:
        """
        Update an existing individual by replacing its property triples.

        Args:
            individual_uri: URI of individual to update
            form_data: New property values
            output_path: Path to TTL file

        Returns:
            Path to saved file
        """
        try:
            logger.info(f"Updating individual {individual_uri}")

            if not output_path.exists():
                raise FileNotFoundError(f"File not found: {output_path}")

            # Load existing graph
            graph = Graph()
            graph.parse(output_path, format='turtle')

            individual_ref = self._uri_to_ref(individual_uri)

            # Remove all triples where this individual is the subject
            # (except rdf:type triples - we keep those)
            triples_to_remove = []
            for s, p, o in graph.triples((individual_ref, None, None)):
                if p != RDF.type:
                    triples_to_remove.append((s, p, o))

            for triple in triples_to_remove:
                graph.remove(triple)

            logger.debug(f"Removed {len(triples_to_remove)} old triples")

            # Add new properties
            for prop_uri, value in form_data.items():
                if value is None or value == "":
                    continue

                try:
                    self._add_property_triple(graph, individual_ref, prop_uri, value)
                except Exception as e:
                    logger.warning(f"Failed to add property {prop_uri}: {e}")

            graph.serialize(output_path, format='turtle')

            logger.info(f"Successfully updated individual {individual_uri}")
            return output_path

        except Exception as e:
            logger.error(f"Failed to update individual: {e}", exc_info=True)
            raise

    def delete_individual(
        self,
        individual_uri: str,
        output_path: Path
    ) -> bool:
        """
        Delete an individual from the TTL file.

        Args:
            individual_uri: URI of individual to delete
            output_path: Path to TTL file

        Returns:
            True if deleted, False if individual not found
        """
        try:
            logger.info(f"Deleting individual {individual_uri}")

            if not output_path.exists():
                raise FileNotFoundError(f"File not found: {output_path}")

            # Load existing graph
            graph = Graph()
            graph.parse(output_path, format='turtle')

            individual_ref = self._uri_to_ref(individual_uri)

            # Remove all triples where this individual is the subject
            triples_to_remove = list(graph.triples((individual_ref, None, None)))

            if not triples_to_remove:
                logger.warning(f"Individual {individual_uri} not found in file")
                return False

            for triple in triples_to_remove:
                graph.remove(triple)

            logger.debug(f"Removed {len(triples_to_remove)} triples")

            graph.serialize(output_path, format='turtle')

            logger.info(f"Successfully deleted individual {individual_uri}")
            return True

        except Exception as e:
            logger.error(f"Failed to delete individual: {e}", exc_info=True)
            raise
