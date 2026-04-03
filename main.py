
from Tree import ls_tree
from Repository import object_find, repo_find,repo_file,ref_resolve,repo_dir,ref_list

if __name__ == "__main__":
    repo = repo_find(".", required=True)
    print(repo_dir(repo, "refs"))

    if repo is None:
        raise SystemExit("No repository found")

    # ls_tree(repo,object_find(repo, "HEAD"),True)
    # log_graphviz(repo, object_find(repo, "HEAD"), set())

