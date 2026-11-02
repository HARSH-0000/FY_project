import time
from app.workflows.research_graph import research_graph, ResearchState
from app.core import logger, settings
from app.core.langsmith_config import get_langsmith_url
from langchain_core.tracers.context import tracing_v2_enabled
from typing import Dict, Optional, List


class ResearchService:
    """Service for executing research workflows."""
    
    def _validate_response_structure(self, result: Dict, query: str) -> None:
        """
        Validate the structure of the research response.
        Logs warnings for malformed responses but doesn't block them.
        
        Args:
            result: The research result dictionary
            query: The original query for context in logs
        """
        try:
            answer = result.get("answer")
            
            # Check if answer exists
            if not answer:
                logger.warning(f"[VALIDATION] Query '{query[:40]}...' - Missing 'answer' field in result")
                return
            
            # Check if answer is properly structured
            if isinstance(answer, dict):
                sections = answer.get("sections", [])
                
                if not sections:
                    logger.warning(f"[VALIDATION] Query '{query[:40]}...' - No sections in structured answer")
                    return
                
                # Validate each section
                for idx, section in enumerate(sections):
                    section_type = section.get("type")
                    
                    if not section_type:
                        logger.warning(f"[VALIDATION] Query '{query[:40]}...' - Section {idx} missing 'type' field")
                    
                    if section_type == "text":
                        content = section.get("content", "")
                        if not content or len(content.strip()) < 10:
                            logger.warning(f"[VALIDATION] Query '{query[:40]}...' - Section {idx} (text) has insufficient content")
                        
                        # Check if content looks like raw JSON (nested)
                        if content.strip().startswith("{") and "sections" in content:
                            logger.error(f"[VALIDATION] Query '{query[:40]}...' - Section {idx} contains nested JSON! This will render incorrectly.")
                    
                    elif section_type == "table":
                        columns = section.get("columns", [])
                        rows = section.get("rows", [])
                        
                        if not columns:
                            logger.warning(f"[VALIDATION] Query '{query[:40]}...' - Section {idx} (table) missing columns")
                        
                        if not rows:
                            logger.warning(f"[VALIDATION] Query '{query[:40]}...' - Section {idx} (table) has no rows")
                        
                        # Validate row length matches column count
                        for row_idx, row in enumerate(rows):
                            if len(row) != len(columns):
                                logger.error(f"[VALIDATION] Query '{query[:40]}...' - Section {idx} (table) row {row_idx} has {len(row)} values but {len(columns)} columns")
                
                logger.info(f"[VALIDATION] Query '{query[:40]}...' - Response structure validated: {len(sections)} sections")
            
            elif isinstance(answer, str):
                # String answer - check if it's accidentally JSON
                if answer.strip().startswith("{") and "sections" in answer:
                    logger.error(f"[VALIDATION] Query '{query[:40]}...' - Answer is a JSON string instead of object! Parsing may be broken.")
                else:
                    logger.info(f"[VALIDATION] Query '{query[:40]}...' - Plain string answer ({len(answer)} chars)")
            
        except Exception as e:
            logger.warning(f"[VALIDATION] Validation check failed for query '{query[:40]}...': {e}")
    
    async def execute_research(
        self,
        query: str,
        bypass_cache: bool = False,
        user_id: Optional[int] = None,
        session_id: Optional[int] = None,
        conversation_id: Optional[str] = None,
        conversation_history: Optional[List[Dict]] = None,
        original_query: Optional[str] = None,
        resolved_query: Optional[str] = None
    ) -> Dict:
        """
        Execute research workflow for a query with caching and persistent memory.
        
        Args:
            query: User query
            bypass_cache: Force fresh computation
            user_id: Optional user identifier
            session_id: Optional session identifier
            conversation_id: Optional conversation identifier for multi-turn context
            conversation_history: Optional list of previous conversation turns
        
        Returns:
            Research result dictionary
        """
        try:
            from app.core.observability import trace_span, metrics, get_current_trace_id
            from app.services.cache import cache_service
            from app.services.memory import memory_service
            from app.services.report_detector import report_detector

            logger.info(f"Starting research for query: {query}")
            
            # Check if this is a report generation request FIRST
            try:
                detection = await report_detector.detect(query)
                if detection.is_report_request:
                    logger.info(f"Report request detected: topic='{detection.topic}', format={detection.format}")
                    
                    try:
                        # Generate report
                        from app.services.report_content_generator import report_content_generator
                        from app.services.pdf_generator import pdf_generator
                        from app.services.docx_generator import docx_generator
                        from app.services.pdf_page_counter import count_pdf_pages
                        from pathlib import Path
                        import uuid
                        
                        # Generate unique report ID
                        report_id = uuid.uuid4().hex
                        reports_dir = Path("data/reports")
                        reports_dir.mkdir(parents=True, exist_ok=True)
                        output_filename = f"report_{report_id}.{detection.format}"
                        output_path = reports_dir / output_filename
                        
                        # Generate content
                        content = await report_content_generator.generate(
                            detection,
                            session_id=session_id,
                            uploaded_document_ids=None
                        )
                        
                        # Render to PDF or DOCX
                        if detection.format == "pdf":
                            pdf_generator.generate(content, output_path)
                            actual_pages = count_pdf_pages(output_path)
                        else:  # docx
                            docx_generator.generate(content, output_path)
                            actual_pages = None
                        
                        # Return report response
                        return {
                            "type": "report",
                            "report_id": report_id,
                            "title": content.title,
                            "format": detection.format,
                            "filename": output_filename,
                            "pages": actual_pages,
                            "status": "completed",
                            "download_url": f"/api/reports/{report_id}/download",
                            "message": f"Report generated successfully! {actual_pages or '?'} pages." if actual_pages else "Report generated successfully!",
                            "route": "REPORT",
                            "evidence": [],
                            "sources": []
                        }
                    except Exception as generation_error:
                        logger.warning(f"Report generation failed, falling back to chat response: {generation_error}")
                        # Fall through to normal research flow if generation fails
                        # Continue below with normal chat response
            except Exception as report_error:
                logger.error(f"Report detection failed: {report_error}")
                # Continue with normal research flow if report detection fails
            
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

            # Extract facts from conversation history for multi-turn context
            from app.services.fact_memory import fact_memory_service
            conversation_facts = {}
            if conversation_history:
                conversation_facts = fact_memory_service.extract_facts_from_history(
                    conversation_history, query
                )
                if conversation_facts:
                    logger.info(f"Extracted {len(conversation_facts)} fact entities from conversation history")

            # Initialize request budget and trace context
            from app.core.budget import start_request_budget
            budget = start_request_budget(
                request_id=get_current_trace_id()
            )

            # Initialize state
            initial_state: ResearchState = {
                "query": effective_query,
                "original_query": original_query or query,
                "resolved_query": resolved_query or query,
                "route": "",
                "route_reason": "",
                
                # Multi-turn conversation context
                "conversation_id": conversation_id or "default",
                "conversation_history": conversation_history or [],
                "conversation_facts": conversation_facts,  # Extracted facts from history
                
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
                "visualizations": [],
                "result": {},
                "error": ""
            }
            
            # Execute graph
            start_time = time.time()
            
            with trace_span("workflow:research") as span:
                final_state = await research_graph.ainvoke(initial_state)
            
            duration_ms = (time.time() - start_time) * 1000
            metrics.record_workflow(duration_ms)
            
            # Log structured per-request observability summary
            budget.outcome = "success" if not final_state.get("error") else "failed"
            logger.info(
                f"\n--- REQUEST OBSERVABILITY SUMMARY ---\n"
                f"{budget.summary()}\n"
                f"Latency: {round(duration_ms, 2)}ms\n"
                f"------------------------------------"
            )

            # Check for errors
            if final_state.get("error"):
                logger.error(f"Research failed: {final_state['error']}")
                metrics.record_error("research_workflow", "WorkflowError")
                return {
                    "answer": f"Research failed: {final_state['error']}",
                    "evidence": [],
                    "sources": [],
                    "visualizations": [],
                    "table": None,
                    "route": final_state.get("route", "UNKNOWN"),
                    "error": final_state["error"],
                    "trace_id": get_current_trace_id(),
                    "duration_ms": round(duration_ms, 2)
                }
            
            # Return result
            result = final_state.get("result", {})
            result["original_query"] = original_query or query
            result["resolved_query"] = resolved_query or query
            if "visualizations" not in result:
                result["visualizations"] = final_state.get("visualizations", [])
            
            # Extract table section for schema compatibility
            table_val = None
            answer_obj = result.get("answer")
            if isinstance(answer_obj, dict):
                for sec in answer_obj.get("sections", []):
                    if isinstance(sec, dict) and sec.get("type") == "table":
                        table_val = sec
                        break
            result["table"] = table_val
            result["trace_id"] = get_current_trace_id()
            result["duration_ms"] = round(duration_ms, 2)
            
            # Validate JSON structure of the response
            self._validate_response_structure(result, query)
            
            # Store in cache ONLY if result is valid and contains actual content
            if result and not result.get("error"):
                # Validate result has meaningful content before caching
                answer = result.get("answer")
                has_content = False
                
                if isinstance(answer, dict) and "sections" in answer:
                    # Check if any section has non-empty content
                    for section in answer.get("sections", []):
                        if section.get("content", "").strip():
                            has_content = True
                            break
                elif isinstance(answer, str) and answer.strip():
                    has_content = True
                
                if has_content:
                    tier = final_state.get("route", "DEFAULT")
                    ttl = cache_service.get_ttl_for_tier(tier)
                    await cache_service.set(cache_key, result, ttl_seconds=ttl)
                    logger.info(f"Cached research result for query: '{query[:40]}...' [ttl={ttl}s]")
                else:
                    logger.warning(f"Skipping cache for query '{query[:40]}...' - result has no content")

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
