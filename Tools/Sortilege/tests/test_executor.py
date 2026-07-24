"""Tests for sortilege.py's executor -- Task 4.

Covers ensure_directories(), object_path(), execute_plan(), and
fix_soft_references(). sortilege.py already has CONFIG/probe/scan/
classify/build_plan (Task 2) and format_preview/write_summary/UndoLog
(Task 3). These tests are written first (TDD) -- execute_plan() etc. do
not exist yet and this file is expected to fail with AttributeError until
Task 4 implements them.

Every test loads a fresh module + fresh mock via helpers.load_sortilege()
so no state leaks between tests.
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


class ExecutorTestBase(unittest.TestCase):
    def setUp(self):
        self.sortilege = helpers.load_sortilege()
        self.tmp_dir = tempfile.mkdtemp(prefix="sortilege_test_")

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _plan(self, assets, config_overrides=None, register=True):
        if register:
            for a in assets:
                mock_unreal.add_asset(a["path"], a["class_name"])
        config = dict(self.sortilege.CONFIG)
        if config_overrides:
            config.update(config_overrides)
        return self.sortilege.build_plan(assets, config, self.sortilege.probe_capabilities())

    def _undo_log(self, plan):
        return self.sortilege.UndoLog.begin(self.tmp_dir, plan)


class ObjectPathHelperTests(unittest.TestCase):
    def test_object_path_appends_dot_name(self):
        sortilege = helpers.load_sortilege()
        self.assertEqual(
            sortilege.object_path("/Game/Meshes/Rock"), "/Game/Meshes/Rock.Rock")

    def test_object_path_handles_root_level_asset(self):
        sortilege = helpers.load_sortilege()
        self.assertEqual(sortilege.object_path("/Game/Rock"), "/Game/Rock.Rock")


class EnsureDirectoriesTests(ExecutorTestBase):
    def test_creates_every_distinct_missing_dest_folder(self):
        assets = [
            asset("/Game/Stuff/Rock", "StaticMesh"),
            asset("/Game/Stuff/Wood", "Texture2D"),
        ]
        plan = self._plan(assets)
        lib = mock_unreal.EditorAssetLibrary
        self.assertFalse(lib.does_directory_exist("/Game/Meshes"))
        self.assertFalse(lib.does_directory_exist("/Game/Textures"))

        self.sortilege.ensure_directories(plan)

        self.assertTrue(lib.does_directory_exist("/Game/Meshes"))
        self.assertTrue(lib.does_directory_exist("/Game/Textures"))

    def test_does_not_error_when_dest_already_exists(self):
        assets = [asset("/Game/Stuff/Rock", "StaticMesh")]
        plan = self._plan(assets)
        mock_unreal.EditorAssetLibrary.make_directory("/Game/Meshes")
        # Should not raise even though the folder is already there.
        self.sortilege.ensure_directories(plan)
        self.assertTrue(mock_unreal.EditorAssetLibrary.does_directory_exist("/Game/Meshes"))


class ExecutePlanHappyPathTests(ExecutorTestBase):
    def test_move_updates_referencer_deps_and_leaves_a_redirector(self):
        mock_unreal.add_asset("/Game/Blueprints/BP_User", "Blueprint",
                               deps=["/Game/Stuff/Rock"])
        assets = [asset("/Game/Stuff/Rock", "StaticMesh")]
        plan = self._plan(assets)
        undo_log = self._undo_log(plan)
        caps = self.sortilege.probe_capabilities()

        results = self.sortilege.execute_plan(plan, caps, undo_log)

        self.assertEqual(results["moved"], [("/Game/Stuff/Rock", "/Game/Meshes/Rock")])
        self.assertEqual(results["failed"], [])

        state = mock_unreal.get_state()
        self.assertIn("/Game/Meshes/Rock", state["assets"])
        self.assertNotIn("/Game/Stuff/Rock", state["assets"])
        self.assertEqual(state["redirectors"]["/Game/Stuff/Rock"], "/Game/Meshes/Rock")
        self.assertEqual(
            state["assets"]["/Game/Blueprints/BP_User"]["deps"],
            ["/Game/Meshes/Rock"],
        )

    def test_successful_move_is_recorded_in_undo_log_immediately(self):
        assets = [
            asset("/Game/Stuff/Rock", "StaticMesh"),
            asset("/Game/Stuff/Wood", "Texture2D"),
        ]
        plan = self._plan(assets)
        undo_log = self._undo_log(plan)
        caps = self.sortilege.probe_capabilities()

        self.sortilege.execute_plan(plan, caps, undo_log)

        self.assertEqual(len(undo_log.moves), 2)
        loaded = self.sortilege.load_undo_log(undo_log.path)
        self.assertEqual(len(loaded["moves"]), 2)


class ExecutePlanCollisionTests(ExecutorTestBase):
    def test_collision_item_fails_without_corrupting_others(self):
        assets = [
            asset("/Game/Stuff/Rock", "StaticMesh"),
            asset("/Game/Stuff/Wood", "Texture2D"),
        ]
        plan = self._plan(assets)
        undo_log = self._undo_log(plan)
        caps = self.sortilege.probe_capabilities()

        # Force a real execution-time collision on the Rock move: occupy its
        # destination AFTER the plan was already built (build_plan's own
        # collision detection can't see this).
        mock_unreal.add_asset("/Game/Meshes/Rock", "StaticMesh")

        results = self.sortilege.execute_plan(plan, caps, undo_log)

        failed_paths = [f[0] for f in results["failed"]]
        moved_paths = [m[0] for m in results["moved"]]
        self.assertIn("/Game/Stuff/Rock", failed_paths)
        self.assertIn("/Game/Stuff/Wood", moved_paths)

        state = mock_unreal.get_state()
        # The colliding item must be untouched -- still at its original path.
        self.assertIn("/Game/Stuff/Rock", state["assets"])
        self.assertNotIn("/Game/Stuff/Rock", state["redirectors"])
        # The other item must have gone through cleanly.
        self.assertIn("/Game/Textures/Wood", state["assets"])
        self.assertEqual(len(undo_log.moves), 1)


class ExecutePlanExceptionResilienceTests(ExecutorTestBase):
    def test_exception_on_one_item_does_not_stop_the_batch(self):
        assets = [
            asset("/Game/Stuff/Rock", "StaticMesh"),
            asset("/Game/Stuff/Wood", "Texture2D"),
        ]
        plan = self._plan(assets)
        undo_log = self._undo_log(plan)
        caps = self.sortilege.probe_capabilities()

        original_rename = mock_unreal.EditorAssetLibrary.rename_asset

        def flaky_rename(src, dst):
            if "Rock" in src:
                raise RuntimeError("simulated engine crash on this asset")
            return original_rename(src, dst)

        mock_unreal.EditorAssetLibrary.rename_asset = staticmethod(flaky_rename)
        try:
            results = self.sortilege.execute_plan(plan, caps, undo_log)
        finally:
            mock_unreal.EditorAssetLibrary.rename_asset = staticmethod(original_rename)

        failed_paths = [f[0] for f in results["failed"]]
        moved_paths = [m[0] for m in results["moved"]]
        self.assertIn("/Game/Stuff/Rock", failed_paths)
        self.assertIn("/Game/Stuff/Wood", moved_paths)
        self.assertIn("simulated engine crash", results["failed"][0][2])


class ExecutePlanGarbageCollectionTests(ExecutorTestBase):
    def test_collect_garbage_called_exactly_once_on_a_25_item_batch(self):
        assets = [asset("/Game/Stuff/Rock%02d" % i, "StaticMesh") for i in range(25)]
        plan = self._plan(assets)
        self.assertEqual(len(plan["moves"]), 25)
        undo_log = self._undo_log(plan)
        caps = self.sortilege.probe_capabilities()
        self.assertTrue(caps.collect_garbage)

        self.sortilege.execute_plan(plan, caps, undo_log)

        self.assertEqual(mock_unreal.get_state()["gc_calls"], 1)

    def test_collect_garbage_called_exactly_twice_on_a_50_item_batch(self):
        assets = [asset("/Game/Stuff/Rock%02d" % i, "StaticMesh") for i in range(50)]
        plan = self._plan(assets)
        self.assertEqual(len(plan["moves"]), 50)
        undo_log = self._undo_log(plan)
        caps = self.sortilege.probe_capabilities()
        self.assertTrue(caps.collect_garbage)

        self.sortilege.execute_plan(plan, caps, undo_log)

        self.assertEqual(mock_unreal.get_state()["gc_calls"], 2)

    def test_collect_garbage_not_called_on_small_batches(self):
        assets = [asset("/Game/Stuff/Rock", "StaticMesh")]
        plan = self._plan(assets)
        undo_log = self._undo_log(plan)
        caps = self.sortilege.probe_capabilities()

        self.sortilege.execute_plan(plan, caps, undo_log)

        self.assertEqual(mock_unreal.get_state()["gc_calls"], 0)


class ExecutePlanProgressTests(ExecutorTestBase):
    def test_progress_callable_invoked_once_per_move(self):
        assets = [
            asset("/Game/Stuff/Rock", "StaticMesh"),
            asset("/Game/Stuff/Wood", "Texture2D"),
        ]
        plan = self._plan(assets)
        undo_log = self._undo_log(plan)
        caps = self.sortilege.probe_capabilities()

        seen = []
        self.sortilege.execute_plan(plan, caps, undo_log, progress=lambda m: seen.append(m["path"]))

        self.assertEqual(len(seen), 2)

    def test_broken_progress_callable_does_not_abort_batch(self):
        assets = [asset("/Game/Stuff/Rock", "StaticMesh")]
        plan = self._plan(assets)
        undo_log = self._undo_log(plan)
        caps = self.sortilege.probe_capabilities()

        def broken_progress(_m):
            raise RuntimeError("progress bar exploded")

        results = self.sortilege.execute_plan(plan, caps, undo_log, progress=broken_progress)
        self.assertEqual(results["moved"], [("/Game/Stuff/Rock", "/Game/Meshes/Rock")])


class ExecutePlanCancellationTests(ExecutorTestBase):
    def test_cancel_via_progress_stops_batch_cleanly(self):
        assets = [
            asset("/Game/Stuff/Rock", "StaticMesh"),
            asset("/Game/Stuff/Wood", "Texture2D"),
            asset("/Game/Stuff/Boom", "SoundWave"),
        ]
        plan = self._plan(assets)
        self.assertEqual(len(plan["moves"]), 3)
        undo_log = self._undo_log(plan)
        caps = self.sortilege.probe_capabilities()

        calls = []

        def cancelling_progress(m):
            calls.append(m["path"])
            if len(calls) == 2:
                raise self.sortilege.SortilegeCancelled("user cancelled")

        results = self.sortilege.execute_plan(
            plan, caps, undo_log, progress=cancelling_progress)

        # Item 1 was moved before the cancel; items 2 and 3 were not.
        self.assertTrue(results.get("cancelled"))
        self.assertEqual(len(results["moved"]), 1)
        self.assertEqual(results["failed"], [])

        # The undo log already durably holds exactly that one move.
        loaded = self.sortilege.load_undo_log(undo_log.path)
        self.assertEqual(len(loaded["moves"]), 1)

    def test_normal_run_has_no_cancelled_flag(self):
        assets = [asset("/Game/Stuff/Rock", "StaticMesh")]
        plan = self._plan(assets)
        undo_log = self._undo_log(plan)
        caps = self.sortilege.probe_capabilities()

        results = self.sortilege.execute_plan(plan, caps, undo_log)

        self.assertFalse(results.get("cancelled", False))


class FixSoftReferencesTests(ExecutorTestBase):
    def test_gated_call_happens_with_correct_old_to_new_map(self):
        mock_unreal.add_asset("/Game/Blueprints/BP_User", "Blueprint",
                               deps=["/Game/Stuff/Rock"])
        assets = [asset("/Game/Stuff/Rock", "StaticMesh")]
        plan = self._plan(assets)
        undo_log = self._undo_log(plan)
        caps = self.sortilege.probe_capabilities()
        self.assertTrue(caps.soft_path_rename)

        results = self.sortilege.execute_plan(plan, caps, undo_log)
        outcome = self.sortilege.fix_soft_references(results, caps)

        self.assertTrue(outcome)
        calls = mock_unreal.get_state()["soft_rename_calls"]
        self.assertEqual(len(calls), 1)
        self.assertEqual(
            calls[0]["map"],
            {"/Game/Stuff/Rock.Rock": "/Game/Meshes/Rock.Rock"},
        )
        self.assertIn("/Game/Blueprints/BP_User", calls[0]["packages"])

    def test_absent_capability_returns_none(self):
        sortilege = helpers.load_sortilege(features={"soft_path_rename": False})
        mock_unreal.add_asset("/Game/Stuff/Rock", "StaticMesh")
        assets = [asset("/Game/Stuff/Rock", "StaticMesh")]
        config = dict(sortilege.CONFIG)
        caps = sortilege.probe_capabilities()
        self.assertFalse(caps.soft_path_rename)
        plan = sortilege.build_plan(assets, config, caps)
        undo_log = sortilege.UndoLog.begin(self.tmp_dir, plan)
        results = sortilege.execute_plan(plan, caps, undo_log)

        outcome = sortilege.fix_soft_references(results, caps)
        self.assertIsNone(outcome)

    def test_queries_both_old_and_new_path_per_moved_pair(self):
        """Regression: fix_soft_references() used to query only the NEW
        (post-move) path via find_package_referencers_for_asset(). The
        packages still holding a stale soft reference are found at the
        OLD path (through the redirector left there) -- the SAME
        orientation cleanup_redirectors() already uses. Pin this with a
        spy on find_package_referencers_for_asset: both the old and the
        new path must be queried for every moved pair, not just the new
        one."""
        assets = [asset("/Game/Stuff/Rock", "StaticMesh")]
        plan = self._plan(assets)
        undo_log = self._undo_log(plan)
        caps = self.sortilege.probe_capabilities()

        results = self.sortilege.execute_plan(plan, caps, undo_log)
        self.assertEqual(results["moved"], [("/Game/Stuff/Rock", "/Game/Meshes/Rock")])

        original = mock_unreal.EditorAssetLibrary.find_package_referencers_for_asset
        queried = []

        def spy(path, *args, **kwargs):
            queried.append(path)
            return original(path, *args, **kwargs)

        mock_unreal.EditorAssetLibrary.find_package_referencers_for_asset = staticmethod(spy)
        try:
            self.sortilege.fix_soft_references(results, caps)
        finally:
            mock_unreal.EditorAssetLibrary.find_package_referencers_for_asset = staticmethod(original)

        self.assertIn("/Game/Stuff/Rock", queried)
        self.assertIn("/Game/Meshes/Rock", queried)

    def test_stale_referencer_still_pointed_at_old_path_lands_in_packages(self):
        """A referencer added AFTER the move with a deliberately stale dep
        on the OLD (now-redirector) path -- simulating a soft reference
        that was never auto-rewritten -- must still end up in the package
        list handed to rename_referencing_soft_object_paths()."""
        assets = [asset("/Game/Stuff/Rock", "StaticMesh")]
        plan = self._plan(assets)
        undo_log = self._undo_log(plan)
        caps = self.sortilege.probe_capabilities()

        results = self.sortilege.execute_plan(plan, caps, undo_log)
        self.assertEqual(results["moved"], [("/Game/Stuff/Rock", "/Game/Meshes/Rock")])

        mock_unreal.add_asset("/Game/Blueprints/BP_Stale", "Blueprint",
                               deps=["/Game/Stuff/Rock"])

        outcome = self.sortilege.fix_soft_references(results, caps)

        self.assertTrue(outcome)
        calls = mock_unreal.get_state()["soft_rename_calls"]
        self.assertEqual(len(calls), 1)
        self.assertIn("/Game/Blueprints/BP_Stale", calls[0]["packages"])


# ---------------------------------------------------------------------------
# P1 -- comprehensive soft-path rewrite. Root-cause fix: find_package_
# referencers_for_asset() is not a reliable index of every SOFT referencer
# on every UEFN build (field report -- see test_redirectors.py's P0
# class for the exact incident). rename_referencing_soft_object_paths()
# must be handed EVERY project package, not just referencer-graph hits,
# so a soft reference gets repointed regardless of whether the
# referencer-graph query happened to surface it.
# ---------------------------------------------------------------------------

class ComprehensiveSoftRewriteTests(ExecutorTestBase):
    def test_comprehensive_scan_includes_packages_outside_the_referencer_graph(self):
        """Two assets with NO relationship at all to the moved asset --
        nothing links them, nothing would ever put them in find_package_
        referencers_for_asset's result -- still show up in the package
        list handed to rename_referencing_soft_object_paths(), proving
        the scope is "every project package", not "every referencer"."""
        mock_unreal.add_asset("/Game/Unrelated/Thing1", "Texture2D")
        mock_unreal.add_asset("/Game/Unrelated/Thing2", "SoundWave")
        assets = [asset("/Game/Stuff/Rock", "StaticMesh")]
        plan = self._plan(assets)
        undo_log = self._undo_log(plan)
        caps = self.sortilege.probe_capabilities()

        results = self.sortilege.execute_plan(plan, caps, undo_log)
        outcome = self.sortilege.fix_soft_references(results, caps)

        self.assertTrue(outcome)
        calls = mock_unreal.get_state()["soft_rename_calls"]
        self.assertEqual(len(calls), 1)
        self.assertIn("/Game/Unrelated/Thing1", calls[0]["packages"])
        self.assertIn("/Game/Unrelated/Thing2", calls[0]["packages"])

    def test_soft_referencer_outside_the_referencer_graph_still_gets_rewritten(self):
        """THE root-cause proof: Spinner_red's ONLY reference to RVB2 is a
        soft one (soft_deps=), which find_package_referencers_for_asset
        can never see (see mock_unreal.py) -- the OLD code's referencer-
        graph-only scan would never have handed Spinner_red to
        rename_referencing_soft_object_paths at all, so its stale soft
        path would survive untouched. The comprehensive scan must reach
        it anyway: after fix_soft_references(), Spinner_red's soft_deps
        entry must point at RVB2's NEW location, not the old one."""
        mock_unreal.add_asset("/Game/Props/Spinner_red", "Blueprint",
                               soft_deps=["/Game/Stuff/RVB2"])
        assets = [asset("/Game/Stuff/RVB2", "StaticMesh")]
        plan = self._plan(assets)
        undo_log = self._undo_log(plan)
        caps = self.sortilege.probe_capabilities()

        results = self.sortilege.execute_plan(plan, caps, undo_log)
        self.assertEqual(results["moved"], [("/Game/Stuff/RVB2", "/Game/Meshes/RVB2")])

        # Pin the premise: today's single referencer query genuinely
        # cannot see Spinner_red's soft reference either end of the move.
        refs_old = mock_unreal.EditorAssetLibrary.find_package_referencers_for_asset(
            "/Game/Stuff/RVB2")
        refs_new = mock_unreal.EditorAssetLibrary.find_package_referencers_for_asset(
            "/Game/Meshes/RVB2")
        self.assertNotIn("/Game/Props/Spinner_red", refs_old)
        self.assertNotIn("/Game/Props/Spinner_red", refs_new)

        outcome = self.sortilege.fix_soft_references(results, caps)

        self.assertTrue(outcome)
        state = mock_unreal.get_state()
        self.assertEqual(
            state["assets"]["/Game/Props/Spinner_red"]["soft_deps"],
            ["/Game/Meshes/RVB2"])

    def test_large_project_chunks_calls_and_is_fail_soft_per_chunk(self):
        """"chunk if needed for very large projects, e.g. batches of a few
        hundred, fail-soft per chunk": 650 unrelated packages plus the
        moved pair must split into multiple rename_referencing_soft_
        object_paths calls, and a single chunk raising must not stop the
        others from still being attempted."""
        for i in range(650):
            mock_unreal.add_asset("/Game/Bulk/Thing%04d" % i, "Texture2D")
        assets = [asset("/Game/Stuff/Rock", "StaticMesh")]
        plan = self._plan(assets)
        undo_log = self._undo_log(plan)
        caps = self.sortilege.probe_capabilities()
        results = self.sortilege.execute_plan(plan, caps, undo_log)

        tools = mock_unreal.AssetToolsHelpers.get_asset_tools()
        original = type(tools).rename_referencing_soft_object_paths
        call_count = [0]

        def flaky(self, packages, asset_redirector_map):
            call_count[0] += 1
            if call_count[0] == 2:
                raise RuntimeError("simulated failure on chunk 2")
            return original(self, packages, asset_redirector_map)

        type(tools).rename_referencing_soft_object_paths = flaky
        try:
            outcome = self.sortilege.fix_soft_references(results, caps)
        finally:
            type(tools).rename_referencing_soft_object_paths = original

        calls = mock_unreal.get_state()["soft_rename_calls"]
        # 650 unrelated + old-redirector-path + new-real-path = 652
        # packages -> exactly 3 chunks of <= 300 each (300, 300, 52).
        self.assertEqual(call_count[0], 3)
        # Chunk 2's call raised BEFORE the real impl ever recorded it, so
        # only chunks 1 and 3 land in soft_rename_calls -- fail-soft per
        # chunk means the loop kept going after chunk 2's exception
        # instead of aborting the remaining chunks.
        self.assertEqual(len(calls), 2)
        self.assertFalse(outcome)


if __name__ == "__main__":
    unittest.main()
