import sys , os
from storage import object_read,object_find,GitRepository,repo_file,object_write
from objects import GitTag, GitTree, GitTreeLeaf, GitCommit
from typing import Optional,Dict,Any
from Reference import ref_create, show_ref, ref_list


def cat_file(repo: GitRepository, obj: str, fmt: Optional[bytes] = None) -> None:
    """Output the contents of a Git object.

    Args:
        repo: The repository.
        obj: The object name.
        fmt: Expected format (optional).
    """
    obj_sha = object_find(repo, obj, fmt=fmt)
    obj = object_read(repo, obj_sha)
    sys.stdout.buffer.write(obj.serialize())


def tree_checkout(repo: "GitRepository", tree: "GitTree", path: str) -> None:
    """Checkout a tree to a directory path.

    Args:
        repo: The repository.
        tree: The GitTree object.
        path: The destination path.
    """
    if not hasattr(tree, 'items') or not tree.items:
        return
    
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
    raw_message = commit.kvlm[None].decode("utf8").strip() if None in commit.kvlm else "(no message)"
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
        
        mode = item.mode.decode('ascii') if isinstance(item.mode, bytes) else item.mode
        mode = mode.rjust(6, '0')  # pad with leading zeros
        type_code = mode[0:2]

        match type_code:
            case "04":
                type_str = "tree"
            case "10":
                type_str = "blob"
            case "12":
                type_str = "blob"
            case "16":
                type_str = "commit"
            case _:
                raise Exception(f"Weird tree leaf mode {mode}")

        if not (recursive and type_str == "tree"):
            print(
                f"{mode} {type_str} {item.sha}\t{os.path.join(prefix, item.path)}"
            )
        else:
            ls_tree(repo, item.sha, recursive, os.path.join(prefix, item.path))


def tag_create(repo: GitRepository, tag_name: str, target_sha: str, 
               create_annotated_tag: bool = False, message: bytes = b"") -> None:
    """Create a new tag in the repository.

    Args:
        repo: The Git repository instance.
        tag_name: The name of the tag.
        target_sha: The SHA to tag.
        create_annotated_tag: Whether to create an annotated tag.
        message: The tag message for annotated tags.
    """
    if create_annotated_tag: 
        # Create annotated tag
        tag = GitTag()
        tag.kvlm = {}
        tag.kvlm[b"object"] = target_sha.encode('ascii')
        tag.kvlm[b"type"] = b'commit'
        tag.kvlm[b"tag"] = tag_name.encode('utf-8')
        
        # Add tagger details 
        try:
            name = repo.config.get("user", "name") if repo.config else "gitsh"
            email = repo.config.get("user", "email") if repo.config else "gitsh@example.com"
        except:
            name = "gitsh"
            email = "gitsh@example.com"
        
        tagger = f"{name} <{email}>"
        tag.kvlm[b'tagger'] = tagger.encode('utf-8')
        
        # Add message
        tag.kvlm[None] = message if message else b"Tagged with gitsh\n"
        
        # Write the tag object
        tag_sha = object_write(tag, repo)
        
        # Create reference pointing to the tag object
        ref_create(repo, f"refs/tags/{tag_name}", tag_sha)
        
    else: 
        # Lightweight tag - just a reference
        ref_create(repo, f"refs/tags/{tag_name}", target_sha)




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
                
                



