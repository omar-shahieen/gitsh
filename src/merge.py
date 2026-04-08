import os
import sys
from collections import deque
from datetime import datetime

from Index import GitIndex, GitIndexEntry
from Reference import ref_resolve, ref_create, branch_get_active
from objects import GitCommit, GitTree, GitTreeLeaf
from storage import object_find, object_read, object_write, repo_find


def commit_tree_sha(repo, commit_sha):
    """Return the tree SHA referenced by a commit."""
    commit = object_read(repo, commit_sha)
    if not commit or commit.fmt != b"commit":
        raise Exception(f"{commit_sha} is not a commit")
    return commit.kvlm[b"tree"].decode("ascii")


def tree_to_map(repo, ref, prefix=""):
    """Flatten a tree into a path -> blob SHA map."""
    tree_sha = object_find(repo, ref, fmt=b"tree")
    tree = object_read(repo, tree_sha)

    ret = {}
    for leaf in tree.items:
        full_path = os.path.join(prefix, leaf.path) if prefix else leaf.path
        if leaf.mode.startswith(b"04"):
            ret.update(tree_to_map(repo, leaf.sha, full_path))
        else:
            ret[full_path] = leaf.sha
    return ret


def commit_parents(repo, sha):
    """Return all parent SHAs of a commit."""
    commit = object_read(repo, sha)
    if not commit or commit.fmt != b"commit":
        return []

    parents = commit.kvlm.get(b"parent", [])
    if parents is None:
        return []
    if not isinstance(parents, list):
        parents = [parents]
    return [parent.decode("ascii") for parent in parents]


def merge_base(repo, ours, theirs):
    """Find the nearest common ancestor commit."""
    if ours == theirs:
        return ours

    ours_seen = {ours}
    queue = deque([ours])
    while queue:
        current = queue.popleft()
        for parent in commit_parents(repo, current):
            if parent not in ours_seen:
                ours_seen.add(parent)
                queue.append(parent)

    queue = deque([theirs])
    seen = {theirs}
    while queue:
        current = queue.popleft()
        if current in ours_seen:
            return current
        for parent in commit_parents(repo, current):
            if parent not in seen:
                seen.add(parent)
                queue.append(parent)

    return None


def merge_tree_maps(base_map, ours_map, theirs_map):
    """Merge two file maps using a simple three-way merge."""
    merged = {}
    conflicts = []

    for path in sorted(set(base_map) | set(ours_map) | set(theirs_map)):
        base_sha = base_map.get(path)
        ours_sha = ours_map.get(path)
        theirs_sha = theirs_map.get(path)

        if ours_sha == theirs_sha:
            if ours_sha is not None:
                merged[path] = ours_sha
            continue

        if ours_sha == base_sha:
            if theirs_sha is not None:
                merged[path] = theirs_sha
            continue

        if theirs_sha == base_sha:
            if ours_sha is not None:
                merged[path] = ours_sha
            continue

        if base_sha is None:
            if ours_sha is None and theirs_sha is not None:
                merged[path] = theirs_sha
                continue
            if theirs_sha is None and ours_sha is not None:
                merged[path] = ours_sha
                continue

        conflicts.append(path)

    return merged, conflicts


def _tree_from_nested(repo, nested):
    tree = GitTree()
    for name in sorted(nested.keys()):
        value = nested[name]
        if isinstance(value, dict):
            child_sha = _tree_from_nested(repo, value)
            leaf = GitTreeLeaf(mode=b"040000", path=name, sha=child_sha)
        else:
            leaf = GitTreeLeaf(mode=b"100644", path=name, sha=value)
        tree.items.append(leaf)
    return object_write(tree, repo)


def tree_from_map(repo, flat_map):
    """Convert a flat path map into stored tree objects and return the root SHA."""
    nested = {}

    for path, sha in flat_map.items():
        parts = path.split(os.sep)
        cursor = nested
        for part in parts[:-1]:
            cursor = cursor.setdefault(part, {})
        cursor[parts[-1]] = sha

    return _tree_from_nested(repo, nested)


def blob_data(repo, sha):
    """Return raw blob bytes for a SHA or empty bytes when absent."""
    if not sha:
        return b""

    obj = object_read(repo, sha)
    if not obj or obj.fmt != b"blob":
        return b""
    return obj.blobdata


def write_conflict_file(repo, path, base_sha, ours_sha, theirs_sha):
    """Write a Git-style conflict file to the worktree."""
    full_path = os.path.join(repo.worktree, path)
    parent = os.path.dirname(full_path)
    if parent and not os.path.exists(parent):
        os.makedirs(parent, exist_ok=True)

    base = blob_data(repo, base_sha)
    ours = blob_data(repo, ours_sha)
    theirs = blob_data(repo, theirs_sha)

    content = b"".join(
        [
            b"<<<<<<< ours\n",
            ours,
            b"\n=======\n",
            theirs,
            b"\n>>>>>>> theirs\n",
        ]
    )

    with open(full_path, "wb") as f:
        f.write(content)


def commit_from_tree(repo, tree_sha, parents, message):
    """Create a commit object with one or more parents."""
    commit = GitCommit()
    commit.kvlm = {}
    commit.kvlm[b"tree"] = tree_sha.encode("ascii")

    if len(parents) == 1:
        commit.kvlm[b"parent"] = parents[0].encode("ascii")
    elif len(parents) > 1:
        commit.kvlm[b"parent"] = [parent.encode("ascii") for parent in parents]

    author = "gitsh <gitsh@example.com>"
    timestamp = datetime.now()
    timestamp_str = str(int(timestamp.timestamp()))
    author_line = f"{author} {timestamp_str} +0000"
    commit.kvlm[b"author"] = author_line.encode("utf-8")
    commit.kvlm[b"committer"] = author_line.encode("utf-8")
    commit.kvlm[None] = message.encode("utf-8")

    return object_write(commit, repo)


def cmd_merge(args):
    """Merge another branch or commit into the current branch."""
    try:
        repo = repo_find()
        ours_sha = ref_resolve(repo, "HEAD")
        theirs_sha = object_find(repo, args.ref, fmt=b"commit")

        if not ours_sha:
            raise Exception("Current branch has no commit to merge into.")

        if ours_sha == theirs_sha:
            print(f"Already up to date with {args.ref}.")
            return

        base_sha = merge_base(repo, ours_sha, theirs_sha)

        if base_sha == theirs_sha:
            print(f"Already up to date with {args.ref}.")
            return

        if base_sha == ours_sha:
            branch = branch_get_active(repo)
            new_ref = f"refs/heads/{branch}" if branch else "HEAD"
            ref_create(repo, new_ref, theirs_sha)
            print(f"Fast-forwarded to {theirs_sha[:7]}.")
            return

        base_map = tree_to_map(repo, commit_tree_sha(repo, base_sha)) if base_sha else {}
        ours_map = tree_to_map(repo, commit_tree_sha(repo, ours_sha))
        theirs_map = tree_to_map(repo, commit_tree_sha(repo, theirs_sha))

        merged_map, conflicts = merge_tree_maps(base_map, ours_map, theirs_map)
        if conflicts:
            for path in conflicts:
                write_conflict_file(
                    repo,
                    path,
                    base_map.get(path),
                    ours_map.get(path),
                    theirs_map.get(path),
                )

            print("Merge completed with conflicts. Resolve the files and commit again.")
            print("Conflicted paths: " + ", ".join(conflicts))
            return

        merged_tree_sha = tree_from_map(repo, merged_map)
        branch = branch_get_active(repo)
        message = args.message if args.message else f"Merge {args.ref} into {branch or 'HEAD'}"
        merge_commit_sha = commit_from_tree(repo, merged_tree_sha, [ours_sha, theirs_sha], message)

        if branch:
            ref_create(repo, f"refs/heads/{branch}", merge_commit_sha)
        else:
            ref_create(repo, "HEAD", merge_commit_sha)

        print(f"✓ Merged {args.ref} into {branch or 'HEAD'} [{merge_commit_sha[:7]}]")

    except Exception as e:
        print(f"✗ Error: {e}", file=sys.stderr)
        sys.exit(1)