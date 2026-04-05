"""Protocol interfaces for pluggable backends.

Define here:
- StorageBackend
- EmbeddingBackend
- RegistryBackend
"""

from typing import Any, List, Optional, Protocol, runtime_checkable


@runtime_checkable
class StorageBackend(Protocol):
    """Protocol for persistent storage of memory units."""

    def write(self, unit: Any) -> str:
        """Write a memory unit dict, return its ID."""
        ...

    def read(self, id: str) -> Optional[dict]:
        """Read a memory unit by ID. Returns dict or None if not found."""
        ...

    def search(self, query_embedding: List[float], limit: int) -> List[dict]:
        """Semantic search over stored units by embedding similarity."""
        ...

    def traverse(self, node_id: str, depth: int) -> List[dict]:
        """Graph traversal from a node, returning units up to given depth."""
        ...

    def delete(self, id: str) -> bool:
        """Delete a memory unit by ID. Returns True if deleted, False otherwise."""
        ...

    def list_by_profile(self, profile_name: str) -> List[dict]:
        """List all memory units belonging to a given profile."""
        ...


@runtime_checkable
class EmbeddingBackend(Protocol):
    """Protocol for text embedding and similarity computation."""

    def encode(self, text: str) -> List[float]:
        """Encode a single text string into an embedding vector."""
        ...

    def encode_batch(self, texts: List[str]) -> List[List[float]]:
        """Encode a batch of text strings into embedding vectors."""
        ...

    def similarity(self, a: List[float], b: List[float]) -> float:
        """Compute similarity between two embedding vectors."""
        ...


@runtime_checkable
class RegistryBackend(Protocol):
    """Protocol for skill profile registry and versioning."""

    def list_profiles(self, filter: Optional[dict] = None) -> List[Any]:
        """List all profiles, optionally filtered."""
        ...

    def get_profile(self, name: str, version: Optional[str] = None) -> Optional[dict]:
        """Get a profile by name and optional version. Returns dict or None."""
        ...

    def save_profile(self, bundle: dict) -> str:
        """Save a skill profile bundle dict. Returns the profile name or ID."""
        ...

    def fork_profile(self, parent_name: str, new_name: str) -> dict:
        """Fork an existing profile under a new name. Returns the new profile dict."""
        ...

    def list_versions(self, name: str) -> List[str]:
        """List all version strings for a given profile name."""
        ...

    def get_diff(self, name_a: str, name_b: str) -> Any:
        """Compute a semantic diff between two profiles."""
        ...


@runtime_checkable
class LLMClient(Protocol):
    """Protocol for LLM completion requests."""

    def complete(self, prompt: str, max_tokens: int = 1000) -> str:
        """Send a completion request. Returns response text."""
        ...
