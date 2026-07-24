"""Tests for crash diagnostics: CrashTracer, the SAFE_MODE/DISABLE_GC/
FIX_SOFT_REFERENCES bisect valves, and the per-stage/per-op trace marks
threaded through run_apply()/run_undo() and the pipeline functions they
call (execute_plan, fix_soft_references, cleanup_redirectors,
cleanup_empty_folders).

CrashTracer and the three new CONFIG keys are brand new -- this file is
expected to fail with AttributeError/KeyError until they exist. Every
other test file in this suite staying green (unmodified) is the proof
that default behavior is unchanged for callers that never pass the new
optional params.
"""
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import helpers
import mock_unreal


def asset(path, class_name):
    folder, name = path.rsplit("/", 1)
    return {"path": path, "name": name, "folder": folder, "class_name": class_name}


# ---------------------------------------------------------------------------
# CrashTracer -- the breadcrumb file itself
# ---------------------------------------------------------------------------

class CrashTracerBasicTests(unittest.TestCase):
    def setUp(self):
        self.sortilege = helpers.load_sortilege()
        self.tmp_dir = tempfile.mkdtemp(prefix="sortilege_test_")

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_begin_creates_a_sortilege_trace_file_in_the_given_dir(self):
        tracer = self.sortilege.CrashTracer.begin(self.tmp_dir)

        self.assertTrue(os.path.isfile(tracer.path))
        self.assertEqual(os.path.dirname(tracer.path), self.tmp_dir)
        basename = os.path.basename(tracer.path)
        self.assertTrue(basename.startswith("sortilege_trace_"))
        self.assertTrue(basename.endswith(".log"))

    def test_mark_is_durable_read_back_mid_sequence(self):
        """Same crash-safety proof style as UndoLog's
        test_record_survives_simulated_crash: read the file back from a
        FRESH handle right after each mark(), with nothing else touched
        -- proves the first mark already hit disk before the second one
        was ever made, i.e. a "crash" between the two calls would still
        leave the first line readable."""
        tracer = self.sortilege.CrashTracer.begin(self.tmp_dir)

        tracer.mark("STAGE >>> entering: moves")
        with open(tracer.path, "r", encoding="utf-8") as f:
            mid_crash_content = f.read()
        self.assertIn("STAGE >>> entering: moves", mid_crash_content)

        tracer.mark("STAGE <<< done: moves (moved=1 failed=0)")
        with open(tracer.path, "r", encoding="utf-8") as f:
            final_content = f.read()
        lines = [l for l in final_content.splitlines() if l]
        self.assertEqual(lines, [
            "STAGE >>> entering: moves",
            "STAGE <<< done: moves (moved=1 failed=0)",
        ])

    def test_mark_mirrors_to_console_log_with_trace_prefix(self):
        tracer = self.sortilege.CrashTracer.begin(self.tmp_dir)
        tracer.mark("delete_asset redirector: /Game/Stuff/Rock")

        logged = "\n".join(str(l) for l in mock_unreal.get_state()["log"])
        self.assertIn(
            "Sortilege TRACE: delete_asset redirector: /Game/Stuff/Rock", logged)

    def test_stage_prefixed_mark_calls_fsync(self):
        tracer = self.sortilege.CrashTracer.begin(self.tmp_dir)
        calls = []
        original_fsync = self.sortilege.os.fsync

        def spy_fsync(fd):
            calls.append(fd)
            return original_fsync(fd)

        self.sortilege.os.fsync = spy_fsync
        try:
            tracer.mark("STAGE >>> entering: moves")
        finally:
            self.sortilege.os.fsync = original_fsync
        self.assertEqual(len(calls), 1)

    def test_non_stage_mark_does_not_call_fsync(self):
        tracer = self.sortilege.CrashTracer.begin(self.tmp_dir)
        calls = []
        original_fsync = self.sortilege.os.fsync

        def spy_fsync(fd):
            calls.append(fd)
            return original_fsync(fd)

        self.sortilege.os.fsync = spy_fsync
        try:
            tracer.mark("delete_asset redirector: /Game/Stuff/Rock")
        finally:
            self.sortilege.os.fsync = original_fsync
        self.assertEqual(len(calls), 0)

    def test_mark_never_raises_when_the_file_cannot_be_written(self):
        tracer = self.sortilege.CrashTracer(
            os.path.join(self.tmp_dir, "does", "not", "exist", "sortilege_trace_x.log"))
        # Must not raise even though the parent directory does not exist.
        tracer.mark("STAGE >>> entering: moves")

    def test_begin_never_raises_when_the_log_dir_cannot_be_written(self):
        bogus_dir = os.path.join(self.tmp_dir, "nested", "missing")
        # begin() does not create log_dir itself (that is resolve_log_
        # dir()'s job, always called first by real callers) -- must not
        # raise even so.
        tracer = self.sortilege.CrashTracer.begin(bogus_dir)
        self.assertTrue(tracer.path.startswith(bogus_dir))

    def test_console_mirror_failure_does_not_prevent_the_file_write(self):
        tracer = self.sortilege.CrashTracer.begin(self.tmp_dir)
        original_console = self.sortilege._console

        def broken_console(_line):
            raise RuntimeError("simulated Output Log failure")

        self.sortilege._console = broken_console
        try:
            tracer.mark("STAGE >>> entering: moves")
        finally:
            self.sortilege._console = original_console

        with open(tracer.path, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("STAGE >>> entering: moves", content)


# ---------------------------------------------------------------------------
# run_apply() -- stage trace, in strict pipeline order, in the resolved
# log dir (same one plan/report/undo files land in)
# ---------------------------------------------------------------------------

class RunApplyStageTraceTests(unittest.TestCase):
    def setUp(self):
        self.sortilege = helpers.load_sortilege()
        self.tmp_dir = tempfile.mkdtemp(prefix="sortilege_test_")
        self.sortilege.CONFIG["LOG_DIR"] = self.tmp_dir

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _trace_files(self):
        return sorted(
            n for n in os.listdir(self.tmp_dir)
            if n.startswith("sortilege_trace_") and n.endswith(".log"))

    def test_full_apply_writes_all_seven_stage_pairs_in_strict_order(self):
        mock_unreal.add_asset("/Game/Stuff/Rock", "StaticMesh")
        assets = [asset("/Game/Stuff/Rock", "StaticMesh")]
        caps = self.sortilege.probe_capabilities()
        plan = self.sortilege.build_plan(assets, self.sortilege.CONFIG, caps)

        self.sortilege.run_apply(plan, caps)

        trace_files = self._trace_files()
        self.assertEqual(len(trace_files), 1)
        with open(os.path.join(self.tmp_dir, trace_files[0]), "r", encoding="utf-8") as f:
            lines = [l for l in f.read().splitlines() if l]
        stage_lines = [l for l in lines if l.startswith("STAGE ")]

        # "verse-references" is new: it always runs right after
        # redirector cleanup, before the empty-folder sweep -- see
        # run_apply()'s docstring.
        expected_stage_order = [
            "moves", "soft-references", "redirector-cleanup",
            "verse-references", "empty-folder-sweep", "verify", "write-summary",
        ]
        expected_fragments = []
        for name in expected_stage_order:
            expected_fragments.append("entering: %s" % name)
            expected_fragments.append("done: %s" % name)

        self.assertEqual(len(stage_lines), len(expected_fragments))
        for expected_fragment, actual_line in zip(expected_fragments, stage_lines):
            self.assertIn(expected_fragment, actual_line)

    def test_trace_file_lands_in_the_same_resolved_log_dir_as_the_report(self):
        mock_unreal.add_asset("/Game/Stuff/Rock", "StaticMesh")
        assets = [asset("/Game/Stuff/Rock", "StaticMesh")]
        caps = self.sortilege.probe_capabilities()
        plan = self.sortilege.build_plan(assets, self.sortilege.CONFIG, caps)

        outcome = self.sortilege.run_apply(plan, caps)

        self.assertEqual(os.path.dirname(outcome["report_path"]), self.tmp_dir)
        self.assertEqual(os.path.dirname(outcome["plan_path"]), self.tmp_dir)
        self.assertEqual(len(self._trace_files()), 1)


# ---------------------------------------------------------------------------
# run_undo() -- its own equivalent stage trace
# ---------------------------------------------------------------------------

class RunUndoStageTraceTests(unittest.TestCase):
    def setUp(self):
        self.sortilege = helpers.load_sortilege()
        self.tmp_dir = tempfile.mkdtemp(prefix="sortilege_test_")
        self.sortilege.CONFIG["LOG_DIR"] = self.tmp_dir

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _trace_files(self):
        return sorted(
            n for n in os.listdir(self.tmp_dir)
            if n.startswith("sortilege_trace_") and n.endswith(".log"))

    def test_full_undo_writes_all_stage_pairs_in_strict_order(self):
        mock_unreal.add_asset("/Game/Stuff/Rock", "StaticMesh")
        assets = [asset("/Game/Stuff/Rock", "StaticMesh")]
        caps = self.sortilege.probe_capabilities()
        plan = self.sortilege.build_plan(assets, self.sortilege.CONFIG, caps)
        outcome = self.sortilege.run_apply(plan, caps)
        # Clear the apply's own trace file so this test can isolate the
        # undo's trace file cleanly.
        for name in self._trace_files():
            os.remove(os.path.join(self.tmp_dir, name))

        self.sortilege.run_undo(outcome["undo_log"].path, caps)

        trace_files = self._trace_files()
        self.assertEqual(len(trace_files), 1)
        with open(os.path.join(self.tmp_dir, trace_files[0]), "r", encoding="utf-8") as f:
            lines = [l for l in f.read().splitlines() if l]
        stage_lines = [l for l in lines if l.startswith("STAGE ")]

        expected_stage_order = [
            "pre-restore-cleanup", "reversed-replay", "redirector-cleanup",
            "empty-folder-sweep", "verify", "summary",
        ]
        expected_fragments = []
        for name in expected_stage_order:
            expected_fragments.append("entering: %s" % name)
            expected_fragments.append("done: %s" % name)

        self.assertEqual(len(stage_lines), len(expected_fragments))
        for expected_fragment, actual_line in zip(expected_fragments, stage_lines):
            self.assertIn(expected_fragment, actual_line)


# ---------------------------------------------------------------------------
# SAFE_MODE -- the "just move the assets, nothing else" bisect valve
# ---------------------------------------------------------------------------

class SafeModeApplyTests(unittest.TestCase):
    def setUp(self):
        self.sortilege = helpers.load_sortilege()
        self.tmp_dir = tempfile.mkdtemp(prefix="sortilege_test_")
        self.sortilege.CONFIG["LOG_DIR"] = self.tmp_dir
        self.sortilege.CONFIG["SAFE_MODE"] = True

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_safe_mode_still_moves_assets_and_keeps_undo_log_intact(self):
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
        self.assertEqual(len(outcome["undo_log"].moves), 1)
        loaded = self.sortilege.load_undo_log(outcome["undo_log"].path)
        self.assertEqual(len(loaded["moves"]), 1)

    def test_safe_mode_skips_soft_references_redirector_cleanup_and_empty_folder_sweep(self):
        mock_unreal.add_asset("/Game/Stuff/Rock", "StaticMesh")
        mock_unreal.add_asset("/Game/Blueprints/BP_User", "Blueprint",
                               deps=["/Game/Stuff/Rock"])
        assets = [asset("/Game/Stuff/Rock", "StaticMesh")]
        caps = self.sortilege.probe_capabilities()
        plan = self.sortilege.build_plan(assets, self.sortilege.CONFIG, caps)

        outcome = self.sortilege.run_apply(plan, caps)
        results = outcome["results"]

        # cleanup_redirectors never ran -- the forward-move redirector is
        # still squatting at the old path.
        state = mock_unreal.get_state()
        self.assertIn("/Game/Stuff/Rock", state["redirectors"])
        self.assertNotIn("redirector_cleanup", results)

        # cleanup_empty_folders never ran -- the now-empty source folder
        # is still registered.
        self.assertTrue(mock_unreal.EditorAssetLibrary.does_directory_exist("/Game/Stuff"))
        self.assertNotIn("empty_folders", results)

        # fix_soft_references never ran -- no rename_referencing_soft_
        # object_paths call was ever recorded, even though BP_User's
        # stale dep would normally have triggered exactly one.
        self.assertEqual(state["soft_rename_calls"], [])

    def test_safe_mode_makes_zero_collect_garbage_calls_on_a_big_batch(self):
        # 30 moves comfortably trips BOTH the execute_plan (every 25) and
        # cleanup_redirectors (every 10) GC thresholds if either ran.
        assets = [asset("/Game/Stuff/Rock%02d" % i, "StaticMesh") for i in range(30)]
        for a in assets:
            mock_unreal.add_asset(a["path"], a["class_name"])
        caps = self.sortilege.probe_capabilities()
        plan = self.sortilege.build_plan(assets, self.sortilege.CONFIG, caps)

        self.sortilege.run_apply(plan, caps)

        self.assertEqual(mock_unreal.get_state()["gc_calls"], 0)

    def test_safe_mode_traces_loud_skip_lines_for_each_skipped_stage(self):
        mock_unreal.add_asset("/Game/Stuff/Rock", "StaticMesh")
        assets = [asset("/Game/Stuff/Rock", "StaticMesh")]
        caps = self.sortilege.probe_capabilities()
        plan = self.sortilege.build_plan(assets, self.sortilege.CONFIG, caps)

        outcome = self.sortilege.run_apply(plan, caps)

        report_dir = os.path.dirname(outcome["report_path"])
        trace_files = [n for n in os.listdir(report_dir)
                       if n.startswith("sortilege_trace_")]
        self.assertEqual(len(trace_files), 1)
        with open(os.path.join(report_dir, trace_files[0]), "r", encoding="utf-8") as f:
            content = f.read()

        self.assertIn("STAGE >>> entering: moves", content)
        self.assertIn("SAFE_MODE active: skipping soft-references", content)
        self.assertIn("SAFE_MODE active: skipping redirector-cleanup", content)
        self.assertIn("SAFE_MODE active: skipping empty-folder-sweep", content)
        self.assertNotIn("STAGE >>> entering: soft-references", content)
        self.assertNotIn("STAGE >>> entering: redirector-cleanup", content)
        self.assertNotIn("STAGE >>> entering: empty-folder-sweep", content)
        # verify is NOT part of SAFE_MODE's skip set -- it still ran.
        self.assertIn("STAGE >>> entering: verify", content)
        self.assertIn("STAGE <<< done: verify", content)


class SafeModeUndoTests(unittest.TestCase):
    def setUp(self):
        self.sortilege = helpers.load_sortilege()
        self.tmp_dir = tempfile.mkdtemp(prefix="sortilege_test_")
        self.sortilege.CONFIG["LOG_DIR"] = self.tmp_dir

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_safe_mode_in_run_undo_skips_cleanup_stages_but_still_restores(self):
        mock_unreal.add_asset("/Game/Stuff/Rock", "StaticMesh")
        assets = [asset("/Game/Stuff/Rock", "StaticMesh")]
        caps = self.sortilege.probe_capabilities()
        plan = self.sortilege.build_plan(assets, self.sortilege.CONFIG, caps)
        # The apply itself runs with SAFE_MODE off -- only the undo below
        # is diagnosed.
        outcome = self.sortilege.run_apply(plan, caps)

        self.sortilege.CONFIG["SAFE_MODE"] = True
        results = self.sortilege.run_undo(outcome["undo_log"].path, caps)

        # The restore rename itself still happened...
        self.assertEqual(results["moved"], [("/Game/Meshes/Rock", "/Game/Stuff/Rock")])
        state = mock_unreal.get_state()
        self.assertIn("/Game/Stuff/Rock", state["assets"])
        # ...but nothing after the replay ran: no pre-restore cleanup, no
        # redirector cleanup, no empty-folder sweep -- so the redirector
        # the restore left behind is still there, and the vacated sort
        # folder was never swept.
        self.assertIsNone(results["pre_restore_cleanup"])
        self.assertNotIn("redirector_cleanup", results)
        self.assertIn("/Game/Meshes/Rock", state["redirectors"])
        self.assertNotIn("empty_folders", results)
        self.assertTrue(mock_unreal.EditorAssetLibrary.does_directory_exist("/Game/Meshes"))


# ---------------------------------------------------------------------------
# DISABLE_GC -- independent of SAFE_MODE
# ---------------------------------------------------------------------------

class DisableGcTests(unittest.TestCase):
    def setUp(self):
        self.sortilege = helpers.load_sortilege()
        self.tmp_dir = tempfile.mkdtemp(prefix="sortilege_test_")
        self.sortilege.CONFIG["LOG_DIR"] = self.tmp_dir

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_disable_gc_true_suppresses_collect_garbage_via_run_apply(self):
        self.sortilege.CONFIG["DISABLE_GC"] = True
        assets = [asset("/Game/Stuff/Rock%02d" % i, "StaticMesh") for i in range(30)]
        for a in assets:
            mock_unreal.add_asset(a["path"], a["class_name"])
        caps = self.sortilege.probe_capabilities()
        plan = self.sortilege.build_plan(assets, self.sortilege.CONFIG, caps)

        self.sortilege.run_apply(plan, caps)

        self.assertEqual(mock_unreal.get_state()["gc_calls"], 0)

    def test_disable_gc_false_preserves_existing_gc_behavior_via_run_apply(self):
        """Regression guard: DISABLE_GC defaults False, so a plain
        run_apply() on a big batch must still collect_garbage() exactly
        as it did before this feature existed."""
        self.assertFalse(self.sortilege.CONFIG["DISABLE_GC"])
        assets = [asset("/Game/Stuff/Rock%02d" % i, "StaticMesh") for i in range(25)]
        for a in assets:
            mock_unreal.add_asset(a["path"], a["class_name"])
        caps = self.sortilege.probe_capabilities()
        plan = self.sortilege.build_plan(assets, self.sortilege.CONFIG, caps)

        self.sortilege.run_apply(plan, caps)

        self.assertEqual(mock_unreal.get_state()["gc_calls"], 1)

    def test_disable_gc_true_suppresses_collect_garbage_in_cleanup_redirectors_manual_path(self):
        # fix_up_redirectors OFF forces the manual per-item recipe, whose
        # every-10 GC threshold this test actually trips (12 items).
        sortilege = helpers.load_sortilege(features={"fix_up_redirectors": False})
        sortilege.CONFIG["DISABLE_GC"] = True
        caps = sortilege.probe_capabilities()
        self.assertFalse(caps.fix_up_redirectors)
        for i in range(12):
            path = "/Game/Stuff/Rock%02d" % i
            mock_unreal.add_asset(path, "StaticMesh")
            mock_unreal.EditorAssetLibrary.rename_asset(path, "/Game/Meshes/Rock%02d" % i)

        gc_enabled = sortilege._effective_gc_enabled(caps, sortilege.CONFIG)
        self.assertFalse(gc_enabled)
        result = sortilege.cleanup_redirectors(
            ["/Game/Stuff", "/Game/Meshes"], caps, gc_enabled=gc_enabled)

        self.assertEqual(len(result["fixed"]), 12)
        self.assertEqual(mock_unreal.get_state()["gc_calls"], 0)

    def test_effective_gc_enabled_helper_matrix(self):
        caps_on = self.sortilege.probe_capabilities()
        self.assertTrue(caps_on.collect_garbage)

        self.assertTrue(self.sortilege._effective_gc_enabled(caps_on, {}))
        self.assertFalse(self.sortilege._effective_gc_enabled(caps_on, {"DISABLE_GC": True}))
        self.assertFalse(self.sortilege._effective_gc_enabled(caps_on, {"SAFE_MODE": True}))
        self.assertFalse(self.sortilege._effective_gc_enabled(
            caps_on, {"SAFE_MODE": True, "DISABLE_GC": True}))

        sortilege_no_gc = helpers.load_sortilege(features={"collect_garbage": False})
        caps_off = sortilege_no_gc.probe_capabilities()
        self.assertFalse(caps_off.collect_garbage)
        self.assertFalse(sortilege_no_gc._effective_gc_enabled(caps_off, {}))


# ---------------------------------------------------------------------------
# FIX_SOFT_REFERENCES -- independently gates the soft-reference pass
# ---------------------------------------------------------------------------

class FixSoftReferencesConfigGateTests(unittest.TestCase):
    def setUp(self):
        self.sortilege = helpers.load_sortilege()
        self.tmp_dir = tempfile.mkdtemp(prefix="sortilege_test_")
        self.sortilege.CONFIG["LOG_DIR"] = self.tmp_dir

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _plan_with_referencer(self):
        mock_unreal.add_asset("/Game/Stuff/Rock", "StaticMesh")
        mock_unreal.add_asset("/Game/Blueprints/BP_User", "Blueprint",
                               deps=["/Game/Stuff/Rock"])
        assets = [asset("/Game/Stuff/Rock", "StaticMesh")]
        caps = self.sortilege.probe_capabilities()
        plan = self.sortilege.build_plan(assets, self.sortilege.CONFIG, caps)
        return plan, caps

    def test_fix_soft_references_true_default_matches_current_behavior(self):
        self.assertTrue(self.sortilege.CONFIG["FIX_SOFT_REFERENCES"])
        plan, caps = self._plan_with_referencer()

        self.sortilege.run_apply(plan, caps)

        self.assertEqual(len(mock_unreal.get_state()["soft_rename_calls"]), 1)

    def test_fix_soft_references_false_skips_the_call(self):
        self.sortilege.CONFIG["FIX_SOFT_REFERENCES"] = False
        plan, caps = self._plan_with_referencer()

        outcome = self.sortilege.run_apply(plan, caps)

        self.assertEqual(mock_unreal.get_state()["soft_rename_calls"], [])
        # The move itself still happened -- only the soft-reference pass
        # was skipped.
        self.assertEqual(outcome["results"]["moved"],
                          [("/Game/Stuff/Rock", "/Game/Meshes/Rock")])


# ---------------------------------------------------------------------------
# Per-op trace marks -- durability + presence at each destructive call site
# ---------------------------------------------------------------------------

class PerOpTraceMarkTests(unittest.TestCase):
    def setUp(self):
        self.sortilege = helpers.load_sortilege()
        self.tmp_dir = tempfile.mkdtemp(prefix="sortilege_test_")
        mock_unreal.set_project_root("/ProjectX")

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_delete_asset_mark_is_durable_even_if_delete_asset_then_raises(self):
        # fix_up_redirectors OFF forces the manual recipe, whose
        # delete_asset() call is the one this mark guards.
        self.sortilege = helpers.load_sortilege(features={"fix_up_redirectors": False})
        mock_unreal.set_project_root("/ProjectX")
        mock_unreal.add_asset("/ProjectX/Stuff/Rock", "StaticMesh")
        mock_unreal.EditorAssetLibrary.rename_asset(
            "/ProjectX/Stuff/Rock", "/ProjectX/Meshes/Rock")
        caps = self.sortilege.probe_capabilities()
        self.assertFalse(caps.fix_up_redirectors)
        tracer = self.sortilege.CrashTracer.begin(self.tmp_dir)

        original_delete_asset = mock_unreal.EditorAssetLibrary.delete_asset

        def boom(path):
            raise RuntimeError("simulated crash mid-delete")

        mock_unreal.EditorAssetLibrary.delete_asset = staticmethod(boom)
        try:
            result = self.sortilege.cleanup_redirectors(
                ["/ProjectX/Stuff", "/ProjectX/Meshes"], caps, tracer=tracer)
        finally:
            mock_unreal.EditorAssetLibrary.delete_asset = staticmethod(original_delete_asset)

        # cleanup_redirectors' own try/except caught the simulated crash
        # -- the redirector lands in "remaining", not "fixed".
        self.assertEqual(result["fixed"], [])
        remaining_paths = [p for p, _why in result["remaining"]]
        self.assertIn("/ProjectX/Stuff/Rock", remaining_paths)

        # But the breadcrumb naming the victim was ALREADY durably on
        # disk before delete_asset was ever called -- same crash-safety
        # proof as UndoLog's, applied to the real call site.
        with open(tracer.path, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("delete_asset redirector: /ProjectX/Stuff/Rock", content)

    def test_delete_directory_mark_appears_before_the_folder_is_removed(self):
        assets = [asset("/ProjectX/Stuff/Rock", "StaticMesh")]
        for a in assets:
            mock_unreal.add_asset(a["path"], a["class_name"])
        config = dict(self.sortilege.CONFIG)
        caps = self.sortilege.probe_capabilities()
        plan = self.sortilege.build_plan(assets, config, caps)
        undo_log = self.sortilege.UndoLog.begin(self.tmp_dir, plan)
        self.sortilege.execute_plan(plan, caps, undo_log)
        self.sortilege.cleanup_redirectors(["/ProjectX/Stuff", "/ProjectX/Meshes"], caps)

        tracer = self.sortilege.CrashTracer.begin(self.tmp_dir)
        result = self.sortilege.cleanup_empty_folders(plan, config, tracer=tracer)

        self.assertIn("/ProjectX/Stuff", result["removed"])
        with open(tracer.path, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("delete_directory: /ProjectX/Stuff", content)

    def test_collect_garbage_mark_appears_with_the_running_count(self):
        # fix_up_redirectors OFF forces the manual per-item loop whose
        # every-10 GC threshold this test trips (12 redirectors).
        self.sortilege = helpers.load_sortilege(features={"fix_up_redirectors": False})
        mock_unreal.set_project_root("/ProjectX")
        for i in range(12):
            path = "/ProjectX/Stuff/Rock%02d" % i
            mock_unreal.add_asset(path, "StaticMesh")
            mock_unreal.EditorAssetLibrary.rename_asset(path, "/ProjectX/Meshes/Rock%02d" % i)
        caps = self.sortilege.probe_capabilities()
        self.assertFalse(caps.fix_up_redirectors)
        tracer = self.sortilege.CrashTracer.begin(self.tmp_dir)

        self.sortilege.cleanup_redirectors(
            ["/ProjectX/Stuff", "/ProjectX/Meshes"], caps, tracer=tracer)

        with open(tracer.path, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("collect_garbage (n=10)", content)

    def test_rename_referencing_soft_object_paths_mark_appears_with_package_count(self):
        # P1 (soft-reference bounty fix): fix_soft_references() now checks
        # EVERY project package under the discovered content root, not
        # just find_package_referencers_for_asset()'s hits -- the root-
        # cause fix for a soft referencer that query can miss entirely
        # (see test_redirectors.py's ConservativeRedirectorDeletionTests
        # and test_executor.py's ComprehensiveSoftRewriteTests for the
        # field-reported incident this closes). The count below is
        # therefore every package under "/ProjectX" after this fixture's
        # move -- BP_User, Rock's new real location, and Rock's old
        # (redirector) location -- 3, not just the 1 referencer-graph hit
        # this mark used to report before the comprehensive scan existed.
        mock_unreal.add_asset("/ProjectX/Blueprints/BP_User", "Blueprint",
                               deps=["/ProjectX/Stuff/Rock"])
        assets = [asset("/ProjectX/Stuff/Rock", "StaticMesh")]
        for a in assets:
            mock_unreal.add_asset(a["path"], a["class_name"])
        config = dict(self.sortilege.CONFIG)
        caps = self.sortilege.probe_capabilities()
        plan = self.sortilege.build_plan(assets, config, caps)
        undo_log = self.sortilege.UndoLog.begin(self.tmp_dir, plan)
        results = self.sortilege.execute_plan(plan, caps, undo_log)
        tracer = self.sortilege.CrashTracer.begin(self.tmp_dir)

        self.sortilege.fix_soft_references(results, caps, tracer=tracer)

        with open(tracer.path, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("rename_referencing_soft_object_paths (3 packages)", content)

    def test_resave_referencer_mark_appears_flush_only(self):
        # fix_up_redirectors OFF forces the manual recipe, whose resave
        # loop is the one this (high-volume, flush-only) mark guards.
        self.sortilege = helpers.load_sortilege(features={"fix_up_redirectors": False})
        mock_unreal.set_project_root("/ProjectX")
        mock_unreal.add_asset("/ProjectX/Stuff/Rock", "StaticMesh")
        mock_unreal.EditorAssetLibrary.rename_asset(
            "/ProjectX/Stuff/Rock", "/ProjectX/Meshes/Rock")
        mock_unreal.add_asset("/ProjectX/Blueprints/BP_User", "Blueprint",
                               deps=["/ProjectX/Stuff/Rock"])
        caps = self.sortilege.probe_capabilities()
        self.assertFalse(caps.fix_up_redirectors)
        tracer = self.sortilege.CrashTracer.begin(self.tmp_dir)

        self.sortilege.cleanup_redirectors(
            ["/ProjectX/Stuff", "/ProjectX/Meshes"], caps, tracer=tracer)

        with open(tracer.path, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("resave referencer: /ProjectX/Blueprints/BP_User", content)


if __name__ == "__main__":
    unittest.main()
