import ast
import os
import re
from abc import ABC, abstractmethod
import string
from pathlib import Path
from typing import List

from yadl.datatypes import VisitPayload, Memory, Code


class BaseVisitor(ABC):
    @classmethod
    @abstractmethod
    def visit(cls, payload: VisitPayload) -> None:
        pass


class AttributeVisitor(BaseVisitor):
    @classmethod
    def visit(cls, payload: VisitPayload) -> None:
        if isinstance(payload.node.ctx, ast.Store):
            payload.memory.add_definition(payload=payload, name=payload.node.attr, code=Code.UNUSED_ATTRIBUTE)
        elif isinstance(payload.node.ctx, ast.Load):
            payload.memory.add_usage(payload.node.attr)


class BinOpVisitor(BaseVisitor):
    @classmethod
    def visit(cls, payload: VisitPayload) -> None:
        if (
            isinstance(payload.node.left, ast.Str)
            and isinstance(payload.node.op, ast.Mod)
            and _is_locals_call(payload.node.right)
        ):
            for item in set(re.findall(r"%\((\w+)\)", payload.node.left.s)):
                payload.memory.add_usage(item)


class CallVisitor(BaseVisitor):
    @classmethod
    def visit(cls, payload: VisitPayload) -> None:
        # Count getattr/hasattr(x, "some_attr", ...) as usage of some_attr.
        if isinstance(payload.node.func, ast.Name) and (
            (payload.node.func.id == "getattr" and 2 <= len(payload.node.args) <= 3)
            or (payload.node.func.id == "hasattr" and len(payload.node.args) == 2)
        ):
            attr_name_arg = payload.node.args[1]
            if isinstance(attr_name_arg, ast.Str):
                payload.memory.add_usage(attr_name_arg.s)

        if (
            isinstance(payload.node.func, ast.Attribute)
            and isinstance(payload.node.func.value, ast.Str)
            and payload.node.func.attr == "format"
            and any(kw.arg is None and _is_locals_call(kw.value) for kw in payload.node.keywords)
        ):

            def is_identifier(name: str) -> bool:
                return bool(re.match(r"[a-zA-Z_][a-zA-Z0-9_]*", name))

            parser = string.Formatter()
            try:
                names = [name for _, name, _, _ in parser.parse(payload.node.func.value.s) if name]
            except ValueError:
                names = []

            for field_name in names:
                for var in re.sub(r"\[\w*]", "", field_name).split("."):
                    if is_identifier(var):
                        payload.memory.add_usage(var)


class ClassDefVisitor(BaseVisitor):
    @classmethod
    def visit(cls, payload: VisitPayload) -> None:
        for _ in payload.node.decorator_list:
            payload.memory.add_definition(payload=payload, name=payload.node.name, code=Code.UNUSED_CLASS)


class FunctionDefVisitor(BaseVisitor):
    @classmethod
    def visit(cls, payload: VisitPayload) -> None:
        payload.memory.add_definition(payload=payload, name=payload.node.name, code=Code.UNUSED_FUNCTION)


class ImportVisitor(BaseVisitor):
    @classmethod
    def visit(cls, payload: VisitPayload) -> None:
        _add_aliases(payload)


class ImportFromVisitor(BaseVisitor):
    @classmethod
    def visit(cls, payload: VisitPayload) -> None:
        if payload.node.module != "__future__":
            _add_aliases(payload)


class NameVisitor(BaseVisitor):
    @classmethod
    def visit(cls, payload: VisitPayload) -> None:
        if isinstance(payload.node.ctx, (ast.Load, ast.Del)) and payload.node.id not in {"object", "self"}:
            payload.memory.add_usage(payload.node.id)
        elif isinstance(payload.node.ctx, (ast.Param, ast.Store)):
            payload.memory.add_definition(payload=payload, name=payload.node.id, code=Code.UNUSED_VARIABLE)


class AssignVisitor(BaseVisitor):
    @classmethod
    def visit(cls, payload: VisitPayload) -> None:
        if not (
            isinstance(payload.node.value, (ast.List, ast.Tuple))
            and any(target.id == "__all__" for target in payload.node.targets if isinstance(target, ast.Name))
        ) or not isinstance(payload.node.value, (ast.List, ast.Tuple)):
            return

        for elt in payload.node.value.elts:
            if isinstance(elt, ast.Str):
                payload.memory.add_usage(elt.s)


class MatchClassVisitor(BaseVisitor):
    @classmethod
    def visit(cls, payload: VisitPayload) -> None:
        for kwd_attr in payload.node.kwd_attrs:
            payload.memory.add_usage(kwd_attr)


def _is_locals_call(node: ast.AST) -> bool:
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "locals"
        and not node.args
        and not node.keywords
    )


def _add_aliases(payload: VisitPayload) -> None:
    if not isinstance(payload.node, (ast.Import, ast.ImportFrom)):
        return
    for name_and_alias in payload.node.names:
        name = name_and_alias.name.partition(".")[0]
        alias = name_and_alias.asname
        payload.memory.add_definition(payload=payload, name=alias or name, code=Code.UNUSED_IMPORT)
        if alias is not None:
            payload.memory.add_usage(name_and_alias.name)


class NodeVisitor(BaseVisitor):
    _visitors = {
        "AsyncFunctionDef": FunctionDefVisitor,
        "Attribute": AttributeVisitor,
        "BinOp": BinOpVisitor,
        "Call": CallVisitor,
        "ClassDef": ClassDefVisitor,
        "FunctionDef": FunctionDefVisitor,
        "Import": ImportVisitor,
        "ImportFrom": ImportFromVisitor,
        "Name": NameVisitor,
        "Assign": AssignVisitor,
        "MatchClass": MatchClassVisitor,
    }

    @classmethod
    def visit(cls, payload: VisitPayload) -> None:
        node_type = payload.node.__class__.__name__
        if node_type in cls._visitors:
            return cls._visitors[node_type].visit(payload)


class FileVisitor(BaseVisitor):
    @classmethod
    def visit(cls, payload: VisitPayload) -> None:
        NodeVisitor.visit(payload)

        type_comment = getattr(payload.node, "type_comment", None)
        if type_comment is not None:
            mode = "func_type" if isinstance(payload.node, (ast.FunctionDef, ast.AsyncFunctionDef)) else "eval"
            cls.visit(payload.with_next(ast.parse(type_comment, filename="<type_comment>", mode=mode)))

        if payload.node:
            for _, value in ast.iter_fields(payload.node):
                if isinstance(value, list):
                    [cls.visit(payload.with_next(item)) for item in value if isinstance(item, ast.AST)]
                elif isinstance(value, ast.AST):
                    cls.visit(payload.with_next(value))


class FilesVisitor:
    @classmethod
    def visit(cls, filenames: List[str], memory: Memory) -> None:
        for filename in filenames:
            with open(filename, "rb") as f:
                basename = os.path.basename(filename)

                file_content = f.read()
                payload = VisitPayload(
                    filename=Path(filename),
                    path=(ast.parse(file_content, filename=filename, type_comments=True),),
                    memory=memory,
                )

                if file_content.strip():
                    FileVisitor.visit(payload)
                else:
                    memory.add_definition(payload=payload, name=basename, code=Code.EMPTY_FILE)
