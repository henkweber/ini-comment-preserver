# INI Comment Preserver

Reads and writes INI files while preserving full-line comments, key ordering, and inline whitespace that `configparser` discards.

```python
from ini_comment_preserver import INICommentPreserver

p = INICommentPreserver()
p.read_string("[server]\nhost = localhost\n")
print(p.get("server", "host"))   # 'localhost' or None
p.set("server", "port", "9090")
p.remove("server", "debug")
print(p.write_string())
```

Exported names: `INICommentPreserver`, `ParseError`. Methods: `read_string(text)`, `write_string() -> str`, `get(section, key) -> str | None`, `set(section, key, value)`, `remove(section, key) -> bool`, `sections() -> list[str]`, `keys(section) -> list[str]`.

## Why

`configparser` is a fine reader but a lossy one: it drops comments and reorders keys. If you use it to read a config, modify one value, and write it back, you hand the user back a file with all their annotations gone. This library keeps each line — whether comment, blank, or key/value — as an item in an ordered list, so a parse-modify-serialize round trip is near-identity (modulo trailing whitespace, which is stripped on input).

The trade-off: we parse less than a full INI grammar. No inline comments (`k = v # note`), no multi-line values, no interpolation. Supporting inline comments in particular requires picking a delimiter convention, and every convention I tried either ate valid value characters or failed to survive a round trip. The simpler scope is stated plainly rather than silently producing wrong output.

## Awkward edges

- `key = value # not a comment` is kept literally; the `#` is part of the value. If you want inline comments, strip them yourself before `set`.
- Leading indentation on key/value and comment lines is discarded. `  host = x` and `host = x` parse identically and both emit as `host=x`.
- A key/value line appearing before any `[section]` raises `ParseError` rather than being silently assigned to a synthetic default section.
- `read_string` replaces all existing state; calling it twice does not merge.

## Performance

The window keeps a bounded buffer, so `push` is constant time and memory does not
grow with the length of the stream. `peak` and `trough` are linear in the window
size, which is the trade that keeps `push` cheap.

