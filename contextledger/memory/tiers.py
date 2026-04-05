"""Three-tier memory router.

Routes queries to the appropriate tier:
- Immediate: verbatim last N turns
- Synthesis: compressed recent findings
- Archival: full semantic history
"""
