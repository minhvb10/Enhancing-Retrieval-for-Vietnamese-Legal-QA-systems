import os
from pathlib import Path

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

DATA_DIR = Path(os.getenv("LEGAL_QA_DATA_DIR", BASE_DIR / "data")).expanduser()

CORPUS_FILE = Path(
    os.getenv(
        "LEGAL_QA_CORPUS_FILE",
        DATA_DIR / "corpus_preprocessed_v2.jsonl",
    )
).expanduser()
EMBEDDINGS_FILE = Path(
    os.getenv("LEGAL_QA_EMBEDDINGS_FILE", DATA_DIR / "paragraph_embeddings.pkl")
).expanduser()
FAISS_INDEX_FILE = Path(
    os.getenv("LEGAL_QA_FAISS_INDEX_FILE", DATA_DIR / "paragraph_embeddings.faiss")
).expanduser()
GRAPH_FILE = Path(
    os.getenv("LEGAL_QA_GRAPH_FILE", DATA_DIR / "legal_kg_complete.json")
).expanduser()

EMBEDDING_MODEL_NAME = os.getenv("LEGAL_QA_EMBEDDING_MODEL", "BAAI/bge-m3")
RERANK_MODEL_NAME = os.getenv(
    "LEGAL_QA_RERANK_MODEL", "BAAI/bge-reranker-v2-m3"
)

EMBED_BATCH_SIZE = int(os.getenv("LEGAL_QA_EMBED_BATCH_SIZE", "32"))
SEMANTIC_TOP_K_PARAGRAPHS = int(
    os.getenv(
        "LEGAL_QA_SEMANTIC_TOP_K_PARAGRAPHS",
        os.getenv("LEGAL_QA_TOP_K_SEEDS", "80"),
    )
)
BM25_TOP_K_PARAGRAPHS = int(
    os.getenv(
        "LEGAL_QA_BM25_TOP_K_PARAGRAPHS",
        os.getenv("LEGAL_QA_BM25_TOP_K_SECTIONS", "30"),
    )
)
KG_RELATION_HOPS = int(
    os.getenv(
        "LEGAL_QA_KG_RELATION_HOPS",
        os.getenv("LEGAL_QA_M_HOPS", "1"),
    )
)
MAX_CANDIDATE_PARAGRAPHS_BEFORE_RERANK = int(
    os.getenv(
        "LEGAL_QA_MAX_CANDIDATE_PARAGRAPHS_BEFORE_RERANK",
        os.getenv("LEGAL_QA_MAX_RERANK_CANDIDATES", "200"),
    )
)
TOP_K_CONTEXT = int(os.getenv("LEGAL_QA_TOP_K_CONTEXT", "5"))

SEMANTIC_WEIGHT = float(os.getenv("LEGAL_QA_SEMANTIC_WEIGHT", "0.7"))
BM25_WEIGHT = float(os.getenv("LEGAL_QA_BM25_WEIGHT", "0.2"))
KG_WEIGHT = float(os.getenv("LEGAL_QA_KG_WEIGHT", "0.1"))

USE_HYBRID_RERANK_SCORE = os.getenv(
    "LEGAL_QA_USE_HYBRID_RERANK_SCORE", "false"
).lower() in {"1", "true", "yes", "on"}
RERANKER_WEIGHT = float(os.getenv("LEGAL_QA_RERANKER_WEIGHT", "0.7"))
BEFORE_FUSION_WEIGHT = float(
    os.getenv("LEGAL_QA_BEFORE_FUSION_WEIGHT", "0.3")
)
RERANKER_MAX_LENGTH = int(os.getenv("LEGAL_QA_RERANKER_MAX_LENGTH", "1024"))
RERANK_BATCH_SIZE = int(os.getenv("LEGAL_QA_RERANK_BATCH_SIZE", "256"))
HUGGINGFACE_HUB_TOKEN = (
    os.getenv("HUGGINGFACE_HUB_TOKEN")
    or os.getenv("HF_TOKEN")
    or os.getenv("HUGGING_FACE_HUB_TOKEN")
)

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen3:8b")
OLLAMA_TIMEOUT_SECONDS = int(os.getenv("OLLAMA_TIMEOUT_SECONDS", "180"))

TEMPERATURE = float(os.getenv("LEGAL_QA_TEMPERATURE", "0.2"))
TOP_P = float(os.getenv("LEGAL_QA_TOP_P", "0.9"))
MAX_CONTEXT_CHARS = int(os.getenv("LEGAL_QA_MAX_CONTEXT_CHARS", "12000"))
MAX_QUERY_CHARS = int(os.getenv("LEGAL_QA_MAX_QUERY_CHARS", "2000"))
SOURCE_PREVIEW_CHARS = int(os.getenv("LEGAL_QA_SOURCE_PREVIEW_CHARS", "1600"))

EAGER_LOAD = os.getenv("LEGAL_QA_EAGER_LOAD", "true").lower() in {
    "1",
    "true",
    "yes",
    "on",
}
