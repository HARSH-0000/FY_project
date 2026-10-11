from app.providers.tavily import tavily_provider
from app.core import logger
from typing import List, Dict


# Source priority for FinTech research
SOURCE_PRIORITY = {
    "rbi.org.in": 100,
    "sebi.gov.in": 100,
    "nseindia.com": 90,
    "bseindia.com": 90,
    "mca.gov.in": 85,
    "government": 80,
    ".gov": 80,
    "investor": 75,
    "annual-report": 75,
    "financial-results": 75,
    "reuters.com": 70,
    "bloomberg.com": 70,
    "moneycontrol.com": 65,
    "economictimes.com": 65,
    "livemint.com": 65,
}


class SearchService:
    """Search service with source prioritization."""
    
    def __init__(self):
        self.tavily = tavily_provider
    
    async def search(self, query: str, max_results: int = 10) -> List[Dict]:
        """
        Perform web search with source prioritization.
        
        Returns:
            List of search results sorted by priority and relevance
        """
        try:
            import time
            from app.core.observability import trace_span, metrics
            from app.services.cache import cache_service

            cache_key = cache_service.build_key("search", query, max_results=max_results)
            cached_search = await cache_service.get(cache_key)
            if cached_search is not None:
                logger.info(f"Search Cache HIT for: '{query[:40]}...'")
                return cached_search

            start_time = time.time()
            
            with trace_span("retrieval:search", {"results_requested": max_results}) as span:
                # Get search results from Tavily
                results = await self.tavily.search(
                    query=query,
                    max_results=max_results
                )
            
            duration_ms = (time.time() - start_time) * 1000
            metrics.record_retrieval(duration_ms)
            
            # Add priority scores
            for result in results:
                result["priority_score"] = self._calculate_priority(result)
            
            # Sort by priority and relevance
            results.sort(
                key=lambda x: (x["priority_score"], x.get("score", 0)),
                reverse=True
            )
            
            # Cache search results for 30 minutes (1800s)
            await cache_service.set(cache_key, results, ttl_seconds=1800)
            
            logger.info(f"Search completed: {len(results)} results in {round(duration_ms, 2)}ms")
            return results
            
        except Exception as e:
            logger.error(f"Search failed: {e}")
            raise
    
    def _calculate_priority(self, result: Dict) -> float:
        """Calculate priority score based on source."""
        url = result.get("url", "").lower()
        title = result.get("title", "").lower()
        
        priority = 0.0
        
        # Check URL and title against priority sources
        for source, score in SOURCE_PRIORITY.items():
            if source in url or source in title:
                priority = max(priority, score)
        
        return priority
    
    async def search_with_context(self, query: str) -> Dict:
        """Search with Tavily's instant answer."""
        try:
            result = await self.tavily.search_with_answer(query)
            
            # Add priority scores
            for item in result["results"]:
                item["priority_score"] = self._calculate_priority(item)
            
            # Sort results
            result["results"].sort(
                key=lambda x: (x["priority_score"], x.get("score", 0)),
                reverse=True
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Search with context failed: {e}")
            raise


# Global search service instance
search_service = SearchService()
