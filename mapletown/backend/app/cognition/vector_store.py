import asyncio
import logging
import threading

import chromadb

from app.cognition.embeddings import embedding_service
from app.core.config import get_settings

logger = logging.getLogger("mapletown.vector_store")

_COLLECTION = "memories"


class VectorStore:
    """Chroma 向量库封装：记忆向量的持久化与按居民的相关性检索。

    嵌入维度由 provider 决定；provider 切换（维度变化）时自动重建 collection。
    """

    def __init__(self) -> None:
        self._client: chromadb.ClientAPI | None = None
        self._collection = None
        self._lock = threading.Lock()

    def _ensure(self):
        if self._collection is not None:
            return self._collection
        with self._lock:
            if self._collection is not None:
                return self._collection
            settings = get_settings()
            if settings.chroma_dir == ":memory:":
                client = chromadb.EphemeralClient()
            else:
                client = chromadb.PersistentClient(path=settings.chroma_dir)
            dim = len(embedding_service.embed(["维度探测"])[0])
            existing = None
            for c in client.list_collections():
                name = c.name if hasattr(c, "name") else str(c)
                if name == _COLLECTION:
                    existing = c
                    break
            if existing is not None:
                meta = existing.metadata or {}
                if str(meta.get("embedding_dim")) != str(dim):
                    logger.warning(
                        "embedding dim changed (%s -> %s), rebuilding collection", meta.get("embedding_dim"), dim
                    )
                    client.delete_collection(_COLLECTION)
                    existing = None
            if existing is None:
                existing = client.get_or_create_collection(
                    name=_COLLECTION,
                    metadata={"hnsw:space": "cosine", "embedding_dim": dim},
                )
            self._client = client
            self._collection = existing
            return self._collection

    async def upsert(self, memories: list[dict]) -> int:
        """memories: [{"id": int, "resident_id": int, "content": str}]"""
        if not memories:
            return 0
        collection = await asyncio.to_thread(self._ensure)
        embeddings = await asyncio.to_thread(
            embedding_service.embed, [m["content"] for m in memories]
        )
        await asyncio.to_thread(
            collection.upsert,
            ids=[str(m["id"]) for m in memories],
            embeddings=embeddings,
            documents=[m["content"] for m in memories],
            metadatas=[{"resident_id": m["resident_id"], "memory_id": m["id"]} for m in memories],
        )
        return len(memories)

    async def query(self, resident_id: int, query_text: str, top_k: int = 32) -> list[dict]:
        """返回 [{"memory_id": int, "relevance": float}]，relevance ∈ [0,1]（cosine 相似度）。"""
        collection = await asyncio.to_thread(self._ensure)
        if collection.count() == 0:
            return []
        query_vec = await asyncio.to_thread(embedding_service.embed, [query_text])
        result = await asyncio.to_thread(
            collection.query,
            query_embeddings=query_vec,
            n_results=min(top_k, max(1, collection.count())),
            where={"resident_id": {"$eq": resident_id}},
            include=["metadatas", "distances"],
        )
        items: list[dict] = []
        ids = result.get("ids", [[]])[0]
        distances = result.get("distances", [[]])[0]
        metadatas = result.get("metadatas", [[]])[0]
        for mid, dist, meta in zip(ids, distances, metadatas):
            similarity = 1.0 - float(dist)
            items.append(
                {
                    "memory_id": int(meta.get("memory_id", mid)) if meta else int(mid),
                    "relevance": max(0.0, min(1.0, similarity)),
                }
            )
        return items

    def clear(self) -> None:
        with self._lock:
            if self._client is None:
                settings = get_settings()
                if settings.chroma_dir == ":memory:":
                    self._client = chromadb.EphemeralClient()
                else:
                    self._client = chromadb.PersistentClient(path=settings.chroma_dir)
            try:
                self._client.delete_collection(_COLLECTION)
            except Exception:
                pass
            self._collection = None


vector_store = VectorStore()
