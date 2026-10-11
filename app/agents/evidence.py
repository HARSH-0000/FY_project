from app.core import logger
from typing import List, Dict


class EvidenceAgent:
    """Evidence agent for consolidating findings into evidence."""
    
    def consolidate(self, all_findings: List[Dict]) -> List[Dict]:
        """
        Consolidate findings from multiple tasks into evidence.
        
        Args:
            all_findings: List of findings from reader agent
        
        Returns:
            List of evidence items
        """
        try:
            logger.info(f"Evidence agent consolidating {len(all_findings)} findings")
            
            evidence = []
            
            for finding in all_findings:
                # Convert finding to evidence format
                evidence_item = {
                    "claim": finding.get("information", ""),
                    "source_title": finding.get("source_title", ""),
                    "source_url": finding.get("source_url", ""),
                    "source_name": finding.get("source_name", ""),
                    "evidence_text": finding.get("context", finding.get("information", "")),
                    "confidence": finding.get("confidence", 0.7)
                }
                
                evidence.append(evidence_item)
            
            logger.info(f"Evidence agent created {len(evidence)} evidence items")
            return evidence
            
        except Exception as e:
            logger.error(f"Evidence agent failed: {e}")
            return []


# Global evidence agent instance
evidence_agent = EvidenceAgent()
