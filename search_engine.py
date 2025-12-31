"""
Search Engine - Vector DB initialized with resources and ACL permissions
"""

import json
from pathlib import Path

import chromadb


class SearchEngine:
    def __init__(self, collection_name: str = "resources_db", acl_path: str = "config/acl.json"):
        """
        Initialize SearchEngine for querying the vector database.
        
        Note: The database must be initialized by DBManager before using SearchEngine.
        
        Args:
            collection_name: Name of the ChromaDB collection to query (default: "resources_db")
            acl_path: Path to ACL configuration file for permission checks
        """
        self.acl_path = Path(acl_path)
        self.client = chromadb.Client()
        self.collection_name = collection_name
        
        # Load ACL configuration for permission checks
        self.acl = self._load_acl()
        
        # Get the existing collection (must be initialized by DBManager first)
        try:
            self.collection = self.client.get_collection(name=collection_name)
        except Exception as e:
            raise RuntimeError(
                f"Collection '{collection_name}' not found. "
                f"Please initialize the database using DBManager.init_db() first."
            ) from e

    def _load_acl(self) -> dict:
        """Load ACL configuration from JSON file."""
        if not self.acl_path.exists():
            print(f"Warning: ACL file not found at {self.acl_path}")
            return {}

        with open(self.acl_path, "r") as f:
            return json.load(f)

    def _get_file_permissions(self, file_path: str) -> dict:
        """Get permissions for a file from ACL configuration.
        
        New structure: resources -> { resource_path: { user_id: [permissions] } }
        """
        resources = self.acl.get("resources", {})
        return resources.get(file_path, {})

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

    def can_access(self, user_id: str, file_path: str, action: str = "read") -> bool:
        """Check if a user can perform an action on a file.
        
        New structure: resources -> { resource_path: { user_id: [permissions] } }
        """
        resources = self.acl.get("resources", {})
        resource_perms = resources.get(file_path, {})
        user_perms = resource_perms.get(user_id, [])

        return action in user_perms


def main():
    """Quick demo of SearchEngine."""
    from db_update import DBManager
    
    # First, initialize the database using DBManager
    print("Initializing database with DBManager...")
    db = DBManager()
    db.init_db()
    
    # Then, use SearchEngine to query
    print("\nSearching with SearchEngine...")
    engine = SearchEngine(collection_name="resources_db")
    results = engine.search("test", n_results=5)
    
    print(f"\nFound {len(results)} results:")
    for i, result in enumerate(results, 1):
        print(f"{i}. {result['filename']} (distance: {result['distance']:.4f})")
    
    print("\nRun tests with: pytest tests/ -v")


if __name__ == "__main__":
    main()

