"""Tests for the post-flight empty-folder sweep.

cleanup_empty_folders() is upgraded from "delete direct source parents,
return a discarded list, default OFF" to a real post-flight step: source
folders PLUS all ancestors up to (never including) the content roots,
deepest-first, deleted only when genuinely empty (leftover redirectors
count as content), never touching roots/protected/excluded/out-of-root
folders, returning {"removed": [...], "kept": [(path, reason)]} that is
attached to results["empty_folders"], surfaced in the summary report and
the GUI results bar, and ON by default (CLEAN_EMPTY_FOLDERS: True).
RED-first TDD.
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


class EmptyFolderTestBase(unittest.TestCase):
    def setUp(self):
        self.sortilege = helpers.load_sortilege()
        self.tmp_dir = tempfile.mkdtemp(prefix="sortilege_test_")
        self.sortilege.CONFIG["LOG_DIR"] = self.tmp_dir

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _apply(self, assets, config_overrides=None):
        for a in assets:
            mock_unreal.add_asset(a["path"], a["class_name"])
        config = dict(self.sortilege.CONFIG)
        if config_overrides:
            config.update(config_overrides)
        caps = self.sortilege.probe_capabilities()
        plan = self.sortilege.build_plan(assets, config, caps)
        undo_log = self.sortilege.UndoLog.begin(self.tmp_dir, plan)
        self.sortilege.execute_plan(plan, caps, undo_log)
        return plan, caps


class NestedShellChainTests(EmptyFolderTestBase):
    def test_nested_shells_all_removed_deepest_first(self):
        """The VFXs/_pack/_material shape: after the one asset moves out
        and its redirector is cleaned, all three nested shells are empty
        and all three go, deepest first (child removal is what makes the
        parent read empty)."""
        assets = [asset("/Game/VFXs/_pack/_material/NS_Boom", "NiagaraSystem")]
        plan, caps = self._apply(assets)
        self.sortilege.cleanup_redirectors(
            ["/Game/VFXs", "/Game/VFX"], caps)

        result = self.sortilege.cleanup_empty_folders(plan, self.sortilege.CONFIG)

        removed = result["removed"]
        self.assertIn("/Game/VFXs/_pack/_material", removed)
        self.assertIn("/Game/VFXs/_pack", removed)
        self.assertIn("/Game/VFXs", removed)
        # Deepest-first order: each child precedes its parent.
        self.assertLess(removed.index("/Game/VFXs/_pack/_material"),
                        removed.index("/Game/VFXs/_pack"))
        self.assertLess(removed.index("/Game/VFXs/_pack"),
                        removed.index("/Game/VFXs"))
        lib = mock_unreal.EditorAssetLibrary
        self.assertFalse(lib.does_directory_exist("/Game/VFXs"))


class SweepSafetyTests(EmptyFolderTestBase):
    def test_folder_holding_leftover_redirector_is_kept_with_reason(self):
        """A leftover redirector is real registry content: its folder
        reads non-empty and survives the sweep, listed in kept."""
        assets = [asset("/Game/Stuff/Rock", "StaticMesh")]
        plan, caps = self._apply(assets)
        # No redirector cleanup: the redirector still squats at
        # /Game/Stuff/Rock.
        state = mock_unreal.get_state()
        self.assertIn("/Game/Stuff/Rock", state["redirectors"])

        result = self.sortilege.cleanup_empty_folders(plan, self.sortilege.CONFIG)

        self.assertNotIn("/Game/Stuff", result["removed"])
        kept = dict(result["kept"])
        self.assertEqual(kept.get("/Game/Stuff"), "not empty")
        self.assertTrue(
            mock_unreal.EditorAssetLibrary.does_directory_exist("/Game/Stuff"))

    def test_excluded_folder_never_deleted(self):
        # Synthetic plan: the sweep must refuse an excluded source even if
        # a move claims to have come from there (belt and braces -- the
        # EXCLUDE list could have changed between plan and sweep).
        mock_unreal.add_folder("/Game/Keep/Sub")
        plan = {"moves": [{"path": "/Game/Keep/Sub/Rock",
                            "dest_folder": "/Game/Meshes",
                            "dest_path": "/Game/Meshes/Rock"}],
                "skips": [], "content_root": "/Game"}
        config = dict(self.sortilege.CONFIG)
        config["EXCLUDE_FOLDERS"] = ["/Game/Keep"]

        result = self.sortilege.cleanup_empty_folders(plan, config)

        self.assertNotIn("/Game/Keep/Sub", result["removed"])
        self.assertNotIn("/Game/Keep", result["removed"])
        kept = dict(result["kept"])
        self.assertEqual(kept.get("/Game/Keep/Sub"), "excluded folder")

    def test_protected_folder_never_deleted(self):
        plan = {"moves": [{"path": "/Game/__ExternalActors__/x/Foo",
                            "dest_folder": "/Game/Meshes",
                            "dest_path": "/Game/Meshes/Foo"}],
                "skips": [], "content_root": "/Game"}

        result = self.sortilege.cleanup_empty_folders(
            plan, self.sortilege.CONFIG)

        self.assertNotIn("/Game/__ExternalActors__/x", result["removed"])
        self.assertNotIn("/Game/__ExternalActors__", result["removed"])
        kept = dict(result["kept"])
        self.assertEqual(kept.get("/Game/__ExternalActors__/x"),
                          "protected system folder")

    def test_content_root_never_a_candidate(self):
        assets = [asset("/Game/Rock", "StaticMesh")]
        plan, caps = self._apply(assets)
        self.sortilege.cleanup_redirectors(["/Game"], caps)

        result = self.sortilege.cleanup_empty_folders(plan, self.sortilege.CONFIG)

        self.assertNotIn("/Game", result["removed"])
        self.assertNotIn("/Game", [p for p, _r in result["kept"]])

    def test_out_of_root_folder_never_deleted(self):
        plan = {"moves": [{"path": "/Elsewhere/Sub/Foo",
                            "dest_folder": "/Game/Meshes",
                            "dest_path": "/Game/Meshes/Foo"}],
                "skips": [], "content_root": "/Game"}

        result = self.sortilege.cleanup_empty_folders(
            plan, self.sortilege.CONFIG)

        self.assertEqual(result["removed"], [])
        kept = dict(result["kept"])
        self.assertEqual(kept.get("/Elsewhere/Sub"), "outside project content")


class SubfolderGuardTests(EmptyFolderTestBase):
    """The real EditorAssetLibrary.delete_directory is a FORCE delete
    (mock now mirrors that): a folder whose only remaining content is an
    empty subfolder reads empty via list_assets(include_folder=False),
    and deleting it would take the subfolder with it. The sweep must run
    a second include_folder=True listing and keep the parent."""

    def test_excluded_empty_subfolder_keeps_parent_and_survives(self):
        mock_unreal.add_folder("/Game/Stuff/KeepMe")
        assets = [asset("/Game/Stuff/Rock", "StaticMesh")]
        plan, caps = self._apply(assets, config_overrides={
            "EXCLUDE_FOLDERS": ["/Game/Stuff/KeepMe"]})
        self.sortilege.cleanup_redirectors(["/Game/Stuff", "/Game/Meshes"], caps)

        config = dict(self.sortilege.CONFIG)
        config["EXCLUDE_FOLDERS"] = ["/Game/Stuff/KeepMe"]
        result = self.sortilege.cleanup_empty_folders(plan, config)

        self.assertNotIn("/Game/Stuff", result["removed"])
        kept = dict(result["kept"])
        self.assertEqual(kept.get("/Game/Stuff"), "contains subfolders")
        lib = mock_unreal.EditorAssetLibrary
        self.assertTrue(lib.does_directory_exist("/Game/Stuff"))
        self.assertTrue(lib.does_directory_exist("/Game/Stuff/KeepMe"))
        # And the force-delete trail proves nothing was blast-radiused.
        state = mock_unreal.get_state()
        for trail in state["force_deleted"]:
            self.assertNotEqual(trail["folder"], "/Game/Stuff")

    def test_plain_empty_scaffolding_subfolder_survives(self):
        """Even a NON-excluded, deliberately-created empty subfolder
        (future scaffolding) keeps its parent alive -- the sweep only
        removes folders with genuinely nothing under them."""
        mock_unreal.add_folder("/Game/Stuff/Future")
        assets = [asset("/Game/Stuff/Rock", "StaticMesh")]
        plan, caps = self._apply(assets)
        self.sortilege.cleanup_redirectors(["/Game/Stuff", "/Game/Meshes"], caps)

        result = self.sortilege.cleanup_empty_folders(plan, self.sortilege.CONFIG)

        self.assertNotIn("/Game/Stuff", result["removed"])
        kept = dict(result["kept"])
        self.assertEqual(kept.get("/Game/Stuff"), "contains subfolders")
        self.assertTrue(
            mock_unreal.EditorAssetLibrary.does_directory_exist("/Game/Stuff/Future"))

    def test_reverse_containment_guard_for_unregistered_excluded_path(self):
        """Belt and braces: an EXCLUDE_FOLDERS entry pointing UNDER a
        candidate keeps that candidate even when the registry lists no
        such subfolder (nothing was ever created there) -- deleting the
        parent would still destroy the excluded location's future home."""
        assets = [asset("/Game/Stuff/Rock", "StaticMesh")]
        plan, caps = self._apply(assets)
        self.sortilege.cleanup_redirectors(["/Game/Stuff", "/Game/Meshes"], caps)

        config = dict(self.sortilege.CONFIG)
        config["EXCLUDE_FOLDERS"] = ["/Game/Stuff/NotYetCreated"]
        result = self.sortilege.cleanup_empty_folders(plan, config)

        self.assertNotIn("/Game/Stuff", result["removed"])
        kept = dict(result["kept"])
        self.assertEqual(kept.get("/Game/Stuff"), "would remove excluded folder")
        self.assertTrue(
            mock_unreal.EditorAssetLibrary.does_directory_exist("/Game/Stuff"))


class PipelineIntegrationTests(EmptyFolderTestBase):
    def test_default_on_apply_path_sweeps_and_surfaces_results(self):
        """CLEAN_EMPTY_FOLDERS defaults True: a plain run_apply() removes
        the emptied source folder, attaches results["empty_folders"], and
        the summary report shows the Cleaned up section."""
        self.assertTrue(self.sortilege.CONFIG["CLEAN_EMPTY_FOLDERS"])
        mock_unreal.add_asset("/Game/Stuff/Rock", "StaticMesh")
        assets = [asset("/Game/Stuff/Rock", "StaticMesh")]
        caps = self.sortilege.probe_capabilities()
        plan = self.sortilege.build_plan(assets, self.sortilege.CONFIG, caps)

        outcome = self.sortilege.run_apply(plan, caps)

        empty = outcome["results"].get("empty_folders")
        self.assertIsNotNone(empty)
        self.assertIn("/Game/Stuff", empty["removed"])
        self.assertFalse(
            mock_unreal.EditorAssetLibrary.does_directory_exist("/Game/Stuff"))

        with open(outcome["report_path"], "r") as f:
            report = f.read()
        self.assertIn("Cleaned up 1 empty folder(s):", report)
        self.assertIn("/Game/Stuff", report)

    def test_sweep_runs_after_redirector_cleanup_in_apply(self):
        """Order matters: the source folder only reads empty once its
        leftover redirector is cleaned, so a default apply (redirector
        cleanup ON) must still be able to remove it."""
        mock_unreal.add_asset("/Game/Stuff/Rock", "StaticMesh")
        assets = [asset("/Game/Stuff/Rock", "StaticMesh")]
        caps = self.sortilege.probe_capabilities()
        plan = self.sortilege.build_plan(assets, self.sortilege.CONFIG, caps)

        outcome = self.sortilege.run_apply(plan, caps)

        # The redirector was cleaned first, so the sweep saw an empty
        # folder and removed it -- if the order were reversed the folder
        # would have been kept ("not empty").
        self.assertIn("/Game/Stuff", outcome["results"]["empty_folders"]["removed"])

    def test_sweep_off_when_config_disabled(self):
        self.sortilege.CONFIG["CLEAN_EMPTY_FOLDERS"] = False
        mock_unreal.add_asset("/Game/Stuff/Rock", "StaticMesh")
        assets = [asset("/Game/Stuff/Rock", "StaticMesh")]
        caps = self.sortilege.probe_capabilities()
        plan = self.sortilege.build_plan(assets, self.sortilege.CONFIG, caps)

        outcome = self.sortilege.run_apply(plan, caps)

        self.assertNotIn("empty_folders", outcome["results"])
        self.assertTrue(
            mock_unreal.EditorAssetLibrary.does_directory_exist("/Game/Stuff"))

    def test_partial_undo_keeps_failed_dest_folder_and_sweeps_vacated_one(self):
        """A restore where ONE item fails (its original source path got
        re-occupied after the apply): the failed item's sort folder still
        holds it, so it is kept "not empty"; the fully-vacated sort
        folder is removed."""
        mock_unreal.add_asset("/Game/Stuff/Rock", "StaticMesh")
        mock_unreal.add_asset("/Game/Stuff/Wood", "Texture2D")
        assets = [asset("/Game/Stuff/Rock", "StaticMesh"),
                  asset("/Game/Stuff/Wood", "Texture2D")]
        caps = self.sortilege.probe_capabilities()
        plan = self.sortilege.build_plan(assets, self.sortilege.CONFIG, caps)
        outcome = self.sortilege.run_apply(plan, caps)
        self.assertEqual(len(outcome["results"]["moved"]), 2)

        # Sabotage exactly one restore: Wood's original home is now
        # occupied by a brand-new asset, so its reverse rename must fail.
        mock_unreal.add_asset("/Game/Stuff/Wood", "SoundWave")

        results = self.sortilege.run_undo(outcome["undo_log"].path, caps)

        self.assertEqual(len(results["moved"]), 1)
        self.assertEqual(len(results["failed"]), 1)
        # Wood is still stranded in its sort folder -- kept "not empty".
        self.assertIn("/Game/Textures/Wood", mock_unreal.get_state()["assets"])
        empty = results["empty_folders"]
        self.assertNotIn("/Game/Textures", empty["removed"])
        kept = dict(empty["kept"])
        self.assertEqual(kept.get("/Game/Textures"), "not empty")
        self.assertTrue(
            mock_unreal.EditorAssetLibrary.does_directory_exist("/Game/Textures"))
        # Rock's sort folder was fully vacated -- swept.
        self.assertIn("/Game/Meshes", empty["removed"])

    def test_undo_sweeps_vacated_sort_folders(self):
        """After a full restore, the sorted destination folders the undo
        vacated are swept the same way (post-redirector-cleanup)."""
        mock_unreal.add_asset("/Game/Stuff/Rock", "StaticMesh")
        assets = [asset("/Game/Stuff/Rock", "StaticMesh")]
        caps = self.sortilege.probe_capabilities()
        plan = self.sortilege.build_plan(assets, self.sortilege.CONFIG, caps)
        outcome = self.sortilege.run_apply(plan, caps)
        self.assertIn("/Game/Meshes/Rock", mock_unreal.get_state()["assets"])

        results = self.sortilege.run_undo(outcome["undo_log"].path, caps)

        self.assertIn("/Game/Stuff/Rock", mock_unreal.get_state()["assets"])
        empty = results.get("empty_folders")
        self.assertIsNotNone(empty)
        self.assertIn("/Game/Meshes", empty["removed"])
        self.assertFalse(
            mock_unreal.EditorAssetLibrary.does_directory_exist("/Game/Meshes"))


if __name__ == "__main__":
    unittest.main()
