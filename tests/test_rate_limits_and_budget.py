"""
Unit and Integration Test Suite for Irium Multi-Agent Groq Optimization.
Built using standard library unittest and asyncio (no external pytest dependency).

Validates:
1. Simple query completes without unnecessary agent calls (0 LLM overhead when deterministic)
2. Complex financial query uses appropriate model (openai/gpt-oss-120b)
3. Document query does not repeatedly reprocess uploaded files
4. Multiple simultaneous requests respect global concurrency limit (Semaphore=2)
5. HTTP 429 triggers bounded backoff
6. Retry-After is respected when provided
7. HTTP 400 tool errors do not enter the rate-limit retry loop
8. Retry exhaustion returns controlled response / best answer
9. Graph cycles stop at configured iteration limit
10. Request budgets do not leak across users / requests
11. Verification / critique failure does not discard valid answer
12. Tool failure does not cause infinite graph loop
13. Frontend receives valid response or clear error
14. Existing API behavior remains compatible
"""

import sys
import os
import asyncio
import time
import unittest
from unittest.mock import AsyncMock, patch, MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.core.config import settings
from app.core.model_config import ModelConfig, TaskType
from app.core.budget import RequestBudget, start_request_budget, get_current_budget, BudgetExceededError
from app.services.rate_limiter import GlobalRateLimiter
from app.services.llm import LLMService


class TestGroqOptimization(unittest.IsolatedAsyncioTestCase):

    # 1. Simple query completes without unnecessary agent calls
    async def test_scenario_1_simple_query_routing(self):
        from app.agents.router import router_agent
        with patch.object(LLMService, "invoke") as mock_invoke:
            decision = await router_agent.route("What is EBITDA?")
            self.assertEqual(decision.route, "SIMPLE")
            self.assertEqual(mock_invoke.call_count, 0)

    # 2. Complex financial query uses appropriate model
    def test_scenario_2_complex_task_model_assignment(self):
        complex_model = ModelConfig.get_model_for_task(TaskType.SYNTHESIS_COMPLEX)
        self.assertEqual(complex_model, "openai/gpt-oss-120b")
        
        doc_reasoning_model = ModelConfig.get_model_for_task(TaskType.DOCUMENT_REASONING)
        self.assertEqual(doc_reasoning_model, "openai/gpt-oss-120b")

        standard_model = ModelConfig.get_model_for_task(TaskType.QA_STANDARD)
        self.assertEqual(standard_model, "openai/gpt-oss-20b")

    # 3. Document query does not repeatedly reprocess uploaded file
    async def test_scenario_3_document_query_caching(self):
        from app.agents.document_analysis import document_analysis_agent
        mock_retrieved_context = "Revenue in Q3 was $500M. Net profit was $50M [Page 2]."
        
        with patch("app.services.llm.llm_service.invoke", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = "According to [Page 2], Revenue was $500M and Net profit was $50M."
            result = await document_analysis_agent.analyze(
                query="What was net profit?",
                documents=None,
                retrieved_context=mock_retrieved_context,
                source_pages=[2]
            )
            self.assertIn("50M", result["answer"])
            self.assertEqual(mock_llm.call_count, 1)

    # 4. Multiple simultaneous requests respect global concurrency limit
    async def test_scenario_4_concurrency_limit(self):
        limiter = GlobalRateLimiter(max_concurrency=2, requests_per_minute=100)
        active_concurrent = 0
        max_observed_concurrent = 0
        lock = asyncio.Lock()
        
        async def worker():
            nonlocal active_concurrent, max_observed_concurrent
            await limiter.acquire()
            async with lock:
                active_concurrent += 1
                if active_concurrent > max_observed_concurrent:
                    max_observed_concurrent = active_concurrent
            await asyncio.sleep(0.04)
            async with lock:
                active_concurrent -= 1
            limiter.release()

        tasks = [asyncio.create_task(worker()) for _ in range(6)]
        await asyncio.gather(*tasks)
        self.assertLessEqual(max_observed_concurrent, 2)

    # 5 & 6. HTTP 429 triggers bounded backoff & respects Retry-After
    async def test_scenario_5_and_6_http_429_backoff_and_retry_after(self):
        service = LLMService()
        mock_llm_client = MagicMock()
        mock_llm_client.ainvoke = AsyncMock(side_effect=[
            Exception("Error code: 429 - Please try again in 0.1s."),
            MagicMock(content="Success after retry")
        ])
        
        with patch.object(service, "get_llm", return_value=mock_llm_client), \
             patch("app.services.llm.rate_limiter.acquire", new_callable=AsyncMock, return_value=0.0):
            start_t = time.time()
            response = await service.invoke("Sys", "User", model="openai/gpt-oss-20b")
            elapsed = time.time() - start_t
            self.assertEqual(response, "Success after retry")
            self.assertEqual(mock_llm_client.ainvoke.call_count, 2)
            self.assertGreaterEqual(elapsed, 0.1)

    # 7. HTTP 400 tool errors do not enter rate-limit retry loop
    async def test_scenario_7_http_400_tool_errors_do_not_retry_as_429(self):
        service = LLMService()
        client_400 = MagicMock()
        client_400.ainvoke = AsyncMock(side_effect=Exception(
            "Error code: 400 - {'error': {'message': 'Tool choice is none, but model called a tool', 'code': 'tool_use_failed'}}"
        ))
        client_fallback = MagicMock()
        client_fallback.ainvoke = AsyncMock(return_value=MagicMock(content="Fallback output"))

        def get_llm_side_effect(temperature=0.0, model=None, provider=None, max_tokens=None):
            if model == "openai/gpt-oss-20b":
                return client_400
            return client_fallback

        with patch.object(service, "get_llm", side_effect=get_llm_side_effect), \
             patch("app.services.llm.rate_limiter.acquire", new_callable=AsyncMock, return_value=0.0):
            response = await service.invoke("Sys", "User", model="openai/gpt-oss-20b")
            self.assertEqual(response, "Fallback output")
            self.assertEqual(client_400.ainvoke.call_count, 1)

    # 8. Retry exhaustion returns controlled response or best answer
    async def test_scenario_8_retry_exhaustion_best_answer(self):
        service = LLMService()
        budget = start_request_budget(request_id="req-test-8")
        budget.set_best_answer("Best previously generated draft")
        
        mock_failing_client = MagicMock()
        mock_failing_client.ainvoke = AsyncMock(side_effect=Exception("Error code: 429 - Rate limit reached"))

        with patch.object(service, "get_llm", return_value=mock_failing_client), \
             patch("app.services.llm.rate_limiter.acquire", new_callable=AsyncMock, return_value=0.0), \
             patch("asyncio.sleep", new_callable=AsyncMock):
            response = await service.invoke("Sys", "User", model="openai/gpt-oss-20b")
            self.assertEqual(response, "Best previously generated draft")

    # 9. Graph cycles stop at configured iteration limit
    def test_scenario_9_graph_iteration_limit(self):
        from app.workflows.research_graph import should_retry
        budget = start_request_budget(request_id="req-test-9")
        state = {
            "critique": {"is_acceptable": False, "quality_score": 0.4},
            "retry_count": 0
        }
        decision_1 = should_retry(state)
        self.assertEqual(decision_1, "retry")
        state["retry_count"] = 1
        decision_2 = should_retry(state)
        self.assertEqual(decision_2, "finalize")

    # 10. Request budgets do not leak across users/requests
    async def test_scenario_10_budget_isolation(self):
        budget_a_val = None
        budget_b_val = None
        
        async def task_a():
            nonlocal budget_a_val
            b_a = start_request_budget(request_id="user_a", max_llm_calls=3)
            b_a.record_llm_call()
            b_a.record_llm_call()
            await asyncio.sleep(0.01)
            budget_a_val = get_current_budget().llm_calls

        async def task_b():
            nonlocal budget_b_val
            b_b = start_request_budget(request_id="user_b", max_llm_calls=5)
            b_b.record_llm_call()
            await asyncio.sleep(0.01)
            budget_b_val = get_current_budget().llm_calls

        await asyncio.gather(task_a(), task_b())
        self.assertEqual(budget_a_val, 2)
        self.assertEqual(budget_b_val, 1)

    # 11. Verification / critique failure does not discard valid answer
    async def test_scenario_11_critique_failure_preserves_answer(self):
        from app.workflows.research_graph import critique_node
        state = {
            "query": "HDFC vs ICICI",
            "draft_answer": "Valid draft comparison answer",
            "evidence": [{"claim": "Evidence 1"}],
            "retry_count": 0
        }
        with patch("app.agents.critic.critic_agent.critique", side_effect=Exception("Critic LLM Failed")):
            new_state = await critique_node(state)
            self.assertEqual(new_state["draft_answer"], "Valid draft comparison answer")
            self.assertTrue(new_state["critique"]["is_acceptable"])

    # 12. Tool failure does not cause infinite graph loop
    async def test_scenario_12_tool_failure_resilience(self):
        from app.workflows.research_graph import search_node
        state = {
            "tasks": [{"task_id": 1, "description": "Search entity A", "search_query": "entity A"}],
            "all_findings": [],
            "completed_tasks": []
        }
        with patch("app.services.search.search_service.search", side_effect=Exception("Tavily down")):
            res_state = await search_node(state)
            self.assertEqual(len(res_state["all_findings"]), 0)

    # 13 & 14. Existing API & Frontend compatibility
    async def test_scenario_13_and_14_api_compatibility(self):
        from app.services.research import research_service
        mock_final_state = {
            "route": "SIMPLE",
            "result": {
                "answer": {
                    "sections": [{"type": "text", "title": "Definition", "content": "EBITDA explained"}]
                },
                "evidence": [],
                "sources": [],
                "route": "SIMPLE"
            },
            "error": ""
        }
        with patch("app.workflows.research_graph.research_graph.ainvoke", AsyncMock(return_value=mock_final_state)):
            result = await research_service.execute_research("What is EBITDA?", bypass_cache=True)
            self.assertIn("answer", result)
            self.assertIn("trace_id", result)
            self.assertIn("route", result)
            self.assertEqual(result["route"], "SIMPLE")


if __name__ == "__main__":
    unittest.main()
