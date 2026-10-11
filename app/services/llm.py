from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_groq import ChatGroq
from langchain.schema import HumanMessage, SystemMessage
from app.core import settings, logger
from typing import Optional
import time


class LLMService:
    """LLM service for interacting with language models."""
    
    def __init__(self):
        self.provider = settings.LLM_PROVIDER
        self.model = settings.LLM_MODEL
        self._llm = None
        self.fallback_models = self._get_fallback_models()
    
    def _get_fallback_models(self):
        """Get fallback models based on current provider."""
        if self.provider == "groq":
            # Groq fallback chain: try available models then Google
            return [
                ("google", "gemini-flash-latest"),
                ("google", "gemini-3.8-flash"),
                ("groq", "openai/gpt-oss-20b"),
                ("groq", "qwen/qwen3.8-27b"),
            ]
        elif self.provider == "google":
            # Google fallback chain
            return [
                ("google", "gemini-3.8-flash"),
                ("google", "gemini-flash-latest"),
                ("groq", "openai/gpt-oss-20b"),
                ("groq", "qwen/qwen3.8-27b"),
            ]
        return []
    
    def get_llm(self, temperature: float = 0.0, model: Optional[str] = None, provider: Optional[str] = None):
        """Get LLM instance based on provider."""
        model_to_use = model or self.model
        provider_to_use = provider or self.provider
        
        if provider_to_use == "google":
            if not settings.GOOGLE_API_KEY:
                raise ValueError("GOOGLE_API_KEY not configured")
            
            # Map legacy/deprecated model names to current available models
            legacy_map = {
                "gemini-1.5-flash": "gemini-flash-latest",
                "gemini-1.5-pro": "gemini-3.8-flash",
                "gemini-2.0-flash": "gemini-flash-latest",
                "gemini-2.5-flash": "gemini-flash-latest",
                "gemini-2.5-pro": "gemini-3.8-flash",
            }
            model_to_use = legacy_map.get(model_to_use, model_to_use)
            
            return ChatGoogleGenerativeAI(
                google_api_key=settings.GOOGLE_API_KEY,
                model=model_to_use,
                temperature=temperature
            )
        elif provider_to_use == "groq":
            if not settings.GROQ_API_KEY:
                raise ValueError("GROQ_API_KEY not configured")
            return ChatGroq(
                groq_api_key=settings.GROQ_API_KEY,
                model_name=model_to_use,
                temperature=temperature
            )
        else:
            raise ValueError(f"Unsupported LLM provider: {provider_to_use}")
    
    async def invoke(
        self,
        system_prompt: str,
        user_message: str,
        temperature: float = 0.0,
        model: Optional[str] = None
    ) -> str:
        """Invoke LLM with system and user messages, with automatic fallback on rate limits."""
        # Try primary model
        try:
            model_name = model or self.model
            logger.info(f"Invoking {self.provider}/{model_name}")
            llm = self.get_llm(temperature=temperature, model=model)
            
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_message)
            ]
            
            start_time = time.time()
            from app.core.observability import trace_span, metrics
            with trace_span(f"llm:{self.provider}/{model_name}") as span:
                response = await llm.ainvoke(messages)
            
            duration_ms = (time.time() - start_time) * 1000
            metrics.record_llm_call(self.provider, model_name, duration_ms, status="success")
            return response.content
            
        except Exception as e:
            error_str = str(e)
            
            # Check if it's a rate limit error
            if "rate_limit" in error_str.lower() or "429" in error_str:
                logger.warning(f"Rate limit hit on {self.provider}/{model or self.model}: {e}")
                
                # Try fallback models
                for fallback_provider, fallback_model in self.fallback_models:
                    try:
                        logger.info(f"Trying fallback: {fallback_provider}/{fallback_model}")
                        fallback_llm = self.get_llm(
                            temperature=temperature,
                            model=fallback_model,
                            provider=fallback_provider
                        )
                        
                        messages = [
                            SystemMessage(content=system_prompt),
                            HumanMessage(content=user_message)
                        ]
                        
                        response = await fallback_llm.ainvoke(messages)
                        logger.info(f"✓ Fallback successful with {fallback_provider}/{fallback_model}")
                        return response.content
                        
                    except Exception as fallback_error:
                        logger.warning(f"Fallback {fallback_provider}/{fallback_model} failed: {fallback_error}")
                        continue
                
                # If all fallbacks failed, raise original error
                logger.error("All fallback models failed")
                raise Exception(f"Rate limit exceeded and all fallbacks failed. Original error: {e}")
            
            # Non-rate-limit error, raise immediately
            logger.error(f"LLM invocation failed: {e}")
            raise


# Global LLM service instance
llm_service = LLMService()
