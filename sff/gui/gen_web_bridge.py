"""Generate web_bridge.py from web_bridge_backup.py and bridge modules.

Reads web_bridge_backup.py, replaces each @pyqtSlot method body with
a single-line delegation to the corresponding bridge function,
then writes web_bridge.py. Shared helpers and signals are preserved.
"""
import re
from pathlib import Path

BACKUP = Path(__file__).parent / "web_bridge_backup.py"
OUTPUT = Path(__file__).parent / "web_bridge.py"
BRIDGES = Path(__file__).parent / "bridges"

# Build mapping from bridge files: method_name -> (func_name, bridge_stem)
mapping: dict[str, tuple[str, str]] = {}
for bf in BRIDGES.glob("*.py"):
    if bf.name == "__init__.py":
        continue
    content = bf.read_text(encoding="utf-8")
    for m in re.finditer(r"^def (_bridge_\w+)\(bridge", content, re.MULTILINE):
        func_name = m.group(1)
        # _bridge_validate_game_files -> validate_game_files
        method_name = func_name[8:]  # strip _bridge_ prefix
        mapping[method_name] = (func_name, bf.stem)

# Also look for methods called from __init__ like _prefetch_installed_games
# and _preload_all_store_data which reference bridge objects
extra_method_map = {
    # Methods that call into bridge functions
    "refresh_library": ("_bridge_refresh_library", "misc_bridge"),
    "load_library": ("_bridge_load_library", "misc_bridge"),
    "get_installed_games": ("_bridge_get_game_list", "misc_bridge"),    # no direct bridge, uses internal
}

# Map from bridge functions that use bridge.xxx methods that need to stay
# For example: _bridge_refresh_library calls bridge.load_library()
# which itself is a @pyqtSlot. So refresh_library's bridge also needs to
# call bridge.load_library() through its bridge delegate.

# Read backup
with open(BACKUP, "r", encoding="utf-8") as f:
    text = f.read()

# Find all @pyqtSlot method definitions
# Pattern: @pyqtSlot(...)\n    def method_name(self, ...):
slot_pattern = re.compile(
    r"((?:    @pyqtSlot[^\n]*\n)+)"
    r"(    def )(\w+)(\(self[^)]*\):)"
)

def _find_method_end(text: str, start: int) -> int:
    """Return the offset of the line that begins the *next* class-level
    definition (``def`` or ``@`` at indent 4).  The replacement will
    extend from ``start`` up to (but not including) that boundary line,
    preserving the next method's decorators and signature.

    Falls back to module-level ``def`` / end of file when no more
    class-level definitions follow.
    """
    rest = text[start:]
    if not rest:
        return start
    lines = rest.split("\n")

    for i, raw in enumerate(lines):
        stripped = raw.rstrip()
        if stripped == "":
            continue
        # Count leading spaces: a class-level line has exactly 4 spaces
        # of indent (class body is at 4, method body at 8, etc.).
        indent = len(raw) - len(raw.lstrip())
        ch = stripped.lstrip()[0]
        # Comments inside a method don't count as boundaries.
        if ch == "#":
            continue
        # Any line at indent 4 (class body) that starts with ``@`` or
        # ``def`` signals the next method / helper.  Lines at indent 0
        # that start with ``def`` mark the end of the class and
        # the beginning of module-level functions — stop there too.
        if indent <= 4 and (ch == "@" or ch == "d"):
            if ch == "d" and not raw.lstrip().startswith("def "):
                continue
            offset = sum(len(l) + 1 for l in lines[:i])
            return start + offset

    return start + len(rest)

replacements = []
for m in slot_pattern.finditer(text):
    decorators = m.group(1)
    def_kw = m.group(2)
    method_name = m.group(3)
    params = m.group(4)
    
    if method_name not in mapping:
        continue
    
    func_name, bridge_module = mapping[method_name]
    
    # Find the method body end  
    body_start = m.start()
    body_end = _find_method_end(text, m.end())
    
    # Build replacement: extract parameter names from the signature
    sig = params[1:]  # remove leading (
    
    # Parse parameter list, handling result=str
    param_str = sig
    has_result_type = False
    if ", result" in sig:
        idx = sig.index(", result")
        has_result_type = True
        param_str = sig[:idx]
    
    # Remove leading "self" and trailing ":" and close paren
    # sig is like "self, query, offset, per_page, sort_by, tag, request_id):"
    if param_str.startswith("self"):
        param_str = param_str[4:]  # remove "self"
    
    # Remove trailing "):"
    param_str = param_str.rstrip("):")
    
    # Build the call arguments
    arg_names = [p.strip().split(":")[0].strip() for p in param_str.split(",") if p.strip()]
    # Also handle when a param has a default like sort_by='updated'
    arg_names = [a.split("=")[0].strip() for a in arg_names]
    
    if arg_names:
        call = f"        return _bridge_{method_name}(self, {', '.join(arg_names)})\n"
    else:
        call = f"        return _bridge_{method_name}(self)\n"
    
    new_body = f"{decorators}{def_kw}{method_name}(self{param_str}{', result=str' if has_result_type else ''}):\n{call}"
    
    # Rewrite the full method block
    old_full = text[body_start:body_end]
    replacements.append((body_start, body_end, new_body))

# Apply replacements in reverse order to preserve offsets
for start, end, new in sorted(replacements, reverse=True):
    text = text[:start] + new + text[end:]

# Build the bridge import block - grouped by module
from collections import OrderedDict
module_imports: dict[str, list[str]] = OrderedDict()
for method_name, (func_name, bridge_module) in sorted(mapping.items()):
    module_imports.setdefault(bridge_module, []).append(f"_bridge_{method_name}")

import_lines = []
for module_name in sorted(module_imports.keys()):
    funcs = module_imports[module_name]
    if len(funcs) <= 5:
        import_lines.append(f"from sff.gui.bridges.{module_name} import {', '.join(funcs)}")
    else:
        # Multi-line import for long lists
        import_lines.append(f"from sff.gui.bridges.{module_name} import (")
        for f in funcs:
            import_lines.append(f"    {f},")
        import_lines[-1] = import_lines[-1].rstrip(",")  # Remove trailing comma on last
        import_lines.append(")")

bridge_imports = "\n".join(import_lines)

# Insert imports after the original imports block but before _SSL_CTX = None
# Find the insertion point: after the last import from the initial block
lines = text.split("\n")
insert_at = None
for i, line in enumerate(lines):
    if line.strip() == "logger = logging.getLogger(__name__)":
        # Next line after logger definition
        insert_at = i + 1
        break

if insert_at is not None:
    lines.insert(insert_at, "")
    lines.insert(insert_at + 1, "")
    lines.insert(insert_at + 2, "# Bridge module imports — thin delegates to domain-specific bridge files")
    # Insert each import line individually
    for line in reversed(bridge_imports.split("\n")):
        lines.insert(insert_at + 2, line)
    lines.insert(insert_at + 2, "")

with open(OUTPUT, "w", encoding="utf-8") as f:
    f.write("\n".join(lines))

print(f"Generated web_bridge.py with {len(replacements)} delegated methods")
for mn, (fn, bm) in sorted(mapping.items()):
    print(f"  {mn} -> {bm}.{fn}")
