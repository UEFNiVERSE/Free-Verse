"""Tests for sortilege.py's CONFIG, capability probe, content-root
discovery, asset scan, and classification.

sortilege.py does not exist until Task 2 implements it; these tests are
written first (TDD) and are expected to fail with a missing-file error
until then. Every test loads a fresh module + fresh mock via
helpers.load_sortilege() so no state leaks between tests.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import helpers
import mock_unreal


class ConfigShapeTests(unittest.TestCase):
    def test_config_has_all_required_keys(self):
        sortilege = helpers.load_sortilege()
        required = (
            "FOLDER_MAP", "CLASSIFICATION", "PREFIX_MAP", "SORT_ROOT",
            "SCOPE_FOLDERS", "USE_SELECTION", "EXCLUDE_FOLDERS",
            "ENABLE_PREFIX_RENAME", "CLEAN_REDIRECTORS", "VERIFY_AFTER",
            "CLEAN_EMPTY_FOLDERS", "STRICT_MODE", "LOG_DIR",
            "I_UNDERSTAND_THIS_MODIFIES_MY_PROJECT",
        )
        for key in required:
            self.assertIn(key, sortilege.CONFIG)

    def test_config_defaults_are_safe(self):
        sortilege = helpers.load_sortilege()
        self.assertEqual(sortilege.CONFIG["I_UNDERSTAND_THIS_MODIFIES_MY_PROJECT"], False)
        self.assertEqual(sortilege.CONFIG["SORT_ROOT"], "")
        self.assertEqual(sortilege.CONFIG["SCOPE_FOLDERS"], [])
        self.assertEqual(sortilege.CONFIG["STRICT_MODE"], False)


class CapabilityProbeTests(unittest.TestCase):
    def test_probe_capabilities_all_on_by_default(self):
        sortilege = helpers.load_sortilege()
        caps = sortilege.probe_capabilities()
        self.assertTrue(caps.editor_dialog)
        self.assertTrue(caps.selected_folders)
        self.assertTrue(caps.scoped_slow_task)
        self.assertTrue(caps.fix_up_redirectors)
        self.assertTrue(caps.class_paths_filter)
        self.assertTrue(caps.project_root_api)

    def test_probe_capabilities_reflects_features_off(self):
        sortilege = helpers.load_sortilege(features={
            "editor_dialog": False, "fix_up_redirectors": False,
            "project_root_api": False,
        })
        caps = sortilege.probe_capabilities()
        self.assertFalse(caps.editor_dialog)
        self.assertFalse(caps.fix_up_redirectors)
        self.assertFalse(caps.project_root_api)

    def test_report_returns_printable_lines(self):
        sortilege = helpers.load_sortilege()
        caps = sortilege.probe_capabilities()
        lines = caps.report()
        self.assertIsInstance(lines, list)
        self.assertTrue(len(lines) > 0)
        for line in lines:
            self.assertIsInstance(line, str)


class ContentRootDiscoveryTests(unittest.TestCase):
    def test_discover_via_project_root_api(self):
        sortilege = helpers.load_sortilege()
        mock_unreal.set_project_root("/ProjectX")
        roots = sortilege.discover_content_roots()
        self.assertEqual(roots, ["/ProjectX"])

    def test_discover_fallback_when_project_root_api_off(self):
        sortilege = helpers.load_sortilege(features={"project_root_api": False})
        mock_unreal.add_asset("/ProjectX/Meshes/Rock", "StaticMesh")
        mock_unreal.add_asset("/Engine/Foo/Bar", "StaticMesh")
        roots = sortilege.discover_content_roots()
        self.assertEqual(roots, ["/ProjectX"])

    def test_discover_fallback_prefers_game_when_present(self):
        sortilege = helpers.load_sortilege(features={"project_root_api": False})
        mock_unreal.add_asset("/Game/Meshes/Rock", "StaticMesh")
        mock_unreal.add_asset("/ProjectX/Meshes/Rock", "StaticMesh")
        roots = sortilege.discover_content_roots()
        self.assertEqual(roots, ["/Game"])


class ScanAssetsTests(unittest.TestCase):
    def test_scan_returns_expected_shape(self):
        sortilege = helpers.load_sortilege()
        mock_unreal.set_project_root("/ProjectX")
        mock_unreal.add_asset("/ProjectX/Stuff/Rock", "StaticMesh")

        results = sortilege.scan_assets([])
        self.assertEqual(len(results), 1)
        item = results[0]
        self.assertEqual(item["path"], "/ProjectX/Stuff/Rock")
        self.assertEqual(item["name"], "Rock")
        self.assertEqual(item["folder"], "/ProjectX/Stuff")
        self.assertEqual(item["class_name"], "StaticMesh")

    def test_scan_respects_scope_folders(self):
        sortilege = helpers.load_sortilege()
        mock_unreal.set_project_root("/ProjectX")
        mock_unreal.add_asset("/ProjectX/Stuff/Rock", "StaticMesh")
        mock_unreal.add_asset("/ProjectX/Blueprints/BP_User", "Blueprint")

        results = sortilege.scan_assets(["/ProjectX/Stuff"])
        paths = [item["path"] for item in results]
        self.assertEqual(paths, ["/ProjectX/Stuff/Rock"])

    def test_scan_survives_legacy_asset_class_throws_using_asset_class_path(self):
        sortilege = helpers.load_sortilege(features={"legacy_asset_class_throws": True})
        mock_unreal.set_project_root("/ProjectX")
        mock_unreal.add_asset("/ProjectX/Stuff/Rock", "StaticMesh")

        results = sortilege.scan_assets([])
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["class_name"], "StaticMesh")

    def test_scan_falls_back_to_unknown_when_both_class_fields_unavailable(self):
        sortilege = helpers.load_sortilege(features={
            "legacy_asset_class_throws": True, "class_paths_filter": False,
        })
        mock_unreal.set_project_root("/ProjectX")
        mock_unreal.add_asset("/ProjectX/Stuff/Rock", "StaticMesh")

        results = sortilege.scan_assets([])
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["class_name"], "Unknown")


class ClassifyTests(unittest.TestCase):
    def test_classification_table_hits(self):
        sortilege = helpers.load_sortilege()
        config = sortilege.CONFIG
        cases = {
            "StaticMesh": "Meshes",
            "SkeletalMesh": "Meshes",
            "Material": "Materials",
            "Texture2D": "Textures",
            "SoundWave": "Audio",
            "AnimSequence": "Animations",
            "Blueprint": "Props",
            "WidgetBlueprint": "UI",
            "NiagaraSystem": "VFX",
        }
        for class_name, expected_category in cases.items():
            category, reason = sortilege.classify(class_name, config)
            self.assertEqual(category, expected_category, class_name)
            self.assertIsNone(reason, class_name)

    def test_verse_class_protected(self):
        sortilege = helpers.load_sortilege()
        category, reason = sortilege.classify("VerseClass", sortilege.CONFIG)
        self.assertIsNone(category)
        self.assertIn("Verse", reason)

    def test_verse_containing_class_name_is_protected_by_defensive_net(self):
        """PROTECTED_CATEGORIES["VerseClass"] is a best-guess name pending
        live-probe confirmation against a real UEFN build. classify() must
        also protect ANY class name that merely contains "Verse"
        (case-insensitive), so whatever the real engine's actual
        Verse-linked class name(s) turn out to be, they still get caught."""
        sortilege = helpers.load_sortilege()
        category, reason = sortilege.classify("SolarisVerseClass", sortilege.CONFIG)
        self.assertIsNone(category)
        self.assertIn("Verse", reason)

    def test_world_protected(self):
        sortilege = helpers.load_sortilege()
        category, reason = sortilege.classify("World", sortilege.CONFIG)
        self.assertIsNone(category)
        self.assertIn("Level", reason)

    def test_level_protected(self):
        sortilege = helpers.load_sortilege()
        category, reason = sortilege.classify("Level", sortilege.CONFIG)
        self.assertIsNone(category)

    def test_object_redirector_protected(self):
        sortilege = helpers.load_sortilege()
        category, reason = sortilege.classify("ObjectRedirector", sortilege.CONFIG)
        self.assertIsNone(category)
        self.assertIn("redirector", reason)

    def test_strict_mode_off_unknown_goes_to_other(self):
        sortilege = helpers.load_sortilege(config_overrides={"STRICT_MODE": False})
        category, reason = sortilege.classify("SomeWeirdFutureType", sortilege.CONFIG)
        self.assertEqual(category, "Other")
        self.assertIsNone(reason)

    def test_strict_mode_on_unknown_is_skipped(self):
        sortilege = helpers.load_sortilege(config_overrides={"STRICT_MODE": True})
        category, reason = sortilege.classify("SomeWeirdFutureType", sortilege.CONFIG)
        self.assertIsNone(category)
        self.assertIsNotNone(reason)


class ProtectedPathTests(unittest.TestCase):
    def test_external_actors_path_is_protected(self):
        sortilege = helpers.load_sortilege()
        self.assertTrue(sortilege.is_protected_path(
            "/ProjectX/__ExternalActors__/0/1/2/ABCDEFG"))

    def test_external_objects_path_is_protected(self):
        sortilege = helpers.load_sortilege()
        self.assertTrue(sortilege.is_protected_path(
            "/ProjectX/__ExternalObjects__/0/1/2/ABCDEFG"))

    def test_dunder_prefixed_segment_is_protected(self):
        sortilege = helpers.load_sortilege()
        self.assertTrue(sortilege.is_protected_path("/ProjectX/__SystemFolder__/Thing"))

    def test_normal_path_is_not_protected(self):
        sortilege = helpers.load_sortilege()
        self.assertFalse(sortilege.is_protected_path("/ProjectX/Meshes/Rock"))


class ValidateAssetNameTests(unittest.TestCase):
    def test_valid_name_returns_none(self):
        sortilege = helpers.load_sortilege()
        self.assertIsNone(sortilege.validate_asset_name("SM_Rock"))

    def test_empty_name_rejected(self):
        sortilege = helpers.load_sortilege()
        self.assertIsNotNone(sortilege.validate_asset_name(""))

    def test_period_rejected(self):
        sortilege = helpers.load_sortilege()
        self.assertIsNotNone(sortilege.validate_asset_name("Bad.Name"))

    def test_illegal_chars_rejected(self):
        sortilege = helpers.load_sortilege()
        for ch in '\\/:*?"<>|':
            name = "Bad" + ch + "Name"
            self.assertIsNotNone(sortilege.validate_asset_name(name), repr(name))

    def test_leading_trailing_whitespace_rejected(self):
        sortilege = helpers.load_sortilege()
        self.assertIsNotNone(sortilege.validate_asset_name(" Rock"))
        self.assertIsNotNone(sortilege.validate_asset_name("Rock "))


if __name__ == "__main__":
    unittest.main()
