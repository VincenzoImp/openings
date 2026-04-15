"""Tests for vector_store and vector_commands modules."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

# Mock chromadb and sentence-transformers before importing
_mock_chromadb = MagicMock()
_mock_chromadb_utils = MagicMock()
_mock_chromadb_utils_ef = MagicMock()
sys.modules["chromadb"] = _mock_chromadb
sys.modules["chromadb.utils"] = _mock_chromadb_utils
sys.modules["chromadb.utils.embedding_functions"] = _mock_chromadb_utils_ef


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture(autouse=True)
def _reset_vector_store_singleton():
    """Reset the vector store singleton between tests."""
    import vector_store as vs_module

    original = vs_module._vector_store
    original_key = getattr(vs_module, "_vector_store_key", None)
    yield
    vs_module._vector_store = original
    vs_module._vector_store_key = original_key


@pytest.fixture
def mock_collection():
    """Create a mock ChromaDB collection."""
    collection = MagicMock()
    collection.count.return_value = 0
    collection.get.return_value = {"ids": []}
    collection.query.return_value = {
        "ids": [[]],
        "distances": [[]],
        "metadatas": [[]],
    }
    return collection


@pytest.fixture
def mock_client(mock_collection):
    """Create a mock ChromaDB PersistentClient."""
    client = MagicMock()
    client.get_or_create_collection.return_value = mock_collection
    return client


@pytest.fixture
def vector_store(mock_client, mock_collection, tmp_path):
    """Create a JobVectorStore with mocked ChromaDB."""
    with patch.object(_mock_chromadb, "PersistentClient", return_value=mock_client):
        from vector_store import JobVectorStore

        store = JobVectorStore(persist_dir=tmp_path / "chroma")
    return store


@pytest.fixture
def sample_jobs():
    """Sample job dicts for testing."""
    return [
        {
            "job_id": "abc123",
            "title": "Software Engineer",
            "company": "Acme Corp",
            "location": "New York, NY",
            "description": "Build cool stuff",
            "site": "linkedin",
            "relevance_score": 30,
            "first_seen": "2026-01-01",
            "job_url": "https://example.com/1",
        },
        {
            "job_id": "def456",
            "title": "Data Scientist",
            "company": "Big Data Inc",
            "location": "Remote",
            "description": "Analyze data",
            "site": "indeed",
            "relevance_score": 25,
            "first_seen": "2026-01-02",
            "job_url": "https://example.com/2",
        },
    ]


@pytest.fixture
def mock_db_record():
    """Create a mock JobDBRecord."""
    record = MagicMock()
    record.job_id = "abc123"
    record.title = "Software Engineer"
    record.company = "Acme Corp"
    record.location = "New York, NY"
    record.description = "Build cool stuff"
    record.site = "linkedin"
    record.relevance_score = 30
    record.first_seen = "2026-01-01"
    record.job_url = "https://example.com/1"
    return record


# =============================================================================
# SemanticSearchResult TESTS
# =============================================================================


class TestSemanticSearchResult:
    """Tests for the SemanticSearchResult dataclass."""

    def test_creation(self):
        from vector_store import SemanticSearchResult

        result = SemanticSearchResult(
            job_id="abc123",
            distance=0.25,
            similarity=0.75,
            metadata={"title": "Engineer"},
        )
        assert result.job_id == "abc123"
        assert result.distance == 0.25
        assert result.similarity == 0.75
        assert result.metadata == {"title": "Engineer"}

    def test_frozen(self):
        from vector_store import SemanticSearchResult

        result = SemanticSearchResult(
            job_id="abc123", distance=0.2, similarity=0.8, metadata={}
        )
        with pytest.raises(AttributeError):
            result.job_id = "new_id"


# =============================================================================
# JobVectorStore TESTS
# =============================================================================


class TestJobVectorStore:
    """Tests for the JobVectorStore class."""

    def test_initialization(self, vector_store, mock_client):
        """Test that the vector store initializes with ChromaDB."""
        mock_client.get_or_create_collection.assert_called_once()

    def test_add_jobs_valid(self, vector_store, mock_collection, sample_jobs):
        """Test adding jobs with valid data."""
        count = vector_store.add_jobs(sample_jobs)
        assert count == 2
        mock_collection.upsert.assert_called_once()

        call_kwargs = mock_collection.upsert.call_args
        assert len(call_kwargs.kwargs["ids"]) == 2
        assert "abc123" in call_kwargs.kwargs["ids"]
        assert "def456" in call_kwargs.kwargs["ids"]

    def test_add_jobs_empty_list(self, vector_store, mock_collection):
        """Test adding an empty list returns 0."""
        count = vector_store.add_jobs([])
        assert count == 0
        mock_collection.upsert.assert_not_called()

    def test_add_jobs_skips_missing_job_id(self, vector_store, mock_collection):
        """Test that jobs without job_id are skipped."""
        jobs = [{"title": "No ID Job", "company": "Corp"}]
        count = vector_store.add_jobs(jobs)
        assert count == 0
        mock_collection.upsert.assert_not_called()

    def test_add_jobs_skips_empty_document(self, vector_store, mock_collection):
        """Test that jobs producing empty documents are skipped."""
        jobs = [{"job_id": "x", "title": "", "company": "", "location": ""}]
        count = vector_store.add_jobs(jobs)
        assert count == 0

    def test_add_jobs_batching(self, vector_store, mock_collection):
        """Test that large lists are batched."""
        jobs = [
            {
                "job_id": f"id_{i}",
                "title": f"Job {i}",
                "company": "Corp",
                "location": "NYC",
            }
            for i in range(250)
        ]
        count = vector_store.add_jobs(jobs, batch_size=100)
        assert count == 250
        assert mock_collection.upsert.call_count == 3  # 100 + 100 + 50

    def test_add_jobs_from_dataframe(self, vector_store, mock_collection):
        """Test adding jobs from a pandas DataFrame."""
        import pandas as pd

        df = pd.DataFrame(
            [
                {
                    "job_id": "df_1",
                    "title": "Engineer",
                    "company": "Corp",
                    "location": "NYC",
                    "description": "Code",
                },
            ]
        )
        count = vector_store.add_jobs_from_dataframe(df)
        assert count == 1
        mock_collection.upsert.assert_called_once()

    def test_search_returns_results(self, vector_store, mock_collection):
        """Test search returns SemanticSearchResult list."""
        mock_collection.count.return_value = 5
        mock_collection.query.return_value = {
            "ids": [["abc123", "def456"]],
            "distances": [[0.2, 0.5]],
            "metadatas": [[{"title": "Eng"}, {"title": "DS"}]],
        }

        results = vector_store.search("software engineer")
        assert len(results) == 2
        assert results[0].job_id == "abc123"
        assert results[0].distance == 0.2
        assert results[0].similarity == pytest.approx(0.8)
        assert results[1].similarity == pytest.approx(0.5)

    def test_search_empty_query(self, vector_store, mock_collection):
        """Test search with empty/whitespace query returns empty list."""
        results = vector_store.search("")
        assert results == []
        results = vector_store.search("   ")
        assert results == []
        mock_collection.query.assert_not_called()

    def test_search_empty_collection(self, vector_store, mock_collection):
        """Test search on empty collection returns empty list."""
        mock_collection.count.return_value = 0
        results = vector_store.search("engineer")
        assert results == []
        mock_collection.query.assert_not_called()

    def test_search_with_min_score_filter(self, vector_store, mock_collection):
        """Test search passes min_score as where filter."""
        mock_collection.count.return_value = 10
        mock_collection.query.return_value = {
            "ids": [[]],
            "distances": [[]],
            "metadatas": [[]],
        }

        vector_store.search("engineer", min_score=20)

        call_kwargs = mock_collection.query.call_args.kwargs
        assert call_kwargs["where"] == {"relevance_score": {"$gte": 20}}

    def test_search_with_site_filter(self, vector_store, mock_collection):
        """Test search passes site as where filter."""
        mock_collection.count.return_value = 10
        mock_collection.query.return_value = {
            "ids": [[]],
            "distances": [[]],
            "metadatas": [[]],
        }

        vector_store.search("engineer", site="linkedin")

        call_kwargs = mock_collection.query.call_args.kwargs
        assert call_kwargs["where"] == {"site": "linkedin"}

    def test_search_with_combined_filters(self, vector_store, mock_collection):
        """Test search combines multiple filters with $and."""
        mock_collection.count.return_value = 10
        mock_collection.query.return_value = {
            "ids": [[]],
            "distances": [[]],
            "metadatas": [[]],
        }

        vector_store.search("engineer", min_score=15, site="indeed")

        call_kwargs = mock_collection.query.call_args.kwargs
        where = call_kwargs["where"]
        assert "$and" in where
        assert {"relevance_score": {"$gte": 15}} in where["$and"]
        assert {"site": "indeed"} in where["$and"]

    def test_search_similarity_clamped(self, vector_store, mock_collection):
        """Test similarity is clamped to [0, 1]."""
        mock_collection.count.return_value = 5
        mock_collection.query.return_value = {
            "ids": [["id1", "id2"]],
            "distances": [[-0.5, 2.0]],  # Would give 1.5 and -1.0 unclamped
            "metadatas": [[{}, {}]],
        }

        results = vector_store.search("test")
        assert results[0].similarity == 1.0  # clamped from 1.5
        assert results[1].similarity == 0.0  # clamped from -1.0

    def test_delete_jobs(self, vector_store, mock_collection):
        """Test deleting jobs from the vector store."""
        mock_collection.get.return_value = {"ids": ["abc123"]}

        vector_store.delete_jobs(["abc123", "nonexistent"])

        mock_collection.delete.assert_called_once_with(ids=["abc123"])

    def test_delete_jobs_empty_list(self, vector_store, mock_collection):
        """Test deleting empty list is a no-op."""
        vector_store.delete_jobs([])
        mock_collection.get.assert_not_called()
        mock_collection.delete.assert_not_called()

    def test_delete_jobs_none_exist(self, vector_store, mock_collection):
        """Test deleting IDs that don't exist skips the delete call."""
        mock_collection.get.return_value = {"ids": []}

        vector_store.delete_jobs(["nonexistent"])
        mock_collection.delete.assert_not_called()

    def test_get_embedded_ids(self, vector_store, mock_collection):
        """Test getting all embedded job IDs."""
        mock_collection.get.return_value = {"ids": ["a", "b", "c"]}

        ids = vector_store.get_embedded_ids()
        assert ids == {"a", "b", "c"}

    def test_get_embedded_ids_empty(self, vector_store, mock_collection):
        """Test getting embedded IDs when store is empty."""
        mock_collection.get.return_value = {"ids": []}
        ids = vector_store.get_embedded_ids()
        assert ids == set()

    def test_count(self, vector_store, mock_collection):
        """Test count returns collection count."""
        mock_collection.count.return_value = 42
        assert vector_store.count() == 42

    def test_build_document(self, vector_store):
        """Test _build_document concatenates non-empty fields."""
        doc = vector_store._build_document("Eng", "Corp", "NYC", "Code")
        assert doc == "Eng | Corp | NYC | Code"

    def test_build_document_skips_empty(self, vector_store):
        """Test _build_document skips empty/nan values."""
        doc = vector_store._build_document("Eng", "", "nan", "Code")
        assert doc == "Eng | Code"

    def test_build_metadata(self, vector_store, sample_jobs):
        """Test _build_metadata extracts correct fields."""
        meta = vector_store._build_metadata(sample_jobs[0])
        assert meta["title"] == "Software Engineer"
        assert meta["company"] == "Acme Corp"
        assert meta["relevance_score"] == 30
        assert meta["site"] == "linkedin"

    def test_build_metadata_skips_nan(self, vector_store):
        """Test _build_metadata skips nan/None values."""
        meta = vector_store._build_metadata(
            {"title": "Eng", "company": None, "site": "nan"}
        )
        assert "company" not in meta
        assert "site" not in meta


# =============================================================================
# get_vector_store SINGLETON TESTS
# =============================================================================


class TestGetVectorStore:
    """Tests for the get_vector_store singleton accessor."""

    def test_creates_instance(self, mock_client, tmp_path):
        """Test that get_vector_store creates a new instance."""
        import vector_store as vs_module

        vs_module._vector_store = None
        vs_module._vector_store_key = None

        with patch.object(_mock_chromadb, "PersistentClient", return_value=mock_client):
            store = vs_module.get_vector_store(persist_dir=tmp_path / "chroma")

        assert store is not None
        assert isinstance(store, vs_module.JobVectorStore)

    def test_returns_singleton(self, mock_client, tmp_path):
        """Test that get_vector_store returns the same instance."""
        import vector_store as vs_module

        vs_module._vector_store = None
        vs_module._vector_store_key = None

        with patch.object(_mock_chromadb, "PersistentClient", return_value=mock_client):
            store1 = vs_module.get_vector_store(persist_dir=tmp_path / "chroma")
            store2 = vs_module.get_vector_store(persist_dir=tmp_path / "chroma")

        assert store1 is store2

    def test_recreates_singleton_when_path_changes(self, mock_client, tmp_path):
        """Test singleton refreshes when the persist_dir changes."""
        import vector_store as vs_module

        vs_module._vector_store = None
        vs_module._vector_store_key = None

        with patch.object(_mock_chromadb, "PersistentClient", return_value=mock_client):
            store1 = vs_module.get_vector_store(persist_dir=tmp_path / "chroma-a")
            store2 = vs_module.get_vector_store(persist_dir=tmp_path / "chroma-b")

        assert store1 is not store2


# =============================================================================
# vector_commands TESTS
# =============================================================================


class TestBackfillEmbeddings:
    """Tests for backfill_embeddings command."""

    def test_backfill_with_jobs_to_embed(
        self, vector_store, mock_collection, mock_db_record
    ):
        """Test backfilling jobs that aren't yet embedded."""
        from vector_commands import backfill_embeddings

        mock_db = MagicMock()
        mock_db.get_all_jobs.return_value = [mock_db_record]

        # Vector store has no jobs embedded yet
        mock_collection.get.return_value = {"ids": []}

        count = backfill_embeddings(mock_db, vector_store, batch_size=50)

        assert count == 1
        mock_collection.upsert.assert_called_once()
        upsert_kwargs = mock_collection.upsert.call_args.kwargs
        assert "abc123" in upsert_kwargs["ids"]

    def test_backfill_nothing_to_embed(
        self, vector_store, mock_collection, mock_db_record
    ):
        """Test backfill when all jobs are already embedded."""
        from vector_commands import backfill_embeddings

        mock_db = MagicMock()
        mock_db.get_all_jobs.return_value = [mock_db_record]

        # Vector store already has this job
        mock_collection.get.return_value = {"ids": ["abc123"]}

        count = backfill_embeddings(mock_db, vector_store, batch_size=50)

        assert count == 0
        mock_collection.upsert.assert_not_called()

    def test_backfill_empty_database(self, vector_store, mock_collection):
        """Test backfill when database has no jobs."""
        from vector_commands import backfill_embeddings

        mock_db = MagicMock()
        mock_db.get_all_jobs.return_value = []
        mock_collection.get.return_value = {"ids": []}

        count = backfill_embeddings(mock_db, vector_store, batch_size=50)
        assert count == 0


class TestSyncDeletions:
    """Tests for sync_deletions command."""

    def test_sync_removes_stale_entries(self, vector_store, mock_collection):
        """Test that stale embeddings are removed."""
        from vector_commands import sync_deletions

        mock_db = MagicMock()
        # DB only has "abc123"
        mock_db_record = MagicMock()
        mock_db_record.job_id = "abc123"
        mock_db.get_all_jobs.return_value = [mock_db_record]

        # Vector store has "abc123" and "stale_id"
        mock_collection.get.side_effect = [
            {"ids": ["abc123", "stale_id"]},  # get_embedded_ids call
            {"ids": ["stale_id"]},  # delete_jobs -> get call
        ]

        removed = sync_deletions(mock_db, vector_store)

        assert removed == 1
        mock_collection.delete.assert_called_once_with(ids=["stale_id"])

    def test_sync_no_stale_entries(self, vector_store, mock_collection):
        """Test sync when everything is in sync."""
        from vector_commands import sync_deletions

        mock_db = MagicMock()
        mock_db_record = MagicMock()
        mock_db_record.job_id = "abc123"
        mock_db.get_all_jobs.return_value = [mock_db_record]

        mock_collection.get.return_value = {"ids": ["abc123"]}

        removed = sync_deletions(mock_db, vector_store)

        assert removed == 0
        mock_collection.delete.assert_not_called()

    def test_sync_empty_vector_store(self, vector_store, mock_collection):
        """Test sync when vector store is empty."""
        from vector_commands import sync_deletions

        mock_db = MagicMock()
        mock_db.get_all_jobs.return_value = []
        mock_collection.get.return_value = {"ids": []}

        removed = sync_deletions(mock_db, vector_store)
        assert removed == 0
