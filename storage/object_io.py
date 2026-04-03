
import hashlib
import os ,re
from typing import Optional, List,Any

from storage.compression import read_decompress, write_compressed
from objects import GitObject, get_object_class, initialize_registry

from repository import GitRepository, repo_file,repo_dir

# Initialize the object registry on import
initialize_registry()


def object_write(obj: GitObject, repo: Optional[GitRepository] = None) -> str:
    """Write a Git object to the repository.

    Args:
        obj: The Git object to write.
        repo: The repository to write to (optional).

    Returns:
        The SHA hash of the written object.
    """
    data = obj.serialize()
    header = obj.fmt + b" " + str(len(data)).encode() + b"\x00"
    h = hashlib.sha1()
    h.update(header)
    h.update(data)
    sha = h.hexdigest()

    if repo:
        path = repo_file(repo, "objects", sha[0:2], sha[2:], mkdir=True)
        if not os.path.exists(path):
            write_compressed(path, header, data)
    return sha


def object_read(repo: GitRepository, sha: str) -> Optional[GitObject]:
    """Read a Git object from the repository.

    Args:
        repo: The repository to read from.
        sha: The SHA hash of the object.

    Returns:
        The Git object, or None if not found.
    """
    path = repo_file(repo, "objects", sha[0:2], sha[2:])

    if not os.path.isfile(path):
        return None

    raw = read_decompress(path)
    x = raw.find(b" ")
    fmt = raw[0:x]

    y = raw.find(b"\x00", x)
    size = int(raw[x + 1 : y].decode("ascii"))

    if size != len(raw) - y - 1:
        raise Exception(f"Malformed object {sha}: bad length")

    obj_class = get_object_class(fmt)
    if not obj_class:
        raise Exception(f"Unknown type {fmt.decode('ascii')} for object {sha}")

    return obj_class(raw[y + 1 :])


def object_find(repo: GitRepository, name: str, fmt: Optional[bytes] = None, follow: bool = True) -> Optional[str]:
    """Find an object by name and optionally verify its type.

    Args:
        repo: The repository.
        name: The object name or reference.
        fmt: Expected format (optional).
        follow: Whether to follow tags/commits to trees.

    Returns:
        The SHA hash, or None.
    """
    sha = object_resolve(repo, name)

    if not sha:
        raise Exception(f"No such reference {name}.")

    if len(sha) > 1:
        candidates_str = "\n - ".join(sha)
        raise Exception(f"Ambiguous reference {name}: Candidates are:\n - {candidates_str}.")

    sha = sha[0]

    if not fmt:
        return sha

    while True:
        obj = object_read(repo, sha)

        if obj.fmt == fmt:
            return sha

        if not follow:
            return None

        if obj.fmt == b"tag":
            sha = obj.kvlm[b"object"].decode("ascii")
        elif obj.fmt == b"commit" and fmt == b"tree":
            sha = obj.kvlm[b"tree"].decode("ascii")
        else:
            return None


def object_resolve(repo: GitRepository, name: str) -> Optional[List[str]]:
    """Resolve a name to possible SHA hashes.

    Args:
        repo: The repository.
        name: The name to resolve.

    Returns:
        List of candidate SHAs, or None.
    """
    from reference import ref_resolve
    
    candidates = list()
    hashRE = re.compile(r"^[0-9A-Fa-f]{4,40}$")

    if not name.strip():
        return None

    if name == "HEAD":
        return [ref_resolve(repo, "HEAD")]

    if hashRE.match(name):
        name = name.lower()
        prefix = name[0:2]
        path = repo_dir(repo, "objects", prefix, mkdir=False)
        if path:
            rem = name[2:]
            for f in os.listdir(path):
                if f.startswith(rem):
                    candidates.append(prefix + f)

    as_tag = ref_resolve(repo, "refs/tags/" + name)
    if as_tag:
        candidates.append(as_tag)

    as_branch = ref_resolve(repo, "refs/heads/" + name)
    if as_branch:
        candidates.append(as_branch)

    as_remote_branch = ref_resolve(repo, "refs/remotes/" + name)
    if as_remote_branch:
        candidates.append(as_remote_branch)

    return candidates


def object_hash(fd: Any, fmt: bytes, repo: Optional[GitRepository] = None) -> str:
    """Hash data from a file descriptor and write as object.

    Args:
        fd: File descriptor to read data from.
        fmt: Object format.
        repo: Repository to write to (optional).

    Returns:
        The SHA hash.
    """
    data = fd.read()

    obj_class = get_object_class(fmt)
    if not obj_class:
        raise Exception(f"Unknown type {fmt.decode('ascii')} ")
    
    obj = obj_class(data)
   

    return object_write(obj, repo)

