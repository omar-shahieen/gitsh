from abc import ABC, abstractmethod
from typing import Optional


class GitObject(ABC):
    """Abstract base class for all Git objects."""

    def __init__(self, data: Optional[bytes] = None) -> None:
        """Initialize the Git object.

        Args:
            data: Serialized data to deserialize, or None to initialize empty.
        """
        if data is not None:
            self.deserialize(data)
        else:
            self.init()

    @abstractmethod
    def serialize(self) -> bytes:
        """Serialize the object to bytes.

        Returns:
            The serialized data.
        """
        ...

    @abstractmethod
    def deserialize(self, data: bytes) -> None:
        """Deserialize the object from bytes.

        Args:
            data: The serialized data.
        """
        ...

    def init(self) -> None:
        """Initialize the object with default values."""
        pass
