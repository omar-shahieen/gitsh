"""Object type registry for mapping git object format bytes to classes."""

from typing import Dict, Type, Optional


_object_registry: Dict[bytes, Type] = {}


def register_object_type(fmt: bytes, cls: Type) -> None:
    """Register an object type class.
    
    Args:
        fmt: Format bytes (e.g., b"blob", b"commit", b"tree", b"tag").
        cls: The GitObject subclass.
    """
    _object_registry[fmt] = cls


def get_object_class(fmt: bytes) -> Optional[Type]:
    """Get the class for a given object format.
    
    Args:
        fmt: Format bytes.
    
    Returns:
        The GitObject subclass, or None if not registered.
    """
    return _object_registry.get(fmt)


def initialize_registry() -> None:
    """Initialize the object registry with all known object types."""
    from .blob import GitBlob
    from .commit import GitCommit
    from .tree import GitTree
    from .tag import GitTag
    
    register_object_type(b"blob", GitBlob)
    register_object_type(b"commit", GitCommit)
    register_object_type(b"tree", GitTree)
    register_object_type(b"tag", GitTag)
