from .gitobject import GitObject
from storage import kvlm_parse, kvlm_serialize

class GitCommit(GitObject):
    """Represents a Git commit object."""

    fmt = b"commit"

    def serialize(self) -> bytes:
        """Serialize the commit data.

        Returns:
            The serialized commit data.
        """
        return kvlm_serialize(self.kvlm)

    def deserialize(self, data: bytes) -> None:
        """Deserialize the commit data.

        Args:
            data: The commit data.
        """
        self.kvlm = kvlm_parse(data)

    def init(self) -> None:
        """Initialize the commit with an empty KVL map."""
        self.kvlm = dict()

