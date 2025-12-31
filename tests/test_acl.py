"""
Unit tests for ACLManager
"""

import pytest
from pathlib import Path
from src.acl import ACLManager


class TestACLManager:
    """Test cases for ACLManager class."""

    @pytest.fixture
    def acl_manager(self):
        """Create ACLManager instance with default ACL path."""
        return ACLManager(acl_path="config/acl.json")

    @pytest.fixture
    def acl_manager_custom_path(self, tmp_path):
        """Create ACLManager instance with custom ACL file in temporary directory."""
        acl_file = tmp_path / "test_acl.json"
        acl_file.write_text("""{
  "version": "1.0",
  "description": "Test ACL",
  "resources": {
    "test/file1.txt": {
      "user1": ["read", "write"],
      "user2": ["read"]
    }
  },
  "users": {
    "user1": {"name": "User One"},
    "user2": {"name": "User Two"}
  }
}""")
        return ACLManager(acl_path=str(acl_file))

    # ==================== Initialization ====================

    def test_acl_manager_initialization(self, acl_manager):
        """Test that ACLManager initializes correctly."""
        assert acl_manager is not None
        assert acl_manager.acl_path == Path("config/acl.json")
        assert isinstance(acl_manager.acl, dict)

    def test_acl_manager_loads_acl_on_init(self, acl_manager):
        """Test that ACL is loaded during initialization."""
        assert "resources" in acl_manager.acl
        assert "users" in acl_manager.acl

    def test_acl_manager_with_missing_file(self, tmp_path):
        """Test ACLManager handles missing ACL file gracefully."""
        missing_path = tmp_path / "missing_acl.json"
        acl_manager = ACLManager(acl_path=str(missing_path))
        
        assert acl_manager.acl == {}
        assert acl_manager.acl_path == missing_path

    # ==================== load_acl ====================

    def test_load_acl_loads_valid_json(self, acl_manager):
        """Test load_acl loads valid JSON file."""
        acl = acl_manager.load_acl()
        
        assert isinstance(acl, dict)
        assert "resources" in acl
        assert "users" in acl

    def test_load_acl_returns_empty_dict_for_missing_file(self, tmp_path):
        """Test load_acl returns empty dict for missing file."""
        missing_path = tmp_path / "missing.json"
        acl_manager = ACLManager(acl_path=str(missing_path))
        
        acl = acl_manager.load_acl()
        assert acl == {}

    # ==================== get_file_permissions ====================

    def test_get_file_permissions_returns_permissions(self, acl_manager):
        """Test get_file_permissions returns correct permissions for existing file."""
        perms = acl_manager.get_file_permissions("resources/testfile1.txt")
        
        assert isinstance(perms, dict)
        assert "user1" in perms
        assert "user2" in perms
        assert perms["user1"] == ["read", "write", "delete"]
        assert perms["user2"] == ["read"]

    def test_get_file_permissions_returns_empty_dict_for_missing_file(self, acl_manager):
        """Test get_file_permissions returns empty dict for non-existent file."""
        perms = acl_manager.get_file_permissions("resources/nonexistent.txt")
        
        assert perms == {}

    def test_get_file_permissions_with_custom_acl(self, acl_manager_custom_path):
        """Test get_file_permissions works with custom ACL file."""
        perms = acl_manager_custom_path.get_file_permissions("test/file1.txt")
        
        assert "user1" in perms
        assert "user2" in perms
        assert perms["user1"] == ["read", "write"]
        assert perms["user2"] == ["read"]

    # ==================== can_access ====================

    def test_can_access_granted_read(self, acl_manager):
        """Test can_access returns True for granted read permission."""
        assert acl_manager.can_access("user1", "resources/testfile1.txt", "read") is True
        assert acl_manager.can_access("user2", "resources/testfile1.txt", "read") is True
        assert acl_manager.can_access("user2", "resources/testfile2.txt", "read") is True

    def test_can_access_granted_write(self, acl_manager):
        """Test can_access returns True for granted write permission."""
        assert acl_manager.can_access("user1", "resources/testfile1.txt", "write") is True

    def test_can_access_granted_delete(self, acl_manager):
        """Test can_access returns True for granted delete permission."""
        assert acl_manager.can_access("user1", "resources/testfile1.txt", "delete") is True

    def test_can_access_denied_read(self, acl_manager):
        """Test can_access returns False for denied read permission."""
        assert acl_manager.can_access("user1", "resources/testfile2.txt", "read") is False

    def test_can_access_denied_write(self, acl_manager):
        """Test can_access returns False for denied write permission."""
        assert acl_manager.can_access("user2", "resources/testfile1.txt", "write") is False

    def test_can_access_nonexistent_user(self, acl_manager):
        """Test can_access returns False for non-existent user."""
        assert acl_manager.can_access("nonexistent_user", "resources/testfile1.txt", "read") is False

    def test_can_access_nonexistent_file(self, acl_manager):
        """Test can_access returns False for non-existent file."""
        assert acl_manager.can_access("user1", "resources/nonexistent.txt", "read") is False

    def test_can_access_default_action_is_read(self, acl_manager):
        """Test can_access defaults to 'read' action when not specified."""
        assert acl_manager.can_access("user1", "resources/testfile1.txt") is True
        assert acl_manager.can_access("user1", "resources/testfile2.txt") is False

    def test_can_access_with_custom_acl(self, acl_manager_custom_path):
        """Test can_access works with custom ACL file."""
        assert acl_manager_custom_path.can_access("user1", "test/file1.txt", "read") is True
        assert acl_manager_custom_path.can_access("user1", "test/file1.txt", "write") is True
        assert acl_manager_custom_path.can_access("user2", "test/file1.txt", "read") is True
        assert acl_manager_custom_path.can_access("user2", "test/file1.txt", "write") is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

