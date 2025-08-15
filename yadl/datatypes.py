import ast
import os
from dataclasses import dataclass, field
from enum import Enum
from importlib.util import spec_from_file_location, module_from_spec
from pathlib import Path
from typing import List, Set, Tuple


class Code(Enum):
    UNUSED_ATTRIBUTE = "UNUSED_ATTRIBUTE"
    UNUSED_CLASS = "UNUSED_CLASS"
    UNUSED_FUNCTION = "UNUSED_FUNCTION"
    UNUSED_VARIABLE = "UNUSED_VARIABLE"
    UNUSED_IMPORT = "UNUSED_IMPORT"
    EMPTY_FILE = "EMPTY_FILE"


@dataclass
class Args:
    project_dir: str


@dataclass
class CodeItem:
    filename: Path
    name: str
    path: Tuple[ast.AST, ...]
    code: Code

    @property
    def filename_with_position(self) -> str:
        return (
            str(self.filename)
            + ":"
            + str(self.path[-1].lineno if hasattr(self.path[-1], "lineno") else 1)
            + ":"
            + str(self.path[-1].col_offset if hasattr(self.path[-1], "col_offset") else 1)
            + ":"
        )

    def __repr__(self) -> str:
        return repr(self.name)

    def __eq__(self, other: object) -> bool:
        if isinstance(other, str):
            return self.name == other

        if isinstance(other, CodeItem):
            return self.name == other.name
        return False

    def __hash__(self) -> int:
        return hash(self.name)

    @property
    def node(self):
        return self.path[-1]

    def should_ignore(self) -> bool:
        if os.path.isfile(".yadlignore.py"):
            spec = spec_from_file_location("yadlignore", ".yadlignore.py")
            module = module_from_spec(spec)  # type: ignore[arg-type]
            spec.loader.exec_module(module)  # type: ignore[union-attr]
            return module.ignore(self)

        return False

    @staticmethod
    def remove_ignored(items: List["CodeItem"]) -> List["CodeItem"]:
        return [item for item in items if not item.should_ignore()]

    @staticmethod
    def render(items: List["CodeItem"]) -> str:
        return "\n".join(f"{item.filename_with_position} {item.code.name} unused {item.name}" for item in items)


@dataclass
class Memory:
    _definitions: List[CodeItem] = field(default_factory=list)
    _usages: Set[str] = field(default_factory=set)

    def add_definition(self, payload: "VisitPayload", name: str, code: Code) -> None:
        self._definitions.append(CodeItem(filename=payload.filename, name=name, path=payload.path, code=code))

    def add_usage(self, name: str) -> None:
        self._usages.add(name)

    def get_unused_items(self) -> List[CodeItem]:
        return sorted(
            sorted(
                [item for item in self._definitions if item.name not in self._usages],
                key=lambda item: item.name.lower(),
            ),
            key=lambda item: (
                item.filename,
                item.node.lineno if hasattr(item.node, "lineno") else 1,
            ),
        )


@dataclass
class VisitPayload:
    filename: Path
    path: Tuple[ast.AST, ...]
    memory: Memory = field(default_factory=Memory)

    @property
    def node(self):
        return self.path[-1]

    def with_next(self, item: ast.AST) -> "VisitPayload":
        return VisitPayload(filename=self.filename, path=self.path + (item,), memory=self.memory)
