"""Sortilege

A single-file UEFN Python editor tool that scans a project's Content
Drawer, classifies every asset by type, and sorts assets into a standard
folder structure using reference-safe move APIs. Dry-run preview is the
default; a deliberate confirm is required before anything is changed.
Redirectors left behind by moves are auto-cleaned on a best-effort basis,
every run is logged, and an undo log lets you reverse a completed run.

Usage (from the UEFN Output Log, in Cmd mode -- not the Python console):
    py "C:/path/to/sortilege.py" [preview|apply|undo|probe]

    preview (default) - scan, classify, print a dry-run plan, write it to
                         a JSON file. Never changes anything.
    apply             - same as preview, then executes the plan if
                         I_UNDERSTAND_THIS_MODIFIES_MY_PROJECT is True
                         below (and, if available, a Yes/No dialog).
    undo              - reverse the moves recorded in the most recent
                         undo log (or a path given as the next argument).
    probe             - print a read-only capability + environment
                         report. Never changes anything.

Credit: mangoUEFN.
License: Apache 2.0 + Commons Clause.
"""

# =====================================================================
# === CONFIG - EDIT ME ===
# =====================================================================
# Everything in this section is safe to change by hand -- no coding
# knowledge required. Save the file and re-run the script after any
# change here.

CONFIG = {
    # Which folder each category of asset gets sorted into, as a folder
    # name under the sort root (see SORT_ROOT below). Change the name on
    # the right to rename a destination folder; it is created if missing.
    "FOLDER_MAP": {
        "Meshes": "Meshes", "Materials": "Materials", "Textures": "Textures",
        "Audio": "Audio", "Animations": "Animations", "Props": "Props",
        "UI": "UI", "VFX": "VFX", "Other": "Other",
    },
    # Which category each engine asset type belongs to. Add a line here
    # if you use an asset type that is not listed; unlisted types fall
    # back to "Other" (or get skipped entirely if STRICT_MODE is True).
    "CLASSIFICATION": {
        "StaticMesh": "Meshes", "SkeletalMesh": "Meshes",
        "Material": "Materials", "MaterialInstanceConstant": "Materials",
        "MaterialFunction": "Materials", "MaterialParameterCollection": "Materials",
        "Texture2D": "Textures", "TextureCube": "Textures", "TextureRenderTarget2D": "Textures",
        "SoundWave": "Audio", "SoundCue": "Audio", "SoundClass": "Audio",
        "SoundAttenuation": "Audio", "MetaSoundSource": "Audio",
        "AnimSequence": "Animations", "AnimMontage": "Animations",
        "AnimBlueprint": "Animations", "BlendSpace": "Animations",
        "Skeleton": "Animations", "PhysicsAsset": "Animations",
        "Blueprint": "Props", "LevelSequence": "Props",
        "WidgetBlueprint": "UI", "Font": "UI", "FontFace": "UI",
        "NiagaraSystem": "VFX", "NiagaraEmitter": "VFX", "ParticleSystem": "VFX",
    },
    # Bonus feature: rename files to match a prefix convention (SM_, M_,
    # T_, ...) whenever ENABLE_PREFIX_RENAME below is True. Ignored
    # otherwise. Add a line here to teach it a new class -> prefix.
    "PREFIX_MAP": {
        "StaticMesh": "SM_", "SkeletalMesh": "SK_", "Material": "M_",
        "MaterialInstanceConstant": "MI_", "MaterialFunction": "MF_",
        "Texture2D": "T_", "TextureCube": "TC_", "SoundWave": "S_",
        "SoundCue": "SC_", "AnimSequence": "A_", "AnimMontage": "AM_",
        "AnimBlueprint": "ABP_", "Blueprint": "BP_", "WidgetBlueprint": "WBP_",
        "NiagaraSystem": "NS_", "Skeleton": "SKEL_", "PhysicsAsset": "PHYS_",
        "LevelSequence": "LS_", "BlendSpace": "BS_",
    },
    # "" = sort straight into folders at the content root. Set this to a
    # name like "_Organized" to nest all sorted folders under one parent
    # instead, leaving whatever else you have at the root untouched.
    "SORT_ROOT": "",
    # False = flat per-type sorting (the default): every mesh to Meshes,
    # every texture to Textures, and so on. True = keep each asset's KIT
    # together instead: a prop's mesh, its materials, and their textures
    # all live under one folder named after the prop, nested along the
    # dependency chain (see README, "Keeping kits together"). Needs a
    # dependency-lookup API; builds without it fall back to flat sorting
    # automatically (a note is printed when that happens).
    "GROUP_BY_ASSET": False,
    # Which asset types can OWN a kit, in priority order: the first type
    # in this list that matches wins, so a mesh referenced by a Blueprint
    # belongs to the Blueprint's kit rather than starting its own.
    "GROUP_ANCHOR_CLASSES": [
        "Blueprint", "WidgetBlueprint", "NiagaraSystem", "SkeletalMesh",
        "StaticMesh", "LevelSequence",
    ],
    # Where things used by TWO OR MORE kits go (they belong to no single
    # kit): a folder with this name at the sort root, with the usual
    # per-type subfolders inside it.
    "GROUP_SHARED_FOLDER": "Shared",
    # [] = scan the whole project. Or list specific folders to limit the
    # scan to, e.g. ["/YourProject/OldStuff"].
    "SCOPE_FOLDERS": [],
    # True = scope to whatever folder(s) are selected in the Content
    # Browser when you run the script. Only works if your UEFN build
    # supports reading the selection; falls back to SCOPE_FOLDERS above
    # when it does not. Experimental -- see README.
    "USE_SELECTION": False,
    # Extra folders that should never be touched, on top of the built-in
    # protections (Verse, levels/maps, __ExternalActors__, etc).
    "EXCLUDE_FOLDERS": [],
    # True = also rename files to match the PREFIX_MAP convention above.
    "ENABLE_PREFIX_RENAME": False,
    # True = try to clean up leftover redirectors after moving assets.
    "CLEAN_REDIRECTORS": True,
    # Safety net for the line above: True (recommended, default) = before
    # actually deleting a redirector, ALSO double-check the asset
    # registry's own get_referencers() (hard+soft references) when this
    # build exposes it, on top of the existing find_package_referencers_
    # for_asset check. Research/field report: find_package_referencers_
    # for_asset does not reliably report every SOFT reference on every
    # UEFN build, which let a still-soft-referenced redirector get
    # deleted in a live sort (breaking that reference the instant the
    # redirector was gone: "soft references a missing package"). When
    # either check reports a referencer, either one raises, or get_
    # referencers is simply unavailable on this build (no way to double-
    # check at all), the redirector is KEPT instead of deleted -- left
    # behind and reported in the run summary, but never a broken
    # reference. Set to False to go back to the old single-check
    # criterion (find_package_referencers_for_asset only).
    "CONSERVATIVE_REDIRECTORS": True,
    # True = double-check the result after applying (recommended).
    "VERIFY_AFTER": True,
    # True = after applying (or undoing), remove folders the moves left
    # completely empty -- including parent folders that empty out once
    # their children go. Folders still holding ANYTHING (assets,
    # subfolders, leftover redirectors) are kept and listed in the run
    # report. Set this to False to keep every folder exactly as it is.
    "CLEAN_EMPTY_FOLDERS": True,
    # True = skip asset types that are not listed in CLASSIFICATION
    # instead of sending them to the "Other" folder.
    "STRICT_MODE": False,
    # "" = pick a log folder automatically (your project's Saved folder
    # if it can be found, otherwise the folder this script lives in).
    "LOG_DIR": "",
    # True = show an interactive preview window (recommended) when you run
    # this script with no argument (or "preview"). It shows the same scan
    # results as the console, lets you tweak folder mappings live and
    # re-scan, and gates apply behind an in-window checkbox instead of
    # editing this file. Automatically falls back to the console-only
    # flow below if this UEFN build's Python can't open the window for
    # any reason. Set this to False (non-coders: change True to False
    # above) to always use the console-only flow.
    "USE_GUI": True,
    # Crash-diagnostics switch. True = an apply (or undo) only MOVES the
    # assets -- every optional pass after that (soft-reference fixup,
    # redirector cleanup, empty-folder sweep) and every collect_garbage()
    # call are skipped. Use this to narrow down which stage of a
    # crash-prone run is actually responsible: run once with this True,
    # then flip the individual switches below back on one at a time.
    # Verify still runs afterward (it only reads, never writes) unless
    # VERIFY_AFTER above is also False. Leave this False for normal use.
    "SAFE_MODE": False,
    # Crash-diagnostics switch. True = every collect_garbage() call is
    # skipped, independent of SAFE_MODE above -- use this to test whether
    # garbage collection itself is the crash cause without also turning
    # off the redirector/soft-reference/empty-folder passes. SAFE_MODE
    # already skips these regardless of this setting. Leave this False
    # for normal use.
    "DISABLE_GC": False,
    # True = best-effort fix-up of FSoftObjectPath references to moved
    # assets after an apply (only actually does anything on builds that
    # support it). Set to False to skip just this one pass without
    # turning on full SAFE_MODE above (which forces it off regardless).
    "FIX_SOFT_REFERENCES": True,
    # True = after moving an asset your Verse code references by its
    # folder-qualified name (Asset Reflection -- see the README's
    # "Fixing Verse references" section), rewrite that reference in your
    # real .verse source files so the qualified name matches the asset's
    # new location. Off = leave every .verse file exactly as it is (the
    # caution about updating Verse code by hand still applies). Python
    # cannot compile Verse -- always run Build Verse Code in UEFN
    # afterward to confirm your project still compiles.
    "FIX_VERSE_REFERENCES": True,
    # True = also rewrite a BARE root-level Verse reference (a plain name
    # with no folder qualification at all, like "T_Hex" -- see the
    # README's "Fixing Verse references" section). A bare name is a
    # plain word with nothing to distinguish it from an unrelated
    # identifier that merely happens to match, so it is always flagged
    # "(bare name - review)" in the preview either way. Set this to
    # False to SKIP bare-name rewrites entirely (they are listed in the
    # preview/report as "skipped (bare name - fix manually)" instead, so
    # you know to handle those by hand) while still rewriting every
    # qualified (dotted) reference automatically -- the common,
    # provably-safe case this feature exists for. Ignored when
    # FIX_VERSE_REFERENCES above is False.
    "FIX_VERSE_BARE_NAMES": True,
    # "" = auto-detect this project's real directory from a scanned
    # asset's on-disk path (unreal.SystemLibrary.get_system_path()) and
    # look for .verse source files there. Deliberately NOT unreal.Paths.
    # project_dir() by default -- in UEFN that call resolves to the
    # Fortnite ENGINE directory, not your project, which used to make this
    # feature silently scan the wrong folder and find zero real edits. Set
    # this to a specific folder path (your project's folder, the one
    # containing your .uefnproject) to skip auto-detection and search
    # there instead.
    "VERSE_SEARCH_DIR": "",
    # The deliberate safety switch. Leave this False to only ever preview
    # what would happen -- nothing is changed. Set it to True (and
    # re-run) when you are ready to actually move things. See README.md
    # for the full walkthrough, including the confirm dialog.
    "I_UNDERSTAND_THIS_MODIFIES_MY_PROJECT": False,
}


# =====================================================================
# === IMPORTS ===
# =====================================================================
# `unreal` only exists inside UEFN's embedded Python. Wrapped so this
# file still imports cleanly (and CONFIG above is still usable) even
# when run outside the editor, e.g. by a plain syntax check.

try:
    import unreal
except ImportError:
    unreal = None
    print("Sortilege: could not import 'unreal'. This script only runs "
          "inside UEFN's embedded Python (enable Project Settings > "
          "Plugins > Python Editor Script Plugin, then run it from the "
          "Output Log in Cmd mode: py \"path/to/sortilege.py\").")

import datetime
import json
import os
import re
import shutil
import sys


# =====================================================================
# === PROTECTED ASSETS ===
# =====================================================================
# These are never touched, no matter what the config above says, and
# every skip is logged with the reason below.

PROTECTED_CATEGORIES = {
    # "VerseClass" is a best-guess protected class name pending live-probe
    # confirmation against a real UEFN build -- kept alongside the
    # defensive "any class name containing 'Verse'" net in classify()
    # below, so whatever the real engine's actual Verse-linked class
    # name(s) turn out to be, they still get caught and protected.
    "VerseClass": (
        "Verse-linked asset (moving it can break Verse code references; "
        "Verse source is not rewritten by asset-move APIs)"
    ),
    "World": "Level/map (moving can break the island)",
    "Level": "Level/map (moving can break the island)",
    "ObjectRedirector": "redirector (handled by cleanup pass)",
}

# NEVER_MOVE: structural project assets that must NEVER be moved, no
# matter what -- checked FIRST inside classify(), before PROTECTED_
# CATEGORIES, the CLASSIFICATION table, grouping, or STRICT_MODE's
# "Other" fallback, in BOTH flat and group-by-asset sorting modes. A
# field-reported live UEFN apply moved the project's GameFeatureData
# asset and broke the project ("Project 'X' is broken because it's
# missing its GameFeatureData"), leaving broken references behind --
# this is the fix. Exact class names research-confirmed (Epic's own
# Python/API docs, 2026-07-23): UGameFeatureData -> "GameFeatureData"
# (a UPrimaryDataAsset subclass); UMapBuildDataRegistry ->
# "MapBuildDataRegistry" (a UObject subclass, one per level, holds its
# precomputed lighting/reflection data); AWorldDataLayers ->
# "WorldDataLayers" (unreal.WorldDataLayers is a real Python-exposed
# class) and UDataLayerAsset -> "DataLayerAsset" (World Partition's data
# layers). "World"/"Level" (UWorld/ULevel) were already protected above.
NEVER_MOVE_CLASSES = {
    "World", "Level", "MapBuildDataRegistry", "GameFeatureData",
    "LevelStreaming", "WorldDataLayers", "DataLayerAsset",
}

NEVER_MOVE_REASON = (
    "structural project asset (GameFeatureData/Level/Verse) - moving it "
    "breaks the project, kept in place"
)

# Case-insensitive substring net -- same defensive idea as the pre-
# existing "any class name containing 'Verse'" net below, extended to
# GameFeatureData/World-Partition: catches subclasses or build-specific
# variants whose exact class name could not be enumerated in advance (a
# future "UEFNGameFeatureDataOverride" or "VerseDevice"-style type).
# Deliberately does NOT include "level" as a bare substring -- that would
# wrongly catch LevelSequence, a normal, safe Props asset that must keep
# moving; only the exact "Level"/"LevelStreaming" names above are
# protected by name.
NEVER_MOVE_SUBSTRINGS = ("verse", "gamefeature", "worldpartition")


def _never_move_reason(class_name):
    """Return the NEVER_MOVE skip reason if `class_name` is a structural
    project asset that must never be moved, else None. This is checked
    FIRST inside classify() -- before PROTECTED_CATEGORIES, the
    CLASSIFICATION table, and STRICT_MODE -- so both build_plan()'s
    per-asset loop and _compute_group_plan()'s eligibility filter honor
    it identically in flat and group-by-asset modes: an asset this
    returns a reason for can never anchor a kit nor be pulled into
    another kit's dependency closure, because _compute_group_plan()
    excludes it from `eligible` up front, before any anchor/closure
    computation runs."""
    if class_name in NEVER_MOVE_CLASSES:
        return NEVER_MOVE_REASON
    lowered = class_name.lower()
    for substr in NEVER_MOVE_SUBSTRINGS:
        if substr in lowered:
            return NEVER_MOVE_REASON
    return None


# Path segments that mark a system/protected location (One-File-Per-Actor
# data and similar engine-managed folders); never reorganized.
_PROTECTED_PATH_MARKERS = ("__ExternalActors__", "__ExternalObjects__")


def is_protected_path(path):
    """True if `path` sits inside a system-managed folder that must never
    be touched: __ExternalActors__/__ExternalObjects__ (OFPA data) or any
    folder segment starting with a double underscore."""
    for marker in _PROTECTED_PATH_MARKERS:
        if marker in path:
            return True
    for segment in path.split("/"):
        if segment.startswith("__"):
            return True
    return False


_ILLEGAL_NAME_CHARS = "\\/:*?\"<>|"


def validate_asset_name(name):
    """Return None if `name` is a safe asset name to rename to, else a
    skip reason. Unreal's rename APIs throw validation errors on periods
    and the usual filesystem-illegal characters; leading/trailing
    whitespace is never an intentional name."""
    if not name:
        return "invalid target name"
    if name != name.strip():
        return "invalid target name"
    if "." in name:
        return "invalid target name"
    for ch in name:
        if ch in _ILLEGAL_NAME_CHARS:
            return "invalid target name"
    return None


# =====================================================================
# === CAPABILITY PROBE ===
# =====================================================================
# Different UEFN builds whitelist different slices of the Python API.
# The core set this tool assumes is always present: EditorAssetLibrary,
# AssetRegistryHelpers, AssetToolsHelpers. Everything else is probed once
# here with hasattr/getattr, wrapped in try/except, and gated at the call
# site -- never assumed.

class Capabilities:
    """Bag of booleans describing what this UEFN build's Python API
    actually supports. Build one with probe_capabilities(); do not
    construct by hand."""

    def __init__(self):
        self.editor_dialog = False
        self.selected_folders = False
        self.path_view_folders = False
        self.scoped_slow_task = False
        self.fix_up_redirectors = False
        self.class_paths_filter = False
        self.project_root_api = False
        self.soft_path_rename = False
        self.collect_garbage = False
        self.dependency_query = False
        self.referencer_query = False

    def report(self):
        """Printable lines for probe mode and the summary log."""
        names = (
            "editor_dialog", "selected_folders", "path_view_folders",
            "scoped_slow_task", "fix_up_redirectors", "class_paths_filter",
            "project_root_api", "soft_path_rename", "collect_garbage",
            "dependency_query", "referencer_query",
        )
        lines = ["Sortilege capability probe:"]
        for name in names:
            value = getattr(self, name, False)
            lines.append("  %-20s %s" % (name, "yes" if value else "no"))
        return lines


def probe_capabilities():
    """Probe the live (or mock) `unreal` module for every optional API
    Sortilege can use, and return a Capabilities instance. Every single
    check is wrapped in its own try/except so one odd build can't crash
    the probe -- a failed check just reads as "not available"."""
    caps = Capabilities()
    if unreal is None:
        return caps

    try:
        caps.editor_dialog = hasattr(unreal, "EditorDialog")
    except Exception:
        caps.editor_dialog = False

    try:
        caps.selected_folders = (
            hasattr(unreal, "EditorUtilityLibrary")
            and hasattr(unreal.EditorUtilityLibrary, "get_selected_folder_paths")
        )
    except Exception:
        caps.selected_folders = False

    try:
        caps.path_view_folders = (
            hasattr(unreal, "EditorUtilityLibrary")
            and hasattr(unreal.EditorUtilityLibrary, "get_selected_path_view_folder_paths")
        )
    except Exception:
        caps.path_view_folders = False

    try:
        caps.scoped_slow_task = hasattr(unreal, "ScopedSlowTask")
    except Exception:
        caps.scoped_slow_task = False

    try:
        tools = unreal.AssetToolsHelpers.get_asset_tools()
        caps.fix_up_redirectors = hasattr(tools, "fix_up_redirectors")
    except Exception:
        caps.fix_up_redirectors = False

    try:
        caps.class_paths_filter = hasattr(unreal, "TopLevelAssetPath")
    except Exception:
        caps.class_paths_filter = False

    try:
        caps.project_root_api = hasattr(unreal.EditorAssetLibrary, "get_project_root_asset_directory")
    except Exception:
        caps.project_root_api = False

    try:
        tools = unreal.AssetToolsHelpers.get_asset_tools()
        caps.soft_path_rename = hasattr(tools, "rename_referencing_soft_object_paths")
    except Exception:
        caps.soft_path_rename = False

    try:
        caps.collect_garbage = (
            hasattr(unreal, "SystemLibrary")
            and hasattr(unreal.SystemLibrary, "collect_garbage")
        )
    except Exception:
        caps.collect_garbage = False

    try:
        registry = unreal.AssetRegistryHelpers.get_asset_registry()
        caps.dependency_query = (
            hasattr(registry, "get_dependencies")
            and hasattr(unreal, "AssetRegistryDependencyOptions")
        )
    except Exception:
        caps.dependency_query = False

    try:
        registry = unreal.AssetRegistryHelpers.get_asset_registry()
        caps.referencer_query = (
            hasattr(registry, "get_referencers")
            and hasattr(unreal, "AssetRegistryDependencyOptions")
        )
    except Exception:
        caps.referencer_query = False

    return caps


# =====================================================================
# === SCAN ===
# =====================================================================

def discover_content_roots():
    """Return the top-level content mount(s) for this project, e.g.
    ["/MyProject"] in UEFN, or ["/Game"] for a .uproject-style project.
    Never hardcode "/Game/" anywhere else in this file -- always call
    this and use its result.

    Primary (research-confirmed): unreal.EditorAssetLibrary.
    get_project_root_asset_directory(). Falls back to scanning the
    registry's top-level mounts when that API is unavailable."""
    if unreal is None:
        return []

    lib = unreal.EditorAssetLibrary
    if hasattr(lib, "get_project_root_asset_directory"):
        try:
            raw = lib.get_project_root_asset_directory()
            root = "/" + str(raw).strip("/")
            if root and root != "/":
                return [root]
        except Exception:
            pass

    try:
        entries = lib.list_assets("/", recursive=False, include_folder=True)
    except Exception:
        entries = []

    mounts = []
    seen = set()
    for entry in entries:
        top = str(entry).rstrip("/")
        if not top.startswith("/"):
            continue
        segments = top.split("/")
        if len(segments) < 2 or not segments[1]:
            continue
        if segments[1] in ("Engine", "Script"):
            continue
        if segments[1].startswith("__"):
            continue
        mount = "/" + segments[1]
        if mount not in seen:
            seen.add(mount)
            mounts.append(mount)

    if "/Game" in mounts:
        return ["/Game"]
    return mounts


def scan_assets(scope_folders):
    """Scan the asset registry and return a flat list of dicts:
    {"path", "name", "folder", "class_name"}. `scope_folders` limits the
    scan to those folders; pass an empty list to scan every discovered
    content root.

    Deprecated-field trap (research-confirmed via UEFN-TOOLBELT):
    AssetData.object_path and .asset_class are deprecated and can throw
    inside current builds. object_path is never touched. class_name
    comes from asset_class_path.asset_name first (its own try/except),
    falling back to the legacy asset_class (its own try/except), else
    the literal string "Unknown". Everything is str()'d defensively."""
    if unreal is None:
        return []

    registry = unreal.AssetRegistryHelpers.get_asset_registry()
    folders = list(scope_folders) if scope_folders else discover_content_roots()

    results = []
    seen_paths = set()
    for folder in folders:
        try:
            asset_datas = registry.get_assets_by_path(folder, recursive=True)
        except Exception:
            asset_datas = []

        for asset_data in asset_datas:
            try:
                path = str(asset_data.package_name)
            except Exception:
                continue
            if not path or path in seen_paths:
                continue
            seen_paths.add(path)

            try:
                name = str(asset_data.asset_name)
            except Exception:
                name = path.rsplit("/", 1)[-1]

            folder_of_asset = path.rsplit("/", 1)[0] if "/" in path else ""

            try:
                class_name = str(asset_data.asset_class_path.asset_name)
            except Exception:
                try:
                    class_name = str(asset_data.asset_class)
                except Exception:
                    class_name = "Unknown"

            results.append({
                "path": path,
                "name": name,
                "folder": folder_of_asset,
                "class_name": class_name,
            })

    return results


# =====================================================================
# === CLASSIFY ===
# =====================================================================

def classify(class_name, config):
    """Return (category, None) if `class_name` should be sorted, else
    (None, skip_reason). Checks NEVER_MOVE first (structural project
    assets -- GameFeatureData/Level/World/MapBuildDataRegistry/Verse --
    see _never_move_reason()), then PROTECTED_CATEGORIES, then a
    defensive "contains Verse" net, then the editable CLASSIFICATION
    table, then STRICT_MODE vs. "Other". NEVER_MOVE is checked before
    everything else, including STRICT_MODE, so it can never be bypassed
    by any config combination."""
    never_move = _never_move_reason(class_name)
    if never_move:
        return None, never_move

    if class_name in PROTECTED_CATEGORIES:
        return None, PROTECTED_CATEGORIES[class_name]

    # Defensive net: PROTECTED_CATEGORIES's "VerseClass" entry is a
    # best-guess pending live-probe confirmation of the real engine's
    # actual Verse-linked class name(s). Any class name that merely
    # CONTAINS "Verse" (case-insensitive) is treated the same protected
    # way, so whatever the real name turns out to be, it is still caught.
    if "verse" in class_name.lower():
        return None, PROTECTED_CATEGORIES["VerseClass"]

    classification = config.get("CLASSIFICATION", {})
    if class_name in classification:
        return classification[class_name], None

    if config.get("STRICT_MODE", False):
        return None, "unknown class (STRICT_MODE)"

    return "Other", None


# =====================================================================
# === PLAN BUILDER ===
# =====================================================================

def _dest_folder(content_root, sort_root, folder_name):
    parts = [content_root.rstrip("/")]
    if sort_root:
        parts.append(sort_root.strip("/"))
    parts.append(folder_name)
    return "/".join(parts)


def _is_excluded(path, exclude_folders):
    for raw in exclude_folders:
        excl = str(raw).rstrip("/")
        if not excl:
            continue
        if path == excl or path.startswith(excl + "/"):
            return True
    return False


def _compute_new_name(name, class_name, config):
    """Apply the ENABLE_PREFIX_RENAME convention. Returns
    (new_name, needs_rename). Only adds the correct prefix when it is
    genuinely absent; if a *different* known prefix is present (e.g.
    "T_Rock" on a StaticMesh), that wrong prefix is stripped first so the
    result is "SM_Rock", not "SM_T_Rock"."""
    if not config.get("ENABLE_PREFIX_RENAME", False):
        return name, False

    prefix_map = config.get("PREFIX_MAP", {})
    correct_prefix = prefix_map.get(class_name)
    if not correct_prefix:
        return name, False

    if name.startswith(correct_prefix):
        return name, False

    stripped = name
    known_prefixes = sorted(set(prefix_map.values()), key=len, reverse=True)
    for other_prefix in known_prefixes:
        if other_prefix != correct_prefix and name.startswith(other_prefix):
            stripped = name[len(other_prefix):]
            break

    new_name = correct_prefix + stripped
    return new_name, (new_name != name)


# --- Group-by-asset (dependency clustering) ------------------------------
# Real-world grounding: imported props are KITS -- a mesh plus its
# material instance(s) plus their textures (e.g. SM_Alessio +
# MI_Bone_Alessio + T_Bone_Position/Rotation/Weights), times ~90 kits in a
# real project. Flat per-type sorting scatters every kit across /Meshes,
# /Materials, /Textures. When CONFIG["GROUP_BY_ASSET"] is on (and this
# build's registry exposes a dependency-query API -- caps.dependency_
# query), build_plan() keeps each kit together instead, chain-nested:
# a member's destination nests along its dependency path from the kit's
# anchor, each hop appending that node's type folder, consecutive
# same-type hops collapsed. Assets shared by 2+ kits go to a flat
# GROUP_SHARED_FOLDER (they have no single owning chain); assets in no
# kit sort flat exactly as before.

def _kit_name(name, class_name, prefix_map):
    """Kit folder name for an anchor: the anchor's asset name with its
    own class's PREFIX_MAP prefix stripped when present (SM_Alessio ->
    Alessio, BP_LuckyBlock -> LuckyBlock). Falls back to the full name
    when there is no prefix to strip or stripping would leave nothing."""
    prefix = prefix_map.get(class_name)
    if prefix and name.startswith(prefix) and len(name) > len(prefix):
        return name[len(prefix):]
    return name


def _dependency_scan(anchor_path, eligible_paths, boundary_paths=None):
    """BFS the dependency graph out from `anchor_path`, restricted to
    `eligible_paths` (scanned project assets that passed every skip rule
    -- engine/script paths and protected/excluded assets are never
    traversed or collected). Returns {member_path: [path nodes]} where
    the node list is the member's dependency path from the anchor (first
    hop first, ending with the member itself, anchor excluded).

    `boundary_paths` are KIT BOUNDARIES: assets that belong to their own
    kit (anchors of the same or higher priority class than this scan's
    anchor -- see _compute_group_plan). Reaching one neither absorbs it
    nor traverses through it; it and its subtree stay with its own kit.

    Shortest path wins by construction (BFS), with ties broken by
    discovery order over SORTED dependency lists -- deterministic run to
    run. A visited set makes dependency cycles terminate; the anchor
    itself can never become its own member. Every registry call is
    fail-soft: an exception just means that node contributes no further
    dependencies."""
    if unreal is None:
        return {}
    try:
        registry = unreal.AssetRegistryHelpers.get_asset_registry()
    except Exception:
        return {}
    try:
        options = unreal.AssetRegistryDependencyOptions(
            include_hard_package_references=True,
            include_soft_package_references=True)
    except Exception:
        try:
            options = unreal.AssetRegistryDependencyOptions()
        except Exception:
            return {}

    parents = {}
    visited = set([anchor_path])
    queue = [anchor_path]
    while queue:
        current = queue.pop(0)
        try:
            deps = registry.get_dependencies(current, options)
        except Exception:
            deps = []
        for dep_path in sorted(str(d) for d in (deps or [])):
            if dep_path in visited:
                continue
            visited.add(dep_path)
            if dep_path not in eligible_paths:
                # Not a movable scanned asset (engine path, protected,
                # excluded, unscanned): never in a kit, never traversed
                # THROUGH either -- its own dependencies belong to it.
                continue
            if boundary_paths is not None and dep_path in boundary_paths:
                # Kit boundary: another anchor's territory. Not absorbed,
                # not traversed through -- its subtree is its own kit's.
                continue
            parents[dep_path] = current
            queue.append(dep_path)

    members = {}
    for member in parents:
        nodes = []
        cursor = member
        while cursor != anchor_path:
            nodes.append(cursor)
            cursor = parents[cursor]
        nodes.reverse()
        members[member] = nodes
    return members


def _compute_group_plan(assets, config, content_root_norm, all_roots_norm):
    """The grouping pass: decide a destination-folder override for every
    asset that belongs to a kit. Returns (overrides, stats) where
    `overrides` maps asset path -> dest folder (assets absent from it
    sort flat, exactly as without grouping) and `stats` is {"kits": N,
    "shared": M, "loose": K} for the preview header.

    Skip rules are applied FIRST: an asset that is protected, excluded,
    outside every content root, or of a protected class is not eligible
    -- it never anchors a kit, never joins one, and keeps its normal skip
    reason in the main build_plan() loop.

    Anchors are chosen in GROUP_ANCHOR_CLASSES priority order, iterating
    candidates in sorted(asset path) order (never scan order) so results
    are deterministic run to run. An asset already claimed by a
    higher-priority anchor's dependency closure can not anchor its own
    kit (a StaticMesh referenced by a Blueprint is part of the
    Blueprint's kit). Anchor-to-anchor edges at the SAME or HIGHER
    priority are kit boundaries instead: BFS neither absorbs the other
    anchor nor traverses through it -- it (and its subtree) belongs to
    its own kit, so a Blueprint depending on another Blueprint yields
    two real kits, identically regardless of scan order. An accepted
    anchor's own destination is final; member routing can never
    overwrite it. Members reachable from 2+ accepted anchors are shared:
    they go to GROUP_SHARED_FOLDER/<type folder>, flat, since no single
    chain owns them. Everything else in a closure nests chain-style: kit
    root (anchor's type folder + kit name), then one type-folder segment
    per node along the member's dependency path, consecutive duplicates
    collapsed (a Material's MaterialFunction sits beside it, not in
    Materials/Materials)."""
    folder_map = config.get("FOLDER_MAP", {})
    prefix_map = config.get("PREFIX_MAP", {})
    sort_root = config.get("SORT_ROOT", "") or ""
    exclude_folders = config.get("EXCLUDE_FOLDERS", [])
    anchor_classes = config.get("GROUP_ANCHOR_CLASSES", []) or []
    shared_folder = config.get("GROUP_SHARED_FOLDER", "Shared") or "Shared"

    eligible = {}
    for a in assets:
        path = a["path"]
        if is_protected_path(path):
            continue
        if _is_excluded(path, exclude_folders):
            continue
        in_any_root = any(
            path == root or path.startswith(root + "/") for root in all_roots_norm
        )
        if not in_any_root:
            continue
        category, _reason = classify(a["class_name"], config)
        if category is None:
            continue
        eligible[path] = {"asset": a, "category": category}

    eligible_paths = set(eligible.keys())

    # Priority index per anchor class: lower index = higher priority.
    # First occurrence wins if a class is listed twice.
    anchor_priority = {}
    for index, cls in enumerate(anchor_classes):
        if cls not in anchor_priority:
            anchor_priority[cls] = index

    claimed = set()
    kits = []
    for anchor_class in anchor_classes:
        # Kit boundaries for this priority tier: every eligible asset of
        # an anchor class at the SAME or HIGHER priority belongs to its
        # own kit -- BFS must neither absorb it nor traverse through it.
        # Lower-priority anchor classes are NOT boundaries: a Blueprint
        # still absorbs its StaticMesh.
        tier = anchor_priority[anchor_class]
        boundaries = set(
            p for p, info in eligible.items()
            if info["asset"]["class_name"] in anchor_priority
            and anchor_priority[info["asset"]["class_name"]] <= tier
        )
        # Candidates iterate in sorted(path) order, never scan order, so
        # any remaining tie-break is deterministic run to run.
        candidates = sorted(
            p for p, info in eligible.items()
            if info["asset"]["class_name"] == anchor_class
        )
        for path in candidates:
            if path in claimed:
                continue
            members = _dependency_scan(
                path, eligible_paths, boundary_paths=boundaries - set([path]))
            members.pop(path, None)
            claimed.add(path)
            claimed.update(members.keys())
            kits.append((path, members))

    anchor_root_paths = set(anchor_path for anchor_path, _members in kits)

    # Shared counting runs AFTER boundary handling, over the final
    # closures only -- no phantom double-counts from an anchor absorbed
    # into another kit; the stats below match the folders that actually
    # materialize. Anchor roots can never count as members.
    membership_counts = {}
    for _anchor_path, members in kits:
        for member in members:
            if member in anchor_root_paths:
                continue
            membership_counts[member] = membership_counts.get(member, 0) + 1
    shared_members = set(
        m for m, count in membership_counts.items() if count > 1)

    overrides = {}
    # Pass 1: every accepted anchor's own destination -- FINAL.
    kit_roots = {}
    for anchor_path, _members in kits:
        anchor_info = eligible[anchor_path]
        kit_type_folder = folder_map.get(
            anchor_info["category"], anchor_info["category"])
        kit_name = _kit_name(
            anchor_info["asset"]["name"], anchor_info["asset"]["class_name"],
            prefix_map)
        kit_root = (_dest_folder(content_root_norm, sort_root, kit_type_folder)
                    + "/" + kit_name)
        kit_roots[anchor_path] = kit_root
        overrides[anchor_path] = kit_root

    # Pass 2: member routing. An anchor root must never be overwritten --
    # boundary handling above makes anchors unreachable as members, but
    # the guard stays regardless (assert-style skip, not a crash).
    for anchor_path, members in kits:
        kit_root = kit_roots[anchor_path]
        for member, nodes in members.items():
            if member in anchor_root_paths:
                continue
            if member in shared_members:
                continue
            segments = []
            for node in nodes:
                node_folder = folder_map.get(
                    eligible[node]["category"], eligible[node]["category"])
                if not segments or segments[-1] != node_folder:
                    segments.append(node_folder)
            overrides[member] = kit_root + "/" + "/".join(segments)

    for member in shared_members:
        member_folder = folder_map.get(
            eligible[member]["category"], eligible[member]["category"])
        overrides[member] = (
            _dest_folder(content_root_norm, sort_root, shared_folder)
            + "/" + member_folder)

    stats = {
        "kits": len(kits),
        "shared": len(shared_members),
        "loose": len(eligible) - len(claimed),
    }
    return overrides, stats


def build_plan(assets, config, caps):
    """Build the immutable plan dict from a list of scanned assets (the
    shape scan_assets() returns). Reads the current content root via
    discover_content_roots() and otherwise operates purely on `assets`
    and `config`. Returns:

    {"moves": [...], "skips": [...], "stats": {...},
     "content_root": str, "sort_root": str, "timestamp": str}

    When CONFIG["GROUP_BY_ASSET"] is on and the build supports dependency
    queries (caps.dependency_query), a "grouping" key is added with the
    kit statistics and destinations come from the grouping pass above --
    every OTHER rule (skips, collisions, renames) applies unchanged."""
    roots = discover_content_roots()
    # roots[0] is the PRIMARY root -- used below for computing every
    # destination folder, exactly as before. But discover_content_roots()
    # can come back with MORE than one mount on its fallback path (no
    # "/Game" among them), and an asset legitimately living under any of
    # those other mounts is still project content, not something to skip
    # as "outside project content" -- membership is checked against the
    # union of every discovered root, not just the primary one.
    content_root = roots[0] if roots else ""
    all_roots_norm = [r.rstrip("/") for r in roots if r]
    sort_root = config.get("SORT_ROOT", "") or ""
    exclude_folders = config.get("EXCLUDE_FOLDERS", [])
    folder_map = config.get("FOLDER_MAP", {})

    moves = []
    skips = []
    planned_dest_paths = {}
    existing_paths = set(a["path"] for a in assets)

    content_root_norm = content_root.rstrip("/")

    group_overrides = {}
    grouping_stats = None
    if config.get("GROUP_BY_ASSET", False):
        if caps is not None and getattr(caps, "dependency_query", False):
            group_overrides, grouping_stats = _compute_group_plan(
                assets, config, content_root_norm, all_roots_norm)
        else:
            _console_warning(
                "Sortilege: grouping unavailable in this build (no "
                "dependency query API), using flat mapping.")

    for a in assets:
        path = a["path"]
        name = a["name"]
        folder = a["folder"]
        class_name = a["class_name"]

        if is_protected_path(path):
            skips.append({"path": path, "class_name": class_name,
                           "reason": "protected system folder"})
            continue

        if _is_excluded(path, exclude_folders):
            skips.append({"path": path, "class_name": class_name,
                           "reason": "excluded folder"})
            continue

        in_any_root = any(
            path == root or path.startswith(root + "/") for root in all_roots_norm
        )
        if not in_any_root:
            skips.append({"path": path, "class_name": class_name,
                           "reason": "outside project content"})
            continue

        category, reason = classify(class_name, config)
        if category is None:
            skips.append({"path": path, "class_name": class_name, "reason": reason})
            continue

        dest_folder = group_overrides.get(path) or _dest_folder(
            content_root_norm, sort_root, folder_map.get(category, category))
        new_name, needs_rename = _compute_new_name(name, class_name, config)
        needs_move = (folder != dest_folder)

        if not needs_move and not needs_rename:
            skips.append({"path": path, "class_name": class_name, "reason": "already sorted"})
            continue

        if needs_rename:
            name_reason = validate_asset_name(new_name)
            if name_reason:
                skips.append({"path": path, "class_name": class_name,
                               "reason": "invalid target name"})
                continue

        dest_path = dest_folder + "/" + new_name

        if dest_path in existing_paths and dest_path != path:
            skips.append({"path": path, "class_name": class_name,
                           "reason": "destination occupied"})
            continue

        if dest_path in planned_dest_paths:
            skips.append({"path": path, "class_name": class_name,
                           "reason": "name collision with planned move"})
            continue

        if needs_move and needs_rename:
            action = "move+rename"
        elif needs_move:
            action = "move"
        else:
            action = "rename"

        planned_dest_paths[dest_path] = path
        moves.append({
            "path": path, "name": name, "class_name": class_name,
            "category": category, "dest_folder": dest_folder,
            "dest_path": dest_path, "new_name": new_name, "action": action,
        })

    by_category = {}
    for move in moves:
        by_category[move["category"]] = by_category.get(move["category"], 0) + 1

    stats = {
        "scanned": len(assets),
        "moves": len(moves),
        "renames": sum(1 for m in moves if "rename" in m["action"]),
        "skips": len(skips),
        "by_category": by_category,
    }

    timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")

    plan = {
        "moves": moves,
        "skips": skips,
        "stats": stats,
        "content_root": content_root_norm,
        "sort_root": sort_root,
        "timestamp": timestamp,
    }
    if grouping_stats is not None:
        plan["grouping"] = {
            "mode": "by_asset",
            "kits": grouping_stats["kits"],
            "shared": grouping_stats["shared"],
            "loose": grouping_stats["loose"],
        }

    # Verse-side reference fixup (bounty clarification: "no broken
    # references" also covers Verse-side references -- see the VERSE
    # REFERENCES section below). Skipped entirely, with zero filesystem
    # work, when there are no moves at all (nothing could have changed a
    # Verse ref) or when CONFIG["FIX_VERSE_REFERENCES"] is off.
    plan["verse_edits"] = []
    plan["verse_search_dir"] = None
    plan["verse_files_count"] = 0
    if config.get("FIX_VERSE_REFERENCES", True):
        # A handful of real scanned asset package paths (any normal,
        # non-protected asset works) -- resolve_verse_search_dir() uses
        # these to auto-detect the real project directory. See its
        # docstring for why this replaced trusting unreal.Paths.
        # project_dir() unconditionally (PROVEN BUG: that call returns
        # the Fortnite engine dir in UEFN, not the user's project).
        verse_sample_paths = [
            a["path"] for a in assets if not is_protected_path(a["path"])
        ][:5]
        verse_dir = resolve_verse_search_dir(config, sample_asset_paths=verse_sample_paths)
        verse_files = find_verse_files(verse_dir) if verse_dir else []
        plan["verse_search_dir"] = verse_dir
        plan["verse_files_count"] = len(verse_files)
        if moves and verse_files:
            plan["verse_edits"] = build_verse_edits(
                moves, verse_files, all_roots_norm,
                fix_bare_names=config.get("FIX_VERSE_BARE_NAMES", True))

    return plan


# =====================================================================
# === VERSE REFERENCES ===
# =====================================================================
# Bounty OP clarification: "no broken references" also covers Verse-side
# references. Ground truth (Epic's Asset Reflection docs): an exposed
# asset's Verse reference is its Content-folder path with the content
# root stripped and "/" replaced by ".". Moving an asset therefore
# changes its Verse-qualified name, and Epic's asset-move APIs never
# rewrite Verse SOURCE -- only the asset system's own redirectors (see
# _CAUTION_VERSE_REFERENCES above, which stays accurate: this section is
# a SEPARATE mechanism, not a claim that redirectors rewrite Verse code).
#
# This section finds every real .verse source file, works out each moved
# asset's old/new Verse ref, and rewrites every boundary-safe occurrence
# in place -- backed up first, undoable after. Python cannot COMPILE
# Verse (that is a UEFN action): this fixup keeps the qualified names
# correct so a Build Verse Code afterward has a chance to succeed; it can
# never itself prove the result compiles. See the README's "Fixing Verse
# references" section.

def content_path_to_verse_ref(content_path, content_roots):
    """Epic's Asset Reflection rule, exactly: strip the matching content
    root from `content_path` (an exposed asset's Content-folder package
    path) and replace every remaining "/" with ".". A root-level asset
    (nothing left after stripping the root) yields a bare name with no
    dots at all -- "the subfolder name becomes the name of the Verse
    module," so a root-level asset simply has no module segment to
    contribute.

    `content_roots` may hold more than one discovered mount (discover_
    content_roots() can return several on its fallback path); the FIRST
    root that is a genuine prefix of `content_path` wins. A trailing "/"
    on either the root or `content_path` is tolerated. Returns None if
    `content_path` sits under none of `content_roots`, or equals a root
    exactly (the root itself is not an asset) -- fail-soft, not an
    assert; callers treat None as "cannot compute a Verse ref for this,
    skip it" rather than raising."""
    path = (content_path or "").rstrip("/")
    for raw_root in content_roots or []:
        root = str(raw_root or "").rstrip("/")
        if not root:
            continue
        if path == root:
            return None
        prefix = root + "/"
        if path.startswith(prefix):
            remainder = path[len(prefix):]
            if not remainder:
                return None
            return ".".join(remainder.split("/"))
    return None


def resolve_verse_search_dir(config, sample_asset_paths=None):
    """Decide which real directory to walk for .verse source files.

    PROVEN BUG this fixes: a live UEFN diagnostic showed unreal.Paths.
    project_dir() resolving to the FORTNITE ENGINE directory, not the
    user's project (the preview line read "Verse fixup: 7 .verse file(s)
    found under ..\\..\\..\\FortniteGame" -- real .verse files, entirely the
    wrong project). find_verse_files() then scanned Fortnite's own .verse
    files and produced zero edits even though the user's real project had
    a genuine Verse reference to a moved asset.

    This now builds an ORDERED list of candidate directories and returns
    the FIRST one for which find_verse_files() actually finds something --
    whichever real directory demonstrably HAS Verse source wins, rather
    than trusting any single link in the chain blindly. If no candidate
    has files, the first non-None candidate is returned anyway, so the
    "Verse fixup: N file(s) found under X" diagnostic still names a real
    path instead of going blank.

    Candidate order:
    1. CONFIG["VERSE_SEARCH_DIR"] if set -- trusted as-is, unconditionally,
       no files check at all. The user said "look here"; honor it, same
       as always. Short-circuits everything below.
    2. Derived from `sample_asset_paths` (a handful of real scanned asset
       package paths -- build_plan()/run_apply() each pass a few
       non-protected ones): unreal.EditorAssetLibrary.load_asset(path) ->
       unreal.SystemLibrary.get_system_path(asset) gives a real on-disk
       path like ".../PremFN_1v1/Content/Textures/T_Foo.uasset"; the
       project directory is the parent of that path's "Content" segment
       (see _project_dir_from_asset_disk_path()). This is the reliable
       UEFN way to find the user's actual project root, and the primary
       fix for the bug above. Up to 5 sample paths are tried; each is its
       own hasattr-gated, try/except attempt -- one bad/stale sample never
       blocks the rest.
    3. unreal.Paths.project_dir() -- kept only as a low-priority fallback
       now (this is the call that returns the Fortnite engine dir in
       UEFN; see the bug above).
    4. unreal.SystemLibrary.get_project_directory().

    Every optional API is hasattr-gated AND wrapped in its own try/except,
    same as resolve_log_dir() -- a build (or, in tests, the mock) that
    simply does not define one of these getters just falls through to the
    next link.

    Unlike resolve_log_dir(), this deliberately does NOT fall back to the
    script's own folder or the current working directory when nothing
    resolves: a log dir must exist somewhere to write to, but there is no
    safe default folder to blind-walk looking for Verse source, so
    "nothing resolved at all" fails soft to None -- find_verse_files(None)
    simply returns no files, and the whole feature quietly no-ops."""
    raw = config.get("VERSE_SEARCH_DIR", "") or ""
    if raw:
        return os.path.normpath(raw)

    candidates = []

    if (unreal is not None and sample_asset_paths
            and hasattr(unreal, "EditorAssetLibrary")
            and hasattr(unreal.EditorAssetLibrary, "load_asset")
            and hasattr(unreal, "SystemLibrary")
            and hasattr(unreal.SystemLibrary, "get_system_path")):
        for sample_path in list(sample_asset_paths)[:5]:
            try:
                asset_obj = unreal.EditorAssetLibrary.load_asset(sample_path)
                if asset_obj is None:
                    continue
                disk_path = unreal.SystemLibrary.get_system_path(asset_obj)
                project_dir = _project_dir_from_asset_disk_path(disk_path)
                if project_dir and project_dir not in candidates:
                    candidates.append(project_dir)
            except Exception:
                continue

    if unreal is not None:
        try:
            if hasattr(unreal, "Paths") and hasattr(unreal.Paths, "project_dir"):
                candidate = unreal.Paths.project_dir()
                if candidate:
                    norm = os.path.normpath(str(candidate))
                    if norm not in candidates:
                        candidates.append(norm)
        except Exception:
            pass

    if unreal is not None:
        try:
            if hasattr(unreal, "SystemLibrary") and hasattr(
                unreal.SystemLibrary, "get_project_directory"
            ):
                candidate = unreal.SystemLibrary.get_project_directory()
                if candidate:
                    norm = os.path.normpath(str(candidate))
                    if norm not in candidates:
                        candidates.append(norm)
        except Exception:
            pass

    if not candidates:
        return None

    for candidate in candidates:
        if find_verse_files(candidate):
            return candidate

    return candidates[0]


def _project_dir_from_asset_disk_path(disk_path):
    """Given a real on-disk asset path (as unreal.SystemLibrary.
    get_system_path() returns, e.g. ".../PremFN_1v1/Content/Textures/
    T_Foo.uasset"), return the project directory: the parent of the
    nearest path segment literally named "Content". Every UEFN/UE asset
    lives under exactly one project's Content folder, so this is the
    reliable inverse of "where does this asset's project live on disk".

    Fail-soft: returns None (never raises) if `disk_path` is falsy or has
    no "Content" segment with anything above it."""
    if not disk_path:
        return None
    try:
        norm = os.path.normpath(str(disk_path))
        parts = norm.split(os.sep)
        for i, part in enumerate(parts):
            if part == "Content" and i > 0:
                return os.sep.join(parts[:i])
    except Exception:
        return None
    return None


# Path segments that mark a location never worth searching for real Verse
# source: engine-regenerated/VCS/build bookkeeping folders. os.walk()
# prunes its own `dirs` list against this set on every iteration, so a
# match at ANY depth stops that whole subtree from being descended into,
# not just an immediate child of `project_dir`.
_VERSE_EXCLUDE_DIR_SEGMENTS = {
    "Intermediate", "Saved", "Build", "DerivedDataCache", ".git",
    "__ExternalActors__", "__ExternalObjects__",
}


def find_verse_files(project_dir):
    """Walk `project_dir` for every real Verse source file (*.verse),
    using NORMAL Python file I/O -- these are text SOURCE files, not
    `unreal`-managed assets, so the unreal-only access rule elsewhere in
    this file does not apply here. Excludes *.digest.verse (Assets.
    digest.verse and similar -- auto-generated by UEFN itself, NEVER
    hand-edited and never a real reference source) and anything under a
    path segment in _VERSE_EXCLUDE_DIR_SEGMENTS. Returns absolute paths.

    Fail-soft: a falsy/missing/unwalkable `project_dir` returns []
    rather than raising."""
    if not project_dir:
        return []
    results = []
    try:
        for root, dirs, files in os.walk(project_dir):
            dirs[:] = [d for d in dirs if d not in _VERSE_EXCLUDE_DIR_SEGMENTS]
            for name in files:
                lowered = name.lower()
                if not lowered.endswith(".verse"):
                    continue
                if lowered.endswith(".digest.verse"):
                    continue
                results.append(os.path.abspath(os.path.join(root, name)))
    except Exception:
        return results
    return results


def _verse_ref_pattern(old_ref):
    """Compile the boundary-safe regex shared by every Verse-source
    replacement this file makes -- both dotted asset references
    (PowersWheelAssets.Models.Textures.T_Hex) and using-statement folder
    paths (/PremFN_1v1/PowersWheelAssets/Models/Textures) alike, since
    the same rule works for both: a match must not be immediately
    preceded by a word character or a "." (so a shorter ref is never
    replaced as the tail fragment of a longer qualified name -- "A.B.
    T_Hex" does not match inside "X.A.B.T_Hex") and must not be
    immediately followed by a word character (so "T_Hex" never matches
    inside "T_Hex2"). "/" is not a word character, so this same rule also
    correctly bounds a slash-form folder path with no special casing."""
    return re.compile(r"(?<![\w.])" + re.escape(old_ref) + r"(?![\w])")


# using { /Some/Folder/Path } -- captures the path text between the
# braces (non-whitespace, backtracks past a trailing "}").
_USING_STATEMENT_RE = re.compile(r"using\s*\{\s*(\S+?)\s*\}")


def build_verse_edits(plan_moves, verse_files, content_roots, fix_bare_names=True):
    """Compute every Verse-source edit needed to keep `.verse` code
    compiling after `plan_moves` relocates assets referenced by folder-
    qualified name (Asset Reflection). `plan_moves` is build_plan()'s
    moves list (dicts with at least "path"/"dest_path", optionally
    "dest_folder") -- or execute_plan()'s actually-moved pairs, normalized
    to the same {"path": old, "dest_path": new} shape by the caller (see
    run_apply()).

    Returns a list of edits: {"file", "line_no", "old_line", "new_line",
    "old_ref", "new_ref", "is_bare", "count", "kind", "skipped"} -- one
    entry per (file, line, old_ref) triple where at least one boundary-
    safe occurrence of that ref was found. "is_bare" is True whenever
    old_ref has no "." (a root-level asset name, or -- structurally
    dot-free the same way -- a using-statement's slash path); "kind"
    tells the two apart for display purposes ("ref" for a plain dotted
    asset reference, "using" for a whole-folder using-statement rewrite)
    -- see format_verse_preview(), which only flags the former as the
    riskier case worth a manual look.

    `fix_bare_names` (CONFIG["FIX_VERSE_BARE_NAMES"], default True) gates
    ONLY a bare "ref"-kind entry -- a using-statement edit is a
    different, already-conservative category (gated by the folder-
    agreement rule below, not by its dot count) and is never affected by
    this flag regardless of how many dots its own old_ref happens to
    have. When False, a bare ref match is still FOUND (so the user can
    see and fix it manually) but marked "skipped": True and left
    UNCHANGED in "new_line" -- apply_verse_edits() never writes a
    skipped entry to disk. Every other entry always has "skipped": False.

    Every replacement is boundary-safe (_verse_ref_pattern) -- never a
    naive substring replace. A move whose old and new Verse ref come out
    identical (most commonly a no-op {"path": x, "dest_path": x} pair)
    contributes no edit.

    using-statement rewriting is deliberately conservative: a folder-
    level old->new mapping is only derived when EVERY move sharing that
    old folder agrees on the very same new folder; a folder whose
    contents scattered to two or more destinations in this run is left
    out entirely rather than guessed at. Even then, a using-line is only
    ever rewritten when the path captured between its braces EXACTLY
    equals a mapped old folder (trailing "/" tolerated) -- this never
    touches a comment or string that merely happens to contain the same
    text elsewhere on the line.

    Every .verse file is read with normal Python text I/O; a single
    unreadable file is skipped (fail-soft) rather than aborting the
    whole scan."""
    edits = []

    ref_pairs = []
    for m in plan_moves:
        old_path = m.get("path")
        new_path = m.get("dest_path")
        if not old_path or not new_path:
            continue
        old_ref = content_path_to_verse_ref(old_path, content_roots)
        new_ref = content_path_to_verse_ref(new_path, content_roots)
        if not old_ref or not new_ref or old_ref == new_ref:
            continue
        ref_pairs.append((old_ref, new_ref))

    folder_candidates = {}
    for m in plan_moves:
        old_path = m.get("path")
        if not old_path or "/" not in old_path:
            continue
        old_folder = old_path.rsplit("/", 1)[0]
        dest_path = m.get("dest_path") or ""
        new_folder = m.get("dest_folder") or (
            dest_path.rsplit("/", 1)[0] if "/" in dest_path else "")
        if not new_folder or old_folder == new_folder:
            continue
        folder_candidates.setdefault(old_folder, set()).add(new_folder)
    folder_pairs = [
        (old_folder, next(iter(new_folders)))
        for old_folder, new_folders in folder_candidates.items()
        if len(new_folders) == 1
    ]

    if not ref_pairs and not folder_pairs:
        return edits

    for file_path in verse_files:
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
        except Exception:
            continue

        for line_no, raw_line in enumerate(lines, start=1):
            line = raw_line.rstrip("\r\n")

            for old_ref, new_ref in ref_pairs:
                is_bare = "." not in old_ref
                pattern = _verse_ref_pattern(old_ref)
                if is_bare and not fix_bare_names:
                    # Found, but deliberately left unrewritten -- listed
                    # as "skipped (bare name - fix manually)" so the user
                    # knows to handle it by hand instead of it silently
                    # vanishing from the preview/report.
                    count = len(pattern.findall(line))
                    if count:
                        edits.append({
                            "file": file_path, "line_no": line_no,
                            "old_line": line, "new_line": line,
                            "old_ref": old_ref, "new_ref": new_ref,
                            "is_bare": True, "count": count,
                            "kind": "ref", "skipped": True,
                        })
                    continue
                new_line, count = pattern.subn(new_ref, line)
                if count:
                    edits.append({
                        "file": file_path, "line_no": line_no,
                        "old_line": line, "new_line": new_line,
                        "old_ref": old_ref, "new_ref": new_ref,
                        "is_bare": is_bare, "count": count,
                        "kind": "ref", "skipped": False,
                    })

            if folder_pairs:
                using_match = _USING_STATEMENT_RE.search(line)
                if using_match:
                    used_path = using_match.group(1).rstrip("/")
                    for old_folder, new_folder in folder_pairs:
                        if used_path != old_folder:
                            continue
                        pattern = _verse_ref_pattern(old_folder)
                        new_line, count = pattern.subn(new_folder, line)
                        if count:
                            edits.append({
                                "file": file_path, "line_no": line_no,
                                "old_line": line, "new_line": new_line,
                                "old_ref": old_folder, "new_ref": new_folder,
                                "is_bare": "." not in old_folder,
                                "count": count, "kind": "using",
                                "skipped": False,
                            })

    return edits


def format_verse_preview(edits):
    """Render `edits` (build_verse_edits()'s output) as ASCII lines,
    grouped by file, each row showing the line number and old_ref ->
    new_ref. A bare (dot-free) plain reference -- a root-level asset name
    with no module qualification -- gets a " (bare name - review)"
    suffix: it is inherently more likely to collide with an unrelated
    identifier that merely happens to share it, so it is flagged for a
    manual look even though the boundary-safe regex already guards
    against a partial-token false match. A using-statement folder-path
    edit is never flagged this way even though a folder path also has no
    "." -- it is a different, already-conservative rewrite (see build_
    verse_edits' docstring), not a short bare identifier.

    An entry build_verse_edits() marked "skipped": True (CONFIG
    ["FIX_VERSE_BARE_NAMES"] = False, a bare ref found but deliberately
    left unrewritten) is listed SEPARATELY, under its own "skipped (bare
    name - fix manually): N" heading, so it is never confused with an
    edit that will actually happen but is still visible enough that it
    does not just silently vanish. Returns [] (nothing to print) when
    `edits` is empty."""
    lines = []
    real_edits = [e for e in edits if not e.get("skipped")]
    skipped_bare = [e for e in edits if e.get("skipped")]
    if not real_edits and not skipped_bare:
        return lines

    def _grouped_by_file(entries):
        by_file = {}
        file_order = []
        for e in entries:
            f = e["file"]
            if f not in by_file:
                by_file[f] = []
                file_order.append(f)
            by_file[f].append(e)
        return file_order, by_file

    if real_edits:
        lines.append("-- Verse reference edits (%d) --" % len(real_edits))
        file_order, by_file = _grouped_by_file(real_edits)
        for f in file_order:
            lines.append("  %s" % f)
            for e in by_file[f]:
                suffix = ""
                if e.get("is_bare") and e.get("kind", "ref") == "ref":
                    suffix = " (bare name - review)"
                lines.append("    line %d: %s -> %s%s" % (
                    e["line_no"], e["old_ref"], e["new_ref"], suffix))

    if skipped_bare:
        lines.append("skipped (bare name - fix manually): %d" % len(skipped_bare))
        file_order, by_file = _grouped_by_file(skipped_bare)
        for f in file_order:
            lines.append("  %s" % f)
            for e in by_file[f]:
                lines.append("    line %d: %s (would become: %s)" % (
                    e["line_no"], e["old_ref"], e["new_ref"]))

    return lines


def _verse_backup_path(backup_dir, file_path):
    """Map a real .verse file's absolute path to a unique, collision-free
    backup filename under `backup_dir`: the drive letter (if any) and
    every path separator are folded into one "_"-joined component, so two
    files that only differ by folder (or drive) can never collide the
    way two bare basenames could."""
    norm = os.path.normpath(file_path)
    drive, rest = os.path.splitdrive(norm)
    rest = rest.replace("\\", "/").strip("/")
    safe = rest.replace("/", "_")
    if drive:
        safe = drive.rstrip(":") + "_" + safe
    return os.path.join(backup_dir, safe or "verse_file")


def apply_verse_edits(edits, log_dir):
    """Apply every collected Verse-reference edit (build_verse_edits()'s
    output) to the real .verse files on disk. BEFORE touching a file,
    copies it to a backup under `<log_dir>/verse_backup_<ts>/` and
    records {original_path: backup_path} in a freshly written sortilege_
    verse_undo_<ts>.json alongside it (same `ts`, so the two always pair
    up) -- see undo_verse_edits(). All edits for one file are applied
    TOGETHER, line-index by line-index, against that file's CURRENT
    on-disk content (read fresh here, never a stale snapshot a caller
    might be holding from preview time), so two edits landing on the same
    line both take effect correctly instead of one clobbering the
    other's precomputed "new_line" text.

    Every file is its own try/except -- fail-soft, one bad file (missing,
    permission error, whatever) never aborts the rest of the batch; it is
    recorded in "failed" instead. Written back with encoding="utf-8" via
    the same temp-file + os.replace() atomic-write pattern every other
    writer in this file uses.

    Returns {"edited": [files], "failed": [(file, err)], "backup_index":
    path_or_None}. `edits` empty -- or holding ONLY entries build_verse_
    edits() marked "skipped": True (CONFIG["FIX_VERSE_BARE_NAMES"] =
    False) -- is a clean no-op: no backup folder, no index file, no file
    ever opened for writing, "backup_index" is None."""
    edited = []
    failed = []
    real_edits = [e for e in edits if not e.get("skipped")]
    if not real_edits:
        return {"edited": edited, "failed": failed, "backup_index": None}

    by_file = {}
    file_order = []
    for e in real_edits:
        f = e["file"]
        if f not in by_file:
            by_file[f] = []
            file_order.append(f)
        by_file[f].append(e)

    ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_dir = os.path.join(log_dir, "verse_backup_%s" % ts)
    backups = {}

    for file_path in file_order:
        file_edits = by_file[file_path]
        try:
            if not os.path.isdir(backup_dir):
                os.makedirs(backup_dir)
            backup_path = _verse_backup_path(backup_dir, file_path)
            backup_parent = os.path.dirname(backup_path)
            if backup_parent and not os.path.isdir(backup_parent):
                os.makedirs(backup_parent)
            shutil.copy2(file_path, backup_path)

            with open(file_path, "r", encoding="utf-8") as f:
                current_lines = f.readlines()

            for e in file_edits:
                idx = e["line_no"] - 1
                if idx < 0 or idx >= len(current_lines):
                    continue
                pattern = _verse_ref_pattern(e["old_ref"])
                current_lines[idx] = pattern.sub(e["new_ref"], current_lines[idx])

            tmp_path = file_path + ".tmp"
            with open(tmp_path, "w", encoding="utf-8") as f:
                f.writelines(current_lines)
            os.replace(tmp_path, file_path)

            backups[file_path] = backup_path
            edited.append(file_path)
        except Exception as exc:
            failed.append((file_path, str(exc)))

    index_path = None
    if backups:
        index_path = os.path.join(log_dir, "sortilege_verse_undo_%s.json" % ts)
        data = {"version": 1, "created": ts, "backups": backups}
        try:
            tmp_path = index_path + ".tmp"
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            os.replace(tmp_path, index_path)
        except Exception:
            index_path = None

    return {"edited": edited, "failed": failed, "backup_index": index_path}


def undo_verse_edits(backup_index_path):
    """Restore every .verse file recorded in `backup_index_path` (an
    apply_verse_edits()-written sortilege_verse_undo_<ts>.json) from its
    backup copy. Returns {"restored": [files], "failed": [(file, err)]}.

    Fail-soft, same contract as load_undo_log(): a missing/unreadable
    index (or a falsy path) returns both lists empty rather than raising.
    Each file's restore is its own try/except -- one bad file never
    aborts the rest of the batch."""
    restored = []
    failed = []
    if not backup_index_path:
        return {"restored": restored, "failed": failed}

    try:
        with open(backup_index_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as exc:
        _console_warning(
            "Sortilege: could not read Verse backup index %s (%s)." % (
                backup_index_path, exc))
        return {"restored": restored, "failed": failed}

    for original_path, backup_path in data.get("backups", {}).items():
        try:
            shutil.copy2(backup_path, original_path)
            restored.append(original_path)
        except Exception as exc:
            failed.append((original_path, str(exc)))

    return {"restored": restored, "failed": failed}


# =====================================================================
# === PREVIEW ===
# =====================================================================
# Turns a plan dict (build_plan()'s output) into ASCII text a human can
# read in the Output Log before anything is touched. Pure formatting --
# no filesystem or `unreal` access happens here (that's print_preview()
# and the writers below).

def _truncate_middle(text, maxlen=60):
    """Shorten `text` to at most `maxlen` characters by cutting out its
    middle and inserting a literal "..." marker, so both the start and
    the end of a long asset path stay visible. Never used on anything
    but display strings -- the underlying plan dict is untouched."""
    text = "" if text is None else str(text)
    if len(text) <= maxlen:
        return text
    keep = maxlen - 3
    if keep <= 0:
        return text[:maxlen]
    left = keep - keep // 2
    right = keep // 2
    tail = text[-right:] if right else ""
    return text[:left] + "..." + tail


def _group_by_reason(skips):
    """Group a skips list into (reason, [items]) pairs, sorted by reason
    so the preview and the summary report always list reasons in the
    same order."""
    grouped = {}
    order = []
    for skip in skips:
        reason = skip.get("reason", "unknown")
        if reason not in grouped:
            grouped[reason] = []
            order.append(reason)
        grouped[reason].append(skip)
    return [(reason, grouped[reason]) for reason in sorted(order)]


# Destination paths longer than this get a preview warning (deep grouped
# chains can exceed platform path limits) -- display-only, never affects
# what the executor attempts.
_LONG_DEST_PATH_WARN = 200

# The two research-mandated caution lines. Verbatim -- do not reword.
_CAUTION_REFERENCER_CACHE = (
    "NOTE: referencer data is cached by the engine; counts can include "
    "false positives until assets are loaded and re-saved."
)
_CAUTION_VERSE_REFERENCES = (
    "CAUTION: if your Verse code references assets by folder-qualified "
    "name (Asset Reflection), moving those assets requires updating "
    "that Verse code. Redirectors do not rewrite Verse source."
)


def preview_counts(plan):
    """Pure counts derived from `plan` (build_plan()'s output), the exact
    same math format_preview()'s header and confirmed_to_execute()'s
    dialog message already use: total-to-move / move+rename / rename-in-
    place / skipped counts derived from `plan["moves"]` itself (not
    echoed from `plan["stats"]`, whose "renames" counts "rename" AND
    "move+rename" together -- see format_preview()'s docstring), plus the
    by-category breakdown and the content/sort root display strings.

    Extracted so the GUI header can show the identical numbers without a
    second hand-rolled copy of this math that could quietly drift from
    format_preview()'s own console output.
    """
    moves = plan.get("moves", [])
    skips = plan.get("skips", [])
    stats = plan.get("stats", {})

    move_only = [m for m in moves if m["action"] == "move"]
    move_rename = [m for m in moves if m["action"] == "move+rename"]
    rename_only = [m for m in moves if m["action"] == "rename"]
    total_to_move = len(move_only) + len(move_rename)

    return {
        "scanned": stats.get("scanned", len(moves) + len(skips)),
        "total_to_move": total_to_move,
        "move_rename": len(move_rename),
        "rename_only": len(rename_only),
        "skips": len(skips),
        "by_category": dict(stats.get("by_category", {})),
        "content_root": plan.get("content_root", "") or "(unknown)",
        "sort_root": plan.get("sort_root", "") or "(none)",
    }


def format_preview(plan):
    """Render `plan` (build_plan()'s output) as a list of ASCII lines:
    a header with scan stats, a per-category FROM -> TO table (class +
    action columns, paths capped at 60 chars with middle-ellipsis), a
    skip section grouped by reason with counts, and a footer with the
    dry-run notice plus the two mandatory caution lines.

    Counts in the header are derived directly from `plan["moves"]`, not
    echoed from `plan["stats"]` -- stats["renames"] counts "rename" and
    "move+rename" items together, which reads as ambiguous on its own.
    """
    moves = plan.get("moves", [])
    skips = plan.get("skips", [])
    counts = preview_counts(plan)

    lines = []
    lines.append("=" * 70)
    lines.append("Sortilege - dry run preview")
    lines.append("=" * 70)
    lines.append("Content root: %s    Sort root: %s" % (
        counts["content_root"], counts["sort_root"],
    ))
    lines.append("Scanned %d asset(s)." % counts["scanned"])
    lines.append(
        "%d asset(s) to move (%d will also be renamed), %d rename-in-place, "
        "%d skipped" % (counts["total_to_move"], counts["move_rename"],
                         counts["rename_only"], counts["skips"])
    )
    if counts["by_category"]:
        cat_bits = ["%s: %d" % (k, v) for k, v in sorted(counts["by_category"].items())]
        lines.append("By category: " + ", ".join(cat_bits))
    grouping = plan.get("grouping")
    if grouping:
        lines.append("Grouping: by asset (%d kits, %d shared, %d loose)" % (
            grouping.get("kits", 0), grouping.get("shared", 0),
            grouping.get("loose", 0)))
    verse_edits = plan.get("verse_edits") or []
    verse_real_edit_count = len([e for e in verse_edits if not e.get("skipped")])
    verse_skipped_bare_count = len([e for e in verse_edits if e.get("skipped")])
    if verse_real_edit_count:
        lines.append("Verse reference edits proposed: %d" % verse_real_edit_count)
    if verse_skipped_bare_count:
        lines.append(
            "Verse bare-name edits skipped (fix manually): %d" % verse_skipped_bare_count)
    # Always report where the Verse scan looked and how many .verse files it
    # found -- otherwise "0 Verse edits" is ambiguous between "wrong search
    # directory, found nothing" and "found the files, nothing referenced a
    # moved asset". Fastest field diagnostic for the Verse fixup.
    _vdir = plan.get("verse_search_dir")
    _vcount = plan.get("verse_files_count", 0)
    if _vdir:
        lines.append("Verse fixup: %d .verse file(s) found under %s" % (_vcount, _vdir))
    else:
        lines.append(
            "Verse fixup: NO .verse search directory resolved -- set "
            "VERSE_SEARCH_DIR in CONFIG to your UEFN project folder "
            "(the one containing your .uefnproject).")
    # Deep grouped chains can push destination paths past what some
    # platforms/tools move reliably. Purely a preview warning -- the
    # executor's per-item failure handling already covers any actual
    # failure; nothing about execution changes here.
    long_dest_count = sum(
        1 for m in moves if len(m.get("dest_path", "")) > _LONG_DEST_PATH_WARN)
    if long_dest_count:
        lines.append(
            "WARNING: %d destination path(s) are very long and may fail "
            "to move on this platform; consider flat mode or a shallower "
            "FOLDER_MAP. Affected rows are marked with ! below."
            % long_dest_count)
    lines.append("")

    if moves:
        by_category = {}
        cat_order = []
        for m in moves:
            cat = m["category"]
            if cat not in by_category:
                by_category[cat] = []
                cat_order.append(cat)
            by_category[cat].append(m)

        class_w = max([len(m["class_name"]) for m in moves] + [len("Class")])
        action_w = max([len(m["action"]) for m in moves] + [len("Action")])
        from_w = max([len(_truncate_middle(m["path"])) for m in moves] + [len("From")])

        for category in sorted(cat_order):
            cat_moves = by_category[category]
            lines.append("-- %s (%d) --" % (category, len(cat_moves)))
            for m in cat_moves:
                frm = _truncate_middle(m["path"])
                to = _truncate_middle(m["dest_path"])
                line = "  %-*s  %-*s  %-*s -> %s" % (
                    class_w, m["class_name"], action_w, m["action"], from_w, frm, to)
                if len(m.get("dest_path", "")) > _LONG_DEST_PATH_WARN:
                    line += " !"
                lines.append(line)
            lines.append("")

    if skips:
        lines.append("-- Skipped (%d) --" % len(skips))
        for reason, items in _group_by_reason(skips):
            lines.append("  %s (%d):" % (reason, len(items)))
            for s in items:
                lines.append("    %s [%s]" % (_truncate_middle(s["path"]), s["class_name"]))
        lines.append("")

    if verse_edits:
        lines.extend(format_verse_preview(verse_edits))
        lines.append("")

    lines.append("-" * 70)
    lines.append(
        "DRY RUN - nothing was changed. To execute: open sortilege.py, set "
        "I_UNDERSTAND_THIS_MODIFIES_MY_PROJECT = True in the CONFIG section "
        "near the top of the file, save, and re-run this script with "
        "'apply' (py \"path/to/sortilege.py\" apply)."
    )
    lines.append("")
    lines.append(_CAUTION_REFERENCER_CACHE)
    lines.append(_CAUTION_VERSE_REFERENCES)

    return lines


def print_preview(plan):
    """format_preview(plan), then log every line via _console() (unreal.log
    when available, falling back to plain print() when `unreal` genuinely
    isn't -- e.g. a syntax check run outside the editor)."""
    lines = format_preview(plan)
    for line in lines:
        _console(line)
    return lines


def plan_to_move_rows(plan):
    """Flatten plan["moves"] into GUI-table rows: one dict per move with
    "category", "class_name", "from", "to". Grouped by category (sorted
    alphabetically, same order format_preview()'s console table uses)
    with each category's original move order preserved within it. Unlike
    format_preview()'s console table, "from"/"to" are the FULL,
    untruncated paths -- the GUI's Treeview has room to show them."""
    moves = plan.get("moves", [])
    by_category = {}
    cat_order = []
    for m in moves:
        cat = m["category"]
        if cat not in by_category:
            by_category[cat] = []
            cat_order.append(cat)
        by_category[cat].append(m)

    rows = []
    for category in sorted(cat_order):
        for m in by_category[category]:
            rows.append({
                "category": category,
                "class_name": m["class_name"],
                "from": m["path"],
                "to": m["dest_path"],
            })
    return rows


def plan_to_skip_rows(plan):
    """Flatten plan["skips"] into GUI-table rows: one dict per skip with
    "reason", "class_name", "path" -- grouped/sorted by reason the same
    way _group_by_reason() groups the console preview's skip section."""
    rows = []
    for reason, items in _group_by_reason(plan.get("skips", [])):
        for s in items:
            rows.append({
                "reason": reason,
                "class_name": s["class_name"],
                "path": s["path"],
            })
    return rows


def plan_to_verse_edit_rows(plan):
    """Flatten plan["verse_edits"] (build_verse_edits()'s output, as
    attached by build_plan()) into GUI-table rows: one dict per entry
    with "file", "line_no", "old_ref", "new_ref", "note" -- the exact
    same distinction the console's format_verse_preview() draws, just
    reshaped for a Treeview instead of ASCII lines. "note" is "bare name
    - review" for a real (non-skipped) bare plain reference, "skipped -
    fix manually" for an entry build_verse_edits() left unrewritten under
    CONFIG["FIX_VERSE_BARE_NAMES"] = False, or "" otherwise (a qualified
    reference, or any using-statement folder-path edit -- never flagged
    bare regardless of its own dot count, same reasoning as format_
    verse_preview())."""
    rows = []
    for e in plan.get("verse_edits", []) or []:
        if e.get("skipped"):
            note = "skipped - fix manually"
        elif e.get("is_bare") and e.get("kind", "ref") == "ref":
            note = "bare name - review"
        else:
            note = ""
        rows.append({
            "file": e["file"], "line_no": e["line_no"],
            "old_ref": e["old_ref"], "new_ref": e["new_ref"], "note": note,
        })
    return rows


# =====================================================================
# === LOG DIR + FILE WRITERS ===
# =====================================================================
# Every run's plan JSON, human-readable summary, and undo log land in
# the same resolved log directory. resolve_log_dir() is the single
# gated chain every writer below goes through.

def resolve_log_dir(config):
    """Decide where Sortilege writes its plan/report/undo files. Chain:
    CONFIG["LOG_DIR"] if set -> unreal.SystemLibrary.get_project_saved_
    directory() (hasattr-gated) -> unreal.Paths.project_saved_dir()
    (hasattr-gated) -> the directory this script lives in -> the current
    working directory. Every optional API is hasattr-gated AND wrapped
    in its own try/except -- a UEFN build (or, in tests, the mock) that
    simply does not define one of these getters just falls through to
    the next link, same as every other optional-capability probe in this
    file. Result is normalized with os.path.normpath and the directory
    is created if it doesn't exist yet."""
    raw = config.get("LOG_DIR", "") or ""

    if not raw and unreal is not None:
        try:
            if hasattr(unreal, "SystemLibrary") and hasattr(
                unreal.SystemLibrary, "get_project_saved_directory"
            ):
                candidate = unreal.SystemLibrary.get_project_saved_directory()
                if candidate:
                    raw = str(candidate)
        except Exception:
            raw = ""

    if not raw and unreal is not None:
        try:
            if hasattr(unreal, "Paths") and hasattr(unreal.Paths, "project_saved_dir"):
                candidate = unreal.Paths.project_saved_dir()
                if candidate:
                    raw = str(candidate)
        except Exception:
            raw = ""

    if not raw:
        try:
            raw = os.path.dirname(os.path.abspath(__file__))
        except Exception:
            raw = ""

    if not raw:
        raw = os.getcwd()

    log_dir = os.path.normpath(raw)

    try:
        if not os.path.isdir(log_dir):
            os.makedirs(log_dir)
    except Exception:
        pass

    return log_dir


def write_plan_json(plan, log_dir):
    """Write `plan` as-is to sortilege_plan_<timestamp>.json in `log_dir`
    and return the full path. Uses plan["timestamp"] (already stamped by
    build_plan()) so the filename and the plan's own recorded timestamp
    always agree. Written atomically (temp file + os.replace) -- same
    cheap hardening as UndoLog._write(), even though this is a
    single-shot write per run: a crash mid-write must never leave a
    truncated plan file where a complete one (or none at all) belongs."""
    timestamp = plan.get("timestamp") or datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    filename = "sortilege_plan_%s.json" % timestamp
    path = os.path.join(log_dir, filename)
    tmp_path = path + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(plan, f, indent=2)
    os.replace(tmp_path, path)
    return path


def _format_redirector_cleanup(redirector_cleanup):
    if not redirector_cleanup:
        return "not run"
    fixed = redirector_cleanup.get("fixed", [])
    remaining = redirector_cleanup.get("remaining", [])
    return "%d fixed, %d remaining (method=%s)" % (
        len(fixed), len(remaining), redirector_cleanup.get("method", "?"))


def _format_verify(verify):
    if not verify:
        return "not run"
    return ("ok=%s missing=%d old_paths_alive=%d leftover_redirectors=%d "
            "broken_soft_refs=%d") % (
        verify.get("ok"),
        len(verify.get("missing", [])),
        len(verify.get("old_paths_alive", [])),
        len(verify.get("leftover_redirectors", [])),
        len(verify.get("broken_soft_refs", [])),
    )


def write_summary(plan, results, log_dir):
    """Write a human-readable sortilege_report_<timestamp>.txt to
    `log_dir` and return the full path: what moved where (old -> new),
    what was renamed, what was skipped and why, the redirector cleanup
    result, and the verify result.

    `results` is the executor's output dict, `{"moved": [(old, new)],
    "failed": [(old, new, error)]}` (Task 4's execute_plan()). The
    optional redirector-cleanup and verify reports are accepted as
    extra keys on that same `results` dict -- `results["redirector_
    cleanup"]` (cleanup_redirectors()'s return shape) and `results
    ["verify"]` (verify_results()'s return shape) -- rather than as
    separate positional params, so callers that don't have them yet
    (or ever) can simply omit the keys; both are reported as "not run"
    when absent. `results["cancelled"]` (set by execute_plan() when a
    ScopedSlowTask cancel came through mid-batch) and `results["pre_
    restore_cleanup"]` (undo()'s pre-reversal redirector cleanup, run
    before the restore moves) are reported the same optional-key way
    when present, so a partial run's summary explains itself instead
    of just silently looking short."""
    results = results or {}
    moved = results.get("moved", [])
    failed = results.get("failed", [])
    renamed = [m for m in plan.get("moves", []) if "rename" in m["action"]]
    skips = plan.get("skips", [])

    lines = []
    if results.get("cancelled"):
        lines.append("RUN CANCELLED BY USER - partial results below.")
        lines.append("")
    lines.append("Sortilege run summary - %s" % plan.get("timestamp", ""))
    lines.append("Content root: %s" % plan.get("content_root", ""))
    grouping = plan.get("grouping")
    if grouping:
        lines.append("Grouping: by asset (%d kits, %d shared, %d loose)" % (
            grouping.get("kits", 0), grouping.get("shared", 0),
            grouping.get("loose", 0)))
    lines.append("")

    lines.append("Moved (%d):" % len(moved))
    for old, new in moved:
        lines.append("  %s -> %s" % (old, new))
    lines.append("")

    lines.append("Renamed (%d):" % len(renamed))
    for m in renamed:
        lines.append("  %s -> %s (%s)" % (m["path"], m["new_name"], m["action"]))
    lines.append("")

    lines.append("Failed (%d):" % len(failed))
    for old, new, error in failed:
        lines.append("  %s -> %s : %s" % (old, new, error))
    lines.append("")

    lines.append("Skipped (%d):" % len(skips))
    for reason, items in _group_by_reason(skips):
        lines.append("  %s (%d):" % (reason, len(items)))
        for s in items:
            lines.append("    %s" % s["path"])
    lines.append("")

    if "pre_restore_cleanup" in results:
        lines.append("Pre-restore redirector cleanup: %s" % _format_redirector_cleanup(
            results.get("pre_restore_cleanup")))
    lines.append("Redirector cleanup: %s" % _format_redirector_cleanup(
        results.get("redirector_cleanup")))
    verse_edits = results.get("verse_edits")
    if verse_edits is not None:
        lines.append(
            "Verse references rewritten: %d edit(s) across %d file(s), "
            "%d failed" % (
                verse_edits.get("edit_count", 0),
                len(verse_edits.get("edited", [])),
                len(verse_edits.get("failed", [])),
            ))
        skipped_bare_count = verse_edits.get("skipped_bare_count", 0)
        if skipped_bare_count:
            lines.append(
                "Verse bare-name edits skipped (fix manually): %d" % skipped_bare_count)
    verse_undo = results.get("verse_undo")
    if verse_undo is not None:
        lines.append(
            "Verse references restored: %d file(s), %d failed" % (
                len(verse_undo.get("restored", [])),
                len(verse_undo.get("failed", [])),
            ))
    empty_folders = results.get("empty_folders")
    if empty_folders is not None:
        removed_folders = empty_folders.get("removed", [])
        kept_folders = empty_folders.get("kept", [])
        lines.append("Cleaned up %d empty folder(s):" % len(removed_folders))
        for folder in removed_folders:
            lines.append("  %s" % folder)
        if kept_folders:
            lines.append("Kept %d folder(s):" % len(kept_folders))
            for folder, reason in kept_folders:
                lines.append("  %s (%s)" % (folder, reason))
    lines.append("Verify: %s" % _format_verify(results.get("verify")))

    timestamp = plan.get("timestamp") or datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    filename = "sortilege_report_%s.txt" % timestamp
    path = os.path.join(log_dir, filename)
    # Same temp-file + os.replace() atomic-write hardening as UndoLog.
    # _write() and write_plan_json(): a single-shot write, but a crash
    # mid-write must never leave a truncated report where a complete one
    # (or none at all) belongs.
    tmp_path = path + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    os.replace(tmp_path, path)
    return path


# =====================================================================
# === UNDO LOG ===
# =====================================================================
# A crash-safe, incrementally-written log of every move actually
# committed during an apply run. Every .record() call rewrites the
# whole file immediately -- if the process dies mid-run (editor crash,
# power loss, whatever), everything recorded up to that point is still
# on disk; nothing already moved is ever left un-undoable.

class UndoLog:
    """Use UndoLog.begin(log_dir, plan) to start one; do not construct
    directly. `.path` is the file it's writing to; `.record(old, new)`
    appends one move and rewrites the file on every call."""

    def __init__(self, path, created, moves, verse_backup_index=None):
        self.path = path
        self.created = created
        self.moves = moves
        self.verse_backup_index = verse_backup_index

    @classmethod
    def begin(cls, log_dir, plan):
        """Create sortilege_undo_<timestamp>.json in `log_dir` (empty
        moves list) and return the UndoLog instance that writes to it."""
        timestamp = plan.get("timestamp") or datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        filename = "sortilege_undo_%s.json" % timestamp
        path = os.path.join(log_dir, filename)
        log = cls(path, timestamp, [])
        log._write()
        return log

    def record(self, old_path, new_path):
        """Append one committed move and rewrite the file immediately."""
        self.moves.append({"from": old_path, "to": new_path})
        self._write()

    def set_verse_backup_index(self, path):
        """Record the path to this run's Verse-edit backup index (see
        apply_verse_edits()) so a LATER undo -- which only ever receives
        THIS file's own path, not the run's live results dict -- can find
        and restore the paired .verse backups too (see run_undo()).
        Rewrites the file immediately, same as record()."""
        self.verse_backup_index = path
        self._write()

    def _write(self):
        """Write the whole undo record atomically: a crash (or, as
        exercised in tests, a raised exception) partway through the dump
        must never truncate/corrupt the file that was already durably on
        disk from the PREVIOUS successful call. Write to a sibling
        "<path>.tmp" file first, then os.replace() it into place -- on
        POSIX and on Windows (Python 3.3+) os.replace() is an atomic
        rename, so self.path only ever flips between its previous
        complete content and its new complete content, never a partial
        write."""
        data = {"version": 1, "created": self.created, "moves": self.moves,
                 "verse_backup_index": self.verse_backup_index}
        tmp_path = self.path + ".tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        os.replace(tmp_path, self.path)


def load_undo_log(path):
    """Read an undo log file back into a plain dict. Fail-soft, same as
    every other user-input edge in this file: a missing/unreadable file
    or invalid JSON logs a clean warning naming the path and returns
    None -- never raises. Callers (undo()) treat None as "nothing to
    replay" and abort cleanly."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as exc:
        _console_warning(
            "Sortilege: could not read undo log %s (%s)." % (path, exc))
        return None


# =====================================================================
# === CRASH TRACER ===
# =====================================================================
# A UE hard crash (native access violation) bypasses Python's try/except
# entirely, and can lose the last buffered lines of UEFN's own Output Log
# right along with it. CrashTracer is a separate, deliberately dumb
# breadcrumb log built to survive that: every mark() call opens the trace
# file in append mode, writes ONE line, and flushes it to the OS before
# returning -- so even a hard crash a microsecond later still leaves that
# line on disk. STAGE-boundary marks (see run_apply()/run_undo()) also
# os.fsync() -- a handful of coarse, infrequent calls that force the OS to
# actually write the bytes rather than just buffer them, cheap because
# there are so few of them. The many high-volume per-item marks inside a
# big batch skip fsync and rely on the flush alone (still far more durable
# than Python's normal buffered file I/O). Every mark is also mirrored to
# _console() so it shows up in UEFN's own Output Log while the run is
# still alive, in case the trace file itself is never read.
#
# Tracing must never be the reason a run breaks or slows to a crawl:
# everything below is wrapped in its own try/except, and a tracing
# failure is always silent -- no warning spam, no raised exception, ever.

class CrashTracer:
    """Use CrashTracer.begin(log_dir) to start one; do not construct
    directly. `.path` is the file it writes to. `.mark(msg)` appends one
    breadcrumb line, flushed (and, for STAGE-boundary lines, fsync'd) to
    disk before returning -- never raises."""

    def __init__(self, path):
        self.path = path

    @classmethod
    def begin(cls, log_dir):
        """Create sortilege_trace_<timestamp>.log in `log_dir` -- the
        same directory (and the same datetime.now().strftime("%Y%m%d-
        %H%M%S") timestamp format) every other writer in this file uses
        for its own sortilege_plan_/sortilege_report_/sortilege_undo_
        artifact. The file is created (empty) immediately so its
        existence alone is proof the run got at least this far, even if
        nothing ever calls mark(). Never raises: a log_dir that can't be
        written to yields a tracer whose every mark() silently no-ops."""
        timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        filename = "sortilege_trace_%s.log" % timestamp
        path = os.path.join(log_dir, filename)
        try:
            with open(path, "a", encoding="utf-8"):
                pass
        except Exception:
            pass
        return cls(path)

    def mark(self, msg):
        """Append one breadcrumb line and flush it to disk immediately.
        STAGE-boundary lines (msg starting with the literal "STAGE ")
        additionally os.fsync() -- coarse and infrequent by construction
        (one entering/done pair per pipeline stage), so the extra
        disk-sync cost never lands on the many high-volume per-item
        marks. Always mirrored to _console() (prefixed "Sortilege
        TRACE: ") so it shows up in UEFN's Output Log too. Every failure
        here is swallowed -- tracing must never break or slow-crash the
        run it exists to diagnose."""
        line = str(msg)
        try:
            _console("Sortilege TRACE: " + line)
        except Exception:
            pass
        try:
            with open(self.path, "a", encoding="utf-8") as f:
                f.write(line + "\n")
                f.flush()
                if line.startswith("STAGE "):
                    try:
                        os.fsync(f.fileno())
                    except Exception:
                        pass
        except Exception:
            pass


def _effective_gc_enabled(caps, config):
    """The single place that decides whether a collect_garbage() call
    site should actually fire this run: the build must support it
    (caps.collect_garbage) AND the user must not have disabled it via
    CONFIG["DISABLE_GC"] AND SAFE_MODE must not be active (SAFE_MODE
    implies DISABLE_GC -- a "just move the assets, nothing else" run
    never garbage-collects either). run_apply()/run_undo() compute this
    once and pass it into execute_plan()/cleanup_redirectors() as
    `gc_enabled`; both default that parameter to plain caps.collect_
    garbage when it's left None, so any direct/test caller that predates
    this function sees byte-identical behavior."""
    if not caps.collect_garbage:
        return False
    if config.get("SAFE_MODE", False):
        return False
    if config.get("DISABLE_GC", False):
        return False
    return True


# =====================================================================
# === EXECUTOR ===
# =====================================================================
# Research-mandated strategy (docs/research-brief.md sections 2-3): the
# ONLY move primitive used is a per-asset EditorAssetLibrary.rename_asset
# loop -- never AssetTools.rename_assets()/AssetRenameData (confirmed
# constructor arg-order trap, no batch semantics we need). Every item is
# its own try/except so one bad asset can never abort the run, and every
# successful move is written to the undo log immediately (crash-safe).

class SortilegeCancelled(Exception):
    """Raised by a `progress` callable to stop a running batch cleanly.

    This is the ONE exception execute_plan()'s progress handling lets
    through (every other progress-callback exception is swallowed so a UI
    hiccup can't abort a batch). main() raises it from its ScopedSlowTask
    wrapper when should_cancel() turns true; anything else driving
    execute_plan() can raise it the same way. On cancellation,
    execute_plan() returns cleanly with everything completed so far plus
    results["cancelled"] = True -- and since every successful move was
    already recorded in the undo log the moment it happened, a cancelled
    batch is always fully undoable."""
    pass


def object_path(package_path):
    """"/Root/Folder/Name" -> "/Root/Folder/Name.Name" -- rename_asset (and
    every other asset-object API) takes a full object path, not just the
    package path build_plan()'s moves are keyed by."""
    name = package_path.rsplit("/", 1)[-1]
    return package_path + "." + name


def ensure_directories(plan):
    """make_directory() for every distinct dest folder in `plan`, only
    when it doesn't already exist. Never errors out the whole run -- one
    bad folder is logged and skipped, same as every other per-item op in
    this file."""
    if unreal is None:
        return
    lib = unreal.EditorAssetLibrary
    dest_folders = sorted(set(m["dest_folder"] for m in plan.get("moves", [])))
    for folder in dest_folders:
        try:
            if not lib.does_directory_exist(folder):
                lib.make_directory(folder)
        except Exception:
            try:
                unreal.log_warning("Sortilege: could not create folder %s" % folder)
            except Exception:
                pass


def execute_plan(plan, caps, undo_log, progress=None, tracer=None, gc_enabled=None):
    """Execute every move in `plan["moves"]` via a per-asset rename_asset
    call. Returns {"moved": [(old, new)], "failed": [(old, new, error)]}.

    Every item is its own try/except: on success (rename_asset truthy AND
    does_asset_exist(new) confirms it), the move is recorded in
    `undo_log` IMMEDIATELY -- so a crash mid-batch never loses an already
    -committed move -- and appended to "moved"; on any failure (a False
    return, a failed post-condition check, or a raised exception) the
    item goes to "failed" with a detail string and the batch continues.

    `progress`, if given, is called once per item -- BEFORE that item's
    move is attempted, so it doubles as the cancellation point: raising
    SortilegeCancelled from it stops the batch cleanly (that item and
    everything after it untouched, results["cancelled"] = True, and the
    undo log already durably holds every move committed so far). Any
    OTHER exception from the progress callable is swallowed so a UI
    hiccup can never abort a batch. Every 25 processed items,
    unreal.SystemLibrary.collect_garbage() runs -- research: this is what
    prevents loaded-asset memory pain on big batches.

    `tracer`, if given (a CrashTracer), gets one mark() immediately before
    each collect_garbage() call -- so a hard crash during/after GC still
    names it as the last thing that happened. `gc_enabled`, if given,
    overrides whether collect_garbage() fires at all; left at its default
    None, this is exactly caps.collect_garbage, i.e. today's behavior
    unchanged -- run_apply()/run_undo() are the only callers that compute
    and pass the CONFIG-aware effective flag (see _effective_gc_enabled).
    """
    moved = []
    failed = []
    results = {"moved": moved, "failed": failed}
    if unreal is None:
        return results

    lib = unreal.EditorAssetLibrary
    moves = plan.get("moves", [])
    ensure_directories(plan)

    if gc_enabled is None:
        gc_enabled = caps.collect_garbage

    try:
        for index, m in enumerate(moves, start=1):
            if progress is not None:
                try:
                    progress(m)
                except SortilegeCancelled:
                    raise
                except Exception:
                    pass

            old = m["path"]
            new = m["dest_path"]
            try:
                ok = lib.rename_asset(object_path(old), object_path(new))
                if ok and lib.does_asset_exist(new):
                    moved.append((old, new))
                    undo_log.record(old, new)
                else:
                    failed.append((old, new, "rename_asset returned a falsy result or "
                                              "the destination did not verify afterward"))
            except Exception as exc:
                failed.append((old, new, str(exc)))

            if gc_enabled and index % 25 == 0:
                if tracer is not None:
                    tracer.mark("collect_garbage (n=%d)" % index)
                try:
                    unreal.SystemLibrary.collect_garbage()
                except Exception:
                    pass
    except SortilegeCancelled:
        results["cancelled"] = True

    return results


def fix_soft_references(results, caps, tracer=None):
    """Best-effort fix-up of FSoftObjectPath references to every asset
    moved in this run, gated on caps.soft_path_rename. Builds one
    {old_object_path: new_object_path} map for the whole batch, then
    checks a COMPREHENSIVE package set with AssetTools.rename_
    referencing_soft_object_paths(packages_to_check, map) (research:
    "renames all FSoftObjectPath object[s] with the old asset path to the
    new one").

    Root-cause fix (field report): find_package_referencers_for_asset()
    is NOT a reliable index of every SOFT referencer on every UEFN build
    -- a live sort moved an asset, cleanup_redirectors() correctly saw no
    referencers for its redirector via that query and deleted it, but a
    DIFFERENT asset still held a soft reference to the old path that this
    function had never even attempted to fix, because that asset was
    never in its (then referencer-graph-scoped) package list either.
    "soft references a missing package" was the result.

    The fix: `packages_to_check` is now the union of (a) the SAME
    find_package_referencers_for_asset() query as before, across BOTH the
    OLD and the NEW path of every moved pair (kept as a belt-and-braces
    net for any referencer living outside the discovered content roots,
    e.g. an Engine/plugin mount), and (b) EVERY asset package under every
    discovered content root (discover_content_roots() + list_assets()) --
    so every soft reference to a moved asset gets a chance to be
    repointed, regardless of whether the referencer-graph query above
    happened to surface it. Handing rename_referencing_soft_object_paths
    a package that has nothing to rewrite is a harmless no-op for that
    package.

    The comprehensive package list is split into CHUNK_SIZE-sized batches
    (a few hundred each) so one apply on a very large project never hands
    a single native call an unbounded list; each chunk is its own try/
    except -- one bad chunk is fail-soft (does not abort the rest of the
    batch). `tracer`, if given (a CrashTracer), gets one mark() before the
    chunked calls begin, naming the total comprehensive package count --
    run_apply() is the only caller that passes this (gated by CONFIG
    ["FIX_SOFT_REFERENCES"] and SAFE_MODE; see there).

    Returns True when every chunk's call succeeded, False if at least one
    chunk raised, and None when the capability is simply absent on this
    build -- redirectors left in place still resolve soft refs correctly,
    so nothing breaks when this returns None; it just means those soft
    refs survive as redirector hops instead of being rewritten in
    place."""
    if not caps.soft_path_rename or unreal is None:
        return None

    moved = (results or {}).get("moved", [])
    if not moved:
        return True

    lib = unreal.EditorAssetLibrary
    old_to_new = {}
    referencer_packages = set()
    for old, new in moved:
        old_to_new[object_path(old)] = object_path(new)
        for candidate in (old, new):
            try:
                referencer_packages.update(lib.find_package_referencers_for_asset(candidate))
            except Exception:
                continue

    # COMPREHENSIVE NET -- see docstring above: every project package,
    # not just the referencer-graph hits collected above.
    for root in discover_content_roots():
        try:
            referencer_packages.update(
                lib.list_assets(root, recursive=True, include_folder=False))
        except Exception:
            continue

    try:
        tools = unreal.AssetToolsHelpers.get_asset_tools()
    except Exception:
        return False

    sorted_packages = sorted(referencer_packages)
    if tracer is not None:
        tracer.mark("rename_referencing_soft_object_paths (%d packages)" % len(sorted_packages))

    CHUNK_SIZE = 300
    if sorted_packages:
        chunks = [sorted_packages[i:i + CHUNK_SIZE]
                  for i in range(0, len(sorted_packages), CHUNK_SIZE)]
    else:
        # No candidate packages at all -- still make exactly one call
        # (with an empty list), matching the pre-comprehensive behavior
        # of always calling the API once per batch of moves.
        chunks = [[]]

    all_ok = True
    for chunk in chunks:
        try:
            tools.rename_referencing_soft_object_paths(chunk, old_to_new)
        except Exception:
            all_ok = False
    return all_ok


# =====================================================================
# === REDIRECTOR CLEANUP ===
# =====================================================================
# There is NO Python fix-up-redirectors API in any shipped engine version
# (research-CONFIRMED) -- the manual recipe below is the primary, real
# path today. The caps.fix_up_redirectors probe is kept purely as
# future-proofing for a hypothetical later engine build; when present it
# is tried first and anything it can't clear falls through to the manual
# recipe. Scope is ALWAYS the union of source + dest folders the plan
# actually touched -- never a whole-project sweep (research: that's the
# documented pain case for redirector cleanup).

def find_redirectors(scope_folders, caps):
    """Return every redirector package path found under `scope_folders`
    (each folder scanned recursively). Primary strategy: list_assets()
    then find_asset_data(p).is_redirector() per item, in try/except.
    Fallback (only if AssetData.is_redirector is missing on this build):
    an asset-registry ARFilter query for class ObjectRedirector, using
    the class_paths_filter variant when caps.class_paths_filter."""
    if unreal is None:
        return []

    lib = unreal.EditorAssetLibrary
    results = []
    seen = set()

    try:
        has_is_redirector = hasattr(unreal.AssetData, "is_redirector")
    except Exception:
        has_is_redirector = False

    for folder in scope_folders:
        if has_is_redirector:
            try:
                paths = lib.list_assets(folder, recursive=True, include_folder=False)
            except Exception:
                paths = []
            for p in paths:
                try:
                    data = lib.find_asset_data(p)
                    if data is not None and data.is_redirector():
                        if p not in seen:
                            seen.add(p)
                            results.append(p)
                except Exception:
                    continue
            continue

        # Fallback: is_redirector() isn't available on this build at all.
        try:
            registry = unreal.AssetRegistryHelpers.get_asset_registry()
            if caps.class_paths_filter and hasattr(unreal, "TopLevelAssetPath"):
                ar_filter = unreal.ARFilter(
                    class_paths=[unreal.TopLevelAssetPath("ObjectRedirector")],
                    package_paths=[folder], recursive_paths=True)
            else:
                ar_filter = unreal.ARFilter(
                    class_names=["ObjectRedirector"],
                    package_paths=[folder], recursive_paths=True)
            for ad in registry.get_assets(ar_filter):
                try:
                    p = str(ad.package_name)
                except Exception:
                    continue
                if p not in seen:
                    seen.add(p)
                    results.append(p)
        except Exception:
            continue

    return results


def _registry_referencers_or_none(path, caps, include_hard=True, include_soft=True):
    """Query unreal.AssetRegistry.get_referencers(path, options) for every
    package that references `path` (hard and/or soft, per the include_
    flags), gated on caps.referencer_query. Returns None -- "could not
    double-check" -- when the capability is absent, the registry/options
    can't be constructed, or the call itself raises (or itself returns
    None, which the real API's own docs allow for "operation could not be
    completed"). Callers treat None conservatively but NOT identically:
    cleanup_redirectors' CONSERVATIVE_REDIRECTORS check treats None the
    same as "found a referencer" (never delete on an unconfirmed empty
    result); verify_results' broken_soft_refs check treats None as
    "nothing to report" (an absent capability must not manufacture a
    false failure on every such build) -- see each call site."""
    if not caps.referencer_query or unreal is None:
        return None
    try:
        registry = unreal.AssetRegistryHelpers.get_asset_registry()
        try:
            options = unreal.AssetRegistryDependencyOptions(
                include_hard_package_references=include_hard,
                include_soft_package_references=include_soft)
        except Exception:
            options = unreal.AssetRegistryDependencyOptions()
        refs = registry.get_referencers(path, options)
    except Exception:
        return None
    if refs is None:
        return None
    return list(refs)


def cleanup_redirectors(scope_folders, caps, tracer=None, gc_enabled=None,
                         progress_hook=None):
    """Clean up every redirector found under `scope_folders`. Returns
    {"fixed": [paths], "remaining": [(path, why)], "method": str}.

    `tracer`, if given (a CrashTracer), gets one mark() immediately
    before every destructive/native call this makes: each resave (flush-
    only -- can be high volume), each delete_asset(), and each
    collect_garbage(). `gc_enabled`, if given, overrides whether
    collect_garbage() fires at all; left at its default None, this is
    exactly caps.collect_garbage, i.e. today's behavior unchanged -- see
    execute_plan()'s matching parameter and _effective_gc_enabled().

    `progress_hook`, if given, is called as progress_hook(processed,
    total) every 5 items processed in EACH of the two manual-recipe
    phases below (the part of this pass that can run for minutes on a
    big redirector batch, with nothing else in this file pumping the
    GUI's window in the meantime) -- `total` is the size of whichever
    phase's own worklist is currently running (the unique-referencer
    count in the resave phase, the redirector count in the delete phase),
    so it always matches what is actually being iterated. Every call is
    its own try/except and a no-op when progress_hook is None (the
    console path is unaffected).

    Chain: (1) if caps.fix_up_redirectors (future-proofing -- no shipped
    engine has this today), load each redirector's own asset object via
    find_asset_data(p).get_asset() and hand the batch to AssetTools.
    fix_up_redirectors(); whatever is confirmed gone afterward counts as
    fixed, anything left over falls through to (2); (2) the manual
    recipe, the real path today, now BATCHED across 3 passes instead of
    one loop that repeated work per redirector:

      (a) GATHER -- for each remaining redirector p, find its referencers
          (load_assets_to_confirm=True) and fold every referencer path
          into one deduplicated `all_referencers` list (first-seen
          order). A redirector whose referencer lookup itself raises
          goes straight to "remaining" with the error text here, exactly
          like the old single loop, and is excluded from (b)/(c).

      (b) RESAVE -- load + resave (only_if_is_dirty=False forces the
          resave regardless of dirty state) each package in
          `all_referencers` exactly ONCE for the whole batch. Resaving a
          package rewrites ALL of its stale redirector-path references in
          one write, so one resave per unique referencer is both
          sufficient and -- unlike the old per-redirector loop, which
          could load+resave the SAME shared referencer once per
          redirector it happened to touch -- never redundant.

      (c) DELETE -- for each remaining redirector (skipping any that
          already failed in (a)), re-check its referencer list; still
          non-empty -> remaining with "still referenced by: ...". EMPTY
          is no longer an automatic delete: when CONFIG["CONSERVATIVE_
          REDIRECTORS"] is True (the default), an empty find_package_
          referencers_for_asset() result is ALSO double-checked against
          AssetRegistry.get_referencers() (hard+soft) via _registry_
          referencers_or_none() -- see its docstring and CONFIG's own
          comment for the field-reported incident this exists to close.
          Only when BOTH checks confirm zero referencers does delete_
          asset() + verify-gone -> fixed actually run; otherwise the
          redirector lands in remaining with "kept: still referenced
          (possible soft reference)" -- covering a referencer either
          check found, either check raising, and the capability being
          unavailable altogether (nothing to double-check with). Every
          item in every phase is its own try/except -- an exception moves
          that item to remaining with the error text instead of aborting
          the batch.

    With CONFIG["CONSERVATIVE_REDIRECTORS"] at its default (True), a
    redirector that used to get silently deleted on an unconfirmed-empty
    referencer list now survives into `remaining` instead -- the one
    deliberate behavior change from the old per-redirector loop. With it
    set to False, the {fixed, remaining} outcome is identical to the old
    algorithm for the same input; only the number of resave calls (and
    hence wall-clock time on a batch with shared referencers) changes.

    Gated collect_garbage() every 10 packages resaved in (b) AND,
    independently, every 10 redirectors processed in (c) (two separate
    counters -- research: mirrors the community fixup tooling's own
    batch-and-GC throttle so neither phase ever sweeps unbounded
    memory)."""
    result = {"fixed": [], "remaining": [], "method": "manual"}
    if unreal is None:
        return result

    lib = unreal.EditorAssetLibrary
    redirector_paths = find_redirectors(scope_folders, caps)

    handled = set()
    used_fixup = False

    if gc_enabled is None:
        gc_enabled = caps.collect_garbage

    if caps.fix_up_redirectors and redirector_paths:
        try:
            tools = unreal.AssetToolsHelpers.get_asset_tools()
            objects = []
            candidate_paths = []
            for p in redirector_paths:
                try:
                    data = lib.find_asset_data(p)
                    if data is None:
                        continue
                    objects.append(data.get_asset())
                    candidate_paths.append(p)
                except Exception:
                    continue
            if objects:
                tools.fix_up_redirectors(objects)
                used_fixup = True
            for p in candidate_paths:
                try:
                    still_there = lib.does_asset_exist(p)
                except Exception:
                    still_there = True
                if not still_there:
                    result["fixed"].append(p)
                    handled.add(p)
        except Exception:
            pass

    remaining_paths = [p for p in redirector_paths if p not in handled]
    total_remaining = len(remaining_paths)

    # --- (a) GATHER: one referencer lookup per redirector, folded into a
    # single deduplicated worklist (first-seen order) -----------------
    referencers_by_redirector = {}
    all_referencers = []
    seen_referencers = set()
    for p in remaining_paths:
        try:
            referencers = lib.find_package_referencers_for_asset(p, True)
        except Exception as exc:
            result["remaining"].append((p, str(exc)))
            continue
        referencers_by_redirector[p] = referencers
        for ref in referencers:
            if ref not in seen_referencers:
                seen_referencers.add(ref)
                all_referencers.append(ref)

    # --- (b) RESAVE: each unique referencer, exactly once ------------
    total_referencers = len(all_referencers)
    resave_gc_count = 0
    for index, ref in enumerate(all_referencers, start=1):
        if progress_hook is not None and index % 5 == 0:
            try:
                progress_hook(index, total_referencers)
            except Exception:
                pass
        try:
            if tracer is not None:
                tracer.mark("resave referencer: %s" % ref)
            obj = lib.load_asset(ref)
            if obj is not None:
                lib.save_loaded_asset(obj, only_if_is_dirty=False)
        except Exception:
            pass

        resave_gc_count += 1
        if gc_enabled and resave_gc_count % 10 == 0:
            if tracer is not None:
                tracer.mark("collect_garbage (n=%d)" % resave_gc_count)
            try:
                unreal.SystemLibrary.collect_garbage()
            except Exception:
                pass

    # --- (c) DELETE: re-check + remove, skipping anything (a) already
    # sent to "remaining" -- index/total stay over the FULL remaining_
    # paths list (not just the ones that survived (a)) so progress_hook's
    # cadence is byte-identical to the old single-loop numbering ------
    #
    # P0 SAFETY NET (CONFIG["CONSERVATIVE_REDIRECTORS"], default True):
    # find_package_referencers_for_asset() alone is not a reliable index
    # of every SOFT referencer on every UEFN build (field report -- see
    # fix_soft_references()'s docstring for the exact incident this
    # closes). Before trusting an empty `still_refs`, ALSO double-check
    # with the asset registry's own get_referencers() (hard+soft) when
    # this build exposes it. Delete only if the UNION of both checks is
    # empty; if either reports a referencer, either raises, or get_
    # referencers is simply unavailable (no way to double-check at all),
    # KEEP the redirector instead of risking a broken reference. When
    # CONSERVATIVE_REDIRECTORS is False, the old single-check criterion
    # applies unchanged.
    conservative = bool(CONFIG.get("CONSERVATIVE_REDIRECTORS", True))
    delete_gc_count = 0
    for index, p in enumerate(remaining_paths, start=1):
        if progress_hook is not None and index % 5 == 0:
            try:
                progress_hook(index, total_remaining)
            except Exception:
                pass

        if p in referencers_by_redirector:
            try:
                still_refs = lib.find_package_referencers_for_asset(p, False)
            except Exception as exc:
                result["remaining"].append((p, str(exc)))
                still_refs = None
            else:
                keep_reason = None
                if still_refs:
                    keep_reason = "still referenced by: " + ", ".join(still_refs)
                elif conservative:
                    registry_refs = _registry_referencers_or_none(p, caps)
                    if registry_refs is None or len(registry_refs) > 0:
                        keep_reason = "kept: still referenced (possible soft reference)"

                if keep_reason is not None:
                    result["remaining"].append((p, keep_reason))
                else:
                    try:
                        if tracer is not None:
                            tracer.mark("delete_asset redirector: %s" % p)
                        lib.delete_asset(p)
                        if not lib.does_asset_exist(p):
                            result["fixed"].append(p)
                        else:
                            result["remaining"].append((p, "delete_asset did not remove it"))
                    except Exception as exc:
                        result["remaining"].append((p, str(exc)))
        # else: (a) already recorded this redirector into result["remaining"].

        delete_gc_count += 1
        if gc_enabled and delete_gc_count % 10 == 0:
            if tracer is not None:
                tracer.mark("collect_garbage (n=%d)" % delete_gc_count)
            try:
                unreal.SystemLibrary.collect_garbage()
            except Exception:
                pass

    if used_fixup and not remaining_paths:
        result["method"] = "fix_up_redirectors"
    else:
        result["method"] = "manual"

    return result


# =====================================================================
# === VERIFY ===
# =====================================================================

def verify_results(results, scope_folders, caps):
    """Double-check an apply run's outcome. Returns {"ok": bool,
    "missing": [...], "old_paths_alive": [...], "leftover_redirectors":
    [...], "referencer_spot_checks": int, "broken_soft_refs": [(referencer,
    old_path), ...]}.

    For every moved (old, new) pair: `new` must exist (else -> missing);
    `old` must no longer resolve to a REAL (non-redirector) asset --
    a leftover redirector at `old` is expected/fine, only a genuine live
    asset there is a failure (-> old_paths_alive); find_package_
    referencers_for_asset(new) must run without raising (a spot check,
    counted but not scored). Leftover redirectors anywhere under
    `scope_folders` are listed for information only -- they resolve
    correctly, they're just clutter, so they never affect `ok`.

    P2 (soft-reference bounty fix): if `old` no longer resolves AT ALL --
    no redirector left to hop through, no live asset either -- but some
    OTHER package still SOFT-references that exact old path (via
    AssetRegistry.get_referencers(), soft-only, gated on caps.
    referencer_query), that is a genuinely BROKEN reference: the exact
    failure mode CONSERVATIVE_REDIRECTORS (cleanup_redirectors) and the
    comprehensive rewrite (fix_soft_references) exist to prevent. Each
    hit is recorded as a (referencer_package, old_path) pair in
    "broken_soft_refs". A leftover redirector at `old` is NOT broken --
    it still resolves the soft reference correctly, just with an extra
    hop -- so this check only ever runs once `old` is entirely gone.
    When caps.referencer_query is unavailable, this check is silently
    skipped (like the referencer_spot_checks above, it degrades to "not
    checked", never to a false "broken").

    `ok` = no missing AND no old_paths_alive AND no broken_soft_refs."""
    out = {"ok": True, "missing": [], "old_paths_alive": [],
           "leftover_redirectors": [], "referencer_spot_checks": 0,
           "broken_soft_refs": []}
    if unreal is None:
        return out

    lib = unreal.EditorAssetLibrary
    moved = (results or {}).get("moved", [])

    for old, new in moved:
        try:
            exists = lib.does_asset_exist(new)
        except Exception:
            exists = False
        if not exists:
            out["missing"].append(new)

        try:
            old_data = lib.find_asset_data(old)
        except Exception:
            old_data = None

        old_is_real_asset = False
        if old_data is not None:
            try:
                old_is_real_asset = not old_data.is_redirector()
            except Exception:
                old_is_real_asset = True
        if old_is_real_asset:
            out["old_paths_alive"].append(old)

        try:
            lib.find_package_referencers_for_asset(new)
            out["referencer_spot_checks"] += 1
        except Exception:
            pass

        try:
            old_gone_entirely = not lib.does_asset_exist(old)
        except Exception:
            old_gone_entirely = False
        if old_gone_entirely:
            registry_refs = _registry_referencers_or_none(
                old, caps, include_hard=False, include_soft=True)
            for ref in (registry_refs or []):
                entry = (str(ref), old)
                if entry not in out["broken_soft_refs"]:
                    out["broken_soft_refs"].append(entry)

    for p in find_redirectors(scope_folders, caps):
        if p not in out["leftover_redirectors"]:
            out["leftover_redirectors"].append(p)

    out["ok"] = (
        (not out["missing"])
        and (not out["old_paths_alive"])
        and (not out["broken_soft_refs"])
    )
    return out


# =====================================================================
# === CLEANUP EMPTY FOLDERS ===
# =====================================================================

def cleanup_empty_folders(plan, config=None, tracer=None, progress_hook=None):
    """Post-flight empty-folder sweep. Candidates are every distinct
    SOURCE folder of the plan's moves PLUS every ancestor of each, up to
    (never including) the discovered content roots. Processed deepest
    first, so a deleted child naturally lets its parent read empty on
    the same pass. A folder is deleted only when list_assets(folder,
    recursive=True, include_folder=False) comes back empty -- the
    registry includes redirector entries, so a folder still holding a
    leftover redirector correctly reads NON-empty and survives (which is
    why callers run this AFTER cleanup_redirectors) -- AND a second
    include_folder=True listing shows no subfolders either: the real
    delete_directory is a FORCE delete (confirmed live), so a folder
    whose only content is an empty subfolder must be kept, not deleted
    out from under it.

    Never deleted, ever: the content roots themselves, protected paths
    (is_protected_path), folders under CONFIG["EXCLUDE_FOLDERS"], and
    anything outside the discovered roots. Each delete is its own
    try/except -- a failure is logged and recorded, never fatal.

    Callers (run_apply()/run_undo()) gate this on CONFIG
    ["CLEAN_EMPTY_FOLDERS"] -- this function always does the work when
    called. Returns {"removed": [paths], "kept": [(path, reason)]},
    attached by callers as results["empty_folders"] and surfaced in the
    summary report and the GUI results bar.

    `tracer`, if given (a CrashTracer), gets one mark() immediately
    before every delete_directory() call, naming the exact folder about
    to be force-deleted.

    `progress_hook`, if given, is called as progress_hook(processed,
    total) every 5 candidate folders visited below -- `total` is
    len(ordered), the full candidate list this function walks, so a big
    sweep (the other minutes-long post-move stage nothing used to pump
    the GUI's window during) keeps producing progress ticks regardless
    of whether any given candidate is actually removed, kept, or
    errors out. Every call is its own try/except and a no-op when
    progress_hook is None (the console path is unaffected)."""
    result = {"removed": [], "kept": []}
    if unreal is None:
        return result
    if config is None:
        config = CONFIG

    lib = unreal.EditorAssetLibrary
    roots = set(r.rstrip("/") for r in discover_content_roots() if r)
    exclude_folders = config.get("EXCLUDE_FOLDERS", [])

    candidates = set()
    for m in plan.get("moves", []):
        path = m.get("path", "")
        if "/" not in path:
            continue
        folder = path.rsplit("/", 1)[0]
        while folder and folder not in roots:
            candidates.add(folder)
            if "/" not in folder[1:]:
                break
            parent = folder.rsplit("/", 1)[0]
            if not parent or parent == folder:
                break
            folder = parent

    ordered = sorted(candidates, key=lambda f: (f.count("/"), f), reverse=True)
    total_candidates = len(ordered)
    for index, folder in enumerate(ordered, start=1):
        if progress_hook is not None and index % 5 == 0:
            try:
                progress_hook(index, total_candidates)
            except Exception:
                pass
        if is_protected_path(folder):
            result["kept"].append((folder, "protected system folder"))
            continue
        if _is_excluded(folder, exclude_folders):
            result["kept"].append((folder, "excluded folder"))
            continue
        in_any_root = any(
            folder == root or folder.startswith(root + "/") for root in roots)
        if not in_any_root:
            result["kept"].append((folder, "outside project content"))
            continue
        try:
            remaining = lib.list_assets(folder, recursive=True, include_folder=False)
        except Exception as exc:
            result["kept"].append((folder, "could not inspect: %s" % exc))
            continue
        if remaining:
            result["kept"].append((folder, "not empty"))
            continue
        # Second listing WITH folders: the real delete_directory is a
        # FORCE delete (confirmed live in UEFN) -- it takes everything
        # under the folder with it, including empty subfolders the
        # asset-only listing above cannot see. Any folder entry here
        # means this candidate is NOT safe to delete. Deepest-first
        # ordering keeps nested shell chains collapsing: genuinely swept
        # children are already gone from the registry by the time their
        # parent is evaluated.
        try:
            folder_entries = lib.list_assets(folder, recursive=True, include_folder=True)
        except Exception as exc:
            result["kept"].append((folder, "could not inspect: %s" % exc))
            continue
        if folder_entries:
            result["kept"].append((folder, "contains subfolders"))
            continue
        # Reverse-containment guard, regardless of what the registry
        # listed: an EXCLUDE_FOLDERS entry that equals or sits UNDER this
        # candidate means deleting it would destroy (or pre-destroy) an
        # explicitly protected location -- keep it even if nothing is
        # registered there yet.
        contains_excluded = False
        for raw in exclude_folders:
            excl = str(raw).rstrip("/")
            if not excl:
                continue
            if excl == folder or excl.startswith(folder + "/"):
                contains_excluded = True
                break
        if contains_excluded:
            result["kept"].append((folder, "would remove excluded folder"))
            continue
        try:
            if tracer is not None:
                tracer.mark("delete_directory: %s" % folder)
            if lib.delete_directory(folder):
                result["removed"].append(folder)
            else:
                result["kept"].append((folder, "delete_directory refused"))
                _console_warning(
                    "Sortilege: could not remove empty folder %s "
                    "(delete_directory refused)." % folder)
        except Exception as exc:
            result["kept"].append((folder, str(exc)))
            _console_warning(
                "Sortilege: could not remove empty folder %s (%s)." % (
                    folder, exc))

    return result


# =====================================================================
# === UNDO ===
# =====================================================================

def _reversed_moves_from_log(data):
    """Build execute_plan()-shaped move dicts that replay `data["moves"]`
    (an UndoLog's loaded {"from": old, "to": new} entries) backwards:
    new -> old, last recorded first."""
    reversed_moves = []
    for entry in reversed(data.get("moves", [])):
        current_path = entry.get("to")
        original_path = entry.get("from")
        if not current_path or not original_path:
            continue
        reversed_moves.append({
            "path": current_path,
            "name": current_path.rsplit("/", 1)[-1],
            "class_name": "",
            "category": "",
            "dest_folder": original_path.rsplit("/", 1)[0] if "/" in original_path else "",
            "dest_path": original_path,
            "new_name": original_path.rsplit("/", 1)[-1],
            "action": "undo-move",
        })
    return reversed_moves


def run_undo(undo_log_path, caps, echo_preview=True, status_callback=None):
    """The ungated undo mechanics -- the mirror of run_apply(): load the
    undo log at `undo_log_path`, print the about-to-restore preview lines
    (suppressed with echo_preview=False when the caller already printed
    them, i.e. console undo() below), clear the redirectors squatting on
    the restore destinations, replay every recorded move new -> old (LAST
    recorded first) through execute_plan() on a minimal synthetic plan,
    then run the scoped redirector cleanup + verify passes and write the
    summary report.

    Deliberately does NOT gate anything itself -- gating is entirely the
    caller's job, exactly like run_apply(): the console `undo` mode wraps
    this in the flag + EditorDialog gates (undo() below), and the GUI's
    "Undo this run" button calls this directly because its own tkinter
    messagebox confirm IS the deliberate confirm in GUI context (popping
    the native EditorDialog on top of it would be a double-confirm).

    Returns execute_plan()'s results dict with "pre_restore_cleanup",
    "redirector_cleanup", "verify", and "report_path" layered on; or
    {"moved": [], "failed": [], "blocked": "unreadable undo log"} when
    the log can't be read (nothing touched).

    The reversal run mints its OWN fresh timestamp for every artifact it
    writes (its undo log, its summary report). The original run's
    "created" stamp is used in display text only -- reusing it for the
    reversal's artifacts would make UndoLog.begin() truncate the very
    undo file being replayed (and write_summary() overwrite the original
    run's report) whenever both live in the same log dir. The "-undo"
    suffix additionally guarantees no collision with any forward run's
    artifacts even inside the same wall-clock second.

    A fresh CrashTracer is started here (same log dir) and STAGE-bracket
    marks every sub-stage below ("pre-restore-cleanup", "reversed-
    replay", "redirector-cleanup", "empty-folder-sweep", "verify",
    "summary"), so the last unmatched ">>> entering" line in the trace
    file names whichever one a hard crash interrupted. CONFIG["SAFE_
    MODE"] skips pre-restore-cleanup, redirector-cleanup, and empty-
    folder-sweep (and every collect_garbage() call) the same way it does
    in run_apply() -- a loud "SAFE_MODE active: skipping <stage>" mark
    replaces the entering/done pair for each one skipped.

    `status_callback`, if given, mirrors run_apply()'s own: one call with
    a human-readable string before each stage that actually runs
    ("Preparing restore locations...", "Restoring assets...", "Cleaning
    up redirectors...", "Removing empty folders...", "Verifying...",
    "Writing report..."), and is also threaded through as the progress_
    hook for the pre-restore and main redirector-cleanup passes and the
    empty-folder sweep -- see run_apply()'s docstring for the full
    rationale (this closes the same "frozen window for minutes" gap on
    the undo side). Every call is wrapped in its own try/except and is a
    no-op when status_callback is None."""
    def _status(text):
        if status_callback is not None:
            try:
                status_callback(text)
            except Exception:
                pass

    data = load_undo_log(undo_log_path)
    if data is None:
        # load_undo_log() already logged why the file couldn't be read;
        # nothing has been touched, so just abort with a blocked result.
        return {"moved": [], "failed": [], "blocked": "unreadable undo log"}
    reversed_moves = _reversed_moves_from_log(data)

    reversal_timestamp = (
        datetime.datetime.now().strftime("%Y%m%d-%H%M%S") + "-undo")

    preview_plan = {
        "moves": reversed_moves,
        "skips": [],
        "stats": {
            "scanned": len(reversed_moves), "moves": len(reversed_moves),
            "renames": 0, "skips": 0, "by_category": {},
        },
        "content_root": "",
        "sort_root": "",
        "timestamp": reversal_timestamp,
    }

    if echo_preview:
        _console("Sortilege undo: about to restore %d move(s) from run %s:" % (
            len(reversed_moves), data.get("created", "?")))
        for m in reversed_moves:
            _console("  %s -> %s" % (m["path"], m["dest_path"]))

    # log_dir is resolved (and the crash tracer started) up front --
    # earlier than the pre-Task-diagnostics version of this function --
    # so the pre-restore cleanup below (the first destructive call this
    # function can make) is traced too, not just everything after it.
    log_dir = resolve_log_dir(CONFIG)
    tracer = CrashTracer.begin(log_dir)
    safe_mode = bool(CONFIG.get("SAFE_MODE", False))
    gc_enabled = _effective_gc_enabled(caps, CONFIG)

    # Every destination we're about to restore into is still squatted on
    # by the redirector the forward move left behind. Clear them with the
    # same referencer-safe cleanup used everywhere else: resave
    # referencers, delete ONLY when the referencer list is confirmed
    # empty (delete_asset is a FORCE delete -- it must never be called on
    # a redirector something still points at, even here). A redirector
    # this cleanup cannot clear stays put, and that item's reverse rename
    # below then fails loudly into results["failed"] -- the guard rail
    # holds; the rest of the batch still restores.
    restore_folders = sorted(set(
        m["dest_folder"] for m in reversed_moves if m["dest_folder"]))
    pre_restore_cleanup = None
    if safe_mode:
        tracer.mark("SAFE_MODE active: skipping pre-restore-cleanup")
    elif restore_folders:
        _status("Preparing restore locations...")
        tracer.mark("STAGE >>> entering: pre-restore-cleanup")

        def _pre_restore_progress(done, total):
            _status("Preparing restore locations %d/%d..." % (done, total))

        pre_restore_cleanup = cleanup_redirectors(
            restore_folders, caps, tracer=tracer, gc_enabled=gc_enabled,
            progress_hook=_pre_restore_progress)
        tracer.mark("STAGE <<< done: pre-restore-cleanup (fixed=%d remaining=%d)" % (
            len(pre_restore_cleanup["fixed"]), len(pre_restore_cleanup["remaining"])))

    reversal_undo_log = UndoLog.begin(log_dir, preview_plan)

    _status("Restoring assets...")
    tracer.mark("STAGE >>> entering: reversed-replay")
    results = execute_plan(preview_plan, caps, reversal_undo_log,
                            tracer=tracer, gc_enabled=gc_enabled)
    tracer.mark("STAGE <<< done: reversed-replay (moved=%d failed=%d)" % (
        len(results.get("moved", [])), len(results.get("failed", []))))
    # Attached even when None (no restore folders needed cleaning, or
    # SAFE_MODE skipped it) so a partially-failed undo's summary always
    # shows whether this pre-pass ran and what it found -- see
    # write_summary()'s "pre_restore_cleanup" handling above.
    results["pre_restore_cleanup"] = pre_restore_cleanup

    scope = set()
    for m in reversed_moves:
        if "/" in m["path"]:
            scope.add(m["path"].rsplit("/", 1)[0])
        if "/" in m["dest_path"]:
            scope.add(m["dest_path"].rsplit("/", 1)[0])
    scope_folders = sorted(scope)

    if safe_mode:
        tracer.mark("SAFE_MODE active: skipping redirector-cleanup")
    else:
        _status("Cleaning up redirectors...")
        tracer.mark("STAGE >>> entering: redirector-cleanup")

        def _redirector_progress(done, total):
            _status("Cleaning up redirectors %d/%d..." % (done, total))

        results["redirector_cleanup"] = cleanup_redirectors(
            scope_folders, caps, tracer=tracer, gc_enabled=gc_enabled,
            progress_hook=_redirector_progress)
        tracer.mark("STAGE <<< done: redirector-cleanup (fixed=%d remaining=%d)" % (
            len(results["redirector_cleanup"]["fixed"]),
            len(results["redirector_cleanup"]["remaining"])))

    # Mirrors run_apply()'s verse-references stage, but data-dependent
    # rather than CONFIG-dependent: whether THIS run's original apply
    # ever produced a Verse backup to restore is a fact recorded in the
    # undo log itself (data["verse_backup_index"]), not something an
    # undo-time CONFIG flag could sensibly gate -- there is nothing to
    # restore if the original apply never touched a .verse file. SAFE_
    # MODE still forces it off regardless, same skip-mark convention as
    # pre-restore-cleanup above.
    verse_backup_index = data.get("verse_backup_index")
    if safe_mode:
        tracer.mark("SAFE_MODE active: skipping verse-undo")
    elif verse_backup_index:
        _status("Restoring Verse references...")
        tracer.mark("STAGE >>> entering: verse-undo")
        results["verse_undo"] = undo_verse_edits(verse_backup_index)
        tracer.mark("STAGE <<< done: verse-undo (restored=%d failed=%d)" % (
            len(results["verse_undo"]["restored"]), len(results["verse_undo"]["failed"])))

    # Sweep the sorted folders the restore just vacated (the reversal
    # plan's SOURCE folders), after redirector cleanup for the same
    # reason as run_apply(): a folder holding only a leftover redirector
    # must first be emptied before it can read empty.
    do_empty_folders = CONFIG.get("CLEAN_EMPTY_FOLDERS", True) and not safe_mode
    if safe_mode:
        tracer.mark("SAFE_MODE active: skipping empty-folder-sweep")
    if do_empty_folders:
        _status("Removing empty folders...")
        tracer.mark("STAGE >>> entering: empty-folder-sweep")

        def _empty_folder_progress(done, total):
            _status("Removing empty folders %d/%d..." % (done, total))

        results["empty_folders"] = cleanup_empty_folders(
            preview_plan, CONFIG, tracer=tracer, progress_hook=_empty_folder_progress)
        tracer.mark("STAGE <<< done: empty-folder-sweep (removed=%d kept=%d)" % (
            len(results["empty_folders"]["removed"]),
            len(results["empty_folders"]["kept"])))

    _status("Verifying...")
    tracer.mark("STAGE >>> entering: verify")
    results["verify"] = verify_results(results, scope_folders, caps)
    tracer.mark("STAGE <<< done: verify (ok=%s)" % results["verify"].get("ok"))

    _status("Writing report...")
    tracer.mark("STAGE >>> entering: summary")
    results["report_path"] = write_summary(preview_plan, results, log_dir)
    tracer.mark("STAGE <<< done: summary")
    return results


def undo(undo_log_path, caps):
    """The console undo flow: print a preview of what is about to be
    restored, pass the same two-gate confirm as apply (CONFIG
    ["I_UNDERSTAND_THIS_MODIFIES_MY_PROJECT"] must be True, and -- only
    if caps.editor_dialog -- a Yes/No EditorDialog confirm as well),
    then hand the actual restore work to run_undo() above. Nothing is
    touched unless both gates pass."""
    data = load_undo_log(undo_log_path)
    if data is None:
        # load_undo_log() already logged why the file couldn't be read;
        # nothing has been touched, so just abort with a blocked result.
        return {"moved": [], "failed": [], "blocked": "unreadable undo log"}
    reversed_moves = _reversed_moves_from_log(data)

    _console("Sortilege undo: about to restore %d move(s) from run %s:" % (
        len(reversed_moves), data.get("created", "?")))
    for m in reversed_moves:
        _console("  %s -> %s" % (m["path"], m["dest_path"]))

    if not CONFIG.get("I_UNDERSTAND_THIS_MODIFIES_MY_PROJECT", False):
        _console("Undo blocked: set I_UNDERSTAND_THIS_MODIFIES_MY_PROJECT = True "
                  "in sortilege.py's CONFIG and re-run to actually restore.")
        return {"moved": [], "failed": [], "blocked": "confirm flag off"}

    if unreal is not None and caps.editor_dialog:
        try:
            answer = unreal.EditorDialog.show_message(
                "Sortilege", "Restore %d move(s)?" % len(reversed_moves),
                unreal.AppMsgType.YES_NO, default_value="No")
            if str(answer) != str(unreal.AppReturnType.YES):
                _console("Undo blocked: declined at the confirm dialog.")
                return {"moved": [], "failed": [], "blocked": "dialog declined"}
        except Exception:
            pass

    # Preview already printed above (before the gates, so a blocked run
    # still shows exactly what it WOULD have restored) -- don't echo it
    # a second time inside the mechanics.
    return run_undo(undo_log_path, caps, echo_preview=False)


# =====================================================================
# === CONSOLE HELPERS ===
# =====================================================================
# Tiny shared print/log helpers -- the single implementation print_preview(),
# undo(), and the main flow below all route through: unreal.log/log_warning
# when available, plain print() when genuinely not (e.g. a syntax check run
# outside the editor). Referenced by name from functions defined earlier in
# this file; that's fine -- Python resolves module-level names at call time,
# and both helpers exist by the time anything actually runs.

def _console(line):
    if unreal is not None:
        try:
            unreal.log(line)
            return
        except Exception:
            pass
    print(line)


def _console_warning(line):
    if unreal is not None:
        try:
            unreal.log_warning(line)
            return
        except Exception:
            pass
    print(line)


# =====================================================================
# === SELECTION SCOPE ===
# =====================================================================
# Which folders a run should act on. USE_SELECTION asks "what's selected
# in the Content Browser right now" via two DIFFERENT selection APIs that
# research could not confirm as reliable in a shipped UEFN build -- so
# both are tried, both are hasattr/try-except gated, and an empty/absent
# result from either (or both) is not an error, just a reason to fall
# back to the explicit SCOPE_FOLDERS config, and beyond that to every
# discovered content root (the same "scan everything" default scan_
# assets() itself falls back to).

def _normalize_scope_path(raw):
    """Strip a trailing "/" and rewrite a leading "/All/<Root>/..." form
    (an alternate Content Browser path some UEFN surfaces return, with
    "/All" standing in for the umbrella view over every mount) down to
    the plain "/<Root>/..." package-path form the rest of this file
    always uses. Returns "" for a value that normalizes to nothing
    usable (e.g. "/All" itself, or an empty string)."""
    path = str(raw).rstrip("/")
    if not path:
        return ""
    if path == "/All":
        return ""
    if path.startswith("/All/"):
        path = "/" + path[len("/All/"):]
    return path


def resolve_scope(config, caps):
    """Decide which folder(s) this run scans/acts on. Chain:

    1. If CONFIG["USE_SELECTION"] is True (and `unreal` is available):
       collect the union of EditorUtilityLibrary.get_selected_folder_
       paths() (gated caps.selected_folders) and, only when caps.path_
       view_folders, get_selected_path_view_folder_paths() -- the two
       surfaces research found catch different Content Browser selection
       states, and neither is confirmed-working, so both are consulted.
       Every returned path is normalized (see _normalize_scope_path).
       If this union comes back non-empty, it wins.
    2. Otherwise (USE_SELECTION off, or on but nothing usable came back
       -- logged as a clear warning so a silent config/API mismatch
       doesn't read as "it scanned nothing on purpose"): CONFIG
       ["SCOPE_FOLDERS"] if non-empty.
    3. Otherwise: discover_content_roots() -- the same whole-project
       default scan_assets() uses on its own.
    """
    if config.get("USE_SELECTION", False) and unreal is not None:
        raw_selected = []

        if caps.selected_folders:
            try:
                raw_selected.extend(unreal.EditorUtilityLibrary.get_selected_folder_paths())
            except Exception:
                pass

        if caps.path_view_folders:
            try:
                raw_selected.extend(
                    unreal.EditorUtilityLibrary.get_selected_path_view_folder_paths())
            except Exception:
                pass

        normalized = []
        seen = set()
        for raw in raw_selected:
            path = _normalize_scope_path(raw)
            if path and path not in seen:
                seen.add(path)
                normalized.append(path)

        if normalized:
            return normalized

        _console_warning(
            "Sortilege: USE_SELECTION is True but no usable folder "
            "selection was returned by this build (selected_folders=%s, "
            "path_view_folders=%s) -- falling back to SCOPE_FOLDERS." % (
                caps.selected_folders, caps.path_view_folders))

    scope_folders = config.get("SCOPE_FOLDERS", [])
    if scope_folders:
        return list(scope_folders)

    return discover_content_roots()


# =====================================================================
# === CONFIRM GATES ===
# =====================================================================
# The bounty's #1 requirement: dry-run preview is the default, and a
# deliberate confirm is required before anything is allowed to mutate
# the project. Two gates, checked in order; every block is logged so a
# blocked run is never a silent no-op.

def confirmed_to_execute(config, caps, plan):
    """Return True only if this run is allowed to mutate the project.

    Gate 1 (always checked): CONFIG["I_UNDERSTAND_THIS_MODIFIES_MY_
    PROJECT"] must be True -- the one flag the preview footer and the
    file's own top-of-file usage docstring both point at. False here
    blocks unconditionally; the caller (main()) is responsible for
    printing the loud how-to-unblock instructions, since that message
    differs from a plain "declined" -- this function only decides and
    logs which gate stopped the run.

    Gate 2 (only if caps.editor_dialog): a Yes/No EditorDialog confirm
    naming the actual move/rename counts from `plan`. Absent capability
    means gate 1 alone is sufficient (logged as such, not a failure).

    The dialog's counts are derived directly from plan["moves"], the SAME
    way format_preview() derives its header counts -- not echoed from
    plan["stats"], whose "moves" is every planned item regardless of
    action and whose "renames" counts "rename" AND "move+rename" together.
    Reading straight from stats would double-count a move+rename item:
    it is included in BOTH stats["moves"] and stats["renames"], so a
    single item would read back as "1 move, 1 rename" -- two changes
    instead of the one it actually is.
    """
    if not config.get("I_UNDERSTAND_THIS_MODIFIES_MY_PROJECT", False):
        _console_warning(
            "Sortilege: blocked at gate 1 -- "
            "I_UNDERSTAND_THIS_MODIFIES_MY_PROJECT is False.")
        return False

    if not caps.editor_dialog:
        _console(
            "Sortilege: gate 1 passed (I_UNDERSTAND_THIS_MODIFIES_MY_PROJECT "
            "is True); no confirm dialog is available on this build, so "
            "gate 1 alone is sufficient to proceed.")
        return True

    moves = plan.get("moves", [])
    move_rename_count = sum(1 for m in moves if m["action"] == "move+rename")
    rename_only_count = sum(1 for m in moves if m["action"] == "rename")
    total_to_move = sum(1 for m in moves if m["action"] in ("move", "move+rename"))

    message = (
        "%d asset(s) to move (%d also renamed), %d rename-in-place. "
        "Modify the project now?" % (total_to_move, move_rename_count, rename_only_count)
    )

    try:
        answer = unreal.EditorDialog.show_message(
            "Sortilege", message,
            unreal.AppMsgType.YES_NO, default_value="No")
        if str(answer) == str(unreal.AppReturnType.YES):
            return True
        _console_warning("Sortilege: blocked at gate 2 -- declined at the confirm dialog.")
        return False
    except Exception:
        _console_warning(
            "Sortilege: gate 2 confirm dialog call failed on this build; "
            "treating the run as not confirmed.")
        return False


_APPLY_BLOCKED_INSTRUCTIONS = (
    "=" * 70,
    "APPLY BLOCKED - nothing was changed.",
    "=" * 70,
    "To execute for real: open sortilege.py, find the CONFIG section near",
    "the top of the file, and change this line:",
    '    "I_UNDERSTAND_THIS_MODIFIES_MY_PROJECT": False,',
    "to:",
    '    "I_UNDERSTAND_THIS_MODIFIES_MY_PROJECT": True,',
    "Save the file and re-run this script with 'apply'",
    '(py "path/to/sortilege.py" apply). If your UEFN build supports it, a',
    "Yes/No confirm dialog will still ask before anything actually moves.",
    "=" * 70,
)


# =====================================================================
# === PROBE MODE ===
# =====================================================================
# Read-only, always -- the demo's 10-second "does this build even
# support this" sanity check. Never scans with intent to act, never
# writes a plan/report/undo file, never touches a single asset.

def probe():
    """Print (and return, for callers that want it) a read-only snapshot
    of this environment: Python version, project name (gated unreal.
    SystemLibrary.get_game_name()), discovered content roots, the full
    capability report, headline scan counts per category, and the
    resolved log directory."""
    caps = probe_capabilities()

    _console("=" * 70)
    _console("Sortilege capability probe:")
    _console("=" * 70)
    _console("Python: %s" % sys.version.split("\n")[0])

    project_name = "(unknown)"
    if unreal is not None:
        try:
            if hasattr(unreal, "SystemLibrary") and hasattr(unreal.SystemLibrary, "get_game_name"):
                project_name = str(unreal.SystemLibrary.get_game_name())
        except Exception:
            pass
    _console("Project: %s" % project_name)

    roots = discover_content_roots()
    _console("Content roots: %s" % (", ".join(roots) if roots else "(none found)"))

    for line in caps.report():
        _console(line)

    scope_folders = resolve_scope(CONFIG, caps)
    assets = scan_assets(scope_folders)
    plan = build_plan(assets, CONFIG, caps)
    stats = plan.get("stats", {})
    by_category = stats.get("by_category", {})
    if by_category:
        cat_bits = ["%s: %d" % (k, v) for k, v in sorted(by_category.items())]
        _console("Scan headline: " + ", ".join(cat_bits) +
                  " (scanned %d, %d skipped)" % (stats.get("scanned", 0), stats.get("skips", 0)))
    else:
        _console("Scan headline: no sortable assets found (scanned %d, %d skipped)" % (
            stats.get("scanned", 0), stats.get("skips", 0)))

    log_dir = resolve_log_dir(CONFIG)
    _console("Log dir: %s" % log_dir)
    _console("=" * 70)

    return {
        "caps": caps, "project_name": project_name, "content_roots": roots,
        "stats": stats, "log_dir": log_dir,
    }


# =====================================================================
# === MAIN ===
# =====================================================================

def _newest_undo_log(log_dir):
    """Return the path to the most recently created sortilege_undo_*.json
    in `log_dir`, or None if there isn't one. The embedded timestamp in
    the filename makes lexical (name) sort order the same as chronological
    order, so a plain sorted os.listdir() is enough -- no file mtimes
    needed."""
    try:
        names = [n for n in os.listdir(log_dir)
                 if n.startswith("sortilege_undo_") and n.endswith(".json")]
    except Exception:
        names = []
    if not names:
        return None
    names.sort()
    return os.path.join(log_dir, names[-1])


def _run_with_progress(plan, caps, undo_log, extra_progress=None, tracer=None, gc_enabled=None):
    """execute_plan(), wrapped in a ScopedSlowTask progress UI when this
    build supports it (caps.scoped_slow_task); a plain progress=None call
    otherwise. make_dialog(can_cancel=True) is its own try/except -- the
    real signature is unconfirmed and a build that rejects the kwarg (or
    lacks the method) must not abort the run over a progress-bar detail.
    The progress callable calls enter_progress_frame(1, "<current asset>")
    then, only if this build's task object actually has should_cancel
    (hasattr-gated -- most won't), raises SortilegeCancelled when it
    returns True. execute_plan() already catches SortilegeCancelled and
    returns cleanly with results["cancelled"] = True, so no extra
    exception handling is needed around that path here.

    `extra_progress`, if given, is an additional callable invoked once per
    move at the same point (before that item's move is attempted) -- the
    GUI passes root.update() through this so its window stays repaintable
    during a long batch. Any exception it raises other than
    SortilegeCancelled is swallowed, same as execute_plan()'s own
    progress-callback handling.

    `tracer` and `gc_enabled`, if given, are forwarded straight through
    to every execute_plan() call this makes (see execute_plan()'s own
    docstring) -- this function is purely a progress-UI wrapper around
    that one call, so it has no diagnostics logic of its own."""
    # A GUI-driven run (extra_progress present) shows progress in the tkinter
    # window; it must NOT also spin up UEFN's native ScopedSlowTask modal
    # dialog. Two UI systems -- tkinter's mainloop and Slate's own modal
    # progress loop -- driven on the editor's single main thread reenter each
    # other and hard-crash the editor the instant Apply starts (no crash
    # reporter). Console runs (extra_progress is None) keep the native bar.
    if extra_progress is not None or not caps.scoped_slow_task:
        return execute_plan(plan, caps, undo_log, progress=extra_progress,
                             tracer=tracer, gc_enabled=gc_enabled)

    try:
        total = len(plan.get("moves", []))
        with unreal.ScopedSlowTask(total, "Sortilege: moving assets") as task:
            try:
                task.make_dialog(can_cancel=True)
            except Exception:
                pass

            def _progress(move):
                try:
                    task.enter_progress_frame(1, move.get("path", ""))
                except Exception:
                    pass
                if hasattr(task, "should_cancel"):
                    try:
                        should_stop = task.should_cancel()
                    except Exception:
                        should_stop = False
                    if should_stop:
                        raise SortilegeCancelled("cancelled via ScopedSlowTask")
                if extra_progress is not None:
                    try:
                        extra_progress(move)
                    except SortilegeCancelled:
                        raise
                    except Exception:
                        pass

            return execute_plan(plan, caps, undo_log, progress=_progress,
                                 tracer=tracer, gc_enabled=gc_enabled)
    except Exception:
        # A genuinely broken ScopedSlowTask on this build (construction or
        # context-manager entry itself failing) -- fall back to a plain
        # run rather than lose the apply entirely. Today this is provably
        # safe: nothing in the try block above can have executed a real
        # move before this point without also returning normally. But if
        # a future refactor ever let an exception escape execute_plan()
        # itself mid-batch, blindly re-running execute_plan(plan, ...)
        # here would re-attempt (and potentially re-log) every item in
        # `plan`, including ones already safely committed and recorded in
        # the undo log. Guard against that directly: once the undo log
        # already holds recorded moves, refuse to re-execute and report
        # what is already known from the undo log instead. Only fall back
        # to a plain re-run when nothing has moved yet, which is exactly
        # the safe case above.
        if undo_log.moves:
            _console_warning(
                "Sortilege: the progress-wrapped run was aborted after %d "
                "move(s) were already committed; NOT re-executing the plan "
                "(that would double-move already-completed items). See the "
                "undo log at %s for what has been done so far." % (
                    len(undo_log.moves), undo_log.path))
            already_moved = [(m["from"], m["to"]) for m in undo_log.moves]
            return {"moved": already_moved, "failed": [], "aborted": True}
        return execute_plan(plan, caps, undo_log, progress=extra_progress,
                             tracer=tracer, gc_enabled=gc_enabled)


def run_apply(plan, caps, extra_progress=None, status_callback=None):
    """The ONE apply pipeline: write_plan_json -> ensure_directories ->
    UndoLog.begin -> execute_plan (progress-wrapped when this build
    supports ScopedSlowTask) -> fix_soft_references -> cleanup_redirectors
    (if CONFIG["CLEAN_REDIRECTORS"]) -> cleanup_empty_folders (if CONFIG
    ["CLEAN_EMPTY_FOLDERS"]) -> verify_results (if CONFIG["VERIFY_AFTER"])
    -> write_summary.

    Extracted out of main()'s old inline apply body so there is exactly
    one place that can move an asset for real: main()'s console apply
    path (gated by confirmed_to_execute()) and the GUI's Apply button
    (gated by its in-window checkbox) both call this. Deliberately does
    NOT gate anything itself -- gating is entirely the caller's job, so
    the console flag+dialog gates and the GUI's checkbox gate stay each
    exactly where they belong and are never applied twice.

    `extra_progress`, if given, is threaded through to _run_with_progress()
    -- see its docstring; the GUI uses it to pump root.update().

    `status_callback`, if given, is called with a single human-readable
    string once before each pipeline stage starts: "Moving assets...",
    "Fixing references...", "Cleaning up redirectors...", "Removing
    empty folders...", "Verifying...", "Writing report..." -- one call
    per stage that actually runs (a stage SAFE_MODE or its own CONFIG
    gate skips gets no call, same as the CrashTracer's own entering/done
    marks). It is ALSO threaded through as the progress_hook for the two
    post-move stages that can run for minutes with nothing else pumping
    the GUI's window (cleanup_redirectors, cleanup_empty_folders): every
    5th item produces an additional "<stage text> X/N..." call, so a
    long redirector-cleanup or empty-folder-sweep phase keeps producing
    status updates instead of going silent between its single entering
    call and the next stage. Every call is wrapped in its own try/except
    and is a no-op when status_callback is None -- the console path
    (main()'s apply branch) never passes one, so it is entirely
    unaffected.

    A fresh CrashTracer is started here (resolve_log_dir()'s directory)
    and STAGE-brackets every sub-stage below ("moves", "soft-references",
    "redirector-cleanup", "empty-folder-sweep", "verify", "write-
    summary"), so the last unmatched ">>> entering" line in the trace
    file names whichever one a hard crash interrupted -- see CrashTracer.
    CONFIG["SAFE_MODE"] additionally skips soft-references, redirector-
    cleanup, empty-folder-sweep, and every collect_garbage() call (a
    "just move the assets, nothing else" apply, to isolate which stage a
    crash actually lives in); CONFIG["DISABLE_GC"] skips only the
    collect_garbage() calls; CONFIG["FIX_SOFT_REFERENCES"] independently
    gates the soft-references pass. Every skip gets a loud "SAFE_MODE
    active: skipping <stage>" mark instead of the usual entering/done
    pair. verify_results() is unaffected by SAFE_MODE -- it only reads --
    and still runs unless CONFIG["VERIFY_AFTER"] is False.

    Returns {"plan_path": str, "report_path": str, "undo_log": UndoLog,
    "results": dict}. `results` is exactly what execute_plan()/
    _run_with_progress() returned, with "redirector_cleanup" / "verify"
    keys layered on when those passes ran."""
    def _status(text):
        if status_callback is not None:
            try:
                status_callback(text)
            except Exception:
                pass

    log_dir = resolve_log_dir(CONFIG)
    plan_path = write_plan_json(plan, log_dir)

    tracer = CrashTracer.begin(log_dir)
    safe_mode = bool(CONFIG.get("SAFE_MODE", False))
    gc_enabled = _effective_gc_enabled(caps, CONFIG)

    ensure_directories(plan)
    undo_log = UndoLog.begin(log_dir, plan)

    _status("Moving assets...")
    tracer.mark("STAGE >>> entering: moves")
    results = _run_with_progress(plan, caps, undo_log, extra_progress=extra_progress,
                                  tracer=tracer, gc_enabled=gc_enabled)
    tracer.mark("STAGE <<< done: moves (moved=%d failed=%d)" % (
        len(results.get("moved", [])), len(results.get("failed", []))))

    do_soft_refs = CONFIG.get("FIX_SOFT_REFERENCES", True) and not safe_mode
    if safe_mode:
        tracer.mark("SAFE_MODE active: skipping soft-references")
    if do_soft_refs:
        _status("Fixing references...")
        tracer.mark("STAGE >>> entering: soft-references")
        fix_soft_references(results, caps, tracer=tracer)
        tracer.mark("STAGE <<< done: soft-references")

    touched_folders = set()
    for m in plan.get("moves", []):
        if "/" in m["path"]:
            touched_folders.add(m["path"].rsplit("/", 1)[0])
        if m.get("dest_folder"):
            touched_folders.add(m["dest_folder"])
    scope_for_cleanup = sorted(touched_folders)

    do_redirector_cleanup = CONFIG.get("CLEAN_REDIRECTORS", True) and not safe_mode
    if safe_mode:
        tracer.mark("SAFE_MODE active: skipping redirector-cleanup")
    if do_redirector_cleanup:
        _status("Cleaning up redirectors...")
        tracer.mark("STAGE >>> entering: redirector-cleanup")

        def _redirector_progress(done, total):
            _status("Cleaning up redirectors %d/%d..." % (done, total))

        results["redirector_cleanup"] = cleanup_redirectors(
            scope_for_cleanup, caps, tracer=tracer, gc_enabled=gc_enabled,
            progress_hook=_redirector_progress)
        tracer.mark("STAGE <<< done: redirector-cleanup (fixed=%d remaining=%d)" % (
            len(results["redirector_cleanup"]["fixed"]),
            len(results["redirector_cleanup"]["remaining"])))

    # AFTER the asset moves + redirector cleanup succeed (bounty
    # clarification: "no broken references" also covers Verse-side
    # references -- see build_verse_edits()'s docstring). Gated the same
    # way as every other optional post-move pass: SAFE_MODE forces it off
    # regardless of CONFIG, the same "just move the assets, nothing else"
    # bisect valve as soft-references/redirector-cleanup/empty-folder-
    # sweep. Built from results["moved"] -- the ACTUALLY-moved pairs, not
    # the full plan -- so a partially-failed batch only ever rewrites
    # Verse refs for assets that genuinely ended up at their new path.
    do_verse_fix = CONFIG.get("FIX_VERSE_REFERENCES", True) and not safe_mode
    if safe_mode:
        tracer.mark("SAFE_MODE active: skipping verse-references")
    if do_verse_fix:
        _status("Rewriting Verse references...")
        tracer.mark("STAGE >>> entering: verse-references")
        moved_as_moves = [{"path": old, "dest_path": new}
                          for old, new in results.get("moved", [])]
        # Sample from the NEW (post-move) paths -- they are real,
        # existing assets right now, unlike the old paths (redirectors).
        # Same auto-detect mechanism build_plan() uses; see
        # resolve_verse_search_dir()'s docstring.
        verse_sample_paths = [mv["dest_path"] for mv in moved_as_moves][:5]
        verse_dir = resolve_verse_search_dir(CONFIG, sample_asset_paths=verse_sample_paths)
        verse_files = find_verse_files(verse_dir)
        verse_edit_list = build_verse_edits(
            moved_as_moves, verse_files, discover_content_roots(),
            fix_bare_names=CONFIG.get("FIX_VERSE_BARE_NAMES", True))
        verse_apply_result = apply_verse_edits(verse_edit_list, log_dir)
        verse_apply_result["edit_count"] = len(
            [e for e in verse_edit_list if not e.get("skipped")])
        verse_apply_result["skipped_bare_count"] = len(
            [e for e in verse_edit_list if e.get("skipped")])
        results["verse_edits"] = verse_apply_result
        if verse_apply_result.get("backup_index"):
            undo_log.set_verse_backup_index(verse_apply_result["backup_index"])
        tracer.mark("STAGE <<< done: verse-references (edited=%d failed=%d)" % (
            len(verse_apply_result["edited"]), len(verse_apply_result["failed"])))

    # AFTER redirector cleanup on purpose: a folder holding only a
    # leftover redirector reads non-empty until that redirector is
    # cleaned, so sweeping first would keep folders the cleanup was
    # about to empty out.
    do_empty_folders = CONFIG.get("CLEAN_EMPTY_FOLDERS", True) and not safe_mode
    if safe_mode:
        tracer.mark("SAFE_MODE active: skipping empty-folder-sweep")
    if do_empty_folders:
        _status("Removing empty folders...")
        tracer.mark("STAGE >>> entering: empty-folder-sweep")

        def _empty_folder_progress(done, total):
            _status("Removing empty folders %d/%d..." % (done, total))

        results["empty_folders"] = cleanup_empty_folders(
            plan, CONFIG, tracer=tracer, progress_hook=_empty_folder_progress)
        tracer.mark("STAGE <<< done: empty-folder-sweep (removed=%d kept=%d)" % (
            len(results["empty_folders"]["removed"]),
            len(results["empty_folders"]["kept"])))

    if CONFIG.get("VERIFY_AFTER", True):
        _status("Verifying...")
        tracer.mark("STAGE >>> entering: verify")
        results["verify"] = verify_results(results, scope_for_cleanup, caps)
        tracer.mark("STAGE <<< done: verify (ok=%s)" % results["verify"].get("ok"))

    _status("Writing report...")
    tracer.mark("STAGE >>> entering: write-summary")
    report_path = write_summary(plan, results, log_dir)
    tracer.mark("STAGE <<< done: write-summary")

    return {
        "plan_path": plan_path,
        "report_path": report_path,
        "undo_log": undo_log,
        "results": results,
    }


# =====================================================================
# === GUI (optional, tkinter) ===
# =====================================================================
# tkinter is plausible-but-unofficial inside UEFN's embedded Python
# (docs/research-brief.md section 5 -- one shipped organizer uses it, a
# third-party tool runs a persistent Toplevel window, but Epic never
# documents it). Everything below is therefore strictly OPTIONAL: it is
# reached only from main()'s "preview" branch, gated on CONFIG["USE_GUI"],
# and every entry point (launch_preview_window()) catches every exception
# -- an ImportError on `import tkinter`, a failed Tk() construction, or
# any exception while building the window -- and falls back to the plain
# console preview that has ALREADY fully run by the time this is ever
# reached. This section never raises out to main().
#
# ONE tk.Tk() root only: research section 5 -- creating a second Tk()
# instance while one is still alive crashes tcl. _GUI_ROOT is the
# module-level singleton _make_or_reuse_root() reuses/re-creates around.
#
# Everything runs on the editor's main thread, sequentially, exactly like
# every other unreal.* call in this file -- no threads, no callbacks off
# the main loop. During Apply, run_apply()'s extra_progress hook calls
# root.update() once per move so the window stays repainted/responsive
# even though it's all still happening inside the single Apply button
# click handler.

_GUI_ROOT = None

_PREVIEW_WINDOW_TITLE = "Sortilege - dry run preview"


def apply_folder_map_edits(config, edits):
    """Validate and apply GUI-edited FOLDER_MAP / SORT_ROOT values onto
    `config` IN PLACE. `edits` is {"FOLDER_MAP": {category: folder_name,
    ...}, "SORT_ROOT": sort_root_value} -- either key is optional.

    Every folder-name path segment is validated with validate_asset_
    name()'s same empty/whitespace/illegal-character checks build_plan()
    already applies to renamed asset names -- a destination folder name
    follows the same rules. "" is a valid SORT_ROOT (means "sort straight
    into the content root", same meaning CONFIG's own comment documents).

    Returns None on success (`config` already mutated). On ANY validation
    failure, returns {"field": <label>, "reason": <why>} and leaves
    `config` COMPLETELY UNCHANGED -- everything is validated before
    anything is mutated, so there is never a partial apply."""
    folder_map_edits = (edits or {}).get("FOLDER_MAP") or {}
    sort_root_edit = (edits or {}).get("SORT_ROOT", None)

    existing_categories = config.get("FOLDER_MAP", {})
    for category, folder_name in folder_map_edits.items():
        # Only categories that already exist can be edited -- an unknown
        # key would silently invent a brand-new category nothing ever
        # classifies into, so reject it instead of setdefault-ing it in.
        if category not in existing_categories:
            return {"field": "FOLDER_MAP.%s" % category,
                    "reason": "unknown category"}
        segments = str(folder_name).split("/")
        for segment in segments:
            reason = validate_asset_name(segment)
            if reason:
                return {"field": "FOLDER_MAP.%s" % category, "reason": reason}

    if sort_root_edit is not None and sort_root_edit != "":
        for segment in str(sort_root_edit).strip("/").split("/"):
            reason = validate_asset_name(segment)
            if reason:
                return {"field": "SORT_ROOT", "reason": reason}

    if folder_map_edits:
        config.setdefault("FOLDER_MAP", {}).update(folder_map_edits)
    if sort_root_edit is not None:
        config["SORT_ROOT"] = sort_root_edit

    return None


def _make_or_reuse_root(tk):
    """Return a live Tk() root, reusing the module-level singleton if one
    is already alive -- constructing a SECOND Tk() while one is alive
    crashes tcl (research, section 5). If the previous root was destroyed
    (or checking it raises -- the interpreter it belonged to is simply
    gone), fall through and create a fresh one."""
    global _GUI_ROOT
    if _GUI_ROOT is not None:
        try:
            if _GUI_ROOT.winfo_exists():
                try:
                    _GUI_ROOT.deiconify()
                    _GUI_ROOT.lift()
                except Exception:
                    pass
                return _GUI_ROOT
        except Exception:
            pass
        _GUI_ROOT = None
    _GUI_ROOT = tk.Tk()
    return _GUI_ROOT


def _build_preview_window(tk, ttk, messagebox, plan, caps):
    """Build (or reuse/refresh) the preview window for `plan` using the
    given tk/ttk/messagebox modules -- injected as parameters (rather
    than imported here) so tests can pass in a minimal fake stub and
    exercise the construction + Apply-callback wiring without a display.
    launch_preview_window() is the real entry point that does the actual
    `import tkinter` and calls this.

    Does NOT call mainloop() -- the caller does that (real usage blocks
    there until the window is closed; the fake-stub tests get a no-op
    mainloop() back and inspect the returned handles directly instead).

    Returns a dict of handles ({"root", "state", "apply_var",
    "apply_button", "status_var", "logs_var", "on_apply", "on_rescan",
    "on_close"}) -- real callers only care that this didn't raise; tests
    use the handles to drive the Apply/Re-scan seams directly.

    The window is pinned on top (-topmost + lift()) when built and
    re-asserts this at the start of Apply/Undo and on every status
    update during either run (see _assert_on_top()/_gui_status_callback()
    below) -- a field-reported run left the window hidden behind the
    UEFN editor with no way to bring it forward. "status_var" backs a
    persistent status label that run_apply()/run_undo()'s status_
    callback keeps current through every pipeline stage, not just the
    moves stage extra_progress already pumped -- the other field-
    reported gap (a frozen, silent window for the ~8-minute post-move
    phase). "logs_var" surfaces the same resolved log directory main()
    announces on the console."""
    root = _make_or_reuse_root(tk)
    root.title(_PREVIEW_WINDOW_TITLE)
    try:
        root.geometry("900x650")
    except Exception:
        pass
    try:
        root.resizable(True, True)
    except Exception:
        pass

    # Field report: the preview window could end up hiding BEHIND the
    # UEFN editor during a long apply, with no way to bring it forward --
    # a soft-lock, since the editor itself was waiting on this window's
    # (invisible) confirm/results flow. -topmost pins it above every other
    # window; lift() additionally raises it in the current stacking
    # order. Each call is its own try/except -- an embedded-tk build
    # missing either method (or one that raises) must never crash the
    # window; it just stays wherever it was. Called once right here (the
    # window is built) and again at the start of Apply/Undo and
    # periodically through the run via _gui_status_callback() below, so
    # it keeps re-asserting itself instead of only ever doing so once.
    def _assert_on_top():
        try:
            root.attributes("-topmost", True)
        except Exception:
            pass
        try:
            root.lift()
        except Exception:
            pass

    _assert_on_top()

    # Module-level singleton reuse means a previous run's widgets can
    # still be attached to this same root -- clear them before rebuilding.
    try:
        for child in list(root.winfo_children()):
            try:
                child.destroy()
            except Exception:
                pass
    except Exception:
        pass

    # "busy" is the in-flight guard: True for exactly as long as the
    # apply or undo pipeline is running. _on_close() refuses to destroy
    # the root while it is set (see there for why), and re-entrant
    # apply/undo clicks no-op against it. "on_undo" is populated by
    # _show_results_bar() once a run has completed. "poll_id"/"closed"
    # belong to the confirm-gate fallback poll: the pending root.after id
    # (cancelled by _on_close) and the flag that stops the loop from ever
    # re-scheduling once the window is gone.
    state = {"plan": plan, "caps": caps, "apply_outcome": None,
             "busy": False, "on_undo": None, "poll_id": None, "closed": False}

    header_var = tk.StringVar(master=root)
    header_label = tk.Label(root, textvariable=header_var, justify="left", anchor="w")
    header_label.pack(fill="x", padx=10, pady=(10, 4))

    def _refresh_header():
        counts = preview_counts(state["plan"])
        text = (
            "Content root: %s    Sort root: %s\n"
            "Scanned %d asset(s) -- %d to move (%d also renamed), "
            "%d rename-in-place, %d skipped" % (
                counts["content_root"], counts["sort_root"], counts["scanned"],
                counts["total_to_move"], counts["move_rename"],
                counts["rename_only"], counts["skips"],
            )
        )
        grouping = state["plan"].get("grouping")
        if grouping:
            text += "\nGrouping: by asset (%d kits, %d shared, %d loose)" % (
                grouping.get("kits", 0), grouping.get("shared", 0),
                grouping.get("loose", 0))
        header_var.set(text)

    notebook = ttk.Notebook(root)
    notebook.pack(fill="both", expand=True, padx=10, pady=4)

    moves_frame = ttk.Frame(notebook)
    skips_frame = ttk.Frame(notebook)
    verse_frame = ttk.Frame(notebook)
    mapping_frame = ttk.Frame(notebook)
    notebook.add(moves_frame, text="Planned moves")
    notebook.add(skips_frame, text="Skipped")
    notebook.add(verse_frame, text="Verse edits")
    notebook.add(mapping_frame, text="Folder mapping")

    moves_tree = ttk.Treeview(
        moves_frame, columns=("category", "class", "from", "to"), show="headings")
    for key, label in (("category", "Category"), ("class", "Class"),
                       ("from", "From"), ("to", "To")):
        moves_tree.heading(key, text=label)
        moves_tree.column(key, width=150 if key in ("category", "class") else 260, anchor="w")
    moves_scroll = ttk.Scrollbar(moves_frame, orient="vertical", command=moves_tree.yview)
    moves_tree.configure(yscrollcommand=moves_scroll.set)
    moves_tree.pack(side="left", fill="both", expand=True)
    moves_scroll.pack(side="right", fill="y")

    skips_tree = ttk.Treeview(
        skips_frame, columns=("reason", "class", "path"), show="headings")
    for key, label in (("reason", "Reason"), ("class", "Class"), ("path", "Path")):
        skips_tree.heading(key, text=label)
        skips_tree.column(key, width=180 if key == "reason" else 260, anchor="w")
    skips_scroll = ttk.Scrollbar(skips_frame, orient="vertical", command=skips_tree.yview)
    skips_tree.configure(yscrollcommand=skips_scroll.set)
    skips_tree.pack(side="left", fill="both", expand=True)
    skips_scroll.pack(side="right", fill="y")

    # "Verse edits" tab: the console preview's "-- Verse reference edits
    # --" section (see format_verse_preview()), shown in the window too --
    # review Minor: the Output Log was the only place a Verse edit was
    # ever visible before this. Populated (and re-populated on Re-scan)
    # from the SAME plan["verse_edits"] list build_plan() attaches, via
    # plan_to_verse_edit_rows() -- one row per proposed edit, "note"
    # holding the same "bare name - review" / "skipped - fix manually"
    # flag the console draws.
    verse_tree = ttk.Treeview(
        verse_frame, columns=("file", "line", "old_ref", "new_ref", "note"),
        show="headings")
    for key, label, width in (
        ("file", "File", 220), ("line", "Line", 50), ("old_ref", "Old ref", 180),
        ("new_ref", "New ref", 180), ("note", "Note", 160),
    ):
        verse_tree.heading(key, text=label)
        verse_tree.column(key, width=width, anchor="w")
    verse_scroll = ttk.Scrollbar(verse_frame, orient="vertical", command=verse_tree.yview)
    verse_tree.configure(yscrollcommand=verse_scroll.set)
    verse_tree.pack(side="left", fill="both", expand=True)
    verse_scroll.pack(side="right", fill="y")

    def _refresh_tables():
        try:
            for item in moves_tree.get_children():
                moves_tree.delete(item)
        except Exception:
            pass
        for row in plan_to_move_rows(state["plan"]):
            moves_tree.insert(
                "", "end",
                values=(row["category"], row["class_name"], row["from"], row["to"]))

        try:
            for item in skips_tree.get_children():
                skips_tree.delete(item)
        except Exception:
            pass
        for row in plan_to_skip_rows(state["plan"]):
            skips_tree.insert(
                "", "end", values=(row["reason"], row["class_name"], row["path"]))

        try:
            for item in verse_tree.get_children():
                verse_tree.delete(item)
        except Exception:
            pass
        for row in plan_to_verse_edit_rows(state["plan"]):
            verse_tree.insert(
                "", "end",
                values=(row["file"], row["line_no"], row["old_ref"],
                         row["new_ref"], row["note"]))

    # --- Folder mapping tab ---
    mapping_error_var = tk.StringVar(master=root, value="")
    mapping_entries = {}

    row_index = [0]

    def _add_mapping_row(label_text, initial_value):
        tk.Label(mapping_frame, text=label_text).grid(
            row=row_index[0], column=0, sticky="e", padx=4, pady=2)
        entry = tk.Entry(mapping_frame, width=30)
        entry.insert(0, initial_value)
        entry.grid(row=row_index[0], column=1, sticky="w", padx=4, pady=2)
        row_index[0] += 1
        return entry

    folder_map = CONFIG.get("FOLDER_MAP", {})
    for category in sorted(folder_map.keys()):
        mapping_entries[category] = _add_mapping_row(category + ":", folder_map[category])

    sort_root_entry = _add_mapping_row("SORT_ROOT:", CONFIG.get("SORT_ROOT", "") or "")

    # Sorting mode: flat per-type vs dependency-clustered kits. The radio
    # only picks the mode; the Re-scan button below applies it (same as
    # every other edit on this tab). On builds without a dependency-query
    # API the by-asset option is disabled with a note.
    mode_var = tk.StringVar(
        master=root,
        value="by_asset" if CONFIG.get("GROUP_BY_ASSET", False) else "flat")
    tk.Label(mapping_frame, text="Sorting mode:").grid(
        row=row_index[0], column=0, sticky="e", padx=4, pady=2)
    flat_radio = tk.Radiobutton(
        mapping_frame, text="By type (flat)", variable=mode_var, value="flat")
    flat_radio.grid(row=row_index[0], column=1, sticky="w", padx=4, pady=2)
    row_index[0] += 1
    by_asset_radio = tk.Radiobutton(
        mapping_frame, text="By asset (keep kits together)",
        variable=mode_var, value="by_asset")
    by_asset_radio.grid(row=row_index[0], column=1, sticky="w", padx=4, pady=2)
    row_index[0] += 1
    if not getattr(caps, "dependency_query", False):
        by_asset_radio.configure(state="disabled")
        tk.Label(mapping_frame,
                 text="(grouping needs a dependency-query API this "
                      "build's Python does not expose)").grid(
            row=row_index[0], column=1, sticky="w", padx=4, pady=2)
        row_index[0] += 1

    # Crash-diagnostics checkbox: mirrors CONFIG["SAFE_MODE"] (skips
    # soft-reference fixup, redirector cleanup, and the empty-folder
    # sweep on the next Apply -- see run_apply()'s docstring). Reads its
    # initial state from CONFIG so a value already set in the file itself
    # (before the GUI ever opened) shows up checked; writes straight back
    # to CONFIG the instant it's toggled, since run_apply() reads CONFIG
    # directly at Apply-click time -- no Re-scan needed for this one to
    # take effect. Fail-soft like every other control on this tab: a
    # broken Variable here only means the diagnostics switch doesn't
    # flip, never a crashed window.
    safe_mode_var = tk.BooleanVar(master=root, value=bool(CONFIG.get("SAFE_MODE", False)))

    def _on_safe_mode_toggle():
        try:
            CONFIG["SAFE_MODE"] = bool(safe_mode_var.get())
        except Exception:
            pass

    safe_mode_checkbox = tk.Checkbutton(
        mapping_frame, text="Safe mode (skip cleanup, just move)",
        variable=safe_mode_var, command=_on_safe_mode_toggle)
    safe_mode_checkbox.grid(row=row_index[0], column=0, columnspan=2, sticky="w", padx=4, pady=2)
    row_index[0] += 1

    mapping_error_label = tk.Label(mapping_frame, textvariable=mapping_error_var, fg="red")
    mapping_error_label.grid(row=row_index[0], column=0, columnspan=2, sticky="w", padx=4, pady=2)
    row_index[0] += 1

    def _on_rescan():
        # The whole handler is one try/except -- an exception here (a
        # widget read failing, apply_folder_map_edits() misbehaving on
        # unexpected input, the re-scan itself) must never crash the
        # window; it surfaces in the mapping tab's own error label.
        try:
            edits = {
                "FOLDER_MAP": dict(
                    (cat, entry.get()) for cat, entry in mapping_entries.items()),
                "SORT_ROOT": sort_root_entry.get(),
            }
            error = apply_folder_map_edits(CONFIG, edits)
            if error:
                mapping_error_var.set("%s: %s" % (error["field"], error["reason"]))
                return
            mapping_error_var.set("")

            # The sorting-mode radio applies on Re-scan, like every other
            # edit on this tab.
            try:
                CONFIG["GROUP_BY_ASSET"] = (mode_var.get() == "by_asset")
            except Exception:
                pass

            scope_folders = resolve_scope(CONFIG, state["caps"])
            assets = scan_assets(scope_folders)
            new_plan = build_plan(assets, CONFIG, state["caps"])
            state["plan"] = new_plan
            _refresh_header()
            _refresh_tables()
            # The plan just changed under the checkbox -- the deliberate
            # confirm must be re-earned against the NEW plan, never
            # carried over from before the re-scan.
            apply_var.set(False)
        except Exception as exc:
            mapping_error_var.set("Re-scan failed: %s" % exc)

    rescan_button = tk.Button(
        mapping_frame, text="Re-scan with these mappings", command=_on_rescan)
    rescan_button.grid(row=row_index[0], column=0, columnspan=2, pady=6)
    row_index[0] += 1

    # --- Bottom bar ---
    bottom_frame = tk.Frame(root)
    bottom_frame.pack(fill="x", padx=10, pady=(4, 10))

    caution_label = tk.Label(
        bottom_frame,
        text=_CAUTION_REFERENCER_CACHE + "\n" + _CAUTION_VERSE_REFERENCES,
        justify="left", anchor="w", wraplength=860)
    caution_label.pack(fill="x")

    # Persistent status line: run_apply()/run_undo()'s status_callback
    # (see _gui_status_callback() below) updates this throughout the
    # WHOLE run, not just during the moves stage -- the field-reported
    # gap this closes is the ~8-minute post-move phase (soft-reference
    # fixup, redirector cleanup, empty-folder sweep, verify) that used to
    # run with a frozen, silent window. Stays packed (never destroyed)
    # through the results-bar transition so it keeps reflecting Undo's
    # own progress too.
    status_var = tk.StringVar(master=root, value="")
    status_label = tk.Label(
        bottom_frame, textvariable=status_var, justify="left", anchor="w")
    status_label.pack(fill="x")

    # Log-path visibility: the same absolute directory main()'s console
    # line announces (resolve_log_dir()) -- so "I could not find the
    # trace file" has one obvious place to look without reading the
    # Output Log scrollback.
    logs_var = tk.StringVar(
        master=root, value="Logs: %s" % resolve_log_dir(CONFIG))
    logs_label = tk.Label(
        bottom_frame, textvariable=logs_var, justify="left", anchor="w")
    logs_label.pack(fill="x")

    def _gui_status_callback(text):
        """Wired into run_apply()/run_undo() as status_callback: updates
        the persistent status label AND re-asserts the on-top/lift state
        (the "periodically during the run" half of the on-top fix) AND
        repaints immediately -- the same root.update() pump extra_
        progress already does for the moves stage, now covering every
        other stage too."""
        try:
            status_var.set(text)
        except Exception:
            pass
        # Repaint only (update_idletasks, not update), and do NOT re-lift mid
        # run: the window is already -topmost from build/Apply-start, and
        # re-dispatching events or poking the window manager during a batch is
        # exactly what reenters UEFN's UI and hard-crashes the editor.
        try:
            root.update_idletasks()
        except Exception:
            pass

    controls_frame = tk.Frame(bottom_frame)
    controls_frame.pack(fill="x", pady=(6, 0))

    # Field-report lesson (real UEFN session): ticking the checkbox did
    # NOT un-gray Apply on UEFN's embedded tk 3.11 even though the same
    # code worked on desktop tk. Which event mechanism is broken there is
    # unknowable from here, so the confirm gate below is deliberately
    # over-wired: explicit master= on every Variable (default-root
    # resolution is a known embedded-interpreter trap), THREE redundant
    # refresh signals (Checkbutton command=, variable trace, a
    # <ButtonRelease-1> bind routed through after_idle so it reads the
    # var AFTER the toggle lands), ttk widgets for the gate pair so the
    # button state can be driven through BOTH the configure(state=...)
    # option and ttk state flags, and an ultimate-fallback 200ms poll
    # (cancelled on close) that guarantees the button reflects the
    # checkbox even if every event mechanism is dead. Every refresh that
    # actually CHANGES the state logs one line so the next field test
    # produces evidence either way.

    apply_var = tk.BooleanVar(master=root, value=False)
    error_var = tk.StringVar(master=root, value="")

    _gate_last = {"confirm": None, "button": None}

    def _refresh_gate(*_args):
        if state["busy"]:
            # Never let the poll (or a stray event) re-enable Apply while
            # the apply/undo pipeline is mid-run and controls are
            # deliberately disabled.
            return
        confirmed = None
        try:
            confirmed = bool(apply_var.get())
        except Exception:
            confirmed = None
        if confirmed is None:
            # The Variable itself is broken on this tk build -- fall back
            # to the widget's own ttk state flags.
            try:
                confirmed = "selected" in apply_checkbox.state()
            except Exception:
                confirmed = False
        target = "normal" if confirmed else "disabled"
        try:
            apply_button.configure(state=target)
        except Exception:
            pass
        try:
            if confirmed:
                apply_button.state(["!disabled"])
            else:
                apply_button.state(["disabled"])
        except Exception:
            pass
        if _gate_last["confirm"] != confirmed or _gate_last["button"] != target:
            _gate_last["confirm"] = confirmed
            _gate_last["button"] = target
            _console("Sortilege GUI: confirm=%s, apply button=%s" % (
                confirmed, target))

    apply_checkbox = ttk.Checkbutton(
        controls_frame, text="I understand this will modify my project",
        variable=apply_var, command=_refresh_gate)
    apply_checkbox.pack(side="left")

    apply_button = ttk.Button(controls_frame, text="Apply", state="disabled")
    apply_button.pack(side="left", padx=(10, 0))
    try:
        apply_button.state(["disabled"])
    except Exception:
        pass

    close_button = tk.Button(controls_frame, text="Close")
    close_button.pack(side="right")

    error_label = tk.Label(bottom_frame, textvariable=error_var, fg="red")
    error_label.pack(fill="x")

    # Signal 2: variable trace (modern spelling first, legacy fallback).
    try:
        apply_var.trace_add("write", _refresh_gate)
    except Exception:
        try:
            apply_var.trace("w", _refresh_gate)
        except Exception:
            pass

    # Signal 3: the raw click itself. ButtonRelease fires BEFORE the
    # variable toggle settles on some builds, so the refresh is deferred
    # with after_idle to read the post-toggle value.
    def _on_checkbox_release(_event):
        try:
            root.after_idle(_refresh_gate)
        except Exception:
            _refresh_gate()

    try:
        apply_checkbox.bind("<ButtonRelease-1>", _on_checkbox_release)
    except Exception:
        pass

    # Signal 4 (ultimate fallback): a 200ms poll for as long as the
    # window lives -- even if command=, trace AND bind are all dead on
    # this tk build, the button reflects the checkbox within 200ms.
    def _poll_gate():
        if state.get("closed"):
            return
        try:
            _refresh_gate()
        except Exception:
            pass
        try:
            state["poll_id"] = root.after(200, _poll_gate)
        except Exception:
            state["poll_id"] = None

    try:
        state["poll_id"] = root.after(200, _poll_gate)
    except Exception:
        state["poll_id"] = None

    all_controls = (
        [moves_tree, skips_tree, verse_tree, rescan_button, apply_checkbox, apply_button,
         close_button, safe_mode_checkbox]
        + list(mapping_entries.values()) + [sort_root_entry]
    )

    def _set_controls_state(enabled):
        state_str = "normal" if enabled else "disabled"
        for widget in all_controls:
            try:
                widget.configure(state=state_str)
            except Exception:
                pass
        if enabled:
            # Respect the checkbox's own gating instead of blanket-
            # enabling Apply along with everything else.
            _refresh_gate()

    def _on_close():
        global _GUI_ROOT
        if state["busy"]:
            # A run is mid-flight (the apply/undo pipeline is committing
            # real moves and pumping root.update(), which is exactly when
            # a WM_DELETE_WINDOW can arrive). Destroying the root now
            # would kill the window under the running pipeline: the moves
            # already committed stay committed (and undo-logged), but the
            # results bar would then throw on the dead root and a
            # SUCCESSFUL run would read as "Apply failed". Refuse the
            # close and say why; it works again the moment the run ends.
            try:
                error_var.set("Run in progress - please wait.")
            except Exception:
                pass
            return
        # Stop the confirm-gate fallback poll: flag first (so an already-
        # queued tick exits without re-scheduling), then cancel the
        # pending after callback so nothing dangles on a destroyed root.
        state["closed"] = True
        if state.get("poll_id") is not None:
            try:
                root.after_cancel(state["poll_id"])
            except Exception:
                pass
            state["poll_id"] = None
        try:
            root.destroy()
        finally:
            _GUI_ROOT = None

    def _show_results_bar(outcome):
        results = outcome["results"]
        moved_count = len(results.get("moved", []))
        failed_count = len(results.get("failed", []))
        redirector_cleanup = results.get("redirector_cleanup") or {}
        remaining = len(redirector_cleanup.get("remaining", []))
        cleaned = len(redirector_cleanup.get("fixed", []))

        try:
            for widget in list(controls_frame.winfo_children()):
                widget.destroy()
        except Exception:
            pass
        # caution lines give way to the results; error_label deliberately
        # STAYS packed -- it's the visible surface for undo errors and
        # the close-while-busy notice in this final state too.
        try:
            caution_label.pack_forget()
        except Exception:
            pass

        summary_text = (
            "Done: %d moved, %d failed, redirectors cleaned %d remaining %d"
            % (moved_count, failed_count, cleaned, remaining))
        empty_removed = len((results.get("empty_folders") or {}).get("removed", []))
        if empty_removed:
            summary_text += ", %d empty folder%s removed" % (
                empty_removed, "" if empty_removed == 1 else "s")
        broken_soft_refs = len((results.get("verify") or {}).get("broken_soft_refs", []))
        if broken_soft_refs:
            summary_text += ", %d BROKEN soft reference%s (see report)" % (
                broken_soft_refs, "" if broken_soft_refs == 1 else "s")
        verse_edit_count = (results.get("verse_edits") or {}).get("edit_count", 0)
        if verse_edit_count:
            summary_text += ", %d Verse reference%s updated" % (
                verse_edit_count, "" if verse_edit_count == 1 else "s")
        summary_text += " - full report: %s" % outcome["report_path"]

        result_var = tk.StringVar(master=root)
        result_var.set(summary_text)
        state["result_var"] = result_var
        result_label = tk.Label(
            bottom_frame, textvariable=result_var, justify="left", anchor="w",
            wraplength=860)
        result_label.pack(fill="x")

        undo_button = tk.Button(controls_frame, text="Undo this run")
        undo_button.pack(side="left")
        new_close_button = tk.Button(controls_frame, text="Close", command=_on_close)
        new_close_button.pack(side="right")

        def _on_undo():
            if state["busy"]:
                return
            confirmed = True
            try:
                confirmed = messagebox.askyesno(
                    "Sortilege",
                    "Undo this run? This restores every moved asset back to "
                    "where it was.")
            except Exception:
                # The messagebox itself failing shouldn't strand the user
                # with no undo at all -- the button click was deliberate.
                confirmed = True
            if not confirmed:
                return

            # run_undo() -- the UNGATED mechanics. The messagebox above is
            # the deliberate confirm in GUI context; going through the
            # console undo() wrapper here would silently block on the
            # (unset) config flag and/or pop a second native EditorDialog
            # on top of the confirm the user just clicked.
            state["busy"] = True
            error_var.set("")
            _assert_on_top()
            undo_results = None
            undo_error = None
            try:
                undo_results = run_undo(outcome["undo_log"].path, state["caps"],
                                         status_callback=_gui_status_callback)
            except Exception as exc:
                undo_error = exc
                _console_warning("Sortilege: undo from the GUI failed (%s)." % exc)
            finally:
                state["busy"] = False

            if undo_error is not None:
                error_var.set("Undo failed: %s -- see the Output Log." % undo_error)
                return
            if not undo_results or undo_results.get("blocked"):
                error_var.set("Undo did not run: %s." % (
                    (undo_results or {}).get("blocked") or "unknown error"))
                return

            restored_count = len(undo_results.get("moved", []))
            undo_failed_count = len(undo_results.get("failed", []))
            result_var.set("Restored %d, failed %d, report: %s" % (
                restored_count, undo_failed_count,
                undo_results.get("report_path", "")))
            # One undo log replays once -- a second click would re-attempt
            # already-restored moves and report them all as failures.
            try:
                undo_button.configure(state="disabled")
            except Exception:
                pass

        undo_button.configure(command=_on_undo)
        state["on_undo"] = _on_undo

    def _on_apply():
        if not apply_var.get():
            return
        if state["busy"]:
            return
        state["busy"] = True
        _set_controls_state(False)
        error_var.set("")
        _assert_on_top()
        try:
            def _pump(_move):
                # update_idletasks() repaints WITHOUT re-dispatching input
                # events; root.update() would re-enter the tkinter event loop
                # mid-operation and (alongside UEFN's own UI on the same
                # thread) crash the editor. Redraw-only is all a batch needs.
                try:
                    root.update_idletasks()
                except Exception:
                    pass

            outcome = run_apply(state["plan"], state["caps"], extra_progress=_pump,
                                 status_callback=_gui_status_callback)
            state["apply_outcome"] = outcome
            _show_results_bar(outcome)
        except Exception as exc:
            _console_warning("Sortilege: GUI apply failed (%s)." % exc)
            error_var.set("Apply failed: %s -- see the Output Log." % exc)
            # busy must clear BEFORE the re-enable: _set_controls_state's
            # closing _refresh_gate() no-ops while busy, which used to
            # leave Apply blanket-enabled (ignoring the checkbox) until
            # the next poll tick.
            state["busy"] = False
            _set_controls_state(True)
        finally:
            state["busy"] = False

    apply_button.configure(command=_on_apply)
    close_button.configure(command=_on_close)

    try:
        root.protocol("WM_DELETE_WINDOW", _on_close)
    except Exception:
        pass

    _refresh_header()
    _refresh_tables()

    return {
        "root": root,
        "state": state,
        "apply_var": apply_var,
        "apply_checkbox": apply_checkbox,
        "apply_button": apply_button,
        "mode_var": mode_var,
        "by_asset_radio": by_asset_radio,
        "safe_mode_var": safe_mode_var,
        "safe_mode_checkbox": safe_mode_checkbox,
        "status_var": status_var,
        "logs_var": logs_var,
        "verse_tree": verse_tree,
        "on_apply": _on_apply,
        "on_rescan": _on_rescan,
        "on_close": _on_close,
    }


def launch_preview_window(plan, caps):
    """Attempt to show the tkinter preview window for `plan`, then block
    in mainloop() until the user closes it (real usage: this IS the
    deliberate in-window confirm gate the feature is built around).

    Returns True if the window was shown. Returns False on ANY failure --
    tkinter import, Tk() construction, or any exception raised while
    building/running the window -- in which case the plain console
    preview (already fully printed before this was ever called) is the
    whole story; this function only ever adds to that, never replaces
    it. Never raises."""
    try:
        import tkinter as tk
        from tkinter import ttk
        from tkinter import messagebox
    except Exception as exc:
        _console_warning(
            "Sortilege: tkinter is not available on this build (%s); "
            "using the console-only preview above." % exc)
        return False

    try:
        handles = _build_preview_window(tk, ttk, messagebox, plan, caps)
        handles["root"].mainloop()
        return True
    except Exception as exc:
        _console_warning(
            "Sortilege: the preview window failed to build or run (%s); "
            "using the console-only preview above." % exc)
        return False


def main(mode=None):
    """Entry point. `mode` overrides sys.argv[1] (handy for direct calls,
    e.g. from tests); when not given, argv[1] is used if present, else
    the safe default "preview". Modes: preview, apply, undo, probe.
    Anything else prints usage and returns without touching anything."""
    if unreal is None:
        # Running under plain system Python (e.g. Windows Command Prompt)
        # there is no project to scan; without this guard the tool would
        # print a misleading empty "Scanned 0 asset(s)" preview.
        print("Sortilege: the 'unreal' module is not available, so there "
              "is no Fortnite project to work on. This script must be run "
              "inside UEFN: open your project, go to Window > Output Log, "
              "set the console dropdown (bottom left) to Cmd, then run: "
              "py \"path/to/sortilege.py\"")
        return

    if mode is None:
        mode = sys.argv[1] if len(sys.argv) > 1 else "preview"
    mode = str(mode).strip().lower()

    # Field report: "I could not find the trace file" -- every mode
    # (preview/apply/undo/probe) writes its plan/report/undo/trace files
    # to the SAME resolve_log_dir() directory, but nothing said so out
    # loud until you dug for it. One loud line, at the very start, before
    # any mode-specific work, so the path is the first thing in the
    # Output Log for every run.
    log_dir = resolve_log_dir(CONFIG)
    _console("Sortilege: logs, trace, and undo files are written to: %s" % log_dir)

    if mode == "probe":
        probe()
        return

    if mode == "undo":
        caps = probe_capabilities()
        log_dir = resolve_log_dir(CONFIG)
        if len(sys.argv) > 2:
            undo_path = sys.argv[2]
            if not os.path.isfile(undo_path):
                _console_warning(
                    "Sortilege: undo log %s does not exist or is not a "
                    "file -- nothing to undo." % undo_path)
                return
        else:
            undo_path = _newest_undo_log(log_dir)
        if not undo_path:
            _console_warning(
                "Sortilege: no sortilege_undo_*.json found in %s -- "
                "nothing to undo." % log_dir)
            return
        undo(undo_path, caps)
        return

    if mode not in ("preview", "apply"):
        _console("Sortilege: unrecognized mode %r." % mode)
        _console("Usage: py \"path/to/sortilege.py\" [preview|apply|undo|probe]")
        return

    caps = probe_capabilities()
    scope_folders = resolve_scope(CONFIG, caps)
    assets = scan_assets(scope_folders)
    plan = build_plan(assets, CONFIG, caps)
    print_preview(plan)

    if mode == "preview":
        log_dir = resolve_log_dir(CONFIG)
        write_plan_json(plan, log_dir)
        # The interactive preview window is an OPTIONAL layer on top of
        # the console preview above, which has already fully run by this
        # point -- launch_preview_window() never raises; on ANY failure
        # (tkinter missing, Tk() construction failing, any exception
        # while building the window) it just logs a warning and returns
        # False, and this preview-mode invocation is already complete
        # exactly as it was before the GUI existed. GUI attaches to
        # preview invocations only -- "apply" stays headless/console-
        # gated below, unconditionally.
        if CONFIG.get("USE_GUI", True):
            launch_preview_window(plan, caps)
        return

    # mode == "apply" -- dry-run preview has already printed above; from
    # here on nothing happens without passing both confirm gates. This
    # console path is untouched by the GUI: it always uses the
    # CONFIG flag + EditorDialog gate, never the in-window checkbox.
    if not confirmed_to_execute(CONFIG, caps, plan):
        if not CONFIG.get("I_UNDERSTAND_THIS_MODIFIES_MY_PROJECT", False):
            for line in _APPLY_BLOCKED_INSTRUCTIONS:
                _console(line)
        else:
            _console("APPLY BLOCKED - declined at the confirm dialog. Nothing was changed.")
        return

    outcome = run_apply(plan, caps)
    results = outcome["results"]
    undo_log = outcome["undo_log"]
    plan_path = outcome["plan_path"]
    report_path = outcome["report_path"]

    moved_count = len(results.get("moved", []))
    failed_count = len(results.get("failed", []))

    _console("")
    _console("=" * 70)
    if results.get("cancelled"):
        _console("RUN CANCELLED BY USER - partial results below.")
    _console("Sortilege apply complete: %d moved, %d failed." % (moved_count, failed_count))
    _console("Plan:   %s" % plan_path)
    _console("Report: %s" % report_path)
    _console("Undo:   py \"%s\" undo \"%s\"" % (
        os.path.abspath(__file__), undo_log.path))
    _console("=" * 70)


if __name__ == "__main__":
    main()
