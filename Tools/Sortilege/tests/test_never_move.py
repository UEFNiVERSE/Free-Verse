"""Tests for NEVER_MOVE structural-asset protection.

Field report: a live UEFN apply moved the project's GameFeatureData asset
and broke the project ("Project 'X' is broken because it's missing its
GameFeatureData"), leaving broken references behind. GameFeatureData,
levels/maps (World/Level), their MapBuildDataRegistry, and anything
World-Partition/Verse-linked must NEVER be moved -- checked before
classify()'s normal category/grouping/Other logic, in both flat and
group-by-asset sorting modes, regardless of STRICT_MODE.

RED-first TDD against classify()'s not-yet-added NEVER_MOVE guard.
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
# classify() -- exact classes, substring net, LevelSequence non-regression
# ---------------------------------------------------------------------------

class NeverMoveClassifyTests(unittest.TestCase):
    def setUp(self):
        self.sortilege = helpers.load_sortilege()

    def _skipped(self, class_name):
        category, reason = self.sortilege.classify(class_name, self.sortilege.CONFIG)
        self.assertIsNone(category, "%s should be skipped, not classified" % class_name)
        self.assertIsNotNone(reason, "%s should carry a skip reason" % class_name)
        return reason

    def test_game_feature_data_skipped_with_reason(self):
        reason = self._skipped("GameFeatureData")
        self.assertIn("GameFeatureData", reason)

    def test_world_skipped(self):
        self._skipped("World")

    def test_level_skipped(self):
        self._skipped("Level")

    def test_map_build_data_registry_skipped(self):
        self._skipped("MapBuildDataRegistry")

    def test_level_streaming_skipped(self):
        self._skipped("LevelStreaming")

    def test_world_data_layers_skipped(self):
        self._skipped("WorldDataLayers")

    def test_data_layer_asset_skipped(self):
        self._skipped("DataLayerAsset")

    def test_gamefeature_substring_class_skipped(self):
        """A hypothetical subclass name we did not enumerate exactly --
        caught by the case-insensitive "gamefeature" substring net."""
        reason = self._skipped("UEFNGameFeatureDataOverride")
        self.assertIn("GameFeatureData", reason)

    def test_worldpartition_substring_class_skipped(self):
        self._skipped("WorldPartitionHLODHelper")

    def test_verse_substring_class_still_skipped(self):
        """The new NEVER_MOVE substring set extends (never regresses) the
        pre-existing Verse defensive net."""
        reason = self._skipped("MyVerseDeviceClass")
        self.assertIn("Verse", reason)

    def test_level_sequence_still_moves_not_caught(self):
        """"level" must never be used as a bare substring -- it would
        wrongly catch LevelSequence, a normal, safe Props asset that must
        keep moving. Only the exact names "Level"/"LevelStreaming" are
        protected."""
        category, reason = self.sortilege.classify("LevelSequence", self.sortilege.CONFIG)
        self.assertEqual(category, "Props")
        self.assertIsNone(reason)

    def test_unrelated_class_unaffected(self):
        category, reason = self.sortilege.classify("StaticMesh", self.sortilege.CONFIG)
        self.assertEqual(category, "Meshes")
        self.assertIsNone(reason)

    def test_strict_mode_true_still_skips_never_move_classes(self):
        sortilege = helpers.load_sortilege(config_overrides={"STRICT_MODE": True})
        category, reason = sortilege.classify("GameFeatureData", sortilege.CONFIG)
        self.assertIsNone(category)
        self.assertIn("structural", reason.lower())

    def test_strict_mode_false_still_skips_never_move_classes(self):
        sortilege = helpers.load_sortilege(config_overrides={"STRICT_MODE": False})
        category, reason = sortilege.classify("GameFeatureData", sortilege.CONFIG)
        self.assertIsNone(category)
        self.assertIn("structural", reason.lower())


# ---------------------------------------------------------------------------
# build_plan() -- flat mode: a NEVER_MOVE asset never becomes a move
# ---------------------------------------------------------------------------

class NeverMoveBuildPlanTests(unittest.TestCase):
    def setUp(self):
        self.sortilege = helpers.load_sortilege()
        mock_unreal.set_project_root("/ProjectX")

    def test_game_feature_data_asset_never_becomes_a_move(self):
        mock_unreal.add_asset("/ProjectX/ProjectXGameFeature", "GameFeatureData")
        assets = [asset("/ProjectX/ProjectXGameFeature", "GameFeatureData")]
        caps = self.sortilege.probe_capabilities()

        plan = self.sortilege.build_plan(assets, self.sortilege.CONFIG, caps)

        move_paths = [m["path"] for m in plan["moves"]]
        self.assertNotIn("/ProjectX/ProjectXGameFeature", move_paths)
        skips = [s for s in plan["skips"] if s["path"] == "/ProjectX/ProjectXGameFeature"]
        self.assertEqual(len(skips), 1)
        self.assertIn("GameFeatureData", skips[0]["reason"])

    def test_level_asset_never_becomes_a_move(self):
        mock_unreal.add_asset("/ProjectX/Maps/Island", "World")
        assets = [asset("/ProjectX/Maps/Island", "World")]
        caps = self.sortilege.probe_capabilities()

        plan = self.sortilege.build_plan(assets, self.sortilege.CONFIG, caps)

        move_paths = [m["path"] for m in plan["moves"]]
        self.assertNotIn("/ProjectX/Maps/Island", move_paths)

    def test_map_build_data_registry_never_becomes_a_move(self):
        mock_unreal.add_asset("/ProjectX/Maps/Island_BuiltData", "MapBuildDataRegistry")
        assets = [asset("/ProjectX/Maps/Island_BuiltData", "MapBuildDataRegistry")]
        caps = self.sortilege.probe_capabilities()

        plan = self.sortilege.build_plan(assets, self.sortilege.CONFIG, caps)

        move_paths = [m["path"] for m in plan["moves"]]
        self.assertNotIn("/ProjectX/Maps/Island_BuiltData", move_paths)

    def test_level_sequence_still_becomes_a_move(self):
        """Non-regression at the build_plan() level too, mirroring the
        classify()-level guard above."""
        mock_unreal.add_asset("/ProjectX/Stuff/Cutscene", "LevelSequence")
        assets = [asset("/ProjectX/Stuff/Cutscene", "LevelSequence")]
        caps = self.sortilege.probe_capabilities()

        plan = self.sortilege.build_plan(assets, self.sortilege.CONFIG, caps)

        move_paths = [m["path"] for m in plan["moves"]]
        self.assertIn("/ProjectX/Stuff/Cutscene", move_paths)


# ---------------------------------------------------------------------------
# build_plan() -- group-by-asset mode: never a kit anchor, never pulled
# into another kit's dependency closure
# ---------------------------------------------------------------------------

class NeverMoveGroupingTests(unittest.TestCase):
    def setUp(self):
        self.sortilege = helpers.load_sortilege(config_overrides={"GROUP_BY_ASSET": True})
        mock_unreal.set_project_root("/ProjectX")

    def _plan(self, scan):
        caps = self.sortilege.probe_capabilities()
        return self.sortilege.build_plan(scan, self.sortilege.CONFIG, caps)

    def test_blueprint_kit_leaves_dependent_level_untouched(self):
        mock_unreal.add_asset("/ProjectX/Maps/Island", "World")
        mock_unreal.add_asset(
            "/ProjectX/Blueprints/BP_Loader", "Blueprint",
            deps=["/ProjectX/Maps/Island"])
        scan = [
            asset("/ProjectX/Maps/Island", "World"),
            asset("/ProjectX/Blueprints/BP_Loader", "Blueprint"),
        ]

        plan = self._plan(scan)

        move_paths = [m["path"] for m in plan["moves"]]
        self.assertNotIn("/ProjectX/Maps/Island", move_paths)
        skip_paths = [s["path"] for s in plan["skips"]]
        self.assertIn("/ProjectX/Maps/Island", skip_paths)
        # Never absorbed as a kit member: no destination anywhere nests it
        # under the Blueprint's kit folder.
        for m in plan["moves"]:
            self.assertNotIn("Island", m["dest_path"])

    def test_blueprint_kit_leaves_dependent_gamefeaturedata_untouched(self):
        mock_unreal.add_asset(
            "/ProjectX/ProjectXGameFeature", "GameFeatureData")
        mock_unreal.add_asset(
            "/ProjectX/Blueprints/BP_Loader", "Blueprint",
            deps=["/ProjectX/ProjectXGameFeature"])
        scan = [
            asset("/ProjectX/ProjectXGameFeature", "GameFeatureData"),
            asset("/ProjectX/Blueprints/BP_Loader", "Blueprint"),
        ]

        plan = self._plan(scan)

        move_paths = [m["path"] for m in plan["moves"]]
        self.assertNotIn("/ProjectX/ProjectXGameFeature", move_paths)
        grouping = plan.get("grouping")
        self.assertIsNotNone(grouping)
        for m in plan["moves"]:
            self.assertNotIn("ProjectXGameFeature", m["dest_path"])

    def test_never_move_asset_not_counted_as_kit_member_or_shared(self):
        """The protected asset must not show up in the grouping stats
        either (not a kit, not shared, not loose-counted as an eligible
        asset at all)."""
        mock_unreal.add_asset("/ProjectX/Maps/Island", "World")
        mock_unreal.add_asset(
            "/ProjectX/Blueprints/BP_A", "Blueprint",
            deps=["/ProjectX/Maps/Island"])
        mock_unreal.add_asset(
            "/ProjectX/Blueprints/BP_B", "Blueprint",
            deps=["/ProjectX/Maps/Island"])
        scan = [
            asset("/ProjectX/Maps/Island", "World"),
            asset("/ProjectX/Blueprints/BP_A", "Blueprint"),
            asset("/ProjectX/Blueprints/BP_B", "Blueprint"),
        ]

        plan = self._plan(scan)

        move_paths = [m["path"] for m in plan["moves"]]
        self.assertNotIn("/ProjectX/Maps/Island", move_paths)
        # Two independent Blueprint kits, neither one containing Island.
        for m in plan["moves"]:
            self.assertNotIn("Island", m["dest_path"])


if __name__ == "__main__":
    unittest.main()
