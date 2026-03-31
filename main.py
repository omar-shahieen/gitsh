
from Commit import log_graphviz
from Repository import object_find, repo_find


if __name__ == "__main__":
    repo = repo_find(".", required=True)
    if repo is None:
        raise SystemExit("No repository found")

    log_graphviz(repo, object_find(repo, "HEAD"), set())

