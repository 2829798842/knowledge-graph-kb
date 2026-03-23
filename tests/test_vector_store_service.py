"""Tests for the FAISS vector storage implementation."""

from src.config import Settings
from src.services import FaissVectorStore, VectorRecord


def test_faiss_vector_store_persists_results_and_filters_by_document(tmp_path):
    """The FAISS store should persist embeddings and support document filtering."""

    settings = Settings(vector_store_dir=str((tmp_path / "faiss-store").resolve()))
    store = FaissVectorStore(settings)
    store.add_embeddings(
        [
            VectorRecord(
                chunk_id="chunk-1",
                document_id="doc-1",
                node_id="chunk:1",
                text="first chunk",
                vector=[1.0, 0.0],
            ),
            VectorRecord(
                chunk_id="chunk-2",
                document_id="doc-1",
                node_id="chunk:2",
                text="second chunk",
                vector=[0.8, 0.2],
            ),
            VectorRecord(
                chunk_id="chunk-3",
                document_id="doc-2",
                node_id="chunk:3",
                text="third chunk",
                vector=[0.0, 1.0],
            ),
        ]
    )

    results = store.search([1.0, 0.0], limit=2)

    assert [result.chunk_id for result in results] == ["chunk-1", "chunk-2"]
    assert results[0].similarity >= results[1].similarity

    filtered_results = store.search([1.0, 0.0], limit=5, document_ids=["doc-2"])

    assert [result.chunk_id for result in filtered_results] == ["chunk-3"]

    reloaded_store = FaissVectorStore(settings)
    persisted_results = reloaded_store.search([1.0, 0.0], limit=2)

    assert [result.chunk_id for result in persisted_results] == ["chunk-1", "chunk-2"]
