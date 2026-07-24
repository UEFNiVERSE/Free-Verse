"""Tests for the optional tkinter preview-window layer -- Task: GUI.

Covers the pure, display-free logic the GUI is built on (preview_counts,
plan_to_move_rows, plan_to_skip_rows, apply_folder_map_edits), the
run_apply() refactor (main()'s apply body extracted into one shared
function the console path and the GUI both call), and the GUI shell's
two failure-mode seams:

  1. tkinter genuinely unavailable (sys.modules["tkinter"] = None trick)
     -- main("preview") with USE_GUI True must fall back to the plain
     console preview without crashing.
  2. a FAKE minimal tkinter/ttk/messagebox stub injected directly into
     the window-build function -- proves the construction code and the
     Apply-callback wiring (gated on the checkbox variable) without ever
     touching a real display.

None of these tests create a real tk.Tk() -- this suite must not require
a display. Every test loads a fresh module + fresh mock via
helpers.load_sortilege() so no state leaks between tests.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import helpers
import mock_unreal


def asset(path, class_name):
    folder, name = path.rsplit("/", 1)
    return {"path": path, "name": name, "folder": folder, "class_name": class_name}


# ---------------------------------------------------------------------------
# preview_counts()
# ---------------------------------------------------------------------------

class PreviewCountsTests(unittest.TestCase):
    def setUp(self):
        self.sortilege = helpers.load_sortilege()

    def test_counts_match_format_preview_header_numbers(self):
        config = dict(self.sortilege.CONFIG)
        config["ENABLE_PREFIX_RENAME"] = True
        assets = [
            asset("/Game/Stuff/Boom", "MetaSoundSource"),          # move
            asset("/Game/Stuff/T_Rock", "StaticMesh"),              # move+rename
            asset("/Game/Meshes/T_Boulder", "StaticMesh"),          # rename-in-place
            asset("/Game/Weird/Thing", "SomeUnknownClass"),         # -> Other move
        ]
        for a in assets:
            mock_unreal.add_asset(a["path"], a["class_name"])
        caps = self.sortilege.probe_capabilities()
        plan = self.sortilege.build_plan(assets, config, caps)

        counts = self.sortilege.preview_counts(plan)

        self.assertEqual(counts["scanned"], plan["stats"]["scanned"])
        self.assertEqual(counts["total_to_move"], 3)  # Boom, T_Rock, Weird/Thing
        self.assertEqual(counts["move_rename"], 1)
        self.assertEqual(counts["rename_only"], 1)
        self.assertEqual(counts["skips"], 0)
        self.assertEqual(counts["content_root"], "/Game")
        self.assertEqual(counts["sort_root"], "(none)")
        self.assertIn("Other", counts["by_category"])

    def test_counts_on_empty_plan(self):
        caps = self.sortilege.probe_capabilities()
        plan = self.sortilege.build_plan([], self.sortilege.CONFIG, caps)

        counts = self.sortilege.preview_counts(plan)

        self.assertEqual(counts["scanned"], 0)
        self.assertEqual(counts["total_to_move"], 0)
        self.assertEqual(counts["move_rename"], 0)
        self.assertEqual(counts["rename_only"], 0)
        self.assertEqual(counts["skips"], 0)
        self.assertEqual(counts["by_category"], {})

    def test_format_preview_header_uses_the_same_numbers(self):
        """Regression guard: format_preview()'s header must derive from
        the SAME preview_counts() math, not a second hand-rolled copy
        that could quietly drift."""
        mock_unreal.add_asset("/Game/Stuff/Rock", "StaticMesh")
        assets = [asset("/Game/Stuff/Rock", "StaticMesh")]
        caps = self.sortilege.probe_capabilities()
        plan = self.sortilege.build_plan(assets, self.sortilege.CONFIG, caps)

        counts = self.sortilege.preview_counts(plan)
        lines = self.sortilege.format_preview(plan)
        text = "\n".join(lines)

        self.assertIn(
            "%d asset(s) to move (%d will also be renamed), %d rename-in-place, "
            "%d skipped" % (counts["total_to_move"], counts["move_rename"],
                             counts["rename_only"], counts["skips"]),
            text,
        )


# ---------------------------------------------------------------------------
# plan_to_move_rows() / plan_to_skip_rows()
# ---------------------------------------------------------------------------

class PlanToMoveRowsTests(unittest.TestCase):
    def setUp(self):
        self.sortilege = helpers.load_sortilege()

    def test_rows_grouped_by_category_alphabetically_full_paths(self):
        long_folder = "/Game/" + ("VeryLongSubfolderName/" * 6) + "Deep"
        assets = [
            asset("/Game/Stuff/Wood", "Texture2D"),   # Textures
            asset("/Game/Stuff/Rock", "StaticMesh"),  # Meshes
            asset(long_folder + "/Boom", "SoundWave"),  # Audio, long path
        ]
        for a in assets:
            mock_unreal.add_asset(a["path"], a["class_name"])
        caps = self.sortilege.probe_capabilities()
        plan = self.sortilege.build_plan(assets, self.sortilege.CONFIG, caps)

        rows = self.sortilege.plan_to_move_rows(plan)

        categories = [r["category"] for r in rows]
        self.assertEqual(categories, sorted(categories))
        self.assertEqual(set(categories), {"Audio", "Meshes", "Textures"})

        audio_row = [r for r in rows if r["category"] == "Audio"][0]
        # Full, UNtruncated path -- unlike format_preview()'s 60-char cap.
        self.assertEqual(audio_row["from"], long_folder + "/Boom")
        self.assertGreater(len(audio_row["from"]), 60)
        self.assertEqual(audio_row["to"], "/Game/Audio/Boom")
        self.assertEqual(audio_row["class_name"], "SoundWave")

    def test_empty_plan_gives_empty_rows(self):
        caps = self.sortilege.probe_capabilities()
        plan = self.sortilege.build_plan([], self.sortilege.CONFIG, caps)
        self.assertEqual(self.sortilege.plan_to_move_rows(plan), [])


class PlanToSkipRowsTests(unittest.TestCase):
    def setUp(self):
        self.sortilege = helpers.load_sortilege()

    def test_rows_grouped_by_reason_alphabetically(self):
        mock_unreal.add_asset("/Game/Levels/Main", "World")
        mock_unreal.add_asset("/__ExternalActors__/x/Foo", "StaticMesh")
        assets = [
            asset("/Game/Levels/Main", "World"),
            asset("/__ExternalActors__/x/Foo", "StaticMesh"),
        ]
        caps = self.sortilege.probe_capabilities()
        plan = self.sortilege.build_plan(assets, self.sortilege.CONFIG, caps)

        rows = self.sortilege.plan_to_skip_rows(plan)

        reasons = [r["reason"] for r in rows]
        self.assertEqual(reasons, sorted(reasons))
        self.assertEqual(len(rows), 2)
        for row in rows:
            self.assertIn("path", row)
            self.assertIn("class_name", row)

    def test_empty_plan_gives_empty_rows(self):
        caps = self.sortilege.probe_capabilities()
        plan = self.sortilege.build_plan([], self.sortilege.CONFIG, caps)
        self.assertEqual(self.sortilege.plan_to_skip_rows(plan), [])


# ---------------------------------------------------------------------------
# apply_folder_map_edits()
# ---------------------------------------------------------------------------

class ApplyFolderMapEditsTests(unittest.TestCase):
    def setUp(self):
        self.sortilege = helpers.load_sortilege()

    def test_valid_edit_updates_config_in_place_and_returns_none(self):
        config = dict(self.sortilege.CONFIG)
        config["FOLDER_MAP"] = dict(config["FOLDER_MAP"])
        edits = {"FOLDER_MAP": {"Meshes": "3D/Meshes"}, "SORT_ROOT": "_Sorted"}

        error = self.sortilege.apply_folder_map_edits(config, edits)

        self.assertIsNone(error)
        self.assertEqual(config["FOLDER_MAP"]["Meshes"], "3D/Meshes")
        self.assertEqual(config["SORT_ROOT"], "_Sorted")
        # Untouched categories are left alone.
        self.assertEqual(config["FOLDER_MAP"]["Textures"], "Textures")

    def test_empty_sort_root_is_valid_meaning_content_root(self):
        config = dict(self.sortilege.CONFIG)
        edits = {"SORT_ROOT": ""}

        error = self.sortilege.apply_folder_map_edits(config, edits)

        self.assertIsNone(error)
        self.assertEqual(config["SORT_ROOT"], "")

    def test_illegal_character_in_folder_name_rejected_and_config_unchanged(self):
        config = dict(self.sortilege.CONFIG)
        config["FOLDER_MAP"] = dict(config["FOLDER_MAP"])
        original = dict(config["FOLDER_MAP"])
        edits = {"FOLDER_MAP": {"Meshes": "Bad:Name"}}

        error = self.sortilege.apply_folder_map_edits(config, edits)

        self.assertIsNotNone(error)
        self.assertEqual(error["field"], "FOLDER_MAP.Meshes")
        self.assertEqual(config["FOLDER_MAP"], original)

    def test_empty_folder_name_rejected(self):
        config = dict(self.sortilege.CONFIG)
        config["FOLDER_MAP"] = dict(config["FOLDER_MAP"])
        edits = {"FOLDER_MAP": {"Meshes": ""}}

        error = self.sortilege.apply_folder_map_edits(config, edits)

        self.assertIsNotNone(error)

    def test_bad_sort_root_rejected_and_folder_map_edits_not_partially_applied(self):
        """One bad field must block the WHOLE edit -- never a partial
        apply that leaves FOLDER_MAP changed but SORT_ROOT not, or
        vice versa."""
        config = dict(self.sortilege.CONFIG)
        config["FOLDER_MAP"] = dict(config["FOLDER_MAP"])
        original_map = dict(config["FOLDER_MAP"])
        original_sort_root = config["SORT_ROOT"]
        edits = {"FOLDER_MAP": {"Meshes": "GoodName"}, "SORT_ROOT": "Bad*Root"}

        error = self.sortilege.apply_folder_map_edits(config, edits)

        self.assertIsNotNone(error)
        self.assertEqual(error["field"], "SORT_ROOT")
        self.assertEqual(config["FOLDER_MAP"], original_map)
        self.assertEqual(config["SORT_ROOT"], original_sort_root)

    def test_whitespace_only_name_rejected(self):
        config = dict(self.sortilege.CONFIG)
        config["FOLDER_MAP"] = dict(config["FOLDER_MAP"])
        edits = {"FOLDER_MAP": {"Meshes": " Meshes "}}

        error = self.sortilege.apply_folder_map_edits(config, edits)

        self.assertIsNotNone(error)

    def test_unknown_category_key_rejected_not_setdefaulted(self):
        """Review fix: an edit keyed by a category that does not exist in
        FOLDER_MAP must be rejected with an error entry -- never silently
        setdefault'ed in as a brand-new category."""
        config = dict(self.sortilege.CONFIG)
        config["FOLDER_MAP"] = dict(config["FOLDER_MAP"])
        original = dict(config["FOLDER_MAP"])
        edits = {"FOLDER_MAP": {"Bogus": "SomewhereValid"}}

        error = self.sortilege.apply_folder_map_edits(config, edits)

        self.assertIsNotNone(error)
        self.assertEqual(error["field"], "FOLDER_MAP.Bogus")
        self.assertNotIn("Bogus", config["FOLDER_MAP"])
        self.assertEqual(config["FOLDER_MAP"], original)


# ---------------------------------------------------------------------------
# run_apply() -- the shared apply pipeline (main()'s console path + the
# GUI's Apply button both call this; refactored out of main() so there is
# exactly one place that can move an asset for real).
# ---------------------------------------------------------------------------

class RunApplyDirectTests(unittest.TestCase):
    def setUp(self):
        self.sortilege = helpers.load_sortilege()

    def test_run_apply_called_directly_matches_console_apply_outcome(self):
        """Adapted from test_main_flow.ApplyGateEndToEndTests.
        test_apply_executes_when_dialog_confirmed -- but called directly,
        with NO confirm gate and NO argv involved at all, proving
        run_apply() itself does not re-implement (or bypass-and-forget)
        any gating -- gating is entirely the CALLER's job now."""
        mock_unreal.add_asset("/Game/Stuff/Rock", "StaticMesh")
        assets = [asset("/Game/Stuff/Rock", "StaticMesh")]
        caps = self.sortilege.probe_capabilities()
        plan = self.sortilege.build_plan(assets, self.sortilege.CONFIG, caps)

        outcome = self.sortilege.run_apply(plan, caps)

        state = mock_unreal.get_state()
        self.assertIn("/Game/Meshes/Rock", state["assets"])
        self.assertNotIn("/Game/Stuff/Rock", state["assets"])

        self.assertEqual(outcome["results"]["moved"],
                          [("/Game/Stuff/Rock", "/Game/Meshes/Rock")])
        self.assertEqual(outcome["results"]["failed"], [])
        self.assertIn("redirector_cleanup", outcome["results"])
        self.assertIn("verify", outcome["results"])
        self.assertTrue(os.path.isfile(outcome["plan_path"]))
        self.assertTrue(os.path.isfile(outcome["report_path"]))
        self.assertEqual(len(outcome["undo_log"].moves), 1)
        self.assertTrue(os.path.isfile(outcome["undo_log"].path))

    def test_run_apply_matches_main_apply_mode_end_state(self):
        """Same starting state run through BOTH main(mode="apply") (the
        console path, gated) and a direct run_apply() call (the GUI's
        path, ungated) on a fresh mock each time -- both must reach the
        identical end state. This is the refactor's safety proof: one
        pipeline, two callers."""
        mock_unreal.add_asset("/Game/Stuff/Rock", "StaticMesh")
        self.sortilege.CONFIG["I_UNDERSTAND_THIS_MODIFIES_MY_PROJECT"] = True
        mock_unreal.set_dialog_answer("Yes")
        self.sortilege.main(mode="apply")
        console_state = dict(mock_unreal.get_state()["assets"])

        sortilege2 = helpers.load_sortilege()
        mock_unreal.add_asset("/Game/Stuff/Rock", "StaticMesh")
        assets = [asset("/Game/Stuff/Rock", "StaticMesh")]
        caps = sortilege2.probe_capabilities()
        plan = sortilege2.build_plan(assets, sortilege2.CONFIG, caps)
        sortilege2.run_apply(plan, caps)
        gui_state = dict(mock_unreal.get_state()["assets"])

        self.assertEqual(set(console_state.keys()), set(gui_state.keys()))
        self.assertIn("/Game/Meshes/Rock", console_state)
        self.assertIn("/Game/Meshes/Rock", gui_state)

    def test_run_apply_extra_progress_fires_once_per_move(self):
        """The GUI's root.update() pump hook -- extra_progress must be
        called once per move, same timing as execute_plan()'s own
        progress callback (before that item's move is attempted)."""
        mock_unreal.add_asset("/Game/Stuff/Rock", "StaticMesh")
        mock_unreal.add_asset("/Game/Stuff/Wood", "Texture2D")
        assets = [asset("/Game/Stuff/Rock", "StaticMesh"),
                  asset("/Game/Stuff/Wood", "Texture2D")]
        caps = self.sortilege.probe_capabilities()
        plan = self.sortilege.build_plan(assets, self.sortilege.CONFIG, caps)

        calls = []
        outcome = self.sortilege.run_apply(
            plan, caps, extra_progress=lambda m: calls.append(m["path"]))

        self.assertEqual(len(calls), 2)
        self.assertEqual(len(outcome["results"]["moved"]), 2)

    def test_run_apply_extra_progress_exception_does_not_abort_batch(self):
        """A UI hiccup in the pump callback must never abort a batch --
        same swallow-and-continue contract execute_plan() already gives
        its own progress callback."""
        mock_unreal.add_asset("/Game/Stuff/Rock", "StaticMesh")
        assets = [asset("/Game/Stuff/Rock", "StaticMesh")]
        caps = self.sortilege.probe_capabilities()
        plan = self.sortilege.build_plan(assets, self.sortilege.CONFIG, caps)

        def _boom(_move):
            raise RuntimeError("simulated UI hiccup")

        outcome = self.sortilege.run_apply(plan, caps, extra_progress=_boom)

        self.assertEqual(outcome["results"]["moved"],
                          [("/Game/Stuff/Rock", "/Game/Meshes/Rock")])
        self.assertEqual(outcome["results"]["failed"], [])


# ---------------------------------------------------------------------------
# GUI shell -- import-guard fallback (tkinter genuinely absent)
# ---------------------------------------------------------------------------

class GuiImportGuardTests(unittest.TestCase):
    def setUp(self):
        self._had_tkinter = "tkinter" in sys.modules
        self._saved_tkinter = sys.modules.get("tkinter")
        # The standard trick: None in sys.modules forces `import tkinter`
        # to raise ImportError immediately, without needing tkinter to be
        # genuinely uninstalled on this machine.
        sys.modules["tkinter"] = None
        self.sortilege = helpers.load_sortilege(config_overrides={"USE_GUI": True})

    def tearDown(self):
        if self._had_tkinter:
            sys.modules["tkinter"] = self._saved_tkinter
        else:
            sys.modules.pop("tkinter", None)

    def test_preview_falls_back_to_console_when_tkinter_import_fails(self):
        mock_unreal.add_asset("/Game/Stuff/Rock", "StaticMesh")

        self.sortilege.main(mode="preview")  # must not raise/hang

        state = mock_unreal.get_state()
        # Never mutates -- preview stays a dry run even with the GUI
        # attempted-and-failed.
        self.assertIn("/Game/Stuff/Rock", state["assets"])
        self.assertNotIn("/Game/Meshes/Rock", state["assets"])
        logged = "\n".join(state["log"])
        self.assertIn("dry run preview", logged)

    def test_launch_preview_window_returns_false_on_import_failure(self):
        caps = self.sortilege.probe_capabilities()
        plan = self.sortilege.build_plan([], self.sortilege.CONFIG, caps)

        shown = self.sortilege.launch_preview_window(plan, caps)

        self.assertFalse(shown)
        logged = "\n".join(mock_unreal.get_state()["log"]).lower()
        self.assertTrue("tkinter" in logged)


# ---------------------------------------------------------------------------
# GUI shell -- fake minimal tkinter stub, testing the seam not the pixels
# ---------------------------------------------------------------------------
# These fakes are deliberately generic/minimal: every widget class accepts
# any args/kwargs and no-ops every layout/config call, so the window-build
# function can run start to finish without a display. The one thing that
# must behave for real is BooleanVar (get/set) and Button's stored
# `command` callable, since that's the actual seam under test: the Apply
# button must only invoke run_apply() when the checkbox variable is True.

class _FakeWidget(object):
    def __init__(self, *args, **kwargs):
        self._kwargs = kwargs
        self.command = kwargs.get("command")
        self._state_flags = set()
        self._bindings = {}

    def __getattr__(self, name):
        # Any unrecognized method call (pack, grid, heading, column,
        # insert, delete, get_children, winfo_children, ...) becomes a
        # no-op that returns an empty list (safe for "for x in
        # widget.get_children()"-style callers) or None.
        def _noop(*a, **k):
            return []
        return _noop

    def configure(self, **kwargs):
        self._kwargs.update(kwargs)
        if "command" in kwargs:
            self.command = kwargs["command"]

    def bind(self, event, callback):
        self._bindings[event] = callback

    def state(self, flags=None):
        """ttk-style state query/set. Query (no args): reports "selected"
        when the widget's attached variable is truthy (or the flag was
        set directly), plus any explicitly-set flags like "disabled".
        Set: applies "flag" / "!flag" items like ttk does."""
        if flags is None:
            current = []
            var = self._kwargs.get("variable")
            selected = "selected" in self._state_flags
            if not selected and var is not None:
                try:
                    selected = bool(var.get())
                except Exception:
                    selected = False
            if selected:
                current.append("selected")
            for flag in sorted(self._state_flags):
                if flag not in current:
                    current.append(flag)
            return tuple(current)
        for flag in flags:
            if flag.startswith("!"):
                self._state_flags.discard(flag[1:])
            else:
                self._state_flags.add(flag)
        return None

    def get(self):
        return self._kwargs.get("_text", "")

    def insert(self, *args, **kwargs):
        return None

    def winfo_exists(self):
        return True

    def winfo_children(self):
        return []


class _FakeEntry(_FakeWidget):
    def __init__(self, *args, **kwargs):
        _FakeWidget.__init__(self, *args, **kwargs)
        self._text = ""

    def insert(self, index, text):
        self._text = self._text[:index] + text + self._text[index:]

    def get(self):
        return self._text

    def delete(self, *args, **kwargs):
        self._text = ""


class _FakeTreeview(_FakeWidget):
    """Unlike the generic _FakeWidget (whose insert()/get_children() are
    inert no-ops), this tracks every insert()'s `values` tuple in order
    -- lets tests verify a Treeview's actual populated content, not just
    that construction/wiring didn't crash. delete() always clears
    everything regardless of which item id(s) it's called with, which is
    behaviorally equivalent here: every real caller in this file always
    walks get_children() and deletes every item before repopulating (see
    _refresh_tables()), never a single selective delete."""

    def __init__(self, *args, **kwargs):
        _FakeWidget.__init__(self, *args, **kwargs)
        self.inserted_rows = []

    def insert(self, parent, index, values=None, **kwargs):
        self.inserted_rows.append(values)
        return None

    def get_children(self):
        return list(range(len(self.inserted_rows)))

    def delete(self, *args, **kwargs):
        self.inserted_rows = []


class _FakeBooleanVar(object):
    def __init__(self, master=None, value=False):
        self._master = master
        self._value = value
        self._callbacks = []

    def get(self):
        return self._value

    def set(self, value):
        self._value = value
        for cb in self._callbacks:
            cb()

    def trace_add(self, mode, callback):
        self._callbacks.append(callback)

    def trace(self, mode, callback):
        self._callbacks.append(lambda *a: callback())


class _FakeStringVar(object):
    def __init__(self, master=None, value=""):
        self._master = master
        self._value = value
        # Every set() call recorded, in order -- lets tests recover the
        # full sequence of status-label updates during a real run, not
        # just the final value.
        self.history = [value]

    def get(self):
        return self._value

    def set(self, value):
        self._value = value
        self.history.append(value)


class _FakeTk(object):
    """Root stand-in. mainloop()/destroy()/protocol() are no-ops so the
    window-build call returns immediately in tests -- a real root would
    block in mainloop() until the user closes it. after()/after_idle()/
    after_cancel() model tk's deferred-callback registry: callbacks are
    RECORDED, never auto-run -- tests fire them explicitly with
    run_pending(), which is how "only the poll loop is alive" scenarios
    get simulated."""

    def __init__(self, *args, **kwargs):
        self._destroyed = False
        self._children = []
        self._pending = {}
        self._cancelled = []
        self._after_seq = [0]
        # Recorded, real behavior for the on-top window seam: every
        # attributes(...) call args tuple, and a plain lift() counter --
        # the seam under test for the "window hid behind the editor" fix.
        self.attributes_calls = []
        self.lift_calls = 0

    def title(self, *a, **k):
        pass

    def geometry(self, *a, **k):
        pass

    def resizable(self, *a, **k):
        pass

    def protocol(self, *a, **k):
        pass

    def mainloop(self):
        pass

    def update(self):
        pass

    def attributes(self, *args, **kwargs):
        self.attributes_calls.append(args)

    def lift(self):
        self.lift_calls += 1

    def after(self, _ms, callback):
        self._after_seq[0] += 1
        after_id = "after#%d" % self._after_seq[0]
        self._pending[after_id] = callback
        return after_id

    def after_idle(self, callback):
        return self.after(0, callback)

    def after_cancel(self, after_id):
        self._cancelled.append(after_id)
        self._pending.pop(after_id, None)

    def run_pending(self):
        """Fire every currently-pending after/after_idle callback once
        (snapshot semantics: callbacks that re-schedule themselves stay
        pending for the NEXT run_pending call, like a real event loop
        tick)."""
        snapshot = list(self._pending.items())
        for after_id, callback in snapshot:
            self._pending.pop(after_id, None)
            callback()

    def destroy(self):
        self._destroyed = True

    def winfo_exists(self):
        return not self._destroyed

    def winfo_children(self):
        return []


def _make_fake_tk_module():
    fake_tk = type("FakeTkModule", (object,), {})
    fake_tk.Tk = _FakeTk
    fake_tk.Frame = _FakeWidget
    fake_tk.Label = _FakeWidget
    fake_tk.Button = _FakeWidget
    fake_tk.Checkbutton = _FakeWidget
    fake_tk.Radiobutton = _FakeWidget
    fake_tk.Entry = _FakeEntry
    fake_tk.BooleanVar = _FakeBooleanVar
    fake_tk.StringVar = _FakeStringVar
    return fake_tk


def _make_fake_ttk_module():
    fake_ttk = type("FakeTtkModule", (object,), {})
    fake_ttk.Notebook = _FakeWidget
    fake_ttk.Frame = _FakeWidget
    fake_ttk.Treeview = _FakeTreeview
    fake_ttk.Scrollbar = _FakeWidget
    fake_ttk.Button = _FakeWidget
    fake_ttk.Label = _FakeWidget
    fake_ttk.Entry = _FakeEntry
    fake_ttk.Checkbutton = _FakeWidget
    return fake_ttk


class _FakeMessagebox(object):
    answer = True

    @classmethod
    def askyesno(cls, *a, **k):
        return cls.answer

    @staticmethod
    def showinfo(*a, **k):
        pass

    @staticmethod
    def showerror(*a, **k):
        pass


class GuiShellSeamTests(unittest.TestCase):
    def setUp(self):
        self.sortilege = helpers.load_sortilege()
        # Every test gets its own fresh singleton slot.
        self.sortilege._GUI_ROOT = None

    def _plan(self):
        mock_unreal.add_asset("/Game/Stuff/Rock", "StaticMesh")
        assets = [asset("/Game/Stuff/Rock", "StaticMesh")]
        caps = self.sortilege.probe_capabilities()
        plan = self.sortilege.build_plan(assets, self.sortilege.CONFIG, caps)
        return plan, caps

    def test_build_function_consumes_plan_data_without_error(self):
        plan, caps = self._plan()
        fake_tk = _make_fake_tk_module()
        fake_ttk = _make_fake_ttk_module()

        handles = self.sortilege._build_preview_window(
            fake_tk, fake_ttk, _FakeMessagebox, plan, caps)  # must not raise

        self.assertIn("root", handles)
        self.assertIn("apply_var", handles)
        self.assertIn("apply_button", handles)
        self.assertIn("on_apply", handles)

    def test_apply_callback_does_not_call_run_apply_when_checkbox_unchecked(self):
        plan, caps = self._plan()
        fake_tk = _make_fake_tk_module()
        fake_ttk = _make_fake_ttk_module()
        handles = self.sortilege._build_preview_window(
            fake_tk, fake_ttk, _FakeMessagebox, plan, caps)

        calls = []
        original_run_apply = self.sortilege.run_apply
        self.sortilege.run_apply = lambda *a, **k: calls.append(1) or {
            "results": {"moved": [], "failed": []}, "plan_path": "x",
            "report_path": "y", "undo_log": type("U", (), {"path": "z"})(),
        }
        try:
            self.assertFalse(handles["apply_var"].get())
            handles["on_apply"]()
            self.assertEqual(calls, [])

            handles["apply_var"].set(True)
            handles["on_apply"]()
            self.assertEqual(calls, [1])
        finally:
            self.sortilege.run_apply = original_run_apply

        # Nothing was actually moved in the mock -- the checkbox-gated
        # call above used a stubbed run_apply, proving the SEAM (the
        # callback only proceeds when ticked) without needing the fake
        # tkinter stub to also fake out the real apply pipeline.
        state = mock_unreal.get_state()
        self.assertIn("/Game/Stuff/Rock", state["assets"])

    def test_checkbox_toggle_enables_and_disables_apply_button(self):
        plan, caps = self._plan()
        fake_tk = _make_fake_tk_module()
        fake_ttk = _make_fake_ttk_module()
        handles = self.sortilege._build_preview_window(
            fake_tk, fake_ttk, _FakeMessagebox, plan, caps)

        self.assertEqual(handles["apply_button"]._kwargs.get("state"), "disabled")
        handles["apply_var"].set(True)
        self.assertEqual(handles["apply_button"]._kwargs.get("state"), "normal")
        handles["apply_var"].set(False)
        self.assertEqual(handles["apply_button"]._kwargs.get("state"), "disabled")


# ---------------------------------------------------------------------------
# Sorting-mode radio pair (Folder mapping tab) -- group-by-asset seam
# ---------------------------------------------------------------------------

class GuiSortingModeSeamTests(unittest.TestCase):
    def setUp(self):
        self.sortilege = helpers.load_sortilege()
        self.sortilege._GUI_ROOT = None

    def _window(self, features=None):
        if features is not None:
            self.sortilege = helpers.load_sortilege(features=features)
            self.sortilege._GUI_ROOT = None
        mock_unreal.add_asset("/Game/Stuff/SM_Rock", "StaticMesh",
                               deps=["/Game/Stuff/T_R"])
        mock_unreal.add_asset("/Game/Stuff/T_R", "Texture2D")
        assets = [asset("/Game/Stuff/SM_Rock", "StaticMesh"),
                  asset("/Game/Stuff/T_R", "Texture2D")]
        caps = self.sortilege.probe_capabilities()
        plan = self.sortilege.build_plan(assets, self.sortilege.CONFIG, caps)
        return self.sortilege._build_preview_window(
            _make_fake_tk_module(), _make_fake_ttk_module(), _FakeMessagebox,
            plan, caps)

    def test_mode_radio_flips_config_and_rescan_groups(self):
        handles = self._window()
        self.assertIn("mode_var", handles)
        self.assertEqual(handles["mode_var"].get(), "flat")
        self.assertFalse(self.sortilege.CONFIG["GROUP_BY_ASSET"])

        handles["mode_var"].set("by_asset")
        handles["on_rescan"]()

        self.assertTrue(self.sortilege.CONFIG["GROUP_BY_ASSET"])
        self.assertIn("grouping", handles["state"]["plan"])
        dests = dict((m["path"], m["dest_path"])
                     for m in handles["state"]["plan"]["moves"])
        self.assertEqual(dests["/Game/Stuff/SM_Rock"],
                          "/Game/Meshes/Rock/SM_Rock")

    def test_mode_radio_back_to_flat_ungroups(self):
        handles = self._window()
        handles["mode_var"].set("by_asset")
        handles["on_rescan"]()
        self.assertIn("grouping", handles["state"]["plan"])

        handles["mode_var"].set("flat")
        handles["on_rescan"]()

        self.assertFalse(self.sortilege.CONFIG["GROUP_BY_ASSET"])
        self.assertNotIn("grouping", handles["state"]["plan"])

    def test_by_asset_radio_disabled_when_capability_absent(self):
        handles = self._window(features={"dependency_query": False})
        radio = handles.get("by_asset_radio")
        self.assertIsNotNone(radio)
        self.assertEqual(radio._kwargs.get("state"), "disabled")


# ---------------------------------------------------------------------------
# Safe mode checkbox (Folder mapping tab) -- crash-diagnostics bisect
# valve; mirrors CONFIG["SAFE_MODE"] straight through, no Re-scan needed.
# ---------------------------------------------------------------------------

class GuiSafeModeSeamTests(unittest.TestCase):
    def setUp(self):
        self.sortilege = helpers.load_sortilege()
        self.sortilege._GUI_ROOT = None

    def _window(self):
        mock_unreal.add_asset("/Game/Stuff/Rock", "StaticMesh")
        assets = [asset("/Game/Stuff/Rock", "StaticMesh")]
        caps = self.sortilege.probe_capabilities()
        plan = self.sortilege.build_plan(assets, self.sortilege.CONFIG, caps)
        return self.sortilege._build_preview_window(
            _make_fake_tk_module(), _make_fake_ttk_module(), _FakeMessagebox,
            plan, caps)

    def test_safe_mode_checkbox_defaults_unchecked_and_matches_config(self):
        self.assertFalse(self.sortilege.CONFIG["SAFE_MODE"])
        handles = self._window()

        self.assertIn("safe_mode_var", handles)
        self.assertIn("safe_mode_checkbox", handles)
        self.assertFalse(handles["safe_mode_var"].get())

    def test_toggling_safe_mode_checkbox_updates_config_immediately(self):
        handles = self._window()

        handles["safe_mode_var"].set(True)
        handles["safe_mode_checkbox"].command()
        self.assertTrue(self.sortilege.CONFIG["SAFE_MODE"])

        handles["safe_mode_var"].set(False)
        handles["safe_mode_checkbox"].command()
        self.assertFalse(self.sortilege.CONFIG["SAFE_MODE"])

    def test_safe_mode_checkbox_starts_checked_when_config_file_set_it_true(self):
        """The Minor fallback the spec explicitly allows for -- even
        without ever touching the checkbox, a SAFE_MODE=True set in the
        config file itself must be honored by the GUI apply path (run_
        apply() already reads CONFIG directly). This test additionally
        confirms the checkbox's initial state reflects that file value."""
        sortilege = helpers.load_sortilege(config_overrides={"SAFE_MODE": True})
        sortilege._GUI_ROOT = None
        mock_unreal.add_asset("/Game/Stuff/Rock", "StaticMesh")
        assets = [asset("/Game/Stuff/Rock", "StaticMesh")]
        caps = sortilege.probe_capabilities()
        plan = sortilege.build_plan(assets, sortilege.CONFIG, caps)
        handles = sortilege._build_preview_window(
            _make_fake_tk_module(), _make_fake_ttk_module(), _FakeMessagebox,
            plan, caps)

        self.assertTrue(handles["safe_mode_var"].get())

    def test_safe_mode_checkbox_disabled_during_an_in_flight_apply(self):
        """The checkbox is wired into the same all_controls sweep as
        every other mapping-tab input, so it gets disabled for the
        duration of a run exactly like rescan_button/mapping_entries do
        -- proven here by inspecting its state from INSIDE a stubbed
        run_apply() call, i.e. while _on_apply() has it disabled."""
        handles = self._window()
        handles["apply_var"].set(True)

        captured = {}
        original_run_apply = self.sortilege.run_apply

        def _capture_mid_run(plan_arg, caps_arg, extra_progress=None, status_callback=None):
            captured["state"] = handles["safe_mode_checkbox"]._kwargs.get("state")
            return original_run_apply(plan_arg, caps_arg, extra_progress=extra_progress,
                                       status_callback=status_callback)

        self.sortilege.run_apply = _capture_mid_run
        try:
            handles["on_apply"]()
        finally:
            self.sortilege.run_apply = original_run_apply

        self.assertEqual(captured.get("state"), "disabled")


# ---------------------------------------------------------------------------
# Confirm-gate wiring -- field-report fix: in UEFN's embedded tk 3.11,
# ticking the checkbox did NOT un-gray the Apply button (it worked on
# desktop tk). Root cause unknowable from here, so the gate is wired
# through THREE redundant signals (Checkbutton command=, variable trace,
# <ButtonRelease-1> bind -> after_idle) plus an ultimate-fallback 200ms
# root.after poll -- ANY one of them alive un-grays the button. These
# tests exercise each signal in isolation against the fake-tk seam.
# ---------------------------------------------------------------------------

class GuiGateWiringTests(unittest.TestCase):
    def setUp(self):
        self.sortilege = helpers.load_sortilege()
        self.sortilege._GUI_ROOT = None

    def _window(self):
        mock_unreal.add_asset("/Game/Stuff/Rock", "StaticMesh")
        assets = [asset("/Game/Stuff/Rock", "StaticMesh")]
        caps = self.sortilege.probe_capabilities()
        plan = self.sortilege.build_plan(assets, self.sortilege.CONFIG, caps)
        return self.sortilege._build_preview_window(
            _make_fake_tk_module(), _make_fake_ttk_module(), _FakeMessagebox,
            plan, caps)

    def _silently_check(self, handles):
        """Flip the checkbox variable WITHOUT firing any event mechanism:
        dead trace (cleared callbacks), no command call, no bind fire --
        the exact situation the field report describes."""
        handles["apply_var"]._callbacks = []
        handles["apply_var"]._value = True

    def test_poll_alone_enables_button_when_all_event_wiring_dead(self):
        handles = self._window()
        self._silently_check(handles)
        # No signal has fired -- still gated.
        self.assertEqual(handles["apply_button"]._kwargs.get("state"), "disabled")

        # The 200ms fallback poll fires (simulated event-loop tick).
        handles["root"].run_pending()

        self.assertEqual(handles["apply_button"]._kwargs.get("state"), "normal")
        # And the poll re-scheduled itself -- the window is still alive.
        self.assertTrue(handles["root"]._pending)

    def test_checkbutton_command_alone_enables_button(self):
        handles = self._window()
        self._silently_check(handles)
        self.assertEqual(handles["apply_button"]._kwargs.get("state"), "disabled")

        # Real tk invokes command= AFTER toggling the variable.
        handles["apply_checkbox"].command()

        self.assertEqual(handles["apply_button"]._kwargs.get("state"), "normal")

    def test_button_release_bind_alone_enables_button(self):
        handles = self._window()
        self._silently_check(handles)
        binding = handles["apply_checkbox"]._bindings.get("<ButtonRelease-1>")
        self.assertIsNotNone(binding)

        binding(None)               # the click releases...
        handles["root"].run_pending()  # ...and the after_idle refresh runs

        self.assertEqual(handles["apply_button"]._kwargs.get("state"), "normal")

    def test_gate_falls_back_to_widget_state_when_var_get_raises(self):
        handles = self._window()

        def _boom():
            raise RuntimeError("simulated dead Variable in embedded tk")

        handles["apply_var"].get = _boom
        # The widget's own ttk state still knows it's ticked.
        handles["apply_checkbox"].state(["selected"])

        handles["root"].run_pending()

        self.assertEqual(handles["apply_button"]._kwargs.get("state"), "normal")

    def test_gate_sets_ttk_state_flags_as_well_as_configure(self):
        handles = self._window()
        self.assertIn("disabled", handles["apply_button"].state())

        handles["apply_var"].set(True)

        self.assertNotIn("disabled", handles["apply_button"].state())
        self.assertEqual(handles["apply_button"]._kwargs.get("state"), "normal")

    def test_poll_cancelled_after_close(self):
        handles = self._window()
        root = handles["root"]
        poll_id = handles["state"].get("poll_id")
        self.assertIsNotNone(poll_id)

        handles["on_close"]()

        # The pending poll was explicitly cancelled -- no dangling after
        # callbacks on a destroyed window.
        self.assertIn(poll_id, root._cancelled)
        self.assertEqual(root._pending, {})
        # And even if a stale tick DID somehow fire, the closed flag stops
        # the loop from re-scheduling.
        root.run_pending()
        self.assertEqual(root._pending, {})

    def test_poll_does_not_reenable_apply_while_run_in_flight(self):
        handles = self._window()
        handles["apply_var"]._callbacks = []
        handles["apply_var"]._value = True
        handles["state"]["busy"] = True
        handles["apply_button"].configure(state="disabled")

        handles["root"].run_pending()

        self.assertEqual(handles["apply_button"]._kwargs.get("state"), "disabled")

    def test_gate_state_changes_are_logged_for_field_diagnosis(self):
        handles = self._window()
        log_before = len(mock_unreal.get_state()["log"])

        handles["apply_var"].set(True)

        new_lines = [str(l) for l in mock_unreal.get_state()["log"][log_before:]]
        gate_lines = [l for l in new_lines if "Sortilege GUI: confirm=" in l]
        self.assertTrue(gate_lines)
        self.assertIn("confirm=True", gate_lines[-1])
        self.assertIn("apply button=normal", gate_lines[-1])

    def test_failed_apply_reenables_controls_honoring_checkbox_immediately(self):
        """Review fix (MINOR): in _on_apply's except branch,
        _set_controls_state(True) used to run while state["busy"] was
        still True (finally cleared it AFTERWARD), so the closing
        _refresh_gate() no-op'd and Apply came back blanket-enabled --
        ignoring the checkbox -- until the next poll tick. busy must be
        cleared BEFORE the re-enable, so the gate applies immediately."""
        handles = self._window()
        handles["apply_var"].set(True)

        original_run_apply = self.sortilege.run_apply

        def _fail_and_untick(plan_arg, caps_arg, extra_progress=None, status_callback=None):
            # The checkbox flips off during the failed run (silently --
            # no trace fires, mirroring an embedded-tk quirk); after the
            # failure the button must honor the CURRENT checkbox state
            # immediately, not wait for the poll.
            handles["apply_var"]._callbacks = []
            handles["apply_var"]._value = False
            raise RuntimeError("simulated apply failure")

        self.sortilege.run_apply = _fail_and_untick
        try:
            handles["on_apply"]()
        finally:
            self.sortilege.run_apply = original_run_apply

        self.assertFalse(handles["state"]["busy"])
        self.assertEqual(handles["apply_button"]._kwargs.get("state"),
                          "disabled")


# ---------------------------------------------------------------------------
# run_undo() -- the ungated undo mechanics (mirror of the run_apply
# extraction: console `undo` mode keeps its two-gate wrapper, the GUI's
# "Undo this run" button calls this directly -- its own tkinter messagebox
# confirm IS the deliberate confirm in GUI context).
# ---------------------------------------------------------------------------

class RunUndoDirectTests(unittest.TestCase):
    def setUp(self):
        self.sortilege = helpers.load_sortilege()
        import tempfile
        self.tmp_dir = tempfile.mkdtemp(prefix="sortilege_test_")
        self.sortilege.CONFIG["LOG_DIR"] = self.tmp_dir

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _applied_run(self):
        mock_unreal.add_asset("/Game/Stuff/Rock", "StaticMesh")
        assets = [asset("/Game/Stuff/Rock", "StaticMesh")]
        caps = self.sortilege.probe_capabilities()
        plan = self.sortilege.build_plan(assets, self.sortilege.CONFIG, caps)
        outcome = self.sortilege.run_apply(plan, caps)
        return outcome, caps

    def test_run_undo_restores_without_any_gate(self):
        """run_undo() must restore with the config flag at its DEFAULT
        False and no dialog answer queued -- it is the ungated mechanics;
        gating (console flag+dialog, or the GUI messagebox) is entirely
        the caller's job."""
        outcome, caps = self._applied_run()
        self.assertFalse(
            self.sortilege.CONFIG["I_UNDERSTAND_THIS_MODIFIES_MY_PROJECT"])

        results = self.sortilege.run_undo(outcome["undo_log"].path, caps)

        self.assertEqual(results["moved"],
                          [("/Game/Meshes/Rock", "/Game/Stuff/Rock")])
        state = mock_unreal.get_state()
        self.assertIn("/Game/Stuff/Rock", state["assets"])
        self.assertNotIn("/Game/Meshes/Rock", state["assets"])
        # The GUI results bar needs the report path.
        self.assertTrue(results.get("report_path"))
        self.assertTrue(os.path.isfile(results["report_path"]))

    def test_run_undo_never_pops_the_editor_dialog(self):
        outcome, caps = self._applied_run()
        self.assertTrue(caps.editor_dialog)
        log_before = len(mock_unreal.get_state()["log"])

        self.sortilege.run_undo(outcome["undo_log"].path, caps)

        new_lines = mock_unreal.get_state()["log"][log_before:]
        dialog_lines = [l for l in new_lines if str(l).startswith("dialog:")]
        self.assertEqual(dialog_lines, [])

    def test_run_undo_unreadable_log_returns_blocked_and_touches_nothing(self):
        caps = self.sortilege.probe_capabilities()
        mock_unreal.add_asset("/Game/Meshes/Rock", "StaticMesh")
        bogus = os.path.join(self.tmp_dir, "sortilege_no_such_undo.json")

        results = self.sortilege.run_undo(bogus, caps)

        self.assertEqual(results["moved"], [])
        self.assertTrue(results.get("blocked"))
        self.assertIn("/Game/Meshes/Rock", mock_unreal.get_state()["assets"])


# ---------------------------------------------------------------------------
# GUI undo button -- regression: it used to call the GATED undo(), which
# silently blocked on the default config flag (user confirmed the
# messagebox and nothing happened, no error shown), and popped a SECOND
# native EditorDialog when the flag happened to be True.
# ---------------------------------------------------------------------------

class GuiUndoSeamTests(unittest.TestCase):
    def setUp(self):
        self.sortilege = helpers.load_sortilege()
        self.sortilege._GUI_ROOT = None
        import tempfile
        self.tmp_dir = tempfile.mkdtemp(prefix="sortilege_test_")
        self.sortilege.CONFIG["LOG_DIR"] = self.tmp_dir
        _FakeMessagebox.answer = True

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp_dir, ignore_errors=True)
        _FakeMessagebox.answer = True

    def _window_after_apply(self):
        mock_unreal.add_asset("/Game/Stuff/Rock", "StaticMesh")
        assets = [asset("/Game/Stuff/Rock", "StaticMesh")]
        caps = self.sortilege.probe_capabilities()
        plan = self.sortilege.build_plan(assets, self.sortilege.CONFIG, caps)
        handles = self.sortilege._build_preview_window(
            _make_fake_tk_module(), _make_fake_ttk_module(), _FakeMessagebox,
            plan, caps)
        handles["apply_var"].set(True)
        handles["on_apply"]()
        # The real pipeline ran against the mock: asset moved.
        self.assertIn("/Game/Meshes/Rock", mock_unreal.get_state()["assets"])
        self.assertIsNotNone(handles["state"]["apply_outcome"])
        return handles

    def test_gui_undo_actually_restores_with_default_config(self):
        """RED-first regression for the CRITICAL: with CONFIG at its
        default (confirm flag False), clicking "Undo this run" and
        confirming the messagebox must actually restore the moved asset
        -- not silently no-op."""
        handles = self._window_after_apply()
        self.assertFalse(
            self.sortilege.CONFIG["I_UNDERSTAND_THIS_MODIFIES_MY_PROJECT"])

        on_undo = handles["state"].get("on_undo")
        self.assertIsNotNone(on_undo)
        on_undo()

        state = mock_unreal.get_state()
        self.assertIn("/Game/Stuff/Rock", state["assets"])
        self.assertNotIn("/Game/Meshes/Rock", state["assets"])

    def test_gui_undo_never_pops_editor_dialog_even_with_flag_on(self):
        """The double-dialog half of the CRITICAL: with the flag True and
        caps.editor_dialog available, the GUI undo must NOT additionally
        pop the native EditorDialog on top of its own messagebox."""
        handles = self._window_after_apply()
        self.sortilege.CONFIG["I_UNDERSTAND_THIS_MODIFIES_MY_PROJECT"] = True
        caps = handles["state"]["caps"]
        self.assertTrue(caps.editor_dialog)
        log_before = len(mock_unreal.get_state()["log"])

        handles["state"]["on_undo"]()

        new_lines = mock_unreal.get_state()["log"][log_before:]
        dialog_lines = [l for l in new_lines if str(l).startswith("dialog:")]
        self.assertEqual(dialog_lines, [])
        self.assertIn("/Game/Stuff/Rock", mock_unreal.get_state()["assets"])

    def test_gui_undo_declined_messagebox_restores_nothing(self):
        handles = self._window_after_apply()
        _FakeMessagebox.answer = False

        handles["state"]["on_undo"]()

        state = mock_unreal.get_state()
        self.assertIn("/Game/Meshes/Rock", state["assets"])
        self.assertNotIn("/Game/Stuff/Rock", state["assets"])

    def test_results_bar_reports_empty_folders_removed(self):
        """The sweep's headline number joins the results bar: with the
        default-on sweep, the emptied source folder count appears with
        correct singular/plural grammar ("1 empty folder removed", "N
        empty folders removed")."""
        handles = self._window_after_apply()

        result_var = handles["state"].get("result_var")
        self.assertIsNotNone(result_var)
        text = result_var.get()
        self.assertIn("1 empty folder removed", text)
        self.assertNotIn("1 empty folders removed", text)


# ---------------------------------------------------------------------------
# Close-during-apply guard -- IMPORTANT review fix: WM_DELETE_WINDOW used
# to stay live during the apply pipeline; closing mid-batch destroyed the
# root while moves were committing and the results-bar build then threw on
# the dead root, showing a misleading "Apply failed" even though the
# project HAD mutated.
# ---------------------------------------------------------------------------

class GuiCloseDuringRunGuardTests(unittest.TestCase):
    def setUp(self):
        self.sortilege = helpers.load_sortilege()
        self.sortilege._GUI_ROOT = None
        import tempfile
        self.tmp_dir = tempfile.mkdtemp(prefix="sortilege_test_")
        self.sortilege.CONFIG["LOG_DIR"] = self.tmp_dir
        _FakeMessagebox.answer = True

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_close_during_apply_is_a_noop_and_results_bar_still_renders(self):
        mock_unreal.add_asset("/Game/Stuff/Rock", "StaticMesh")
        assets = [asset("/Game/Stuff/Rock", "StaticMesh")]
        caps = self.sortilege.probe_capabilities()
        plan = self.sortilege.build_plan(assets, self.sortilege.CONFIG, caps)
        handles = self.sortilege._build_preview_window(
            _make_fake_tk_module(), _make_fake_ttk_module(), _FakeMessagebox,
            plan, caps)
        root = handles["root"]

        # A run_apply stub that fires the close handler mid-run --
        # simulating the user hitting the window's X while the pipeline
        # is committing moves -- then finishes normally.
        original_run_apply = self.sortilege.run_apply
        closed_mid_run = {}

        def _run_apply_and_close(plan_arg, caps_arg, extra_progress=None, status_callback=None):
            handles["on_close"]()
            closed_mid_run["root_alive_after_close"] = root.winfo_exists()
            return original_run_apply(plan_arg, caps_arg,
                                       extra_progress=extra_progress,
                                       status_callback=status_callback)

        self.sortilege.run_apply = _run_apply_and_close
        try:
            handles["apply_var"].set(True)
            handles["on_apply"]()
        finally:
            self.sortilege.run_apply = original_run_apply

        # The mid-run close was refused: root stayed alive through the
        # run AND the results bar rendered on it afterward.
        self.assertTrue(closed_mid_run["root_alive_after_close"])
        self.assertTrue(root.winfo_exists())
        self.assertIsNotNone(handles["state"]["apply_outcome"])
        self.assertIn("/Game/Meshes/Rock", mock_unreal.get_state()["assets"])

        # After the run completes, Close works normally again.
        handles["on_close"]()
        self.assertFalse(root.winfo_exists())

    def test_close_during_undo_is_a_noop(self):
        mock_unreal.add_asset("/Game/Stuff/Rock", "StaticMesh")
        assets = [asset("/Game/Stuff/Rock", "StaticMesh")]
        caps = self.sortilege.probe_capabilities()
        plan = self.sortilege.build_plan(assets, self.sortilege.CONFIG, caps)
        handles = self.sortilege._build_preview_window(
            _make_fake_tk_module(), _make_fake_ttk_module(), _FakeMessagebox,
            plan, caps)
        root = handles["root"]
        handles["apply_var"].set(True)
        handles["on_apply"]()

        original_run_undo = self.sortilege.run_undo
        closed_mid_run = {}

        def _run_undo_and_close(path_arg, caps_arg, **kwargs):
            handles["on_close"]()
            closed_mid_run["root_alive_after_close"] = root.winfo_exists()
            return original_run_undo(path_arg, caps_arg, **kwargs)

        self.sortilege.run_undo = _run_undo_and_close
        try:
            handles["state"]["on_undo"]()
        finally:
            self.sortilege.run_undo = original_run_undo

        self.assertTrue(closed_mid_run["root_alive_after_close"])
        self.assertTrue(root.winfo_exists())
        self.assertIn("/Game/Stuff/Rock", mock_unreal.get_state()["assets"])

        handles["on_close"]()
        self.assertFalse(root.winfo_exists())


if __name__ == "__main__":
    unittest.main()
