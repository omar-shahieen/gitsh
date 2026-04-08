from typing import List, Tuple
from .gitobject import GitObject

class _GitTreeLeaf(object):
    """Represents a leaf in a Git tree."""

    def __init__(self, mode: bytes, path: str, sha: str) -> None:
        """Initialize a tree leaf.

        Args:
            mode: The file mode.
            path: The file path.
            sha: The SHA hash.
        """
        self.mode: bytes = mode
        self.path: str = path
        self.sha: str = sha

class GitTree(GitObject):
    """Represents a Git tree object."""

    fmt = b"tree"

    def serialize(self) -> bytes:
        """Serialize the tree data.

        Returns:
            The serialized tree data.
        """
        return _tree_serialize(self)

    def deserialize(self, data: bytes) -> None:
        """Deserialize the tree data.

        Args:
            data: The tree data.
        """
        self.items = _tree_parse(data)

    def init(self) -> None:
        """Initialize the tree with an empty items list."""
        self.items = list()



def _tree_parse_one(raw: bytes, start: int = 0) -> Tuple[int, _GitTreeLeaf]:
    """Parse a single tree leaf from raw bytes.

    Args:
        raw: The raw bytes.
        start: The starting position.

    Returns:
        A tuple of (new_position, leaf).
    """
    x = raw.find(b" ", start)
    assert x - start == 5 or x - start == 6

    mode = raw[start:x]
    if len(mode) == 5:
        mode = b"0" + mode

    y = raw.find(b"\x00", x)
    path = raw[x + 1 : y]

    raw_sha = int.from_bytes(raw[y + 1 : y + 21], "big")
    sha = format(raw_sha, "040x")

    return y + 21, _GitTreeLeaf(mode, path.decode("utf8"), sha)


def _tree_parse(raw: bytes) -> List[_GitTreeLeaf]:
    """Parse all tree leaves from raw bytes.

    Args:
        raw: The raw bytes.

    Returns:
        A list of tree leaves.
    """
    pos = 0
    max_len = len(raw)
    ret: List[_GitTreeLeaf] = []
    while pos < max_len:
        pos, data = _tree_parse_one(raw, pos)
        ret.append(data)
    return ret


def _tree_leaf_sort_key(leaf: _GitTreeLeaf) -> str:
    """Get the sort key for a tree leaf.

    Args:
        leaf: The tree leaf.

    Returns:
        The sort key string.
    """
    if leaf.mode.startswith(b"4"):
        return leaf.path + "/"
    return leaf.path


def _tree_serialize(obj: "GitTree") -> bytes:
    """Serialize a GitTree object.

    Args:
        obj: The GitTree object.

    Returns:
        The serialized bytes.
    """
    obj.items.sort(key=_tree_leaf_sort_key)
    ret = b""

    for i in obj.items:
        ret += i.mode
        ret += b" "
        ret += i.path.encode("utf8")
        ret += b"\x00"
        sha = int(i.sha, 16)
        ret += sha.to_bytes(20, byteorder="big")

    return ret


