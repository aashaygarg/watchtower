"""Architecture fitness test: the frozen dependency rules, enforced.

Watchtower is a hexagon. The domain and ports are the inward rings; the kernel is
the intellectual property; adapters are the replaceable outer ring; ``bootstrap``
is the composition root. This test parses every module's imports and fails the
build if an inward ring reaches outward.

Only *runtime* imports are checked - imports inside ``if TYPE_CHECKING:`` blocks
are erased at runtime and create no coupling, so annotation-only references (for
example a port's return type) are allowed. What the architecture forbids is a
real runtime dependency from the kernel or ports onto an adapter, a provider SDK,
a web/DB framework, or the composition root.
"""

from __future__ import annotations

import ast
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path

_PACKAGE_ROOT = Path(__file__).resolve().parent.parent / "watchtower"

_FORBIDDEN_FRAMEWORKS = frozenset(
    {
        "openai",
        "anthropic",
        "ollama",
        "google",
        "litellm",
        "langgraph",
        "langchain",
        "faiss",
        "flask",
        "fastapi",
        "sqlalchemy",
        "psycopg",
        "sqlite3",
        "peewee",
        "yaml",
        "pyyaml",
    }
)


def _module_files(package: str) -> Iterator[Path]:
    yield from sorted((_PACKAGE_ROOT / package).rglob("*.py"))


def _is_type_checking(test: ast.expr) -> bool:
    if isinstance(test, ast.Name):
        return test.id == "TYPE_CHECKING"
    if isinstance(test, ast.Attribute):
        return test.attr == "TYPE_CHECKING"
    return False


def _collect(node: ast.AST, imports: set[str]) -> None:
    for child in ast.iter_child_nodes(node):
        if isinstance(child, ast.If) and _is_type_checking(child.test):
            for sub in child.orelse:  # keep the else branch; skip the TYPE_CHECKING body
                _collect(sub, imports)
            continue
        if isinstance(child, ast.Import):
            imports.update(alias.name for alias in child.names)
        elif isinstance(child, ast.ImportFrom) and child.module and child.level == 0:
            imports.add(child.module)
        _collect(child, imports)


def _runtime_imports(path: Path) -> set[str]:
    """Return modules imported at runtime (outside ``if TYPE_CHECKING`` blocks)."""
    imports: set[str] = set()
    _collect(ast.parse(path.read_text(encoding="utf-8")), imports)
    return imports


def _is_framework(module: str) -> bool:
    return module.split(".", 1)[0] in _FORBIDDEN_FRAMEWORKS


def test_kernel_never_reaches_outward() -> None:
    violations = [
        (path.relative_to(_PACKAGE_ROOT), module)
        for path in _module_files("kernel")
        for module in _runtime_imports(path)
        if module.startswith("watchtower.adapters")
        or module == "watchtower.bootstrap"
        or _is_framework(module)
    ]
    assert not violations, f"kernel reached outward at runtime: {violations}"


def test_ports_import_only_domain() -> None:
    violations = [
        (path.relative_to(_PACKAGE_ROOT), module)
        for path in _module_files("ports")
        for module in _runtime_imports(path)
        if (module.startswith("watchtower.") and not module.startswith("watchtower.domain"))
        or _is_framework(module)
    ]
    assert not violations, f"a port imported outside the domain at runtime: {violations}"


def test_inner_rings_never_import_the_composition_root() -> None:
    violations = [
        path.relative_to(_PACKAGE_ROOT)
        for package in ("domain", "ports", "kernel", "adapters")
        for path in _module_files(package)
        if "watchtower.bootstrap" in _runtime_imports(path)
    ]
    assert not violations, f"an inner ring imported the composition root: {violations}"


# Third-party packages the kernel must never pull in - not even transitively
# through a first-party import. Extends the framework list with the YAML/file
# loader and the UI toolkits that live strictly in the outer rings.
_RUNTIME_FORBIDDEN = frozenset({*_FORBIDDEN_FRAMEWORKS, "typer", "rich", "httpx"})


def _kernel_module_names() -> list[str]:
    names: list[str] = []
    for path in _module_files("kernel"):
        if path.name == "__init__.py":
            continue
        rel = path.relative_to(_PACKAGE_ROOT).with_suffix("")
        names.append("watchtower." + rel.as_posix().replace("/", "."))
    return names


def test_kernel_pulls_in_no_framework_at_runtime() -> None:
    """Importing the kernel must not load any adapter/framework, even transitively.

    The static tests above see only each module's own import statements. This one
    imports every kernel module in a fresh interpreter and asserts that no
    forbidden third-party package (an SDK, a web/DB framework, a YAML/file
    loader, or a UI toolkit) ended up in ``sys.modules`` - the failure mode where
    the kernel reaches an adapter by importing a first-party module that itself
    imports one (for example a value object fused into a YAML loader).
    """
    modules = _kernel_module_names()
    forbidden = sorted(_RUNTIME_FORBIDDEN)
    code = (
        "import importlib, sys\n"
        f"for name in {modules!r}:\n"
        "    importlib.import_module(name)\n"
        f"roots = set({forbidden!r})\n"
        "leaked = sorted(m for m in sys.modules if m.split('.')[0] in roots)\n"
        "print(';'.join(leaked))\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        check=True,
    )
    leaked = [m for m in result.stdout.strip().split(";") if m]
    assert not leaked, f"importing the kernel pulled in forbidden packages: {leaked}"
