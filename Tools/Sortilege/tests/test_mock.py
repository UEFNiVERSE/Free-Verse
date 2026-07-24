"""Sanity tests for tests/mock_unreal.py -- the fake `unreal` module.

These tests exercise the mock directly (no sortilege.py involved -- it does
not exist yet). Every later task's test suite depends on this mock behaving
exactly like the real UEFN `unreal` module for the slice of API it covers.
"""
import os
import tempfile
import unittest

import mock_unreal as unreal


class AssetsAndFoldersTests(unittest.TestCase):
    def setUp(self):
        unreal.reset()

    def test_add_and_list_assets_recursive(self):
        unreal.add_asset("/ProjectX/Stuff/Rock", "StaticMesh")
        unreal.add_asset("/ProjectX/Stuff/Sub/Pebble", "StaticMesh")
        unreal.add_folder("/ProjectX/Empty")

        lib = unreal.EditorAssetLibrary
        recursive = lib.list_assets("/ProjectX", recursive=True, include_folder=False)
        self.assertIn("/ProjectX/Stuff/Rock", recursive)
        self.assertIn("/ProjectX/Stuff/Sub/Pebble", recursive)

    def test_list_assets_non_recursive_excludes_deeper_paths(self):
        unreal.add_asset("/ProjectX/Rock", "StaticMesh")
        unreal.add_asset("/ProjectX/Stuff/Pebble", "StaticMesh")

        lib = unreal.EditorAssetLibrary
        shallow = lib.list_assets("/ProjectX", recursive=False, include_folder=False)
        self.assertIn("/ProjectX/Rock", shallow)
        self.assertNotIn("/ProjectX/Stuff/Pebble", shallow)

    def test_list_assets_include_folder_has_trailing_slash(self):
        unreal.add_folder("/ProjectX/Meshes")
        lib = unreal.EditorAssetLibrary
        results = lib.list_assets("/ProjectX", recursive=True, include_folder=True)
        self.assertIn("/ProjectX/Meshes/", results)

    def test_does_asset_and_directory_exist(self):
        unreal.add_asset("/ProjectX/Stuff/Rock", "StaticMesh")
        lib = unreal.EditorAssetLibrary
        self.assertTrue(lib.does_asset_exist("/ProjectX/Stuff/Rock"))
        self.assertFalse(lib.does_asset_exist("/ProjectX/Stuff/Nope"))
        self.assertTrue(lib.does_directory_exist("/ProjectX/Stuff"))
        self.assertFalse(lib.does_directory_exist("/ProjectX/Nowhere"))

    def test_make_directory_registers_folder(self):
        lib = unreal.EditorAssetLibrary
        lib.make_directory("/ProjectX/NewFolder")
        self.assertTrue(lib.does_directory_exist("/ProjectX/NewFolder"))


class AssetDataTests(unittest.TestCase):
    def setUp(self):
        unreal.reset()
        unreal.add_asset("/ProjectX/Stuff/Rock", "StaticMesh")

    def test_find_asset_data_fields(self):
        data = unreal.EditorAssetLibrary.find_asset_data("/ProjectX/Stuff/Rock")
        self.assertEqual(str(data.package_name), "/ProjectX/Stuff/Rock")
        self.assertEqual(str(data.asset_name), "Rock")
        self.assertEqual(str(data.asset_class), "StaticMesh")
        self.assertEqual(str(data.asset_class_path.asset_name), "StaticMesh")

    def test_asset_class_path_absent_when_feature_off(self):
        unreal.reset(features={"class_paths_filter": False})
        unreal.add_asset("/ProjectX/Stuff/Rock", "StaticMesh")
        data = unreal.EditorAssetLibrary.find_asset_data("/ProjectX/Stuff/Rock")
        self.assertFalse(hasattr(data, "asset_class_path"))
        self.assertEqual(str(data.asset_class), "StaticMesh")


class RenameAndRedirectorTests(unittest.TestCase):
    def setUp(self):
        unreal.reset()
        unreal.add_asset("/ProjectX/Stuff/Rock", "StaticMesh")
        unreal.add_asset("/ProjectX/Blueprints/BP_User", "Blueprint",
                          deps=["/ProjectX/Stuff/Rock"])

    def test_rename_assets_creates_redirector_and_rewrites_deps(self):
        tools = unreal.AssetToolsHelpers.get_asset_tools()
        asset = unreal.EditorAssetLibrary.load_asset("/ProjectX/Stuff/Rock")
        rename_data = unreal.AssetRenameData(asset, "/ProjectX/Meshes", "Rock")

        result = tools.rename_assets([rename_data])

        self.assertTrue(result)
        state = unreal.get_state()
        self.assertIn("/ProjectX/Meshes/Rock", state["assets"])
        self.assertNotIn("/ProjectX/Stuff/Rock", state["assets"])
        self.assertEqual(state["redirectors"]["/ProjectX/Stuff/Rock"], "/ProjectX/Meshes/Rock")
        self.assertEqual(
            state["assets"]["/ProjectX/Blueprints/BP_User"]["deps"],
            ["/ProjectX/Meshes/Rock"],
        )

    def test_rename_assets_collision_fails_safely(self):
        unreal.add_asset("/ProjectX/Meshes/Rock", "StaticMesh")
        tools = unreal.AssetToolsHelpers.get_asset_tools()
        asset = unreal.EditorAssetLibrary.load_asset("/ProjectX/Stuff/Rock")
        rename_data = unreal.AssetRenameData(asset, "/ProjectX/Meshes", "Rock")

        result = tools.rename_assets([rename_data])

        self.assertFalse(result)
        state = unreal.get_state()
        self.assertIn("/ProjectX/Stuff/Rock", state["assets"])
        self.assertNotIn("/ProjectX/Stuff/Rock", state["redirectors"])
        self.assertEqual(
            state["assets"]["/ProjectX/Blueprints/BP_User"]["deps"],
            ["/ProjectX/Stuff/Rock"],
        )

    def test_rename_asset_single_via_editor_asset_library(self):
        lib = unreal.EditorAssetLibrary
        ok = lib.rename_asset("/ProjectX/Stuff/Rock", "/ProjectX/Meshes/Rock")
        self.assertTrue(ok)
        self.assertTrue(lib.does_asset_exist("/ProjectX/Meshes/Rock"))
        state = unreal.get_state()
        self.assertEqual(state["redirectors"]["/ProjectX/Stuff/Rock"], "/ProjectX/Meshes/Rock")

    def test_rename_asset_single_collision_returns_false_no_change(self):
        unreal.add_asset("/ProjectX/Meshes/Rock", "StaticMesh")
        lib = unreal.EditorAssetLibrary
        ok = lib.rename_asset("/ProjectX/Stuff/Rock", "/ProjectX/Meshes/Rock")
        self.assertFalse(ok)
        state = unreal.get_state()
        self.assertIn("/ProjectX/Stuff/Rock", state["assets"])
        self.assertNotIn("/ProjectX/Stuff/Rock", state["redirectors"])

    def test_find_package_referencers_sees_refs_through_redirector_chain(self):
        lib = unreal.EditorAssetLibrary
        # First hop.
        lib.rename_asset("/ProjectX/Stuff/Rock", "/ProjectX/Temp/Rock")
        # Second hop -- BP_User's dep now points at /ProjectX/Temp/Rock, which
        # itself becomes a redirector after this second move.
        lib.rename_asset("/ProjectX/Temp/Rock", "/ProjectX/Meshes/Rock")

        refs = lib.find_package_referencers_for_asset("/ProjectX/Meshes/Rock")
        self.assertIn("/ProjectX/Blueprints/BP_User", refs)

    def test_load_asset_on_redirector_path_resolves_target(self):
        lib = unreal.EditorAssetLibrary
        lib.rename_asset("/ProjectX/Stuff/Rock", "/ProjectX/Meshes/Rock")

        loaded = lib.load_asset("/ProjectX/Stuff/Rock")
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.path, "/ProjectX/Meshes/Rock")

    def test_delete_asset_on_redirector_and_real_asset(self):
        lib = unreal.EditorAssetLibrary
        lib.rename_asset("/ProjectX/Stuff/Rock", "/ProjectX/Meshes/Rock")

        self.assertTrue(lib.delete_asset("/ProjectX/Stuff/Rock"))
        state = unreal.get_state()
        self.assertNotIn("/ProjectX/Stuff/Rock", state["redirectors"])

        self.assertTrue(lib.delete_asset("/ProjectX/Meshes/Rock"))
        self.assertFalse(lib.does_asset_exist("/ProjectX/Meshes/Rock"))

    def test_save_loaded_asset_rewrites_redirector_deps_to_target(self):
        lib = unreal.EditorAssetLibrary
        lib.rename_asset("/ProjectX/Stuff/Rock", "/ProjectX/Meshes/Rock")

        # BP_User's dep was already rewritten by rename, so force a stale
        # redirector-pointing dep to prove save_loaded_asset resolves it.
        state = unreal.get_state()
        state["assets"]["/ProjectX/Blueprints/BP_User"]["deps"] = ["/ProjectX/Stuff/Rock"]

        referencer = lib.load_asset("/ProjectX/Blueprints/BP_User")
        lib.save_loaded_asset(referencer)

        self.assertEqual(
            state["assets"]["/ProjectX/Blueprints/BP_User"]["deps"],
            ["/ProjectX/Meshes/Rock"],
        )
        self.assertIn("/ProjectX/Blueprints/BP_User", state["saved"])

    def test_verse_and_world_classes_refuse_move(self):
        unreal.add_asset("/ProjectX/Verse/MyDevice", "VerseClass")
        unreal.add_asset("/ProjectX/Maps/Island", "World")
        lib = unreal.EditorAssetLibrary

        self.assertFalse(lib.rename_asset("/ProjectX/Verse/MyDevice", "/ProjectX/Sorted/MyDevice"))
        self.assertFalse(lib.rename_asset("/ProjectX/Maps/Island", "/ProjectX/Sorted/Island"))
        state = unreal.get_state()
        self.assertIn("/ProjectX/Verse/MyDevice", state["assets"])
        self.assertIn("/ProjectX/Maps/Island", state["assets"])


class FeatureGatingTests(unittest.TestCase):
    def test_fix_up_redirectors_absent_when_feature_off(self):
        unreal.reset(features={"fix_up_redirectors": False})
        tools = unreal.AssetToolsHelpers.get_asset_tools()
        self.assertFalse(hasattr(tools, "fix_up_redirectors"))

    def test_fix_up_redirectors_present_by_default(self):
        unreal.reset()
        tools = unreal.AssetToolsHelpers.get_asset_tools()
        self.assertTrue(hasattr(tools, "fix_up_redirectors"))

    def test_editor_dialog_absent_when_feature_off(self):
        unreal.reset(features={"editor_dialog": False})
        self.assertFalse(hasattr(unreal, "EditorDialog"))

    def test_editor_dialog_present_by_default(self):
        unreal.reset()
        self.assertTrue(hasattr(unreal, "EditorDialog"))

    def test_selected_folders_method_absent_when_feature_off(self):
        unreal.reset(features={"selected_folders": False})
        self.assertFalse(hasattr(unreal.EditorUtilityLibrary, "get_selected_folder_paths"))

    def test_scoped_slow_task_absent_when_feature_off(self):
        unreal.reset(features={"scoped_slow_task": False})
        self.assertFalse(hasattr(unreal, "ScopedSlowTask"))

    def test_asset_rename_data_absent_when_feature_off(self):
        unreal.reset(features={"asset_rename_data": False})
        self.assertFalse(hasattr(unreal, "AssetRenameData"))

    def test_features_reset_back_to_all_on(self):
        unreal.reset(features={"editor_dialog": False, "fix_up_redirectors": False})
        unreal.reset()
        tools = unreal.AssetToolsHelpers.get_asset_tools()
        self.assertTrue(hasattr(unreal, "EditorDialog"))
        self.assertTrue(hasattr(tools, "fix_up_redirectors"))


class DialogAndSelectionTests(unittest.TestCase):
    def setUp(self):
        unreal.reset()

    def test_dialog_answer_queue_yes_then_no(self):
        unreal.set_dialog_answer("Yes")
        unreal.set_dialog_answer("No")

        first = unreal.EditorDialog.show_message("Title", "Msg", unreal.AppMsgType.YES_NO)
        second = unreal.EditorDialog.show_message("Title", "Msg", unreal.AppMsgType.YES_NO)

        self.assertEqual(first, unreal.AppReturnType.YES)
        self.assertEqual(second, unreal.AppReturnType.NO)

    def test_selected_folders_round_trip(self):
        unreal.set_selected_folders(["/ProjectX/Stuff", "/ProjectX/Meshes"])
        got = unreal.EditorUtilityLibrary.get_selected_folder_paths()
        self.assertEqual(got, ["/ProjectX/Stuff", "/ProjectX/Meshes"])


class ScopedSlowTaskTests(unittest.TestCase):
    def setUp(self):
        unreal.reset()

    def test_scoped_slow_task_context_manager_records_calls(self):
        with unreal.ScopedSlowTask(2, "Sorting") as task:
            task.make_dialog()
            task.enter_progress_frame(1, "step one")
        state = unreal.get_state()
        self.assertTrue(any("ScopedSlowTask" in line for line in state["log"]))


class RegistryTests(unittest.TestCase):
    def setUp(self):
        unreal.reset()
        unreal.add_asset("/ProjectX/Stuff/Rock", "StaticMesh")
        unreal.add_asset("/ProjectX/Blueprints/BP_User", "Blueprint")

    def test_get_assets_by_path_includes_redirectors(self):
        unreal.EditorAssetLibrary.rename_asset("/ProjectX/Stuff/Rock", "/ProjectX/Meshes/Rock")
        registry = unreal.AssetRegistryHelpers.get_asset_registry()
        results = registry.get_assets_by_path("/ProjectX", recursive=True)
        classes = {str(ad.package_name): str(ad.asset_class) for ad in results}
        self.assertEqual(classes.get("/ProjectX/Stuff/Rock"), "ObjectRedirector")
        self.assertEqual(classes.get("/ProjectX/Meshes/Rock"), "StaticMesh")

    def test_get_assets_filters_by_class_names(self):
        registry = unreal.AssetRegistryHelpers.get_asset_registry()
        ar_filter = unreal.ARFilter(class_names=["Blueprint"], package_paths=["/ProjectX"])
        results = registry.get_assets(ar_filter)
        paths = [str(ad.package_name) for ad in results]
        self.assertEqual(paths, ["/ProjectX/Blueprints/BP_User"])


class LogAndPathsTests(unittest.TestCase):
    def setUp(self):
        unreal.reset()

    def test_log_functions_append_to_state_log(self):
        unreal.log("hello")
        unreal.log_warning("careful")
        unreal.log_error("boom")
        state = unreal.get_state()
        self.assertTrue(any("hello" in line for line in state["log"]))
        self.assertTrue(any("careful" in line for line in state["log"]))
        self.assertTrue(any("boom" in line for line in state["log"]))

    def test_paths_project_saved_dir_returns_string(self):
        result = unreal.Paths.project_saved_dir()
        self.assertIsInstance(result, str)
        self.assertTrue(len(result) > 0)


class HelpersModuleImportTests(unittest.TestCase):
    def test_helpers_module_is_importable_and_exposes_load_sortilege(self):
        # sortilege.py does not exist yet (Task 2) -- only confirm the loader
        # function is defined; do not call it here.
        import helpers
        self.assertTrue(hasattr(helpers, "load_sortilege"))
        self.assertTrue(callable(helpers.load_sortilege))


# ---------------------------------------------------------------------------
# Task 2 mock amendments: project-root API, ancestor-folder registration,
# legacy asset_class deprecation-throw simulation.
# ---------------------------------------------------------------------------

class ProjectRootApiTests(unittest.TestCase):
    def setUp(self):
        unreal.reset()

    def test_default_project_root_is_game(self):
        lib = unreal.EditorAssetLibrary
        self.assertEqual(lib.get_project_root_asset_directory(), "/Game/")

    def test_set_project_root_changes_result(self):
        unreal.set_project_root("/ProjectX")
        lib = unreal.EditorAssetLibrary
        self.assertEqual(lib.get_project_root_asset_directory(), "/ProjectX/")

    def test_project_root_api_absent_when_feature_off(self):
        unreal.reset(features={"project_root_api": False})
        self.assertFalse(hasattr(unreal.EditorAssetLibrary, "get_project_root_asset_directory"))

    def test_project_root_api_present_by_default(self):
        self.assertTrue(hasattr(unreal.EditorAssetLibrary, "get_project_root_asset_directory"))

    def test_project_root_resets_to_default_between_runs(self):
        unreal.set_project_root("/ProjectX")
        unreal.reset()
        lib = unreal.EditorAssetLibrary
        self.assertEqual(lib.get_project_root_asset_directory(), "/Game/")


class AncestorFolderTests(unittest.TestCase):
    def setUp(self):
        unreal.reset()

    def test_does_directory_exist_true_for_every_ancestor(self):
        unreal.add_asset("/ProjectX/Stuff/Sub/Pebble", "StaticMesh")
        lib = unreal.EditorAssetLibrary
        self.assertTrue(lib.does_directory_exist("/ProjectX"))
        self.assertTrue(lib.does_directory_exist("/ProjectX/Stuff"))
        self.assertTrue(lib.does_directory_exist("/ProjectX/Stuff/Sub"))
        self.assertFalse(lib.does_directory_exist("/ProjectX/Nowhere"))

    def test_does_directory_exist_true_for_single_level_asset_root(self):
        unreal.add_asset("/ProjectX/Rock", "StaticMesh")
        lib = unreal.EditorAssetLibrary
        self.assertTrue(lib.does_directory_exist("/ProjectX"))

    def test_rename_registers_full_ancestor_chain_of_new_path(self):
        unreal.add_asset("/ProjectX/Stuff/Rock", "StaticMesh")
        lib = unreal.EditorAssetLibrary
        lib.rename_asset("/ProjectX/Stuff/Rock", "/ProjectX/Deep/Nested/Meshes/Rock")
        self.assertTrue(lib.does_directory_exist("/ProjectX/Deep"))
        self.assertTrue(lib.does_directory_exist("/ProjectX/Deep/Nested"))
        self.assertTrue(lib.does_directory_exist("/ProjectX/Deep/Nested/Meshes"))


class LegacyAssetClassThrowsTests(unittest.TestCase):
    def test_asset_class_access_raises_when_feature_on(self):
        unreal.reset(features={"legacy_asset_class_throws": True})
        unreal.add_asset("/ProjectX/Stuff/Rock", "StaticMesh")
        data = unreal.EditorAssetLibrary.find_asset_data("/ProjectX/Stuff/Rock")
        with self.assertRaises(Exception):
            data.asset_class

    def test_asset_class_path_still_available_when_legacy_throws(self):
        unreal.reset(features={"legacy_asset_class_throws": True})
        unreal.add_asset("/ProjectX/Stuff/Rock", "StaticMesh")
        data = unreal.EditorAssetLibrary.find_asset_data("/ProjectX/Stuff/Rock")
        self.assertEqual(str(data.asset_class_path.asset_name), "StaticMesh")

    def test_asset_class_ok_when_feature_off(self):
        unreal.reset()
        unreal.add_asset("/ProjectX/Stuff/Rock", "StaticMesh")
        data = unreal.EditorAssetLibrary.find_asset_data("/ProjectX/Stuff/Rock")
        self.assertEqual(str(data.asset_class), "StaticMesh")


# ---------------------------------------------------------------------------
# Task 4 mock amendments: is_redirector/get_asset, save_loaded_asset's and
# find_package_referencers_for_asset's new args, rename_asset accepting full
# object paths, SystemLibrary.collect_garbage, AssetTools.rename_referencing_
# soft_object_paths.
# ---------------------------------------------------------------------------

class IsRedirectorAndGetAssetTests(unittest.TestCase):
    def setUp(self):
        unreal.reset()
        unreal.add_asset("/ProjectX/Stuff/Rock", "StaticMesh")

    def test_is_redirector_false_for_real_asset(self):
        data = unreal.EditorAssetLibrary.find_asset_data("/ProjectX/Stuff/Rock")
        self.assertFalse(data.is_redirector())

    def test_is_redirector_true_for_redirector_entry(self):
        unreal.EditorAssetLibrary.rename_asset("/ProjectX/Stuff/Rock", "/ProjectX/Meshes/Rock")
        data = unreal.EditorAssetLibrary.find_asset_data("/ProjectX/Stuff/Rock")
        self.assertTrue(data.is_redirector())

    def test_get_asset_on_redirector_returns_the_redirectors_own_path(self):
        unreal.EditorAssetLibrary.rename_asset("/ProjectX/Stuff/Rock", "/ProjectX/Meshes/Rock")
        data = unreal.EditorAssetLibrary.find_asset_data("/ProjectX/Stuff/Rock")
        obj = data.get_asset()
        self.assertEqual(obj.path, "/ProjectX/Stuff/Rock")


class RenameAsFullObjectPathTests(unittest.TestCase):
    def setUp(self):
        unreal.reset()
        unreal.add_asset("/ProjectX/Stuff/Rock", "StaticMesh")

    def test_rename_asset_accepts_full_object_paths(self):
        lib = unreal.EditorAssetLibrary
        ok = lib.rename_asset("/ProjectX/Stuff/Rock.Rock", "/ProjectX/Meshes/Rock.Rock")
        self.assertTrue(ok)
        self.assertTrue(lib.does_asset_exist("/ProjectX/Meshes/Rock"))
        state = unreal.get_state()
        self.assertEqual(state["redirectors"]["/ProjectX/Stuff/Rock"], "/ProjectX/Meshes/Rock")

    def test_rename_asset_accepts_mixed_package_and_object_paths(self):
        lib = unreal.EditorAssetLibrary
        ok = lib.rename_asset("/ProjectX/Stuff/Rock", "/ProjectX/Meshes/Rock.Rock")
        self.assertTrue(ok)
        self.assertTrue(lib.does_asset_exist("/ProjectX/Meshes/Rock"))


class SaveLoadedAssetOnlyIfDirtyArgTests(unittest.TestCase):
    def setUp(self):
        unreal.reset()
        unreal.add_asset("/ProjectX/Stuff/Rock", "StaticMesh")
        unreal.add_asset("/ProjectX/Blueprints/BP_User", "Blueprint",
                          deps=["/ProjectX/Stuff/Rock"])

    def test_save_loaded_asset_accepts_only_if_is_dirty_kwarg(self):
        lib = unreal.EditorAssetLibrary
        lib.rename_asset("/ProjectX/Stuff/Rock", "/ProjectX/Meshes/Rock")
        state = unreal.get_state()
        state["assets"]["/ProjectX/Blueprints/BP_User"]["deps"] = ["/ProjectX/Stuff/Rock"]

        referencer = lib.load_asset("/ProjectX/Blueprints/BP_User")
        result = lib.save_loaded_asset(referencer, only_if_is_dirty=False)

        self.assertTrue(result)
        self.assertEqual(
            state["assets"]["/ProjectX/Blueprints/BP_User"]["deps"],
            ["/ProjectX/Meshes/Rock"],
        )

    def test_save_loaded_asset_accepts_only_if_is_dirty_positionally(self):
        lib = unreal.EditorAssetLibrary
        referencer = lib.load_asset("/ProjectX/Blueprints/BP_User")
        result = lib.save_loaded_asset(referencer, True)
        self.assertTrue(result)


class FindPackageReferencersLoadArgTests(unittest.TestCase):
    def setUp(self):
        unreal.reset()
        unreal.add_asset("/ProjectX/Stuff/Rock", "StaticMesh")
        unreal.add_asset("/ProjectX/Blueprints/BP_User", "Blueprint",
                          deps=["/ProjectX/Stuff/Rock"])

    def test_accepts_load_assets_to_confirm_kwarg(self):
        lib = unreal.EditorAssetLibrary
        refs = lib.find_package_referencers_for_asset(
            "/ProjectX/Stuff/Rock", load_assets_to_confirm=True)
        self.assertIn("/ProjectX/Blueprints/BP_User", refs)

    def test_accepts_load_assets_to_confirm_positionally(self):
        lib = unreal.EditorAssetLibrary
        refs = lib.find_package_referencers_for_asset("/ProjectX/Stuff/Rock", False)
        self.assertIn("/ProjectX/Blueprints/BP_User", refs)


class RedirectorSpecificReferencerTests(unittest.TestCase):
    """The core mechanic the redirector-cleanup recipe depends on: once a
    referencer's dependency has been resaved to point straight at the
    resolved target, it must stop showing up as "still referencing" the
    now-orphaned redirector specifically -- even though plenty of other
    (perfectly healthy) referencers may still legitimately point at that
    same target forever. Querying the resolved target itself keeps the
    older "sees refs through the chain" behavior for exactly that reason:
    that query is about the asset, not about any one specific redirector.
    """

    def setUp(self):
        unreal.reset()
        unreal.add_asset("/ProjectX/Stuff/Rock", "StaticMesh")
        unreal.EditorAssetLibrary.rename_asset("/ProjectX/Stuff/Rock", "/ProjectX/Meshes/Rock")
        # A referencer added AFTER the move, with a deliberately stale dep
        # still pointing at the old (now-redirector) path -- simulates a
        # package that was cached before the move and never resaved.
        unreal.add_asset("/ProjectX/Blueprints/BP_Stale", "Blueprint",
                          deps=["/ProjectX/Stuff/Rock"])
        # A second, healthy referencer that references the final target
        # directly and should never block the redirector's own cleanup.
        unreal.add_asset("/ProjectX/Blueprints/BP_Healthy", "Blueprint",
                          deps=["/ProjectX/Meshes/Rock"])

    def test_querying_the_redirector_finds_only_the_stale_referencer(self):
        lib = unreal.EditorAssetLibrary
        refs = lib.find_package_referencers_for_asset("/ProjectX/Stuff/Rock", True)
        self.assertIn("/ProjectX/Blueprints/BP_Stale", refs)
        self.assertNotIn("/ProjectX/Blueprints/BP_Healthy", refs)

    def test_resaving_the_stale_referencer_clears_the_redirector_query(self):
        lib = unreal.EditorAssetLibrary
        referencer = lib.load_asset("/ProjectX/Blueprints/BP_Stale")
        lib.save_loaded_asset(referencer, only_if_is_dirty=False)

        refs = lib.find_package_referencers_for_asset("/ProjectX/Stuff/Rock", False)
        self.assertEqual(refs, [])

    def test_querying_the_resolved_target_still_finds_everyone(self):
        lib = unreal.EditorAssetLibrary
        refs = lib.find_package_referencers_for_asset("/ProjectX/Meshes/Rock")
        self.assertIn("/ProjectX/Blueprints/BP_Stale", refs)
        self.assertIn("/ProjectX/Blueprints/BP_Healthy", refs)


class DeleteDirectoryTests(unittest.TestCase):
    def setUp(self):
        unreal.reset()

    def test_delete_directory_removes_empty_folder(self):
        lib = unreal.EditorAssetLibrary
        lib.make_directory("/ProjectX/Empty")
        self.assertTrue(lib.delete_directory("/ProjectX/Empty"))
        self.assertFalse(lib.does_directory_exist("/ProjectX/Empty"))

    def test_delete_directory_force_deletes_everything_under_it(self):
        """The REAL EditorAssetLibrary.delete_directory is a FORCE
        delete (empirically confirmed live): it takes assets, redirectors
        and subfolders with it and returns True. The mock's old refusal
        behavior was safer than reality and masked a sweep bug -- this
        test pins the realistic semantics plus the recorded blast-radius
        trail."""
        lib = unreal.EditorAssetLibrary
        unreal.add_asset("/ProjectX/Stuff/Rock", "StaticMesh")
        unreal.add_folder("/ProjectX/Stuff/Sub")
        self.assertTrue(lib.delete_directory("/ProjectX/Stuff"))
        state = unreal.get_state()
        self.assertNotIn("/ProjectX/Stuff/Rock", state["assets"])
        self.assertFalse(lib.does_directory_exist("/ProjectX/Stuff"))
        self.assertFalse(lib.does_directory_exist("/ProjectX/Stuff/Sub"))
        trail = state["force_deleted"][-1]
        self.assertEqual(trail["folder"], "/ProjectX/Stuff")
        self.assertIn("/ProjectX/Stuff/Rock", trail["assets"])
        self.assertIn("/ProjectX/Stuff/Sub", trail["folders"])


class SystemLibraryCollectGarbageTests(unittest.TestCase):
    def test_collect_garbage_present_by_default_and_records_calls(self):
        unreal.reset()
        self.assertTrue(hasattr(unreal, "SystemLibrary"))
        unreal.SystemLibrary.collect_garbage()
        unreal.SystemLibrary.collect_garbage()
        self.assertEqual(unreal.get_state()["gc_calls"], 2)

    def test_system_library_absent_when_feature_off(self):
        unreal.reset(features={"collect_garbage": False})
        self.assertFalse(hasattr(unreal, "SystemLibrary"))


class SoftObjectPathRenameTests(unittest.TestCase):
    def test_present_by_default_and_records_calls(self):
        unreal.reset()
        tools = unreal.AssetToolsHelpers.get_asset_tools()
        self.assertTrue(hasattr(tools, "rename_referencing_soft_object_paths"))
        tools.rename_referencing_soft_object_paths(
            ["/ProjectX/Blueprints/BP_User"],
            {"/ProjectX/Stuff/Rock.Rock": "/ProjectX/Meshes/Rock.Rock"},
        )
        calls = unreal.get_state()["soft_rename_calls"]
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["packages"], ["/ProjectX/Blueprints/BP_User"])
        self.assertEqual(
            calls[0]["map"],
            {"/ProjectX/Stuff/Rock.Rock": "/ProjectX/Meshes/Rock.Rock"},
        )

    def test_absent_when_feature_off(self):
        unreal.reset(features={"soft_path_rename": False})
        tools = unreal.AssetToolsHelpers.get_asset_tools()
        self.assertFalse(hasattr(tools, "rename_referencing_soft_object_paths"))


# ---------------------------------------------------------------------------
# Verse-dir auto-detect support: unreal.SystemLibrary.get_system_path() +
# set_project_disk_dir() -- lets resolve_verse_search_dir() derive the real
# UEFN project directory from a scanned asset's on-disk path instead of
# trusting unreal.Paths.project_dir() (which in real UEFN resolves to the
# Fortnite ENGINE directory, not the user's project -- the live-diagnosed
# bug this whole mechanism exists to fix).
# ---------------------------------------------------------------------------

class SystemLibraryGetSystemPathTests(unittest.TestCase):
    def setUp(self):
        unreal.reset()

    def test_present_by_default_and_derives_disk_path_from_package_path(self):
        self.assertTrue(hasattr(unreal, "SystemLibrary"))
        self.assertTrue(hasattr(unreal.SystemLibrary, "get_system_path"))

        project_disk = os.path.join(tempfile.gettempdir(), "MockProjA")
        unreal.set_project_disk_dir(project_disk)
        unreal.add_asset("/Game/Textures/T_Foo", "Texture2D")
        asset = unreal.EditorAssetLibrary.load_asset("/Game/Textures/T_Foo")

        disk_path = unreal.SystemLibrary.get_system_path(asset)

        expected = os.path.join(project_disk, "Content", "Textures", "T_Foo.uasset")
        self.assertEqual(disk_path, expected)

    def test_root_level_asset_has_no_subfolder_before_the_filename(self):
        project_disk = os.path.join(tempfile.gettempdir(), "MockProjB")
        unreal.set_project_disk_dir(project_disk)
        unreal.add_asset("/Game/T_Bare", "Texture2D")
        asset = unreal.EditorAssetLibrary.load_asset("/Game/T_Bare")

        disk_path = unreal.SystemLibrary.get_system_path(asset)

        self.assertEqual(disk_path, os.path.join(project_disk, "Content", "T_Bare.uasset"))

    def test_default_project_disk_dir_is_under_the_system_tempdir(self):
        state = unreal.get_state()
        self.assertEqual(
            state["project_disk_dir"],
            os.path.join(tempfile.gettempdir(), "MockProj"))

    def test_absent_when_feature_off(self):
        unreal.reset(features={"system_path": False})
        # SystemLibrary itself still exists (gated separately by
        # "collect_garbage") -- only get_system_path is missing.
        self.assertTrue(hasattr(unreal, "SystemLibrary"))
        self.assertFalse(hasattr(unreal.SystemLibrary, "get_system_path"))

    def test_entirely_absent_when_collect_garbage_also_off(self):
        unreal.reset(features={"collect_garbage": False, "system_path": False})
        self.assertFalse(hasattr(unreal, "SystemLibrary"))


if __name__ == "__main__":
    unittest.main()
