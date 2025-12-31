"""
Access Control List (ACL) Manager - Permission management component
"""

import json
from pathlib import Path


class ACLManager:
    """Standalone component for managing Access Control List (ACL)"""
    
    def __init__(self, acl_path: str = "config/acl.json"):
        """
        Initialize ACLManager
        
        Args:
            acl_path: Path to ACL configuration file (default: "config/acl.json")
        """
        self.acl_path = Path(acl_path)
        self.acl = self.load_acl()
    
    def load_acl(self) -> dict:
        """Load ACL configuration from JSON file"""
        if not self.acl_path.exists():
            print(f"Warning: ACL file not found at {self.acl_path}")
            return {}
        
        with open(self.acl_path, "r") as f:
            return json.load(f)
    
    def get_file_permissions(self, file_path: str) -> dict:
        """Get permissions for a file from ACL configuration
        
        Args:
            file_path: File path
            
        Returns:
            Permission dictionary, format: { user_id: [permissions] }
            
        New structure: resources -> { resource_path: { user_id: [permissions] } }
        """
        resources = self.acl.get("resources", {})
        return resources.get(file_path, {})
    
    def can_access(self, user_id: str, file_path: str, action: str = "read") -> bool:
        """Check if a user can perform a specified action on a file
        
        Args:
            user_id: User ID
            file_path: File path
            action: Action type (default: "read")
            
        Returns:
            True if user has permission, False otherwise
            
        New structure: resources -> { resource_path: { user_id: [permissions] } }
        """
        resources = self.acl.get("resources", {})
        resource_perms = resources.get(file_path, {})
        user_perms = resource_perms.get(user_id, [])
        
        return action in user_perms

