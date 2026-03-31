import os
from typing import List, Optional, Tuple

from Blob import GitObject


class GitTreeLeaf(object):
    def __init__(self, mode: bytes, path: str, sha: str) -> None:
        self.mode: bytes = mode
        self.path: str = path
        self.sha: str = sha


def tree_parse_one(raw: bytes, start: int = 0) -> Tuple[int, GitTreeLeaf]:
    x = raw.find(b" ", start)
    assert x - start == 5 or x - start == 6

    mode = raw[start:x]
    if len(mode) == 5:
        mode = b"0" + mode

    y = raw.find(b"\x00", x)
    path = raw[x + 1 : y]

    raw_sha = int.from_bytes(raw[y + 1 : y + 21], "big")
    sha = format(raw_sha, "040x")

    return y + 21, GitTreeLeaf(mode, path.decode("utf8"), sha)


def tree_parse(raw: bytes) -> List[GitTreeLeaf]:
    pos = 0
    max_len = len(raw)
    ret: List[GitTreeLeaf] = []
    while pos < max_len:
        pos, data = tree_parse_one(raw, pos)
        ret.append(data)
    return ret


def tree_leaf_sort_key(leaf: GitTreeLeaf) -> str:
    if leaf.mode.startswith(b"4"):
        return leaf.path + "/"
    return leaf.path


def tree_serialize(obj: "GitTree") -> bytes:
    obj.items.sort(key=tree_leaf_sort_key)
    ret = b""

    for i in obj.items:
        ret += i.mode
        ret += b" "
        ret += i.path.encode("utf8")
        ret += b"\x00"
        sha = int(i.sha, 16)
        ret += sha.to_bytes(20, byteorder="big")

    return ret


class GitTree(GitObject):
    fmt = b"tree"

    def serialize(self):
        return tree_serialize(self)

    def deserialize(self, data):
        self.items = tree_parse(data)

    def init(self):
        self.items = list()


def ls_tree(repo: "GitRepository", ref: str, recursive: Optional[bool] = None, prefix: str = "") -> None:
    from Repository import object_find, object_read

    sha = object_find(repo, ref, fmt=b"tree")
    obj = object_read(repo, sha)

    for item in obj.items:
        if len(item.mode) == 5:
            type = item.mode[0:1]
        else:
            type = item.mode[0:2]

        match type:
            case b"04":
                type = "tree"
            case b"10":
                type = "blob"
            case b"12":
                type = "blob"
            case b"16":
                type = "commit"
            case _:
                raise Exception(f"Weird tree leaf mode {item.mode}")

        if not (recursive and type == "tree"):
            print(
                f"{'0' * (6 - len(item.mode)) + item.mode.decode('ascii')} {type} {item.sha}\t{os.path.join(prefix, item.path)}"
            )
        else:
            ls_tree(repo, item.sha, recursive, os.path.join(prefix, item.path))
