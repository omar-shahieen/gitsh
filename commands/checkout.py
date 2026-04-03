import os
from ..storage import object_read
from ..repository import GitRepository 
from ..objects import GitTree

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