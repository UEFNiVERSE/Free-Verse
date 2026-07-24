"""Tests for sortilege.py's preview formatting, plan/report/undo-log
file writers -- Task 3.

sortilege.py already has CONFIG/probe/scan/classify/build_plan (Task 2).
These tests cover the presentation + file-writing layer built on top of
build_plan()'s output: format_preview()/print_preview(), resolve_log_dir(),
write_plan_json(), write_summary(), and the crash-safe UndoLog.
"""
import json
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


class FormatPreviewTests(unittest.TestCase):
    def setUp(self):
        self.sortilege = helpers.load_sortilege()

    def _plan(self, assets, config_overrides=None):
        config = dict(self.sortilege.CONFIG)
        if config_overrides:
            config.update(config_overrides)
        return self.sortilege.build_plan(assets, config, self.sortilege.probe_capabilities())

    def test_preview_lists_every_move_exactly_once(self):
        assets = [
            asset("/Game/Stuff/Rock", "StaticMesh"),
            asset("/Game/Stuff/Wood", "Texture2D"),
            asset("/Game/Stuff/Boom", "SoundWave"),
        ]
        plan = self._plan(assets)
        lines = self.sortilege.format_preview(plan)
        text = "\n".join(lines)

        self.assertEqual(len(plan["moves"]), 3)
        for move in plan["moves"]:
            occurrences = text.count(move["path"])
            self.assertEqual(occurrences, 1, "expected %r exactly once, found %d" % (
                move["path"], occurrences))
            self.assertIn(move["dest_path"], text)

    def test_preview_lists_every_skip_reason(self):
        assets = [
            asset("/Game/Verse/MyDevice", "VerseClass"),
            asset("/OtherMount/Stuff/Rock", "StaticMesh"),
        ]
        plan = self._plan(assets)
        lines = self.sortilege.format_preview(plan)
        text = "\n".join(lines)

        reasons = set(s["reason"] for s in plan["skips"])
        self.assertEqual(len(reasons), 2)
        for reason in reasons:
            self.assertIn(reason, text)

    def test_preview_header_counts_are_unambiguous(self):
        # one plain move, one move+rename, one rename-in-place, one skip
        config = dict(self.sortilege.CONFIG)
        config["ENABLE_PREFIX_RENAME"] = True
        assets = [
            # MetaSoundSource has no PREFIX_MAP entry -- a pure move, not
            # touched by the rename pass even with ENABLE_PREFIX_RENAME on.
            asset("/Game/Stuff/Boom", "MetaSoundSource"),     # plain move
            asset("/Game/Stuff/T_Rock", "StaticMesh"),        # move+rename
            asset("/Game/Meshes/T_Boulder", "StaticMesh"),    # rename-in-place
            asset("/Game/Verse/MyDevice", "VerseClass"),      # skip
        ]
        plan = self.sortilege.build_plan(assets, config, self.sortilege.probe_capabilities())
        move_actions = [m["action"] for m in plan["moves"]]
        self.assertEqual(sorted(move_actions), ["move", "move+rename", "rename"])

        lines = self.sortilege.format_preview(plan)
        text = "\n".join(lines)
        self.assertIn(
            "2 asset(s) to move (1 will also be renamed), 1 rename-in-place, "
            "1 skipped",
            text,
        )

    def test_preview_is_ascii_only(self):
        assets = [asset("/Game/Stuff/Rock", "StaticMesh")]
        plan = self._plan(assets)
        lines = self.sortilege.format_preview(plan)
        for line in lines:
            self.assertTrue(all(ord(c) < 128 for c in line), "non-ascii in: %r" % line)

    def test_preview_truncates_long_paths_with_ellipsis(self):
        long_folder = "/Game/" + ("VeryLongFolderName" * 5)
        assets = [asset(long_folder + "/Rock", "StaticMesh")]
        plan = self._plan(assets)
        lines = self.sortilege.format_preview(plan)
        text = "\n".join(lines)

        self.assertIn("...", text)
        self.assertNotIn(long_folder, text)  # the untruncated original must not appear

    def test_preview_footer_has_mandatory_caution_lines_verbatim(self):
        plan = self._plan([asset("/Game/Stuff/Rock", "StaticMesh")])
        lines = self.sortilege.format_preview(plan)
        text = "\n".join(lines)

        self.assertIn(
            "NOTE: referencer data is cached by the engine; counts can "
            "include false positives until assets are loaded and re-saved.",
            text,
        )
        self.assertIn(
            "CAUTION: if your Verse code references assets by "
            "folder-qualified name (Asset Reflection), moving those "
            "assets requires updating that Verse code. Redirectors do "
            "not rewrite Verse source.",
            text,
        )
        self.assertIn("DRY RUN - nothing was changed. To execute:", text)


class PrintPreviewTests(unittest.TestCase):
    def test_print_preview_logs_via_unreal_log(self):
        sortilege = helpers.load_sortilege()
        plan = sortilege.build_plan(
            [asset("/Game/Stuff/Rock", "StaticMesh")],
            sortilege.CONFIG, sortilege.probe_capabilities())

        sortilege.print_preview(plan)

        logged = "\n".join(mock_unreal.get_state()["log"])
        self.assertIn("/Game/Stuff/Rock", logged)
        self.assertIn("DRY RUN", logged)


class LogDirAndFileWriterTests(unittest.TestCase):
    def setUp(self):
        self.sortilege = helpers.load_sortilege()
        self.tmp_dir = tempfile.mkdtemp(prefix="sortilege_test_")

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_resolve_log_dir_honors_config_override(self):
        override_dir = os.path.join(self.tmp_dir, "custom_logs")
        log_dir = self.sortilege.resolve_log_dir({"LOG_DIR": override_dir})
        self.assertEqual(log_dir, os.path.normpath(override_dir))
        self.assertTrue(os.path.isdir(log_dir))

    def test_resolve_log_dir_falls_back_when_no_override(self):
        # Task 4 added unreal.SystemLibrary (for collect_garbage()), but it
        # still genuinely does not define get_project_saved_directory() --
        # that absence IS the gating -- so this exercises the fall-through
        # to unreal.Paths.project_saved_dir().
        self.assertFalse(hasattr(mock_unreal, "SystemLibrary")
                          and hasattr(mock_unreal.SystemLibrary, "get_project_saved_directory"))
        log_dir = self.sortilege.resolve_log_dir({"LOG_DIR": ""})
        self.assertTrue(os.path.isdir(log_dir))

    def test_write_plan_json_round_trips(self):
        plan = self.sortilege.build_plan(
            [asset("/Game/Stuff/Rock", "StaticMesh")],
            self.sortilege.CONFIG, self.sortilege.probe_capabilities())
        path = self.sortilege.write_plan_json(plan, self.tmp_dir)

        self.assertTrue(os.path.isfile(path))
        self.assertTrue(os.path.basename(path).startswith("sortilege_plan_"))
        self.assertTrue(path.endswith(".json"))

        with open(path, "r", encoding="utf-8") as f:
            loaded = json.load(f)
        self.assertEqual(loaded, plan)

    def test_non_ascii_asset_name_round_trips_through_plan_json_and_undo_log(self):
        # Reviewer-carried minor: every open() in sortilege.py must pin
        # encoding="utf-8" so a non-ASCII asset name can't crash a run on a
        # Windows box whose locale-default encoding (e.g. cp1252) can't
        # represent it. Covers the whole persistence surface a real apply
        # run touches: the plan JSON, the human-readable summary report
        # (raw text, not JSON-escaped -- the one writer that actually can't
        # fall back to ASCII), and the undo log.
        non_ascii_name = u"Rock_資産"  # "Rock_資産"
        assets = [
            asset("/Game/Stuff/Rock", "StaticMesh"),
            asset(u"/Game/Stuff/" + non_ascii_name, "StaticMesh"),
        ]
        plan = self.sortilege.build_plan(assets, self.sortilege.CONFIG,
                                          self.sortilege.probe_capabilities())
        non_ascii_move = next(m for m in plan["moves"] if m["name"] == non_ascii_name)

        plan_path = self.sortilege.write_plan_json(plan, self.tmp_dir)
        with open(plan_path, "r", encoding="utf-8") as f:
            loaded_plan = json.load(f)
        self.assertEqual(loaded_plan, plan)

        results = {"moved": [(non_ascii_move["path"], non_ascii_move["dest_path"])], "failed": []}
        report_path = self.sortilege.write_summary(plan, results, self.tmp_dir)
        with open(report_path, "r", encoding="utf-8") as f:
            report_text = f.read()
        self.assertIn(non_ascii_name, report_text)

        undo_log = self.sortilege.UndoLog.begin(self.tmp_dir, plan)
        undo_log.record(non_ascii_move["path"], non_ascii_move["dest_path"])
        reloaded_undo = self.sortilege.load_undo_log(undo_log.path)
        self.assertEqual(reloaded_undo["moves"][0],
                          {"from": non_ascii_move["path"], "to": non_ascii_move["dest_path"]})

    def test_write_summary_contains_moved_renamed_skipped(self):
        assets = [
            asset("/Game/Stuff/Rock", "StaticMesh"),
            asset("/Game/Verse/MyDevice", "VerseClass"),
        ]
        plan = self.sortilege.build_plan(assets, self.sortilege.CONFIG,
                                          self.sortilege.probe_capabilities())
        results = {
            "moved": [("/Game/Stuff/Rock", "/Game/Meshes/Rock")],
            "failed": [],
        }
        path = self.sortilege.write_summary(plan, results, self.tmp_dir)

        self.assertTrue(os.path.isfile(path))
        self.assertTrue(os.path.basename(path).startswith("sortilege_report_"))
        self.assertTrue(path.endswith(".txt"))

        with open(path, "r") as f:
            text = f.read()
        self.assertIn("/Game/Stuff/Rock", text)
        self.assertIn("/Game/Meshes/Rock", text)
        # The protected-class skip reason -- now the unified NEVER_MOVE
        # structural-asset message (supersedes the old Verse-specific
        # text; see classify()'s NEVER_MOVE guard).
        self.assertIn("structural project asset", text)
        self.assertIn("Verse", text)
        self.assertIn("Redirector cleanup: not run", text)
        self.assertIn("Verify: not run", text)

    def test_write_summary_reports_redirector_cleanup_and_verify_when_present(self):
        plan = self.sortilege.build_plan([], self.sortilege.CONFIG,
                                          self.sortilege.probe_capabilities())
        results = {
            "moved": [],
            "failed": [],
            "redirector_cleanup": {"fixed": ["/Game/Old/Rock"], "remaining": [], "method": "manual"},
            "verify": {"ok": True, "missing": [], "old_paths_alive": [], "leftover_redirectors": []},
        }
        path = self.sortilege.write_summary(plan, results, self.tmp_dir)
        with open(path, "r") as f:
            text = f.read()
        self.assertIn("1 fixed, 0 remaining", text)
        self.assertIn("ok=True", text)

    def test_write_summary_flags_a_cancelled_run(self):
        """Task 5 review carry-over: execute_plan() sets results["cancelled"]
        = True when a ScopedSlowTask cancel came through mid-batch. The
        summary must surface that loudly instead of a partial result set
        silently reading like a clean, complete run."""
        plan = self.sortilege.build_plan([], self.sortilege.CONFIG,
                                          self.sortilege.probe_capabilities())
        results = {
            "moved": [("/Game/Stuff/Rock", "/Game/Meshes/Rock")],
            "failed": [],
            "cancelled": True,
        }
        path = self.sortilege.write_summary(plan, results, self.tmp_dir)
        with open(path, "r") as f:
            text = f.read()
        self.assertIn("RUN CANCELLED BY USER", text)

    def test_write_summary_omits_cancelled_line_on_a_normal_run(self):
        plan = self.sortilege.build_plan([], self.sortilege.CONFIG,
                                          self.sortilege.probe_capabilities())
        results = {"moved": [], "failed": []}
        path = self.sortilege.write_summary(plan, results, self.tmp_dir)
        with open(path, "r") as f:
            text = f.read()
        self.assertNotIn("CANCELLED", text)

    def test_write_summary_reports_pre_restore_cleanup_when_present(self):
        """Task 5 review carry-over: undo() attaches its pre-reversal
        redirector cleanup as results["pre_restore_cleanup"] so a
        partially-failed undo is self-explanatory in the summary."""
        plan = self.sortilege.build_plan([], self.sortilege.CONFIG,
                                          self.sortilege.probe_capabilities())
        results = {
            "moved": [], "failed": [],
            "pre_restore_cleanup": {"fixed": [], "remaining": [("/Game/Old/Rock", "still referenced")],
                                     "method": "manual"},
        }
        path = self.sortilege.write_summary(plan, results, self.tmp_dir)
        with open(path, "r") as f:
            text = f.read()
        self.assertIn("Pre-restore redirector cleanup: 0 fixed, 1 remaining", text)

    def test_write_summary_omits_pre_restore_cleanup_line_when_absent(self):
        plan = self.sortilege.build_plan([], self.sortilege.CONFIG,
                                          self.sortilege.probe_capabilities())
        results = {"moved": [], "failed": []}
        path = self.sortilege.write_summary(plan, results, self.tmp_dir)
        with open(path, "r") as f:
            text = f.read()
        self.assertNotIn("Pre-restore", text)


class UndoLogTests(unittest.TestCase):
    def setUp(self):
        self.sortilege = helpers.load_sortilege()
        self.tmp_dir = tempfile.mkdtemp(prefix="sortilege_test_")

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _empty_plan(self):
        return self.sortilege.build_plan([], self.sortilege.CONFIG,
                                          self.sortilege.probe_capabilities())

    def test_begin_creates_file_with_expected_shape(self):
        undo = self.sortilege.UndoLog.begin(self.tmp_dir, self._empty_plan())

        self.assertTrue(os.path.isfile(undo.path))
        self.assertTrue(os.path.basename(undo.path).startswith("sortilege_undo_"))

        with open(undo.path, "r") as f:
            data = json.load(f)
        self.assertEqual(data["version"], 1)
        self.assertEqual(data["moves"], [])
        self.assertIn("created", data)

    def test_record_survives_simulated_crash(self):
        undo = self.sortilege.UndoLog.begin(self.tmp_dir, self._empty_plan())

        undo.record("/Game/Stuff/Rock", "/Game/Meshes/Rock")
        # Simulate a crash right here: read the file back from disk without
        # calling anything else on the UndoLog instance. The first record
        # must already be durably persisted.
        with open(undo.path, "r") as f:
            mid_crash_data = json.load(f)
        self.assertEqual(mid_crash_data["moves"],
                          [{"from": "/Game/Stuff/Rock", "to": "/Game/Meshes/Rock"}])

        undo.record("/Game/Stuff/Wood", "/Game/Textures/Wood")
        with open(undo.path, "r") as f:
            final_data = json.load(f)
        self.assertEqual(len(final_data["moves"]), 2)
        self.assertEqual(final_data["moves"][1],
                          {"from": "/Game/Stuff/Wood", "to": "/Game/Textures/Wood"})

    def test_load_undo_log_reads_back_the_same_shape(self):
        undo = self.sortilege.UndoLog.begin(self.tmp_dir, self._empty_plan())
        undo.record("/Game/Stuff/Rock", "/Game/Meshes/Rock")

        loaded = self.sortilege.load_undo_log(undo.path)
        self.assertEqual(loaded["version"], 1)
        self.assertEqual(loaded["moves"], [{"from": "/Game/Stuff/Rock", "to": "/Game/Meshes/Rock"}])

    def test_record_never_leaves_a_tmp_file_behind(self):
        """UndoLog._write() must write to a "<path>.tmp" file and
        os.replace() it into place, never write self.path directly --
        so a crash mid-write can only ever leave a half-written .tmp
        file, never a truncated real undo log. After a normal successful
        record(), no .tmp file should remain."""
        undo = self.sortilege.UndoLog.begin(self.tmp_dir, self._empty_plan())
        undo.record("/Game/Stuff/Rock", "/Game/Meshes/Rock")

        self.assertFalse(os.path.isfile(undo.path + ".tmp"))
        with open(undo.path, "r") as f:
            data = json.load(f)
        self.assertEqual(data["moves"], [{"from": "/Game/Stuff/Rock", "to": "/Game/Meshes/Rock"}])

    def test_write_is_atomic_a_mid_write_failure_never_corrupts_the_prior_record(self):
        """Regression: UndoLog._write() used to open(self.path, "w") and
        json.dump() straight into it -- a crash/exception partway through
        that dump would leave a truncated (or empty) file on disk,
        destroying the PRIOR successful record even though nothing new
        was actually lost. Simulate that failure mode directly: make
        json.dump raise on the second record() call and confirm the file
        on disk still parses and still holds exactly the first move."""
        undo = self.sortilege.UndoLog.begin(self.tmp_dir, self._empty_plan())
        undo.record("/Game/Stuff/Rock", "/Game/Meshes/Rock")

        with open(undo.path, "r") as f:
            after_first = json.load(f)
        self.assertEqual(after_first["moves"],
                          [{"from": "/Game/Stuff/Rock", "to": "/Game/Meshes/Rock"}])

        original_dump = self.sortilege.json.dump

        def flaky_dump(*args, **kwargs):
            raise RuntimeError("simulated crash mid-write")

        self.sortilege.json.dump = flaky_dump
        try:
            with self.assertRaises(RuntimeError):
                undo.record("/Game/Stuff/Wood", "/Game/Textures/Wood")
        finally:
            self.sortilege.json.dump = original_dump

        with open(undo.path, "r") as f:
            after_failed_second = json.load(f)
        self.assertEqual(after_failed_second["moves"],
                          [{"from": "/Game/Stuff/Rock", "to": "/Game/Meshes/Rock"}])


if __name__ == "__main__":
    unittest.main()
