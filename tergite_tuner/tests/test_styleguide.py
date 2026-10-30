# This code is part of Tergite
#
# (C) Copyright Chalmers Next Labs AB 2026
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.
"""The house style that black and ruff cannot enforce, checked on every test run.

Code that broke a rule when the rule was added is listed in
fixtures/styleguide_baseline.txt. That list may only shrink: a new violation fails, and so
does a listed one that has been fixed but not deleted from the list.
"""

import ast
import re
import tokenize
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from functools import cache
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parent.parent.parent
BASELINE_FILE = Path(__file__).parent / "fixtures" / "styleguide_baseline.txt"
PACKAGE = "tergite_tuner"
ALL_ROOTS = (PACKAGE, "conftest.py", "dev")

# a new verb is added here in review, never to the baseline
VERBS = frozenset(
    {
        "accept",
        "add",
        "align",
        "analyse",
        "analyze",
        "apply",
        "assign",
        "authenticate",
        "authorize",
        "broadcast",
        "calculate",
        "calibrate",
        "cancel",
        "cast",
        "check",
        "choose",
        "claim",
        "classify",
        "cleanup",
        "clear",
        "close",
        "collect",
        "compare",
        "compile",
        "compute",
        "configure",
        "connect",
        "construct",
        "convert",
        "count",
        "create",
        "decode",
        "decrypt",
        "delete",
        "derive",
        "deserialize",
        "destroy",
        "detect",
        "disconnect",
        "dismiss",
        "dispatch",
        "display",
        "do",
        "draw",
        "emit",
        "encode",
        "encrypt",
        "ensure",
        "execute",
        "expire",
        "export",
        "extract",
        "fetch",
        "fill",
        "filter",
        "find",
        "fit",
        "forget",
        "format",
        "from",
        "generate",
        "get",
        "group",
        "guess",
        "handle",
        "hash",
        "identify",
        "ignore",
        "include",
        "increment",
        "index",
        "init",
        "initialize",
        "insert",
        "inspect",
        "is",
        "keep",
        "load",
        "log",
        "login",
        "logout",
        "make",
        "manage",
        "map",
        "mark",
        "measure",
        "merge",
        "mitigate",
        "move",
        "notify",
        "open",
        "order",
        "pad",
        "paginate",
        "parse",
        "partition",
        "patch",
        "pick",
        "plot",
        "populate",
        "precompile",
        "prepare",
        "print",
        "process",
        "prune",
        "publish",
        "pull",
        "push",
        "query",
        "raise",
        "ramp",
        "read",
        "reanalyse",
        "receive",
        "record",
        "redirect",
        "reduce",
        "refresh",
        "register",
        "reject",
        "remove",
        "render",
        "replace",
        "reply",
        "request",
        "require",
        "reset",
        "resolve",
        "restore",
        "revert",
        "route",
        "run",
        "save",
        "scrape",
        "search",
        "seed",
        "send",
        "serialize",
        "set",
        "setup",
        "should",
        "sign",
        "sort",
        "split",
        "start",
        "stop",
        "store",
        "switch",
        "sync",
        "to",
        "toggle",
        "transfer",
        "translate",
        "try",
        "tune",
        "unwrap",
        "update",
        "upsert",
        "use",
        "validate",
        "verify",
        "view",
        "wait",
        "write",
    }
)
HOOK_PREFIX = "on"
BOOLEAN_PREFIXES = ("is_", "should_")
BOOLEAN_ANNOTATIONS = frozenset(
    {"bool", "Optional[bool]", "bool | None", "None | bool"}
)
VALUE_DECORATORS = frozenset({"property", "cached_property", "computed_field"})
LICENSE_MARKERS = (
    "# This code is part of Tergite",
    "This code is licensed under the Apache License, Version 2.0",
)
LICENSE_SEARCH_LINES = 15
CONSTANT_NAME = re.compile(r"^_?[A-Z][A-Z0-9_]*$")
BANNER_COMMENT = re.compile(
    r"^#\s*(?:[-=*#~_]{10,}|[-=*#~_]{3,}\s*\S.*\S\s*[-=*#~_]{3,})$"
)
# a package imports only from the layers below it: utils < storage, config < lib < tuner, export
FORBIDDEN_IMPORTS = {
    "tergite_tuner/utils": ("lib", "config", "storage", "tuner", "export"),
    "tergite_tuner/storage": ("lib", "tuner", "export"),
    "tergite_tuner/config": ("lib", "tuner", "export"),
    "tergite_tuner/lib": ("tuner", "export"),
}
# each package that may import these, and only it
CONFINED_IMPORTS = {
    "quantify_scheduler": "tergite_tuner/backend/",
    "qblox_scheduler": "tergite_tuner/backend/",
    "redis": "tergite_tuner/storage/",
}
HOST_TAKEOVER_CALLS = frozenset({"quit", "exit", "sys.exit", "matplotlib.use"})
DEFINITIONS = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)

FunctionNode = ast.FunctionDef | ast.AsyncFunctionDef


@dataclass(frozen=True)
class Violation:
    rule: str
    location: str

    def __str__(self) -> str:
        return f"{self.rule}: {self.location}"


@dataclass(frozen=True)
class Module:
    name: str
    path: Path
    tree: ast.Module


def test_functions_are_named_with_a_verb():
    _assert_follows("verb")


def test_booleans_start_with_is_or_should():
    _assert_follows("boolean")


def test_constants_sit_above_the_first_definition():
    _assert_follows("constant-position")


def test_private_helpers_sit_below_public_code():
    _assert_follows("private-helper-position")


def test_no_banner_comments():
    _assert_follows("banner")


def test_every_file_carries_the_license_header():
    _assert_follows("license-header")


def test_all_lists_strings():
    _assert_follows("all-strings")


def test_imports_respect_the_layers():
    _assert_follows("import-layering")


def test_scheduler_and_redis_are_imported_in_one_package_each():
    _assert_follows("confined-import")


def test_library_code_never_takes_over_its_host():
    _assert_follows("host-takeover")


def test_functions_are_fully_type_hinted():
    _assert_follows("type-hints")


def test_baseline_lists_only_current_violations():
    current = {str(violation) for rule in _RULES for violation in find_violations(rule)}
    fixed = sorted(_read_baseline() - current)

    assert fixed == [], f"fixed, so delete from {BASELINE_FILE.name}:\n" + "\n".join(
        fixed
    )


def test_checks_catch_what_they_describe(tmp_path: Path):
    (tmp_path / "tergite_tuner" / "utils").mkdir(parents=True)
    (tmp_path / "tergite_tuner" / "utils" / "sample.py").write_text(
        "import matplotlib\n"
        "import redis\n"
        "from tergite_tuner.lib.base import node\n"
        "def _get_limit() -> None: ...\n"
        "def job_status(active: bool) -> None:\n"
        "    matplotlib.use('agg')\n"
        "# ---- jobs ----\n"
        "LIMIT = 5\n"
    )

    found = {
        str(violation)
        for rule in _RULES
        for violation in find_violations(rule, app_root=tmp_path)
    }

    assert found == {
        "verb: tergite_tuner/utils/sample.py::job_status",
        "boolean: tergite_tuner/utils/sample.py::job_status(active)",
        "constant-position: tergite_tuner/utils/sample.py::LIMIT",
        "private-helper-position: tergite_tuner/utils/sample.py::job_status",
        "banner: tergite_tuner/utils/sample.py: # ---- jobs ----",
        "license-header: tergite_tuner/utils/sample.py",
        "import-layering: tergite_tuner/utils/sample.py::import tergite_tuner.lib.base",
        "confined-import: tergite_tuner/utils/sample.py::import redis",
        "host-takeover: tergite_tuner/utils/sample.py::job_status matplotlib.use",
    }


def find_violations(rule: str, app_root: Path = APP_ROOT) -> list[Violation]:
    check, should_include_tests = _RULES[rule]
    return [
        violation
        for module in _parse_modules(app_root, should_include_tests)
        for violation in check(module)
    ]


def _assert_follows(rule: str):
    baseline = _read_baseline()
    new = [str(v) for v in find_violations(rule) if str(v) not in baseline]

    assert new == [], "\n".join(new)


@cache
def _read_baseline() -> set[str]:
    lines = BASELINE_FILE.read_text().splitlines() if BASELINE_FILE.exists() else []
    return {line.strip() for line in lines if line.strip() and not line.startswith("#")}


@cache
def _parse_modules(app_root: Path, should_include_tests: bool) -> tuple[Module, ...]:
    return tuple(
        Module(
            name=path.relative_to(app_root).as_posix(),
            path=path,
            tree=ast.parse(path.read_text(), filename=str(path)),
        )
        for path in _iter_python_files(app_root, should_include_tests)
    )


def _iter_python_files(app_root: Path, should_include_tests: bool) -> Iterator[Path]:
    roots = ALL_ROOTS if should_include_tests else (PACKAGE,)
    for root in roots:
        path = app_root / root
        if path.is_file():
            yield path
        elif path.is_dir():
            yield from sorted(
                file
                for file in path.rglob("*.py")
                if "__pycache__" not in file.parts
                and (should_include_tests or "tests" not in file.parts)
            )


def _check_verbs(module: Module) -> Iterator[Violation]:
    for qualname, node in _walk_functions(module.tree):
        if not (
            _is_dunder(node.name) or _is_value(node) or _starts_with_verb(node.name)
        ):
            yield Violation("verb", f"{module.name}::{qualname}")


def _check_booleans(module: Module) -> Iterator[Violation]:
    for qualname, node in _walk_functions(module.tree):
        for argument in _arguments_of(node):
            if _is_boolean(argument.annotation) and not _has_boolean_prefix(
                argument.arg
            ):
                yield Violation("boolean", f"{module.name}::{qualname}({argument.arg})")

    for qualname, node in _walk_annotated_names(module.tree):
        if _is_boolean(node.annotation) and not _has_boolean_prefix(node.target.id):
            yield Violation("boolean", f"{module.name}::{qualname}")


def _check_constant_positions(module: Module) -> Iterator[Violation]:
    defined_names: set[str] = set()
    for statement in module.tree.body:
        if isinstance(statement, DEFINITIONS):
            defined_names.add(statement.name)
            continue

        is_after_definitions = bool(defined_names)
        is_built_from_definitions = bool(_names_used_in(statement) & defined_names)
        for name in _constant_names_assigned_by(statement):
            if is_after_definitions and not is_built_from_definitions:
                yield Violation("constant-position", f"{module.name}::{name}")


def _check_private_helper_positions(module: Module) -> Iterator[Violation]:
    has_private_function_above = False
    for statement in module.tree.body:
        if not isinstance(statement, DEFINITIONS) or _is_dunder(statement.name):
            continue

        is_private = statement.name.startswith("_")
        if is_private and not isinstance(statement, ast.ClassDef):
            has_private_function_above = True
        elif not is_private and has_private_function_above:
            yield Violation(
                "private-helper-position", f"{module.name}::{statement.name}"
            )


def _check_banners(module: Module) -> Iterator[Violation]:
    with module.path.open("rb") as file:
        for token in tokenize.tokenize(file.readline):
            if token.type == tokenize.COMMENT and BANNER_COMMENT.match(
                token.string.strip()
            ):
                # keyed by text, not line, so that editing above it does not move it
                yield Violation("banner", f"{module.name}: {token.string.strip()}")


def _check_license_header(module: Module) -> Iterator[Violation]:
    head = "\n".join(module.path.read_text().splitlines()[:LICENSE_SEARCH_LINES])
    if not all(marker in head for marker in LICENSE_MARKERS):
        yield Violation("license-header", module.name)


def _check_all_strings(module: Module) -> Iterator[Violation]:
    for statement in module.tree.body:
        if (
            isinstance(statement, ast.Assign)
            and any(
                isinstance(t, ast.Name) and t.id == "__all__" for t in statement.targets
            )
            and isinstance(statement.value, (ast.List, ast.Tuple))
            and not all(
                isinstance(item, ast.Constant) and isinstance(item.value, str)
                for item in statement.value.elts
            )
        ):
            yield Violation("all-strings", f"{module.name}::__all__")


def _check_import_layering(module: Module) -> Iterator[Violation]:
    package = "/".join(module.name.split("/")[:2])
    forbidden = FORBIDDEN_IMPORTS.get(package, ())
    for imported in _imported_modules(module):
        parts = imported.split(".")
        if parts[0] == PACKAGE and len(parts) > 1 and parts[1] in forbidden:
            yield Violation("import-layering", f"{module.name}::import {imported}")


def _check_confined_imports(module: Module) -> Iterator[Violation]:
    for imported in _imported_modules(module):
        home = CONFINED_IMPORTS.get(imported.split(".")[0])
        if home is not None and not module.name.startswith(home):
            yield Violation("confined-import", f"{module.name}::import {imported}")


def _check_host_takeover(module: Module) -> Iterator[Violation]:
    for qualname, node in _walk_functions(module.tree):
        for call in ast.walk(node):
            if (
                isinstance(call, ast.Call)
                and ast.unparse(call.func) in HOST_TAKEOVER_CALLS
            ):
                yield Violation(
                    "host-takeover",
                    f"{module.name}::{qualname} {ast.unparse(call.func)}",
                )


def _check_type_hints(module: Module) -> Iterator[Violation]:
    for qualname, node in _walk_functions(module.tree):
        arguments = _arguments_of(node)
        if _is_method(qualname) and arguments and arguments[0].arg in ("self", "cls"):
            arguments = arguments[1:]
        is_missing_return = node.returns is None and node.name != "__init__"
        if is_missing_return or any(a.annotation is None for a in arguments):
            yield Violation("type-hints", f"{module.name}::{qualname}")


def _walk_functions(tree: ast.AST) -> Iterator[tuple[str, FunctionNode]]:
    for qualname, node in _walk_qualified(tree, prefix=""):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            yield qualname, node


def _walk_annotated_names(tree: ast.AST) -> Iterator[tuple[str, ast.AnnAssign]]:
    for qualname, node in _walk_qualified(tree, prefix=""):
        if isinstance(node, ast.AnnAssign):
            yield qualname, node


def _walk_qualified(node: ast.AST, prefix: str) -> Iterator[tuple[str, ast.AST]]:
    """Yields every function, class and annotated name with its dotted qualified name"""
    for child in ast.iter_child_nodes(node):
        if isinstance(child, DEFINITIONS):
            qualname = f"{prefix}{child.name}"
            yield qualname, child
            yield from _walk_qualified(child, prefix=f"{qualname}.")
        elif isinstance(child, ast.AnnAssign) and isinstance(child.target, ast.Name):
            yield f"{prefix}{child.target.id}", child
        else:
            yield from _walk_qualified(child, prefix)


def _arguments_of(node: FunctionNode) -> list[ast.arg]:
    args = node.args
    variadic = [arg for arg in (args.vararg, args.kwarg) if arg is not None]
    return args.posonlyargs + args.args + args.kwonlyargs + variadic


def _imported_modules(module: Module) -> Iterator[str]:
    for node in ast.walk(module.tree):
        if isinstance(node, ast.Import):
            yield from (alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            base = _resolve_import(module.name, node.level, node.module)
            yield base
            if node.module is None:
                yield from (f"{base}.{alias.name}" for alias in node.names)


def _resolve_import(module_name: str, level: int, target: str | None) -> str:
    """Turns a relative import into the absolute module it names"""
    if level == 0:
        return target or ""
    package = module_name.removesuffix(".py").split("/")[:-1]
    anchor = package[: len(package) - (level - 1)]
    return ".".join(anchor + ([target] if target else []))


def _names_used_in(statement: ast.stmt) -> set[str]:
    return {node.id for node in ast.walk(statement) if isinstance(node, ast.Name)}


def _constant_names_assigned_by(statement: ast.stmt) -> list[str]:
    if isinstance(statement, ast.Assign):
        targets = statement.targets
    elif isinstance(statement, ast.AnnAssign):
        targets = [statement.target]
    else:
        return []
    return [
        t.id for t in targets if isinstance(t, ast.Name) and CONSTANT_NAME.match(t.id)
    ]


def _is_method(qualname: str) -> bool:
    return "." in qualname


def _is_dunder(name: str) -> bool:
    return name.startswith("__") and name.endswith("__")


def _is_value(node: FunctionNode) -> bool:
    """Whether a decorator turns the function into a value, which is named as a noun"""
    return any(
        _decorator_name(decorator) in VALUE_DECORATORS
        for decorator in node.decorator_list
    )


def _decorator_name(decorator: ast.expr) -> str:
    target = decorator.func if isinstance(decorator, ast.Call) else decorator
    if isinstance(target, ast.Attribute):
        return target.attr
    return target.id if isinstance(target, ast.Name) else ""


def _starts_with_verb(name: str) -> bool:
    first_word = name.lstrip("_").split("_")[0]
    return first_word in VERBS or first_word == HOOK_PREFIX


def _is_boolean(annotation: ast.expr | None) -> bool:
    return annotation is not None and ast.unparse(annotation) in BOOLEAN_ANNOTATIONS


def _has_boolean_prefix(name: str) -> bool:
    return name.lstrip("_").startswith(BOOLEAN_PREFIXES)


_RULES: dict[str, tuple[Callable[[Module], Iterator[Violation]], bool]] = {
    "verb": (_check_verbs, False),
    "boolean": (_check_booleans, False),
    "constant-position": (_check_constant_positions, False),
    "private-helper-position": (_check_private_helper_positions, False),
    "banner": (_check_banners, True),
    "license-header": (_check_license_header, True),
    "all-strings": (_check_all_strings, False),
    "import-layering": (_check_import_layering, False),
    "confined-import": (_check_confined_imports, False),
    "host-takeover": (_check_host_takeover, False),
    "type-hints": (_check_type_hints, False),
}
