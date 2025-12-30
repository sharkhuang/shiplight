"""
Search Engine - Vector DB initialized with resources and ACL permissions
"""

import json
from pathlib import Path

import chromadb


class SearchEngine:
    def __init__(self, resources_dir: str = "resources", acl_path: str = "config/acl.json"):
        self.resources_dir = Path(resources_dir)
        self.acl_path = Path(acl_path)
        self.client = chromadb.Client()
        self.collection = None
        self.acl = {}

    def init_vector_db(self) -> None:
        """
        Initialize vector DB with files from resources folder
        and permissions from ACL configuration.
        """
        # Load ACL configuration
        self.acl = self._load_acl()

        # Create collection
        self.collection = self.client.get_or_create_collection(name="resources_search")

        # Load resource files and index them
        documents = []
        metadatas = []
        ids = []

        for file_path in self.resources_dir.iterdir():
            if file_path.is_file():
                # Read file content
                content = file_path.read_text()

                # Get permissions for this file
                relative_path = str(file_path)
                permissions = self._get_file_permissions(relative_path)

                # Build metadata with user access flags for filtering
                metadata = {
                    "filename": file_path.name,
                    "path": relative_path,
                    "permissions": json.dumps(permissions),
                }
                
                # Add boolean flags for each user's access (enables metadata filtering)
                for user_id in self.acl.get("users", {}).keys():
                    metadata[f"{user_id}_access"] = user_id in permissions

                documents.append(content)
                metadatas.append(metadata)
                ids.append(file_path.name)

        # Add to vector DB
        if documents:
            self.collection.add(
                documents=documents,
                metadatas=metadatas,
                ids=ids,
            )

        print(f"Initialized vector DB with {len(documents)} files from {self.resources_dir}")

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
            raise RuntimeError("Vector DB not initialized. Call init_vector_db() first.")

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
        # Search more documents to account for filtering
        search_limit = n_results * 3 if user_id else n_results

        results = self.collection.query(
            query_texts=[query],
            n_results=search_limit,
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
    engine = SearchEngine()
    engine.init_vector_db()

    print("\nSearchEngine initialized. Run tests with: pytest tests/ -v")


if __name__ == "__main__":
    main()

