"""Tests for sortilege.py's main() flow, confirm gates, selection scope,
and probe mode -- Task 5.

resolve_scope(), confirmed_to_execute(), probe(), and main() do not exist
yet -- this file is expected to fail with AttributeError until Task 5
implements them. Every test loads a fresh module + fresh mock via
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
# resolve_scope()
# ---------------------------------------------------------------------------

class ResolveScopeTests(unittest.TestCase):
    def setUp(self):
        self.sortilege = helpers.load_sortilege()

    def test_uses_selected_folders_when_use_selection_enabled(self):
        caps = self.sortilege.probe_capabilities()
        mock_unreal.set_selected_folders(["/Game/Stuff/"])
        config = dict(self.sortilege.CONFIG)
        config["USE_SELECTION"] = True

        scope = self.sortilege.resolve_scope(config, caps)

        self.assertEqual(scope, ["/Game/Stuff"])

    def test_normalizes_all_root_prefix(self):
        caps = self.sortilege.probe_capabilities()
        mock_unreal.set_selected_folders(["/All/Game/Stuff"])
        config = dict(self.sortilege.CONFIG)
        config["USE_SELECTION"] = True

        scope = self.sortilege.resolve_scope(config, caps)

        self.assertEqual(scope, ["/Game/Stuff"])

    def test_falls_back_to_scope_folders_when_selection_empty(self):
        caps = self.sortilege.probe_capabilities()
        mock_unreal.set_selected_folders([])
        config = dict(self.sortilege.CONFIG)
        config["USE_SELECTION"] = True
        config["SCOPE_FOLDERS"] = ["/Game/OldStuff"]

        scope = self.sortilege.resolve_scope(config, caps)

        self.assertEqual(scope, ["/Game/OldStuff"])
        logged = "\n".join(mock_unreal.get_state()["log"]).lower()
        self.assertTrue("warning" in logged or "falling back" in logged)

    def test_falls_back_to_content_roots_when_nothing_else_configured(self):
        caps = self.sortilege.probe_capabilities()
        config = dict(self.sortilege.CONFIG)

        scope = self.sortilege.resolve_scope(config, caps)

        self.assertEqual(scope, self.sortilege.discover_content_roots())

    def test_use_selection_off_ignores_selection_and_uses_scope_folders(self):
        caps = self.sortilege.probe_capabilities()
        mock_unreal.set_selected_folders(["/Game/Stuff"])
        config = dict(self.sortilege.CONFIG)
        config["USE_SELECTION"] = False
        config["SCOPE_FOLDERS"] = ["/Game/Explicit"]

        scope = self.sortilege.resolve_scope(config, caps)

        self.assertEqual(scope, ["/Game/Explicit"])


# ---------------------------------------------------------------------------
# confirmed_to_execute()
# ---------------------------------------------------------------------------

class ConfirmedToExecuteTests(unittest.TestCase):
    def setUp(self):
        self.sortilege = helpers.load_sortilege()

    def _plan(self):
        mock_unreal.add_asset("/Game/Stuff/Rock", "StaticMesh")
        assets = [asset("/Game/Stuff/Rock", "StaticMesh")]
        return self.sortilege.build_plan(assets, self.sortilege.CONFIG,
                                          self.sortilege.probe_capabilities())

    def test_blocked_when_flag_is_false(self):
        plan = self._plan()
        caps = self.sortilege.probe_capabilities()
        ok = self.sortilege.confirmed_to_execute(self.sortilege.CONFIG, caps, plan)
        self.assertFalse(ok)

    def test_blocked_when_dialog_declines(self):
        plan = self._plan()
        caps = self.sortilege.probe_capabilities()
        self.sortilege.CONFIG["I_UNDERSTAND_THIS_MODIFIES_MY_PROJECT"] = True
        mock_unreal.set_dialog_answer("No")
        ok = self.sortilege.confirmed_to_execute(self.sortilege.CONFIG, caps, plan)
        self.assertFalse(ok)

    def test_confirmed_when_dialog_accepts(self):
        plan = self._plan()
        caps = self.sortilege.probe_capabilities()
        self.sortilege.CONFIG["I_UNDERSTAND_THIS_MODIFIES_MY_PROJECT"] = True
        mock_unreal.set_dialog_answer("Yes")
        ok = self.sortilege.confirmed_to_execute(self.sortilege.CONFIG, caps, plan)
        self.assertTrue(ok)

    def test_flag_alone_suffices_when_dialog_capability_absent(self):
        sortilege = helpers.load_sortilege(features={"editor_dialog": False})
        mock_unreal.add_asset("/Game/Stuff/Rock", "StaticMesh")
        assets = [asset("/Game/Stuff/Rock", "StaticMesh")]
        caps = sortilege.probe_capabilities()
        self.assertFalse(caps.editor_dialog)
        plan = sortilege.build_plan(assets, sortilege.CONFIG, caps)

        sortilege.CONFIG["I_UNDERSTAND_THIS_MODIFIES_MY_PROJECT"] = True
        ok = sortilege.confirmed_to_execute(sortilege.CONFIG, caps, plan)
        self.assertTrue(ok)

    def test_dialog_message_counts_are_derived_from_plan_moves_not_stats(self):
        """Regression: the confirm dialog used to build its move/rename
        counts from plan["stats"]["moves"]/["renames"] -- but stats
        ["moves"] is every planned item regardless of action (move,
        rename, or move+rename) and stats["renames"] counts "rename" AND
        "move+rename" together, so a move+rename item was counted in
        BOTH numbers: one item read back as "1 move, 1 rename" instead of
        the single item it actually is. The dialog must derive its counts
        from plan["moves"] the same way format_preview() does."""
        sortilege = helpers.load_sortilege()
        config = dict(sortilege.CONFIG)
        config["ENABLE_PREFIX_RENAME"] = True
        assets = [
            # MetaSoundSource has no PREFIX_MAP entry -- a pure move.
            asset("/Game/Stuff/Boom", "MetaSoundSource"),
            # Wrong-prefixed StaticMesh outside its dest folder -- move+rename.
            asset("/Game/Stuff/T_Rock", "StaticMesh"),
            # Wrong-prefixed StaticMesh already in its dest folder -- rename-in-place.
            asset("/Game/Meshes/T_Boulder", "StaticMesh"),
        ]
        for a in assets:
            mock_unreal.add_asset(a["path"], a["class_name"])
        caps = sortilege.probe_capabilities()
        plan = sortilege.build_plan(assets, config, caps)
        move_actions = sorted(m["action"] for m in plan["moves"])
        self.assertEqual(move_actions, ["move", "move+rename", "rename"])

        config["I_UNDERSTAND_THIS_MODIFIES_MY_PROJECT"] = True
        mock_unreal.set_dialog_answer("Yes")

        ok = sortilege.confirmed_to_execute(config, caps, plan)

        self.assertTrue(ok)
        logged = "\n".join(mock_unreal.get_state()["log"])
        self.assertIn(
            "2 asset(s) to move (1 also renamed), 1 rename-in-place. "
            "Modify the project now?",
            logged,
        )


# ---------------------------------------------------------------------------
# main() -- apply gates end to end
# ---------------------------------------------------------------------------

class ApplyGateEndToEndTests(unittest.TestCase):
    def setUp(self):
        self.sortilege = helpers.load_sortilege()

    def test_apply_blocked_without_confirm_flag_nothing_moved(self):
        mock_unreal.add_asset("/Game/Stuff/Rock", "StaticMesh")
        self.assertFalse(self.sortilege.CONFIG["I_UNDERSTAND_THIS_MODIFIES_MY_PROJECT"])

        self.sortilege.main(mode="apply")

        state = mock_unreal.get_state()
        self.assertIn("/Game/Stuff/Rock", state["assets"])
        self.assertNotIn("/Game/Meshes/Rock", state["assets"])
        logged = "\n".join(state["log"])
        self.assertIn("I_UNDERSTAND_THIS_MODIFIES_MY_PROJECT", logged)

    def test_apply_blocked_when_dialog_declined(self):
        mock_unreal.add_asset("/Game/Stuff/Rock", "StaticMesh")
        self.sortilege.CONFIG["I_UNDERSTAND_THIS_MODIFIES_MY_PROJECT"] = True
        mock_unreal.set_dialog_answer("No")

        self.sortilege.main(mode="apply")

        state = mock_unreal.get_state()
        self.assertIn("/Game/Stuff/Rock", state["assets"])
        self.assertNotIn("/Game/Meshes/Rock", state["assets"])

    def test_apply_executes_when_dialog_confirmed(self):
        mock_unreal.add_asset("/Game/Stuff/Rock", "StaticMesh")
        self.sortilege.CONFIG["I_UNDERSTAND_THIS_MODIFIES_MY_PROJECT"] = True
        mock_unreal.set_dialog_answer("Yes")

        self.sortilege.main(mode="apply")

        state = mock_unreal.get_state()
        self.assertIn("/Game/Meshes/Rock", state["assets"])
        self.assertNotIn("/Game/Stuff/Rock", state["assets"])

    def test_apply_executes_with_single_gate_when_dialog_capability_absent(self):
        sortilege = helpers.load_sortilege(features={"editor_dialog": False})
        mock_unreal.add_asset("/Game/Stuff/Rock", "StaticMesh")
        caps = sortilege.probe_capabilities()
        self.assertFalse(caps.editor_dialog)
        sortilege.CONFIG["I_UNDERSTAND_THIS_MODIFIES_MY_PROJECT"] = True

        sortilege.main(mode="apply")

        state = mock_unreal.get_state()
        self.assertIn("/Game/Meshes/Rock", state["assets"])
        self.assertNotIn("/Game/Stuff/Rock", state["assets"])

    def test_apply_uses_selection_scope_when_use_selection_enabled(self):
        mock_unreal.add_asset("/Game/Stuff/Rock", "StaticMesh")
        mock_unreal.add_asset("/Game/Keep/Wood", "Texture2D")
        mock_unreal.set_selected_folders(["/Game/Stuff"])
        self.sortilege.CONFIG["USE_SELECTION"] = True
        self.sortilege.CONFIG["I_UNDERSTAND_THIS_MODIFIES_MY_PROJECT"] = True
        mock_unreal.set_dialog_answer("Yes")

        self.sortilege.main(mode="apply")

        state = mock_unreal.get_state()
        # Only the selected folder's asset was touched.
        self.assertIn("/Game/Meshes/Rock", state["assets"])
        self.assertNotIn("/Game/Stuff/Rock", state["assets"])
        # The un-selected folder was left completely alone.
        self.assertIn("/Game/Keep/Wood", state["assets"])
        self.assertNotIn("/Game/Textures/Wood", state["assets"])


# ---------------------------------------------------------------------------
# _run_with_progress() -- ScopedSlowTask fallback double-execution guard
# ---------------------------------------------------------------------------

class RunWithProgressFallbackGuardTests(unittest.TestCase):
    def setUp(self):
        self.sortilege = helpers.load_sortilege()
        import tempfile
        self.tmp_dir = tempfile.mkdtemp(prefix="sortilege_test_")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_exception_after_moves_recorded_does_not_reexecute_the_plan(self):
        """Regression/future-proofing: the except handler around the
        ScopedSlowTask block used to unconditionally fall back to a
        plain execute_plan(plan, caps, undo_log) call. Today that is
        provably safe (nothing in the try block can execute a real move
        without also returning normally), but if a future refactor ever
        let an exception escape execute_plan() mid-batch, blindly
        re-running execute_plan() on the FULL plan here would re-attempt
        every item, including ones already safely committed and recorded
        in the undo log. Guard: once the undo log already holds recorded
        moves, do not re-execute -- report what the undo log shows
        instead, with an "aborted" marker."""
        mock_unreal.add_asset("/Game/Stuff/Rock", "StaticMesh")
        assets = [asset("/Game/Stuff/Rock", "StaticMesh")]
        plan = self.sortilege.build_plan(assets, self.sortilege.CONFIG,
                                          self.sortilege.probe_capabilities())
        caps = self.sortilege.probe_capabilities()
        self.assertTrue(caps.scoped_slow_task)
        undo_log = self.sortilege.UndoLog.begin(self.tmp_dir, plan)

        # A real move already committed successfully (and is durably
        # recorded in the undo log) before the failure this test
        # simulates -- e.g. an earlier _run_with_progress() call that
        # got partway through before something broke.
        real_results = self.sortilege.execute_plan(plan, caps, undo_log)
        self.assertEqual(real_results["moved"], [("/Game/Stuff/Rock", "/Game/Meshes/Rock")])
        self.assertEqual(len(undo_log.moves), 1)

        original_scoped_slow_task = mock_unreal.ScopedSlowTask

        class BrokenScopedSlowTask(object):
            def __init__(self, *a, **kw):
                raise RuntimeError("simulated ScopedSlowTask construction failure")

        mock_unreal.ScopedSlowTask = BrokenScopedSlowTask
        try:
            results = self.sortilege._run_with_progress(plan, caps, undo_log)
        finally:
            mock_unreal.ScopedSlowTask = original_scoped_slow_task

        self.assertTrue(results.get("aborted"))
        self.assertEqual(results["moved"], [("/Game/Stuff/Rock", "/Game/Meshes/Rock")])
        self.assertEqual(results["failed"], [])

        # execute_plan() was never called a second time against the full
        # plan -- the asset is still (only) at its already-moved location,
        # not re-touched or double-logged.
        state = mock_unreal.get_state()
        self.assertIn("/Game/Meshes/Rock", state["assets"])
        self.assertNotIn("/Game/Stuff/Rock", state["assets"])
        loaded = self.sortilege.load_undo_log(undo_log.path)
        self.assertEqual(len(loaded["moves"]), 1)

    def test_exception_with_no_moves_recorded_still_falls_back_and_executes(self):
        """The safe case: nothing has moved yet, so falling back to a
        plain execute_plan() call is exactly right."""
        mock_unreal.add_asset("/Game/Stuff/Rock", "StaticMesh")
        assets = [asset("/Game/Stuff/Rock", "StaticMesh")]
        plan = self.sortilege.build_plan(assets, self.sortilege.CONFIG,
                                          self.sortilege.probe_capabilities())
        caps = self.sortilege.probe_capabilities()
        undo_log = self.sortilege.UndoLog.begin(self.tmp_dir, plan)

        original_scoped_slow_task = mock_unreal.ScopedSlowTask

        class BrokenScopedSlowTask(object):
            def __init__(self, *a, **kw):
                raise RuntimeError("simulated ScopedSlowTask construction failure")

        mock_unreal.ScopedSlowTask = BrokenScopedSlowTask
        try:
            results = self.sortilege._run_with_progress(plan, caps, undo_log)
        finally:
            mock_unreal.ScopedSlowTask = original_scoped_slow_task

        self.assertFalse(results.get("aborted"))
        self.assertEqual(results["moved"], [("/Game/Stuff/Rock", "/Game/Meshes/Rock")])


# ---------------------------------------------------------------------------
# main() -- mode / argv parsing
# ---------------------------------------------------------------------------

class MainModeParsingTests(unittest.TestCase):
    def setUp(self):
        self.sortilege = helpers.load_sortilege()
        self._old_argv = list(sys.argv)

    def tearDown(self):
        sys.argv = self._old_argv

    def test_defaults_to_preview_when_no_argv_and_no_mode(self):
        sys.argv = ["sortilege.py"]
        mock_unreal.add_asset("/Game/Stuff/Rock", "StaticMesh")

        self.sortilege.main()

        state = mock_unreal.get_state()
        self.assertIn("/Game/Stuff/Rock", state["assets"])
        self.assertNotIn("/Game/Meshes/Rock", state["assets"])

    def test_argv_selects_apply_mode(self):
        sys.argv = ["sortilege.py", "apply"]
        mock_unreal.add_asset("/Game/Stuff/Rock", "StaticMesh")
        self.sortilege.CONFIG["I_UNDERSTAND_THIS_MODIFIES_MY_PROJECT"] = True
        mock_unreal.set_dialog_answer("Yes")

        self.sortilege.main()

        state = mock_unreal.get_state()
        self.assertIn("/Game/Meshes/Rock", state["assets"])

    def test_unknown_mode_prints_usage_and_never_mutates(self):
        mock_unreal.add_asset("/Game/Stuff/Rock", "StaticMesh")
        self.sortilege.CONFIG["I_UNDERSTAND_THIS_MODIFIES_MY_PROJECT"] = True
        mock_unreal.set_dialog_answer("Yes")

        self.sortilege.main(mode="bogus-mode")

        state = mock_unreal.get_state()
        self.assertIn("/Game/Stuff/Rock", state["assets"])
        self.assertNotIn("/Game/Meshes/Rock", state["assets"])
        logged = "\n".join(state["log"])
        self.assertIn("Usage", logged)


# ---------------------------------------------------------------------------
# main() -- undo mode dispatch
# ---------------------------------------------------------------------------

class MainUndoModeTests(unittest.TestCase):
    def setUp(self):
        self.sortilege = helpers.load_sortilege()
        # main(mode="undo") still reads sys.argv[2] for an explicit undo
        # file path (mode overrides argv[1] only) -- pin argv to a plain
        # two-element list so whatever this test process was actually
        # invoked with (e.g. unittest's own "-v") can never be mistaken
        # for that path argument.
        self._old_argv = list(sys.argv)
        sys.argv = ["sortilege.py", "undo"]

    def tearDown(self):
        sys.argv = self._old_argv

    def test_undo_mode_with_no_log_present_does_not_crash(self):
        import tempfile
        self.sortilege.CONFIG["LOG_DIR"] = tempfile.mkdtemp(prefix="sortilege_test_")
        # Nothing to undo -- must not raise, must not mutate anything.
        self.sortilege.main(mode="undo")
        state = mock_unreal.get_state()
        self.assertEqual(state["assets"], {})

    def test_undo_mode_with_explicit_nonexistent_path_fails_soft(self):
        """Review fix: an explicit undo-path argument pointing at a file
        that does not exist must produce a clean warning naming the bad
        path -- never a raised FileNotFoundError -- and must not mutate
        anything."""
        import tempfile
        bogus = os.path.join(tempfile.gettempdir(), "sortilege_no_such_undo.json")
        self.assertFalse(os.path.isfile(bogus))
        sys.argv = ["sortilege.py", "undo", bogus]

        mock_unreal.add_asset("/Game/Meshes/Rock", "StaticMesh")
        self.sortilege.CONFIG["I_UNDERSTAND_THIS_MODIFIES_MY_PROJECT"] = True
        mock_unreal.set_dialog_answer("Yes")

        self.sortilege.main(mode="undo")  # must not raise

        state = mock_unreal.get_state()
        self.assertIn("/Game/Meshes/Rock", state["assets"])
        self.assertEqual(state["redirectors"], {})
        logged = "\n".join(state["log"])
        self.assertIn("sortilege_no_such_undo.json", logged)

    def test_undo_mode_with_corrupted_log_file_fails_soft(self):
        """Review fix: a file that exists but is not valid undo-log JSON
        must produce a clean warning naming the path -- never a raised
        json/ValueError -- and must not mutate anything."""
        import shutil
        import tempfile
        log_dir = tempfile.mkdtemp(prefix="sortilege_test_")
        try:
            corrupt = os.path.join(log_dir, "sortilege_undo_corrupt.json")
            with open(corrupt, "w") as f:
                f.write("{ this is not json at all")
            sys.argv = ["sortilege.py", "undo", corrupt]

            mock_unreal.add_asset("/Game/Meshes/Rock", "StaticMesh")
            self.sortilege.CONFIG["I_UNDERSTAND_THIS_MODIFIES_MY_PROJECT"] = True
            mock_unreal.set_dialog_answer("Yes")

            self.sortilege.main(mode="undo")  # must not raise

            state = mock_unreal.get_state()
            self.assertIn("/Game/Meshes/Rock", state["assets"])
            self.assertEqual(state["redirectors"], {})
            logged = "\n".join(state["log"])
            self.assertIn("sortilege_undo_corrupt.json", logged)
        finally:
            shutil.rmtree(log_dir, ignore_errors=True)

    def test_undo_called_directly_with_unreadable_log_aborts_clean(self):
        """The second safety net: undo() itself (bypassing main()'s
        isfile check) must survive an unreadable log -- load_undo_log()
        returns None and undo() aborts with a blocked result instead of
        letting an exception escape."""
        import tempfile
        bogus = os.path.join(tempfile.gettempdir(), "sortilege_no_such_undo.json")
        self.assertFalse(os.path.isfile(bogus))
        caps = self.sortilege.probe_capabilities()

        result = self.sortilege.undo(bogus, caps)  # must not raise

        self.assertEqual(result["moved"], [])
        self.assertEqual(result["failed"], [])
        self.assertTrue(result.get("blocked"))

    def test_undo_mode_picks_newest_log_and_restores(self):
        import shutil
        import tempfile
        log_dir = tempfile.mkdtemp(prefix="sortilege_test_")
        self.sortilege.CONFIG["LOG_DIR"] = log_dir
        try:
            mock_unreal.add_asset("/Game/Stuff/Rock", "StaticMesh")
            assets = [asset("/Game/Stuff/Rock", "StaticMesh")]
            plan = self.sortilege.build_plan(assets, self.sortilege.CONFIG,
                                              self.sortilege.probe_capabilities())
            caps = self.sortilege.probe_capabilities()
            undo_log = self.sortilege.UndoLog.begin(log_dir, plan)
            self.sortilege.execute_plan(plan, caps, undo_log)

            self.sortilege.CONFIG["I_UNDERSTAND_THIS_MODIFIES_MY_PROJECT"] = True
            mock_unreal.set_dialog_answer("Yes")
            self.sortilege.main(mode="undo")

            state = mock_unreal.get_state()
            self.assertIn("/Game/Stuff/Rock", state["assets"])
            self.assertNotIn("/Game/Meshes/Rock", state["assets"])
        finally:
            shutil.rmtree(log_dir, ignore_errors=True)


# ---------------------------------------------------------------------------
# probe() / main(mode="probe")
# ---------------------------------------------------------------------------

class ProbeModeTests(unittest.TestCase):
    def setUp(self):
        self.sortilege = helpers.load_sortilege()

    def test_probe_is_read_only_and_reports_capabilities(self):
        mock_unreal.add_asset("/Game/Stuff/Rock", "StaticMesh")

        self.sortilege.probe()

        state = mock_unreal.get_state()
        self.assertIn("/Game/Stuff/Rock", state["assets"])
        self.assertNotIn("/Game/Meshes/Rock", state["assets"])
        logged = "\n".join(state["log"])
        self.assertIn("editor_dialog", logged)
        self.assertIn("/Game", logged)

    def test_probe_mode_via_main_is_read_only(self):
        mock_unreal.add_asset("/Game/Stuff/Rock", "StaticMesh")

        self.sortilege.main(mode="probe")

        state = mock_unreal.get_state()
        self.assertIn("/Game/Stuff/Rock", state["assets"])
        self.assertNotIn("/Game/Meshes/Rock", state["assets"])


# ---------------------------------------------------------------------------
# All optional capabilities off -- pure core path
# ---------------------------------------------------------------------------

class AllFeaturesOffEndToEndTests(unittest.TestCase):
    def test_preview_and_apply_work_with_every_optional_capability_off(self):
        sortilege = helpers.load_sortilege(features={
            "editor_dialog": False,
            "selected_folders": False,
            "scoped_slow_task": False,
            "fix_up_redirectors": False,
            "asset_rename_data": False,
            "class_paths_filter": False,
            "project_root_api": False,
            "collect_garbage": False,
            "soft_path_rename": False,
        })
        caps = sortilege.probe_capabilities()
        self.assertFalse(caps.editor_dialog)
        self.assertFalse(caps.selected_folders)
        self.assertFalse(caps.path_view_folders)
        self.assertFalse(caps.scoped_slow_task)
        self.assertFalse(caps.fix_up_redirectors)
        # Note: mock_unreal's TopLevelAssetPath class is unconditionally
        # present regardless of the "class_paths_filter" feature switch
        # (that switch only gates AssetData.asset_class_path and the
        # ARFilter class_paths translation in get_assets()) -- so
        # caps.class_paths_filter genuinely stays True here, same as every
        # other test in this suite that touches this feature switch.
        self.assertFalse(caps.project_root_api)
        self.assertFalse(caps.soft_path_rename)
        self.assertFalse(caps.collect_garbage)

        # BP_User is a referencer registered OUTSIDE the scanned scope
        # (SCOPE_FOLDERS below limits the run to /Game/Stuff) -- it's
        # there purely to prove rename_asset() rewrites referencer deps
        # even with every optional capability off, without also being a
        # planned move itself (Blueprint classifies to "Props", which
        # would otherwise make this assertion depend on move ordering).
        mock_unreal.add_asset("/Game/Blueprints/BP_User", "Blueprint",
                               deps=["/Game/Stuff/Rock"])
        mock_unreal.add_asset("/Game/Stuff/Rock", "StaticMesh")
        sortilege.CONFIG["SCOPE_FOLDERS"] = ["/Game/Stuff"]

        # preview must never mutate.
        sortilege.main(mode="preview")
        state = mock_unreal.get_state()
        self.assertIn("/Game/Stuff/Rock", state["assets"])
        self.assertNotIn("/Game/Meshes/Rock", state["assets"])

        # apply, with the flag alone (no dialog capability), must execute.
        sortilege.CONFIG["I_UNDERSTAND_THIS_MODIFIES_MY_PROJECT"] = True
        sortilege.main(mode="apply")

        state = mock_unreal.get_state()
        self.assertIn("/Game/Meshes/Rock", state["assets"])
        self.assertNotIn("/Game/Stuff/Rock", state["assets"])
        self.assertEqual(
            state["assets"]["/Game/Blueprints/BP_User"]["deps"],
            ["/Game/Meshes/Rock"],
        )


# ---------------------------------------------------------------------------
# main() -- log-path visibility (loud console line, every mode)
# ---------------------------------------------------------------------------

class LogPathVisibilityTests(unittest.TestCase):
    """Field report: "I could not find the trace file" -- main() must
    announce the resolved log/trace/undo directory, loudly, at the very
    start, for every mode (preview/apply/undo/probe)."""

    def setUp(self):
        self.sortilege = helpers.load_sortilege()
        import tempfile
        self.tmp_dir = tempfile.mkdtemp(prefix="sortilege_test_")
        self.sortilege.CONFIG["LOG_DIR"] = self.tmp_dir
        self._old_argv = list(sys.argv)
        sys.argv = ["sortilege.py"]

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp_dir, ignore_errors=True)
        sys.argv = self._old_argv

    def _logged(self):
        return "\n".join(str(l) for l in mock_unreal.get_state()["log"])

    def _expected_line(self):
        return "Sortilege: logs, trace, and undo files are written to: " + self.tmp_dir

    def test_preview_mode_announces_log_dir(self):
        self.sortilege.main(mode="preview")
        self.assertIn(self._expected_line(), self._logged())

    def test_apply_mode_announces_log_dir_even_when_blocked(self):
        # Confirm flag left at its default False -- apply is blocked, but
        # the log-path line must already have printed before that gate is
        # even checked.
        self.sortilege.main(mode="apply")
        self.assertIn(self._expected_line(), self._logged())

    def test_undo_mode_announces_log_dir_even_with_nothing_to_undo(self):
        self.sortilege.main(mode="undo")  # nothing to undo -- must not raise
        self.assertIn(self._expected_line(), self._logged())

    def test_probe_mode_announces_log_dir(self):
        self.sortilege.main(mode="probe")
        self.assertIn(self._expected_line(), self._logged())

    def test_line_is_printed_before_any_mode_specific_work(self):
        """Proven via preview mode's own console preview header, which
        must come AFTER the log-path line, not before it."""
        self.sortilege.main(mode="preview")
        lines = [str(l) for l in mock_unreal.get_state()["log"]]
        log_line_index = next(
            i for i, l in enumerate(lines)
            if l.startswith("Sortilege: logs, trace, and undo files are written to:"))
        preview_index = next(
            i for i, l in enumerate(lines) if "dry run preview" in l)
        self.assertLess(log_line_index, preview_index)


class NoUnrealGuardTests(unittest.TestCase):
    """Running outside UEFN (no `unreal` module) must abort main() with
    guidance for EVERY mode -- never print a misleading empty preview.
    Regression: a user ran the script in Windows Command Prompt and got
    'Scanned 0 asset(s)' output that looked like a successful run."""

    def _load_without_unreal(self):
        import importlib.util
        # None in sys.modules makes `import unreal` raise ImportError.
        sys.modules.pop("sortilege", None)
        self._saved_unreal = sys.modules.get("unreal")
        sys.modules["unreal"] = None
        project_root = os.path.dirname(
            os.path.dirname(os.path.abspath(__file__)))
        path = os.path.join(project_root, "sortilege.py")
        spec = importlib.util.spec_from_file_location("sortilege", path)
        module = importlib.util.module_from_spec(spec)
        sys.modules["sortilege"] = module
        import io as _io
        import contextlib
        self._load_out = _io.StringIO()
        with contextlib.redirect_stdout(self._load_out):
            spec.loader.exec_module(module)
        return module

    def tearDown(self):
        if self._saved_unreal is not None:
            sys.modules["unreal"] = self._saved_unreal
        else:
            sys.modules.pop("unreal", None)
        sys.modules.pop("sortilege", None)

    def _run_mode(self, module, mode):
        import io as _io
        import contextlib
        out = _io.StringIO()
        with contextlib.redirect_stdout(out):
            module.main(mode)
        return out.getvalue()

    def test_every_mode_aborts_with_guidance_and_no_preview(self):
        module = self._load_without_unreal()
        self.assertIsNone(module.unreal)
        for mode in ("preview", "apply", "undo", "probe"):
            out = self._run_mode(module, mode)
            self.assertIn("inside UEFN", out,
                          "mode %r must print run-inside-UEFN guidance"
                          % mode)
            self.assertNotIn("dry run preview", out,
                             "mode %r must not print a preview" % mode)
            self.assertNotIn("Scanned", out,
                             "mode %r must not pretend to scan" % mode)

    def test_no_files_written_when_unreal_missing(self):
        import glob
        module = self._load_without_unreal()
        project_root = os.path.dirname(
            os.path.dirname(os.path.abspath(__file__)))
        before = set(glob.glob(os.path.join(project_root, "sortilege_*.json")))
        self._run_mode(module, "preview")
        after = set(glob.glob(os.path.join(project_root, "sortilege_*.json")))
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
