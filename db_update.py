"""
Database Update Module - Initialize and update ChromaDB vector database
"""

import json
from pathlib import Path
from typing import Literal, Optional

import chromadb


class DBManager:
    """Manages ChromaDB vector database initialization and updates."""

    def __init__(
        self,
        resources_dir: str = "resources",
        acl_path: str = "config/acl.json",
        collection_name: str = "resources_db",
    ):
        self.resources_dir = Path(resources_dir)
        self.acl_path = Path(acl_path)
        self.collection_name = collection_name
        self.client = chromadb.Client()
        self.collection = None
        self.acl = {}

    def init_db(self) -> None:
        """
        Initialize the vector database from resources folder and ACL config.
        
        Reads all files from resources folder and indexes them with
        permission metadata from ACL configuration.
        """
        # Load ACL configuration
        self.acl = self._load_acl()

        # Create or get collection
        self.collection = self.client.get_or_create_collection(name=self.collection_name)

        # Load and index all resource files
        documents = []
        metadatas = []
        ids = []

        for file_path in self.resources_dir.iterdir():
            if file_path.is_file():
                content = file_path.read_text()
                relative_path = str(file_path)
                permissions = self._get_file_permissions(relative_path)

                # Build metadata with user access flags
                metadata = {
                    "filename": file_path.name,
                    "path": relative_path,
                    "permissions": json.dumps(permissions),
                }

                # Add boolean flags for each user's access
                for user_id in self.acl.get("users", {}).keys():
                    metadata[f"{user_id}_access"] = user_id in permissions

                documents.append(content)
                metadatas.append(metadata)
                ids.append(file_path.name)

        # Add to vector DB
        if documents:
            self.collection.upsert(
                documents=documents,
                metadatas=metadatas,
                ids=ids,
            )

        print(f"Initialized DB with {len(documents)} files from {self.resources_dir}")
        return self

    def update_db(
        self,
        ids: list[str],
        documents: list[str],
        metadatas: Optional[list[dict]] = None,
        operation: Literal["add", "update", "upsert"] = "upsert",
    ) -> None:
        """
        Update the vector database with new or modified data.
        
        Args:
            ids: List of unique document IDs
            documents: List of document contents
            metadatas: Optional list of metadata dicts for each document
            operation: Type of operation - "add", "update", or "upsert"
                - add: Add new documents (fails if ID exists)
                - update: Update existing documents (fails if ID doesn't exist)
                - upsert: Add or update (recommended - handles both cases)
        
        Example:
            db.update_db(
                ids=["doc1", "doc2"],
                documents=["Content 1", "Content 2"],
                metadatas=[{"type": "note"}, {"type": "article"}],
                operation="upsert"
            )
        """
        if not self.collection:
            raise RuntimeError("DB not initialized. Call init_db() first.")

        if len(ids) != len(documents):
            raise ValueError("ids and documents must have the same length")

        if metadatas and len(metadatas) != len(ids):
            raise ValueError("metadatas must have the same length as ids")

        # Build operation parameters
        params = {
            "ids": ids,
            "documents": documents,
        }
        if metadatas:
            params["metadatas"] = metadatas

        # Execute the appropriate operation
        if operation == "add":
            self.collection.add(**params)
            print(f"Added {len(ids)} documents")
        elif operation == "update":
            self.collection.update(**params)
            print(f"Updated {len(ids)} documents")
        elif operation == "upsert":
            self.collection.upsert(**params)
            print(f"Upserted {len(ids)} documents")
        else:
            raise ValueError(f"Invalid operation: {operation}. Use 'add', 'update', or 'upsert'")

    def update_resource_file(
        self, 
        file_path: str, 
        permissions: Optional[dict] = None,
        upsert_if_missing: bool = False
    ) -> None:
        """
        Update or add a resource file in the database.
        
        Args:
            file_path: Path to the file to update or add
            permissions: Optional permission dict, e.g. {"user1": ["read", "write"]}
                If not provided, will try to load from ACL configuration
            upsert_if_missing: If True, create the document if it doesn't exist (upsert).
                This allows the method to be used for both adding and updating files.
                If False, raise an error if the document doesn't exist (default: False)
        
        Examples:
            # Update existing file (strict mode)
            db.update_resource_file("resources/file.txt")
            
            # Add or update file (upsert mode)
            db.update_resource_file("resources/file.txt", upsert_if_missing=True)
        
        Raises:
            FileNotFoundError: If the file doesn't exist on disk
            RuntimeError: If the document doesn't exist in DB and upsert_if_missing is False
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        if not self.collection:
            raise RuntimeError("DB not initialized. Call init_db() first.")

        # Load ACL if not already loaded
        if not self.acl:
            self.acl = self._load_acl()

        doc_id = path.name

        # If upsert_if_missing is True, we can skip existence check and use upsert directly
        if upsert_if_missing:
            # Skip existence check - upsert will handle both create and update
            pass
        else:
            # Check if document exists for strict update mode
            existing_docs = self.collection.get(ids=[doc_id])
            document_exists = len(existing_docs["ids"]) > 0

            if not document_exists:
                raise RuntimeError(
                    f"Document '{doc_id}' not found in database. "
                    f"Use upsert_if_missing=True to create it if it doesn't exist."
                )

        # Get permissions from ACL if not provided
        if permissions is None:
            relative_path = str(path)
            permissions = self._get_file_permissions(relative_path)

        content = path.read_text()
        
        metadata = {
            "filename": path.name,
            "path": str(path),
            "permissions": json.dumps(permissions or {}),
        }

        # Add boolean flags for each user's access (consistent with init_db)
        for user_id in self.acl.get("users", {}).keys():
            metadata[f"{user_id}_access"] = user_id in (permissions or {})

        # Use update or upsert based on flag
        operation = "upsert" if upsert_if_missing else "update"
        self.update_db(
            ids=[doc_id],
            documents=[content],
            metadatas=[metadata],
            operation=operation,
        )

    def delete_documents(self, ids: list[str]) -> None:
        """Delete documents from the database by IDs."""
        if not self.collection:
            raise RuntimeError("DB not initialized. Call init_db() first.")

        self.collection.delete(ids=ids)
        print(f"Deleted {len(ids)} documents")

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

    def get_all_documents(self) -> dict:
        """Get all documents in the collection."""
        if not self.collection:
            raise RuntimeError("DB not initialized. Call init_db() first.")

        return self.collection.get()


def main():
    """Demo usage of DBManager."""
    # Initialize database
    db = DBManager()
    db.init_db()

    print("\n" + "=" * 50)
    print("DB UPDATE DEMO")
    print("=" * 50)

    # Show current documents
    print("\n[Current Documents]")
    docs = db.get_all_documents()
    for i, doc_id in enumerate(docs["ids"]):
        print(f"  - {doc_id}")

    # Add new document
    print("\n[Adding new document]")
    db.update_db(
        ids=["new_doc"],
        documents=["This is a new document added via update_db"],
        metadatas=[{"type": "dynamic", "user1_access": True}],
        operation="add",
    )

    # Upsert (update existing + add new)
    print("\n[Upserting documents]")
    db.update_db(
        ids=["new_doc", "another_doc"],
        documents=["Updated content for new_doc", "Another new document"],
        metadatas=[{"type": "updated"}, {"type": "new"}],
        operation="upsert",
    )

    # Show updated documents
    print("\n[Documents after updates]")
    docs = db.get_all_documents()
    for i, doc_id in enumerate(docs["ids"]):
        print(f"  - {doc_id}")

    # Update an existing resource file
    print("\n[Updating existing resource file]")
    if db.resources_dir.exists() and any(db.resources_dir.iterdir()):
        # Get first file from resources directory
        first_file = next(db.resources_dir.iterdir(), None)
        if first_file and first_file.is_file():
            try:
                db.update_resource_file(str(first_file))
                print(f"  Updated: {first_file.name}")
            except Exception as e:
                print(f"  Error updating {first_file.name}: {e}")

    # Delete a document
    print("\n[Deleting 'another_doc']")
    db.delete_documents(["another_doc"])

    # Final state
    print("\n[Final documents]")
    docs = db.get_all_documents()
    for i, doc_id in enumerate(docs["ids"]):
        print(f"  - {doc_id}")


if __name__ == "__main__":
    main()

