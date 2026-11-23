"""Critical-path matching for changed file paths."""

import fnmatch


def matches_critical_path(changed_paths: list[str], globs: list[str]) -> bool:
    if not globs or not changed_paths:
        return False
    for path in changed_paths:
        for pattern in globs:
            if fnmatch.fnmatch(path, pattern):
                return True
    return False
