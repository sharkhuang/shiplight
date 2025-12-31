"""
Search Engine - Vector DB initialized with resources and ACL permissions
"""

import json
from typing import Optional

import chromadb


class SearchEngine:
    def __init__(
        self,
        collection_name: str = "resources_db",
        client: Optional[chromadb.Client] = None,
        persist_directory: Optional[str] = None,
    ):
        """
        Initialize SearchEngine for querying the vector database.
        
        Note: The database must be initialized by DBManager before using SearchEngine.
        Permissions are handled via metadata stored in the database by DBManager.
        
        Args:
            collection_name: Name of the ChromaDB collection to query (default: "resources_db")
            client: Optional ChromaDB client instance. If provided, this client will be used.
                If not provided, a new client will be created.
            persist_directory: Optional directory path for persistent storage.
                If provided and client is None, creates a PersistentClient.
                If both are None, uses in-memory client (not recommended for production).
                Default: "./chroma_db" for persistent storage.
        
        Note: To share data with DBManager, either:
            1. Pass the same client instance used by DBManager, OR
            2. Use the same persist_directory path as DBManager
        """
        self.collection_name = collection_name
        
        # Initialize ChromaDB client (must match DBManager's client for data sharing)
        if client is not None:
            self.client = client
        elif persist_directory is not None:
            self.client = chromadb.PersistentClient(path=persist_directory)
        else:
            # Default to persistent storage for data sharing
            self.client = chromadb.PersistentClient(path="./chroma_db")
        
        # Get the existing collection (must be initialized by DBManager first)
        try:
            self.collection = self.client.get_collection(name=collection_name)
        except Exception as e:
            raise RuntimeError(
                f"Collection '{collection_name}' not found. "
                f"Please initialize the database using DBManager.init_db() first."
            ) from e

    def search(
        self,
        query: str,
        user_id: str = None,
        n_results: int = 5,
        method: str = "filter_first",
    ) -> list:
        """
        Search resources with optional user permission filtering.
        
        Args:
            query: Search query text
            user_id: Optional user ID to filter by permissions
            n_results: Number of results to return
            method: Search method - "filter_first" or "query_first"
                - filter_first: Filter by permissions THEN vector search (more efficient)
                - query_first: Vector search THEN filter by permissions (better relevance)
        
        Returns:
            List of search results with metadata
        """
        if not self.collection:
            raise RuntimeError(
                "Collection not available. Ensure DBManager has initialized the database."
            )

        if method == "filter_first":
            return self._search_filter_first(query, user_id, n_results)
        elif method == "query_first":
            return self._search_query_first(query, user_id, n_results)
        else:
            raise ValueError(f"Invalid method: {method}. Use 'filter_first' or 'query_first'")

    def _search_filter_first(self, query: str, user_id: str, n_results: int) -> list:
        """
        Filter by permissions FIRST, then perform vector search.
        
        More efficient - only searches accessible documents.
        May miss relevant results if user has limited access.
        """
        query_params = {
            "query_texts": [query],
            "n_results": n_results,
        }

        # Apply metadata filter before vector search
        if user_id:
            query_params["where"] = {f"{user_id}_access": True}

        results = self.collection.query(**query_params)
        return self._format_results(results)

    def _search_query_first(self, query: str, user_id: str, n_results: int) -> list:
        """
        Vector search FIRST, then filter by permissions.
        
        Better relevance ranking - finds most relevant docs first.
        Then filters out inaccessible ones (may return fewer than n_results).
        """

        results = self.collection.query(
            query_texts=[query],
            n_results=n_results,
        )

        formatted = self._format_results(results)

        # Filter by user permissions after search
        if user_id:
            formatted = [
                r for r in formatted
                if user_id in r["permissions"]
            ]

        # Return only requested number of results
        return formatted[:n_results]

    def _format_results(self, results: dict) -> list:
        """Format raw ChromaDB results into structured output."""
        formatted = []
        if results["documents"] and results["documents"][0]:
            for i, doc in enumerate(results["documents"][0]):
                metadata = results["metadatas"][0][i]
                permissions = json.loads(metadata["permissions"])

                formatted.append({
                    "content": doc,
                    "filename": metadata["filename"],
                    "path": metadata["path"],
                    "permissions": permissions,
                    "distance": results["distances"][0][i],
                })

        return formatted

