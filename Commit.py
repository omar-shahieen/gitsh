from typing import Any, Dict, Optional

from Blob import GitObject
from Utils import kvlm_parse, kvlm_serialize


class GitTag(GitObject):
    fmt = b"tag"

    def serialize(self) -> bytes:
        return b""

    def deserialize(self, data: bytes) -> None:
        self.data = data


class GitCommit(GitObject):
    fmt = b"commit"

    def serialize(self):
        return kvlm_serialize(self.kvlm)

    def deserialize(self, data):
        self.kvlm = kvlm_parse(data)

    def init(self):
        self.kvlm = dict()


def log_graphviz(repo: "GitRepository", sha: str, seen: Optional[set] = None) -> None:
    from Repository import object_read

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
