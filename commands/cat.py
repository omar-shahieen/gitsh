
from repository import GitRepository
from storage import object_find, object_read
from typing import Optional
import sys


def cat_file(repo: GitRepository, obj: str, fmt: Optional[bytes] = None) -> None:
    """Output the contents of a Git object.

    Args:
        repo: The repository.
        obj: The object name.
        fmt: Expected format (optional).
    """
    obj = object_read(repo, object_find(repo, obj, fmt=fmt))
    sys.stdout.buffer.write(obj.serialize())
