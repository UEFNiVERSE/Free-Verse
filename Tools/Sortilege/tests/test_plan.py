"""Tests for sortilege.py's build_plan() -- the pure plan-building logic
that turns a scanned asset list into moves/renames/skips.

sortilege.py does not exist until Task 2 implements it; these tests are
written first (TDD). Every test loads a fresh module + mock via
helpers.load_sortilege() (build_plan calls discover_content_roots()
internally, so the mock's project root must be set up first) then hands
build_plan a hand-built list of asset dicts shaped like scan_assets()'s
output: {"path", "name", "folder", "class_name"}.
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


class BuildPlanHappyPathTests(unittest.TestCase):
    def setUp(self):
        self.sortilege = helpers.load_sortilege()
        # Default mock project root is "/Game" -- use it for every test in
        # this file unless a test explicitly needs a different mount.

    def test_happy_path_move(self):
        assets = [asset("/Game/Stuff/Rock", "StaticMesh")]
        plan = self.sortilege.build_plan(assets, self.sortilege.CONFIG,
                                          self.sortilege.probe_capabilities())

        self.assertEqual(len(plan["moves"]), 1)
        move = plan["moves"][0]
        self.assertEqual(move["path"], "/Game/Stuff/Rock")
        self.assertEqual(move["category"], "Meshes")
        self.assertEqual(move["dest_folder"], "/Game/Meshes")
        self.assertEqual(move["dest_path"], "/Game/Meshes/Rock")
        self.assertEqual(move["action"], "move")
        self.assertEqual(move["new_name"], "Rock")
        self.assertEqual(plan["skips"], [])
        self.assertEqual(plan["stats"]["scanned"], 1)
        self.assertEqual(plan["stats"]["moves"], 1)
        self.assertEqual(plan["stats"]["renames"], 0)
        self.assertEqual(plan["stats"]["skips"], 0)
        self.assertEqual(plan["stats"]["by_category"], {"Meshes": 1})
        self.assertEqual(plan["content_root"], "/Game")
        self.assertEqual(plan["sort_root"], "")
        self.assertIn("timestamp", plan)

    def test_already_sorted_skip(self):
        assets = [asset("/Game/Meshes/Rock", "StaticMesh")]
        plan = self.sortilege.build_plan(assets, self.sortilege.CONFIG,
                                          self.sortilege.probe_capabilities())

        self.assertEqual(plan["moves"], [])
        self.assertEqual(len(plan["skips"]), 1)
        self.assertEqual(plan["skips"][0]["reason"], "already sorted")

    def test_destination_occupied_collision(self):
        assets = [
            asset("/Game/Stuff/Rock", "StaticMesh"),
            asset("/Game/Meshes/Rock", "StaticMesh"),
        ]
        plan = self.sortilege.build_plan(assets, self.sortilege.CONFIG,
                                          self.sortilege.probe_capabilities())

        skip_paths = {s["path"]: s["reason"] for s in plan["skips"]}
        self.assertEqual(skip_paths.get("/Game/Stuff/Rock"), "destination occupied")
        # the already-sorted one is its own skip, not a move
        self.assertEqual(len(plan["moves"]), 0)

    def test_name_collision_with_planned_move(self):
        assets = [
            asset("/Game/Stuff/Rock", "StaticMesh"),
            asset("/Game/Other/Rock", "StaticMesh"),
        ]
        plan = self.sortilege.build_plan(assets, self.sortilege.CONFIG,
                                          self.sortilege.probe_capabilities())

        self.assertEqual(len(plan["moves"]), 1)
        self.assertEqual(plan["moves"][0]["path"], "/Game/Stuff/Rock")
        skip_paths = {s["path"]: s["reason"] for s in plan["skips"]}
        self.assertEqual(skip_paths.get("/Game/Other/Rock"), "name collision with planned move")

    def test_wrong_prefix_strip(self):
        config = dict(self.sortilege.CONFIG)
        config["ENABLE_PREFIX_RENAME"] = True
        assets = [asset("/Game/Stuff/T_Rock", "StaticMesh")]
        plan = self.sortilege.build_plan(assets, config, self.sortilege.probe_capabilities())

        self.assertEqual(len(plan["moves"]), 1)
        move = plan["moves"][0]
        self.assertEqual(move["new_name"], "SM_Rock")
        self.assertEqual(move["dest_path"], "/Game/Meshes/SM_Rock")
        self.assertEqual(move["action"], "move+rename")

    def test_rename_only_action_when_already_in_dest_folder(self):
        config = dict(self.sortilege.CONFIG)
        config["ENABLE_PREFIX_RENAME"] = True
        assets = [asset("/Game/Meshes/Rock", "StaticMesh")]
        plan = self.sortilege.build_plan(assets, config, self.sortilege.probe_capabilities())

        self.assertEqual(len(plan["moves"]), 1)
        move = plan["moves"][0]
        self.assertEqual(move["action"], "rename")
        self.assertEqual(move["dest_folder"], "/Game/Meshes")
        self.assertEqual(move["new_name"], "SM_Rock")
        self.assertEqual(move["dest_path"], "/Game/Meshes/SM_Rock")

    def test_prefix_rename_off_leaves_already_sorted_as_skip(self):
        # ENABLE_PREFIX_RENAME defaults to False -- a wrongly-prefixed but
        # already-in-place asset should just be "already sorted".
        assets = [asset("/Game/Meshes/T_Rock", "StaticMesh")]
        plan = self.sortilege.build_plan(assets, self.sortilege.CONFIG,
                                          self.sortilege.probe_capabilities())
        self.assertEqual(plan["moves"], [])
        self.assertEqual(plan["skips"][0]["reason"], "already sorted")

    def test_sort_root_prefixing(self):
        config = dict(self.sortilege.CONFIG)
        config["SORT_ROOT"] = "_Organized"
        assets = [asset("/Game/Stuff/Rock", "StaticMesh")]
        plan = self.sortilege.build_plan(assets, config, self.sortilege.probe_capabilities())

        self.assertEqual(len(plan["moves"]), 1)
        move = plan["moves"][0]
        self.assertEqual(move["dest_folder"], "/Game/_Organized/Meshes")
        self.assertEqual(move["dest_path"], "/Game/_Organized/Meshes/Rock")
        self.assertEqual(plan["sort_root"], "_Organized")

    def test_exclude_folders(self):
        config = dict(self.sortilege.CONFIG)
        config["EXCLUDE_FOLDERS"] = ["/Game/DoNotTouch"]
        assets = [asset("/Game/DoNotTouch/Rock", "StaticMesh")]
        plan = self.sortilege.build_plan(assets, config, self.sortilege.probe_capabilities())

        self.assertEqual(plan["moves"], [])
        self.assertEqual(plan["skips"][0]["reason"], "excluded folder")

    def test_invalid_target_name_skip(self):
        config = dict(self.sortilege.CONFIG)
        config["ENABLE_PREFIX_RENAME"] = True
        assets = [asset("/Game/Stuff/Bad:Name", "StaticMesh")]
        plan = self.sortilege.build_plan(assets, config, self.sortilege.probe_capabilities())

        self.assertEqual(plan["moves"], [])
        self.assertEqual(plan["skips"][0]["reason"], "invalid target name")

    def test_outside_project_content_skip(self):
        assets = [asset("/OtherMount/Stuff/Rock", "StaticMesh")]
        plan = self.sortilege.build_plan(assets, self.sortilege.CONFIG,
                                          self.sortilege.probe_capabilities())

        self.assertEqual(plan["moves"], [])
        self.assertEqual(plan["skips"][0]["reason"], "outside project content")

    def test_protected_class_skip(self):
        assets = [asset("/Game/Verse/MyDevice", "VerseClass")]
        plan = self.sortilege.build_plan(assets, self.sortilege.CONFIG,
                                          self.sortilege.probe_capabilities())
        self.assertEqual(plan["moves"], [])
        self.assertIn("Verse", plan["skips"][0]["reason"])

    def test_protected_path_skip(self):
        assets = [asset("/Game/__ExternalActors__/0/1/ABCDEF", "StaticMesh")]
        plan = self.sortilege.build_plan(assets, self.sortilege.CONFIG,
                                          self.sortilege.probe_capabilities())
        self.assertEqual(plan["moves"], [])
        self.assertEqual(plan["skips"][0]["reason"], "protected system folder")


class BuildPlanScopeFoldersIntegrationTests(unittest.TestCase):
    def test_scan_then_plan_with_scope_folders(self):
        sortilege = helpers.load_sortilege()
        mock_unreal.set_project_root("/ProjectX")
        mock_unreal.add_asset("/ProjectX/OldStuff/Rock", "StaticMesh")
        mock_unreal.add_asset("/ProjectX/Blueprints/BP_User", "Blueprint")

        assets = sortilege.scan_assets(["/ProjectX/OldStuff"])
        plan = sortilege.build_plan(assets, sortilege.CONFIG, sortilege.probe_capabilities())

        self.assertEqual(plan["stats"]["scanned"], 1)
        self.assertEqual(len(plan["moves"]), 1)
        move = plan["moves"][0]
        self.assertEqual(move["path"], "/ProjectX/OldStuff/Rock")
        # dest folder is relative to the real content root, not the scope
        # folder the asset happened to be scanned from.
        self.assertEqual(move["dest_folder"], "/ProjectX/Meshes")


class BuildPlanMultiRootTests(unittest.TestCase):
    def test_asset_under_a_secondary_discovered_root_is_planned_not_skipped(self):
        """Regression: build_plan() only checked membership against
        roots[0] (discover_content_roots()'s PRIMARY mount), so on the
        fallback path where multiple mounts are discovered, anything
        under mount 2+ was wrongly skipped "outside project content".
        The membership check must accept ANY discovered root; the
        PRIMARY root is still used for computing the destination folder."""
        sortilege = helpers.load_sortilege()
        # Force the multi-mount fallback path deterministically -- which
        # of two same-priority mounts discover_content_roots() lists
        # first is not something worth pinning here (it walks an
        # unordered folder set on the real fallback path); this test is
        # about build_plan()'s membership check, not root ordering.
        sortilege.discover_content_roots = lambda: ["/ProjectX", "/Mount2"]

        assets = [asset("/Mount2/Stuff/Rock", "StaticMesh")]
        plan = sortilege.build_plan(assets, sortilege.CONFIG, sortilege.probe_capabilities())

        self.assertEqual(plan["skips"], [])
        self.assertEqual(len(plan["moves"]), 1)
        move = plan["moves"][0]
        self.assertEqual(move["path"], "/Mount2/Stuff/Rock")
        # Destination is computed against the PRIMARY root (roots[0]),
        # not the secondary mount the asset actually lives under.
        self.assertEqual(move["dest_folder"], "/ProjectX/Meshes")
        self.assertEqual(move["dest_path"], "/ProjectX/Meshes/Rock")
        self.assertEqual(plan["content_root"], "/ProjectX")

    def test_asset_outside_every_discovered_root_is_still_skipped(self):
        sortilege = helpers.load_sortilege()
        sortilege.discover_content_roots = lambda: ["/ProjectX", "/Mount2"]

        assets = [asset("/SomeOtherMount/Stuff/Rock", "StaticMesh")]
        plan = sortilege.build_plan(assets, sortilege.CONFIG, sortilege.probe_capabilities())

        self.assertEqual(plan["moves"], [])
        self.assertEqual(plan["skips"][0]["reason"], "outside project content")


if __name__ == "__main__":
    unittest.main()
