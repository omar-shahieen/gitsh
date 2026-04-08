#!/usr/bin/env python3
"""
Complete Git-like CLI interface for gitsh
"""

import argparse
import sys
import os
from datetime import datetime

from storage import repo_find, repo_create, repo_file, object_write, object_find, object_read, compute_file_hash
from objects import GitBlob, GitCommit, GitTree
from objects import GitTreeLeaf
from Index import index_load, index_save
from Reference import ref_resolve, ref_list, ref_create, branch_get_active, branch_create
from commands import (
    cat_file, tree_checkout, log_graphviz, ls_tree, tag_create, show_ref
)
from merge import cmd_merge


def cmd_init(args):
    """Initialize a new repository."""
    path = args.path if args.path else "."
    try:
        repo = repo_create(path)
        print(f"✓ Initialized empty Git repository in {os.path.abspath(path)}/.gitsh")
    except Exception as e:
        print(f"✗ Error: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_add(args):
    """Add files to the staging area."""
    try:
        repo = repo_find()
        index = index_load(repo)
        
        for path in args.path:
            index.add(path)
            rel_path = os.path.relpath(os.path.abspath(path), repo.worktree)
            print(f"✓ Added {rel_path}")
        
        index.save()
    except Exception as e:
        print(f"✗ Error: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_rm(args):
    """Remove files from the staging area."""
    try:
        repo = repo_find()
        index = index_load(repo)
        
        for path in args.path:
            index.rm(path)
            print(f"✓ Removed {path}")
        
        index.save()
    except Exception as e:
        print(f"✗ Error: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_status(args):
    """Show the working tree status."""
    try:
        repo = repo_find()
        index = index_load(repo)
        status = index.status()
        
        # Show branch
        branch = branch_get_active(repo)
        if branch:
            print(f"On branch {branch}")
        else:
            head_sha = ref_resolve(repo, "HEAD")
            if head_sha:
                print(f"HEAD detached at {head_sha[:7]}")
        
        print()
        
        # Changes staged
        if status['staged']:
            print("Changes to be committed:")
            for f in status['staged']:
                print(f"  ✓ {f}")
        
        print()
        
        # Changes not staged
        if status['modified']:
            print("Changes not staged for commit:")
            for f in status['modified']:
                print(f"  ✗ {f}")
        
        # Deleted files
        if status['deleted']:
            print("Deleted files:")
            for f in status['deleted']:
                print(f"  ✗ {f}")
        
    except Exception as e:
        print(f"✗ Error: {e}", file=sys.stderr)
        sys.exit(1)


def tree_from_index(repo, index):
    """Convert index entries to a tree structure."""
    if not index.entries:
        # Create empty tree
        tree = GitTree()
        return object_write(tree, repo)
    
    # Group entries by directory
    contents = {}
    contents[""] = []
    
    for entry in index.entries.values():
        dirname = os.path.dirname(entry.path)
        
        # Create all parent directories
        key = dirname
        while key != "":
            if key not in contents:
                contents[key] = []
            key = os.path.dirname(key)
        
        # Add entry to its directory
        contents[dirname].append(entry)
    
    # Process directories bottom-up (longest paths first)
    sorted_paths = sorted(contents.keys(), key=len, reverse=True)
    sha = None
    
    for path in sorted_paths:
        tree = GitTree()
        
        for entry in contents[path]:
            # Convert mode to octal format for tree
            mode = f"{entry.mode}".encode('ascii')
            basename = os.path.basename(entry.path)
            leaf = GitTreeLeaf(mode=mode, path=basename, sha=entry.sha)
            tree.items.append(leaf)
        
        # Write tree to object store
        sha = object_write(tree, repo)
        
        # Add tree to parent directory
        parent = os.path.dirname(path)
        if parent and parent != path:
            basename = os.path.basename(path) if path else ""
            if basename:
                contents[parent].append((basename, sha))
    
    return sha


def cmd_commit(args):
    """Create a commit from staged changes."""
    try:
        repo = repo_find()
        message = args.message
        
        if not message:
            print("✗ No commit message provided", file=sys.stderr)
            sys.exit(1)
        
        # Load index
        index = index_load(repo)
        
        if not index.entries:
            print("✗ Nothing staged for commit", file=sys.stderr)
            sys.exit(1)
        
        # Create tree from index
        tree_sha = tree_from_index(repo, index)
        
        # Get parent commit
        head_sha = ref_resolve(repo, "HEAD")
        
        # Create commit
        commit = GitCommit()
        commit.kvlm = {}
        commit.kvlm[b'tree'] = tree_sha.encode('ascii')
        
        if head_sha:
            commit.kvlm[b'parent'] = head_sha.encode('ascii')
        
        # Add author/committer info
        author = "gitsh <gitsh@example.com>"
        timestamp = datetime.now()
        timestamp_str = str(int(timestamp.timestamp()))
        tz_offset = "+0000"  # Simplified, no timezone handling
        
        author_str = f"{author} {timestamp_str} {tz_offset}"
        commit.kvlm[b'author'] = author_str.encode('utf-8')
        commit.kvlm[b'committer'] = author_str.encode('utf-8')
        commit.kvlm[None] = message.encode('utf-8')
        
        # Write commit
        commit_sha = object_write(commit, repo)
        
        # Update HEAD/branch
        branch = branch_get_active(repo)
        if branch:
            ref_create(repo, f"refs/heads/{branch}", commit_sha)
        else:
            # Detached HEAD
            ref_create(repo, "HEAD", commit_sha)
        
        index.clear()
        index_save(index)
        
        print(f"✓ [{'main' if not branch else branch} {commit_sha[:7]}] {message}")
        
    except Exception as e:
        print(f"✗ Error: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_log(args):
    """Show commit history in GraphViz format."""
    try:
        repo = repo_find()
        commit_sha = args.commit if args.commit else "HEAD"
        
        print("digraph gitshlog {")
        print("  node[shape=rect]")
        log_graphviz(repo, object_find(repo, commit_sha), set())
        print("}")
        
    except Exception as e:
        print(f"✗ Error: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_checkout(args):
    """Checkout a commit into a directory."""
    try:
        repo = repo_find()
        target_path = args.path
        commit_ref = args.commit
        
        # Find the object
        obj = object_read(repo, object_find(repo, commit_ref))
        
        # If it's a commit, get its tree
        if obj.fmt == b'commit':
            tree_sha = obj.kvlm[b'tree'].decode('ascii')
            obj = object_read(repo, tree_sha)
        
        # Verify path is empty
        if os.path.exists(target_path):
            if not os.path.isdir(target_path):
                print(f"✗ {target_path} is not a directory", file=sys.stderr)
                sys.exit(1)
            if os.listdir(target_path):
                print(f"✗ {target_path} is not empty", file=sys.stderr)
                sys.exit(1)
        else:
            os.makedirs(target_path)
        
        # Checkout tree
        tree_checkout(repo, obj, os.path.realpath(target_path))
        print(f"✓ Checked out {commit_ref} to {target_path}")
        
    except Exception as e:
        print(f"✗ Error: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_ls_tree(args):
    """List tree contents."""
    try:
        repo = repo_find()
        ls_tree(repo, args.tree, args.recursive)
    except Exception as e:
        print(f"✗ Error: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_cat_file(args):
    """Output object contents."""
    try:
        repo = repo_find()
        cat_file(repo, args.object, fmt=args.type.encode() if args.type else None)
    except Exception as e:
        print(f"✗ Error: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_tag(args):
    """Create or list tags."""
    try:
        repo = repo_find()
        
        if args.name:
            # Create tag
            target = args.target if args.target else "HEAD"
            target_sha = object_find(repo, target)
            tag_create(repo, args.name, target_sha, 
                      create_annotated_tag=args.annotated,
                      message=args.message.encode() if args.message else b"")
            print(f"✓ Created tag {args.name}")
        else:
            # List tags
            refs = ref_list(repo)
            if 'tags' in refs:
                show_ref(repo, refs['tags'], include_hash=False)
            
    except Exception as e:
        print(f"✗ Error: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_show_ref(args):
    """List all references."""
    try:
        repo = repo_find()
        refs = ref_list(repo)
        show_ref(repo, refs)
    except Exception as e:
        print(f"✗ Error: {e}", file=sys.stderr)
        sys.exit(1)


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="gitsh - A simplified Git implementation",
        prog="gitsh"
    )
    
    subparsers = parser.add_subparsers(title="Commands", dest="command", required=True)
    
    # init
    init_parser = subparsers.add_parser("init", help="Initialize a new repository")
    init_parser.add_argument("path", nargs="?", help="Directory to initialize")
    init_parser.set_defaults(func=cmd_init)
    
    # add
    add_parser = subparsers.add_parser("add", help="Add files to staging area")
    add_parser.add_argument("path", nargs="+", help="Files to add")
    add_parser.set_defaults(func=cmd_add)
    
    # rm
    rm_parser = subparsers.add_parser("rm", help="Remove files from staging area")
    rm_parser.add_argument("path", nargs="+", help="Files to remove")
    rm_parser.set_defaults(func=cmd_rm)
    
    # status
    status_parser = subparsers.add_parser("status", help="Show working tree status")
    status_parser.set_defaults(func=cmd_status)
    
    # commit
    commit_parser = subparsers.add_parser("commit", help="Create a commit")
    commit_parser.add_argument("-m", "--message", required=True, help="Commit message")
    commit_parser.set_defaults(func=cmd_commit)

    # merge
    merge_parser = subparsers.add_parser("merge", help="Merge another branch or commit")
    merge_parser.add_argument("ref", help="Branch, tag, or commit to merge")
    merge_parser.add_argument("-m", "--message", help="Merge commit message")
    merge_parser.set_defaults(func=cmd_merge)
    
    # log
    log_parser = subparsers.add_parser("log", help="Show commit history")
    log_parser.add_argument("commit", nargs="?", help="Starting commit (default: HEAD)")
    log_parser.set_defaults(func=cmd_log)
    
    # checkout
    checkout_parser = subparsers.add_parser("checkout", help="Checkout a commit")
    checkout_parser.add_argument("commit", help="Commit to checkout")
    checkout_parser.add_argument("path", help="Target directory")
    checkout_parser.set_defaults(func=cmd_checkout)
    
    # ls-tree
    ls_tree_parser = subparsers.add_parser("ls-tree", help="List tree contents")
    ls_tree_parser.add_argument("-r", "--recursive", action="store_true", help="Recursive listing")
    ls_tree_parser.add_argument("tree", help="Tree reference")
    ls_tree_parser.set_defaults(func=cmd_ls_tree)
    
    # cat-file
    cat_file_parser = subparsers.add_parser("cat-file", help="Output object contents")
    cat_file_parser.add_argument("type", choices=["blob", "tree", "commit", "tag"],
                                help="Object type")
    cat_file_parser.add_argument("object", help="Object reference")
    cat_file_parser.set_defaults(func=cmd_cat_file)
    
    # tag
    tag_parser = subparsers.add_parser("tag", help="Create or list tags")
    tag_parser.add_argument("name", nargs="?", help="Tag name")
    tag_parser.add_argument("-a", "--annotated", action="store_true", help="Create annotated tag")
    tag_parser.add_argument("-m", "--message", help="Tag message")
    tag_parser.add_argument("--target", help="Target reference")
    tag_parser.set_defaults(func=cmd_tag)
    
    # show-ref
    show_ref_parser = subparsers.add_parser("show-ref", help="List references")
    show_ref_parser.set_defaults(func=cmd_show_ref)
    
    args = parser.parse_args()
    
    try:
        args.func(args)
    except Exception as e:
        print(f"✗ Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
