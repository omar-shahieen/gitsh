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
    
    with open(path,'r') as fp:
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

