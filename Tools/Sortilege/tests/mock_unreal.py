"""Fake `unreal` module for testing sortilege.py without a running UEFN editor.

This module is injected as ``sys.modules["unreal"]`` by tests/helpers.py. It
reproduces the slice of the UEFN Python editor-scripting API that sortilege.py
depends on, including the semantics that matter for reference-safe moves:

- ``AssetTools.rename_assets`` / ``EditorAssetLibrary.rename_asset`` move an
  asset, rewrite hard references (``deps``) in every asset that referenced the
  old path, and leave an ``ObjectRedirector`` entry at the old path.
- ``find_package_referencers_for_asset`` also finds referencers whose deps
  point at a redirector that (transitively) resolves to the queried path.
- ``save_loaded_asset`` resaving a referencer rewrites any redirector-path
  deps to their final resolved targets (the real "resave to clear a
  redirector" recipe).
- Optional-API surfaces (``EditorDialog``, ``ScopedSlowTask``,
  ``AssetRenameData``, ``EditorUtilityLibrary.get_selected_folder_paths``,
  ``AssetTools.fix_up_redirectors``, ``AssetData.asset_class_path``,
  ``SystemLibrary.collect_garbage``, ``SystemLibrary.get_system_path``,
  ``AssetTools.rename_referencing_soft_object_paths``) are genuinely
  ABSENT (not None) when their feature switch is off, exactly like a UEFN
  build missing that API from its Python whitelist. The tool under test
  gates on these with ``hasattr``.
- ``SystemLibrary.get_system_path(asset)`` derives a fake but realistic
  on-disk path from an asset's package path, rooted under a settable
  module-level fake project disk directory (``set_project_disk_dir()``) --
  models the real UEFN API sortilege.py uses to auto-detect the user's
  actual project directory (see resolve_verse_search_dir() in
  sortilege.py). Gated behind its own "system_path" feature switch
  (default True), independent of "collect_garbage" (which still gates
  whether ``SystemLibrary`` exists on the module at all).
- ``EditorAssetLibrary.rename_asset`` accepts EITHER a package path or a
  full object path ("...Name.Name") for both source and destination, like
  the real API. ``AssetData.is_redirector()``/``.get_asset()`` are always
  present (not feature-gated).
- ``add_asset(path, class_name, deps=, soft_deps=)`` models TWO separate
  reference kinds: ``deps`` (hard-like -- auto-rewritten by a rename,
  resolved by a resave) and ``soft_deps`` (true FSoftObjectPath modeling
  -- never touched by a rename or a plain resave, only by
  ``AssetTools.rename_referencing_soft_object_paths``). ``AssetRegistry.
  get_referencers`` (gated by the "dependency_query" feature switch,
  alongside ``get_dependencies``) sees BOTH; ``EditorAssetLibrary.
  find_package_referencers_for_asset`` only ever sees ``deps`` -- the
  deliberate field-gap Sortilege's conservative redirector-deletion path
  is built to survive.

Stdlib only.
"""
import os
import sys
import tempfile


# ---------------------------------------------------------------------------
# Feature switches
# ---------------------------------------------------------------------------

_DEFAULT_FEATURES = {
    "editor_dialog": True,
    "selected_folders": True,
    "scoped_slow_task": True,
    "fix_up_redirectors": True,
    "asset_rename_data": True,
    "class_paths_filter": True,
    "project_root_api": True,
    "legacy_asset_class_throws": False,
    "collect_garbage": True,
    "soft_path_rename": True,
    "dependency_query": True,
    "system_path": True,
}

_PROTECTED_MOVE_CLASSES = {
    "VerseClass", "World", "Level", "MapBuildDataRegistry",
    "GameFeatureData", "LevelStreaming", "WorldDataLayers", "DataLayerAsset",
}

_state = {}


# ---------------------------------------------------------------------------
# Simple value types
# ---------------------------------------------------------------------------

class Name(str):
    """Mirrors unreal.Name: a str subclass, so str(x) always works."""
    pass


class TopLevelAssetPath:
    """Trivial stand-in for unreal.TopLevelAssetPath -- only .asset_name matters."""

    def __init__(self, class_name):
        self.package_name = Name("/Script/Engine")
        self.asset_name = Name(class_name)

    def __str__(self):
        return str(self.asset_name)


class AssetData:
    def __init__(self, package_name, asset_name, class_name):
        self.package_name = Name(package_name)
        self.asset_name = Name(asset_name)
        self._class_name = Name(class_name)
        if _state.get("features", _DEFAULT_FEATURES)["class_paths_filter"]:
            self.asset_class_path = TopLevelAssetPath(class_name)

    @property
    def asset_class(self):
        """Legacy deprecated field. Real current-build UEFN can throw when
        this is accessed (per UEFN-TOOLBELT's documented trap) -- simulate
        that via the "legacy_asset_class_throws" feature switch so the
        tool's asset_class_path-first fallback chain is testable."""
        if _state.get("features", _DEFAULT_FEATURES).get("legacy_asset_class_throws"):
            raise Exception("AssetData.asset_class is deprecated and disabled on this build")
        return self._class_name

    def is_redirector(self):
        """True for ObjectRedirector entries. Task 4's find_redirectors()
        primary strategy is find_asset_data(p).is_redirector() per item."""
        return str(self._class_name) == "ObjectRedirector"

    def get_asset(self):
        """Mirrors unreal.AssetData.get_asset(): hands back the actual
        object this AssetData describes. For a redirector entry this is
        the redirector object itself (its own package path, NOT resolved
        through the chain) -- exactly what AssetTools.fix_up_redirectors
        expects to receive. Not gated by any feature switch -- always
        present, same as the real engine's AssetData.get_asset()."""
        return FakeAsset(str(self.package_name))


class FakeAsset:
    """What EditorAssetLibrary.load_asset() hands back -- a live handle onto
    a real asset's path (redirectors are resolved before wrapping)."""

    def __init__(self, path):
        self.path = path

    def get_path_name(self):
        return self.path

    def __repr__(self):
        return "FakeAsset(%r)" % (self.path,)


class ARFilter:
    def __init__(self, class_names=None, package_paths=None, recursive_paths=True,
                 class_paths=None):
        self.class_names = list(class_names) if class_names else []
        self.package_paths = list(package_paths) if package_paths else []
        self.recursive_paths = recursive_paths
        self.class_paths = list(class_paths) if class_paths else []


class AppMsgType:
    YES_NO = "YES_NO"


class AppReturnType:
    YES = "YES"
    NO = "NO"


class Paths:
    @staticmethod
    def project_saved_dir():
        return os.path.join(tempfile.gettempdir(), "sortilege_mock_project", "Saved")


# ---------------------------------------------------------------------------
# Internal path helpers
# ---------------------------------------------------------------------------

def _is_under(candidate, base, recursive):
    """True if `candidate` sits inside folder `base` (root = "" or "/")."""
    base_norm = base.rstrip("/") if base else ""
    if candidate == base_norm:
        return False
    if base_norm == "":
        if candidate == "/":
            return False
        if recursive:
            return True
        return candidate.count("/") == 1
    if not candidate.startswith(base_norm + "/"):
        return False
    if recursive:
        return True
    remainder = candidate[len(base_norm) + 1:]
    return "/" not in remainder


def _resolve(path):
    """Follow the redirector chain from `path` to its final real target."""
    seen = set()
    current = path
    while current in _state["redirectors"] and current not in seen:
        seen.add(current)
        current = _state["redirectors"][current]
    return current


def _join_package(package_path, name):
    return package_path.rstrip("/") + "/" + name


def _register_ancestor_folders(path):
    """Register every ancestor folder of `path` (not just its immediate
    parent), so does_directory_exist() answers True for any ancestor of
    registered content -- mirrors the real engine, where an asset deep in
    a folder tree implies every folder above it exists too."""
    parent = path.rsplit("/", 1)[0]
    while parent:
        _state["folders"].add(parent)
        if "/" not in parent[1:]:
            break
        parent = parent.rsplit("/", 1)[0]


def _asset_ref_to_path(asset):
    if isinstance(asset, str):
        return asset
    if hasattr(asset, "path"):
        return asset.path
    if hasattr(asset, "package_name"):
        return str(asset.package_name)
    return str(asset)


def _make_asset_data(path):
    if path in _state["assets"]:
        class_name = _state["assets"][path]["class"]
    elif path in _state["redirectors"]:
        class_name = "ObjectRedirector"
    else:
        return None
    name = path.rsplit("/", 1)[-1]
    return AssetData(path, name, class_name)


def _do_rename(old_path, new_path):
    if old_path not in _state["assets"]:
        return False
    cls = _state["assets"][old_path]["class"]
    if cls in _PROTECTED_MOVE_CLASSES:
        log_error("Cannot move protected asset class %s at %s" % (cls, old_path))
        return False
    if old_path == new_path:
        return False
    if new_path in _state["assets"] or new_path in _state["redirectors"]:
        return False

    data = _state["assets"].pop(old_path)
    _state["assets"][new_path] = data
    for _p, adata in _state["assets"].items():
        adata["deps"] = [new_path if d == old_path else d for d in adata["deps"]]

    _state["redirectors"][old_path] = new_path
    _register_ancestor_folders(new_path)
    return True


# ---------------------------------------------------------------------------
# Log functions (module-level, always present)
# ---------------------------------------------------------------------------

def log(msg):
    line = str(msg)
    _state["log"].append(line)
    print(line)


def log_warning(msg):
    line = "WARNING: " + str(msg)
    _state["log"].append(line)
    print(line)


def log_error(msg):
    line = "ERROR: " + str(msg)
    _state["log"].append(line)
    print(line)


# ---------------------------------------------------------------------------
# EditorAssetLibrary
# ---------------------------------------------------------------------------

class EditorAssetLibrary:
    @staticmethod
    def list_assets(path, recursive=True, include_folder=False):
        results = []
        for p in list(_state["assets"].keys()) + list(_state["redirectors"].keys()):
            if _is_under(p, path, recursive):
                results.append(p)
        if include_folder:
            for f in _state["folders"]:
                if _is_under(f, path, recursive):
                    results.append(f.rstrip("/") + "/")
        return results

    @staticmethod
    def does_asset_exist(path):
        return path in _state["assets"] or path in _state["redirectors"]

    @staticmethod
    def does_directory_exist(path):
        norm = path.rstrip("/")
        if norm in _state["folders"]:
            return True
        for p in list(_state["assets"].keys()) + list(_state["redirectors"].keys()):
            if p.rsplit("/", 1)[0] == norm:
                return True
        return False

    @staticmethod
    def make_directory(path):
        _state["folders"].add(path.rstrip("/"))
        return True

    @staticmethod
    def delete_directory(path):
        """FORCE delete, matching the REAL EditorAssetLibrary.delete_
        directory (empirically confirmed in a live UEFN session): removes
        the folder and EVERYTHING still under it -- assets, redirectors,
        subfolders -- unconditionally, and returns True. The old mock
        refused non-empty deletes, which was SAFER than reality and
        masked a sweep bug (a folder whose only content is an empty
        subfolder read as empty and the force delete took the subfolder
        with it). Every call records exactly what got destroyed in
        _state["force_deleted"] so tests can assert the blast radius."""
        norm = path.rstrip("/")
        destroyed = {"folder": norm, "assets": [], "redirectors": [], "folders": []}
        for p in list(_state["assets"].keys()):
            if _is_under(p, norm, True):
                destroyed["assets"].append(p)
                del _state["assets"][p]
        for p in list(_state["redirectors"].keys()):
            if _is_under(p, norm, True):
                destroyed["redirectors"].append(p)
                del _state["redirectors"][p]
        for f in list(_state["folders"]):
            if f != norm and _is_under(f, norm, True):
                destroyed["folders"].append(f)
                _state["folders"].discard(f)
        _state["folders"].discard(norm)
        _state.setdefault("force_deleted", []).append(destroyed)
        return True

    @staticmethod
    def find_asset_data(path):
        return _make_asset_data(path)

    @staticmethod
    def load_asset(path):
        target = _resolve(path)
        if target in _state["assets"]:
            return FakeAsset(target)
        return None

    @staticmethod
    def rename_asset(src, dst):
        """Accepts EITHER a package path ("/Root/Folder/Name") OR a full
        object path ("/Root/Folder/Name.Name") for both src and dst, like
        the real EditorAssetLibrary.rename_asset (which takes full object
        paths). Asset names can never legally contain "." (validate_asset_
        name() rejects it), so splitting on the first "." unambiguously
        recovers the package path either way."""
        src_pkg = src.split(".", 1)[0] if "." in src else src
        dst_pkg = dst.split(".", 1)[0] if "." in dst else dst
        return _do_rename(src_pkg, dst_pkg)

    @staticmethod
    def delete_asset(path):
        if path in _state["redirectors"]:
            del _state["redirectors"][path]
            return True
        if path in _state["assets"]:
            del _state["assets"][path]
            return True
        return False

    @staticmethod
    def save_loaded_asset(asset, only_if_is_dirty=True):
        """`only_if_is_dirty` is accepted for real-API signature parity
        (the manual redirector-cleanup recipe calls this with
        only_if_is_dirty=False to force a resave). The mock does not
        track a dirty flag, so the resave itself always happens the same
        way regardless of the argument's value."""
        path = _asset_ref_to_path(asset)
        if path not in _state["assets"]:
            return False
        deps = _state["assets"][path]["deps"]
        _state["assets"][path]["deps"] = [_resolve(d) for d in deps]
        _state["saved"].append(path)
        return True

    @staticmethod
    def save_asset(path):
        target = _resolve(path)
        return EditorAssetLibrary.save_loaded_asset(FakeAsset(target))

    @staticmethod
    def find_package_referencers_for_asset(path, load_assets_to_confirm=False):
        """`load_assets_to_confirm` is accepted for real-API signature
        parity; the mock's dependency data is never "unloaded" so it does
        not change the result.

        Two distinct query semantics, matching real-engine behavior:
        - Querying a REAL (non-redirector) path -- e.g. an asset's final
          resolved location -- also surfaces referencers still stuck on
          any redirector that (transitively) resolves here. This is the
          documented "sees refs through the redirector chain" behavior
          the manual cleanup recipe's soft-reference pass relies on.
        - Querying a path that is ITSELF a live redirector only counts a
          referencer whose dep is LITERALLY still that exact redirector
          path. A referencer that already points straight at the final
          target is not blocking THIS redirector's deletion -- it may be
          the reason a *different* (earlier-hop) redirector can't be
          deleted yet, but not this one. Without this distinction, the
          redirector-cleanup recipe could never reach "zero referencers"
          for any asset that's still legitimately used anywhere.

        Deliberately NEVER scans `soft_deps` -- this mirrors the real-
        world field gap this build's redirector cleanup has to defend
        against: find_package_referencers_for_asset() is not a reliable
        index of every SOFT referencer. AssetRegistry.get_referencers()
        (below) is the one query that DOES see `soft_deps`.
        """
        target = _resolve(path)
        if path == target:
            aliases = {target}
            for old in _state["redirectors"]:
                if _resolve(old) == target:
                    aliases.add(old)
        else:
            aliases = {path}
        refs = []
        for p, data in _state["assets"].items():
            if any(d in aliases for d in data["deps"]):
                refs.append(p)
        return refs


# ---------------------------------------------------------------------------
# Asset registry
# ---------------------------------------------------------------------------

class AssetRegistry:
    def get_assets_by_path(self, path, recursive=True):
        results = []
        for p in list(_state["assets"].keys()) + list(_state["redirectors"].keys()):
            if _is_under(p, path, recursive):
                results.append(_make_asset_data(p))
        return results

    def get_assets(self, ar_filter):
        class_names = set(getattr(ar_filter, "class_names", None) or [])
        class_paths = getattr(ar_filter, "class_paths", None) or []
        package_paths = getattr(ar_filter, "package_paths", None) or []
        recursive_paths = getattr(ar_filter, "recursive_paths", True)

        if _state["features"]["class_paths_filter"]:
            for cp in class_paths:
                name = getattr(cp, "asset_name", None)
                class_names.add(str(name) if name is not None else str(cp))

        if package_paths:
            candidates = []
            seen = set()
            for pp in package_paths:
                for ad in self.get_assets_by_path(pp, recursive_paths):
                    key = str(ad.package_name)
                    if key not in seen:
                        seen.add(key)
                        candidates.append(ad)
        else:
            candidates = self.get_assets_by_path("/", True)

        if not class_names:
            return candidates
        return [ad for ad in candidates if str(ad.asset_class) in class_names]


class _AssetRegistryDependencyOptionsImpl:
    """Mirrors unreal.AssetRegistryDependencyOptions -- the options bag
    registry.get_dependencies() takes. Only the two kwargs Sortilege
    passes are modeled; extras are accepted and ignored, like the real
    struct's many other fields. Behind the "dependency_query" feature
    switch (default True) together with AssetRegistry.get_dependencies."""

    def __init__(self, include_hard_package_references=True,
                 include_soft_package_references=True, **kwargs):
        self.include_hard_package_references = include_hard_package_references
        self.include_soft_package_references = include_soft_package_references


def _get_dependencies_impl(self, package_name, options):
    """Mirrors unreal.AssetRegistry.get_dependencies(package_name,
    dependency_options): returns the package names this asset depends on,
    derived from the mock's existing per-asset deps graph (the same
    `deps=` lists add_asset() records and rename_asset() rewrites).
    Returned in insertion order and as Name objects -- callers are
    expected to str() and sort them, exactly like the real registry gives
    no useful ordering guarantee."""
    asset = _state["assets"].get(str(package_name))
    if asset is None:
        return []
    return [Name(dep) for dep in asset.get("deps", [])]


def _get_referencers_impl(self, package_name, options=None):
    """Mirrors unreal.AssetRegistry.get_referencers(package_name,
    reference_options) -- the reverse of get_dependencies(): every
    package that references the supplied one. THE feature-gap query:
    unlike EditorAssetLibrary.find_package_referencers_for_asset(), this
    scans BOTH `deps` (hard-reference-like) AND `soft_deps` (true soft-
    object-path modeling -- see add_asset()) when the options ask for
    each kind, via the same include_hard_package_references /
    include_soft_package_references flags get_dependencies() takes.

    Same alias-resolution rule as find_package_referencers_for_asset:
    querying a real (resolved) path also counts every redirector alias
    that chains to it; querying a redirector path itself only counts a
    referencer whose dep/soft_dep is LITERALLY that exact redirector
    path. Returned as Name objects, like get_dependencies()."""
    path = str(package_name)
    target = _resolve(path)
    if path == target:
        aliases = {target}
        for old in _state["redirectors"]:
            if _resolve(old) == target:
                aliases.add(old)
    else:
        aliases = {path}

    include_hard = getattr(options, "include_hard_package_references", True) \
        if options is not None else True
    include_soft = getattr(options, "include_soft_package_references", True) \
        if options is not None else True

    refs = []
    for p, data in _state["assets"].items():
        hit = include_hard and any(d in aliases for d in data.get("deps", []))
        if not hit and include_soft:
            hit = any(d in aliases for d in data.get("soft_deps", []))
        if hit:
            refs.append(Name(p))
    return refs


_registry_singleton = AssetRegistry()


class AssetRegistryHelpers:
    @staticmethod
    def get_asset_registry():
        return _registry_singleton


# ---------------------------------------------------------------------------
# Asset tools
# ---------------------------------------------------------------------------

class AssetTools:
    def rename_assets(self, rename_data_list):
        overall = True
        for rd in rename_data_list:
            old_path = _asset_ref_to_path(rd.asset)
            new_path = _join_package(rd.new_package_path, rd.new_name)
            if not _do_rename(old_path, new_path):
                overall = False
        return overall


def _fix_up_redirectors_impl(self, redirector_objects):
    fixed = []
    for obj in redirector_objects:
        old_path = _asset_ref_to_path(obj)
        if old_path not in _state["redirectors"]:
            continue
        refs = EditorAssetLibrary.find_package_referencers_for_asset(old_path)
        for ref in refs:
            EditorAssetLibrary.save_loaded_asset(FakeAsset(ref))
        del _state["redirectors"][old_path]
        fixed.append(old_path)
    return fixed


def _rename_referencing_soft_object_paths_impl(self, packages, asset_redirector_map):
    """Mirrors unreal.AssetTools.rename_referencing_soft_object_paths --
    records the call (packages checked + the old->new map) so tests can
    assert fix_soft_references() built the right arguments, AND actually
    rewrites matching `soft_deps` entries in every package handed in, so
    the comprehensive-rewrite fix (P1) is assertable end-to-end: a
    package that owns a stale soft_deps entry ends up pointing at the new
    path IF (and only if) it's in `packages` -- exactly like the real
    API, which only touches FSoftObjectPath fields (never the hard
    `deps` a rename/resave already fixes) in the packages it's told to
    check. Behind the "soft_path_rename" feature switch; a genuine no-op
    with the method entirely absent when that feature is off."""
    _state.setdefault("soft_rename_calls", []).append(
        {"packages": list(packages), "map": dict(asset_redirector_map)}
    )
    pkg_map = {}
    for old_obj, new_obj in asset_redirector_map.items():
        old_pkg = old_obj.split(".", 1)[0] if "." in old_obj else old_obj
        new_pkg = new_obj.split(".", 1)[0] if "." in new_obj else new_obj
        pkg_map[old_pkg] = new_pkg
    for pkg in packages:
        asset_entry = _state["assets"].get(pkg)
        if asset_entry is None:
            continue
        soft_deps = asset_entry.get("soft_deps")
        if not soft_deps:
            continue
        asset_entry["soft_deps"] = [pkg_map.get(d, d) for d in soft_deps]
    return True


_asset_tools_singleton = AssetTools()


class AssetToolsHelpers:
    @staticmethod
    def get_asset_tools():
        return _asset_tools_singleton


# ---------------------------------------------------------------------------
# Editor utility library (selected folders)
# ---------------------------------------------------------------------------

class EditorUtilityLibrary:
    pass


def _get_selected_folder_paths_impl():
    return list(_state["selected_folders"])


# ---------------------------------------------------------------------------
# Feature-gated implementations (attached/detached by reset())
# ---------------------------------------------------------------------------

class _EditorDialogImpl:
    @staticmethod
    def show_message(title, message, message_type, default_value=None):
        _state["log"].append("dialog: %s - %s" % (title, message))
        if _state["dialog_answers"]:
            answer = _state["dialog_answers"].pop(0)
        else:
            answer = default_value if default_value is not None else "No"
        if str(answer) == "Yes":
            return AppReturnType.YES
        return AppReturnType.NO


class _ScopedSlowTaskImpl:
    def __init__(self, steps, desc=""):
        self.steps = steps
        self.desc = desc

    def __enter__(self):
        _state["log"].append("ScopedSlowTask enter: %s" % self.desc)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        _state["log"].append("ScopedSlowTask exit: %s" % self.desc)
        return False

    def make_dialog(self):
        _state.setdefault("slow_task_calls", []).append("make_dialog")

    def enter_progress_frame(self, n=1, msg=""):
        _state.setdefault("slow_task_calls", []).append(("enter_progress_frame", n, msg))


class _AssetRenameDataImpl:
    def __init__(self, asset, new_package_path, new_name):
        self.asset = asset
        self.new_package_path = new_package_path
        self.new_name = new_name


def _get_project_root_asset_directory_impl():
    """Mirrors unreal.EditorAssetLibrary.get_project_root_asset_directory():
    returns "/<ProjectName>/" in UEFN ("/Game/" only for .uproject
    fallback), trailing slash included like the real API."""
    root = _state.get("project_root", "/Game")
    return root.rstrip("/") + "/"


class _SystemLibraryImpl:
    """Mirrors the slice of unreal.SystemLibrary Sortilege uses:
    collect_garbage(). Gated behind the "collect_garbage" feature switch
    (default True) -- when off, `unreal.SystemLibrary` is absent entirely,
    same as every other optional-capability class in this mock. Note this
    intentionally does NOT define get_project_saved_directory(): that
    absence is what exercises resolve_log_dir()'s fall-through to
    unreal.Paths.project_saved_dir() in tests/test_preview_logs.py. Also
    intentionally never defines get_project_directory() -- resolve_verse_
    search_dir()'s own fall-through chain in test_verse_references.py
    depends on that absence too.

    get_system_path() is attached separately, gated by its OWN
    "system_path" feature switch (see _apply_feature_gates) -- independent
    of "collect_garbage" so a test can turn one off without the other."""

    @staticmethod
    def collect_garbage():
        _state["gc_calls"] = _state.get("gc_calls", 0) + 1


def _get_system_path_impl(obj):
    """Mirrors unreal.SystemLibrary.get_system_path(): given an asset
    object (as EditorAssetLibrary.load_asset() returns -- a FakeAsset
    whose `.path` is its resolved package path), derive a fake but
    realistic on-disk path rooted under the settable module-level fake
    project disk directory (see set_project_disk_dir()) -- e.g. package
    "/Game/Textures/T_Foo" -> "<root>/Content/Textures/T_Foo.uasset". The
    mount segment (the package path's first segment -- "Game" above) is
    always replaced by "Content", exactly like a real UEFN/UE project's
    disk layout. Gated behind the "system_path" feature switch (default
    True, independent of "collect_garbage")."""
    path = _asset_ref_to_path(obj)
    pkg = path.split(".", 1)[0] if "." in path else path
    segments = [p for p in pkg.split("/") if p]
    remainder = segments[1:]
    disk_root = _state.get("project_disk_dir") or os.path.join(
        tempfile.gettempdir(), "MockProj")
    return os.path.join(disk_root, "Content", *remainder) + ".uasset"


def _gate_module_attr(name, impl, enabled):
    this_module = sys.modules[__name__]
    if enabled:
        setattr(this_module, name, impl)
    elif hasattr(this_module, name):
        delattr(this_module, name)


def _gate_class_attr(cls, name, impl, enabled):
    if enabled:
        setattr(cls, name, impl)
    elif name in cls.__dict__:
        delattr(cls, name)


def _apply_feature_gates(features):
    _gate_module_attr("EditorDialog", _EditorDialogImpl, features["editor_dialog"])
    _gate_module_attr("ScopedSlowTask", _ScopedSlowTaskImpl, features["scoped_slow_task"])
    _gate_module_attr("AssetRenameData", _AssetRenameDataImpl, features["asset_rename_data"])
    _gate_class_attr(EditorUtilityLibrary, "get_selected_folder_paths",
                      staticmethod(_get_selected_folder_paths_impl), features["selected_folders"])
    _gate_class_attr(AssetTools, "fix_up_redirectors", _fix_up_redirectors_impl,
                      features["fix_up_redirectors"])
    _gate_class_attr(EditorAssetLibrary, "get_project_root_asset_directory",
                      staticmethod(_get_project_root_asset_directory_impl),
                      features["project_root_api"])
    _gate_module_attr("SystemLibrary", _SystemLibraryImpl, features["collect_garbage"])
    _gate_class_attr(_SystemLibraryImpl, "get_system_path",
                      staticmethod(_get_system_path_impl), features["system_path"])
    _gate_class_attr(AssetTools, "rename_referencing_soft_object_paths",
                      _rename_referencing_soft_object_paths_impl,
                      features["soft_path_rename"])
    _gate_module_attr("AssetRegistryDependencyOptions",
                       _AssetRegistryDependencyOptionsImpl,
                       features["dependency_query"])
    _gate_class_attr(AssetRegistry, "get_dependencies",
                      _get_dependencies_impl, features["dependency_query"])
    _gate_class_attr(AssetRegistry, "get_referencers",
                      _get_referencers_impl, features["dependency_query"])


# ---------------------------------------------------------------------------
# Public mock-control API
# ---------------------------------------------------------------------------

def reset(features=None):
    """Wipe the fake project state. `features` overrides the default (all-on)
    optional-API switches; anything not mentioned keeps its default."""
    global _state
    merged = dict(_DEFAULT_FEATURES)
    if features:
        merged.update(features)
    _state = {
        "assets": {},
        "folders": set(),
        "redirectors": {},
        "saved": [],
        "dialog_answers": [],
        "log": [],
        "selected_folders": [],
        "features": merged,
        "project_root": "/Game",
        "gc_calls": 0,
        "soft_rename_calls": [],
        "force_deleted": [],
        "project_disk_dir": os.path.join(tempfile.gettempdir(), "MockProj"),
    }
    _apply_feature_gates(merged)


def add_asset(path, class_name, deps=None, soft_deps=None):
    """`deps` models HARD-reference-like dependencies: rewritten
    immediately (everywhere) by rename_asset()/_do_rename() and resolved
    by save_loaded_asset(), same as always. `soft_deps` models a TRUE
    FSoftObjectPath reference: a plain string a rename never touches and
    a plain resave never resolves -- the only thing that ever rewrites it
    is AssetTools.rename_referencing_soft_object_paths(), and the only
    thing that ever SEES it as a referencer is AssetRegistry.
    get_referencers() (with include_soft_package_references=True);
    EditorAssetLibrary.find_package_referencers_for_asset() never looks
    at it. This is the deliberate field-gap Sortilege's conservative
    redirector-deletion check (CONSERVATIVE_REDIRECTORS) exists to
    survive: a referencer registered ONLY via `soft_deps` is exactly the
    kind find_package_referencers_for_asset can miss."""
    _state["assets"][path] = {
        "class": class_name,
        "deps": list(deps) if deps else [],
        "soft_deps": list(soft_deps) if soft_deps else [],
    }
    _register_ancestor_folders(path)


def add_folder(path):
    _state["folders"].add(path.rstrip("/"))


def get_state():
    return _state


def set_dialog_answer(answer):
    _state["dialog_answers"].append(answer)


def set_selected_folders(paths):
    _state["selected_folders"] = list(paths)


def set_project_root(path):
    """Set the mock project's root content mount, e.g. "/ProjectX". Read
    back via EditorAssetLibrary.get_project_root_asset_directory()."""
    _state["project_root"] = path.rstrip("/") if path else "/Game"


def set_project_disk_dir(path):
    """Set the mock's fake project disk root -- what unreal.SystemLibrary.
    get_system_path() derives every fake on-disk asset path from (see
    _get_system_path_impl()). Defaults to a "MockProj" folder under the
    system temp dir (see reset())."""
    _state["project_disk_dir"] = path


# Initialize a valid default state as soon as the module is imported, so the
# mock is usable even if a caller forgets to call reset() first.
reset()
