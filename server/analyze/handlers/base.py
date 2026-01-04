"""
Base classes for card handlers.

CardHandler provides a clean interface for:
- Executing a card (fetching/computing data)
- Validating the output
- Providing fallback payloads
- Normalizing output schema
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from server.analyze.meta_utils import ensure_meta


@dataclass
class CardResult:
    """
    Result of card execution.
    
    Attributes:
        data: The card payload (dict expected)
        is_fallback: Whether this is a fallback/unavailable payload
        meta: Additional metadata to attach
        skip_validation: If True, accept this result without validation
    """
    data: Dict[str, Any]
    is_fallback: bool = False
    meta: Optional[Dict[str, Any]] = None
    skip_validation: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to final output dict with _meta attached."""
        result = dict(self.data)
        
        # Build meta
        meta_dict = dict(self.meta or {})
        if self.is_fallback:
            meta_dict["fallback"] = True
        if "preserve_empty" not in meta_dict:
            meta_dict["preserve_empty"] = True
            
        if meta_dict:
            result["_meta"] = meta_dict
            
        return result


@dataclass
class ExecutionContext:
    """
    Context for card execution.
    
    Provides access to:
    - Job metadata (user_id, job_id, source, options)
    - Card metadata (card_type, card_id, retry_count)
    - Artifacts from resource cards
    - Progress emission callback
    """
    job_id: str
    card_id: int
    user_id: str
    source: str
    card_type: str
    
    # Card input from rules.py
    card_input: Dict[str, Any] = field(default_factory=dict)
    
    # Job-level options
    options: Dict[str, Any] = field(default_factory=dict)
    
    # Artifacts from completed cards
    artifacts: Dict[str, Any] = field(default_factory=dict)
    
    # Retry info
    retry_count: int = 0
    max_retries: int = 2
    
    # Progress callback: (step, message, data) -> None
    progress_callback: Optional[Callable[[str, str, Optional[Dict[str, Any]]], None]] = None
    
    def emit_progress(self, step: str, message: str, data: Optional[Dict[str, Any]] = None) -> None:
        """Emit a progress event."""
        if self.progress_callback:
            try:
                self.progress_callback(step, message, data)
            except Exception:
                pass
    
    def get_artifact(self, artifact_key: str, default: Any = None) -> Any:
        """Get an artifact by key (e.g., 'resource.github.data')."""
        return self.artifacts.get(artifact_key, default)


class CardHandler(ABC):
    """
    Abstract base class for card handlers.
    
    Each handler is responsible for:
    1. execute(): Compute/fetch the card data
    2. validate(): Check if the output is acceptable
    3. fallback(): Generate a fallback payload when validation fails
    4. normalize(): Optional output normalization (e.g., field renaming)
    """
    
    # Subclasses must set these
    source: str = ""
    card_type: str = ""
    version: str = "1"  # Bump when handler logic changes to invalidate cache
    
    @abstractmethod
    def execute(self, ctx: ExecutionContext) -> CardResult:
        """
        Execute the card logic.
        
        Args:
            ctx: Execution context with job/card metadata and artifacts
            
        Returns:
            CardResult with the computed data
            
        Raises:
            Exception: On unrecoverable errors (will trigger fallback)
        """
        pass
    
    def validate(self, data: Dict[str, Any], ctx: ExecutionContext) -> bool:
        """
        Validate the card output.
        
        Args:
            data: The card data to validate
            ctx: Execution context
            
        Returns:
            True if valid, False if should retry/fallback
            
        Default implementation: accept non-empty dicts
        """
        return isinstance(data, dict) and bool(data)
    
    @abstractmethod
    def fallback(self, ctx: ExecutionContext, error: Optional[Exception] = None) -> CardResult:
        """
        Generate fallback payload when execution/validation fails.
        
        Args:
            ctx: Execution context
            error: The exception that caused the fallback (if any)
            
        Returns:
            CardResult with fallback data (should have is_fallback=True)
        """
        pass
    
    def normalize(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normalize the output schema.
        
        Optional hook for subclasses to rename fields, add defaults, etc.
        Default implementation: pass through.
        """
        return data
    
    @classmethod
    def get_key(cls) -> tuple[str, str]:
        """Get the (source, card_type) key for this handler."""
        return (cls.source, cls.card_type)


class HandlerRegistry:
    """
    Registry for card handlers.
    
    Allows looking up handlers by (source, card_type).
    """
    
    def __init__(self):
        self._handlers: Dict[tuple[str, str], CardHandler] = {}
    
    def register(self, handler: CardHandler) -> None:
        """Register a handler instance."""
        key = handler.get_key()
        if not key[0] or not key[1]:
            raise ValueError(f"Handler must have non-empty source and card_type: {handler}")
        self._handlers[key] = handler
    
    def register_class(self, handler_class: type[CardHandler]) -> None:
        """Register a handler class (will instantiate it)."""
        self.register(handler_class())
    
    def get(self, source: str, card_type: str) -> Optional[CardHandler]:
        """Get a handler by (source, card_type)."""
        key = (str(source).strip().lower(), str(card_type).strip())
        return self._handlers.get(key)
    
    def has(self, source: str, card_type: str) -> bool:
        """Check if a handler is registered."""
        return self.get(source, card_type) is not None
    
    def list_keys(self) -> List[tuple[str, str]]:
        """List all registered (source, card_type) pairs."""
        return list(self._handlers.keys())
    
    def get_version_hash(self, source: str) -> str:
        """Get combined version hash for all handlers of a source."""
        import hashlib
        versions = []
        src = str(source).strip().lower()
        for (s, ct), handler in sorted(self._handlers.items()):
            if s == src:
                versions.append(f"{ct}:{getattr(handler, 'version', '1')}")
        if not versions:
            return "0"
        combined = "|".join(versions)
        return hashlib.sha256(combined.encode()).hexdigest()[:8]
