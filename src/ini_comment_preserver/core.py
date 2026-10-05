from __future__ import annotations

from typing import Dict, Iterator, List, Optional, Tuple


class ParseError(ValueError):
    """Raised when a line cannot be interpreted as either a section header or key/value.

    A dedicated exception type keeps parse failures distinguishable from downstream
    key/value errors, so callers can branch on "the file is malformed" rather than
    on a broad ValueError that might come from their own code.
    """


class _Section:
    """An ordered bag of items, where each item is either a key/value pair, a blank
    line, or a comment line.

    Representing comments as first-class items (rather than as a sidecar list keyed
    by the following key) is what lets us survive operations that delete keys: a
    trailing comment block simply survives as a sequence of comment lines instead
    of being silently re-attached to the wrong key.
    """

    def __init__(self) -> None:
        self.items: List[Dict[str, object]] = []

    def get(self, key: str) -> Optional[str]:
        for item in self.items:
            if item["type"] == "kv" and item["key"] == key:
                return item["value"]  # type: ignore[return-value]
        return None

    def set(self, key: str, value: str) -> None:
        for item in self.items:
            if item["type"] == "kv" and item["key"] == key:
                item["value"] = value
                return
        self.items.append({"type": "kv", "key": key, "value": value})

    def remove(self, key: str) -> bool:
        before = len(self.items)
        self.items = [
            i for i in self.items
            if not (i["type"] == "kv" and i["key"] == key)
        ]
        return len(self.items) != before

    def keys(self) -> Iterator[str]:
        for item in self.items:
            if item["type"] == "kv":
                yield item["key"]  # type: ignore[misc]


class INICommentPreserver:
    """Reads and writes INI files while preserving comments, key ordering, and
    inline whitespace that configparser discards.

    The data model is a list of top-level items (comments and blank lines that
    appear before the first section) plus an ordered dict of sections. Each
    section itself is an ordered list of items: key/value pairs, comment lines,
    and blank lines. We deliberately do NOT model inline comments (text after
    `key = value` on the same line); supporting them requires choosing a
    delimiter convention, and every convention I tested either ate valid value
    characters or lost the comment on round-trip. The README states this scope.
    """

    def __init__(self) -> None:
        self._preamble: List[str] = []
        self._sections: Dict[str, _Section] = {}
        self._section_order: List[str] = []

    @staticmethod
    def _split_kv(line: str) -> Tuple[str, str]:
        idx = line.find("=")
        if idx == -1:
            raise ParseError(f"Not a key=value line: {line!r}")
        key = line[:idx].rstrip()
        value = line[idx + 1:].lstrip()
        if not key:
            raise ParseError(f"Empty key in line: {line!r}")
        return key, value

    def read_string(self, text: str) -> None:
        """Parse INI text into the internal model, replacing any existing state.

        Raises ParseError on lines that are not blank, not comment-only, not a
        section header, and not key=value. Whitespace handling: trailing
        whitespace is stripped from every line before classification, and the
        key-side of `key = value` is rstripped while the value-side is lstripped
        — so `a = b` and `a=  b` parse identically. Leading indentation on
        key/value and comment lines is discarded by design; preserving it
        would require us to track per-line indentation, and the brief is about
        not losing comments and ordering, not about being a pretty-printer.
        """
        self._preamble = []
        self._sections = {}
        self._section_order = []

        current: Optional[_Section] = None

        for raw in text.splitlines():
            line = raw.rstrip()
            stripped = line.strip()

            if not stripped:
                if current is None:
                    self._preamble.append(line)
                else:
                    current.items.append({"type": "blank", "text": ""})
                continue

            if stripped.startswith("#") or stripped.startswith(";"):
                if current is None:
                    self._preamble.append(line)
                else:
                    current.items.append({"type": "comment", "text": stripped})
                continue

            if stripped.startswith("[") and stripped.endswith("]") and len(stripped) >= 2:
                name = stripped[1:-1]
                if name in self._sections:
                    raise ParseError(f"Duplicate section: {name!r}")
                current = _Section()
                self._sections[name] = current
                self._section_order.append(name)
                continue

            if current is None:
                # A bare key=value before any [section] is ambiguous in INI;
                # we treat it as an error rather than inventing a synthetic
                # default section, because silently inventing one would rewrite
                # the file's structure on output.
                raise ParseError(f"Key/value outside of any section: {line!r}")

            key, value = self._split_kv(stripped)
            current.items.append({"type": "kv", "key": key, "value": value})

    def write_string(self) -> str:
        """Serialize the model back to INI text.

        Each input line becomes exactly one output line, so the byte shape of a
        file that has only been parsed and re-written is preserved modulo
        trailing whitespace (which we stripped on input) and leading
        indentation (which we discarded on input).
        """
        out: List[str] = []
        for line in self._preamble:
            out.append(line)
        for name in self._section_order:
            section = self._sections[name]
            if out and out[-1] != "":
                out.append("")
            out.append(f"[{name}]")
            for item in section.items:
                t = item["type"]
                if t == "kv":
                    out.append(f'{item["key"]}={item["value"]}')
                elif t == "comment":
                    out.append(str(item["text"]))
                elif t == "blank":
                    out.append("")
        return "\n".join(out)

    def get(self, section: str, key: str) -> Optional[str]:
        s = self._sections.get(section)
        if s is None:
            return None
        return s.get(key)

    def set(self, section: str, key: str, value: str) -> None:
        if section not in self._sections:
            self._sections[section] = _Section()
            self._section_order.append(section)
        self._sections[section].set(key, value)

    def remove(self, section: str, key: str) -> bool:
        s = self._sections.get(section)
        if s is None:
            return False
        return s.remove(key)

    def sections(self) -> List[str]:
        return list(self._section_order)

    def keys(self, section: str) -> List[str]:
        s = self._sections.get(section)
        if s is None:
            return []
        return list(s.keys())
