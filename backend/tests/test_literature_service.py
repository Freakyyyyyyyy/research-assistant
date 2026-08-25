import asyncio

import pytest
from pydantic import ValidationError

from research_agent.schemas.literature import (
    ArxivPaper,
    LiteratureQuery,
    LiteratureSubquery,
)
from research_agent.services.literature import LiteratureDiscoveryService


def make_paper(index: int) -> ArxivPaper:
    return ArxivPaper(
        arxiv_id=f"2401.0000{index}",
        title=f"Paper {index}",
        authors=[f"Author {index}"],
        abstract=f"Abstract {index}",
        published="2024-01-01",
        categories=["cs.AI"],
        entry_url=f"https://arxiv.org/abs/2401.0000{index}",
        pdf_url=f"https://arxiv.org/pdf/2401.0000{index}",
    )


class QueryMapProvider:
    def __init__(self, results_by_query):
        self.results_by_query = results_by_query
        self.queries = []

    async def search(self, query: str):
        self.queries.append(query)
        return self.results_by_query[query]


class ScriptedGateway:
    model_name = "fake"

    def __init__(self, responses) -> None:
        self.responses = [[response] for response in responses]

    async def stream_chat(self, messages):
        del messages
        for token in self.responses.pop(0):
            yield token


def test_broad_topic_executes_query_plan_and_fuses_duplicate_results() -> None:
    core = '"time series forecasting"'
    statistical = '"time series forecasting" AND (ARIMA OR "statistical model")'
    neural = '"time series forecasting" AND (LSTM OR GRU)'
    transformer = '"time series forecasting" AND transformer'
    state_space = '"time series forecasting" AND "state space model"'
    plan_response = (
        '{"is_broad":true,"core_query":"\\"time series forecasting\\"",'
        '"subqueries":['
        '{"label":"Statistical models","english_query":"\\"time series forecasting\\" AND (ARIMA OR \\"statistical model\\")"},'
        '{"label":"Recurrent networks","english_query":"\\"time series forecasting\\" AND (LSTM OR GRU)"},'
        '{"label":"Transformers","english_query":"\\"time series forecasting\\" AND transformer"},'
        '{"label":"State space models","english_query":"\\"time series forecasting\\" AND \\"state space model\\""}'
        ']}'
    )
    recommendation_response = (
        '[{"arxiv_id":"2401.00002","reason":"Covers multiple method families",'
        '"purpose_labels":["cross-method"]}]'
    )
    provider = QueryMapProvider(
        {
            core: [make_paper(1), make_paper(2), make_paper(3)],
            statistical: [make_paper(2), make_paper(4)],
            neural: [make_paper(2), make_paper(5)],
            transformer: [make_paper(1), make_paper(6)],
            state_space: [make_paper(7), make_paper(2)],
        }
    )

    async def run():
        service = LiteratureDiscoveryService(
            model_gateway=ScriptedGateway([plan_response, recommendation_response]),
            arxiv_provider=provider,
        )
        return await service.discover("时序预测")

    result = asyncio.run(run())

    assert set(provider.queries) == {
        core,
        statistical,
        neural,
        transformer,
        state_space,
    }
    assert result.query == core
    assert result.query_plan.is_broad is True
    assert len(result.query_executions) == 5
    assert len(result.candidates) == 7
    assert len({paper.arxiv_id for paper in result.candidates}) == 7
    assert result.candidates[0].arxiv_id == "2401.00002"
    assert result.recommendations[0].paper.arxiv_id == "2401.00002"


def test_specific_topic_uses_only_core_query() -> None:
    query = '"probabilistic load forecasting" AND transformer'
    plan_response = (
        '{"is_broad":false,'
        '"core_query":"\\"probabilistic load forecasting\\" AND transformer",'
        '"subqueries":[]}'
    )
    provider = QueryMapProvider({query: [make_paper(index) for index in range(1, 7)]})
    gateway = ScriptedGateway(
        [
            plan_response,
            '[{"arxiv_id":"2401.00001","reason":"Exact method and task match",'
            '"purpose_labels":["exact match"]}]',
        ]
    )

    result = asyncio.run(
        LiteratureDiscoveryService(gateway, provider).discover(
            "Transformer 概率负荷预测"
        )
    )

    assert provider.queries == [query]
    assert result.query_plan.is_broad is False
    assert len(result.query_executions) == 1
    assert len(result.recommendations) == 5


def test_broad_query_plan_requires_four_distinct_subqueries() -> None:
    with pytest.raises(ValidationError):
        LiteratureQuery(
            is_broad=True,
            core_query="time series forecasting",
            subqueries=[
                LiteratureSubquery(
                    label="Transformers",
                    english_query="transformer forecasting",
                ),
                LiteratureSubquery(
                    label="Duplicate",
                    english_query="Transformer Forecasting",
                ),
            ],
        )
