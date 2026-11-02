"""
Query Validator Service - Guardrails for Finance/Fintech Queries Only

This service validates that incoming queries are related to finance, fintech, 
accounting, economics, or business topics. Non-financial queries are rejected.
"""

from app.services.llm import llm_service
from app.core import logger
from app.core.model_config import TaskType
import json
import re
from typing import Dict, Optional, List, Any


VALIDATOR_SYSTEM_PROMPT = """You are a query validation system for IRIUM, a specialized financial and economic research assistant.

IRIUM is designed exclusively for:
- Finance and banking
- Fintech and digital payments
- Accounting and auditing
- Economics and monetary policy
- GDP growth, inflation, trade, labor market, and employment
- Economic impacts of geopolitical conflicts and crises
- Assessments, reports, and data from credible international economic and development institutions (e.g., UN Development Programme/UNDP, World Bank, IMF, OECD, central banks)
- Investment and trading
- Corporate finance and valuation
- Financial regulations and compliance
- Insurance and risk management
- Cryptocurrencies and blockchain (financial aspects)
- Business strategy and financial analysis
- Taxation and financial planning
- Stock markets and securities

IRIUM is NOT designed for:
- General programming (algorithms, data structures, coding tutorials)
- Computer science problems (sorting, searching, graph algorithms, DP problems)
- Competitive programming or LeetCode-style problems
- Non-financial mathematics (geometry, calculus unrelated to finance)
- General knowledge (history, geography, science unrelated to finance/economics)
- Entertainment, sports, recipes, or lifestyle topics
- Technology topics unrelated to fintech
- Educational content unrelated to business/finance/economics

Your task: Determine if a user query is related to finance, fintech, business, economics, accounting, or economic impact assessments.

**CRITICAL RULES:**
1. If the query asks for CODE, ALGORITHM, or PROGRAMMING without a CLEAR financial context → INVALID
2. "Maximum subarray sum", "palindrome", "fibonacci", "sorting" → INVALID (pure CS problems)
3. "Python code for X" where X is a pure algorithm → INVALID
4. "NPV calculation code", "options pricing algorithm", "portfolio optimization" → VALID (finance context)
5. A query mentioning financial terms in passing but asking for non-financial code → INVALID
6. If a query discusses economics, trade, GDP, economic losses/impacts from conflicts, or reports/assessments from international economic bodies (such as UNDP, World Bank, IMF) → mark as VALID (economics/finance).
7. Only mark as INVALID if the query is clearly non-financial and non-economic (e.g. coding puzzles, recipes, sports, movies, pure software development).

Return ONLY a JSON object:
{
    "is_valid": boolean,
    "category": "finance" | "fintech" | "accounting" | "economics" | "business" | "invalid",
    "reason": "Brief explanation",
    "suggested_alternative": "Optional suggestion if query is invalid" or null
}

Examples of INVALID queries:
- "Give python code for binary search" → INVALID (pure algorithm)
- "Give python code for maximum subarray sum k" → INVALID (pure CS problem)
- "Explain quicksort algorithm" → INVALID (pure algorithm)
- "How to implement palindrome checker" → INVALID (pure algorithm)
- "Dynamic programming problem solution" → INVALID (pure CS)
- "Write function for fibonacci" → INVALID (pure algorithm)
- "Recipe for chocolate cake" → INVALID (lifestyle)

Examples of VALID queries:
- "What is EBITDA?" → VALID (finance concept)
- "Calculate compound interest" → VALID (finance calculation)
- "Current RBI repo rate" → VALID (finance data)
- "Compare HDFC and ICICI banks" → VALID (finance analysis)
- "Explain economics and monetary policy" → VALID (economics)
- "Explain the influence of Middle East conflicts on GDP growth" → VALID (economics)
- "UN development Programme assessment" → VALID (economic assessment)
- "Analyze the UN Development Programme assessment of economic losses caused by Middle East conflicts" → VALID (economics)
- "Python code to calculate NPV" → VALID (finance-specific calculation)
- "Algorithm for portfolio optimization" → VALID (finance-specific algorithm)
"""


class QueryValidator:
    """Validates queries are finance/fintech related."""
    
    def __init__(self):
        # Financial keywords for fast-path validation
        self.finance_keywords = {
            # Core finance
            'finance', 'financial', 'fintech', 'bank', 'banking', 'loan', 'credit', 
            'debt', 'equity', 'stock', 'bond', 'share', 'dividend', 'interest',
            'investment', 'investor', 'trading', 'portfolio', 'asset', 'liability',
            
            # Accounting
            'accounting', 'audit', 'balance sheet', 'income statement', 'cash flow',
            'ledger', 'journal', 'depreciation', 'amortization', 'accrual', 'gaap',
            'ifrs', 'revenue', 'expense', 'profit', 'loss', 'losses', 'ebitda', 'ebit',
            
            # Economics & Macroeconomics
            'economic', 'economics', 'economy', 'macroeconomic', 'microeconomic',
            'gdp', 'gdp growth', 'inflation', 'deflation', 'stagflation', 'recession',
            'monetary', 'fiscal', 'policy', 'central bank', 'rbi', 'fed', 'ecb',
            'repo rate', 'reverse repo', 'crr', 'slr', 'monetary policy', 'fiscal policy',
            'economic growth', 'growth rate', 'trade', 'employment', 'unemployment',
            'labor market', 'interest rate', 'interest rates', 'bond yield', 'bond yields',
            'economic impact', 'economic losses', 'economic loss', 'economic assessment',
            'economic damage', 'economic consequences', 'cost of living',
            
            # International Economic Bodies & Development
            'undp', 'un development programme', 'united nations development programme',
            'world bank', 'imf', 'international monetary fund', 'wto', 'wef', 'oecd',
            'development programme', 'development program', 'economic development',
            'human development index', 'geopolitical conflict', 'war economics',
            'economic sanctions', 'sanctions', 'tariffs', 'trade deficit',
            'current account deficit', 'fdi', 'forex reserves', 'damage', 'damages',
            'cost', 'costs',
            
            # Markets & Securities
            'market', 'stock market', 'exchange', 'nse', 'bse', 'nasdaq', 'nyse',
            'ipo', 'shares', 'securities', 'derivative', 'option', 'future', 'swap',
            'forex', 'currency', 'commodity', 'index', 'mutual fund', 'etf',
            
            # Valuation & Analysis
            'valuation', 'dcf', 'npv', 'irr', 'wacc', 'capm', 'beta', 'alpha',
            'sharpe ratio', 'pe ratio', 'pb ratio', 'eps', 'roe', 'roa', 'roi',
            'cagr', 'yield', 'return', 'risk', 'volatility',
            
            # Corporate Finance
            'corporate finance', 'merger', 'acquisition', 'ma', 'takeover',
            'restructuring', 'leverage', 'capital structure', 'working capital',
            
            # Fintech & Payments
            'payment', 'upi', 'digital payment', 'mobile banking', 
            'blockchain', 'cryptocurrency', 'bitcoin', 'ethereum', 'defi',
            'wallet', 'payment gateway', 'neobank', 'challenger bank',
            
            # Regulations
            'sebi', 'sec', 'regulation', 'compliance', 'basel', 'kyc', 'aml',
            'mifid', 'dodd-frank', 'sox', 'ifsc', 'fema', 'rera',
            
            # Insurance & Risk
            'insurance', 'premium', 'underwriting', 'actuarial',
            'risk management', 'hedge', 'diversification',
            
            # Taxation
            'tax', 'taxation', 'gst', 'income tax', 'corporate tax', 'vat',
            'tds', 'capital gains', 'deduction',
            
            # Business & Strategy
            'business', 'startup', 'entrepreneurship', 'venture capital', 'vc',
            'private equity', 'angel investor', 'funding',
            'business model', 'revenue model', 'unit economics', 'burn rate',
            
            # Financial Calculations
            'emi', 'sip', 'compound interest', 'simple interest', 'present value',
            'future value', 'annuity', 'perpetuity', 'discount rate',
        }
        
        # Non-financial programming/tech keywords (when used WITHOUT finance context)
        self.pure_tech_keywords = {
            'binary search', 'quicksort', 'merge sort', 'bubble sort', 'linked list',
            'tree traversal', 'graph algorithm', 'dynamic programming', 'recursion',
            'data structure', 'oop', 'inheritance', 'polymorphism', 'web server',
            'html', 'css', 'javascript', 'react', 'angular', 'vue', 'django',
            'flask', 'machine learning', 'neural network', 'deep learning',
            'subarray', 'substring', 'palindrome', 'fibonacci', 'factorial',
            'heap', 'queue', 'stack', 'hash table', 'hash map', 'trie',
            'backtracking', 'greedy algorithm', 'divide and conquer',
        }
        
        # Programming action patterns (without finance context)
        self.code_request_patterns = [
            r'\b(give|write|provide|show|implement|create)\s+(python|java|javascript|cpp|code|program|function)',
            r'\b(python|java|javascript|cpp)\s+(code|program|function|script)\s+(for|to)',
            r'\bcode\s+(for|to|that)\b',
            r'\bprogram\s+(for|to|that)\b',
            r'\bfunction\s+(for|to|that)\b',
            r'\bimplement\s+\w+\s+(algorithm|function)',
        ]
    
    def _fast_path_validate(self, query: str) -> Optional[Dict]:
        """
        Fast-path validation using keyword matching.
        Returns validation result if confident, None if needs LLM.
        """
        q_lower = query.lower()
        
        # Check for code request patterns FIRST (before checking finance keywords)
        has_code_request = any(re.search(pattern, q_lower) for pattern in self.code_request_patterns)
        
        # Check for pure tech keywords without finance context
        has_pure_tech = any(keyword in q_lower for keyword in self.pure_tech_keywords)
        
        # Check for financial keywords with word boundary protection for short keywords
        has_finance_keyword = False
        for keyword in self.finance_keywords:
            if len(keyword) <= 3:
                # Short keywords (like 'ma', 'vc', 'pe') need word boundaries to avoid false positives
                if re.search(r'\b' + re.escape(keyword) + r'\b', q_lower):
                    has_finance_keyword = True
                    break
            else:
                # Longer keywords can use substring matching with word boundary for better precision
                # This helps catch "economics" in "Explain economics and monetary policy"
                escaped_keyword = re.escape(keyword)
                if re.search(r'\b' + escaped_keyword + r'\b', q_lower):
                    has_finance_keyword = True
                    break
                # Fallback to substring for phrases with spaces
                elif ' ' in keyword and keyword in q_lower:
                    has_finance_keyword = True
                    break
        
        # If query has code request pattern WITHOUT finance keywords, reject immediately
        if has_code_request and not has_finance_keyword:
            return {
                "is_valid": False,
                "category": "invalid",
                "reason": "Programming/coding query without financial context",
                "suggested_alternative": "Please ask questions related to finance, fintech, accounting, economics, or business. For financial programming, specify the financial context (e.g., 'Python code to calculate NPV')."
            }
        
        # If query has finance keywords, it's likely valid
        if has_finance_keyword:
            return {
                "is_valid": True,
                "category": "finance",
                "reason": "Query contains financial terminology",
                "suggested_alternative": None
            }
        
        # If query has pure tech keywords and NO finance context, likely invalid
        if has_pure_tech and not has_finance_keyword:
            # Check for code-related patterns
            if any(pattern in q_lower for pattern in ['give code', 'write code', 'python code', 'implement']):
                return {
                    "is_valid": False,
                    "category": "invalid",
                    "reason": "Programming query without financial context",
                    "suggested_alternative": "Please ask questions related to finance, fintech, accounting, economics, or business."
                }
        
        # Check for obvious non-financial topics
        non_finance_patterns = [
            r'\b(recipe|cook|food)\b',
            r'\b(cricket|football|sports|game)\b',
            r'\b(movie|film|music|song)\b',
            r'\b(weather|climate)\b',
            r'\b(health|medical|doctor)\b',
        ]
        
        for pattern in non_finance_patterns:
            if re.search(pattern, q_lower):
                return {
                    "is_valid": False,
                    "category": "invalid",
                    "reason": "Query is not related to finance or business",
                    "suggested_alternative": "IRIUM specializes in financial research. Please ask about finance, banking, investments, economics, or business topics."
                }
        
        # Not confident - defer to LLM
        return None
    
    async def validate_query(
        self, 
        query: str,
        conversation_history: Optional[List[Dict]] = None,
        resolved_query: Optional[str] = None
    ) -> Dict:
        """
        Validate if query (or resolved query in context) is finance/fintech related.
        
        Args:
            query: Original user query
            conversation_history: Optional conversation turns for context
            resolved_query: Optional resolved query incorporating conversation context
            
        Returns:
            {
                "is_valid": bool,
                "category": str,
                "reason": str,
                "suggested_alternative": str or None
            }
        """
        try:
            # Evaluate the resolved query if available, otherwise original query
            query_to_check = resolved_query.strip() if (resolved_query and resolved_query.strip()) else query.strip()
            
            # Try fast-path validation first
            fast_result = self._fast_path_validate(query_to_check)
            if fast_result:
                logger.info(f"Query validation (fast-path): {fast_result['is_valid']} - {fast_result['reason']} (query='{query_to_check[:60]}')")
                return fast_result
            
            # Use LLM for ambiguous cases
            logger.info(f"Query validation: Using LLM for query: {query_to_check[:100]}")
            
            validation_prompt = f"Validate this query:\n\n{query_to_check}"
            if conversation_history and not resolved_query:
                # Provide recent context if query was not already resolved
                recent_ctx = "\n".join([f"{t.get('role', 'user')}: {t.get('content', '')[:150]}" for t in conversation_history[-4:]])
                validation_prompt = f"Conversation Context:\n{recent_ctx}\n\nValidate this query in light of the context:\n\n{query_to_check}"

            response = await llm_service.invoke(
                system_prompt=VALIDATOR_SYSTEM_PROMPT,
                user_message=validation_prompt,
                task_type=TaskType.ROUTING
            )
            
            # Parse JSON response
            response_text = response.strip()
            
            # Handle markdown code blocks
            if "```json" in response_text:
                json_start = response_text.find("```json") + 7
                json_end = response_text.find("```", json_start)
                response_text = response_text[json_start:json_end].strip()
            elif "```" in response_text:
                json_start = response_text.find("```") + 3
                json_end = response_text.find("```", json_start)
                response_text = response_text[json_start:json_end].strip()
            
            # Parse JSON
            result = json.loads(response_text)
            
            logger.info(f"Query validation (LLM): {result['is_valid']} - {result['reason']}")
            return result
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse validation response as JSON: {e}")
            logger.error(f"Response was: '{response}'")
            
            # Default to allowing query if validation fails
            logger.warning("Validation parsing failed - defaulting to ALLOW")
            return {
                "is_valid": True,
                "category": "finance",
                "reason": "Validation failed, defaulting to allow",
                "suggested_alternative": None
            }
            
        except Exception as e:
            logger.error(f"Query validation failed: {e}")
            # Default to allowing query if validation fails
            return {
                "is_valid": True,
                "category": "finance",
                "reason": "Validation error, defaulting to allow",
                "suggested_alternative": None
            }


# Global validator instance
query_validator = QueryValidator()
