from typing import List

from pydantic import BaseModel, Field, field_validator, model_validator


class ArxivPaper(BaseModel):
    arxiv_id: str
    title: str
    authors: List[str] = Field(default_factory=list)
    abstract: str
    published: str
    categories: List[str] = Field(default_factory=list)
    entry_url: str
    pdf_url: str


class RecommendedPaper(BaseModel):
    paper: ArxivPaper
    reason: str
    purpose_labels: List[str] = Field(default_factory=list)


class LiteratureSubquery(BaseModel):
    label: str = Field(min_length=1, max_length=80)
    english_query: str = Field(min_length=3, max_length=500)

    @field_validator("label", "english_query")
    @classmethod
    def normalize_text(cls, value: str) -> str:
        normalized = " ".join(value.split())
        if not normalized:
            raise ValueError("query fields cannot be blank")
        return normalized


class LiteratureQuery(BaseModel):
    is_broad: bool
    core_query: str = Field(min_length=3, max_length=500)
    subqueries: List[LiteratureSubquery] = Field(
        default_factory=list,
        max_length=7,
    )

    @field_validator("core_query")
    @classmethod
    def normalize_core_query(cls, value: str) -> str:
        return " ".join(value.split())

    @model_validator(mode="after")
    def validate_query_strategy(self):
        if self.is_broad and len(self.subqueries) < 4:
            raise ValueError("broad topics require 4 to 7 subqueries")
        if not self.is_broad and len(self.subqueries) > 2:
            raise ValueError("specific topics may use at most 2 focused subqueries")

        normalized_queries = [
            self.core_query.casefold(),
            *(item.english_query.casefold() for item in self.subqueries),
        ]
        if len(normalized_queries) != len(set(normalized_queries)):
            raise ValueError("query plan contains duplicate queries")
        return self


class LiteratureQueryExecution(BaseModel):
    label: str
    english_query: str
    result_count: int = Field(ge=0)


class CandidateProvenance(BaseModel):
    arxiv_id: str
    matched_query_labels: List[str] = Field(default_factory=list)
    rrf_score: float = Field(ge=0)


class RecommendationItem(BaseModel):
    arxiv_id: str
    reason: str
    purpose_labels: List[str] = Field(default_factory=list)


class LiteratureDiscoveryResult(BaseModel):
    query: str
    query_plan: LiteratureQuery
    query_executions: List[LiteratureQueryExecution] = Field(default_factory=list)
    candidates: List[ArxivPaper]
    candidate_provenance: List[CandidateProvenance] = Field(default_factory=list)
    recommendations: List[RecommendedPaper]
