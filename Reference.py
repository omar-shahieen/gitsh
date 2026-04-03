from  Repository import GitRepository,repo_file,repo_dir
import os
from typing import  Optional
def ref_resolve(repo: GitRepository, ref: str) -> Optional[str]:
    path = repo_file(repo, ref)
    
    if not os.path.isfile(path):
        return None
    
    with open(path,'r') as fp:
        data = fp.read()[:-1] # drop \n
        
    if data.startswith("ref: "):
        return ref_resolve(repo , data[5:])
    else:
        return data
    
        
def ref_list(repo,current_path=None):
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


def show_ref(repo , refs , include_hash = True , current_prefix=""):
    # add "/" if we are not at the rool level
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
            
