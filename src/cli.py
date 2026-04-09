#!/usr/bin/env python3
"""Command-line interface for gitsh."""

import argparse
import os
import sys
from datetime import datetime

from Index import (
    add as index_add,
    check_ignore,
    format_owner,
    gitignore_read,
    index_read,
    index_write,
    rm as index_rm,
)
from Reference import branch_get_active, ref_create, ref_list, ref_resolve
from commands import cat_file, log_graphviz, ls_tree, show_ref, tag_create, tree_checkout
from merge import cmd_merge
from objects import GitCommit, GitTree, GitTreeLeaf
from storage import object_find, object_read, object_write, repo_create, repo_file, repo_find
from storage.object_io import object_hash


def tree_to_dict(repo, ref, prefix=""):
    ret = {}
    tree_sha = object_find(repo, ref, fmt=b"tree")
    tree = object_read(repo, tree_sha)

    for leaf in tree.items:
        full_path = os.path.join(prefix, leaf.path) if prefix else leaf.path
        if leaf.mode.startswith(b"04"):
            ret.update(tree_to_dict(repo, leaf.sha, full_path))
        else:
            ret[full_path] = leaf.sha
    return ret


def tree_from_index(repo, index):
    contents = {"": []}

    for entry in index.entries:
        dirname = os.path.dirname(entry.name)

        key = dirname
        while key != "":
            if key not in contents:
                contents[key] = []
            key = os.path.dirname(key)

        contents[dirname].append(entry)

    sorted_paths = sorted(contents.keys(), key=len, reverse=True)
    sha = None

    for path in sorted_paths:
        tree = GitTree()

        for entry in contents[path]:
            if isinstance(entry, tuple):
                leaf = GitTreeLeaf(mode=b"040000", path=entry[0], sha=entry[1])
            else:
                leaf_mode = f"{entry.mode_type:02o}{entry.mode_perms:04o}".encode("ascii")
                leaf = GitTreeLeaf(mode=leaf_mode, path=os.path.basename(entry.name), sha=entry.sha)
            tree.items.append(leaf)

        sha = object_write(tree, repo)

        parent = os.path.dirname(path)
        if path != "":
            base = os.path.basename(path)
            contents[parent].append((base, sha))

    return sha


def gitconfig_read():
    xdg_config_home = os.environ.get("XDG_CONFIG_HOME", "~/.config")
    configfiles = [
        os.path.expanduser(os.path.join(xdg_config_home, "git", "config")),
        os.path.expanduser("~/.gitconfig"),
    ]

    import configparser

    config = configparser.ConfigParser()
    config.read(configfiles)
    return config


def gitconfig_user_get(config):
    if "user" in config and "name" in config["user"] and "email" in config["user"]:
        return f"{config['user']['name']} <{config['user']['email']}>"
    return None


def commit_create(repo, tree, parent, author, timestamp, message):
    commit = GitCommit()
    commit.kvlm = {}
    commit.kvlm[b"tree"] = tree.encode("ascii")
    if parent:
        commit.kvlm[b"parent"] = parent.encode("ascii")

    message = message.strip() + "\n"

    offset_seconds = int(timestamp.astimezone().utcoffset().total_seconds())
    sign = "+" if offset_seconds >= 0 else "-"
    abs_offset = abs(offset_seconds)
    hours = abs_offset // 3600
    minutes = (abs_offset % 3600) // 60
    tz = f"{sign}{hours:02}{minutes:02}"

    author_line = f"{author} {int(timestamp.timestamp())} {tz}"
    commit.kvlm[b"author"] = author_line.encode("utf8")
    commit.kvlm[b"committer"] = author_line.encode("utf8")
    commit.kvlm[None] = message.encode("utf8")

    return object_write(commit, repo)


def cmd_init(args):
    repo_create(args.path)


def cmd_add(args):
    repo = repo_find()
    index_add(repo, args.path)


def cmd_rm(args):
    repo = repo_find()
    index_rm(repo, args.path)


def cmd_ls_files(args):
    repo = repo_find()
    index = index_read(repo)

    if args.verbose:
        print(f"Index file format v{index.version}, containing {len(index.entries)} entries.")

    for e in index.entries:
        print(e.name)
        if args.verbose:
            entry_type = {
                0b1000: "regular file",
                0b1010: "symlink",
                0b1110: "git link",
            }.get(e.mode_type, "unknown")
            print(f"  {entry_type} with perms: {e.mode_perms:o}")
            print(f"  on blob: {e.sha}")
            print(
                "  created: "
                f"{datetime.fromtimestamp(e.ctime[0])}.{e.ctime[1]}, "
                f"modified: {datetime.fromtimestamp(e.mtime[0])}.{e.mtime[1]}"
            )
            print(f"  device: {e.dev}, inode: {e.ino}")
            print("  " + format_owner(e.uid, e.gid))
            print(f"  flags: stage={e.flag_stage} assume_valid={e.flag_assume_valid}")


def cmd_check_ignore(args):
    repo = repo_find()
    rules = gitignore_read(repo)
    for path in args.path:
        if check_ignore(rules, path):
            print(path)


def cmd_status(_args):
    repo = repo_find()
    index = index_read(repo)

    branch = branch_get_active(repo)
    if branch:
        print(f"On branch {branch}")
    else:
        print(f"HEAD detached at {object_find(repo, 'HEAD')}")

    print("Changes to be committed:")
    head = tree_to_dict(repo, "HEAD") if ref_resolve(repo, "HEAD") else {}

    for entry in index.entries:
        if entry.name in head:
            if head[entry.name] != entry.sha:
                print(f"  modified: {entry.name}")
            del head[entry.name]
        else:
            print(f"  added:    {entry.name}")

    for name in head.keys():
        print(f"  deleted:  {name}")

    print()
    print("Changes not staged for commit:")

    ignore = gitignore_read(repo)
    gitdir_prefix = repo.gitdir + os.path.sep

    all_files = []
    for root, dirs, files in os.walk(repo.worktree, topdown=True):
        if root == repo.gitdir or root.startswith(gitdir_prefix):
            continue
        dirs[:] = [d for d in dirs if d != ".gitsh"]
        for f in files:
            full_path = os.path.join(root, f)
            rel_path = os.path.relpath(full_path, repo.worktree)
            all_files.append(rel_path)

    for entry in index.entries:
        full_path = os.path.join(repo.worktree, entry.name)
        if not os.path.exists(full_path):
            print(f"  deleted:  {entry.name}")
        else:
            st = os.stat(full_path)
            ctime_ns = entry.ctime[0] * 10**9 + entry.ctime[1]
            mtime_ns = entry.mtime[0] * 10**9 + entry.mtime[1]
            if st.st_ctime_ns != ctime_ns or st.st_mtime_ns != mtime_ns:
                with open(full_path, "rb") as fd:
                    new_sha = object_hash(fd, b"blob", None)
                if new_sha != entry.sha:
                    print(f"  modified: {entry.name}")

        if entry.name in all_files:
            all_files.remove(entry.name)

    print()
    print("Untracked files:")
    for rel_path in all_files:
        if not check_ignore(ignore, rel_path):
            print(f"  {rel_path}")


def cmd_commit(args):
    repo = repo_find()
    index = index_read(repo)

    if not index.entries:
        raise Exception("Nothing staged for commit")

    user = gitconfig_user_get(gitconfig_read())
    if not user:
        user = "gitsh <gitsh@example.com>"

    tree = tree_from_index(repo, index)
    parent = ref_resolve(repo, "HEAD")
    commit = commit_create(repo, tree, parent, user, datetime.now(), args.message)

    active_branch = branch_get_active(repo)
    if active_branch:
        with open(repo_file(repo, os.path.join("refs", "heads", active_branch)), "w", encoding="utf8") as fd:
            fd.write(commit + "\n")
    else:
        with open(repo_file(repo, "HEAD"), "w", encoding="utf8") as fd:
            fd.write(commit + "\n")

    print(f"[{active_branch if active_branch else 'detached'} {commit[:7]}] {args.message}")


def cmd_log(args):
    repo = repo_find()
    print("digraph gitshlog{")
    print("  node[shape=rect]")
    log_graphviz(repo, object_find(repo, args.commit), set())
    print("}")


def cmd_checkout(args):
    repo = repo_find()
    obj = object_read(repo, object_find(repo, args.commit))

    if obj.fmt == b"commit":
        obj = object_read(repo, obj.kvlm[b"tree"].decode("ascii"))

    if os.path.exists(args.path):
        if not os.path.isdir(args.path):
            raise Exception(f"Not a directory: {args.path}")
        if os.listdir(args.path):
            raise Exception(f"Not empty: {args.path}")
    else:
        os.makedirs(args.path)

    tree_checkout(repo, obj, os.path.realpath(args.path))


def cmd_ls_tree(args):
    repo = repo_find()
    ls_tree(repo, args.tree, args.recursive)


def cmd_cat_file(args):
    repo = repo_find()
    cat_file(repo, args.object, fmt=args.type.encode())


def cmd_hash_object(args):
    repo = repo_find() if args.write else None
    with open(args.path, "rb") as fd:
        sha = object_hash(fd, args.type.encode(), repo)
    print(sha)


def cmd_rev_parse(args):
    repo = repo_find()
    fmt = args.type.encode() if args.type else None
    print(object_find(repo, args.name, fmt=fmt, follow=True))


def cmd_tag(args):
    repo = repo_find()
    if args.name:
        target = args.object if args.object else "HEAD"
        tag_create(
            repo,
            args.name,
            object_find(repo, target),
            create_annotated_tag=args.annotated,
            message=args.message.encode("utf8") if args.message else b"",
        )
    else:
        refs = ref_list(repo)
        if "tags" in refs:
            show_ref(repo, refs["tags"], with_hash=False)


def cmd_show_ref(_args):
    repo = repo_find()
    refs = ref_list(repo)
    show_ref(repo, refs, prefix="refs")


def build_parser():
    parser = argparse.ArgumentParser(description="gitsh - a tiny Git-like implementation")
    subparsers = parser.add_subparsers(title="Commands", dest="command", required=True)

    p = subparsers.add_parser("init", help="Initialize a new, empty repository")
    p.add_argument("path", nargs="?", default=".", help="Where to create the repository")
    p.set_defaults(func=cmd_init)

    p = subparsers.add_parser("add", help="Add files contents to the index")
    p.add_argument("path", nargs="+", help="Files to add")
    p.set_defaults(func=cmd_add)

    p = subparsers.add_parser("rm", help="Remove files from the working tree and index")
    p.add_argument("path", nargs="+", help="Files to remove")
    p.set_defaults(func=cmd_rm)

    p = subparsers.add_parser("status", help="Show working tree status")
    p.set_defaults(func=cmd_status)

    p = subparsers.add_parser("commit", help="Record changes to the repository")
    p.add_argument("-m", "--message", required=True, help="Commit message")
    p.set_defaults(func=cmd_commit)

    p = subparsers.add_parser("log", help="Display history of a given commit")
    p.add_argument("commit", nargs="?", default="HEAD", help="Commit to start at")
    p.set_defaults(func=cmd_log)

    p = subparsers.add_parser("checkout", help="Checkout a commit inside a directory")
    p.add_argument("commit", help="Commit or tree to checkout")
    p.add_argument("path", help="Empty directory to checkout into")
    p.set_defaults(func=cmd_checkout)

    p = subparsers.add_parser("ls-tree", help="Pretty-print a tree object")
    p.add_argument("-r", "--recursive", action="store_true", help="Recurse into sub-trees")
    p.add_argument("tree", help="A tree-ish object")
    p.set_defaults(func=cmd_ls_tree)

    p = subparsers.add_parser("cat-file", help="Provide content of repository objects")
    p.add_argument("type", choices=["blob", "commit", "tag", "tree"], help="Specify the type")
    p.add_argument("object", help="The object to display")
    p.set_defaults(func=cmd_cat_file)

    p = subparsers.add_parser("hash-object", help="Compute object ID and optionally write object")
    p.add_argument("-t", dest="type", choices=["blob", "commit", "tag", "tree"], default="blob")
    p.add_argument("-w", dest="write", action="store_true", help="Write object to the database")
    p.add_argument("path", help="Read object from file")
    p.set_defaults(func=cmd_hash_object)

    p = subparsers.add_parser("rev-parse", help="Parse revision identifiers")
    p.add_argument("--wyag-type", dest="type", choices=["blob", "commit", "tag", "tree"], default=None)
    p.add_argument("name", help="The name to parse")
    p.set_defaults(func=cmd_rev_parse)

    p = subparsers.add_parser("ls-files", help="List all staged files")
    p.add_argument("--verbose", action="store_true", help="Show complete index details")
    p.set_defaults(func=cmd_ls_files)

    p = subparsers.add_parser("check-ignore", help="Check path(s) against ignore rules")
    p.add_argument("path", nargs="+", help="Paths to check")
    p.set_defaults(func=cmd_check_ignore)

    p = subparsers.add_parser("tag", help="List and create tags")
    p.add_argument("-a", "--annotated", action="store_true", help="Create an annotated tag")
    p.add_argument("-m", "--message", help="Tag message")
    p.add_argument("name", nargs="?", help="Tag name")
    p.add_argument("object", nargs="?", default="HEAD", help="Object to tag")
    p.set_defaults(func=cmd_tag)

    p = subparsers.add_parser("show-ref", help="List references")
    p.set_defaults(func=cmd_show_ref)

    p = subparsers.add_parser("merge", help="Merge another branch or commit")
    p.add_argument("ref", help="Branch, tag, or commit to merge")
    p.add_argument("-m", "--message", help="Merge commit message")
    p.set_defaults(func=cmd_merge)

    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        args.func(args)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
