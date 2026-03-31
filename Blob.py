from abc import ABC, abstractmethod
from typing import Optional


class GitObject(ABC):
    def __init__(self, data: Optional[bytes] = None) -> None:
        if data is not None:
            self.deserialize(data)
        else:
            self.init()

    @abstractmethod
    def serialize(self) -> bytes:
        ...

    @abstractmethod
    def deserialize(self, data: bytes) -> None:
        ...

    def init(self) -> None:
        pass


class GitBlob(GitObject):
    fmt = b"blob"

    def serialize(self):
        return self.blobdata

    def deserialize(self, data):
        self.blobdata = data
