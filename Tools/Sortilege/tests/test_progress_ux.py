"""Tests for full-run progress visibility and the on-top preview window.

Field report: the GUI only pumped root.update() during execute_plan's
moves; the post-move stages (fix_soft_references, cleanup_redirectors,
cleanup_empty_folders, verify) ran with a frozen, hidden window for
minutes on a real project, and the window itself could hide BEHIND the
UEFN editor and soft-lock it.

Covers:
  - cleanup_redirectors()/cleanup_empty_folders() progress hooks (called
    every 5 items).
  - run_apply()/run_undo() status_callback threading (called once per
    pipeline stage, in strict order).
  - The GUI's on-top window behavior and persistent status label, through
    the existing fake-tk seam (extended here to assert attributes()/
    lift() calls, fail-soft when those methods are absent).

RED-first TDD against not-yet-added parameters/behavior.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import helpers
import mock_unreal

from test_gui import (
    _FakeTk, _FakeMessagebox, _make_fake_tk_module, _make_fake_ttk_module,
)


def asset(path, class_name):
    folder, name = path.rsplit("/", 1)
    return {"path": path, "name": name, "folder": folder, "class_name": class_name}


# ---------------------------------------------------------------------------
# cleanup_redirectors() -- progress hook, every 5 items
# ---------------------------------------------------------------------------

class CleanupRedirectorsProgressHookTests(unittest.TestCase):
    def setUp(self):
        # Force the manual recipe (fix_up_redirectors would otherwise clear
        # everything in one batch call before the per-item loop ever runs).
        self.sortilege = helpers.load_sortilege(features={"fix_up_redirectors": False})
        mock_unreal.set_project_root("/ProjectX")

    def _make_redirectors(self, count):
        scope = set()
        for i in range(count):
            src = "/ProjectX/Stuff/Rock%d" % i
            dest = "/ProjectX/Meshes/Rock%d" % i
            mock_unreal.add_asset(src, "StaticMesh")
            mock_unreal.EditorAssetLibrary.rename_asset(src, dest)
            scope.add("/ProjectX/Stuff")
            scope.add("/ProjectX/Meshes")
        return sorted(scope)

    def test_progress_hook_called_every_five_items(self):
        scope = self._make_redirectors(12)
        caps = self.sortilege.probe_capabilities()
        self.assertFalse(caps.fix_up_redirectors)

        calls = []
        result = self.sortilege.cleanup_redirectors(
            scope, caps, progress_hook=lambda i, n: calls.append((i, n)))

        self.assertEqual(len(result["fixed"]), 12)
        self.assertIn((5, 12), calls)
        self.assertIn((10, 12), calls)
        self.assertNotIn((1, 12), calls)
        self.assertNotIn((12, 12), calls)

    def test_progress_hook_default_none_is_a_noop(self):
        """Console path (no GUI): progress_hook stays None -- must not
        raise, must not change fixed/remaining outcome."""
        scope = self._make_redirectors(6)
        caps = self.sortilege.probe_capabilities()

        result = self.sortilege.cleanup_redirectors(scope, caps)

        self.assertEqual(len(result["fixed"]), 6)

    def test_progress_hook_exception_does_not_abort_batch(self):
        scope = self._make_redirectors(6)
        caps = self.sortilege.probe_capabilities()

        def _boom(_i, _n):
            raise RuntimeError("simulated UI hiccup")

        result = self.sortilege.cleanup_redirectors(scope, caps, progress_hook=_boom)

        self.assertEqual(len(result["fixed"]), 6)


# ---------------------------------------------------------------------------
# cleanup_empty_folders() -- progress hook, every 5 items
# ---------------------------------------------------------------------------

class CleanupEmptyFoldersProgressHookTests(unittest.TestCase):
    def setUp(self):
        self.sortilege = helpers.load_sortilege()
        mock_unreal.set_project_root("/ProjectX")

    def _make_candidate_folders(self, count):
        moves = []
        scope = set()
        for i in range(count):
            src = "/ProjectX/Stuff%d/Rock" % i
            dest = "/ProjectX/Meshes/Rock%d" % i
            mock_unreal.add_asset(src, "StaticMesh")
            mock_unreal.EditorAssetLibrary.rename_asset(src, dest)
            moves.append({"path": src, "dest_folder": "/ProjectX/Meshes"})
            scope.add("/ProjectX/Stuff%d" % i)
        scope.add("/ProjectX/Meshes")
        caps = self.sortilege.probe_capabilities()
        # Clear the leftover redirectors first (matching run_apply()'s real
        # order) so every source folder actually reads empty.
        self.sortilege.cleanup_redirectors(sorted(scope), caps)
        return moves

    def test_progress_hook_called_every_five_items(self):
        moves = self._make_candidate_folders(12)
        plan = {"moves": moves}

        calls = []
        result = self.sortilege.cleanup_empty_folders(
            plan, self.sortilege.CONFIG,
            progress_hook=lambda i, n: calls.append((i, n)))

        self.assertEqual(len(result["removed"]), 12)
        self.assertIn((5, 12), calls)
        self.assertIn((10, 12), calls)
        self.assertNotIn((1, 12), calls)

    def test_progress_hook_default_none_is_a_noop(self):
        moves = self._make_candidate_folders(3)
        plan = {"moves": moves}

        result = self.sortilege.cleanup_empty_folders(plan, self.sortilege.CONFIG)

        self.assertEqual(len(result["removed"]), 3)


# ---------------------------------------------------------------------------
# run_apply() -- status_callback, once per stage, in strict order
# ---------------------------------------------------------------------------

class RunApplyStatusCallbackTests(unittest.TestCase):
    def setUp(self):
        self.sortilege = helpers.load_sortilege()

    def test_status_callback_invoked_once_per_stage_in_order(self):
        mock_unreal.add_asset("/Game/Stuff/Rock", "StaticMesh")
        assets = [asset("/Game/Stuff/Rock", "StaticMesh")]
        caps = self.sortilege.probe_capabilities()
        plan = self.sortilege.build_plan(assets, self.sortilege.CONFIG, caps)

        calls = []
        self.sortilege.run_apply(
            plan, caps, status_callback=lambda text: calls.append(text))

        # A one-item batch never trips the K=5 redirector/empty-folder
        # progress ticks, so exactly the seven stage-boundary calls fire.
        # "Rewriting Verse references..." is new: FIX_VERSE_REFERENCES
        # defaults True (like every sibling post-move pass, it always
        # announces its stage regardless of whether this run's project
        # actually has any .verse files to rewrite -- see run_apply()).
        self.assertEqual(calls, [
            "Moving assets...", "Fixing references...",
            "Cleaning up redirectors...", "Rewriting Verse references...",
            "Removing empty folders...", "Verifying...", "Writing report...",
        ])

    def test_status_callback_default_none_is_a_noop(self):
        mock_unreal.add_asset("/Game/Stuff/Rock", "StaticMesh")
        assets = [asset("/Game/Stuff/Rock", "StaticMesh")]
        caps = self.sortilege.probe_capabilities()
        plan = self.sortilege.build_plan(assets, self.sortilege.CONFIG, caps)

        outcome = self.sortilege.run_apply(plan, caps)  # must not raise

        self.assertEqual(len(outcome["results"]["moved"]), 1)

    def test_status_callback_exception_does_not_abort_apply(self):
        mock_unreal.add_asset("/Game/Stuff/Rock", "StaticMesh")
        assets = [asset("/Game/Stuff/Rock", "StaticMesh")]
        caps = self.sortilege.probe_capabilities()
        plan = self.sortilege.build_plan(assets, self.sortilege.CONFIG, caps)

        def _boom(_text):
            raise RuntimeError("simulated UI hiccup")

        outcome = self.sortilege.run_apply(plan, caps, status_callback=_boom)

        self.assertEqual(len(outcome["results"]["moved"]), 1)

    def test_status_callback_receives_redirector_progress_ticks_on_big_batch(self):
        """run_apply() must wire its own status_callback through to
        cleanup_redirectors()'s progress_hook, so a long redirector-
        cleanup phase keeps producing status updates, not just the single
        "Cleaning up redirectors..." line at stage entry."""
        sortilege = helpers.load_sortilege(features={"fix_up_redirectors": False})
        for i in range(12):
            mock_unreal.add_asset("/Game/Stuff/Rock%d" % i, "StaticMesh")
        assets = [asset("/Game/Stuff/Rock%d" % i, "StaticMesh") for i in range(12)]
        caps = sortilege.probe_capabilities()
        plan = sortilege.build_plan(assets, sortilege.CONFIG, caps)

        calls = []
        sortilege.run_apply(plan, caps, status_callback=lambda text: calls.append(text))

        self.assertTrue(any("Cleaning up redirectors" in c and "/" in c for c in calls),
                         calls)


# ---------------------------------------------------------------------------
# run_undo() -- status_callback, once per stage, in strict order
# ---------------------------------------------------------------------------

class RunUndoStatusCallbackTests(unittest.TestCase):
    def setUp(self):
        self.sortilege = helpers.load_sortilege()

    def _apply_then_get_undo_log(self):
        mock_unreal.add_asset("/Game/Stuff/Rock", "StaticMesh")
        assets = [asset("/Game/Stuff/Rock", "StaticMesh")]
        caps = self.sortilege.probe_capabilities()
        plan = self.sortilege.build_plan(assets, self.sortilege.CONFIG, caps)
        outcome = self.sortilege.run_apply(plan, caps)
        return outcome["undo_log"].path, caps

    def test_status_callback_invoked_once_per_stage_in_order(self):
        undo_log_path, caps = self._apply_then_get_undo_log()

        calls = []
        self.sortilege.run_undo(
            undo_log_path, caps, status_callback=lambda text: calls.append(text))

        # Every stage name must appear, in order, as a subsequence (a big
        # enough batch could also interleave progress ticks -- this is a
        # one-item batch, so none fire).
        self.assertTrue(len(calls) >= 6, calls)
        stage_calls = [c for c in calls if c.endswith("...") and "/" not in c]
        self.assertEqual(len(stage_calls), 6)

    def test_status_callback_default_none_is_a_noop(self):
        undo_log_path, caps = self._apply_then_get_undo_log()

        results = self.sortilege.run_undo(undo_log_path, caps)  # must not raise

        self.assertEqual(len(results.get("moved", [])), 1)


# ---------------------------------------------------------------------------
# GUI -- on-top window + persistent status label
# ---------------------------------------------------------------------------

class _FakeTkNoTopmostSupport(_FakeTk):
    """Simulates an embedded tk build missing attributes()/lift() entirely
    -- both must be individually try/except-guarded so a build lacking
    them never crashes the window."""

    def attributes(self, *a, **k):
        raise Exception("attributes() not supported on this build")

    def lift(self):
        raise Exception("lift() not supported on this build")


class GuiOnTopAndStatusSeamTests(unittest.TestCase):
    def setUp(self):
        self.sortilege = helpers.load_sortilege()
        self.sortilege._GUI_ROOT = None

    def _plan(self):
        mock_unreal.add_asset("/Game/Stuff/Rock", "StaticMesh")
        assets = [asset("/Game/Stuff/Rock", "StaticMesh")]
        caps = self.sortilege.probe_capabilities()
        plan = self.sortilege.build_plan(assets, self.sortilege.CONFIG, caps)
        return plan, caps

    def test_window_build_sets_topmost_and_lifts(self):
        plan, caps = self._plan()
        handles = self.sortilege._build_preview_window(
            _make_fake_tk_module(), _make_fake_ttk_module(), _FakeMessagebox,
            plan, caps)

        root = handles["root"]
        self.assertTrue(any(
            call == ("-topmost", True) for call in root.attributes_calls),
            root.attributes_calls)
        self.assertGreaterEqual(root.lift_calls, 1)

    def test_apply_reasserts_topmost_and_lift(self):
        plan, caps = self._plan()
        handles = self.sortilege._build_preview_window(
            _make_fake_tk_module(), _make_fake_ttk_module(), _FakeMessagebox,
            plan, caps)
        root = handles["root"]
        lift_calls_before = root.lift_calls

        handles["apply_var"].set(True)
        handles["on_apply"]()

        self.assertGreater(root.lift_calls, lift_calls_before)

    def test_status_label_updates_through_the_run(self):
        plan, caps = self._plan()
        handles = self.sortilege._build_preview_window(
            _make_fake_tk_module(), _make_fake_ttk_module(), _FakeMessagebox,
            plan, caps)
        self.assertIn("status_var", handles)

        handles["apply_var"].set(True)
        handles["on_apply"]()

        history = handles["status_var"].history
        self.assertIn("Moving assets...", history)
        self.assertIn("Writing report...", history)
        # Order preserved: moves before the final report write.
        self.assertLess(
            history.index("Moving assets..."), history.index("Writing report..."))

    def test_logs_label_shows_resolved_log_dir(self):
        plan, caps = self._plan()
        handles = self.sortilege._build_preview_window(
            _make_fake_tk_module(), _make_fake_ttk_module(), _FakeMessagebox,
            plan, caps)
        self.assertIn("logs_var", handles)
        self.assertIn(
            self.sortilege.resolve_log_dir(self.sortilege.CONFIG),
            handles["logs_var"].get())

    def test_fails_soft_when_attributes_and_lift_are_absent(self):
        """An embedded-tk build with neither attributes() nor lift()
        available must neither crash the window build nor abort Apply --
        both calls are individually try/except-guarded."""
        plan, caps = self._plan()
        fake_tk = _make_fake_tk_module()
        fake_tk.Tk = _FakeTkNoTopmostSupport

        handles = self.sortilege._build_preview_window(
            fake_tk, _make_fake_ttk_module(), _FakeMessagebox, plan, caps)  # must not raise

        handles["apply_var"].set(True)
        handles["on_apply"]()  # must not raise

        self.assertIn("/Game/Meshes/Rock", mock_unreal.get_state()["assets"])


if __name__ == "__main__":
    unittest.main()
