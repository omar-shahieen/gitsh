from .gitobject import GitObject

class GitBlob(GitObject):
    """Represents a Git blob object."""

    fmt = b"blob"

    def serialize(self) -> bytes:
        """Serialize the blob data.

        Returns:
            The blob data.
        """
        return self.blobdata

    def deserialize(self, data: bytes) -> None:
        """Deserialize the blob data.

        Args:
            data: The blob data.
        """
        self.blobdata = data
