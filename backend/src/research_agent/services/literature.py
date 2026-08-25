import asyncio
import json
import time
from typing import List, Optional, Sequence, Tuple

from pydantic import TypeAdapter
from sqlalchemy.orm import Session

from research_agent.db.models import Artifact
from research_agent.repositories.artifacts import ArtifactRepository
from research_agent.schemas.literature import (
    ArxivPaper,
    CandidateProvenance,
    LiteratureDiscoveryResult,
    LiteratureQuery,
    LiteratureQueryExecution,
    RecommendationItem,
    RecommendedPaper,
)
from research_agent.services.arxiv_search import ArxivSearchProvider
from research_agent.services.model_call_logging import record_model_call
from research_agent.services.model_gateway import ModelGateway, collect_chat
from research_agent.services.structured_output import extract_json, validate_structured


QUERY_PLANNER_SYSTEM_PROMPT = """你是一名严谨的学术文献检索策略专家。请根据用户输入生成英文文献检索计划。

首先判断主题是否宽泛。如果主题已经包含明确的方法、研究对象、应用场景或其他实质性约束，设置 is_broad=false，只生成核心检索式；仅在同义词确有必要时补充不超过2条聚焦子查询，不得擅自扩大范围。

如果主题宽泛，设置 is_broad=true，并生成：
1. 一条准确表达用户核心主题的英文 core_query；
2. 4至7条互补的 subqueries，从该领域真实存在且具有代表性的理论路线、统计方法、机器学习方法、数据结构或典型研究范式展开。

扩展方向必须由用户主题动态决定，不得机械套用固定热门技术。每条子查询必须保留原始核心主题，方向之间应有明确差异。使用适合 arXiv 的英文术语以及 AND、OR 和英文双引号。不得虚构用户未提出的应用场景、数据集、时间范围或性能约束。

只输出 JSON，不要解释，严格使用以下结构：
{
  "is_broad": true,
  "core_query": "English query",
  "subqueries": [
    {"label": "方向名称", "english_query": "English query"}
  ]
}"""

RRF_K = 60
CORE_QUERY_WEIGHT = 1.25
DEFAULT_MAX_FUSED_CANDIDATES = 40
SearchSpec = Tuple[str, str, float]


class LiteratureDiscoveryService:
    def __init__(
        self,
        model_gateway: ModelGateway,
        arxiv_provider: ArxivSearchProvider,
        db: Optional[Session] = None,
        project_id: Optional[str] = None,
        max_fused_candidates: int = DEFAULT_MAX_FUSED_CANDIDATES,
    ) -> None:
        self.model_gateway = model_gateway
        self.arxiv_provider = arxiv_provider
        self.db = db
        self.project_id = project_id
        self.max_fused_candidates = max(10, min(max_fused_candidates, 100))

    async def discover(self, topic: str) -> LiteratureDiscoveryResult:
        query_plan = await self._generate_query_plan(topic)
        search_specs = [
            ("核心主题", query_plan.core_query, CORE_QUERY_WEIGHT),
            *[
                (item.label, item.english_query, 1.0)
                for item in query_plan.subqueries
            ],
        ]
        search_batches = await asyncio.gather(
            *[
                self.arxiv_provider.search(english_query)
                for _, english_query, _ in search_specs
            ]
        )
        candidates, provenance = _fuse_search_results(
            search_specs,
            search_batches,
            limit=self.max_fused_candidates,
        )
        query_executions = [
            LiteratureQueryExecution(
                label=label,
                english_query=english_query,
                result_count=len(batch),
            )
            for (label, english_query, _), batch in zip(
                search_specs,
                search_batches,
            )
        ]
        recommendations = await self._recommend(topic, candidates)
        return LiteratureDiscoveryResult(
            query=query_plan.core_query,
            query_plan=query_plan,
            query_executions=query_executions,
            candidates=candidates,
            candidate_provenance=provenance,
            recommendations=recommendations,
        )

    async def discover_with_artifact(
        self,
        topic: str,
    ) -> tuple[LiteratureDiscoveryResult, Optional[Artifact]]:
        """Discover papers and generate a structured literature card artifact."""
        result = await self.discover(topic)
        artifact = None
        if self.db is not None and self.project_id is not None and result.recommendations:
            artifact = await self._generate_card_artifact(topic, result)
        return result, artifact

    async def _generate_query_plan(self, topic: str) -> LiteratureQuery:
        started = time.perf_counter()
        try:
            response = await collect_chat(
                self.model_gateway,
                [
                    {"role": "system", "content": QUERY_PLANNER_SYSTEM_PROMPT},
                    {"role": "user", "content": f"用户主题：{topic}"},
                ],
            )
            query_plan = LiteratureQuery.model_validate(extract_json(response))
            record_model_call(
                self.db,
                "literature_query_plan",
                self.model_gateway.model_name,
                started,
                0,
                True,
            )
            return query_plan
        except Exception as exc:
            record_model_call(
                self.db,
                "literature_query_plan",
                self.model_gateway.model_name,
                started,
                0,
                False,
                exc,
            )
            raise

    async def _recommend(
        self,
        topic: str,
        candidates,
    ) -> List[RecommendedPaper]:
        if not candidates:
            return []

        candidate_payload = [
            {
                "arxiv_id": paper.arxiv_id,
                "title": paper.title,
                "abstract": paper.abstract[:800],
            }
            for paper in candidates
        ]
        prompt = (
            "从候选文献中推荐最相关的 5 到 10 篇。"
            "只能使用提供的论文 ID。"
            "只输出 JSON 数组，每项包含 arxiv_id、reason、"
            "purpose_labels。"
            f"\n用户主题：{topic}"
            f"\n候选文献：{json.dumps(candidate_payload, ensure_ascii=False)}"
        )
        adapter = TypeAdapter(List[RecommendationItem])
        started = time.perf_counter()
        try:
            result = await validate_structured(
                gateway=self.model_gateway,
                prompt=prompt,
                validator=adapter.validate_python,
                fallback=[],
            )
            record_model_call(
                self.db,
                "literature_recommendation",
                self.model_gateway.model_name,
                started,
                result.retries,
                True,
            )
            items = result.value
        except Exception as exc:
            record_model_call(
                self.db,
                "literature_recommendation",
                self.model_gateway.model_name,
                started,
                0,
                False,
                exc,
            )
            raise

        candidate_by_id = {
            paper.arxiv_id: paper
            for paper in candidates
        }
        selected = []
        used = set()
        for item in items:
            paper = candidate_by_id.get(item.arxiv_id)
            if paper is None or item.arxiv_id in used:
                continue
            selected.append(
                RecommendedPaper(
                    paper=paper,
                    reason=item.reason,
                    purpose_labels=item.purpose_labels,
                )
            )
            used.add(item.arxiv_id)
            if len(selected) == 10:
                return selected

        target = min(5, len(candidates))
        for paper in candidates:
            if len(selected) >= target:
                break
            if paper.arxiv_id in used:
                continue
            selected.append(
                RecommendedPaper(
                    paper=paper,
                    reason="该文献与当前检索主题相关，建议进一步查看摘要。",
                    purpose_labels=["相关文献"],
                )
            )
            used.add(paper.arxiv_id)
        return selected

    async def _generate_card_artifact(
        self,
        topic: str,
        result: LiteratureDiscoveryResult,
    ) -> Optional[Artifact]:
        """Generate a structured literature card artifact from discovered papers."""
        if not result.recommendations or not self.db or not self.project_id:
            return None

        from research_agent.services.paper_analysis import LiteratureCard

        payload = [
            {
                "arxiv_id": r.paper.arxiv_id,
                "title": r.paper.title,
                "abstract": r.paper.abstract[:600],
                "reason": r.reason,
            }
            for r in result.recommendations[:5]
        ]
        prompt = (
            "You are a research advisor. Based on the user's research topic and recommended papers, "
            "generate a concise literature card (文献卡片) in Chinese.\n"
            "Use the supplied paper information only. Return JSON only with keys: "
            "research_topic, research_question, method, contribution, risks.\n"
            "- research_topic: 研究主题（3-10字）\n"
            "- research_question: 核心研究问题（1-2句话）\n"
            "- method: 主要研究方法（1-3句话）\n"
            "- contribution: 主要贡献和创新点（1-3句话）\n"
            "- risks: 研究局限或风险（列出2-3条）\n"
            f"\nUser topic: {topic}\n"
            f"\nRecommended papers: {json.dumps(payload, ensure_ascii=False)}"
        )
        fallback = LiteratureCard(
            research_topic=topic[:20],
            research_question="基于检索结果的主题分析",
            method="综合多篇文献的方法论概述",
            contribution="详见推荐文献原文",
            risks=["文献数量有限，建议进一步扩大检索范围"],
        )
        started = time.perf_counter()
        try:
            cls_result = await validate_structured(
                gateway=self.model_gateway,
                prompt=prompt,
                validator=LiteratureCard.model_validate,
                fallback=fallback,
            )
            record_model_call(
                self.db,
                "literature_card",
                self.model_gateway.model_name,
                started,
                cls_result.retries,
                True,
            )
            card = cls_result.value
        except Exception as exc:
            record_model_call(
                self.db,
                "literature_card",
                self.model_gateway.model_name,
                started,
                0,
                False,
                exc,
            )
            card = fallback

        evidence_lines = "\n".join(
            f"- {r.paper.title} ({r.paper.arxiv_id})：{r.reason}"
            for r in result.recommendations[:5]
        )
        markdown = (
            f"# 文献卡片\n\n"
            f"## 研究主题\n\n{card.research_topic}\n\n"
            f"## 核心研究问题\n\n{card.research_question}\n\n"
            f"## 主要研究方法\n\n{card.method}\n\n"
            f"## 主要贡献\n\n{card.contribution}\n\n"
            f"## 研究风险与局限\n\n"
            + "\n".join(f"- {r}" for r in card.risks)
            + f"\n\n## 推荐文献\n\n{evidence_lines}\n"
        )
        content = card.model_dump()
        content["query"] = result.query
        content["query_plan"] = result.query_plan.model_dump()
        content["query_executions"] = [
            item.model_dump() for item in result.query_executions
        ]
        content["recommendations"] = [
            {
                "arxiv_id": r.paper.arxiv_id,
                "title": r.paper.title,
                "reason": r.reason,
            }
            for r in result.recommendations
        ]
        return ArtifactRepository(self.db).create_artifact(
            project_id=self.project_id,
            artifact_type="literature_card",
            title=f"文献卡片：{card.research_topic or topic[:20]}",
            content=content,
            markdown=markdown,
        )


class LocalLiteratureDiscoveryService:
    """Model-free paper discovery for privacy-local operation."""

    def __init__(self, arxiv_provider: ArxivSearchProvider) -> None:
        self.arxiv_provider = arxiv_provider

    async def discover(self, topic: str) -> LiteratureDiscoveryResult:
        query = topic.strip()
        raw_candidates = await self.arxiv_provider.search(query)
        query_plan = LiteratureQuery(
            is_broad=False,
            core_query=query,
            subqueries=[],
        )
        candidates, provenance = _fuse_search_results(
            [("本地检索", query, 1.0)],
            [raw_candidates],
            limit=DEFAULT_MAX_FUSED_CANDIDATES,
        )
        recommendations = [
            RecommendedPaper(
                paper=paper,
                reason="本地模式下按检索顺序推荐，请人工核对摘要。",
                purpose_labels=["本地检索"],
            )
            for paper in candidates[:10]
        ]
        return LiteratureDiscoveryResult(
            query=query,
            query_plan=query_plan,
            query_executions=[
                LiteratureQueryExecution(
                    label="本地检索",
                    english_query=query,
                    result_count=len(raw_candidates),
                )
            ],
            candidates=candidates,
            candidate_provenance=provenance,
            recommendations=recommendations,
        )


def _fuse_search_results(
    search_specs: Sequence[SearchSpec],
    search_batches: Sequence[Sequence[ArxivPaper]],
    limit: int,
) -> tuple[List[ArxivPaper], List[CandidateProvenance]]:
    """Fuse ranked result lists with weighted Reciprocal Rank Fusion."""
    papers_by_id = {}
    scores = {}
    labels_by_id = {}
    first_seen = {}
    seen_counter = 0

    for (label, _, weight), papers in zip(search_specs, search_batches):
        seen_in_query = set()
        for rank, paper in enumerate(papers, start=1):
            arxiv_id = paper.arxiv_id
            if arxiv_id in seen_in_query:
                continue
            seen_in_query.add(arxiv_id)
            if arxiv_id not in papers_by_id:
                papers_by_id[arxiv_id] = paper
                first_seen[arxiv_id] = seen_counter
                seen_counter += 1
            scores[arxiv_id] = scores.get(arxiv_id, 0.0) + (
                weight / (RRF_K + rank)
            )
            labels_by_id.setdefault(arxiv_id, []).append(label)

    ranked_ids = sorted(
        papers_by_id,
        key=lambda arxiv_id: (-scores[arxiv_id], first_seen[arxiv_id]),
    )[:limit]
    candidates = [papers_by_id[arxiv_id] for arxiv_id in ranked_ids]
    provenance = [
        CandidateProvenance(
            arxiv_id=arxiv_id,
            matched_query_labels=labels_by_id[arxiv_id],
            rrf_score=scores[arxiv_id],
        )
        for arxiv_id in ranked_ids
    ]
    return candidates, provenance
