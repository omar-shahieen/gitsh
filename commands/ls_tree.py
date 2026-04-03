from repository import object_find, object_read, GitRepository
from typing import Optional
import os

def ls_tree(repo: "GitRepository", ref: str, recursive: Optional[bool] = None, prefix: str = "") -> None:
    """List the contents of a tree object.

    Args:
        repo: The repository.
        ref: The tree reference.
        recursive: Whether to list recursively.
        prefix: Path prefix for output.
    """
    sha = object_find(repo, ref, fmt=b"tree")
    obj = object_read(repo, sha)

    for item in obj.items:
        
        item.mode.rjust(6, b'0') # pad with leading zeros if len = 5
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

