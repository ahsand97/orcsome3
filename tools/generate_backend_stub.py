"""Generate `orcsome3_backend.pyi` from `orcsome3_backend.pyx`.

The compiled extension has no types of its own. This script walks Cython's parse tree of the
`.pyx`, then writes a `.pyi` that type checkers use when `import orcsome3_backend` runs.

Pipeline (`generate`):
1. Parse the `.pyx` with Cython (`parse_from_strings`). Nodes are untyped Cython AST objects;
   helpers poke attributes (`name`, `body.stats`, `return_type_annotation`) by convention.
2. Import the already-built `.so` for real enum integers (`xlib.KeyPress` is an AttributeNode
   in the tree, not a number). Requires `make native-fast` first.
3. Emit enums, `cdef class` wrappers, then module-level `def` functions.
4. Prefix only the imports the text actually uses, then format with ruff so `--check`
   matches `make format`.

What the stub contains:
- Integer `class Foo(IntEnum)` with values from the `.so`. `PROPERTY_FORMAT` stays `Enum`
  because its members are `(bits, array_typecode)` tuples, not ints.
- `cdef class` attributes from `cdef public` fields and from `@property` getters that have a
  Python return annotation (`-> EVENT_TYPES`). PEP-526 lines on cdef classes (`_type: EVENT_TYPES`)
  are ignored by Cython and are not a field source.
- `def` signatures copied from Python `->` annotations on the `.pyx`.

`make stubs` writes the file. `make stubs-check` (CI) runs this script with `--check` (must match the
committed `.pyi`).
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from enum import Enum, EnumMeta
from pathlib import Path
from typing import Optional

from Cython.Compiler.TreeFragment import parse_from_strings

ROOT: Path = Path(__file__).resolve().parent.parent
PYX: Path = ROOT / "orcsome3" / "libs" / "cython_libs" / "orcsome3_backend.pyx"
STUB: Path = ROOT / "orcsome3_backend.pyi"
# Factory / dispatcher used from Python wrappers; keep them on the stub even though they are `_` prefixed.
KEEP_PRIVATE: set[str] = {"_new_from_python_", "_get_specific_event_"}
SKIP_METHODS: set[str] = {"__dealloc__"}
# C / X11 typedefs that should appear as Python builtins on the stub. Unknown names are copied as-is
# (they are expected to be `cdef class` names like `PyDisplay`).
C_TO_PY: dict[str, str] = {
    "int": "int",
    "char": "int",
    "bint": "bool",
    "BOOL": "bool",
    "Window": "int",
    "Atom": "int",
    "Time": "int",
    "XID": "int",
    "KeySym": "int",
    "KeyCode": "int",
    "array": "array[int]",
    "float": "float",
    "double": "float",
    "str": "str",
}


def _stats(node: object) -> list[object]:
    """Return the statement list of a Cython AST node.

    Classes and the module wrap their children in a `body` with `.stats`. A leaf with no list
    is returned as a one-item list so callers can always iterate.
    """
    body: object = getattr(node, "body", node)
    stats: object = getattr(body, "stats", None)
    if not isinstance(stats, list):
        return [body]
    items: list[object] = []
    for item in stats:
        items.append(item)
    return items


def _kind(node: object) -> str:
    """Cython AST class name (`PyClassDefNode`, `DefNode`, `CVarDefNode`, `TupleNode`, …)."""
    return type(node).__name__


def _ann_text(ann: object) -> Optional[str]:
    """Python annotation text from a Cython `AnnotationNode` (`-> EVENT_TYPES`, `x: int`).

    Rewrites `pyarray.array` to `array` so the stub can `from array import array`. Returns
    `None` when the node has no annotation (cdef-only C types).
    """
    if ann is None:
        return None
    string: object = getattr(ann, "string", None)
    value: object = getattr(string, "value", None)
    if not isinstance(value, str):
        return None
    text: str = value.replace("pyarray.array", "array").strip("'\"")
    return text


def _arg_name(arg: object) -> str:
    """Parameter name, walking Cython's nested declarators (`int *p` wraps the name in a pointer node)."""
    dec: object = getattr(arg, "declarator", None)
    name: Optional[str] = None
    while dec is not None:
        raw: object = getattr(dec, "name", None)
        if isinstance(raw, str):
            name = raw
        dec = getattr(dec, "base", None)
    if name is None:
        raise SystemExit("argument with no name")
    return name


def _c_type_name(typed: object) -> Optional[str]:
    """C type name on a cdef argument or field (`int`, `Window`, `bint`), or `None` if absent."""
    base: object = getattr(typed, "base_type", None)
    if base is None:
        return None
    name: object = getattr(base, "name", None)
    return name if isinstance(name, str) else None


def _map_c_type(c_name: Optional[str], *, where: str) -> str:
    """Map a C / X11 type to a Python stub type via `C_TO_PY`; unknown names are kept (cdef classes)."""
    if c_name is None:
        raise SystemExit(f"missing C type at {where}")
    py_name: Optional[str] = C_TO_PY.get(c_name)
    if py_name is None:
        return c_name
    return py_name


def _arg_py_type(arg: object, *, where: str) -> str:
    """Stub type for one parameter: Python `x: T` annotation if present, else the mapped C type."""
    annotated: Optional[str] = _ann_text(ann=getattr(arg, "annotation", None))
    if annotated is not None:
        return annotated
    return _map_c_type(c_name=_c_type_name(typed=arg), where=where)


def _deco_names(node: object) -> list[str]:
    """Decorator names on a `DefNode` (`property`, `setter`, `classmethod`, `staticmethod`)."""
    names: list[str] = []
    for deco in getattr(node, "decorators", None) or []:
        inner: object = getattr(deco, "decorator", deco)
        name: object = getattr(inner, "name", None) or getattr(inner, "attribute", None)
        if isinstance(name, str):
            names.append(name)
    return names


def _is_enum_class(node: object) -> bool:
    """True if this `PyClassDefNode` subclasses `Enum` or `IntEnum` (`pyenum.IntEnum` in the .pyx)."""
    bases: object = getattr(node, "bases", None)
    for base in getattr(bases, "args", None) or []:
        attr: object = getattr(base, "attribute", None) or getattr(base, "name", None)
        if attr in {"Enum", "IntEnum"}:
            return True
    return False


def _enum_python_base(node: object) -> str:
    """Stub base for an enum class: `IntEnum` when the .pyx uses `pyenum.IntEnum`, else `Enum`."""
    bases: object = getattr(node, "bases", None)
    for base in getattr(bases, "args", None) or []:
        attr: object = getattr(base, "attribute", None) or getattr(base, "name", None)
        if attr == "IntEnum":
            return "IntEnum"
        if attr == "Enum":
            return "Enum"
    return "Enum"


def _base_class_name(node: object) -> Optional[str]:
    """First base of a `cdef class` (`PyXButtonEvent(PyXEvent)` → `PyXEvent`), or `None`."""
    bases: object = getattr(node, "bases", None)
    args: object = getattr(bases, "args", None)
    if not isinstance(args, list) or not args:
        return None
    first: object = args[0]
    name: object = getattr(first, "name", None)
    return name if isinstance(name, str) else None


def _declarator_names(var: object) -> list[str]:
    """Field names on a `CVarDefNode`. One cdef line can declare several (`cdef public int x, y`)."""
    names: list[str] = []
    for dec in getattr(var, "declarators", None) or []:
        name: object = getattr(dec, "name", None)
        if isinstance(name, str):
            names.append(name)
    return names


def _format_def(name: str, args: list[str], ret: str, *, decorators: list[str], indent: str) -> str:
    """Render `def name(...) -> ret: ...`, wrapping arguments if the line would exceed 120 chars."""
    lines: list[str] = [f"{indent}@{deco}" for deco in decorators]
    joined: str = ", ".join(args)
    one: str = f"{indent}def {name}({joined}) -> {ret}: ..."
    if len(one) <= 120:
        lines.append(one)
        return "\n".join(lines)
    lines.append(f"{indent}def {name}(")
    for arg in args:
        lines.append(f"{indent}    {arg},")
    lines.append(f"{indent}) -> {ret}: ...")
    return "\n".join(lines)


def _emit_function(node: object, *, indent: str, skip_self: bool) -> str:
    """Stub one `def` from a Cython `DefNode`.

    Requires a Python `->` return annotation on the .pyx (Cython `cpdef int foo()` is not used
    for the Python-facing API). `skip_self` leaves `self`/`cls` untyped, which is normal on stubs.
    """
    name: object = getattr(node, "name", None)
    if not isinstance(name, str):
        raise SystemExit("function with no name")
    ret: Optional[str] = _ann_text(ann=getattr(node, "return_type_annotation", None))
    if ret is None:
        raise SystemExit(f"missing return annotation on {name}")
    args: list[str] = []
    for arg in getattr(node, "args", None) or []:
        arg_name: str = _arg_name(arg=arg)
        if skip_self and arg_name in {"self", "cls"}:
            args.append(arg_name)
            continue
        args.append(f"{arg_name}: {_arg_py_type(arg=arg, where=f'{name}.{arg_name}')}")
    decos: list[str] = [d for d in _deco_names(node=node) if d in {"staticmethod", "classmethod"}]
    return _format_def(name=name, args=args, ret=ret, decorators=decos, indent=indent)


def _runtime_enum_values() -> dict[str, dict[str, object]]:
    """`{enum_class: {member: value}}` from the compiled `orcsome3_backend` module.

    The parse tree stores most members as `xlib.KeyPress` / `libev.EV_READ` (AttributeNodes), not
    integers. The `.so` has already folded those C constants. Exits if the extension is missing.
    """
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    try:
        import orcsome3_backend as backend
    except ImportError:
        raise SystemExit("need a built orcsome3_backend to emit enum values (make native-fast)")
    out: dict[str, dict[str, object]] = {}
    for name in dir(backend):
        obj: object = getattr(backend, name)
        if not isinstance(obj, EnumMeta) or obj is Enum:
            continue
        values: dict[str, object] = {}
        for name_ in obj.__members__:
            member: Enum = getattr(obj, name_)
            values[name_] = member.value
        out[name] = values
    return out


def _enum_member_rhs(*, rhs: object, runtime: object) -> str:
    """Source text for one enum member value on the stub (`2`, `(8, "b")`, …).

    Prefers `runtime` from the `.so`. If that member is not imported yet (pyx added, extension not
    rebuilt), falls back to IntNode / TupleNode in the tree, else `0`.
    """
    if runtime is not None:
        return repr(runtime)
    # ponytail: .so is missing this member (rebuild then remake stubs); IntNode/tuple from the pyx, else 0
    kind: str = _kind(node=rhs)
    if kind == "TupleNode":
        parts: list[str] = []
        for item in getattr(rhs, "args", None) or []:
            item_kind: str = _kind(node=item)
            value: object = getattr(item, "value", None)
            if item_kind == "IntNode":
                parts.append(str(value))
            elif item_kind == "UnicodeNode":
                parts.append(repr(value))
            else:
                parts.append("0")
        return f"({', '.join(parts)})"
    if kind == "IntNode":
        int_value: object = getattr(rhs, "value", None)
        if int_value is not None:
            return str(int_value)
    return "0"


def _emit_enum(node: object, *, runtime: dict[str, dict[str, object]]) -> str:
    """Stub one Python enum: `class NAME(IntEnum|Enum):` members, then any `@classmethod` helpers."""
    name: object = getattr(node, "name", None)
    if not isinstance(name, str):
        raise SystemExit("enum with no name")
    lines: list[str] = [f"class {name}({_enum_python_base(node=node)}):"]
    methods: list[str] = []
    members_runtime: dict[str, object] = runtime.get(name, {})
    for stat in _stats(node=node):
        kind: str = _kind(node=stat)
        if kind == "SingleAssignmentNode":
            member: object = getattr(getattr(stat, "lhs", None), "name", None)
            if isinstance(member, str):
                lines.append(
                    f"    {member} = {_enum_member_rhs(rhs=getattr(stat, 'rhs', None), runtime=members_runtime.get(member))}"
                )
        elif kind == "DefNode":
            methods.append(_emit_function(node=stat, indent="    ", skip_self=True))
    if len(lines) == 1 and not methods:
        lines.append("    ...")
    if methods:
        lines.append("")
        lines.extend(methods)
    return "\n".join(lines)


def _emit_cclass(node: object) -> str:
    """Stub one `cdef class` as a Python class.

    Fields, in order:
    - `cdef public` C attributes (mapped through `C_TO_PY`).
    - `@property` getters with a Python `->` type, emitted as attributes (`type: EVENT_TYPES`).
      Setters are skipped (same name as the getter).
    - Public methods, plus `KEEP_PRIVATE` factories. `__dealloc__` is omitted.

    PEP-526 annotations on cdef classes are not used: Cython warns and drops them.
    """
    name: object = getattr(node, "class_name", None)
    if not isinstance(name, str):
        raise SystemExit("cdef class with no name")
    base: Optional[str] = _base_class_name(node=node)
    header: str = f"class {name}({base}):" if base is not None else f"class {name}:"
    body: list[str] = []
    seen: set[str] = set()
    for stat in _stats(node=node):
        kind: str = _kind(node=stat)
        if kind == "CVarDefNode":
            if getattr(stat, "visibility", None) != "public":
                continue
            py_type: str = _map_c_type(c_name=_c_type_name(typed=stat), where=f"{name} field")
            for field in _declarator_names(var=stat):
                if field in seen:
                    continue
                seen.add(field)
                body.append(f"    {field}: {py_type}")
        elif kind == "DefNode":
            meth: object = getattr(stat, "name", None)
            if not isinstance(meth, str) or meth in SKIP_METHODS:
                continue
            decos: list[str] = _deco_names(node=stat)
            if "setter" in decos:
                continue
            if "property" in decos:
                ret: Optional[str] = _ann_text(ann=getattr(stat, "return_type_annotation", None))
                if ret is None:
                    raise SystemExit(f"missing return annotation on {name}.{meth}")
                if meth not in seen:
                    seen.add(meth)
                    body.append(f"    {meth}: {ret}")
                continue
            if meth.startswith("_") and meth not in KEEP_PRIVATE:
                continue
            body.append(_emit_function(node=stat, indent="    ", skip_self=True))
    if not body:
        return f"{header} ..."
    return "\n".join([header, *body])


def generate() -> str:
    """Build the full `.pyi` text: enums, cdef classes, module functions, then used imports only."""
    source: str = PYX.read_text(encoding="utf-8")
    tree: object = parse_from_strings(name="orcsome3_backend", code=source)
    enums: list[str] = []
    classes: list[str] = []
    functions: list[str] = []
    runtime: dict[str, dict[str, object]] = _runtime_enum_values()
    for stat in _stats(node=tree):
        kind: str = _kind(node=stat)
        if kind == "PyClassDefNode" and _is_enum_class(node=stat):
            enums.append(_emit_enum(node=stat, runtime=runtime))
        elif kind == "CClassDefNode":
            classes.append(_emit_cclass(node=stat))
        elif kind == "DefNode":
            functions.append(_emit_function(node=stat, indent="", skip_self=False))
    text: str = "\n\n".join(enums + classes + functions)
    needs_any: bool = "Any" in text
    needs_callable: bool = "Callable" in text
    needs_optional: bool = "Optional[" in text
    needs_union: bool = "Union[" in text
    needs_array: bool = "array[" in text
    needs_path: bool = "Path" in text
    typing_names: list[str] = []
    if needs_any:
        typing_names.append("Any")
    if needs_optional:
        typing_names.append("Optional")
    if needs_union:
        typing_names.append("Union")
    imports: list[str] = [
        '"""Type stub for the compiled orcsome3_backend extension (generated from orcsome3_backend.pyx)."""',
        "",
        "from __future__ import annotations",
        "",
    ]
    if needs_array:
        imports.append("from array import array")
    if needs_callable:
        imports.append("from collections.abc import Callable")
    imports.append("from enum import Enum, IntEnum")
    if needs_path:
        imports.append("from pathlib import Path")
    if typing_names:
        imports.append(f"from typing import {', '.join(typing_names)}")
    return _ruff_format(source="\n".join(imports) + "\n\n" + text + "\n")


def _ruff_format(source: str) -> str:
    """Format the stub the same way `make format` does, so `--check` is not a false diff."""
    proc: subprocess.CompletedProcess[str] = subprocess.run(
        args=[sys.executable, "-m", "ruff", "format", "--stdin-filename", str(STUB)],
        input=source,
        capture_output=True,
        text=True,
        check=True,
    )
    return proc.stdout


def main() -> int:
    """Write `orcsome3_backend.pyi`, or with `--check` exit 1 if the committed file is stale.

    Also refuses to write a stub that is missing `EVENT_TYPES` as `IntEnum` (regression guard:
    event `.type` must not fall back to `Any`).
    """
    parser: argparse.ArgumentParser = argparse.ArgumentParser(
        description="Generate orcsome3_backend.pyi from orcsome3_backend.pyx"
    )
    _ = parser.add_argument(
        "--check",
        action="store_true",
        help="exit 1 if the committed .pyi does not match a fresh generate() (used by make stubs-check)",
    )
    args: argparse.Namespace = parser.parse_args()
    stub: str = generate()
    if "class EVENT_TYPES(IntEnum):" not in stub or "    type: EVENT_TYPES" not in stub:
        print("generator did not emit EVENT_TYPES as an IntEnum", file=sys.stderr)
        return 1
    if args.check:
        current: str = STUB.read_text(encoding="utf-8") if STUB.is_file() else ""
        if current != stub:
            print(f"{STUB.relative_to(ROOT)} is stale. Run: make stubs", file=sys.stderr)
            return 1
        return 0
    _ = STUB.write_text(data=stub, encoding="utf-8")
    print(f"wrote {STUB.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
