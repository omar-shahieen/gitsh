
from repository import  repo_find,repo_dir



from commands import ls_tree





if __name__ == "__main__":
    repo = repo_find(".", required=True)
    ls_tree(repo,"HEAD")
    print(repo_dir(repo, "refs"))

    if repo is None:
        raise SystemExit("No repository found")

    # ls_tree(repo,object_find(repo, "HEAD"),True)
    # log_graphviz(repo, object_find(repo, "HEAD"), set())

