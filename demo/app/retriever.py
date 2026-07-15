import json
import os
import pickle
import re
import threading
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from app.config import (
    BEFORE_FUSION_WEIGHT,
    BM25_TOP_K_PARAGRAPHS,
    BM25_WEIGHT,
    CORPUS_FILE,
    EMBED_BATCH_SIZE,
    EMBEDDING_MODEL_NAME,
    EMBEDDINGS_FILE,
    FAISS_INDEX_FILE,
    GRAPH_FILE,
    HUGGINGFACE_HUB_TOKEN,
    KG_RELATION_HOPS,
    KG_WEIGHT,
    MAX_CANDIDATE_PARAGRAPHS_BEFORE_RERANK,
    RERANK_BATCH_SIZE,
    RERANK_MODEL_NAME,
    RERANKER_MAX_LENGTH,
    RERANKER_WEIGHT,
    SEMANTIC_TOP_K_PARAGRAPHS,
    SEMANTIC_WEIGHT,
    TOP_K_CONTEXT,
    USE_HYBRID_RERANK_SCORE,
)


LAW_RELATION_EDGE_TYPES = {
    "REFERENCES",
    "AMENDS",
    "REPLACES",
    "DETAILS",
}

LAW_RELATION_WEIGHTS = {
    "DETAILS": 0.9,
    "REFERENCES": 0.9,
    "AMENDS": 0.9,
    "REPLACES": 0.9,
}

DEFAULT_LAW_RELATION_WEIGHT = 0.5
_word_tokenize = None


@dataclass(frozen=True)
class RetrievedContext:
    paragraph_id: str
    section_id: str
    score: float
    text: str


class RetrieverNotReadyError(RuntimeError):
    pass


def simple_tokenize(text: Any) -> List[str]:
    if text is None:
        return []

    normalized = str(text).lower()
    normalized = re.sub(r"[^\w\s]", " ", normalized, flags=re.UNICODE)
    normalized = re.sub(r"\s+", " ", normalized).strip()

    if not normalized:
        return []

    segmented_text = _word_tokenize(normalized, format="text")

    return segmented_text.split()


def extract_section_id(paragraph_id: str) -> str:
    match = re.match(r"^(.+?)_para_\d+$", str(paragraph_id))
    return match.group(1) if match else str(paragraph_id)


def extract_law_id(section_id: str) -> str:
    match = re.match(r"^(.+?)\+\d+$", str(section_id))
    return match.group(1) if match else str(section_id)


def get_edge_attr(graph: Any, source: str, target: str) -> Mapping[str, Any]:
    data = graph.get_edge_data(source, target, default={}) or {}

    if (
        data
        and "edge_type" not in data
        and "relationship_type" not in data
        and "label" not in data
        and "type" not in data
        and all(isinstance(value, dict) for value in data.values())
    ):
        return next(iter(data.values()), {})

    return data


def get_edge_type(edge_attr: Mapping[str, Any]) -> Optional[str]:
    edge_type = (
        edge_attr.get("edge_type")
        or edge_attr.get("relationship_type")
        or edge_attr.get("label")
        or edge_attr.get("type")
    )
    return str(edge_type).upper() if edge_type else None


def update_score(scores: Dict[str, float], key: str, score: float) -> None:
    if score > scores.get(key, float("-inf")):
        scores[key] = float(score)


def paragraph_info(
    embeddings_dict: Mapping[Any, Any],
    paragraph_id: str,
) -> Mapping[str, Any]:
    info = embeddings_dict.get(paragraph_id)
    if info is None and paragraph_id.isdigit():
        info = embeddings_dict.get(int(paragraph_id))
    return info if isinstance(info, Mapping) else {}


def paragraph_text(
    embeddings_dict: Mapping[Any, Any],
    paragraph_id: str,
) -> str:
    info = paragraph_info(embeddings_dict, paragraph_id)
    parts = (
        info.get("section_title", ""),
        info.get("label", ""),
        info.get("content", ""),
    )
    return "\n".join(
        part.strip() for part in parts if isinstance(part, str) and part.strip()
    )


def build_maps(
    section_ids: Sequence[str],
    paragraph_ids: Sequence[str],
) -> Tuple[Dict[str, List[str]], Dict[str, List[str]]]:
    section_to_paragraphs = defaultdict(list)
    law_to_sections = defaultdict(list)
    seen_law_sections = defaultdict(set)

    for paragraph_id in paragraph_ids:
        section_id = extract_section_id(paragraph_id)
        law_id = extract_law_id(section_id)
        section_to_paragraphs[section_id].append(paragraph_id)

        if section_id not in seen_law_sections[law_id]:
            law_to_sections[law_id].append(section_id)
            seen_law_sections[law_id].add(section_id)

    for section_id in section_ids:
        law_id = extract_law_id(section_id)
        if section_id not in seen_law_sections[law_id]:
            law_to_sections[law_id].append(section_id)
            seen_law_sections[law_id].add(section_id)

    return dict(section_to_paragraphs), dict(law_to_sections)


def load_corpus_jsonl(path: Path) -> List[str]:
    section_ids = []

    with path.open("r", encoding="utf-8") as corpus_file:
        for line in corpus_file:
            if not line.strip():
                continue
            item = json.loads(line)
            section_ids.append(str(item["_id"]))

    return section_ids


def build_section_ids_from_paragraphs(
    embeddings_dict: Mapping[Any, Any],
    paragraph_ids: Sequence[str],
) -> List[str]:
    section_ids = []
    seen_sections = set()

    for paragraph_id in paragraph_ids:
        section_id = extract_section_id(paragraph_id)
        if section_id not in seen_sections:
            section_ids.append(section_id)
            seen_sections.add(section_id)

    return section_ids


def build_paragraph_bm25_corpus(
    embeddings_dict: Mapping[Any, Any],
    paragraph_ids: Sequence[str],
) -> List[List[str]]:
    return [
        simple_tokenize(paragraph_text(embeddings_dict, paragraph_id))
        for paragraph_id in paragraph_ids
    ]


def load_knowledge_graph(path: Path, networkx_module: Any) -> Any:
    suffix = path.suffix.lower()
    if suffix == ".graphml":
        return networkx_module.read_graphml(path)

    if suffix != ".json":
        raise ValueError(f"Unsupported graph format: {path}")

    with path.open("r", encoding="utf-8") as graph_file:
        data = json.load(graph_file)

    graph = networkx_module.DiGraph()
    for node_data in data.get("nodes", []):
        attrs = dict(node_data)
        if "id" not in attrs:
            continue
        node_id = str(attrs.pop("id"))
        graph.add_node(node_id, **attrs)

    for edge_data in data.get("edges", []):
        attrs = dict(edge_data)
        if "source" not in attrs or "target" not in attrs:
            continue
        source = str(attrs.pop("source"))
        target = str(attrs.pop("target"))
        graph.add_edge(source, target, **attrs)

    return graph


def load_paragraph_vector_store(
    embeddings_file: Path,
    faiss_index_file: Path,
    faiss_module: Any,
) -> Tuple[Mapping[Any, Any], List[str], Any]:
    with embeddings_file.open("rb") as vector_file:
        embeddings_data = pickle.load(vector_file)

    if not isinstance(embeddings_data, Mapping):
        raise ValueError("The embeddings pickle must contain a mapping")

    try:
        embeddings_dict = embeddings_data["embeddings_dict"]
        paragraph_ids = [str(pid) for pid in embeddings_data["paragraph_ids"]]
    except KeyError as exc:
        raise ValueError(
            f"The embeddings pickle is missing required key: {exc.args[0]}"
        ) from exc

    index = faiss_module.read_index(str(faiss_index_file))
    if index.ntotal != len(paragraph_ids):
        raise ValueError(
            f"FAISS index has {index.ntotal} vectors but the pickle has "
            f"{len(paragraph_ids)} paragraph ids"
        )

    return embeddings_dict, paragraph_ids, index


def _successors(graph: Any, node_id: str) -> Iterable[str]:
    if hasattr(graph, "successors"):
        return graph.successors(node_id)
    return graph.neighbors(node_id)


def get_parent_law(graph: Any, section_id: str) -> str:
    if section_id not in graph:
        return extract_law_id(section_id)

    node_type = str(graph.nodes[section_id].get("node_type", "")).upper()
    if node_type == "LAW":
        return section_id

    predecessors = (
        graph.predecessors(section_id)
        if hasattr(graph, "predecessors")
        else graph.neighbors(section_id)
    )
    for predecessor in predecessors:
        edge_type = get_edge_type(
            get_edge_attr(graph, predecessor, section_id)
        )
        predecessor_type = str(
            graph.nodes[predecessor].get("node_type", "")
        ).upper()
        if predecessor_type == "LAW" and edge_type == "HAS_SECTION":
            return str(predecessor)

    return extract_law_id(section_id)


def iter_law_sections(
    graph: Any,
    law_id: str,
    law_to_sections: Mapping[str, Sequence[str]],
) -> Iterable[str]:
    if law_id in law_to_sections:
        yield from law_to_sections[law_id]
        return

    if law_id not in graph:
        return

    for child in _successors(graph, law_id):
        edge_type = get_edge_type(get_edge_attr(graph, law_id, child))
        node_type = str(graph.nodes[child].get("node_type", "")).upper()
        if node_type == "SECTION" and edge_type == "HAS_SECTION":
            yield str(child)


def iter_related_laws(graph: Any, law_id: str) -> Iterable[Tuple[str, float]]:
    if law_id not in graph:
        return

    for target in _successors(graph, law_id):
        if target not in graph:
            continue
        edge_type = get_edge_type(get_edge_attr(graph, law_id, target))
        node_type = str(graph.nodes[target].get("node_type", "")).upper()
        if node_type != "LAW":
            continue
        if edge_type and edge_type not in LAW_RELATION_EDGE_TYPES:
            continue
        yield (
            str(target),
            LAW_RELATION_WEIGHTS.get(
                edge_type,
                DEFAULT_LAW_RELATION_WEIGHT,
            ),
        )

    if not hasattr(graph, "predecessors"):
        return

    for source in graph.predecessors(law_id):
        if source not in graph:
            continue
        edge_type = get_edge_type(get_edge_attr(graph, source, law_id))
        node_type = str(graph.nodes[source].get("node_type", "")).upper()
        if node_type != "LAW":
            continue
        if edge_type and edge_type not in LAW_RELATION_EDGE_TYPES:
            continue
        yield (
            str(source),
            LAW_RELATION_WEIGHTS.get(
                edge_type,
                DEFAULT_LAW_RELATION_WEIGHT,
            ),
        )


def section_scores_to_paragraph_scores(
    section_scores: Mapping[str, float],
    section_to_paragraphs: Mapping[str, Sequence[str]],
) -> Dict[str, float]:
    paragraph_scores: Dict[str, float] = {}
    for section_id, section_score in section_scores.items():
        for paragraph_id in section_to_paragraphs.get(section_id, ()):
            update_score(paragraph_scores, paragraph_id, section_score)
    return paragraph_scores


def aggregate_paragraph_scores_to_sections(
    paragraph_scores: Mapping[str, float],
) -> Dict[str, float]:
    section_scores: Dict[str, float] = {}
    for paragraph_id, score in paragraph_scores.items():
        update_score(section_scores, extract_section_id(paragraph_id), score)
    return section_scores


def normalize_score_dict(
    scores: Mapping[str, float],
) -> Dict[str, float]:
    if not scores:
        return {}

    min_value = min(float(value) for value in scores.values())
    max_value = max(float(value) for value in scores.values())
    if abs(max_value - min_value) < 1e-12:
        return {key: 1.0 for key in scores}

    scale = max_value - min_value
    return {
        key: (float(value) - min_value) / scale
        for key, value in scores.items()
    }


def expand_kg_section_scores(
    graph: Any,
    seed_section_scores: Mapping[str, float],
    law_to_sections: Mapping[str, Sequence[str]],
    relation_hops: int = KG_RELATION_HOPS,
) -> Dict[str, float]:
    kg_scores: Dict[str, float] = {}
    law_scores: Dict[str, float] = {}

    for section_id, score in seed_section_scores.items():
        update_score(
            law_scores,
            get_parent_law(graph, section_id),
            score,
        )

    frontier = dict(law_scores)
    visited_laws = set(frontier)

    for _ in range(max(0, relation_hops)):
        next_frontier: Dict[str, float] = {}
        for law_id, law_score in frontier.items():
            for related_law_id, relation_weight in iter_related_laws(
                graph,
                law_id,
            ):
                related_law_score = law_score * relation_weight
                for section_id in iter_law_sections(
                    graph,
                    related_law_id,
                    law_to_sections,
                ):
                    update_score(kg_scores, section_id, related_law_score)

                if related_law_id not in visited_laws:
                    update_score(
                        next_frontier,
                        related_law_id,
                        related_law_score,
                    )
                    visited_laws.add(related_law_id)

        frontier = next_frontier
        if not frontier:
            break

    return kg_scores


class LegalRetriever:
    def __init__(self) -> None:
        self.embedding_model = None
        self.reranker = None
        self.embeddings_dict = None
        self.paragraph_ids = None
        self.index = None
        self.graph = None
        self.bm25 = None
        self.section_ids = None
        self.section_to_paragraphs = None
        self.law_to_sections = None
        self.device = "cpu"
        self.load_error: Optional[str] = None
        self.corpus_source: Optional[str] = None
        self._faiss = None
        self._numpy = None
        self._load_lock = threading.Lock()

    @property
    def is_ready(self) -> bool:
        return all(
            item is not None
            for item in (
                self.embedding_model,
                self.reranker,
                self.embeddings_dict,
                self.paragraph_ids,
                self.index,
                self.graph,
                self.bm25,
                self.section_ids,
                self.section_to_paragraphs,
                self.law_to_sections,
            )
        )

    def load(self) -> None:
        if self.is_ready:
            return

        with self._load_lock:
            if self.is_ready:
                return

            required_files = (
                EMBEDDINGS_FILE,
                FAISS_INDEX_FILE,
                GRAPH_FILE,
            )
            missing = [str(path) for path in required_files if not path.is_file()]
            if missing:
                self.load_error = "Missing retrieval data: " + ", ".join(missing)
                raise FileNotFoundError(self.load_error)

            try:
                os.environ.setdefault("TRANSFORMERS_NO_TF", "1")
                os.environ.setdefault("TRANSFORMERS_NO_FLAX", "1")
                if HUGGINGFACE_HUB_TOKEN:
                    os.environ.setdefault("HF_TOKEN", HUGGINGFACE_HUB_TOKEN)
                    os.environ.setdefault(
                        "HUGGINGFACE_HUB_TOKEN",
                        HUGGINGFACE_HUB_TOKEN,
                    )

                import faiss
                import networkx as nx
                import numpy as np
                import torch
                from rank_bm25 import BM25Okapi
                from sentence_transformers import (
                    CrossEncoder,
                    SentenceTransformer,
                )
                from underthesea import word_tokenize

                global _word_tokenize
                _word_tokenize = word_tokenize

                self.device = "cuda" if torch.cuda.is_available() else "cpu"
                self._faiss = faiss
                self._numpy = np

                self.embeddings_dict, self.paragraph_ids, self.index = (
                    load_paragraph_vector_store(
                        EMBEDDINGS_FILE,
                        FAISS_INDEX_FILE,
                        faiss,
                    )
                )

                if CORPUS_FILE.is_file():
                    self.section_ids = load_corpus_jsonl(CORPUS_FILE)
                    self.corpus_source = str(CORPUS_FILE)
                else:
                    self.section_ids = build_section_ids_from_paragraphs(
                        self.embeddings_dict,
                        self.paragraph_ids,
                    )
                    self.corpus_source = "paragraph embeddings fallback"

                self.bm25 = BM25Okapi(
                    build_paragraph_bm25_corpus(
                        self.embeddings_dict,
                        self.paragraph_ids,
                    )
                )
                self.section_to_paragraphs, self.law_to_sections = build_maps(
                    self.section_ids,
                    self.paragraph_ids,
                )
                self.graph = load_knowledge_graph(GRAPH_FILE, nx)

                self.embedding_model = SentenceTransformer(
                    EMBEDDING_MODEL_NAME,
                    device=self.device,
                )
                if self.device == "cuda":
                    self.embedding_model.half()

                self.reranker = CrossEncoder(
                    RERANK_MODEL_NAME,
                    max_length=RERANKER_MAX_LENGTH,
                    device=self.device,
                )
                if self.device == "cuda":
                    self.reranker.model.half()

                self.load_error = None
            except Exception as exc:
                self.load_error = str(exc)
                raise

    def _ensure_ready(self) -> None:
        if not self.is_ready:
            detail = self.load_error or "The retriever has not been loaded"
            raise RetrieverNotReadyError(detail)

    def embed_query(self, query: str) -> Any:
        self._ensure_ready()
        query_embedding = self.embedding_model.encode(
            [query],
            batch_size=EMBED_BATCH_SIZE,
            convert_to_numpy=True,
            show_progress_bar=False,
        ).astype(self._numpy.float32)
        self._faiss.normalize_L2(query_embedding)
        return query_embedding

    def semantic_retrieve_paragraph_scores(
        self,
        query_embedding: Any,
        top_k: int,
    ) -> Dict[str, float]:
        top_k = min(max(1, top_k), self.index.ntotal)
        distances, indices = self.index.search(query_embedding, top_k)

        scores: Dict[str, float] = {}
        for index_position, score in zip(indices[0], distances[0]):
            if index_position < 0:
                continue
            update_score(
                scores,
                self.paragraph_ids[int(index_position)],
                float(score),
            )
        return scores

    def bm25_retrieve_paragraph_scores(
        self,
        query: str,
        top_k: int,
    ) -> Dict[str, float]:
        query_tokens = simple_tokenize(query)
        if not query_tokens:
            return {}

        scores = self.bm25.get_scores(query_tokens)
        top_k = min(max(0, top_k), len(self.paragraph_ids))
        if top_k == 0:
            return {}

        candidate_indices = self._numpy.argpartition(
            scores,
            -top_k,
        )[-top_k:]
        ranked_indices = candidate_indices[
            self._numpy.argsort(scores[candidate_indices])[::-1]
        ]

        return {
            self.paragraph_ids[int(index)]: float(scores[index])
            for index in ranked_indices
            if float(scores[index]) > 0
        }

    def retrieve(
        self,
        query: str,
        semantic_top_k: int = SEMANTIC_TOP_K_PARAGRAPHS,
        bm25_top_k: int = BM25_TOP_K_PARAGRAPHS,
        relation_hops: int = KG_RELATION_HOPS,
        top_k_context: int = TOP_K_CONTEXT,
        max_rerank_candidates: int = (
            MAX_CANDIDATE_PARAGRAPHS_BEFORE_RERANK
        ),
    ) -> List[RetrievedContext]:
        self._ensure_ready()
        query = query.strip()
        if not query:
            return []

        semantic_raw = self.semantic_retrieve_paragraph_scores(
            self.embed_query(query),
            semantic_top_k,
        )
        bm25_raw = self.bm25_retrieve_paragraph_scores(
            query,
            bm25_top_k,
        )

        semantic_scores = normalize_score_dict(semantic_raw)
        bm25_scores = normalize_score_dict(bm25_raw)

        seed_paragraph_ids = set(semantic_scores) | set(bm25_scores)
        seed_paragraph_scores = {
            paragraph_id: (
                SEMANTIC_WEIGHT
                * semantic_scores.get(paragraph_id, 0.0)
                + BM25_WEIGHT
                * bm25_scores.get(paragraph_id, 0.0)
            )
            for paragraph_id in seed_paragraph_ids
        }
        seed_section_scores = aggregate_paragraph_scores_to_sections(
            seed_paragraph_scores
        )
        if not seed_section_scores:
            return []

        kg_section_raw = expand_kg_section_scores(
            self.graph,
            seed_section_scores,
            self.law_to_sections,
            relation_hops,
        )
        kg_paragraph_scores = section_scores_to_paragraph_scores(
            kg_section_raw,
            self.section_to_paragraphs,
        )

        candidate_ids = (
            set(semantic_scores)
            | set(bm25_scores)
            | set(kg_paragraph_scores)
        )
        fusion_scores = {
            paragraph_id: (
                SEMANTIC_WEIGHT
                * semantic_scores.get(paragraph_id, 0.0)
                + BM25_WEIGHT
                * bm25_scores.get(paragraph_id, 0.0)
                + KG_WEIGHT
                * kg_paragraph_scores.get(paragraph_id, 0.0)
            )
            for paragraph_id in candidate_ids
        }

        before_rerank_ids = sorted(
            fusion_scores,
            key=lambda paragraph_id: (
                fusion_scores[paragraph_id],
                paragraph_id,
            ),
            reverse=True,
        )
        before_rerank_ids = before_rerank_ids[
            : max(1, max_rerank_candidates)
        ]

        valid_ids = []
        cross_inputs = []
        for paragraph_id in before_rerank_ids:
            text = paragraph_text(self.embeddings_dict, paragraph_id)
            if text:
                valid_ids.append(paragraph_id)
                cross_inputs.append([query, text])

        if not cross_inputs:
            return [
                RetrievedContext(
                    paragraph_id=paragraph_id,
                    section_id=extract_section_id(paragraph_id),
                    score=float(fusion_scores[paragraph_id]),
                    text=paragraph_text(self.embeddings_dict, paragraph_id),
                )
                for paragraph_id in before_rerank_ids[: max(1, top_k_context)]
            ]

        rerank_scores = self.reranker.predict(
            cross_inputs,
            batch_size=RERANK_BATCH_SIZE,
            show_progress_bar=False,
        )
        normalized_rerank_scores = normalize_score_dict(
            {
                paragraph_id: float(score)
                for paragraph_id, score in zip(valid_ids, rerank_scores)
            }
        )

        if USE_HYBRID_RERANK_SCORE:
            final_scores = {
                paragraph_id: (
                    RERANKER_WEIGHT
                    * normalized_rerank_scores.get(paragraph_id, 0.0)
                    + BEFORE_FUSION_WEIGHT
                    * fusion_scores.get(paragraph_id, 0.0)
                )
                for paragraph_id in valid_ids
            }
        else:
            final_scores = normalized_rerank_scores

        ranked_ids = sorted(
            valid_ids,
            key=lambda paragraph_id: (
                final_scores[paragraph_id],
                paragraph_id,
            ),
            reverse=True,
        )

        return [
            RetrievedContext(
                paragraph_id=paragraph_id,
                section_id=extract_section_id(paragraph_id),
                score=float(final_scores[paragraph_id]),
                text=paragraph_text(self.embeddings_dict, paragraph_id),
            )
            for paragraph_id in ranked_ids[: max(1, top_k_context)]
        ]
