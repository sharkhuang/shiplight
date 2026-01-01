"""
Data models for document metadata.
"""

from pydantic import BaseModel, Field, ConfigDict


class DocumentMetadata(BaseModel):
    """
    Document metadata model for defining and validating ChromaDB document metadata structure.
    
    Includes base fields, standard metadata fields, and supports dynamic permission fields ({user_id}_access).
    """
    
    # Base fields
    filename: str = Field(..., description="File name")
    path: str = Field(..., description="Full file path")
    permissions: str = Field(..., description="Permission information (JSON string format)")
    
    # Standard metadata fields
    created_at: str = Field(..., description="Creation time (ISO format timestamp)")
    updated_at: str = Field(..., description="Update time (ISO format timestamp)")
    content_type: str = Field(default="text/plain", description="Content type (MIME type)")
    file_size: int = Field(ge=0, description="File size in bytes")
    content_length: int = Field(ge=0, description="Content length in characters")
    metadata_version: str = Field(default="1.0", description="Metadata version number")
    
    # Configuration: Allow extra fields (for dynamic permission fields {user_id}_access)
    model_config = ConfigDict(extra="allow")
    
    def to_dict(self) -> dict:
        """
        Convert to ChromaDB-compatible dictionary format.
        
        Returns:
            Dictionary containing all fields, including dynamic permission fields
        """
        return self.model_dump(mode="python")
    
    @classmethod
    def from_dict(cls, data: dict) -> "DocumentMetadata":
        """
        Create DocumentMetadata instance from dictionary.
        
        Args:
            data: Dictionary containing metadata (typically from ChromaDB)
        
        Returns:
            DocumentMetadata instance
        """
        return cls.model_validate(data)

