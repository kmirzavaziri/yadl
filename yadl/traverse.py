import ast
from typing import Optional, List, Iterable


def get_container(path: Iterable[ast.AST]) -> Optional[ast.AST]:
    if len(path) < 2:
        return None

    return path[-2]


def get_attr_chain_root(node: Optional[ast.AST]) -> Optional[ast.expr]:
    if not isinstance(node, ast.Attribute):
        return None

    root = node
    while isinstance(root, ast.Attribute):
        root = root.value

    return root


def get_parent_classes(node: Optional[ast.AST]) -> List[ast.expr]:
    if not isinstance(node, ast.ClassDef):
        return []

    return node.bases


def get_decorators(node: Optional[ast.AST]) -> List[ast.expr]:
    if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return []

    return node.decorator_list


def get_name(node: Optional[ast.AST]) -> str:
    if not isinstance(node, ast.Name):
        return ""

    return node.id
