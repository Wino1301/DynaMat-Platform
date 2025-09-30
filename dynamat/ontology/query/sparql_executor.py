"""
DynaMat Platform - SPARQL Executor
Handles low-level SPARQL query execution and result processing
Extracted from manager.py for better separation of concerns
"""

import logging
from typing import Dict, List, Optional, Any, Union
import time

from rdflib import Graph
from rdflib.plugins.sparql import prepareQuery

from ..core.namespace_manager import NamespaceManager

logger = logging.getLogger(__name__)


class SPARQLExecutor:
    """
    Handles SPARQL query execution and result processing.
    
    Responsibilities:
    - Execute SPARQL queries with proper namespaces
    - Handle query result processing
    - Manage query performance and logging
    - Provide utility methods for common query patterns
    """
    
    def __init__(self, graph: Graph, namespace_manager: NamespaceManager):
        """
        Initialize the SPARQL executor.
        
        Args:
            graph: RDF graph to query
            namespace_manager: Namespace manager for query prefixes
        """
        self.graph = graph
        self.namespace_manager = namespace_manager
        self._query_cache = {}  # Simple query cache
        
        logger.info("SPARQL executor initialized")
    
    def execute_query(self, query: str, bindings: Optional[Dict] = None, 
                     use_cache: bool = False) -> List[Dict[str, Any]]:
        """
        Execute a SPARQL query and return results.
        
        Args:
            query: SPARQL query string
            bindings: Optional variable bindings
            use_cache: Whether to cache the query results
            
        Returns:
            List of result dictionaries
        """
        start_time = time.time()
        
        # Check cache if enabled
        cache_key = None
        if use_cache:
            cache_key = hash(query + str(bindings or {}))
            if cache_key in self._query_cache:
                logger.debug(f"Query cache hit for key: {cache_key}")
                return self._query_cache[cache_key]
        
        try:
            # Add namespace prefixes to query
            prefixed_query = self._add_namespace_prefixes(query)
            
            # Prepare and execute query

            # DEBUG: Check namespaces before query preparation
            namespaces = self.namespace_manager.get_all_namespaces()
            
            # Check for None values
            none_keys = [k for k, v in namespaces.items() if k is None or v is None]
            if none_keys:
                # Filter out None values
                namespaces = {k: v for k, v in namespaces.items() if k is not None and v is not None}

            prepared = prepareQuery(prefixed_query, initNs=self.namespace_manager.get_all_namespaces())
            results = self.graph.query(prepared, initBindings=bindings or {})
            
            # Process results
            processed_results = self._process_query_results(results)
            
            # Cache results if requested
            if use_cache and cache_key:
                self._query_cache[cache_key] = processed_results
            
            execution_time = time.time() - start_time
            logger.debug(f"Query executed in {execution_time:.3f}s, returned {len(processed_results)} results")
            
            return processed_results
            
        except Exception as e:
            logger.error(f"SPARQL query failed: {e}")
            logger.error(f"Query was: {query}")
            raise
    
    def _add_namespace_prefixes(self, query: str) -> str:
        """
        Add namespace prefixes to a SPARQL query.
        
        Args:
            query: Original SPARQL query
            
        Returns:
            Query with namespace prefixes added
        """
        prefixes = []
        namespaces = self.namespace_manager.get_all_namespaces()
        
        for prefix, uri in namespaces.items():
            if prefix and uri:  # Ensure both are not None/empty
                prefixes.append(f"PREFIX {prefix}: <{uri}>")
            else:
                print(f"WARNING: Skipping invalid namespace - prefix: {prefix}, uri: {uri}")
        
        return "\n".join(prefixes) + "\n" + query if prefixes else query
    
    def _process_query_results(self, results) -> List[Dict[str, Any]]:
        """
        Process SPARQL query results into dictionaries.
        
        Args:
            results: Raw SPARQL query results
            
        Returns:
            List of result dictionaries
        """
        processed = []
        
        for row in results:
            result_dict = {}
            for var_name, value in row.asdict().items():
                result_dict[var_name] = self._process_query_value(value)
            processed.append(result_dict)
        
        return processed
    
    def _process_query_value(self, value) -> Any:
        """
        Process a single query result value.
        
        Args:
            value: Raw query result value
            
        Returns:
            Processed value (string, number, etc.)
        """
        if value is None:
            return None
        
        # Convert rdflib objects to strings/values
        if hasattr(value, 'toPython'):
            try:
                return value.toPython()
            except:
                return str(value)
        
        return str(value)
    
    def normalize_data_type(self, raw_type: str) -> str:
        """
        Normalize property data types from ontology.
        
        Args:
            raw_type: Raw data type string from ontology
            
        Returns:
            Normalized data type
        """
        raw_type = raw_type.lower()
        
        if "objectproperty" in raw_type:
            return "object"
        elif "string" in raw_type:
            return "string"
        elif "int" in raw_type:
            return "integer"
        elif "double" in raw_type or "decimal" in raw_type:
            return "double"
        elif "float" in raw_type:
            return "float"
        elif "bool" in raw_type:
            return "boolean"
        elif "date" in raw_type:
            return "date"
        else:
            return "data"  # Generic data property
    
    def clear_cache(self):
        """Clear the query cache."""
        self._query_cache.clear()
        logger.debug("Query cache cleared")
    
    def get_cache_stats(self) -> Dict[str, int]:
        """Get query cache statistics."""
        return {
            'cached_queries': len(self._query_cache),
            'cache_size_bytes': sum(len(str(v)) for v in self._query_cache.values())
        }
    
    def count_triples(self) -> int:
        """Get the total number of triples in the graph."""
        return len(self.graph)
    
    def execute_ask_query(self, query: str, bindings: Optional[Dict] = None) -> bool:
        """
        Execute a SPARQL ASK query.
        
        Args:
            query: SPARQL ASK query string
            bindings: Optional variable bindings
            
        Returns:
            Boolean result
        """
        try:
            prefixed_query = self._add_namespace_prefixes(query)
            prepared = prepareQuery(prefixed_query, initNs=self.namespace_manager.get_all_namespaces())
            result = self.graph.query(prepared, initBindings=bindings or {})
            return bool(result)
        except Exception as e:
            logger.error(f"SPARQL ASK query failed: {e}")
            raise