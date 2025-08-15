# YADL - Yet Another Deadcode Linter

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
