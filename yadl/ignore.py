import ast
from fnmatch import fnmatch

from yadl.datatypes import CodeItem, Code
from yadl.traverse import get_parent_classes, get_container, get_attr_chain_root, get_name, get_decorators


def testing(item: CodeItem) -> bool:
    return (
        item.name.startswith("test_")
        and any(ast.unparse(base).strip() == "TestCase" for base in get_parent_classes(get_container(item.path)))
    ) or (
        item.name in {"side_effect"} and (root := get_attr_chain_root(item.node)) and get_name(root).startswith("mock_")
    )


def python(item: CodeItem) -> bool:
    return pattern_matches(item.filename.as_posix(), ["*/__init__.py"]) or (
        item.code == Code.UNUSED_FUNCTION and pattern_matches(item.name, ["__*__"])
    )


def django(item: CodeItem) -> bool:
    return pattern_matches(item.filename.as_posix(), ["*/migrations/*"]) or (
        item.code == Code.UNUSED_FUNCTION
        and any(
            isinstance(decorator, ast.Call) and get_name(decorator.func) == "receiver"
            for decorator in get_decorators(item.node)
        )
    )


def marshmallow(item: CodeItem) -> bool:
    return (
        item.code == Code.UNUSED_FUNCTION
        and item.name.startswith("get_")
        and any(ast.unparse(base).strip() == "Schema" for base in get_parent_classes(get_container(item.path)))
    )


def pattern_matches(path: str, patterns: list[str]) -> bool:
    return any(fnmatch(path, pattern) for pattern in patterns)
