from storage import GitRepository , repo_file ,repo_dir
import os
from typing import Optional, Dict, Any

def ref_resolve(repo: GitRepository, ref: str) -> Optional[str]:
    """Resolve a reference to its SHA hash.

    Args:
        repo: The Git repository instance.
        ref: The reference name (e.g., 'HEAD', 'refs/heads/master').

    Returns:
        The SHA hash string if the reference is found, None otherwise.
    """
    path = repo_file(repo, ref)
    
    if not os.path.isfile(path):
        return None
    
    with open(path,'r',encoding='utf-8',errors="ignore") as fp:
        data = fp.read()[:-1] # drop \n
        
    if data.startswith("ref: "):
        return ref_resolve(repo , data[5:])
    else:
        return data
    
        
def ref_list(repo: GitRepository, current_path: Optional[str] = None) -> Dict[str, Any]:
    """List all references in the repository.

    Args:
        repo: The Git repository instance.
        current_path: The path to start listing from (defaults to 'refs').

    Returns:
        A nested dictionary of references.
    """
    if not current_path :
        current_path = repo_dir(repo, "refs")
        
    references  = dict()
    
    for entry_name  in sorted(os.listdir(current_path)):
        
        entry_path = os.path.join(current_path , entry_name )
        
        if os.path.isdir(entry_path):
            references [entry_name] = ref_list(repo,entry_path)
        else :
            references [entry_name] = ref_resolve(repo,entry_path)
            
    return references


def ref_create(repo: GitRepository, ref_name: str, sha: str) -> None:
    """Create or update a reference.

    Args:
        repo: The Git repository instance.
        ref_name: Name of the reference (e.g., 'refs/heads/main').
        sha: The SHA hash to point to.
    """
    ref_path = repo_file(repo, ref_name, mkdir=True)
    with open(ref_path, 'w',encoding='utf-8',errors="ignore") as f:
        f.write(sha + '\n')


def branch_get_active(repo: GitRepository) -> Optional[str]:
    """Get the name of the active branch.

    Args:
        repo: The Git repository instance.

    Returns:
        The branch name or None if in detached HEAD state.
    """
    head_path = repo_file(repo, "HEAD")
    
    if not os.path.isfile(head_path):
        return None
    
    with open(head_path, 'r',encoding='utf-8',errors="ignore") as f:
        data = f.read().strip()
    
    if data.startswith("ref: refs/heads/"):
        return data[16:]  # Extract branch name
    
    return None


def branch_create(repo: GitRepository, branch_name: str, target_sha: str) -> None:
    """Create a new branch.

    Args:
        repo: The Git repository instance.
        branch_name: Name of the new branch.
        target_sha: SHA to point the branch to (usually HEAD).
    """
    ref_create(repo, f"refs/heads/{branch_name}", target_sha)


def show_ref(repo: GitRepository, refs: Dict[str, Any], include_hash: bool = True, current_prefix: str = "") -> None:
    """Display references in a formatted way.

    Args:
        repo: The Git repository instance.
        refs: The dictionary of references.
        include_hash: Whether to include SHA hashes in output.
        current_prefix: The current prefix for nested references.
    """
    # add "/" if we are not at the root level
    if current_prefix : 
        current_prefix = current_prefix + "/"
        
    for ref_name, ref_value in refs.items():
        # this is a file (final ref -> sha string)
        if isinstance(ref_value , str) :
            if include_hash:
                print(f"{ref_value} {current_prefix}{ref_name}")
            else :
                print(f"{current_prefix}{ref_name}")
                
        else :  # this is directory (nested ref)
            show_ref(
                repo,
                ref_value,
                include_hash=include_hash,
                current_prefix=f"{current_prefix}{ref_name}"
            ) 

