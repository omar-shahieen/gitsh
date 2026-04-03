import sys , os
from repository import GitRepository
from storage import object_read,object_find
from objects import GitTree
from typing import Optional



def cat_file(repo: GitRepository, obj: str, fmt: Optional[bytes] = None) -> None:
    """Output the contents of a Git object.

    Args:
        repo: The repository.
        obj: The object name.
        fmt: Expected format (optional).
    """
    obj = object_read(repo, object_find(repo, obj, fmt=fmt))
    sys.stdout.buffer.write(obj.serialize())


def tree_checkout(repo: "GitRepository", tree: "GitTree", path: str) -> None:
    """Checkout a tree to a directory path.

    Args:
        repo: The repository.
        tree: The GitTree object.
        path: The destination path.
    """
    for item in tree.items:
        
        obj = object_read(repo, item.sha)
        
        dest = os.path.join(path, item.path)
        
        if obj.fmt == b'tree':
            os.mkdir(dest)
            tree_checkout(repo, obj, dest)
            
            
        elif obj.fmt == b'blob':
            with open(dest, 'wb') as f:
                f.write(obj.blobdata)
                
                


def log_graphviz(repo: "GitRepository", sha: str, seen: Optional[set] = None) -> None:
    """Generate GraphViz dot format for commit graph.

    Args:
        repo: The repository.
        sha: The commit SHA.
        seen: Set of already processed SHAs.
    """
    if seen is None:
        seen = set()
    if sha in seen:
        return
    seen.add(sha)

    commit = object_read(repo, sha)
    assert commit.fmt == b"commit", f"Expected commit, got {commit.fmt} for {sha}"

    short_sha = sha[0:7]
    raw_message = commit.kvlm[None].decode("utf8").strip()
    subject = raw_message.splitlines()[0] if raw_message else "(no message)"
    subject = subject.replace("\\", "\\\\").replace('"', '\\"')

    author_line = commit.kvlm.get(b"author", b"").decode("utf8")
    author_name = author_line.split("<")[0].strip() if "<" in author_line else author_line

    label = f"{short_sha}\\n{subject}\\n{author_name}"
    print(f'  c_{sha} [label="{label}"]')

    parents = commit.kvlm.get(b"parent", None)
    if parents is None:
        return

    if not isinstance(parents, list):
        parents = [parents]

    for p in parents:
        p = p.decode("ascii")
        print(f"  c_{sha} -> c_{p}")
        log_graphviz(repo, p, seen)



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

