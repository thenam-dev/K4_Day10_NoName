from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from core.config import Settings
from core.utils import read_json, safe_slug, write_json
from retrieval.embeddings import MiniLMEmbeddings

try:
    import chromadb
    HAS_CHROMADB = True
except Exception:
    HAS_CHROMADB = False


@dataclass(frozen=True)
class SearchResult:
    paper_id: str
    title: str
    score: float
    content: str
    metadata: dict[str, Any]


class LocalEmbeddingIndex:
    def __init__(
        self,
        settings: Settings,
        collection_name: str,
        documents: list[dict[str, Any]],
        persist_path: Path,
        embeddings: list[list[float]] | None = None,
    ):
        self.settings = settings
        self.collection_name = collection_name
        self.documents = documents
        self.persist_path = persist_path
        self.embedding_backend = "chroma" if HAS_CHROMADB else "local_vector_index"
        self.embedding_model = MiniLMEmbeddings(settings.embedding_model)

        self.client = None
        self.collection = None
        if HAS_CHROMADB:
            try:
                self.client = chromadb.PersistentClient(path=str(persist_path))
                self.collection = self.client.get_collection(name=collection_name)
            except Exception:
                self.embedding_backend = "local_vector_index"

        self.cached_embeddings = embeddings
        if self.cached_embeddings is None:
            self.cached_embeddings = [doc.get("embedding", []) for doc in documents]
            if not any(self.cached_embeddings):
                self.cached_embeddings = self.embedding_model.embed_documents([d["content"] for d in documents])

        self.documents_by_paper_id = {document["paper_id"].lower(): document for document in documents}
        self.documents_by_title = {document["title"].lower(): document for document in documents}

    @staticmethod
    def _build_documents(df: pd.DataFrame) -> list[dict[str, Any]]:
        records = df.to_dict(orient="records")
        documents: list[dict[str, Any]] = []
        for index, row in enumerate(records):
            documents.append(
                {
                    "record_id": f"{row['paper_id']}::{index}",
                    "paper_id": row["paper_id"],
                    "title": row["title"],
                    "content": row["text_for_embedding"],
                    "metadata": {
                        "paper_id": row["paper_id"],
                        "title": row["title"],
                        "published": row["published"],
                        "authors_joined": row["authors_joined"],
                        "categories_joined": row["categories_joined"],
                        "summary": row["summary"],
                        "abs_url": row["abs_url"],
                        "pdf_url": row["pdf_url"],
                    },
                }
            )
        return documents

    @staticmethod
    def _derive_collection_name(settings: Settings, embeddings_output_path: Path | None) -> str:
        if embeddings_output_path is None:
            return settings.baseline_collection_name

        name_map = {
            settings.paths.embeddings_json.resolve(): settings.baseline_collection_name,
            settings.paths.corrupted_embeddings_json.resolve(): settings.corrupted_collection_name,
            settings.paths.repaired_embeddings_json.resolve(): settings.repaired_collection_name,
        }
        resolved_path = embeddings_output_path.resolve()
        if resolved_path in name_map:
            return name_map[resolved_path]
        return safe_slug(embeddings_output_path.stem)

    @classmethod
    def build(
        cls,
        df: pd.DataFrame,
        settings: Settings,
        embeddings_output_path: Path | None = None,
    ) -> "LocalEmbeddingIndex":
        collection_name = cls._derive_collection_name(settings, embeddings_output_path)
        documents = cls._build_documents(df)
        persist_path = settings.paths.chroma_dir
        persist_path.mkdir(parents=True, exist_ok=True)

        embedding_model = MiniLMEmbeddings(settings.embedding_model)
        embeddings = embedding_model.embed_documents([document["content"] for document in documents])

        for doc, emb in zip(documents, embeddings):
            doc["embedding"] = emb

        if HAS_CHROMADB:
            try:
                client = chromadb.PersistentClient(path=str(persist_path))
                try:
                    client.delete_collection(name=collection_name)
                except Exception:
                    pass
                collection = client.create_collection(
                    name=collection_name,
                    configuration={"hnsw": {"space": "cosine"}},
                )
                collection.add(
                    ids=[document["record_id"] for document in documents],
                    embeddings=embeddings,
                    documents=[document["content"] for document in documents],
                    metadatas=[document["metadata"] for document in documents],
                )
            except Exception:
                pass

        manifest_path = embeddings_output_path or settings.paths.embeddings_json
        write_json(
            manifest_path,
            {
                "backend": "chroma" if HAS_CHROMADB else "local_vector_index",
                "embedding_model": settings.embedding_model,
                "persist_path": str(persist_path),
                "collection_name": collection_name,
                "documents": documents,
            },
        )
        return cls(
            settings=settings,
            collection_name=collection_name,
            documents=documents,
            persist_path=persist_path,
            embeddings=embeddings,
        )

    @classmethod
    def load(cls, settings: Settings, embeddings_path: Path | None = None) -> "LocalEmbeddingIndex":
        payload = read_json(embeddings_path or settings.paths.embeddings_json)
        documents = payload["documents"]
        embeddings = [doc.get("embedding", []) for doc in documents]
        return cls(
            settings=settings,
            collection_name=payload["collection_name"],
            documents=documents,
            persist_path=Path(payload["persist_path"]),
            embeddings=embeddings if any(embeddings) else None,
        )

    def search(self, query: str, top_k: int | None = None) -> list[SearchResult]:
        k = top_k or self.settings.top_k
        query_embedding = self.embedding_model.embed_query(query)

        if HAS_CHROMADB and self.collection is not None:
            try:
                results = self.collection.query(
                    query_embeddings=[query_embedding],
                    n_results=k,
                    include=["documents", "metadatas", "distances"],
                )
                ids = results.get("ids", [[]])[0]
                documents = results.get("documents", [[]])[0]
                metadatas = results.get("metadatas", [[]])[0]
                distances = results.get("distances", [[]])[0]

                scored: list[SearchResult] = []
                for record_id, content, metadata, distance in zip(ids, documents, metadatas, distances, strict=False):
                    if not record_id or not metadata or not content:
                        continue
                    scored.append(
                        SearchResult(
                            paper_id=str(metadata["paper_id"]),
                            title=str(metadata["title"]),
                            score=max(0.0, 1.0 - float(distance or 0.0)),
                            content=str(content),
                            metadata=dict(metadata),
                        )
                    )
                return scored
            except Exception:
                pass

        # Native vector similarity search fallback (Cosine Similarity)
        q_vec = np.array(query_embedding, dtype=np.float32)
        q_norm = np.linalg.norm(q_vec)
        if q_norm > 0:
            q_vec = q_vec / q_norm

        scored: list[SearchResult] = []
        for doc, emb in zip(self.documents, self.cached_embeddings):
            if not emb:
                continue
            d_vec = np.array(emb, dtype=np.float32)
            d_norm = np.linalg.norm(d_vec)
            if d_norm > 0:
                d_vec = d_vec / d_norm
            score = float(np.dot(q_vec, d_vec))
            scored.append(
                SearchResult(
                    paper_id=str(doc["paper_id"]),
                    title=str(doc["title"]),
                    score=max(0.0, score),
                    content=str(doc["content"]),
                    metadata=dict(doc["metadata"]),
                )
            )

        scored.sort(key=lambda x: x.score, reverse=True)
        return scored[:k]

    def lookup(self, value: str) -> dict[str, Any] | None:
        needle = value.strip().lower()
        if needle in self.documents_by_paper_id:
            return self.documents_by_paper_id[needle]
        if needle in self.documents_by_title:
            return self.documents_by_title[needle]
        return None

