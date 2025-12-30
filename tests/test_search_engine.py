"""
Unit tests for SearchEngine
"""

import pytest
from search_engine import SearchEngine


class TestSearchEngine:
    """Test cases for SearchEngine class."""

    @pytest.fixture
    def engine(self):
        """Create and initialize a SearchEngine instance."""
        engine = SearchEngine()
        engine.init_vector_db()
        return engine

    # ==================== Initialization ====================

    def test_init_vector_db(self, engine):
        """Test that vector DB initializes correctly."""
        assert engine.collection is not None
        assert engine.acl is not None

    # ==================== Basic Search ====================

    def test_search_returns_all_documents(self, engine):
        """Test search without user filter returns all documents."""
        results = engine.search("test content")
        
        assert len(results) == 2
        filenames = {r["filename"] for r in results}
        assert filenames == {"testfile1.txt", "testfile2.txt"}

    def test_search_result_structure(self, engine):
        """Test that search results contain all required fields."""
        results = engine.search("test content", n_results=1)
        
        assert len(results) == 1
        result = results[0]
        assert "content" in result
        assert "filename" in result
        assert "path" in result
        assert "permissions" in result
        assert "distance" in result
        assert isinstance(result["distance"], float)

    def test_search_respects_n_results(self, engine):
        """Test search returns correct number of results."""
        results = engine.search("test", n_results=1)
        assert len(results) == 1

    def test_search_irrelevant_query_has_high_distance(self, engine):
        """Test irrelevant queries return results with high distance scores."""
        results = engine.search("quantum physics blockchain")
        
        assert len(results) > 0
        for result in results:
            assert result["distance"] > 1.0

    # ==================== Permission Filtering ====================

    def test_search_user1_limited_access(self, engine):
        """Test user1 only sees documents they have access to."""
        results = engine.search("test", user_id="user1")
        
        assert len(results) == 1
        assert results[0]["filename"] == "testfile1.txt"

    def test_search_user2_full_access(self, engine):
        """Test user2 can access both documents."""
        results = engine.search("test", user_id="user2")
        
        assert len(results) == 2
        filenames = {r["filename"] for r in results}
        assert filenames == {"testfile1.txt", "testfile2.txt"}

    def test_search_nonexistent_user_no_results(self, engine):
        """Test non-existent user returns no results."""
        results = engine.search("test", user_id="nonexistent_user")
        assert len(results) == 0

    # ==================== can_access API ====================

    def test_can_access_granted(self, engine):
        """Test can_access returns True for valid permissions."""
        assert engine.can_access("user1", "resources/testfile1.txt", "read") is True
        assert engine.can_access("user1", "resources/testfile1.txt", "write") is True
        assert engine.can_access("user2", "resources/testfile2.txt", "read") is True

    def test_can_access_denied(self, engine):
        """Test can_access returns False for invalid permissions."""
        assert engine.can_access("user1", "resources/testfile2.txt", "read") is False
        assert engine.can_access("user2", "resources/testfile1.txt", "write") is False

    # ==================== Search Methods ====================

    def test_search_methods_produce_same_results(self, engine):
        """Test filter_first and query_first return same results for user with full access."""
        filter_results = engine.search("test", user_id="user2", method="filter_first")
        query_results = engine.search("test", user_id="user2", method="query_first")
        
        filter_files = {r["filename"] for r in filter_results}
        query_files = {r["filename"] for r in query_results}
        
        assert filter_files == query_files
        assert len(filter_results) == 2

    def test_search_methods_with_limited_user(self, engine):
        """Test both methods correctly filter for user with limited access."""
        filter_results = engine.search("test", user_id="user1", method="filter_first")
        query_results = engine.search("test", user_id="user1", method="query_first")
        
        assert len(filter_results) == 1
        assert len(query_results) == 1
        assert filter_results[0]["filename"] == "testfile1.txt"
        assert query_results[0]["filename"] == "testfile1.txt"

    def test_search_invalid_method_raises_error(self, engine):
        """Test invalid search method raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            engine.search("test", method="invalid_method")
        
        assert "Invalid method" in str(exc_info.value)

    def test_query_first_respects_n_results(self, engine):
        """Test query_first respects n_results limit after filtering."""
        results = engine.search("test", user_id="user2", n_results=1, method="query_first")
        assert len(results) == 1

    def test_query_first_misses_results_filter_first_finds(self, engine):
        """
        Test case: query_first returns 0 results, filter_first returns 1.
        
        When many inaccessible documents rank higher than accessible ones,
        query_first may miss accessible documents in its limited search.
        """
        import json
        
        # Add documents highly relevant to "machine learning" but NOT accessible to user1
        ml_docs = [
            "Machine learning algorithms train on datasets",
            "Deep learning neural networks for AI",
            "Artificial intelligence transforms technology",
            "ML models optimize predictions",
            "Neural network architectures process data",
        ]
        
        for i, doc in enumerate(ml_docs):
            engine.collection.add(
                documents=[doc],
                metadatas=[{
                    "filename": f"ml_{i}.txt",
                    "path": f"resources/ml_{i}.txt",
                    "permissions": json.dumps({"user2": ["read"]}),
                    "user1_access": False,
                    "user2_access": True,
                }],
                ids=[f"ml_{i}"],
            )
        
        query = "machine learning neural network AI"
        
        # filter_first: Only searches user1's accessible docs, finds testfile1.txt
        filter_results = engine.search(
            query, user_id="user1", n_results=1, method="filter_first"
        )
        
        # query_first: Searches all docs, top results are ML docs (inaccessible)
        # After filtering, no accessible docs remain
        query_results = engine.search(
            query, user_id="user1", n_results=1, method="query_first"
        )
        
        # filter_first finds 1 result, query_first finds 0
        assert len(filter_results) == 1
        assert filter_results[0]["filename"] == "testfile1.txt"
        assert len(query_results) == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
