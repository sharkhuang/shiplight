"""
Unit tests for SearchEngine
"""

import pytest
from src.search_engine import SearchEngine
from src.db_update import DBManager


class TestSearchEngine:
    """Test cases for SearchEngine class."""

    @pytest.fixture
    def engine(self):
        """Create and initialize database, then create SearchEngine instance."""
        # First, initialize the database using DBManager
        db = DBManager(collection_name="resources_db")
        db.init_db()
        
        # Then, create SearchEngine to query the database
        engine = SearchEngine(collection_name="resources_db")
        return engine

    # ==================== Initialization ====================

    def test_search_engine_initialization(self, engine):
        """Test that SearchEngine connects to existing collection correctly."""
        assert engine.collection is not None
        assert engine.acl_manager is not None
        assert engine.collection_name == "resources_db"

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

    def test_query_first_may_miss_low_ranked_accessible_docs(self, engine):
        """
        Test that query_first may return fewer results when accessible
        documents are ranked lower than n_results.
        
        This demonstrates the tradeoff:
        - filter_first: Always finds accessible docs (searches only accessible)
        - query_first: May miss accessible docs (searches top n_results only)
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
        
        # query_first: Searches top 1 result, which is an ML doc (inaccessible)
        query_results = engine.search(
            query, user_id="user1", n_results=1, method="query_first"
        )
        
        # filter_first finds 1 result, query_first finds 0
        assert len(filter_results) == 1
        assert filter_results[0]["filename"] == "testfile1.txt"
        assert len(query_results) == 0  # Accessible doc not in top 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
