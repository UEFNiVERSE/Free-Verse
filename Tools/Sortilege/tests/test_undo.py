"""Tests for sortilege.py's undo() flow and cleanup_empty_folders() --
Task 4.

undo() does not exist yet -- this file is expected to fail with
AttributeError until Task 4 implements it.
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


class UndoTestBase(unittest.TestCase):
    def setUp(self):
        self.sortilege = helpers.load_sortilege()
        self.tmp_dir = tempfile.mkdtemp(prefix="sortilege_test_")

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _plan(self, assets, config_overrides=None):
        for a in assets:
            mock_unreal.add_asset(a["path"], a["class_name"])
        config = dict(self.sortilege.CONFIG)
        if config_overrides:
            config.update(config_overrides)
        return self.sortilege.build_plan(assets, config, self.sortilege.probe_capabilities())


class UndoRoundTripTests(UndoTestBase):
    def test_full_round_trip_restores_original_paths_and_cleans_redirectors(self):
        mock_unreal.add_asset("/Game/Blueprints/BP_User", "Blueprint",
                               deps=["/Game/Stuff/Rock"])
        assets = [asset("/Game/Stuff/Rock", "StaticMesh")]
        plan = self._plan(assets)
        caps = self.sortilege.probe_capabilities()
        undo_log = self.sortilege.UndoLog.begin(self.tmp_dir, plan)

        exec_results = self.sortilege.execute_plan(plan, caps, undo_log)
        self.assertEqual(exec_results["moved"], [("/Game/Stuff/Rock", "/Game/Meshes/Rock")])

        self.sortilege.CONFIG["I_UNDERSTAND_THIS_MODIFIES_MY_PROJECT"] = True
        mock_unreal.set_dialog_answer("Yes")
        undo_results = self.sortilege.undo(undo_log.path, caps)

        state = mock_unreal.get_state()
        self.assertIn("/Game/Stuff/Rock", state["assets"])
        self.assertNotIn("/Game/Meshes/Rock", state["assets"])
        self.assertNotIn("/Game/Stuff/Rock", state["redirectors"])
        self.assertNotIn("/Game/Meshes/Rock", state["redirectors"])
        self.assertEqual(
            state["assets"]["/Game/Blueprints/BP_User"]["deps"],
            ["/Game/Stuff/Rock"],
        )
        self.assertEqual(undo_results["moved"], [("/Game/Meshes/Rock", "/Game/Stuff/Rock")])

    def test_undo_restores_multiple_moves_in_reverse_order(self):
        assets = [
            asset("/Game/Stuff/Rock", "StaticMesh"),
            asset("/Game/Stuff/Wood", "Texture2D"),
        ]
        plan = self._plan(assets)
        caps = self.sortilege.probe_capabilities()
        undo_log = self.sortilege.UndoLog.begin(self.tmp_dir, plan)
        self.sortilege.execute_plan(plan, caps, undo_log)

        self.sortilege.CONFIG["I_UNDERSTAND_THIS_MODIFIES_MY_PROJECT"] = True
        mock_unreal.set_dialog_answer("Yes")
        self.sortilege.undo(undo_log.path, caps)

        state = mock_unreal.get_state()
        self.assertIn("/Game/Stuff/Rock", state["assets"])
        self.assertIn("/Game/Stuff/Wood", state["assets"])
        self.assertNotIn("/Game/Meshes/Rock", state["assets"])
        self.assertNotIn("/Game/Textures/Wood", state["assets"])


class UndoPreRestoreCleanupResultTests(UndoTestBase):
    def test_results_carry_the_pre_restore_cleanup_outcome(self):
        """Task 5 review carry-over: undo() must attach its pre-reversal
        redirector cleanup pass (the one that clears the forward-move
        redirectors squatting on each restore destination) onto its own
        results dict as "pre_restore_cleanup", so a partially-failed undo
        is self-explanatory from the results/summary alone."""
        assets = [asset("/Game/Stuff/Rock", "StaticMesh")]
        plan = self._plan(assets)
        caps = self.sortilege.probe_capabilities()
        undo_log = self.sortilege.UndoLog.begin(self.tmp_dir, plan)
        self.sortilege.execute_plan(plan, caps, undo_log)

        self.sortilege.CONFIG["I_UNDERSTAND_THIS_MODIFIES_MY_PROJECT"] = True
        mock_unreal.set_dialog_answer("Yes")
        undo_results = self.sortilege.undo(undo_log.path, caps)

        self.assertIn("pre_restore_cleanup", undo_results)
        cleanup = undo_results["pre_restore_cleanup"]
        self.assertIsNotNone(cleanup)
        self.assertIn("fixed", cleanup)
        self.assertIn("remaining", cleanup)
        self.assertIn("method", cleanup)


class UndoConfirmGateTests(UndoTestBase):
    def test_blocked_when_confirm_flag_is_false(self):
        assets = [asset("/Game/Stuff/Rock", "StaticMesh")]
        plan = self._plan(assets)
        caps = self.sortilege.probe_capabilities()
        undo_log = self.sortilege.UndoLog.begin(self.tmp_dir, plan)
        self.sortilege.execute_plan(plan, caps, undo_log)

        self.assertFalse(self.sortilege.CONFIG["I_UNDERSTAND_THIS_MODIFIES_MY_PROJECT"])
        result = self.sortilege.undo(undo_log.path, caps)

        self.assertEqual(result["moved"], [])
        state = mock_unreal.get_state()
        # Nothing was restored -- the asset is still at its post-move path.
        self.assertIn("/Game/Meshes/Rock", state["assets"])
        self.assertNotIn("/Game/Stuff/Rock", state["assets"])

    def test_blocked_when_dialog_declined(self):
        assets = [asset("/Game/Stuff/Rock", "StaticMesh")]
        plan = self._plan(assets)
        caps = self.sortilege.probe_capabilities()
        self.assertTrue(caps.editor_dialog)
        undo_log = self.sortilege.UndoLog.begin(self.tmp_dir, plan)
        self.sortilege.execute_plan(plan, caps, undo_log)

        self.sortilege.CONFIG["I_UNDERSTAND_THIS_MODIFIES_MY_PROJECT"] = True
        mock_unreal.set_dialog_answer("No")
        result = self.sortilege.undo(undo_log.path, caps)

        self.assertEqual(result["moved"], [])
        state = mock_unreal.get_state()
        self.assertIn("/Game/Meshes/Rock", state["assets"])

    def test_proceeds_when_dialog_confirmed(self):
        assets = [asset("/Game/Stuff/Rock", "StaticMesh")]
        plan = self._plan(assets)
        caps = self.sortilege.probe_capabilities()
        undo_log = self.sortilege.UndoLog.begin(self.tmp_dir, plan)
        self.sortilege.execute_plan(plan, caps, undo_log)

        self.sortilege.CONFIG["I_UNDERSTAND_THIS_MODIFIES_MY_PROJECT"] = True
        mock_unreal.set_dialog_answer("Yes")
        result = self.sortilege.undo(undo_log.path, caps)

        self.assertEqual(result["moved"], [("/Game/Meshes/Rock", "/Game/Stuff/Rock")])
        state = mock_unreal.get_state()
        self.assertIn("/Game/Stuff/Rock", state["assets"])


class UndoArtifactCollisionTests(UndoTestBase):
    def test_reversal_artifacts_never_clobber_the_original_undo_log(self):
        """Regression: undo() used to stamp its reversal plan with the
        ORIGINAL run's "created" timestamp. UndoLog.begin() derives its
        filename from that timestamp, and undo() resolves the same log
        dir -- so the reversal's own undo log truncated the very file
        being replayed, destroying the original run's crash-safety
        record. The reversal must mint its own fresh timestamp."""
        import json

        assets = [asset("/Game/Stuff/Rock", "StaticMesh")]
        plan = self._plan(assets)
        caps = self.sortilege.probe_capabilities()

        # The original undo log lives in the SAME directory the reversal
        # will write to (LOG_DIR override makes resolve_log_dir() return
        # exactly this dir inside undo()).
        self.sortilege.CONFIG["LOG_DIR"] = self.tmp_dir
        undo_log = self.sortilege.UndoLog.begin(self.tmp_dir, plan)
        self.sortilege.execute_plan(plan, caps, undo_log)

        with open(undo_log.path, "r") as f:
            original_before = json.load(f)
        self.assertEqual(len(original_before["moves"]), 1)

        self.sortilege.CONFIG["I_UNDERSTAND_THIS_MODIFIES_MY_PROJECT"] = True
        mock_unreal.set_dialog_answer("Yes")
        self.sortilege.undo(undo_log.path, caps)

        # The original run's undo log must survive the reversal intact.
        with open(undo_log.path, "r") as f:
            original_after = json.load(f)
        self.assertEqual(
            original_after["moves"],
            [{"from": "/Game/Stuff/Rock", "to": "/Game/Meshes/Rock"}],
        )

        # And the reversal must have written its own, SEPARATE undo log.
        undo_files = [name for name in os.listdir(self.tmp_dir)
                      if name.startswith("sortilege_undo_")]
        self.assertEqual(len(undo_files), 2)


class UndoOrderDependentReplayTests(UndoTestBase):
    def test_undo_replays_a_two_hop_chain_last_move_first(self):
        """Regression-pin for _reversed_moves_from_log()'s reversed()
        call: when the SAME asset has been moved twice -- e.g. two
        Sortilege applies sharing one undo log, without undoing in
        between -- the chain must be reversed LAST-recorded-first. The
        asset currently lives at the END of the chain (/Game/_Organized/
        Meshes/Rock), not at the middle hop (/Game/Meshes/Rock).
        Reversing oldest-first would try to rename FROM a path nothing
        currently occupies (the middle hop is long gone -- the asset
        moved on) and that item would fail outright, leaving the asset
        stuck partway restored instead of back at its original path."""
        assets = [asset("/Game/Stuff/Rock", "StaticMesh")]
        plan1 = self._plan(assets)
        caps = self.sortilege.probe_capabilities()
        undo_log = self.sortilege.UndoLog.begin(self.tmp_dir, plan1)

        result1 = self.sortilege.execute_plan(plan1, caps, undo_log)
        self.assertEqual(result1["moved"], [("/Game/Stuff/Rock", "/Game/Meshes/Rock")])

        # A second run, sharing the SAME undo log, moves the asset again
        # from wherever the first run left it -- the second hop of the
        # chain. (The asset is already registered in the mock from the
        # first move; no re-registration needed.)
        config2 = dict(self.sortilege.CONFIG)
        config2["SORT_ROOT"] = "_Organized"
        assets2 = [asset("/Game/Meshes/Rock", "StaticMesh")]
        plan2 = self.sortilege.build_plan(assets2, config2, caps)
        result2 = self.sortilege.execute_plan(plan2, caps, undo_log)
        self.assertEqual(
            result2["moved"], [("/Game/Meshes/Rock", "/Game/_Organized/Meshes/Rock")])

        self.assertEqual(len(undo_log.moves), 2)

        self.sortilege.CONFIG["I_UNDERSTAND_THIS_MODIFIES_MY_PROJECT"] = True
        mock_unreal.set_dialog_answer("Yes")
        undo_results = self.sortilege.undo(undo_log.path, caps)

        self.assertEqual(undo_results["failed"], [])
        self.assertEqual(len(undo_results["moved"]), 2)
        state = mock_unreal.get_state()
        self.assertIn("/Game/Stuff/Rock", state["assets"])
        self.assertNotIn("/Game/Meshes/Rock", state["assets"])
        self.assertNotIn("/Game/_Organized/Meshes/Rock", state["assets"])


class UndoReferencedRedirectorGuardTests(UndoTestBase):
    def setUp(self):
        # fix_up_redirectors OFF = today's real UEFN (the API does not
        # exist in any shipped engine) -- forces the manual cleanup
        # recipe, whose referencer-emptiness guard is what this test
        # exercises.
        super(UndoReferencedRedirectorGuardTests, self).setUp()
        self.sortilege = helpers.load_sortilege(features={"fix_up_redirectors": False})

    def test_uncleanable_restore_destination_redirector_is_never_force_deleted(self):
        """Regression: undo() used to force-delete any redirector sitting
        on a restore destination with NO referencer check -- delete_asset
        is a force delete, so a redirector something still points at
        would be ripped out from under its referencers. The reversal must
        instead go through the referencer-safe cleanup; anything that
        cannot be cleared stays put and that item's reverse rename fails
        loudly while the rest of the batch still restores."""
        assets = [
            asset("/Game/Stuff/Rock", "StaticMesh"),
            asset("/Game/Stuff/Wood", "Texture2D"),
        ]
        plan = self._plan(assets)
        caps = self.sortilege.probe_capabilities()
        undo_log = self.sortilege.UndoLog.begin(self.tmp_dir, plan)
        self.sortilege.execute_plan(plan, caps, undo_log)

        # A stale referencer still pointing at Rock's forward-move
        # redirector, whose package can never be loaded (so the cleanup
        # recipe can never resave it and the redirector can never be
        # confirmed referencer-free).
        mock_unreal.add_asset("/Game/Blueprints/BP_Broken", "Blueprint",
                               deps=["/Game/Stuff/Rock"])
        original_load = mock_unreal.EditorAssetLibrary.load_asset

        def flaky_load(path):
            if "BP_Broken" in path:
                return None
            return original_load(path)

        mock_unreal.EditorAssetLibrary.load_asset = staticmethod(flaky_load)
        try:
            self.sortilege.CONFIG["I_UNDERSTAND_THIS_MODIFIES_MY_PROJECT"] = True
            mock_unreal.set_dialog_answer("Yes")
            results = self.sortilege.undo(undo_log.path, caps)
        finally:
            mock_unreal.EditorAssetLibrary.load_asset = staticmethod(original_load)

        state = mock_unreal.get_state()

        # Rock's restore failed loudly -- and its redirector was NEVER
        # force-deleted out from under BP_Broken.
        failed_pairs = [(f[0], f[1]) for f in results["failed"]]
        self.assertIn(("/Game/Meshes/Rock", "/Game/Stuff/Rock"), failed_pairs)
        self.assertIn("/Game/Stuff/Rock", state["redirectors"])
        self.assertIn("/Game/Meshes/Rock", state["assets"])

        # The rest of the batch still restored.
        self.assertIn(("/Game/Textures/Wood", "/Game/Stuff/Wood"), results["moved"])
        self.assertIn("/Game/Stuff/Wood", state["assets"])


class CleanupEmptyFoldersTests(unittest.TestCase):
    def setUp(self):
        self.sortilege = helpers.load_sortilege()

    def _plan(self, assets, config_overrides=None):
        for a in assets:
            mock_unreal.add_asset(a["path"], a["class_name"])
        config = dict(self.sortilege.CONFIG)
        if config_overrides:
            config.update(config_overrides)
        return self.sortilege.build_plan(assets, config, self.sortilege.probe_capabilities())

    def test_deletes_source_folder_left_empty_by_the_moves(self):
        assets = [asset("/Game/Stuff/Rock", "StaticMesh")]
        plan = self._plan(assets)
        caps = self.sortilege.probe_capabilities()
        undo_log_dir = tempfile.mkdtemp(prefix="sortilege_test_")
        try:
            undo_log = self.sortilege.UndoLog.begin(undo_log_dir, plan)
            self.sortilege.execute_plan(plan, caps, undo_log)
            # cleanup_empty_folders runs AFTER cleanup_redirectors in the
            # real main() flow -- a leftover redirector still legitimately
            # occupies (and thus blocks deletion of) the source folder
            # until it's cleaned, same as a real asset would.
            self.sortilege.cleanup_redirectors(["/Game/Stuff", "/Game/Meshes"], caps)

            result = self.sortilege.cleanup_empty_folders(plan)

            self.assertIn("/Game/Stuff", result["removed"])
            self.assertFalse(mock_unreal.EditorAssetLibrary.does_directory_exist("/Game/Stuff"))
        finally:
            shutil.rmtree(undo_log_dir, ignore_errors=True)

    def test_does_not_delete_source_folder_still_holding_other_assets(self):
        mock_unreal.add_asset("/Game/Stuff/Leftover", "SoundWave")
        assets = [asset("/Game/Stuff/Rock", "StaticMesh")]
        plan = self._plan(assets)
        caps = self.sortilege.probe_capabilities()
        undo_log_dir = tempfile.mkdtemp(prefix="sortilege_test_")
        try:
            undo_log = self.sortilege.UndoLog.begin(undo_log_dir, plan)
            self.sortilege.execute_plan(plan, caps, undo_log)

            result = self.sortilege.cleanup_empty_folders(plan)

            self.assertNotIn("/Game/Stuff", result["removed"])
            self.assertTrue(mock_unreal.EditorAssetLibrary.does_directory_exist("/Game/Stuff"))
        finally:
            shutil.rmtree(undo_log_dir, ignore_errors=True)

    def test_never_deletes_the_content_root_itself(self):
        assets = [asset("/Game/Rock", "StaticMesh")]
        plan = self._plan(assets)
        caps = self.sortilege.probe_capabilities()
        undo_log_dir = tempfile.mkdtemp(prefix="sortilege_test_")
        try:
            undo_log = self.sortilege.UndoLog.begin(undo_log_dir, plan)
            self.sortilege.execute_plan(plan, caps, undo_log)

            result = self.sortilege.cleanup_empty_folders(plan)

            self.assertNotIn("/Game", result["removed"])
        finally:
            shutil.rmtree(undo_log_dir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
