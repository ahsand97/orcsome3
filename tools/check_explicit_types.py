"""Fail when a simple assignment has no explicit annotation (`a = 5` → `a: int = 5`).

Skips Enum members, TypeVar/NewType bindings, unpacking, for/with/except targets,
and names already annotated in the same scope (including function args and `global`/`nonlocal`
names annotated in an outer scope). Python has no place to annotate those other bindings.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path
from typing import Union

from typing_extensions import override

SKIP_ROOT: set[str] = {"venv", ".venv", "build", "dist"}
SKIP_ANY: set[str] = {".git", "__pycache__", "orcsome3-stubs"}
SKIP_FILES: set[str] = {"prueba.py"}
TYPING_CTORS: set[str] = {"TypeVar", "NewType", "ParamSpec", "TypeVarTuple", "Concatenate"}
ENUM_BASES: set[str] = {"Enum", "IntEnum", "Flag", "IntFlag", "StrEnum"}


def _iter_py_files(root: Path) -> list[Path]:
    out: list[Path] = []
    for path in sorted(root.rglob(pattern="*.py")):
        rel: Path = path.relative_to(root)
        if rel.parts[0] in SKIP_ROOT:
            continue
        if any(p in SKIP_ANY for p in rel.parts):
            continue
        if path.name in SKIP_FILES:
            continue
        out.append(path)
    return out


def _base_names(node: ast.expr) -> list[str]:
    if isinstance(node, ast.Name):
        return [node.id]
    if isinstance(node, ast.Attribute):
        return [node.attr]
    return []


def _is_enum_class(node: ast.ClassDef) -> bool:
    return any(name in ENUM_BASES for base in node.bases for name in _base_names(node=base))


def _is_typing_ctor(value: ast.expr) -> bool:
    if not isinstance(value, ast.Call):
        return False
    func: ast.expr = value.func
    if isinstance(func, ast.Name):
        return func.id in TYPING_CTORS
    if isinstance(func, ast.Attribute):
        return func.attr in TYPING_CTORS
    return False


class Visitor(ast.NodeVisitor):
    def __init__(self, path: Path) -> None:
        self.path: Path = path
        self.hits: list[tuple[int, int, str]] = []
        self.stack: list[set[str]] = [set()]
        self.enum_depth: int = 0

    def _declare(self, name: str) -> None:
        self.stack[-1].add(name)

    def _known(self, name: str) -> bool:
        return name in self.stack[-1]

    def _arg_names(self, node: Union[ast.FunctionDef, ast.AsyncFunctionDef]) -> set[str]:
        args: ast.arguments = node.args
        names: set[str] = {a.arg for a in args.posonlyargs + args.args + args.kwonlyargs}
        if args.vararg is not None:
            names.add(args.vararg.arg)
        if args.kwarg is not None:
            names.add(args.kwarg.arg)
        for stmt in node.body:
            if isinstance(stmt, (ast.Global, ast.Nonlocal)):
                for name in stmt.names:
                    if any(name in scope for scope in self.stack):
                        names.add(name)
        return names

    @override
    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self.stack.append(self._arg_names(node=node))
        self.generic_visit(node=node)
        _ = self.stack.pop()

    @override
    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self.stack.append(self._arg_names(node=node))
        self.generic_visit(node=node)
        _ = self.stack.pop()

    @override
    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        is_enum: bool = _is_enum_class(node=node)
        if is_enum:
            self.enum_depth += 1
        self.stack.append(set())
        self.generic_visit(node=node)
        _ = self.stack.pop()
        if is_enum:
            self.enum_depth -= 1

    @override
    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        if isinstance(node.target, ast.Name):
            self._declare(name=node.target.id)
        self.generic_visit(node=node)

    @override
    def visit_Assign(self, node: ast.Assign) -> None:
        if self.enum_depth == 0 and not _is_typing_ctor(value=node.value):
            if len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
                name: str = node.targets[0].id
                if name != "_" and not self._known(name=name):
                    self.hits.append((node.lineno, node.col_offset, name))
                    self._declare(name=name)
        self.generic_visit(node=node)


def check_tree(path: Path, tree: ast.AST) -> list[tuple[int, int, str]]:
    visitor: Visitor = Visitor(path=path)
    visitor.visit(node=tree)
    return visitor.hits


def _self_check() -> None:
    def hits(src: str) -> list[str]:
        return [name for _ln, _col, name in check_tree(path=Path("mod.py"), tree=ast.parse(source=src))]

    assert hits(src="a = 5\n") == ["a"]
    assert hits(src="a: int = 5\n") == []
    assert hits(src="def f(a: int) -> None:\n    a = 2\n") == []
    assert hits(src="def f() -> None:\n    x = 1\n") == ["x"]
    assert hits(src="from enum import Enum\nclass E(Enum):\n    A = 1\n") == []
    assert hits(src="from typing import TypeVar\n_T = TypeVar('_T')\n") == []
    assert hits(src="__all__ = ['x']\n") == ["__all__"]
    print("check_explicit_types self-check ok")


def main(argv: list[str]) -> int:
    _self_check()
    root: Path = Path(argv[1] if len(argv) > 1 else Path(__file__).resolve().parents[1])
    n: int = 0
    for path in _iter_py_files(root=root):
        tree: ast.AST = ast.parse(source=path.read_text(), filename=str(path))
        for lineno, col, name in check_tree(path=path, tree=tree):
            try:
                rel: Path = path.relative_to(root)
            except ValueError:
                rel = path
            print(f"{rel}:{lineno}:{col + 1}: unannotated assignment: {name}: <type> = ...")
            n += 1
    if n:
        print(f"{n} explicit-type violation(s)", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(argv=sys.argv))
