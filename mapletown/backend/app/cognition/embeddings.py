import logging
import threading
import zlib

logger = logging.getLogger("mapletown.embeddings")

_FASTEMBED_MODEL = "BAAI/bge-small-zh-v1.5"
_HASHING_DIM = 1024


def _bigrams(text: str) -> list[str]:
    cleaned = "".join(ch for ch in text if ch.isalnum())
    if len(cleaned) < 2:
        return [cleaned] if cleaned else []
    return [cleaned[i : i + 2] for i in range(len(cleaned) - 1)]


class HashingEmbedding:
    """零依赖兜底嵌入：字符 bigram + TF + L2 归一化。

    全离线、确定性，中文短文本的词重叠相关性能用，但语义能力弱于神经模型。
    """

    def __init__(self, dim: int = _HASHING_DIM) -> None:
        self.dim = dim

    def embed(self, texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for text in texts:
            vec = [0.0] * self.dim
            for token in _bigrams(text):
                vec[zlib.crc32(token.encode("utf-8")) % self.dim] += 1.0
            norm = sum(x * x for x in vec) ** 0.5
            if norm > 0:
                vec = [x / norm for x in vec]
            vectors.append(vec)
        return vectors


class EmbeddingService:
    """统一嵌入入口：fastembed(bge-small-zh) 优先，失败降级到哈希嵌入。

    provider 一旦确定就不再切换（切换会导致向量维度不一致、检索失效）。
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.provider: str | None = None
        self.dim: int = 0
        self._model = None

    def _ensure_loaded(self) -> None:
        if self.provider is not None:
            return
        with self._lock:
            if self.provider is not None:
                return
            self.provider, self._model, self.dim = self._load()

    def _load(self) -> tuple[str, object, int]:
        settings_provider = _settings_provider()
        if settings_provider in ("auto", "fastembed"):
            try:
                from fastembed import TextEmbedding

                model = TextEmbedding(_FASTEMBED_MODEL)
                dim = len(next(iter(model.embed(["枫叶镇"]))))
                logger.info("embedding provider: fastembed(%s), dim=%s", _FASTEMBED_MODEL, dim)
                return "fastembed", model, dim
            except Exception as exc:
                logger.warning("fastembed unavailable, fallback to hashing embedding: %s", exc)
        logger.info("embedding provider: hashing, dim=%s", _HASHING_DIM)
        return "hashing", None, _HASHING_DIM

    def embed(self, texts: list[str]) -> list[list[float]]:
        self._ensure_loaded()
        if not texts:
            return []
        if self.provider == "fastembed":
            return [list(map(float, v)) for v in self._model.embed(texts)]
        return HashingEmbedding().embed(texts)


def _settings_provider() -> str:
    from app.core.config import get_settings

    return get_settings().embedding_provider


embedding_service = EmbeddingService()
