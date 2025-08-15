# YADL - Yet Another Deadcode Linter

YADL is a context-free static check tool that tries to look for unused and dead code in your repository, powered by
Python's default ast module.

## Quick Setup

Add this to your `.pre-commit-config.yaml`.

```yaml
-   repo: https://github.com/kmirzavaziri/yadl
    rev: 'v0.6'
    hooks:
    -   id: yadl
        name: Check Deadcode
        files: \.py$
        args: ['.']
```

Optionally create a file called `.yadlignore.py`, and add the following, for ignoring deadcode.

```python
from yadl.datatypes import CodeItem
from yadl.ignore import django
from yadl.ignore import marshmallow
from yadl.ignore import python
from yadl.ignore import testing


def ignore(item: CodeItem) -> bool:
    # You can add any condition you want here
    return any((
        python(item),
        testing(item),
        django(item),
        marshmallow(item),
    ))
```

YADL will look for a function called `ignore(item: CodeItem) -> bool` in a file called `.yadlignore.py` in the current
working directory. If found, it'll pass the CodeItem, and will ignore the lint error if it returns True. This is to
give full control over ignoring based on the AST node to the devs.
