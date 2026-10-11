import time
from app.workflows.research_graph import research_graph, ResearchState
from app.core import logger
from typing import Dict, Optional


class ResearchService:
    """Service for executing research workflows."""
    
    async def execute_research(
        self,
        query: str,
        bypass_cache: bool = False,
        user_id: Optional[int] = None,
        session_id: Optional[int] = None
    ) -> Dict:
        """
        Execute research workflow for a query with caching and persistent memory.
        
        Args:
            query: User query
            bypass_cache: Force fresh computation
            user_id: Optional user identifier
            session_id: Optional session identifier
        
        Returns:
            Research result dictionary
        """
        try:
            from app.core.observability import trace_span, metrics, get_current_trace_id
            from app.services.cache import cache_service
            from app.services.memory import memory_service

            logger.info(f"Starting research for query: {query}")
            cache_key = cache_service.build_key("research", query, user_id=user_id)

            # Update session context with any companies discussed in query
            if session_id:
                for comp in memory_service.extract_companies_from_query(query):
                    memory_service.update_session_context(session_id, company=comp)

            # Check cache if not bypassed
            if not bypass_cache:
                cached = await cache_service.get(cache_key)
                if cached and not cached.get("error"):
                    logger.info(f"Cache HIT for query: '{query[:40]}...' [key={cache_key}]")
                    cached["cached"] = True
                    cached["trace_id"] = get_current_trace_id()
                    return cached
            else:
                logger.info(f"Bypassing cache as requested for query: '{query[:40]}...'")

            # Incorporate persistent memory context (preferences, previous session context)
            memory_context = memory_service.build_memory_prompt_context(query, user_id=user_id, session_id=session_id)
            effective_query = f"{query}\n{memory_context}" if memory_context else query

            # Initialize state
            initial_state: ResearchState = {
                "query": effective_query,
                "route": "",
                "route_reason": "",
                "tasks": [],
                "completed_tasks": [],
                "all_findings": [],
                "search_results": [],
                "evidence": [],
                "draft_answer": "",
                "final_answer": "",
                "sources": [],
                "critique": {},
                "retry_count": 0,
                "result": {},
                "error": ""
            }
            
            # Execute graph
            start_time = time.time()
            
            with trace_span("workflow:research") as span:
                final_state = await research_graph.ainvoke(initial_state)
            
            duration_ms = (time.time() - start_time) * 1000
            metrics.record_workflow(duration_ms)
            
            # Check for errors
            if final_state.get("error"):
                logger.error(f"Research failed: {final_state['error']}")
                metrics.record_error("research_workflow", "WorkflowError")
                return {
                    "answer": f"Research failed: {final_state['error']}",
                    "evidence": [],
                    "sources": [],
                    "route": final_state.get("route", "UNKNOWN"),
                    "error": final_state["error"],
                    "trace_id": get_current_trace_id(),
                    "duration_ms": round(duration_ms, 2)
                }
            
            # Return result
            result = final_state.get("result", {})
            result["trace_id"] = get_current_trace_id()
            result["duration_ms"] = round(duration_ms, 2)
            
            # Store in cache
            if result and not result.get("error"):
                tier = final_state.get("route", "DEFAULT")
                ttl = cache_service.get_ttl_for_tier(tier)
                await cache_service.set(cache_key, result, ttl_seconds=ttl)
                logger.info(f"Cached research result for query: '{query[:40]}...' [ttl={ttl}s]")

            # Record in persistent research history
            try:
                answer_summary = str(result.get("answer", ""))[:300]
                memory_service.record_research_history(
                    query=query,
                    route=final_state.get("route", "UNKNOWN"),
                    summary=answer_summary,
                    sources_count=len(result.get("sources", [])),
                    user_id=user_id,
                    session_id=session_id
                )
            except Exception as e:
                logger.warning(f"Could not record persistent research history: {e}")
            
            logger.info(f"Research completed successfully via {final_state.get('route', 'UNKNOWN')} tier in {round(duration_ms, 2)}ms")
            
            return result
            
        except Exception as e:
            logger.error(f"Research execution failed: {e}")
            raise


# Global research service instance
research_service = ResearchService()
