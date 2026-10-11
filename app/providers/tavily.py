from tavily import AsyncTavilyClient

from app.core import settings, logger

from typing import List, Dict, Optional


class TavilyProvider:
    """Async Tavily search provider."""

    def __init__(self):
        if not settings.TAVILY_API_KEY:
            logger.warning("TAVILY_API_KEY not configured")
            self.client = None
        else:
            self.client = AsyncTavilyClient(
                api_key=settings.TAVILY_API_KEY
            )

    async def search(
        self,
        query: str,
        max_results: Optional[int] = None,
        search_depth: str = "advanced"
    ) -> List[Dict]:
        """
        Perform asynchronous web search using Tavily.
        """

        if not self.client:
            raise ValueError(
                "Tavily client not initialized - check TAVILY_API_KEY"
            )

        try:
            logger.info(f"Tavily search: {query}")

            max_results = (
                max_results or settings.SEARCH_MAX_RESULTS
            )

            response = await self.client.search(
                query=query,
                max_results=max_results,
                search_depth=search_depth,
                include_answer=True,
                include_raw_content=False
            )

            results = []

            if "results" in response:
                for item in response["results"]:
                    results.append({
                        "title": item.get("title", ""),
                        "url": item.get("url", ""),
                        "content": item.get("content", ""),
                        "score": item.get("score", 0.0),
                        "raw_content": item.get("raw_content")
                    })

            logger.info(
                f"Tavily returned {len(results)} results"
            )

            return results

        except Exception as e:
            logger.exception(
                f"Tavily search failed: {e}"
            )
            raise

    async def search_with_answer(
        self,
        query: str
    ) -> Dict:
        """
        Perform asynchronous search and get Tavily's answer.
        """

        if not self.client:
            raise ValueError(
                "Tavily client not initialized - check TAVILY_API_KEY"
            )

        try:
            logger.info(
                f"Tavily search with answer: {query}"
            )

            response = await self.client.search(
                query=query,
                max_results=settings.SEARCH_MAX_RESULTS,
                search_depth="advanced",
                include_answer=True
            )

            results = []

            if "results" in response:
                for item in response["results"]:
                    results.append({
                        "title": item.get("title", ""),
                        "url": item.get("url", ""),
                        "content": item.get("content", ""),
                        "score": item.get("score", 0.0)
                    })

            return {
                "answer": response.get("answer", ""),
                "results": results
            }

        except Exception as e:
            logger.exception(
                f"Tavily search with answer failed: {e}"
            )
            raise


# Global Tavily provider instance
tavily_provider = TavilyProvider()