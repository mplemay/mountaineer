from abc import ABC, abstractmethod
from dataclasses import dataclass
from importlib.metadata import version
from pathlib import Path
from typing import Generator

from mountaineer.client_builder.parser import ControllerWrapper
from mountaineer.paths import ManagedViewPath


@dataclass
class ParsedController:
    """Represents a fully parsed controller with its associated paths and metadata"""

    wrapper: ControllerWrapper
    view_path: ManagedViewPath
    url_prefix: str | None = None
    is_layout: bool = False


class FileGeneratorBase(ABC):
    def __init__(self, *, managed_path: Path):
        self.managed_path = managed_path

        mountaineer_version = version("mountaineer")
        self.standard_header = CodeBlock(
            "/*",
            f" * This file was generated by Mountaineer v{mountaineer_version}. Do not edit it manually.",
            " */",
        )

    def build(self):
        blocks = list(self.script())
        blocks = [self.standard_header] + blocks
        self.managed_path.write_text("\n\n".join(block.content for block in blocks))

    @abstractmethod
    def script(self) -> Generator["CodeBlock", None, None]:
        pass


class CodeBlock:
    """
    Semantic grouping of a particular section of code, typically separated
    from other ones with two blank lines.

    """

    def __init__(self, *lines: str):
        self.lines = lines

    @classmethod
    def indent(cls, line: str):
        """
        Use the first line of the code block to determine the indentation level
        for the other lines that are implicitly imbedded in this line. This most
        acutely covers cases where string templating includes newlines so we can
        preserve the overall layout.

        ie. CodeBlock.indent(f"  my_var = {my_var}\n")

        """
        if not line or "\n" not in line:
            return line

        has_trailing_newline = line.endswith("\n")
        lines = line[:-1].split("\n") if has_trailing_newline else line.split("\n")

        # Get the base indentation from first line
        base_indent, _ = cls._get_indent_level(lines[0])

        # Process all lines
        result: list[str] = []
        result.append(lines[0])  # First line remains unchanged

        # Add base indentation to subsequent lines while preserving their own
        for current_line in lines[1:]:
            if current_line.strip():  # If line has content
                result.append(base_indent + current_line)
            else:  # Preserve empty or whitespace-only lines as-is
                result.append(current_line)

        return "\n".join(result) + ("\n" if has_trailing_newline else "")

    @classmethod
    def _get_indent_level(cls, line: str) -> tuple[str, int]:
        """
        Get the indentation string and count from the start of a line.
        Returns tuple of (indent_str, indent_count).
        """
        indent_str = ""
        for char in line:
            if char not in (" ", "\t"):
                break
            indent_str += char
        return indent_str, len(indent_str)

    @property
    def content(self):
        return "\n".join(self.lines)
