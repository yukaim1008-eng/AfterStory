from dataclasses import dataclass, field
from math import sqrt

from sqlalchemy import func, literal, or_, select

from afterstory.memory_contracts import ConservativeTokenCounter
from afterstory.models import MemoryIndexDocument, PersonalMemory


@dataclass(frozen=True)
class PreparedRuntimeContext:
    instance_id: str
    memory_items: list[dict] = field(default_factory=list)
    selected_ids: list[str] = field(default_factory=list)
    reasons: dict[str, str] = field(default_factory=dict)
    estimated_tokens: int = 0


def cosine(left, right):
    if not left or not right or len(left) != len(right):
        return 0.0
    denominator = sqrt(sum(value * value for value in left)) * sqrt(
        sum(value * value for value in right)
    )
    return (
        sum(a * b for a, b in zip(left, right, strict=True)) / denominator if denominator else 0.0
    )


class MemoryIndexService:
    def __init__(self, sessions, embedding_provider=None, embedding_version="none"):
        self.sessions = sessions
        self.embedding_provider = embedding_provider
        self.embedding_version = embedding_version

    def sync(self, memory_id):
        with self.sessions() as session:
            memory = session.get(PersonalMemory, memory_id)
            if not memory:
                return None
            content = memory.content or ""
            revision = memory.revision
            instance_id = memory.instance_id
            status = memory.status
        embedding = None
        if status == "active" and content and self.embedding_provider:
            vectors = self.embedding_provider.embed([content])
            if len(vectors) != 1:
                raise ValueError("embedding_count_mismatch")
            embedding = vectors[0]
        with self.sessions.begin() as session:
            for old in session.scalars(
                select(MemoryIndexDocument).where(
                    MemoryIndexDocument.memory_id == memory_id,
                    MemoryIndexDocument.status == "active",
                )
            ):
                old.status = "stale"
            if status != "active" or not content:
                return None
            existing = session.scalar(
                select(MemoryIndexDocument).where(
                    MemoryIndexDocument.memory_id == memory_id,
                    MemoryIndexDocument.memory_revision == revision,
                )
            )
            if existing:
                existing.status = "active"
                existing.embedding = embedding
                existing.embedding_version = self.embedding_version if embedding else None
                return existing.id
            document = MemoryIndexDocument(
                instance_id=instance_id,
                memory_id=memory_id,
                memory_revision=revision,
                document_type="memory",
                content=content,
                search_vector=func.to_tsvector("simple", content),
                embedding=embedding,
                embedding_version=self.embedding_version if embedding else None,
                status="active",
            )
            session.add(document)
            session.flush()
            return document.id


class RetrievalService:
    def __init__(
        self,
        sessions,
        embedding_provider=None,
        reranker=None,
        max_candidates=100,
        max_items=20,
        max_tokens=2000,
        token_counter=None,
    ):
        self.sessions = sessions
        self.embedding_provider = embedding_provider
        self.reranker = reranker
        self.max_candidates = max_candidates
        self.max_items = max_items
        self.max_tokens = max_tokens
        self.token_counter = token_counter or ConservativeTokenCounter()

    def prepare(self, instance_id, query):
        with self.sessions() as session:
            tsquery = func.websearch_to_tsquery("simple", query)
            rank = func.ts_rank_cd(MemoryIndexDocument.search_vector, tsquery)
            rows = list(
                session.execute(
                    select(MemoryIndexDocument, PersonalMemory, rank.label("text_rank"))
                    .join(PersonalMemory, PersonalMemory.id == MemoryIndexDocument.memory_id)
                    .where(
                        MemoryIndexDocument.instance_id == instance_id,
                        MemoryIndexDocument.status == "active",
                        PersonalMemory.status == "active",
                        PersonalMemory.revision == MemoryIndexDocument.memory_revision,
                        or_(
                            MemoryIndexDocument.search_vector.op("@@")(tsquery),
                            MemoryIndexDocument.content.ilike(f"%{query}%"),
                        ),
                    )
                    .order_by(rank.desc(), PersonalMemory.updated_at.desc())
                    .limit(self.max_candidates)
                )
            )
            if not rows:
                rows = list(
                    session.execute(
                        select(MemoryIndexDocument, PersonalMemory, literal(0.0))
                        .join(PersonalMemory, PersonalMemory.id == MemoryIndexDocument.memory_id)
                        .where(
                            MemoryIndexDocument.instance_id == instance_id,
                            MemoryIndexDocument.status == "active",
                            PersonalMemory.status == "active",
                            PersonalMemory.revision == MemoryIndexDocument.memory_revision,
                        )
                        .order_by(PersonalMemory.updated_at.desc())
                        .limit(min(self.max_candidates, 30))
                    )
                )
        query_vector = None
        if self.embedding_provider and rows:
            query_vector = self.embedding_provider.embed([query])[0]
        candidates = []
        for document, memory, text_rank in rows:
            vector_score = cosine(query_vector, document.embedding) if query_vector else 0.0
            candidates.append(
                {
                    "id": memory.id,
                    "kind": memory.memory_type,
                    "content": memory.content,
                    "score": float(text_rank or 0) + vector_score,
                    "reason": "fulltext+vector" if vector_score else "fulltext_or_recent",
                }
            )
        candidates.sort(key=lambda item: (-item["score"], item["id"]))
        if self.reranker and len(candidates) > 1:
            ranked = self.reranker.rerank(query, candidates)
            order = {item.candidate_id: index for index, item in enumerate(ranked.items)}
            candidates.sort(key=lambda item: order.get(item["id"], len(order)))
        selected = []
        used = 0
        for item in candidates:
            cost = self.token_counter.count(item["content"])
            if len(selected) >= self.max_items or used + cost > self.max_tokens:
                continue
            selected.append(item)
            used += cost
        return PreparedRuntimeContext(
            instance_id=instance_id,
            memory_items=[{"kind": item["kind"], "content": item["content"]} for item in selected],
            selected_ids=[item["id"] for item in selected],
            reasons={item["id"]: item["reason"] for item in selected},
            estimated_tokens=used,
        )
