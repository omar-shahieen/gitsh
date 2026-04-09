import os
from fnmatch import fnmatch
from math import ceil
from typing import Dict, List, Optional, Tuple

from storage import object_read
from storage.object_io import object_hash
from storage.repository import GitRepository, repo_file

try:
    import grp
    import pwd
except ModuleNotFoundError:
    grp = None
    pwd = None


class GitIndexEntry(object):
    def __init__(
        self,
        ctime: Tuple[int, int],
        mtime: Tuple[int, int],
        dev: int,
        ino: int,
        mode_type: int,
        mode_perms: int,
        uid: int,
        gid: int,
        fsize: int,
        sha: str,
        flag_assume_valid: bool,
        flag_stage: int,
        name: str,
    ) -> None:
        self.ctime = ctime
        self.mtime = mtime
        self.dev = dev
        self.ino = ino
        self.mode_type = mode_type
        self.mode_perms = mode_perms
        self.uid = uid
        self.gid = gid
        self.fsize = fsize
        self.sha = sha
        self.flag_assume_valid = flag_assume_valid
        self.flag_stage = flag_stage
        self.name = name


class GitIndex(object):
    def __init__(self, repo: GitRepository, version: int = 2, entries: Optional[List[GitIndexEntry]] = None) -> None:
        self.repo = repo
        self.version = version
        self.entries = entries if entries is not None else []

    def save(self) -> None:
        index_write(self.repo, self)

    def add(self, filepath: str) -> None:
        add(self.repo, [filepath])
        refreshed = index_read(self.repo)
        self.version = refreshed.version
        self.entries = refreshed.entries

    def rm(self, filepath: str) -> None:
        rm(self.repo, [filepath], delete=False, skip_missing=False)
        refreshed = index_read(self.repo)
        self.version = refreshed.version
        self.entries = refreshed.entries

    def clear(self) -> None:
        self.entries = []
        self.save()


class GitIgnore(object):
    def __init__(self, absolute: List[List[Tuple[str, bool]]], scoped: Dict[str, List[Tuple[str, bool]]]) -> None:
        self.absolute = absolute
        self.scoped = scoped


def index_read(repo: GitRepository) -> GitIndex:
    index_file = repo_file(repo, "index")
    if not index_file or not os.path.exists(index_file):
        return GitIndex(repo)

    with open(index_file, "rb") as f:
        raw = f.read()

    header = raw[:12]
    signature = header[:4]
    if signature != b"DIRC":
        raise Exception("Unsupported index format (expected DIRC)")

    version = int.from_bytes(header[4:8], "big")
    if version != 2:
        raise Exception("gitsh currently supports index version 2 only")

    count = int.from_bytes(header[8:12], "big")
    entries: List[GitIndexEntry] = []

    content = raw[12:]
    idx = 0
    for _ in range(count):
        ctime_s = int.from_bytes(content[idx: idx + 4], "big")
        ctime_ns = int.from_bytes(content[idx + 4: idx + 8], "big")
        mtime_s = int.from_bytes(content[idx + 8: idx + 12], "big")
        mtime_ns = int.from_bytes(content[idx + 12: idx + 16], "big")
        dev = int.from_bytes(content[idx + 16: idx + 20], "big")
        ino = int.from_bytes(content[idx + 20: idx + 24], "big")

        unused = int.from_bytes(content[idx + 24: idx + 26], "big")
        if unused != 0:
            raise Exception("Unsupported index entry extension bits")

        mode = int.from_bytes(content[idx + 26: idx + 28], "big")
        mode_type = mode >> 12
        mode_perms = mode & 0b0000000111111111

        uid = int.from_bytes(content[idx + 28: idx + 32], "big")
        gid = int.from_bytes(content[idx + 32: idx + 36], "big")
        fsize = int.from_bytes(content[idx + 36: idx + 40], "big")
        sha = format(int.from_bytes(content[idx + 40: idx + 60], "big"), "040x")

        flags = int.from_bytes(content[idx + 60: idx + 62], "big")
        flag_assume_valid = (flags & 0b1000000000000000) != 0
        flag_extended = (flags & 0b0100000000000000) != 0
        if flag_extended:
            raise Exception("Extended index flags are not supported")
        flag_stage = flags & 0b0011000000000000
        name_length = flags & 0b0000111111111111

        idx += 62

        if name_length < 0xFFF:
            raw_name = content[idx:idx + name_length]
            idx += name_length + 1
        else:
            null_idx = content.find(b"\x00", idx + 0xFFF)
            raw_name = content[idx:null_idx]
            idx = null_idx + 1

        name = raw_name.decode("utf8")
        idx = 8 * ceil(idx / 8)

        entries.append(
            GitIndexEntry(
                ctime=(ctime_s, ctime_ns),
                mtime=(mtime_s, mtime_ns),
                dev=dev,
                ino=ino,
                mode_type=mode_type,
                mode_perms=mode_perms,
                uid=uid,
                gid=gid,
                fsize=fsize,
                sha=sha,
                flag_assume_valid=flag_assume_valid,
                flag_stage=flag_stage,
                name=name,
            )
        )

    return GitIndex(repo, version=version, entries=entries)


def index_write(repo: GitRepository, index: GitIndex) -> None:
    index_path = repo_file(repo, "index", mkdir=True)
    if not index_path:
        raise Exception("Could not create index path")

    with open(index_path, "wb") as f:
        f.write(b"DIRC")
        f.write(index.version.to_bytes(4, "big"))
        f.write(len(index.entries).to_bytes(4, "big"))

        idx = 0
        for e in sorted(index.entries, key=lambda x: x.name):
            f.write((e.ctime[0] & 0xFFFFFFFF).to_bytes(4, "big"))
            f.write((e.ctime[1] & 0xFFFFFFFF).to_bytes(4, "big"))
            f.write((e.mtime[0] & 0xFFFFFFFF).to_bytes(4, "big"))
            f.write((e.mtime[1] & 0xFFFFFFFF).to_bytes(4, "big"))
            f.write((e.dev & 0xFFFFFFFF).to_bytes(4, "big"))
            f.write((e.ino & 0xFFFFFFFF).to_bytes(4, "big"))
            f.write((0).to_bytes(2, "big"))

            mode = (e.mode_type << 12) | e.mode_perms
            f.write(mode.to_bytes(2, "big"))

            f.write((e.uid & 0xFFFFFFFF).to_bytes(4, "big"))
            f.write((e.gid & 0xFFFFFFFF).to_bytes(4, "big"))
            f.write((e.fsize & 0xFFFFFFFF).to_bytes(4, "big"))
            f.write(int(e.sha, 16).to_bytes(20, "big"))

            flag_assume_valid = (0x1 << 15) if e.flag_assume_valid else 0
            name_bytes = e.name.encode("utf8")
            name_length = min(len(name_bytes), 0xFFF)
            flags = flag_assume_valid | e.flag_stage | name_length
            f.write(flags.to_bytes(2, "big"))

            f.write(name_bytes)
            f.write((0).to_bytes(1, "big"))

            idx += 62 + len(name_bytes) + 1
            if idx % 8 != 0:
                pad = 8 - (idx % 8)
                f.write((0).to_bytes(pad, "big"))
                idx += pad


def rm(repo: GitRepository, paths: List[str], delete: bool = True, skip_missing: bool = False) -> None:
    index = index_read(repo)
    worktree = os.path.realpath(repo.worktree) + os.sep

    abspaths = set()
    for path in paths:
        abspath = os.path.realpath(path if os.path.isabs(path) else os.path.join(repo.worktree, path))
        if abspath.startswith(worktree):
            abspaths.add(abspath)
        else:
            raise Exception(f"Cannot remove paths outside worktree: {path}")

    kept_entries: List[GitIndexEntry] = []
    removed_paths: List[str] = []

    for e in index.entries:
        full_path = os.path.realpath(os.path.join(repo.worktree, e.name))
        if full_path in abspaths:
            removed_paths.append(full_path)
            abspaths.remove(full_path)
        else:
            kept_entries.append(e)

    if abspaths and not skip_missing:
        raise Exception(f"Cannot remove paths not in index: {sorted(abspaths)}")

    if delete:
        for path in removed_paths:
            if os.path.exists(path):
                os.unlink(path)

    index.entries = kept_entries
    index_write(repo, index)


def add(repo: GitRepository, paths: List[str]) -> None:
    rm(repo, paths, delete=False, skip_missing=True)
    index = index_read(repo)

    worktree = os.path.realpath(repo.worktree) + os.sep

    for path in paths:
        abspath = os.path.realpath(path if os.path.isabs(path) else os.path.join(repo.worktree, path))
        if not abspath.startswith(worktree):
            raise Exception(f"Path outside worktree: {path}")
        if not os.path.isfile(abspath):
            raise Exception(f"Not a file: {path}")

        relpath = os.path.relpath(abspath, repo.worktree)
        with open(abspath, "rb") as fd:
            sha = object_hash(fd, b"blob", repo)

        stat = os.stat(abspath)
        mode_perms = 0o644

        index.entries.append(
            GitIndexEntry(
                ctime=(int(stat.st_ctime), stat.st_ctime_ns % 10**9),
                mtime=(int(stat.st_mtime), stat.st_mtime_ns % 10**9),
                dev=stat.st_dev,
                ino=stat.st_ino,
                mode_type=0b1000,
                mode_perms=mode_perms,
                uid=stat.st_uid,
                gid=stat.st_gid,
                fsize=stat.st_size,
                sha=sha,
                flag_assume_valid=False,
                flag_stage=0,
                name=relpath,
            )
        )

    index_write(repo, index)


def gitignore_parse1(raw: str) -> Optional[Tuple[str, bool]]:
    raw = raw.strip()
    if not raw or raw[0] == "#":
        return None
    if raw[0] == "!":
        return (raw[1:], False)
    if raw[0] == "\\":
        return (raw[1:], True)
    return (raw, True)


def gitignore_parse(lines: List[str]) -> List[Tuple[str, bool]]:
    ret: List[Tuple[str, bool]] = []
    for line in lines:
        parsed = gitignore_parse1(line)
        if parsed:
            ret.append(parsed)
    return ret


def gitignore_read(repo: GitRepository) -> GitIgnore:
    ret = GitIgnore(absolute=[], scoped={})

    local_exclude = os.path.join(repo.gitdir, "info", "exclude")
    if os.path.exists(local_exclude):
        with open(local_exclude, "r", encoding="utf8", errors="ignore") as f:
            ret.absolute.append(gitignore_parse(f.readlines()))

    config_home = os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config"))
    global_exclude = os.path.join(config_home, "git", "ignore")
    if os.path.exists(global_exclude):
        with open(global_exclude, "r", encoding="utf8", errors="ignore") as f:
            ret.absolute.append(gitignore_parse(f.readlines()))

    index = index_read(repo)
    for entry in index.entries:
        if entry.name == ".gitignore" or entry.name.endswith("/.gitignore"):
            dir_name = os.path.dirname(entry.name)
            contents = object_read(repo, entry.sha)
            lines = contents.blobdata.decode("utf8", errors="ignore").splitlines()
            ret.scoped[dir_name] = gitignore_parse(lines)

    return ret


def check_ignore1(rules: List[Tuple[str, bool]], path: str) -> Optional[bool]:
    result = None
    for pattern, value in rules:
        if fnmatch(path, pattern):
            result = value
    return result


def check_ignore_scoped(rules: Dict[str, List[Tuple[str, bool]]], path: str) -> Optional[bool]:
    parent = os.path.dirname(path)
    while True:
        if parent in rules:
            result = check_ignore1(rules[parent], path)
            if result is not None:
                return result
        if parent == "":
            break
        parent = os.path.dirname(parent)
    return None


def check_ignore_absolute(rules: List[List[Tuple[str, bool]]], path: str) -> bool:
    for ruleset in rules:
        result = check_ignore1(ruleset, path)
        if result is not None:
            return result
    return False


def check_ignore(rules: GitIgnore, path: str) -> bool:
    if os.path.isabs(path):
        raise Exception("Path must be relative to repository root")

    path = path.replace(os.sep, "/")
    scoped = check_ignore_scoped(rules.scoped, path)
    if scoped is not None:
        return scoped
    return check_ignore_absolute(rules.absolute, path)


def index_load(repo: GitRepository) -> GitIndex:
    return index_read(repo)


def index_save(index: GitIndex) -> None:
    index_write(index.repo, index)


def format_owner(uid: int, gid: int) -> str:
    if pwd is None or grp is None:
        return f"user: {uid}  group: {gid}"
    return f"user: {pwd.getpwuid(uid).pw_name} ({uid})  group: {grp.getgrgid(gid).gr_name} ({gid})"
