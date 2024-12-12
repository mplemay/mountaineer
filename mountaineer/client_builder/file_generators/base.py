class CodeBlock:
    """
    Semantic grouping of a particular section of code, typically separated
    from other ones with two blank lines.

    """
    def __init__(self, lines: list[str]):
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
        if not line or '\n' not in line:
            return line

        has_trailing_newline = line.endswith('\n')
        lines = line[:-1].split('\n') if has_trailing_newline else line.split('\n')

        # Get the base indentation from first line
        base_indent, _ = cls._get_indent_level(lines[0])

        # Process all lines
        result : list[str] = []
        result.append(lines[0])  # First line remains unchanged

        # Add base indentation to subsequent lines while preserving their own
        for current_line in lines[1:]:
            if current_line.strip():  # If line has content
                result.append(base_indent + current_line)
            else:  # Preserve empty or whitespace-only lines as-is
                result.append(current_line)

        return '\n'.join(result) + ('\n' if has_trailing_newline else '')

    @classmethod
    def _get_indent_level(cls, line: str) -> tuple[str, int]:
        """
        Get the indentation string and count from the start of a line.
        Returns tuple of (indent_str, indent_count).
        """
        indent_str = ''
        for char in line:
            if char not in (' ', '\t'):
                break
            indent_str += char
        return indent_str, len(indent_str)
