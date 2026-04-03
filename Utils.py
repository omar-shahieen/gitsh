from typing import Any, Dict, Optional,List
import hashlib
import os
import re
import sys
import zlib ,tempfile
from Blob import GitBlob, GitObject
from Tree import GitTree
from Repository import GitRepository,repo_dir,ref_resolve,repo_file


def _read_decompress(path: str, chunk_size: int = 65536) -> bytes:
    decompressor = zlib.decompressobj()
    parts = []

    with open(path, "rb") as f:
        while chunk := f.read(chunk_size):
            parts.append(decompressor.decompress(chunk))
        parts.append(decompressor.flush())

    return b"".join(parts)


def _write_compressed(path: str, header: bytes, data: bytes, chunk_size: int = 65536) -> None:
    dir_path = os.path.dirname(path)
    compressor = zlib.compressobj()

    with tempfile.NamedTemporaryFile(dir=dir_path, delete=False) as tmp:
        tmp_path = tmp.name
        try:
            tmp.write(compressor.compress(header))

            view = memoryview(data)
            for i in range(0, len(data), chunk_size):
                tmp.write(compressor.compress(view[i : i + chunk_size]))

            tmp.write(compressor.flush())
        except:
            os.unlink(tmp_path)
            raise

    os.replace(tmp_path, path)



def compute_file_hash(filepath: str, algorithm: str = "sha1", BUFF_SIZE: int = 65536) -> str:
    hash_func = hashlib.new(algorithm)

    with open(filepath, "rb") as file:
        while chunk := file.read(BUFF_SIZE):
            hash_func.update(chunk)

    return hash_func.hexdigest()



def kvlm_parse(
    raw: bytes, start: int = 0, dct: Optional[Dict[Optional[bytes], Any]] = None
) -> Dict[Optional[bytes], Any]:
    if not dct:
        dct = dict()

    spc = raw.find(b" ", start)
    nl = raw.find(b"\n", start)

    if (spc < 0) or (nl < spc):
        assert nl == start
        dct[None] = raw[start + 1 :]
        return dct

    key = raw[start:spc]

    end = start
    while True:
        end = raw.find(b"\n", end + 1)
        if raw[end + 1] != ord(" "):
            break

    value = raw[spc + 1 : end].replace(b"\n ", b"\n")

    if key in dct:
        if type(dct[key]) == list:
            dct[key].append(value)
        else:
            dct[key] = [dct[key], value]
    else:
        dct[key] = value

    return kvlm_parse(raw, start=end + 1, dct=dct)


def kvlm_serialize(kvlm: Dict[Optional[bytes], Any]) -> bytes:
    ret = b""

    for k in kvlm.keys():
        if k is None:
            continue
        val = kvlm[k]

        if not isinstance(val, list):
            val = [val]

        for v in val:
            ret += k + b" " + (v.replace(b"\n", b"\n ")) + b"\n"

    ret += b"\n" + kvlm[None]
    return ret



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

    from Commit import GitCommit, GitTag

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


def object_hash(fd: Any, fmt: bytes, repo: Optional[GitRepository] = None) -> str:
    data = fd.read()


    from Commit import GitCommit, GitTag

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
