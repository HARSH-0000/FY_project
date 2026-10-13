from typing import TypedDict, List, Dict, Annotated
import time
import asyncio
from langgraph.graph import StateGraph, END
from app.agents.router import router_agent
from app.agents.simple import simple_agent
from app.agents.verification import verification_agent
from app.agents.planner import planner_agent
from app.agents.reader import reader_agent
from app.agents.evidence import evidence_agent
from app.agents.writer import writer_agent
from app.agents.critic import critic_agent
from app.services.search import search_service
from app.core import logger, settings
from app.core.observability import trace_span, metrics


class ResearchState(TypedDict):
    """State for research workflow."""
    query: str
    route: str
    route_reason: str
    
    # For complex research
    tasks: List[Dict]
    completed_tasks: List[Dict]
    all_findings: List[Dict]
    
    # Search results
    search_results: List[Dict]
    
    # Evidence and output
    evidence: List[Dict]
    draft_answer: str
    final_answer: str
    sources: List[Dict]
    
    # Critique
    critique: Dict
    retry_count: int
    
    # Final result
    result: Dict
    error: str


async def route_node(state: ResearchState) -> ResearchState:
    """Route the query to appropriate tier."""
    start_time = time.time()
    try:
        logger.info("=== ROUTE NODE ===")
        with trace_span("agent:router") as span:
            decision = await router_agent.route(state["query"])
        
        duration_ms = (time.time() - start_time) * 1000
        metrics.record_agent_execution("router", duration_ms, status="success")
        
        state["route"] = decision.route
        state["route_reason"] = decision.reason
        state["retry_count"] = 0
        
        return state
    except Exception as e:
        duration_ms = (time.time() - start_time) * 1000
        metrics.record_agent_execution("router", duration_ms, status="error")
        logger.error(f"Route node failed: {e}")
        state["error"] = str(e)
        return state


async def simple_node(state: ResearchState) -> ResearchState:
    """Handle simple queries."""
    start_time = time.time()
    try:
        logger.info("=== SIMPLE NODE ===")
        with trace_span("agent:simple") as span:
            result = await simple_agent.answer(state["query"])
            
        duration_ms = (time.time() - start_time) * 1000
        metrics.record_agent_execution("simple", duration_ms, status="success")
        state["result"] = result
        return state
    except Exception as e:
        duration_ms = (time.time() - start_time) * 1000
        metrics.record_agent_execution("simple", duration_ms, status="error")
        logger.error(f"Simple node failed: {e}")
        state["error"] = str(e)
        return state


async def verification_node(state: ResearchState) -> ResearchState:
    """Handle verification queries."""
    start_time = time.time()
    try:
        logger.info("=== VERIFICATION NODE ===")
        with trace_span("agent:verification") as span:
            result = await verification_agent.verify(state["query"])
            
        duration_ms = (time.time() - start_time) * 1000
        metrics.record_agent_execution("verification", duration_ms, status="success")
        state["result"] = result
        return state
    except Exception as e:
        duration_ms = (time.time() - start_time) * 1000
        metrics.record_agent_execution("verification", duration_ms, status="error")
        logger.error(f"Verification node failed: {e}")
        state["error"] = str(e)
        return state


async def plan_node(state: ResearchState) -> ResearchState:
    """Create research plan for complex queries."""
    start_time = time.time()
    try:
        logger.info("=== PLAN NODE ===")
        with trace_span("agent:planner") as span:
            plan = await planner_agent.plan(state["query"])
            
        duration_ms = (time.time() - start_time) * 1000
        metrics.record_agent_execution("planner", duration_ms, status="success")
        state["tasks"] = plan["tasks"]
        state["completed_tasks"] = []
        state["all_findings"] = []
        return state
    except Exception as e:
        duration_ms = (time.time() - start_time) * 1000
        metrics.record_agent_execution("planner", duration_ms, status="error")
        logger.error(f"Plan node failed: {e}")
        state["error"] = str(e)
        return state


async def search_node(state: ResearchState) -> ResearchState:
    """Execute search tasks with rate-limit admission and budget enforcement."""
    start_time = time.time()
    try:
        logger.info("=== SEARCH NODE ===")
        from app.core.budget import get_current_budget
        budget = get_current_budget()

        with trace_span("agent:reader") as span:
            tasks = state.get("tasks", [])
            # Cap tasks to max 2 to prevent token explosions on complex queries
            tasks = tasks[:2]

            for task in tasks:
                if budget:
                    try:
                        budget.record_tool_execution()
                    except Exception as be:
                        logger.warning(f"Search tool execution budget reached: {be}")
                        break

                task_id = task.get("task_id", 1)
                desc = task.get("description", "")
                logger.info(f"Executing search task {task_id}: {desc}")
                search_query = task.get("search_query", desc)

                try:
                    results = await search_service.search(search_query, max_results=3)
                    findings = await reader_agent.read(task, results)
                    if findings.get("findings"):
                        state["all_findings"].extend(findings["findings"])
                    state["completed_tasks"].append({
                        **task,
                        "findings": findings
                    })
                except Exception as task_err:
                    logger.warning(f"Search subtask {task_id} failed: {task_err}")
                    continue

        duration_ms = (time.time() - start_time) * 1000
        metrics.record_agent_execution("reader", duration_ms, status="success")
        logger.info(f"Search completed: {len(state['all_findings'])} total findings in {round(duration_ms, 2)}ms")
        return state

    except Exception as e:
        duration_ms = (time.time() - start_time) * 1000
        metrics.record_agent_execution("reader", duration_ms, status="error")
        logger.error(f"Search node failed: {e}")
        state["error"] = str(e)
        return state


async def consolidate_evidence_node(state: ResearchState) -> ResearchState:
    """Consolidate findings into evidence."""
    start_time = time.time()
    try:
        logger.info("=== CONSOLIDATE EVIDENCE NODE ===")
        with trace_span("agent:evidence") as span:
            evidence = evidence_agent.consolidate(state["all_findings"])
            state["evidence"] = evidence
            
            # Extract sources
            sources = []
            seen_urls = set()
            for ev in evidence:
                url = ev.get("source_url", "")
                if url and url not in seen_urls:
                    sources.append({
                        "title": ev.get("source_title", ""),
                        "url": url,
                        "name": ev.get("source_name", "")
                    })
                    seen_urls.add(url)
            
            state["sources"] = sources
        
        duration_ms = (time.time() - start_time) * 1000
        metrics.record_agent_execution("evidence", duration_ms, status="success")
        return state
        
    except Exception as e:
        duration_ms = (time.time() - start_time) * 1000
        metrics.record_agent_execution("evidence", duration_ms, status="error")
        logger.error(f"Consolidate evidence node failed: {e}")
        state["error"] = str(e)
        return state


async def write_node(state: ResearchState) -> ResearchState:
    """Write final answer."""
    start_time = time.time()
    try:
        logger.info("=== WRITE NODE ===")
        with trace_span("agent:writer") as span:
            # Create summary of findings
            findings_summary = f"Completed {len(state['completed_tasks'])} research tasks"
            evidence_count = len(state.get("evidence", []))
            logger.info(f"Write node received {evidence_count} evidence items")
            
            if evidence_count == 0:
                logger.warning("Write node: No evidence available - this will trigger 'Insufficient information' response")
                logger.info(f"Completed tasks: {[task.get('description', 'N/A') for task in state.get('completed_tasks', [])]}")
                logger.info(f"All findings count: {len(state.get('all_findings', []))}")
            
            result = await writer_agent.write(
                state["query"],
                state["evidence"],
                findings_summary
            )
            
            state["draft_answer"] = result["answer"]
        
        duration_ms = (time.time() - start_time) * 1000
        metrics.record_agent_execution("writer", duration_ms, status="success")
        return state
        
    except Exception as e:
        duration_ms = (time.time() - start_time) * 1000
        metrics.record_agent_execution("writer", duration_ms, status="error")
        logger.error(f"Write node failed: {e}")
        state["error"] = str(e)
        return state


async def critique_node(state: ResearchState) -> ResearchState:
    """Critique the answer if budget allows, otherwise finalize immediately."""
    start_time = time.time()
    try:
        logger.info("=== CRITIQUE NODE ===")
        from app.core.budget import get_current_budget
        budget = get_current_budget()

        # If budget does not permit optional critique, skip to finalize directly
        if budget and not budget.can_make_optional_call():
            logger.info("Critique node skipped to preserve remaining request budget.")
            state["critique"] = {
                "quality_score": 0.85,
                "is_acceptable": True,
                "feedback": "Critique bypassed to conserve API quota and latency"
            }
            return state

        with trace_span("agent:critic") as span:
            critique = await critic_agent.critique(
                state["query"],
                state["draft_answer"],
                state["evidence"]
            )
            state["critique"] = critique
            state["retry_count"] = state.get("retry_count", 0) + 1
            
        duration_ms = (time.time() - start_time) * 1000
        metrics.record_agent_execution("critic", duration_ms, status="success")
        return state
        
    except Exception as e:
        duration_ms = (time.time() - start_time) * 1000
        metrics.record_agent_execution("critic", duration_ms, status="error")
        logger.error(f"Critique node failed: {e}")
        # Never fail the entire request on critique error; accept the draft answer
        state["critique"] = {
            "quality_score": 0.75,
            "is_acceptable": True,
            "feedback": f"Evaluation error ({e}), accepting draft response"
        }
        return state


async def finalize_node(state: ResearchState) -> ResearchState:
    """Finalize the result."""
    try:
        logger.info("=== FINALIZE NODE ===")
        
        # Limit evidence to top 7 items by confidence for final response
        evidence = state["evidence"]
        if evidence and len(evidence) > 7:
            sorted_evidence = sorted(
                evidence,
                key=lambda x: x.get('confidence', 0.0),
                reverse=True
            )[:7]
            logger.info(f"Limited evidence from {len(evidence)} to 7 items for final response")
            evidence = sorted_evidence
        
        state["final_answer"] = state["draft_answer"]
        state["result"] = {
            "answer": state["final_answer"],
            "evidence": evidence,
            "sources": state["sources"],
            "route": state["route"],
            "critique": state.get("critique", {})
        }
        
        return state
        
    except Exception as e:
        logger.error(f"Finalize node failed: {e}")
        state["error"] = str(e)
        return state


def should_retry(state: ResearchState) -> str:
    """Determine if we should retry based on critique and budget."""
    from app.core.budget import get_current_budget
    budget = get_current_budget()

    if budget:
        try:
            budget.record_graph_iteration()
        except Exception:
            logger.info("Graph iteration limit reached. Finalizing response immediately.")
            return "finalize"

    critique = state.get("critique", {})
    is_acceptable = critique.get("is_acceptable", True)
    quality_score = critique.get("quality_score", 1.0)
    retry_count = state.get("retry_count", 0)
    
    # If acceptable, score >= 0.6, or budget constrained, finalize immediately
    if is_acceptable or quality_score >= 0.6 or (budget and not budget.can_make_optional_call()):
        logger.info(f"Critique passed or budget constrained (Score={quality_score:.2f}). Finalizing immediately.")
        return "finalize"
    
    # Strict maximum 1 retry iteration to prevent excessive LLM calls
    if retry_count < 1:
        logger.info(f"Critique indicates correction needed (Score={quality_score:.2f}), retrying (1/1)")
        return "retry"
    else:
        logger.info("Max graph retry limit reached. Finalizing.")
        return "finalize"


def route_after_route(state: ResearchState) -> str:
    """Determine next node after routing."""
    route = state.get("route", "SIMPLE")
    
    if route == "SIMPLE":
        return "simple"
    elif route == "VERIFICATION":
        return "verification"
    else:  # COMPLEX
        return "plan"


# Build the graph
def build_research_graph():
    """Build the research workflow graph."""
    workflow = StateGraph(ResearchState)
    
    # Add nodes
    workflow.add_node("router", route_node)
    workflow.add_node("simple", simple_node)
    workflow.add_node("verification", verification_node)
    workflow.add_node("plan", plan_node)
    workflow.add_node("search", search_node)
    workflow.add_node("consolidate_evidence", consolidate_evidence_node)
    workflow.add_node("write", write_node)
    workflow.add_node("critic", critique_node)
    workflow.add_node("finalize", finalize_node)
    
    # Set entry point
    workflow.set_entry_point("router")
    
    # Add conditional edges from router
    workflow.add_conditional_edges(
        "router",
        route_after_route,
        {
            "simple": "simple",
            "verification": "verification",
            "plan": "plan"
        }
    )
    
    # Simple path
    workflow.add_edge("simple", END)
    
    # Verification path
    workflow.add_edge("verification", END)
    
    # Complex path
    workflow.add_edge("plan", "search")
    workflow.add_edge("search", "consolidate_evidence")
    workflow.add_edge("consolidate_evidence", "write")
    workflow.add_edge("write", "critic")
    
    # Conditional edge after critic
    workflow.add_conditional_edges(
        "critic",
        should_retry,
        {
            "retry": "search",  # Retry search with corrections
            "finalize": "finalize"
        }
    )
    
    workflow.add_edge("finalize", END)
    
    return workflow.compile()


# Global research graph instance
research_graph = build_research_graph()
