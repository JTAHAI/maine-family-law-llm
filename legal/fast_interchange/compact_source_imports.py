"""Source-only imports inside the disposable research child, never in the host.

Avoid accepting an ambient .pyc instead of the selected .py.  A caller that has
already verified a read-locked artifact lease can additionally provide a
hash-bound logical source allowlist.  The allowlist is opt-in: it is a narrow
development-runtime integrity control, not native closure or production
admission.
"""

import importlib.machinery

SOURCE_IMPORT_VERSION = "compact_source_only_v1"
SOURCE_ALLOWLIST_VERSION = "compact_source_allowlist_v1"

# Inline before importing application/dependency modules. Importing the installer
# from a mutable directory first would itself permit a cached-bytecode shortcut.
_BOOTSTRAP_SOURCE = """
import hashlib as _compact_hashlib
import importlib.machinery as _compact_machinery
import json as _compact_json
import sys as _compact_sys
from pathlib import Path as _compact_path

_compact_allowlist = None
_compact_policy = 'compact_source_only_v1'

def _compact_logical_path(value):
    path = _compact_path(value).resolve(strict=False)
    roots = (
        (_compact_path(_compact_sys.argv[2]).resolve(strict=False), 'repository'),
        (_compact_path(_compact_sys.argv[1]).resolve(strict=False).parents[1], 'package_runtime'),
        (_compact_path(_compact_sys.base_prefix).resolve(strict=False), 'python_runtime'),
    )
    for root, label in roots:
        try:
            relative = path.relative_to(root).as_posix()
        except ValueError:
            continue
        return label + '/' + relative
    raise ImportError('compact_source_path_unmapped')

def _compact_load_allowlist():
    global _compact_allowlist, _compact_policy
    if len(_compact_sys.argv) == 3:
        return
    if len(_compact_sys.argv) != 5:
        raise ImportError('compact_source_allowlist_arguments_invalid')
    allowlist_path = _compact_path(_compact_sys.argv[3])
    expected = _compact_sys.argv[4]
    if len(expected) != 64 or any(char not in '0123456789abcdef' for char in expected):
        raise ImportError('compact_source_allowlist_hash_invalid')
    raw = allowlist_path.read_bytes()
    if len(raw) > 4 * 1024 * 1024 or _compact_hashlib.sha256(raw).hexdigest() != expected:
        raise ImportError('compact_source_allowlist_integrity_invalid')
    document = _compact_json.loads(raw.decode('utf-8'))
    if (
        set(document) != {'schema_version', 'paths'}
        or document['schema_version'] != 'compact_source_allowlist_v1'
    ):
        raise ImportError('compact_source_allowlist_invalid')
    paths = document['paths']
    if not isinstance(paths, list) or not 1 <= len(paths) <= 32768:
        raise ImportError('compact_source_allowlist_invalid')
    allowed = set()
    for item in paths:
        if not isinstance(item, str) or not item.startswith(
            ('repository/', 'package_runtime/', 'python_runtime/')
        ):
            raise ImportError('compact_source_allowlist_invalid')
        if '\\\\' in item or '..' in item.split('/') or item in allowed:
            raise ImportError('compact_source_allowlist_invalid')
        allowed.add(item)
    _compact_allowlist = allowed
    _compact_policy = 'compact_source_allowlist_v1'

def _compact_assert_selected(path):
    if _compact_allowlist is not None and _compact_logical_path(path) not in _compact_allowlist:
        raise ImportError('compact_source_not_selected')

def _compact_source_code(self, fullname):
    path = self.get_filename(fullname)
    _compact_assert_selected(path)
    return self.source_to_code(self.get_data(path), path)

def _compact_extension_exec(self, module):
    # Some extension modules rewrite ``module.__name__`` while their loader
    # retains the fully qualified name.  The loader identity is the authority
    # for resolving its artifact, not mutable module state.
    _compact_assert_selected(self.get_filename(self.name))
    return _compact_original_extension_exec(self, module)

def _compact_no_bytecode(self, fullname):
    raise ImportError('compact_sourceless_import_forbidden')

_compact_load_allowlist()
_compact_original_extension_exec = _compact_machinery.ExtensionFileLoader.exec_module
_compact_machinery.SourceFileLoader.get_code = _compact_source_code
_compact_machinery.SourcelessFileLoader.get_code = _compact_no_bytecode
_compact_machinery.ExtensionFileLoader.exec_module = _compact_extension_exec
_compact_sys.path[:] = [item for item in _compact_sys.path if not item.lower().endswith('.zip')]
"""

# Inline before importing application/dependency modules. Importing the installer
# from a mutable directory first would itself permit a cached-bytecode shortcut.
SOURCE_ONLY_BOOTSTRAP = "exec(" + repr(_BOOTSTRAP_SOURCE) + ",globals());"


def source_only_active():
    machinery = importlib.machinery
    source = getattr(machinery, "_compact_source_code", None)
    denied = getattr(machinery, "_compact_no_bytecode", None)
    return (
        source is not None
        and denied is not None
        and machinery.SourceFileLoader.get_code is source
        and machinery.SourcelessFileLoader.get_code is denied
    )


def source_import_policy():
    """Return the child-only policy identifier without modifying host imports."""

    return getattr(importlib.machinery, "_compact_policy", SOURCE_IMPORT_VERSION)
