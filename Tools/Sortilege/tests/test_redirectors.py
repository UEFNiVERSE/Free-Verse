"""Tests for sortilege.py's redirector discovery + cleanup, and the
verify pass -- Task 4.

Covers find_redirectors(), cleanup_redirectors(), and verify_results().
These do not exist yet -- this file is expected to fail with
AttributeError until Task 4 implements them.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import helpers
import mock_unreal


class RedirectorTestBase(unittest.TestCase):
    def setUp(self):
        self.sortilege = helpers.load_sortilege()
        mock_unreal.set_project_root("/ProjectX")


class FindRedirectorsTests(RedirectorTestBase):
    def test_finds_redirector_via_is_redirector_primary_path(self):
        mock_unreal.add_asset("/ProjectX/Stuff/Rock", "StaticMesh")
        mock_unreal.EditorAssetLibrary.rename_asset("/ProjectX/Stuff/Rock", "/ProjectX/Meshes/Rock")

        caps = self.sortilege.probe_capabilities()
        found = self.sortilege.find_redirectors(["/ProjectX/Stuff"], caps)

        self.assertEqual(found, ["/ProjectX/Stuff/Rock"])

    def test_scope_limited_to_touched_folders_only(self):
        mock_unreal.add_asset("/ProjectX/Stuff/Rock", "StaticMesh")
        mock_unreal.add_asset("/ProjectX/Untouched/Pebble", "StaticMesh")
        mock_unreal.EditorAssetLibrary.rename_asset("/ProjectX/Stuff/Rock", "/ProjectX/Meshes/Rock")
        mock_unreal.EditorAssetLibrary.rename_asset(
            "/ProjectX/Untouched/Pebble", "/ProjectX/Untouched/Renamed/Pebble")

        caps = self.sortilege.probe_capabilities()
        # Scope only covers /ProjectX/Stuff and /ProjectX/Meshes -- the
        # redirector left behind in /ProjectX/Untouched must never surface.
        found = self.sortilege.find_redirectors(["/ProjectX/Stuff", "/ProjectX/Meshes"], caps)

        self.assertEqual(found, ["/ProjectX/Stuff/Rock"])
        self.assertNotIn("/ProjectX/Untouched/Pebble", found)

    def test_falls_back_to_registry_when_is_redirector_missing(self):
        mock_unreal.add_asset("/ProjectX/Stuff/Rock", "StaticMesh")
        mock_unreal.EditorAssetLibrary.rename_asset("/ProjectX/Stuff/Rock", "/ProjectX/Meshes/Rock")

        caps = self.sortilege.probe_capabilities()
        original = mock_unreal.AssetData.is_redirector
        del mock_unreal.AssetData.is_redirector
        try:
            found = self.sortilege.find_redirectors(["/ProjectX/Stuff"], caps)
        finally:
            mock_unreal.AssetData.is_redirector = original

        self.assertEqual(found, ["/ProjectX/Stuff/Rock"])


class CleanupRedirectorsManualRecipeTests(RedirectorTestBase):
    def setUp(self):
        super(CleanupRedirectorsManualRecipeTests, self).setUp()
        self.sortilege = helpers.load_sortilege(features={"fix_up_redirectors": False})
        mock_unreal.set_project_root("/ProjectX")

    def test_resaves_stale_referencer_then_deletes(self):
        mock_unreal.add_asset("/ProjectX/Stuff/Rock", "StaticMesh")
        mock_unreal.EditorAssetLibrary.rename_asset("/ProjectX/Stuff/Rock", "/ProjectX/Meshes/Rock")
        # Referencer added after the move with a deliberately stale dep --
        # simulates a package cached before the move, never resaved.
        mock_unreal.add_asset("/ProjectX/Blueprints/BP_User", "Blueprint",
                               deps=["/ProjectX/Stuff/Rock"])

        caps = self.sortilege.probe_capabilities()
        self.assertFalse(caps.fix_up_redirectors)

        result = self.sortilege.cleanup_redirectors(["/ProjectX/Stuff", "/ProjectX/Meshes"], caps)

        self.assertEqual(result["fixed"], ["/ProjectX/Stuff/Rock"])
        self.assertEqual(result["remaining"], [])
        self.assertEqual(result["method"], "manual")

        state = mock_unreal.get_state()
        self.assertNotIn("/ProjectX/Stuff/Rock", state["redirectors"])
        self.assertIn("/ProjectX/Blueprints/BP_User", state["saved"])
        self.assertEqual(
            state["assets"]["/ProjectX/Blueprints/BP_User"]["deps"],
            ["/ProjectX/Meshes/Rock"],
        )

    def test_still_referenced_redirector_survives_to_remaining_with_why(self):
        mock_unreal.add_asset("/ProjectX/Stuff/Rock", "StaticMesh")
        mock_unreal.EditorAssetLibrary.rename_asset("/ProjectX/Stuff/Rock", "/ProjectX/Meshes/Rock")
        mock_unreal.add_asset("/ProjectX/Blueprints/BP_Broken", "Blueprint",
                               deps=["/ProjectX/Stuff/Rock"])

        # Simulate a referencer package that cannot be loaded (missing,
        # corrupted, whatever) -- load_asset returns None for it, so it
        # can never be resaved and the redirector must survive.
        original_load = mock_unreal.EditorAssetLibrary.load_asset

        def flaky_load(path):
            if "BP_Broken" in path:
                return None
            return original_load(path)

        mock_unreal.EditorAssetLibrary.load_asset = staticmethod(flaky_load)
        try:
            caps = self.sortilege.probe_capabilities()
            result = self.sortilege.cleanup_redirectors(["/ProjectX/Stuff", "/ProjectX/Meshes"], caps)
        finally:
            mock_unreal.EditorAssetLibrary.load_asset = staticmethod(original_load)

        self.assertEqual(result["fixed"], [])
        self.assertEqual(len(result["remaining"]), 1)
        path, why = result["remaining"][0]
        self.assertEqual(path, "/ProjectX/Stuff/Rock")
        self.assertIn("still referenced by", why)
        self.assertIn("BP_Broken", why)

        state = mock_unreal.get_state()
        self.assertIn("/ProjectX/Stuff/Rock", state["redirectors"])

    def test_collect_garbage_called_exactly_once_for_twelve_redirectors(self):
        for i in range(12):
            path = "/ProjectX/Stuff/Rock%02d" % i
            mock_unreal.add_asset(path, "StaticMesh")
            mock_unreal.EditorAssetLibrary.rename_asset(path, "/ProjectX/Meshes/Rock%02d" % i)

        caps = self.sortilege.probe_capabilities()
        self.assertTrue(caps.collect_garbage)

        result = self.sortilege.cleanup_redirectors(["/ProjectX/Stuff", "/ProjectX/Meshes"], caps)

        self.assertEqual(len(result["fixed"]), 12)
        self.assertEqual(mock_unreal.get_state()["gc_calls"], 1)

    def test_collect_garbage_called_exactly_twice_for_twenty_redirectors(self):
        for i in range(20):
            path = "/ProjectX/Stuff/Rock%02d" % i
            mock_unreal.add_asset(path, "StaticMesh")
            mock_unreal.EditorAssetLibrary.rename_asset(path, "/ProjectX/Meshes/Rock%02d" % i)

        caps = self.sortilege.probe_capabilities()

        result = self.sortilege.cleanup_redirectors(["/ProjectX/Stuff", "/ProjectX/Meshes"], caps)

        self.assertEqual(len(result["fixed"]), 20)
        self.assertEqual(mock_unreal.get_state()["gc_calls"], 2)

    def test_collect_garbage_not_called_for_fewer_than_ten_redirectors(self):
        for i in range(5):
            path = "/ProjectX/Stuff/Rock%02d" % i
            mock_unreal.add_asset(path, "StaticMesh")
            mock_unreal.EditorAssetLibrary.rename_asset(path, "/ProjectX/Meshes/Rock%02d" % i)

        caps = self.sortilege.probe_capabilities()

        result = self.sortilege.cleanup_redirectors(["/ProjectX/Stuff", "/ProjectX/Meshes"], caps)

        self.assertEqual(len(result["fixed"]), 5)
        self.assertEqual(mock_unreal.get_state()["gc_calls"], 0)

    def test_no_redirectors_in_scope_is_a_no_op(self):
        caps = self.sortilege.probe_capabilities()
        result = self.sortilege.cleanup_redirectors(["/ProjectX/Empty"], caps)
        self.assertEqual(result["fixed"], [])
        self.assertEqual(result["remaining"], [])


class CleanupRedirectorsBatchedResaveTests(RedirectorTestBase):
    """The manual recipe must resave each UNIQUE referencing package
    exactly ONCE for the whole batch, instead of once per redirector that
    package happens to touch -- this is the fix for the field-observed
    "Cleaning up redirectors 35/170" multi-minute stall."""

    def setUp(self):
        super(CleanupRedirectorsBatchedResaveTests, self).setUp()
        self.sortilege = helpers.load_sortilege(features={"fix_up_redirectors": False})
        mock_unreal.set_project_root("/ProjectX")

    def test_shared_referencer_resaved_exactly_once_not_once_per_redirector(self):
        for name in ("RockA", "RockB", "RockC"):
            mock_unreal.add_asset("/ProjectX/Stuff/%s" % name, "StaticMesh")
            mock_unreal.EditorAssetLibrary.rename_asset(
                "/ProjectX/Stuff/%s" % name, "/ProjectX/Meshes/%s" % name)
        # Added AFTER all 3 moves -- a package cached before the moves,
        # never resaved, so all 3 deps stay stale literal OLD paths
        # (matches test_resaves_stale_referencer_then_deletes's pattern).
        mock_unreal.add_asset("/ProjectX/Blueprints/BP_Multi", "Blueprint", deps=[
            "/ProjectX/Stuff/RockA", "/ProjectX/Stuff/RockB", "/ProjectX/Stuff/RockC"])
        redirector_paths = {
            "/ProjectX/Stuff/RockA", "/ProjectX/Stuff/RockB", "/ProjectX/Stuff/RockC"}

        # mock_unreal's save_loaded_asset resolves a referencer's FULL
        # deps list in one shot, so a plain shared-referencer fixture
        # would show only 1 resave under EITHER algorithm -- resaving for
        # the first redirector processed incidentally also fixes the
        # other two deps, masking the exact bug this rewrite targets: the
        # OLD per-redirector loop calls find_package_referencers_for_
        # asset(p, True) -- and then resaves whatever it finds --
        # independently for EACH redirector, a real query+load+save cost
        # even on a batch that nets out to a no-op. Stub the referencer
        # query to keep reporting BP_Multi as a referencer of all 3
        # redirectors (mirrors a real editor whose asset-registry
        # dependency cache hasn't caught up to an in-memory-only fix yet)
        # so the test isolates the ALGORITHM's own call pattern instead of
        # the mock's optimistic auto-resolution.
        original_find = mock_unreal.EditorAssetLibrary.find_package_referencers_for_asset

        def _find_stub(path, load_assets_to_confirm=False):
            if path in redirector_paths:
                if load_assets_to_confirm:
                    return ["/ProjectX/Blueprints/BP_Multi"]
                return []
            return original_find(path, load_assets_to_confirm)

        mock_unreal.EditorAssetLibrary.find_package_referencers_for_asset = staticmethod(_find_stub)
        try:
            caps = self.sortilege.probe_capabilities()
            self.assertFalse(caps.fix_up_redirectors)
            result = self.sortilege.cleanup_redirectors(
                ["/ProjectX/Stuff", "/ProjectX/Meshes"], caps)
        finally:
            mock_unreal.EditorAssetLibrary.find_package_referencers_for_asset = staticmethod(original_find)

        self.assertEqual(sorted(result["fixed"]), sorted(redirector_paths))
        self.assertEqual(result["remaining"], [])

        saved_count = mock_unreal.get_state()["saved"].count("/ProjectX/Blueprints/BP_Multi")
        self.assertEqual(saved_count, 1)

    def test_outcome_parity_with_pre_batch_algorithm_on_mixed_fixture(self):
        # 2 redirectors share a referencer that resaves cleanly; a 3rd has
        # its own referencer that can never load, so it must survive.
        # These exact {fixed, remaining} sets were confirmed against the
        # pre-batch algorithm on this identical fixture -- the outcome
        # must be byte-identical after this change; only the resave
        # COUNT and wall-clock are allowed to differ.
        for name in ("RockA", "RockB", "RockC"):
            mock_unreal.add_asset("/ProjectX/Stuff/%s" % name, "StaticMesh")
            mock_unreal.EditorAssetLibrary.rename_asset(
                "/ProjectX/Stuff/%s" % name, "/ProjectX/Meshes/%s" % name)
        mock_unreal.add_asset("/ProjectX/Blueprints/BP_Multi", "Blueprint",
                               deps=["/ProjectX/Stuff/RockA", "/ProjectX/Stuff/RockB"])
        mock_unreal.add_asset("/ProjectX/Blueprints/BP_Broken", "Blueprint",
                               deps=["/ProjectX/Stuff/RockC"])

        original_load = mock_unreal.EditorAssetLibrary.load_asset

        def flaky_load(path):
            if "BP_Broken" in path:
                return None
            return original_load(path)

        mock_unreal.EditorAssetLibrary.load_asset = staticmethod(flaky_load)
        try:
            caps = self.sortilege.probe_capabilities()
            result = self.sortilege.cleanup_redirectors(
                ["/ProjectX/Stuff", "/ProjectX/Meshes"], caps)
        finally:
            mock_unreal.EditorAssetLibrary.load_asset = staticmethod(original_load)

        self.assertEqual(
            sorted(result["fixed"]),
            sorted(["/ProjectX/Stuff/RockA", "/ProjectX/Stuff/RockB"]))
        self.assertEqual(result["remaining"], [
            ("/ProjectX/Stuff/RockC",
             "still referenced by: /ProjectX/Blueprints/BP_Broken"),
        ])
        self.assertEqual(result["method"], "manual")

    def test_all_resaves_complete_before_any_delete_starts(self):
        # 3 INDEPENDENT redirectors, each with its own separate referencer
        # (no sharing at all) -- the old per-redirector loop interleaves
        # save/delete/save/delete/save/delete; the batched algorithm must
        # do every save first, then every delete.
        for i, name in enumerate(("RockA", "RockB", "RockC")):
            mock_unreal.add_asset("/ProjectX/Stuff/%s" % name, "StaticMesh")
            mock_unreal.EditorAssetLibrary.rename_asset(
                "/ProjectX/Stuff/%s" % name, "/ProjectX/Meshes/%s" % name)
            mock_unreal.add_asset("/ProjectX/Blueprints/BP_Ref%d" % i, "Blueprint",
                                   deps=["/ProjectX/Stuff/%s" % name])

        trail = []
        original_save = mock_unreal.EditorAssetLibrary.save_loaded_asset
        original_delete = mock_unreal.EditorAssetLibrary.delete_asset

        def spy_save(asset, only_if_is_dirty=True):
            trail.append(("save", asset.path))
            return original_save(asset, only_if_is_dirty=only_if_is_dirty)

        def spy_delete(path):
            trail.append(("delete", path))
            return original_delete(path)

        mock_unreal.EditorAssetLibrary.save_loaded_asset = staticmethod(spy_save)
        mock_unreal.EditorAssetLibrary.delete_asset = staticmethod(spy_delete)
        try:
            caps = self.sortilege.probe_capabilities()
            result = self.sortilege.cleanup_redirectors(
                ["/ProjectX/Stuff", "/ProjectX/Meshes"], caps)
        finally:
            mock_unreal.EditorAssetLibrary.save_loaded_asset = staticmethod(original_save)
            mock_unreal.EditorAssetLibrary.delete_asset = staticmethod(original_delete)

        self.assertEqual(len(result["fixed"]), 3)
        kinds = [kind for kind, _path in trail]
        self.assertIn("save", kinds)
        self.assertIn("delete", kinds)
        last_save_index = max(i for i, k in enumerate(kinds) if k == "save")
        first_delete_index = min(i for i, k in enumerate(kinds) if k == "delete")
        self.assertLess(last_save_index, first_delete_index, kinds)

    def test_progress_hook_fires_during_both_resave_and_delete_phases(self):
        # 10 redirectors, but only 5 UNIQUE referencer packages (each one
        # covers 2 of the 10) -- M (referencers) != N (redirectors), so
        # the resave-phase's (5, 5) tick and the delete-phase's (5, 10) /
        # (10, 10) ticks are distinguishable by their own "total".
        for i in range(10):
            path = "/ProjectX/Stuff/Rock%d" % i
            mock_unreal.add_asset(path, "StaticMesh")
            mock_unreal.EditorAssetLibrary.rename_asset(path, "/ProjectX/Meshes/Rock%d" % i)
        for i in range(5):
            mock_unreal.add_asset("/ProjectX/Blueprints/BP_Ref%d" % i, "Blueprint", deps=[
                "/ProjectX/Stuff/Rock%d" % (2 * i), "/ProjectX/Stuff/Rock%d" % (2 * i + 1)])

        caps = self.sortilege.probe_capabilities()
        self.assertFalse(caps.fix_up_redirectors)
        calls = []
        result = self.sortilege.cleanup_redirectors(
            ["/ProjectX/Stuff", "/ProjectX/Meshes"], caps,
            progress_hook=lambda i, n: calls.append((i, n)))

        self.assertEqual(len(result["fixed"]), 10)
        self.assertIn((5, 5), calls)    # resave phase: 5/5 unique referencers
        self.assertIn((5, 10), calls)   # delete phase: 5/10 redirectors
        self.assertIn((10, 10), calls)  # delete phase: 10/10 redirectors

    def test_disable_gc_suppresses_both_resave_and_delete_phase_gc(self):
        # 12 redirectors, each with its OWN unique referencer (12 unique
        # packages to resave) -- both the resave-phase and delete-phase
        # every-10 thresholds would fire if gc_enabled weren't False.
        for i in range(12):
            path = "/ProjectX/Stuff/Rock%02d" % i
            mock_unreal.add_asset(path, "StaticMesh")
            mock_unreal.EditorAssetLibrary.rename_asset(path, "/ProjectX/Meshes/Rock%02d" % i)
            mock_unreal.add_asset("/ProjectX/Blueprints/BP_Ref%02d" % i, "Blueprint",
                                   deps=[path])

        caps = self.sortilege.probe_capabilities()
        result = self.sortilege.cleanup_redirectors(
            ["/ProjectX/Stuff", "/ProjectX/Meshes"], caps, gc_enabled=False)

        self.assertEqual(len(result["fixed"]), 12)
        self.assertEqual(mock_unreal.get_state()["gc_calls"], 0)

    def test_collect_garbage_fires_independently_in_each_phase(self):
        # Same 12-unique-referencer fixture, GC left at its default
        # (enabled): 1 GC from the resave phase (its 10th unique
        # referencer) + 1 GC from the delete phase (its 10th redirector)
        # = 2 total -- the two counters are independent of each other.
        for i in range(12):
            path = "/ProjectX/Stuff/Rock%02d" % i
            mock_unreal.add_asset(path, "StaticMesh")
            mock_unreal.EditorAssetLibrary.rename_asset(path, "/ProjectX/Meshes/Rock%02d" % i)
            mock_unreal.add_asset("/ProjectX/Blueprints/BP_Ref%02d" % i, "Blueprint",
                                   deps=[path])

        caps = self.sortilege.probe_capabilities()
        result = self.sortilege.cleanup_redirectors(
            ["/ProjectX/Stuff", "/ProjectX/Meshes"], caps)

        self.assertEqual(len(result["fixed"]), 12)
        self.assertEqual(mock_unreal.get_state()["gc_calls"], 2)


class CleanupRedirectorsFixupPathTests(RedirectorTestBase):
    def test_fixup_path_used_when_capability_present(self):
        mock_unreal.add_asset("/ProjectX/Stuff/Rock", "StaticMesh")
        mock_unreal.EditorAssetLibrary.rename_asset("/ProjectX/Stuff/Rock", "/ProjectX/Meshes/Rock")
        mock_unreal.add_asset("/ProjectX/Blueprints/BP_User", "Blueprint",
                               deps=["/ProjectX/Stuff/Rock"])

        caps = self.sortilege.probe_capabilities()
        self.assertTrue(caps.fix_up_redirectors)

        result = self.sortilege.cleanup_redirectors(["/ProjectX/Stuff", "/ProjectX/Meshes"], caps)

        self.assertEqual(result["fixed"], ["/ProjectX/Stuff/Rock"])
        self.assertEqual(result["method"], "fix_up_redirectors")
        state = mock_unreal.get_state()
        self.assertNotIn("/ProjectX/Stuff/Rock", state["redirectors"])


class VerifyResultsTests(RedirectorTestBase):
    def test_detects_deliberately_missing_dest(self):
        results = {"moved": [("/ProjectX/Stuff/Rock", "/ProjectX/Meshes/Rock")], "failed": []}
        caps = self.sortilege.probe_capabilities()

        out = self.sortilege.verify_results(results, ["/ProjectX/Stuff", "/ProjectX/Meshes"], caps)

        self.assertFalse(out["ok"])
        self.assertIn("/ProjectX/Meshes/Rock", out["missing"])

    def test_detects_leftover_redirector_but_does_not_fail_ok(self):
        mock_unreal.add_asset("/ProjectX/Stuff/Rock", "StaticMesh")
        mock_unreal.EditorAssetLibrary.rename_asset("/ProjectX/Stuff/Rock", "/ProjectX/Meshes/Rock")
        results = {"moved": [("/ProjectX/Stuff/Rock", "/ProjectX/Meshes/Rock")], "failed": []}
        caps = self.sortilege.probe_capabilities()

        out = self.sortilege.verify_results(results, ["/ProjectX/Stuff", "/ProjectX/Meshes"], caps)

        self.assertIn("/ProjectX/Stuff/Rock", out["leftover_redirectors"])
        self.assertTrue(out["ok"])
        self.assertEqual(out["missing"], [])
        self.assertEqual(out["old_paths_alive"], [])

    def test_ok_true_on_fully_clean_run(self):
        mock_unreal.add_asset("/ProjectX/Stuff/Rock", "StaticMesh")
        mock_unreal.EditorAssetLibrary.rename_asset("/ProjectX/Stuff/Rock", "/ProjectX/Meshes/Rock")
        results = {"moved": [("/ProjectX/Stuff/Rock", "/ProjectX/Meshes/Rock")], "failed": []}
        caps = self.sortilege.probe_capabilities()

        self.sortilege.cleanup_redirectors(["/ProjectX/Stuff", "/ProjectX/Meshes"], caps)
        out = self.sortilege.verify_results(results, ["/ProjectX/Stuff", "/ProjectX/Meshes"], caps)

        self.assertTrue(out["ok"])
        self.assertEqual(out["missing"], [])
        self.assertEqual(out["old_paths_alive"], [])
        self.assertEqual(out["leftover_redirectors"], [])
        self.assertEqual(out["referencer_spot_checks"], 1)
        self.assertEqual(out["broken_soft_refs"], [])

    def test_detects_old_path_still_alive_as_a_real_asset(self):
        # Simulate corruption: the move "succeeded" per results, but the old
        # path was never actually vacated (still a real, non-redirector
        # asset there) -- a genuine verify failure.
        mock_unreal.add_asset("/ProjectX/Stuff/Rock", "StaticMesh")
        mock_unreal.add_asset("/ProjectX/Meshes/Rock", "StaticMesh")
        results = {"moved": [("/ProjectX/Stuff/Rock", "/ProjectX/Meshes/Rock")], "failed": []}
        caps = self.sortilege.probe_capabilities()

        out = self.sortilege.verify_results(results, ["/ProjectX/Stuff", "/ProjectX/Meshes"], caps)

        self.assertFalse(out["ok"])
        self.assertIn("/ProjectX/Stuff/Rock", out["old_paths_alive"])


# ---------------------------------------------------------------------------
# P0 -- CONSERVATIVE_REDIRECTORS: a safety net for cleanup_redirectors'
# delete decision. Field report: a live UEFN sort moved /PremFN_1v1/RVB2
# (leaving a redirector) and moved /PremFN_1v1/GoGoatedTutorial the same
# way; cleanup_redirectors deleted BOTH redirectors because find_package_
# referencers_for_asset reported no referencers -- but /PremFN_1v1/Props/
# Spinner_red and /PremFN_1v1/Props/SPINNR_WHEEL still SOFT-referenced
# those old paths, and that reference broke the instant the redirector
# was gone ("soft references a missing package"). These tests reproduce
# that exact gap against the mock's own soft_deps modeling (see
# add_asset()/get_referencers() in mock_unreal.py) and prove the
# conservative double-check closes it without breaking the safe case.
# ---------------------------------------------------------------------------

class ConservativeRedirectorDeletionTests(RedirectorTestBase):
    """fix_up_redirectors OFF forces the manual recipe -- the "primary,
    real path today" per cleanup_redirectors' own docstring (no shipped
    engine exposes a real fix-up-redirectors Python API; see
    CleanupRedirectorsManualRecipeTests above for the same convention).
    The mock's fix_up_redirectors path is an unconditional, always-
    trusted delete (real engine semantics for an API that, when it
    exists, does its own resave+cleanup atomically) -- it would delete
    every redirector in this file's fixtures before the manual recipe's
    conservative delete-decision ever ran."""

    def setUp(self):
        super(ConservativeRedirectorDeletionTests, self).setUp()
        self.sortilege = helpers.load_sortilege(features={"fix_up_redirectors": False})
        mock_unreal.set_project_root("/ProjectX")

    def _soft_only_referenced_fixture(self):
        """RVB2 moves (leaving a redirector at the OLD path). Spinner_red's
        ONLY reference to RVB2 is a soft one, on that OLD path --
        find_package_referencers_for_asset() must never see this (it only
        ever scans `deps`, see mock_unreal.py); only AssetRegistry.
        get_referencers() (hard+soft) can."""
        mock_unreal.add_asset("/ProjectX/Stuff/RVB2", "StaticMesh")
        mock_unreal.EditorAssetLibrary.rename_asset(
            "/ProjectX/Stuff/RVB2", "/ProjectX/Meshes/RVB2")
        mock_unreal.add_asset("/ProjectX/Props/Spinner_red", "Blueprint",
                               soft_deps=["/ProjectX/Stuff/RVB2"])

    def test_fixture_premise_find_package_referencers_for_asset_misses_it(self):
        """Pin the fixture's own premise before testing the fix built on
        top of it: today's single referencer query genuinely cannot see
        Spinner_red's soft reference."""
        self._soft_only_referenced_fixture()
        refs = mock_unreal.EditorAssetLibrary.find_package_referencers_for_asset(
            "/ProjectX/Stuff/RVB2", False)
        self.assertEqual(refs, [])

    def test_conservative_default_keeps_the_still_soft_referenced_redirector(self):
        self._soft_only_referenced_fixture()
        caps = self.sortilege.probe_capabilities()
        self.assertTrue(caps.referencer_query)
        self.assertTrue(self.sortilege.CONFIG["CONSERVATIVE_REDIRECTORS"])

        result = self.sortilege.cleanup_redirectors(
            ["/ProjectX/Stuff", "/ProjectX/Meshes"], caps)

        self.assertEqual(result["fixed"], [])
        self.assertEqual(len(result["remaining"]), 1)
        path, why = result["remaining"][0]
        self.assertEqual(path, "/ProjectX/Stuff/RVB2")
        self.assertIn("kept", why.lower())
        state = mock_unreal.get_state()
        self.assertIn("/ProjectX/Stuff/RVB2", state["redirectors"])

    def test_conservative_off_reproduces_the_original_deletion_bug(self):
        """RED->GREEN proof: with CONSERVATIVE_REDIRECTORS explicitly
        turned off, the exact field-observed bug reproduces -- the old
        single-check criterion (find_package_referencers_for_asset only)
        deletes a redirector a different asset still soft-references,
        which is precisely what broke Spinner_red's reference live."""
        self.sortilege = helpers.load_sortilege(
            features={"fix_up_redirectors": False},
            config_overrides={"CONSERVATIVE_REDIRECTORS": False})
        mock_unreal.set_project_root("/ProjectX")
        self._soft_only_referenced_fixture()
        caps = self.sortilege.probe_capabilities()

        result = self.sortilege.cleanup_redirectors(
            ["/ProjectX/Stuff", "/ProjectX/Meshes"], caps)

        self.assertEqual(result["fixed"], ["/ProjectX/Stuff/RVB2"])
        self.assertEqual(result["remaining"], [])
        state = mock_unreal.get_state()
        self.assertNotIn("/ProjectX/Stuff/RVB2", state["redirectors"])

    def test_kept_when_get_referencers_capability_is_unavailable(self):
        """No way to double-check at all on this build -- conservative
        mode still refuses to trust a single check that might be blind."""
        self.sortilege = helpers.load_sortilege(
            features={"dependency_query": False, "fix_up_redirectors": False})
        mock_unreal.set_project_root("/ProjectX")
        self._soft_only_referenced_fixture()
        caps = self.sortilege.probe_capabilities()
        self.assertFalse(caps.referencer_query)
        self.assertTrue(self.sortilege.CONFIG["CONSERVATIVE_REDIRECTORS"])

        result = self.sortilege.cleanup_redirectors(
            ["/ProjectX/Stuff", "/ProjectX/Meshes"], caps)

        self.assertEqual(result["fixed"], [])
        self.assertEqual(len(result["remaining"]), 1)
        self.assertEqual(result["remaining"][0][0], "/ProjectX/Stuff/RVB2")
        state = mock_unreal.get_state()
        self.assertIn("/ProjectX/Stuff/RVB2", state["redirectors"])

    def test_get_referencers_raising_also_keeps_the_redirector(self):
        """Either query raising is treated exactly like "found a
        referencer" -- conservative means conservative."""
        self._soft_only_referenced_fixture()
        registry = mock_unreal.AssetRegistryHelpers.get_asset_registry()
        original = mock_unreal.AssetRegistry.get_referencers

        def boom(self, package_name, options=None):
            raise RuntimeError("simulated registry hiccup")

        mock_unreal.AssetRegistry.get_referencers = boom
        try:
            caps = self.sortilege.probe_capabilities()
            result = self.sortilege.cleanup_redirectors(
                ["/ProjectX/Stuff", "/ProjectX/Meshes"], caps)
        finally:
            mock_unreal.AssetRegistry.get_referencers = original

        self.assertEqual(result["fixed"], [])
        self.assertEqual(len(result["remaining"]), 1)
        self.assertEqual(result["remaining"][0][0], "/ProjectX/Stuff/RVB2")

    def test_genuinely_unreferenced_redirector_still_deleted(self):
        """Parity: the safe case still works -- conservative mode adds a
        double-check, it does not add caution where none is warranted."""
        mock_unreal.add_asset("/ProjectX/Stuff/Lonely", "StaticMesh")
        mock_unreal.EditorAssetLibrary.rename_asset(
            "/ProjectX/Stuff/Lonely", "/ProjectX/Meshes/Lonely")
        caps = self.sortilege.probe_capabilities()
        self.assertTrue(caps.referencer_query)

        result = self.sortilege.cleanup_redirectors(
            ["/ProjectX/Stuff", "/ProjectX/Meshes"], caps)

        self.assertEqual(result["fixed"], ["/ProjectX/Stuff/Lonely"])
        self.assertEqual(result["remaining"], [])

    def test_hard_referenced_redirector_still_kept_for_the_original_reason(self):
        """Parity: a plain hard-referenced (still-in-use) redirector keeps
        reporting the original "still referenced by" reason, not the new
        conservative "possible soft reference" one -- the two keep-paths
        stay distinguishable in the report."""
        mock_unreal.add_asset("/ProjectX/Stuff/Rock", "StaticMesh")
        mock_unreal.EditorAssetLibrary.rename_asset(
            "/ProjectX/Stuff/Rock", "/ProjectX/Meshes/Rock")
        original_load = mock_unreal.EditorAssetLibrary.load_asset

        def flaky_load(path):
            if "BP_Broken" in path:
                return None
            return original_load(path)

        mock_unreal.add_asset("/ProjectX/Blueprints/BP_Broken", "Blueprint",
                               deps=["/ProjectX/Stuff/Rock"])
        mock_unreal.EditorAssetLibrary.load_asset = staticmethod(flaky_load)
        try:
            caps = self.sortilege.probe_capabilities()
            result = self.sortilege.cleanup_redirectors(
                ["/ProjectX/Stuff", "/ProjectX/Meshes"], caps)
        finally:
            mock_unreal.EditorAssetLibrary.load_asset = staticmethod(original_load)

        self.assertEqual(result["fixed"], [])
        self.assertEqual(len(result["remaining"]), 1)
        path, why = result["remaining"][0]
        self.assertEqual(path, "/ProjectX/Stuff/Rock")
        self.assertIn("still referenced by", why)
        self.assertIn("BP_Broken", why)


# ---------------------------------------------------------------------------
# P2 -- verify_results must DETECT a broken soft reference: some package
# still soft-references an OLD path that no longer resolves at all (no
# redirector, no asset). With P0+P1 in place this should never actually
# happen in a real run; these tests prove the check itself works and
# would catch a residual case.
# ---------------------------------------------------------------------------

class BrokenSoftReferenceDetectionTests(RedirectorTestBase):
    def test_detects_broken_soft_reference_when_old_path_is_entirely_gone(self):
        mock_unreal.add_asset("/ProjectX/Stuff/RVB2", "StaticMesh")
        mock_unreal.EditorAssetLibrary.rename_asset(
            "/ProjectX/Stuff/RVB2", "/ProjectX/Meshes/RVB2")
        # Simulate the residual case: the redirector is gone entirely (no
        # asset, no redirector left at the old path) despite a surviving
        # soft reference -- exactly the state a broken reference leaves.
        mock_unreal.EditorAssetLibrary.delete_asset("/ProjectX/Stuff/RVB2")
        mock_unreal.add_asset("/ProjectX/Props/Spinner_red", "Blueprint",
                               soft_deps=["/ProjectX/Stuff/RVB2"])
        results = {"moved": [("/ProjectX/Stuff/RVB2", "/ProjectX/Meshes/RVB2")], "failed": []}
        caps = self.sortilege.probe_capabilities()
        self.assertTrue(caps.referencer_query)

        out = self.sortilege.verify_results(
            results, ["/ProjectX/Stuff", "/ProjectX/Meshes"], caps)

        self.assertFalse(out["ok"])
        self.assertIn(
            ("/ProjectX/Props/Spinner_red", "/ProjectX/Stuff/RVB2"),
            out["broken_soft_refs"])

    def test_broken_soft_refs_empty_on_a_clean_run_where_the_referencer_was_fixed(self):
        mock_unreal.add_asset("/ProjectX/Stuff/RVB2", "StaticMesh")
        mock_unreal.EditorAssetLibrary.rename_asset(
            "/ProjectX/Stuff/RVB2", "/ProjectX/Meshes/RVB2")
        mock_unreal.EditorAssetLibrary.delete_asset("/ProjectX/Stuff/RVB2")
        # No referencer at all this time -- nothing broken.
        results = {"moved": [("/ProjectX/Stuff/RVB2", "/ProjectX/Meshes/RVB2")], "failed": []}
        caps = self.sortilege.probe_capabilities()

        out = self.sortilege.verify_results(
            results, ["/ProjectX/Stuff", "/ProjectX/Meshes"], caps)

        self.assertTrue(out["ok"])
        self.assertEqual(out["broken_soft_refs"], [])

    def test_soft_reference_through_a_surviving_redirector_is_not_broken(self):
        """A leftover (not-yet-cleaned) redirector still resolves a soft
        reference correctly -- one extra hop, not a break. Only a
        genuinely GONE old path (no redirector, no asset) counts."""
        mock_unreal.add_asset("/ProjectX/Stuff/RVB2", "StaticMesh")
        mock_unreal.EditorAssetLibrary.rename_asset(
            "/ProjectX/Stuff/RVB2", "/ProjectX/Meshes/RVB2")
        mock_unreal.add_asset("/ProjectX/Props/Spinner_red", "Blueprint",
                               soft_deps=["/ProjectX/Stuff/RVB2"])
        results = {"moved": [("/ProjectX/Stuff/RVB2", "/ProjectX/Meshes/RVB2")], "failed": []}
        caps = self.sortilege.probe_capabilities()

        out = self.sortilege.verify_results(
            results, ["/ProjectX/Stuff", "/ProjectX/Meshes"], caps)

        self.assertEqual(out["broken_soft_refs"], [])
        self.assertIn("/ProjectX/Stuff/RVB2", out["leftover_redirectors"])
        self.assertTrue(out["ok"])


if __name__ == "__main__":
    unittest.main()
