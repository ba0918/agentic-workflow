from __future__ import annotations

from fnmatch import fnmatch
import re
import tokenize
from typing import TYPE_CHECKING

from astroid import nodes
from pylint.checkers import BaseTokenChecker
from pylint.checkers.utils import safe_infer

if TYPE_CHECKING:
    from pylint.lint import PyLinter


SUPPRESSION = re.compile(
    r"#\s*(?:pylint:\s*(?:disable|skip-file)|noqa\b|type:\s*ignore\b|"
    r"pyright:\s*ignore\b|mypy:\s*ignore\b)",
    re.IGNORECASE,
)
TYPE_MODULES = {"typing", "typing_extensions"}
TYPE_ESCAPE_HATCHES = {"Any", "cast"}


class DesignChecker(BaseTokenChecker):
    name = "ba0918-design"
    msgs = {
        "E9001": (
            "Inline lint suppression is forbidden: %s",
            "forbidden-lint-suppression",
            "Fix the violation or the checker configuration instead of bypassing it.",
        ),
        "E9002": (
            "Pure layer cannot import %s",
            "forbidden-layer-import",
            "Keep infrastructure dependencies outside declared pure layers.",
        ),
        "E9003": (
            "Type escape hatch %s is forbidden",
            "forbidden-type-escape-hatch",
            "Model the value precisely instead of bypassing static type checking.",
        ),
        "E9004": (
            "Pure layer cannot call %s directly",
            "forbidden-pure-layer-call",
            "Inject side-effecting operations through a boundary instead.",
        ),
    }
    options = (
        (
            "pure-layer-patterns",
            {
                "type": "csv",
                "default": (),
                "help": "File globs that identify pure domain modules.",
            },
        ),
        (
            "pure-layer-forbidden-imports",
            {
                "type": "csv",
                "default": (),
                "help": "Import roots forbidden from pure domain modules.",
            },
        ),
        (
            "pure-layer-forbidden-calls",
            {
                "type": "csv",
                "default": (),
                "help": "Calls forbidden from pure domain modules.",
            },
        ),
    )

    def process_tokens(self, tokens: list[tokenize.TokenInfo]) -> None:
        for token in tokens:
            if token.type == tokenize.COMMENT and SUPPRESSION.search(token.string):
                self.add_message(
                    "forbidden-lint-suppression",
                    line=token.start[0],
                    col_offset=token.start[1],
                    args=token.string,
                )

    def visit_import(self, node: nodes.Import) -> None:
        for imported, _alias in node.names:
            self._check_layer_import(node, imported)

    def visit_importfrom(self, node: nodes.ImportFrom) -> None:
        if node.modname in TYPE_MODULES:
            for imported, _alias in node.names:
                self._check_type_escape_hatch(node, imported)
        if node.modname:
            self._check_layer_import(node, node.modname)

    def visit_attribute(self, node: nodes.Attribute) -> None:
        if (
            isinstance(node.expr, nodes.Name)
            and node.expr.name in TYPE_MODULES
            and node.attrname in TYPE_ESCAPE_HATCHES
        ):
            self._check_type_escape_hatch(node, node.attrname)

    def visit_call(self, node: nodes.Call) -> None:
        if not self._is_pure_layer(node):
            return
        names = {node.func.as_string()}
        inferred = safe_infer(node.func)
        if inferred is not None and hasattr(inferred, "qname"):
            names.add(inferred.qname())
        forbidden = self.linter.config.pure_layer_forbidden_calls
        matched = next(
            (
                configured
                for configured in forbidden
                if configured in names
                or any(name.endswith(f".{configured}") for name in names)
            ),
            None,
        )
        if matched is not None:
            self.add_message(
                "forbidden-pure-layer-call",
                line=node.fromlineno,
                col_offset=node.col_offset,
                args=matched,
            )

    def _check_type_escape_hatch(self, node: nodes.NodeNG, name: str) -> None:
        if name in TYPE_ESCAPE_HATCHES:
            self.add_message(
                "forbidden-type-escape-hatch",
                line=node.fromlineno,
                col_offset=node.col_offset,
                args=name,
            )

    def _check_layer_import(self, node: nodes.NodeNG, imported: str) -> None:
        forbidden = self.linter.config.pure_layer_forbidden_imports
        if not self._is_pure_layer(node):
            return
        imported_root = imported.split(".", maxsplit=1)[0]
        if imported_root in forbidden:
            self.add_message(
                "forbidden-layer-import",
                line=node.fromlineno,
                col_offset=node.col_offset,
                args=imported_root,
            )

    def _is_pure_layer(self, node: nodes.NodeNG) -> bool:
        module_path = str(node.root().file).replace("\\", "/")
        return any(
            fnmatch(module_path, pattern)
            for pattern in self.linter.config.pure_layer_patterns
        )


def register(linter: PyLinter) -> None:
    linter.register_checker(DesignChecker(linter))
