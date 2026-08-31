"""Fail when a call passes positional args that the callee accepts as keywords.

Skip positional-only params, *args, unknown callees, signatures we cannot resolve,
and Mapping key args (`get`/`pop`/…) that inspect reports as keywords but stubs mark `/`.
"""

from __future__ import annotations

import ast
import builtins
import importlib
import inspect
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Iterator, NamedTuple, Optional, Union

POSONLY: Any = inspect.Parameter.POSITIONAL_ONLY
PORK: Any = inspect.Parameter.POSITIONAL_OR_KEYWORD
VARPOS: Any = inspect.Parameter.VAR_POSITIONAL

SKIP_ROOT: set[str] = {"venv", ".venv", "build", "dist"}
SKIP_ANY: set[str] = {".git", "__pycache__", "orcsome3-stubs"}
SKIP_FILES: set[str] = {"prueba.py"}
# inspect often reports Mapping.get/pop key as PORK; typeshed/mypy treat it as positional-only.
_MAPPING_KEY_METHODS: frozenset[str] = frozenset(
    {"get", "pop", "setdefault", "__getitem__", "__setitem__", "__delitem__"}
)


class Sig(NamedTuple):
    params: tuple[tuple[str, Any], ...]


class Hit(NamedTuple):
    path: Path
    lineno: int
    col: int
    param: str


def _kind_params(args: ast.arguments, *, drop_self: bool) -> tuple[tuple[str, Any], ...]:
    params: list[tuple[str, Any]] = []
    for a in args.posonlyargs:
        params.append((a.arg, POSONLY))
    for a in args.args:
        params.append((a.arg, PORK))
    if args.vararg is not None:
        params.append((args.vararg.arg, VARPOS))
    if drop_self and params and params[0][0] in {"self", "cls"}:
        params = params[1:]
    return tuple(params)


def _is_staticmethod(node: Union[ast.FunctionDef, ast.AsyncFunctionDef]) -> bool:
    return any(isinstance(d, ast.Name) and d.id == "staticmethod" for d in node.decorator_list)


def _sig_from_inspect(obj: Any, *, drop_self: bool) -> Optional[Sig]:
    try:
        signature: inspect.Signature = inspect.signature(obj=obj)
    except (TypeError, ValueError):
        return None
    params: list[tuple[str, Any]] = []
    for p in signature.parameters.values():
        if p.kind in (POSONLY, PORK, VARPOS):
            params.append((p.name, p.kind))
    if drop_self and params and params[0][0] in {"self", "cls"}:
        params = params[1:]
    return Sig(params=tuple(params))


def _is_mapping_like(obj: object) -> bool:
    if isinstance(obj, Mapping):
        return True
    return isinstance(obj, type) and issubclass(obj, Mapping)


def _adjust_mapping_method_sig(*, parent: object, method: str, sig: Sig) -> Sig:
    """Mark Mapping key args positional-only so we do not require `key=` (mypy rejects it)."""
    if method not in _MAPPING_KEY_METHODS or not sig.params or not _is_mapping_like(obj=parent):
        return sig
    name, kind = sig.params[0]
    if kind is not PORK:
        return sig
    return Sig(params=((name, POSONLY), *sig.params[1:]))


class Index:
    def __init__(self) -> None:
        self.funcs: dict[str, dict[str, Sig]] = {}
        self.methods: dict[tuple[str, str, str], Sig] = {}
        self.classes: set[tuple[str, str]] = set()

    def add_func(self, mod: str, name: str, sig: Sig) -> None:
        self.funcs.setdefault(mod, {})[name] = sig

    def add_method(self, mod: str, cls: str, name: str, sig: Sig) -> None:
        self.classes.add((mod, cls))
        self.methods[(mod, cls, name)] = sig

    def load_tree(self, mod: str, tree: ast.AST) -> None:
        class_stack: list[str] = []

        def visit(node: ast.AST) -> None:
            if isinstance(node, ast.ClassDef):
                class_stack.append(node.name)
                qual: str = ".".join(class_stack)
                self.classes.add((mod, qual))
                for child in node.body:
                    visit(node=child)
                _ = class_stack.pop()
                return
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                drop_self: bool = bool(class_stack) and not _is_staticmethod(node=node)
                sig: Sig = Sig(params=_kind_params(args=node.args, drop_self=drop_self))
                if class_stack:
                    self.add_method(mod=mod, cls=".".join(class_stack), name=node.name, sig=sig)
                else:
                    self.add_func(mod=mod, name=node.name, sig=sig)
                for child in node.body:
                    visit(node=child)
                return
            for sub in ast.iter_child_nodes(node=node):
                visit(node=sub)

        visit(node=tree)


def _module_name(path: Path, root: Path) -> str:
    rel: Path = path.relative_to(root)
    parts: list[str] = list(rel.with_suffix(suffix="").parts)
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def _iter_source_files(root: Path) -> Iterator[Path]:
    for path in sorted(root.rglob(pattern="*")):
        if not path.is_file() or path.suffix not in {".py", ".pyi"}:
            continue
        rel: Path = path.relative_to(root)
        if rel.parts[0] in SKIP_ROOT:
            continue
        if any(p in SKIP_ANY for p in rel.parts):
            continue
        if path.name in SKIP_FILES:
            continue
        yield path


def _attr_parts(node: ast.AST) -> Optional[list[str]]:
    parts: list[str] = []
    cur: ast.AST = node
    while True:
        if isinstance(cur, ast.Name):
            parts.append(cur.id)
            parts.reverse()
            return parts
        if isinstance(cur, ast.Attribute):
            parts.append(cur.attr)
            cur = cur.value
            continue
        return None


def _unwrap_anno(node: ast.AST) -> ast.AST:
    while True:
        if (
            isinstance(node, ast.Subscript)
            and isinstance(node.value, ast.Name)
            and node.value.id in {"Optional", "Union"}
        ):
            sl: ast.AST = node.slice
            if isinstance(sl, ast.Tuple):
                node = sl.elts[0]
                continue
            node = sl
            continue
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            try:
                node = ast.parse(source=node.value, mode="eval").body
            except SyntaxError:
                return node
            continue
        return node


def _import_map(tree: ast.AST) -> dict[str, tuple[str, str]]:
    """local name -> (module, remainder) where remainder is '' for a module import."""
    out: dict[str, tuple[str, str]] = {}
    for node in ast.walk(node=tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                name: str = alias.asname or alias.name.rsplit(".", 1)[-1]
                out[name] = (alias.name, "")
        elif isinstance(node, ast.ImportFrom) and node.module:
            for alias in node.names:
                if alias.name == "*":
                    continue
                name = alias.asname or alias.name
                out[name] = (node.module, alias.name)
    return out


def _inspect_mod_attr(modname: str, *attrs: str) -> Optional[Sig]:
    if modname.startswith("orcsome3") or modname.split(".")[0] in {"hashlib", "_hashlib"}:
        return None
    try:
        obj: object = importlib.import_module(name=modname)
        parent: object = obj
        for attr in attrs:
            parent = obj
            obj = getattr(obj, attr)
        if inspect.isclass(object=obj):
            return _sig_from_inspect(obj=obj.__init__, drop_self=True)
        sig: Optional[Sig] = _sig_from_inspect(
            obj=obj,
            drop_self=inspect.ismethoddescriptor(object=obj)
            or inspect.isfunction(object=obj)
            and hasattr(obj, "__qualname__")
            and "." in getattr(obj, "__qualname__", ""),
        )
        if sig is None or not attrs:
            return sig
        return _adjust_mapping_method_sig(parent=parent, method=attrs[-1], sig=sig)
    except Exception:
        return None


def _inspect_method(modname: str, cls: str, method: str) -> Optional[Sig]:
    if modname.startswith("orcsome3") or modname.split(".")[0] in {"hashlib", "_hashlib"}:
        return None
    try:
        obj: object = importlib.import_module(name=modname)
        for part in cls.split("."):
            obj = getattr(obj, part)
        parent: object = obj
        obj = getattr(obj, method)
        sig: Optional[Sig] = _sig_from_inspect(obj=obj, drop_self=True)
        if sig is None:
            return None
        return _adjust_mapping_method_sig(parent=parent, method=method, sig=sig)
    except Exception:
        return None


def _builtin_sig(name: str) -> Optional[Sig]:
    obj: object = getattr(builtins, name, None)
    if obj is None:
        return None
    if inspect.isclass(object=obj):
        return _sig_from_inspect(obj=obj.__init__, drop_self=True) or _sig_from_inspect(obj=obj, drop_self=False)
    return _sig_from_inspect(obj=obj, drop_self=False)


class Checker:
    def __init__(self, root: Path) -> None:
        self.root: Path = root
        self.index: Index = Index()
        self.hits: list[Hit] = []
        for path in _iter_source_files(root=root):
            try:
                tree: ast.AST = ast.parse(source=path.read_text(), filename=str(path))
            except SyntaxError:
                continue
            self.index.load_tree(mod=_module_name(path=path, root=root), tree=tree)

    def run(self) -> list[Hit]:
        for path in _iter_source_files(root=self.root):
            if path.suffix != ".py":
                continue
            tree: ast.Module = ast.parse(source=path.read_text(), filename=str(path))
            self.check_file(path=path, tree=tree)
        return self.hits

    def check_file(self, path: Path, tree: ast.Module) -> None:
        imports: dict[str, tuple[str, str]] = _import_map(tree=tree)
        mod: str = _module_name(path=path, root=self.root)
        class_stack: list[str] = []
        bindings: list[dict[str, tuple[str, str]]] = [self._module_bindings(tree=tree, imports=imports, mod=mod)]

        def resolve_type_parts(parts: list[str]) -> Optional[tuple[str, str]]:
            head, tail = parts[0], parts[1:]
            if head in bindings[-1]:
                tmod, tcls = bindings[-1][head]
                extra: str = ".".join(tail)
                cls: str = ".".join(p for p in (tcls, extra) if p)
                return (tmod, cls)
            if head in imports:
                imod, iname = imports[head]
                if iname:
                    cls = ".".join(p for p in (iname, *tail) if p)
                    return (imod, cls)
                return (imod if not tail else imod, ".".join(tail))
            if head in {"self", "cls"} and class_stack:
                if not tail:
                    return (mod, ".".join(class_stack))
                if tail[0] in bindings[-1]:
                    tmod, tcls = bindings[-1][tail[0]]
                    extra = ".".join(tail[1:])
                    return (tmod, ".".join(p for p in (tcls, extra) if p))
                return (mod, ".".join(class_stack))
            return None

        def resolve_sig(func: ast.AST) -> Optional[Sig]:
            if isinstance(func, ast.Name):
                if func.id in imports:
                    imod, iname = imports[func.id]
                    if iname:
                        sig: Optional[Sig] = self.index.funcs.get(imod, {}).get(iname)
                        if sig is not None:
                            return sig
                        sig = self.index.methods.get((imod, iname, "__init__"))
                        if sig is not None:
                            return sig
                        if (imod, iname) in self.index.classes:
                            return Sig(params=())
                        return _inspect_mod_attr(imod, iname)
                    return _inspect_mod_attr(modname=imod)
                sig = self.index.funcs.get(mod, {}).get(func.id)
                if sig is not None:
                    return sig
                if func.id in bindings[-1]:
                    tmod, tcls = bindings[-1][func.id]
                    return self.index.methods.get((tmod, tcls, "__init__")) or _inspect_method(
                        modname=tmod, cls=tcls, method="__init__"
                    )
                return _builtin_sig(name=func.id)
            parts: Optional[list[str]] = _attr_parts(node=func)
            if not parts:
                return None
            if parts[0] in imports:
                imod, iname = imports[parts[0]]
                rest: list[str] = ([iname] if iname else []) + parts[1:]
                if not rest:
                    return _inspect_mod_attr(modname=imod)
                if len(rest) == 1:
                    sig = self.index.funcs.get(imod, {}).get(rest[0])
                    if sig is not None:
                        return sig
                    sig = self.index.methods.get((imod, rest[0], "__init__"))
                    if sig is not None:
                        return sig
                    return _inspect_mod_attr(imod, rest[0])
                cls, method = ".".join(rest[:-1]), rest[-1]
                sig = self.index.methods.get((imod, cls, method))
                if sig is not None:
                    return sig
                if method == "__init__" or (imod, cls) in self.index.classes and method not in {"__init__"}:
                    pass
                return _inspect_method(modname=imod, cls=cls, method=method) or _inspect_mod_attr(imod, *rest)
            typed: Optional[tuple[str, str]] = resolve_type_parts(parts=parts[:-1]) if len(parts) > 1 else None
            if typed is not None:
                tmod, tcls = typed
                meth: str = parts[-1]
                if not tcls:
                    sig = self.index.funcs.get(tmod, {}).get(meth)
                    if sig is not None:
                        return sig
                    return _inspect_mod_attr(tmod, meth)
                sig = self.index.methods.get((tmod, tcls, meth))
                if sig is not None:
                    return sig
                return _inspect_method(modname=tmod, cls=tcls, method=meth)
            if parts[0] in {"self", "cls"} and class_stack and len(parts) == 2:
                return self.index.methods.get((mod, ".".join(class_stack), parts[1]))
            return None

        def bind_anno(name: str, anno: ast.AST) -> None:
            anno = _unwrap_anno(node=anno)
            parts: Optional[list[str]] = _attr_parts(node=anno)
            if not parts:
                return
            resolved: Optional[tuple[str, str]] = resolve_type_parts(parts=parts) if len(parts) >= 1 else None
            if resolved is not None:
                bindings[-1][name] = resolved
                return
            if parts[0] in imports:
                imod, iname = imports[parts[0]]
                cls: str = ".".join(p for p in ((iname, *parts[1:]) if iname else parts[1:]) if p)
                bindings[-1][name] = (imod, cls)
            elif len(parts) == 1:
                bindings[-1][name] = (mod, parts[0])

        def bind_rhs(name: str, value: ast.AST) -> None:
            if not isinstance(value, ast.Call):
                return
            parts: Optional[list[str]] = _attr_parts(node=value.func)
            if not parts:
                return
            if parts[0] in imports:
                imod, iname = imports[parts[0]]
                rest: list[str] = ([iname] if iname else []) + parts[1:]
                if len(rest) >= 1:
                    if len(rest) >= 2:
                        bindings[-1][name] = (imod, ".".join(rest[:-1]))
                    else:
                        bindings[-1][name] = (imod, rest[0])

        def check_call(node: ast.Call) -> None:
            if isinstance(node.func, ast.Name) and node.func.id in {"cast", "exec"}:
                return
            # 3.8 Path.relative_to(*other) vs 3.12+ relative_to(other, *); keyword other= breaks 3.8.
            if isinstance(node.func, ast.Attribute) and node.func.attr == "relative_to":
                return
            sig: Optional[Sig] = resolve_sig(func=node.func)
            if sig is None:
                return
            if any(isinstance(arg, ast.Starred) for arg in node.args):
                return
            n_fixed: int = 0
            for _name, kind in sig.params:
                if kind is VARPOS:
                    break
                n_fixed += 1
            n_plain: int = 0
            for arg in node.args:
                if isinstance(arg, ast.Starred):
                    break
                n_plain += 1
            # Keywording a PORK param would make leftover *args values positional-after-keyword.
            if n_plain > n_fixed:
                return
            i: int = 0
            for arg in node.args:
                if isinstance(arg, ast.Starred):
                    return
                if i >= len(sig.params):
                    return
                pname, kind = sig.params[i]
                if kind is VARPOS:
                    return
                if kind is PORK:
                    self.hits.append(Hit(path=path, lineno=arg.lineno, col=arg.col_offset, param=pname))
                i += 1

        def visit(node: ast.AST) -> None:
            if isinstance(node, ast.ClassDef):
                class_stack.append(node.name)
                bindings.append(dict(bindings[-1]))
                for child in node.body:
                    visit(node=child)
                _ = bindings.pop()
                _ = class_stack.pop()
                return
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                bindings.append(dict(bindings[-1]))
                for a in node.args.args + node.args.posonlyargs + node.args.kwonlyargs:
                    if a.annotation is not None:
                        bind_anno(name=a.arg, anno=a.annotation)
                for child in node.body:
                    visit(node=child)
                _ = bindings.pop()
                return
            if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                bind_anno(name=node.target.id, anno=node.annotation)
                if node.value is not None:
                    bind_rhs(name=node.target.id, value=node.value)
            if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
                bind_rhs(name=node.targets[0].id, value=node.value)
            if isinstance(node, ast.Call):
                check_call(node=node)
            for sub in ast.iter_child_nodes(node=node):
                if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                visit(node=sub)

        visit(node=tree)

    def _module_bindings(
        self, tree: ast.Module, imports: dict[str, tuple[str, str]], mod: str
    ) -> dict[str, tuple[str, str]]:
        bindings: dict[str, tuple[str, str]] = {}
        for node in tree.body:
            if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                anno: ast.AST = _unwrap_anno(node=node.annotation)
                parts: Optional[list[str]] = _attr_parts(node=anno)
                if parts and parts[0] in imports:
                    imod, iname = imports[parts[0]]
                    cls: str = ".".join(p for p in ((iname, *parts[1:]) if iname else parts[1:]) if p)
                    bindings[node.target.id] = (imod, cls)
                elif parts and len(parts) == 1:
                    bindings[node.target.id] = (mod, parts[0])
        return bindings


def _self_check() -> None:
    def hits_for(src: str) -> list[str]:
        root: Path = Path("/tmp/named-args-self-check")
        root.mkdir(parents=True, exist_ok=True)
        path: Path = root / "mod.py"
        _ = path.write_text(data=src)
        checker: Checker = Checker(root=root)
        checker.root = root
        checker.index = Index()
        tree: ast.Module = ast.parse(source=src)
        checker.index.load_tree(mod="mod", tree=tree)
        checker.hits = []
        checker.check_file(path=path, tree=tree)
        return [h.param for h in checker.hits]

    assert hits_for(src="def f(a, /):\n    f(1)\n") == []
    assert hits_for(src="def f(*args):\n    f(1)\n") == []
    assert hits_for(src="def f(a, *args):\n    f(1, 2)\n") == []
    assert hits_for(src="def f(a, *args):\n    f(1)\n") == ["a"]
    assert hits_for(src="def f(a):\n    f(1)\n") == ["a"]
    assert hits_for(src="def f(a, b):\n    f(a=1, b=2)\n") == []
    assert hits_for(src="def f(a, b):\n    f(1, b=2)\n") == ["a"]
    assert hits_for(src="len(x)\n") == []
    assert hits_for(src="import os\nos.environ.pop('DISPLAY')\n") == []
    assert hits_for(src="import os\nos.environ.pop('DISPLAY', None)\n") == ["default"]
    print("check_named_args self-check ok")


def main(argv: list[str]) -> int:
    _self_check()
    root: Path = Path(argv[1] if len(argv) > 1 else Path(__file__).resolve().parents[1])
    hits: list[Hit] = Checker(root=root).run()
    for h in hits:
        try:
            rel: Path = h.path.relative_to(root)
        except ValueError:
            rel = h.path
        print(f"{rel}:{h.lineno}:{h.col + 1}: positional arg should be keyword: {h.param}=")
    if hits:
        print(f"{len(hits)} named-arg violation(s)", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(argv=sys.argv))
