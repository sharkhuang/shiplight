"""
Database Module - Initialize and manage ChromaDB vector database
"""

import json
import mimetypes
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal, Optional

import chromadb

from .acl import ACLManager


class DBManager:
    """Manages ChromaDB vector database initialization and updates."""

    def __init__(
        self,
        resources_dir: str = "resources",
        acl_path: str = "config/acl.json",
        collection_name: str = "resources_db",
        client: Optional[chromadb.Client] = None,
        persist_directory: Optional[str] = None,
    ):
        """
        Initialize DBManager.
        
        Args:
            resources_dir: Directory containing resource files
            acl_path: Path to ACL configuration file
            collection_name: Name of the ChromaDB collection
            client: Optional ChromaDB client instance. If provided, this client will be used.
                If not provided, a new client will be created.
            persist_directory: Optional directory path for persistent storage.
                If provided and client is None, creates a PersistentClient.
                If both are None, uses in-memory client (not recommended for production).
                Default: "./chroma_db" for persistent storage.
        
        Note: To share data between DBManager and SearchEngine, either:
            1. Pass the same client instance to both, OR
            2. Use the same persist_directory path in both
        """
        self.resources_dir = Path(resources_dir)
        self.collection_name = collection_name
        
        # Initialize ChromaDB client
        if client is not None:
            self.client = client
        elif persist_directory is not None:
            self.client = chromadb.PersistentClient(path=persist_directory)
        else:
            # Default to persistent storage for data sharing
            self.client = chromadb.PersistentClient(path="./chroma_db")
        
        self.collection = None
        
        # Initialize ACL manager
        self.acl_manager = ACLManager(acl_path=acl_path)

    def _build_metadata(
        self,
        file_path: Path,
        permissions: Optional[dict] = None,
        preserve_created_at: Optional[str] = None,
    ) -> dict:
        """
        Build complete metadata for a document, including standard fields and permission fields.
        
        Args:
            file_path: File path object
            permissions: Optional permission dictionary. If not provided, will be loaded from ACL config
            preserve_created_at: If provided, preserve the original creation time (for update scenarios)
        
        Returns:
            Complete metadata dictionary
        """
        # Get permissions from ACL if not provided
        if permissions is None:
            relative_path = str(file_path)
            permissions = self.acl_manager.get_file_permissions(relative_path)
        
        # Read file information
        try:
            if file_path.exists():
                file_size = file_path.stat().st_size
                content = file_path.read_text()
                content_length = len(content)
            else:
                # File doesn't exist (update scenario)
                file_size = 0
                content_length = 0
        except Exception:
            file_size = 0
            content_length = 0
        
        # Generate timestamp
        current_time = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        
        # Infer content type
        mime_type, _ = mimetypes.guess_type(str(file_path))
        content_type = mime_type or "text/plain"
        
        # Build base metadata
        metadata = {
            # Base fields
            "filename": file_path.name,
            "path": str(file_path),
            "permissions": json.dumps(permissions or {}),
            
            # Standard metadata fields
            "created_at": preserve_created_at or current_time,
            "updated_at": current_time,
            "content_type": content_type,
            "file_size": file_size,
            "content_length": content_length,
            "metadata_version": "1.0",
        }
        
        # Add permission boolean flags (keep existing logic unchanged)
        for user_id in self.acl_manager.acl.get("users", {}).keys():
            metadata[f"{user_id}_access"] = user_id in (permissions or {})
        
        return metadata

    def init_db(self) -> None:
        """
        Initialize the vector database from resources folder and ACL config.
        
        Reads all files from resources folder and indexes them with
        permission metadata from ACL configuration.
        """
        # Create or get collection
        self.collection = self.client.get_or_create_collection(name=self.collection_name)

        # Load and index all resource files
        documents = []
        metadatas = []
        ids = []

        for file_path in self.resources_dir.iterdir():
            if file_path.is_file():
                content = file_path.read_text()
                
                # Use unified metadata building method
                metadata = self._build_metadata(file_path)

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

        # Get existing document's created_at (if exists) to preserve timestamp consistency
        existing_docs = self.collection.get(ids=[doc_id])
        preserve_created_at = None
        if len(existing_docs["ids"]) > 0 and existing_docs["metadatas"]:
            existing_metadata = existing_docs["metadatas"][0]
            preserve_created_at = existing_metadata.get("created_at")

        content = path.read_text()
        
        # Use unified metadata building method
        metadata = self._build_metadata(
            path,
            permissions=permissions,
            preserve_created_at=preserve_created_at,
        )

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

    def get_all_documents(self) -> dict:
        """Get all documents in the collection."""
        if not self.collection:
            raise RuntimeError("DB not initialized. Call init_db() first.")

        return self.collection.get()

