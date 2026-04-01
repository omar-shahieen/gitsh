import configparser
import hashlib
import os
import re
import sys
from typing import Any, List, Optional

from Blob import GitBlob, GitObject
from Commit import GitCommit, GitTag
from Tree import GitTree
from Utils import _read_decompress, _write_compressed


class GitRepository(object):
    worktree: str = ""
    gitdir: str = ""
    conf: configparser.ConfigParser

    def __init__(self, path: str, force: bool = False) -> None:
        self.worktree = path
        self.gitdir = os.path.join(path, ".gitsh")

        if not (force or os.path.isdir(self.gitdir)):
            raise Exception(f"Not a Git repository {path}")

        self.conf = configparser.ConfigParser()
        cf = repo_file(self, "config")

        if cf and os.path.exists(cf):
            self.conf.read([cf])
        elif not force:
            raise Exception("Configuration file missing")

        if not force:
            vers = int(self.conf.get("core", "repositoryformatversion"))
            if vers != 0:
                raise Exception(f"Unsupported repositoryformatversion: {vers}")


def repo_path(repo: GitRepository, *path: str) -> str:
    return os.path.join(repo.gitdir, *path)


def repo_file(repo: GitRepository, *path: str, mkdir: bool = False) -> Optional[str]:
    if repo_dir(repo, *path[:-1], mkdir=mkdir):
        return repo_path(repo, *path)
    return None


def repo_dir(repo: GitRepository, *path: str, mkdir: bool = False) -> Optional[str]:
    path = repo_path(repo, *path)

    if os.path.exists(path):
        if os.path.isdir(path):
            return path
        raise Exception(f"Not a directory {path}")

    if mkdir:
        os.makedirs(path)
        return path
    return None


def repo_default_config() -> configparser.ConfigParser:
    ret = configparser.ConfigParser()
    ret.add_section("core")
    ret.set("core", "repositoryformatversion", "0")
    ret.set("core", "filemode", "false")
    ret.set("core", "bare", "false")
    return ret


def repo_create(path: str) -> GitRepository:
    repo = GitRepository(path, True)

    if os.path.exists(repo.worktree):
        if not os.path.isdir(repo.worktree):
            raise Exception(f"{path } is not a directory!")
        if os.path.exists(repo.gitdir) and os.listdir(repo.gitdir):
            raise Exception(f"{path} is not empty!")
    else:
        os.makedirs(repo.worktree)

    assert repo_dir(repo, "branches", mkdir=True)
    assert repo_dir(repo, "objects", mkdir=True)
    assert repo_dir(repo, "refs", "tags", mkdir=True)
    assert repo_dir(repo, "refs", "heads", mkdir=True)

    with open(repo_file(repo, "description"), "w") as f:
        f.write("Unnamed repository; edit this file 'description' to name the repository.\n")

    with open(repo_file(repo, "HEAD"), "w") as f:
        f.write("ref: refs/heads/master\n")

    with open(repo_file(repo, "config"), "w") as f:
        config = repo_default_config()
        config.write(f)

    return repo


def repo_find(path: str = ".", required: bool = True) -> Optional[GitRepository]:
    path = os.path.realpath(path)

    if os.path.isdir(os.path.join(path, ".git")):
        return GitRepository(path)

    parent = os.path.realpath(os.path.join(path, ".."))
    if path == parent:
        if required:
            raise Exception("No git directory.")
        return None

    return repo_find(parent, required)


def object_write(obj: GitObject, repo: Optional[GitRepository] = None) -> str:
    data = obj.serialize()
    header = obj.fmt + b" " + str(len(data)).encode() + b"\x00"

    h = hashlib.sha1()
    h.update(header)
    h.update(data)
    sha = h.hexdigest()

    if repo:
        path = repo_file(repo, "objects", sha[0:2], sha[2:], mkdir=True)
        if not os.path.exists(path):
            _write_compressed(path, header, data)
    return sha


def object_read(repo: GitRepository, sha: str) -> Optional[GitObject]:
    path = repo_file(repo, "objects", sha[0:2], sha[2:])

    if not os.path.isfile(path):
        return None

    raw = _read_decompress(path)
    x = raw.find(b" ")
    fmt = raw[0:x]

    y = raw.find(b"\x00", x)
    size = int(raw[x + 1 : y].decode("ascii"))

    if size != len(raw) - y - 1:
        raise Exception(f"Malformed object {sha}: bad length")

    match fmt:
        case b"commit":
            c = GitCommit
        case b"tree":
            c = GitTree
        case b"tag":
            c = GitTag
        case b"blob":
            c = GitBlob
        case _:
            raise Exception(f"Unknown type {fmt.decode('ascii')} for object {sha}")

    return c(raw[y + 1 :])


def cat_file(repo: GitRepository, obj: str, fmt: Optional[bytes] = None) -> None:
    obj = object_read(repo, object_find(repo, obj, fmt=fmt))
    sys.stdout.buffer.write(obj.serialize())


def object_find(repo: GitRepository, name: str, fmt: Optional[bytes] = None, follow: bool = True) -> Optional[str]:
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


def ref_resolve(repo: GitRepository, ref: str) -> Optional[str]:
    path = repo_file(repo, ref)

    if not os.path.isfile(path):
        return None

    with open(path, "r") as fp:
        data = fp.read()[:-1]
    if data.startswith("ref: "):
        return ref_resolve(repo, data[5:])
    return data


def object_hash(fd: Any, fmt: bytes, repo: Optional[GitRepository] = None) -> str:
    data = fd.read()

    match fmt:
        case b"commit":
            obj = GitCommit(data)
        case b"tree":
            obj = GitTree(data)
        case b"tag":
            obj = GitTag(data)
        case b"blob":
            obj = GitBlob(data)
        case _:
            raise Exception(f"Unknown type {fmt}!")

    return object_write(obj, repo)
