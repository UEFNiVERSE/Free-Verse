"""Tests for the group-by-asset sorting mode (dependency clustering).

Real-world grounding: imported props are KITS -- e.g.
/BrainrotMeshes/Alessio/ = SM_Alessio + MI_Bone_Alessio +
T_Bone_Position/Rotation/Weights, times ~90 kits. Flat per-type sorting
scatters each kit across /Meshes,/Materials,/Textures. The new mode keeps
kits together, with a CHAIN-NESTED layout: a member's destination nests
along its dependency path from the anchor, each hop appending that
member's type folder, consecutive same-type hops collapsed, shortest
dependency path winning (BFS discovery order tie-break over sorted deps).

Everything here is RED-first TDD against build_plan()'s grouping pass and
the new dependency_query capability probe.
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


def _register(assets):
    """add_asset() every (path, class, deps) triple and return the
    scan-shaped list build_plan() takes."""
    scan = []
    for path, class_name, deps in assets:
        mock_unreal.add_asset(path, class_name, deps=deps)
        scan.append(asset(path, class_name))
    return scan


def _moves_by_path(plan):
    return dict((m["path"], m) for m in plan["moves"])


class GroupingTestBase(unittest.TestCase):
    def setUp(self):
        self.sortilege = helpers.load_sortilege(
            config_overrides={"GROUP_BY_ASSET": True})

    def _plan(self, scan, config_overrides=None):
        config = dict(self.sortilege.CONFIG)
        if config_overrides:
            config.update(config_overrides)
        caps = self.sortilege.probe_capabilities()
        return self.sortilege.build_plan(scan, config, caps)


# ---------------------------------------------------------------------------
# Capability probe
# ---------------------------------------------------------------------------

class DependencyCapabilityTests(unittest.TestCase):
    def test_probe_reports_dependency_query_available(self):
        sortilege = helpers.load_sortilege()
        caps = sortilege.probe_capabilities()
        self.assertTrue(caps.dependency_query)

    def test_probe_reports_dependency_query_absent(self):
        sortilege = helpers.load_sortilege(features={"dependency_query": False})
        caps = sortilege.probe_capabilities()
        self.assertFalse(caps.dependency_query)

    def test_capability_appears_in_report(self):
        sortilege = helpers.load_sortilege()
        caps = sortilege.probe_capabilities()
        self.assertTrue(any("dependency_query" in line for line in caps.report()))


# ---------------------------------------------------------------------------
# The Alessio kit -- the real-world fixture shape
# ---------------------------------------------------------------------------

class AlessioKitTests(GroupingTestBase):
    def _scan(self):
        base = "/Game/BrainrotMeshes/Alessio"
        return _register([
            (base + "/SM_Alessio", "StaticMesh", [base + "/MI_Bone_Alessio"]),
            (base + "/MI_Bone_Alessio", "MaterialInstanceConstant", [
                base + "/T_Bone_Position", base + "/T_Bone_Rotation",
                base + "/T_Bone_Weights"]),
            (base + "/T_Bone_Position", "Texture2D", []),
            (base + "/T_Bone_Rotation", "Texture2D", []),
            (base + "/T_Bone_Weights", "Texture2D", []),
        ])

    def test_kit_stays_together_chain_nested(self):
        plan = self._plan(self._scan())
        moves = _moves_by_path(plan)
        base = "/Game/BrainrotMeshes/Alessio"

        self.assertEqual(moves[base + "/SM_Alessio"]["dest_path"],
                          "/Game/Meshes/Alessio/SM_Alessio")
        self.assertEqual(moves[base + "/MI_Bone_Alessio"]["dest_path"],
                          "/Game/Meshes/Alessio/Materials/MI_Bone_Alessio")
        for tex in ("T_Bone_Position", "T_Bone_Rotation", "T_Bone_Weights"):
            self.assertEqual(moves[base + "/" + tex]["dest_path"],
                              "/Game/Meshes/Alessio/Materials/Textures/" + tex)

    def test_kit_name_strips_anchor_class_prefix(self):
        plan = self._plan(self._scan())
        moves = _moves_by_path(plan)
        # SM_Alessio -> kit folder "Alessio", not "SM_Alessio".
        self.assertIn("/Alessio/", moves["/Game/BrainrotMeshes/Alessio/SM_Alessio"]["dest_path"])
        self.assertNotIn("/SM_Alessio/", moves["/Game/BrainrotMeshes/Alessio/SM_Alessio"]["dest_path"])

    def test_grouping_stats_on_plan(self):
        plan = self._plan(self._scan())
        grouping = plan.get("grouping")
        self.assertIsNotNone(grouping)
        self.assertEqual(grouping["kits"], 1)
        self.assertEqual(grouping["shared"], 0)
        self.assertEqual(grouping["loose"], 0)

    def test_grouping_header_line_in_preview(self):
        plan = self._plan(self._scan())
        text = "\n".join(self.sortilege.format_preview(plan))
        self.assertIn("Grouping: by asset (1 kits, 0 shared, 0 loose)", text)

    def test_no_grouping_header_when_mode_off(self):
        scan = self._scan()
        plan = self._plan(scan, config_overrides={"GROUP_BY_ASSET": False})
        self.assertNotIn("grouping", plan)
        text = "\n".join(self.sortilege.format_preview(plan))
        self.assertNotIn("Grouping:", text)


# ---------------------------------------------------------------------------
# Full BP -> SM -> MI -> T chain (the amendment's canonical example)
# ---------------------------------------------------------------------------

class ChainNestedLayoutTests(GroupingTestBase):
    def test_full_chain_bp_sm_mi_t(self):
        scan = _register([
            ("/Game/Stuff/BP_LuckyBlock", "Blueprint", ["/Game/Stuff/SM_LuckyBlock"]),
            ("/Game/Stuff/SM_LuckyBlock", "StaticMesh", ["/Game/Stuff/MI_LuckyBlock"]),
            ("/Game/Stuff/MI_LuckyBlock", "MaterialInstanceConstant",
             ["/Game/Stuff/T_LuckyBlock_D"]),
            ("/Game/Stuff/T_LuckyBlock_D", "Texture2D", []),
        ])
        plan = self._plan(scan)
        moves = _moves_by_path(plan)

        self.assertEqual(moves["/Game/Stuff/BP_LuckyBlock"]["dest_path"],
                          "/Game/Props/LuckyBlock/BP_LuckyBlock")
        self.assertEqual(moves["/Game/Stuff/SM_LuckyBlock"]["dest_path"],
                          "/Game/Props/LuckyBlock/Meshes/SM_LuckyBlock")
        self.assertEqual(moves["/Game/Stuff/MI_LuckyBlock"]["dest_path"],
                          "/Game/Props/LuckyBlock/Meshes/Materials/MI_LuckyBlock")
        self.assertEqual(moves["/Game/Stuff/T_LuckyBlock_D"]["dest_path"],
                          "/Game/Props/LuckyBlock/Meshes/Materials/Textures/T_LuckyBlock_D")

    def test_anchor_priority_bp_owns_its_staticmesh(self):
        """A StaticMesh referenced by a Blueprint is part of the BP's kit,
        never its own anchor -- Blueprint outranks StaticMesh in
        GROUP_ANCHOR_CLASSES."""
        scan = _register([
            ("/Game/Stuff/BP_X", "Blueprint", ["/Game/Stuff/SM_Y"]),
            ("/Game/Stuff/SM_Y", "StaticMesh", []),
        ])
        plan = self._plan(scan)
        moves = _moves_by_path(plan)
        grouping = plan["grouping"]

        self.assertEqual(grouping["kits"], 1)
        self.assertEqual(moves["/Game/Stuff/SM_Y"]["dest_path"],
                          "/Game/Props/X/Meshes/SM_Y")

    def test_same_type_consecutive_hops_collapse(self):
        """A Material depending on a MaterialFunction: both category
        Materials -> ONE Materials segment; the MF sits beside the M,
        never Materials/Materials."""
        scan = _register([
            ("/Game/Stuff/SM_Rock", "StaticMesh", ["/Game/Stuff/M_Master"]),
            ("/Game/Stuff/M_Master", "Material", ["/Game/Stuff/MF_Noise"]),
            ("/Game/Stuff/MF_Noise", "MaterialFunction", []),
        ])
        plan = self._plan(scan)
        moves = _moves_by_path(plan)

        self.assertEqual(moves["/Game/Stuff/M_Master"]["dest_path"],
                          "/Game/Meshes/Rock/Materials/M_Master")
        self.assertEqual(moves["/Game/Stuff/MF_Noise"]["dest_path"],
                          "/Game/Meshes/Rock/Materials/MF_Noise")

    def test_diamond_shortest_path_wins(self):
        """An asset reachable both directly from the anchor (1 hop) and
        through a material (2 hops) nests along the SHORTEST path."""
        scan = _register([
            ("/Game/Stuff/SM_D", "StaticMesh",
             ["/Game/Stuff/M_A", "/Game/Stuff/T_X"]),
            ("/Game/Stuff/M_A", "Material", ["/Game/Stuff/T_X"]),
            ("/Game/Stuff/T_X", "Texture2D", []),
        ])
        plan = self._plan(scan)
        moves = _moves_by_path(plan)

        self.assertEqual(moves["/Game/Stuff/T_X"]["dest_path"],
                          "/Game/Meshes/D/Textures/T_X")

    def test_diamond_equal_length_tiebreak_is_bfs_order_over_sorted_deps(self):
        """Two equal-length paths to the same dep: the winner is BFS
        discovery order with sorted dependency iteration -- M_mat sorts
        before S_snd, so T_Y nests under the Materials chain, and the
        result is stable run to run."""
        scan = _register([
            ("/Game/Stuff/BP_T", "Blueprint",
             ["/Game/Stuff/S_snd", "/Game/Stuff/M_mat"]),
            ("/Game/Stuff/M_mat", "Material", ["/Game/Stuff/T_Y"]),
            ("/Game/Stuff/S_snd", "SoundWave", ["/Game/Stuff/T_Y"]),
            ("/Game/Stuff/T_Y", "Texture2D", []),
        ])
        plan = self._plan(scan)
        moves = _moves_by_path(plan)

        self.assertEqual(moves["/Game/Stuff/T_Y"]["dest_path"],
                          "/Game/Props/T/Materials/Textures/T_Y")

    def test_cycle_in_dependencies_terminates_and_groups(self):
        scan = _register([
            ("/Game/Stuff/SM_A", "StaticMesh", ["/Game/Stuff/M_B"]),
            ("/Game/Stuff/M_B", "Material", ["/Game/Stuff/SM_A"]),
        ])
        plan = self._plan(scan)  # must not hang
        moves = _moves_by_path(plan)

        self.assertEqual(moves["/Game/Stuff/SM_A"]["dest_path"],
                          "/Game/Meshes/A/SM_A")
        self.assertEqual(moves["/Game/Stuff/M_B"]["dest_path"],
                          "/Game/Meshes/A/Materials/M_B")


# ---------------------------------------------------------------------------
# Shared members, loose assets, fallbacks, skip rules
# ---------------------------------------------------------------------------

class SharedAndLooseTests(GroupingTestBase):
    def test_member_of_two_kits_goes_to_shared(self):
        scan = _register([
            ("/Game/Stuff/SM_A", "StaticMesh", ["/Game/Stuff/T_S"]),
            ("/Game/Stuff/SM_B", "StaticMesh", ["/Game/Stuff/T_S"]),
            ("/Game/Stuff/T_S", "Texture2D", []),
        ])
        plan = self._plan(scan)
        moves = _moves_by_path(plan)
        grouping = plan["grouping"]

        self.assertEqual(moves["/Game/Stuff/T_S"]["dest_path"],
                          "/Game/Shared/Textures/T_S")
        self.assertEqual(grouping["kits"], 2)
        self.assertEqual(grouping["shared"], 1)

    def test_unanchored_assets_fall_back_flat(self):
        scan = _register([
            ("/Game/Stuff/SM_A", "StaticMesh", []),
            ("/Game/Stuff/S_Long", "SoundWave", []),
        ])
        plan = self._plan(scan)
        moves = _moves_by_path(plan)
        grouping = plan["grouping"]

        # SoundWave is no anchor class and in no closure: flat, as today.
        self.assertEqual(moves["/Game/Stuff/S_Long"]["dest_path"],
                          "/Game/Audio/S_Long")
        self.assertEqual(grouping["loose"], 1)

    def test_capability_absent_falls_back_flat_with_warning(self):
        sortilege = helpers.load_sortilege(
            features={"dependency_query": False},
            config_overrides={"GROUP_BY_ASSET": True})
        mock_unreal.add_asset("/Game/Stuff/SM_A", "StaticMesh",
                               deps=["/Game/Stuff/T_S"])
        mock_unreal.add_asset("/Game/Stuff/T_S", "Texture2D")
        scan = [asset("/Game/Stuff/SM_A", "StaticMesh"),
                asset("/Game/Stuff/T_S", "Texture2D")]
        caps = sortilege.probe_capabilities()
        self.assertFalse(caps.dependency_query)

        plan = sortilege.build_plan(scan, sortilege.CONFIG, caps)
        moves = _moves_by_path(plan)

        self.assertNotIn("grouping", plan)
        self.assertEqual(moves["/Game/Stuff/SM_A"]["dest_path"],
                          "/Game/Meshes/SM_A")
        self.assertEqual(moves["/Game/Stuff/T_S"]["dest_path"],
                          "/Game/Textures/T_S")
        logged = "\n".join(str(l) for l in mock_unreal.get_state()["log"]).lower()
        self.assertIn("grouping unavailable", logged)

    def test_excluded_dependency_never_enters_a_kit(self):
        scan = _register([
            ("/Game/Stuff/SM_K", "StaticMesh", ["/Game/KeepOut/T_Excl"]),
            ("/Game/KeepOut/T_Excl", "Texture2D", []),
        ])
        plan = self._plan(scan, config_overrides={
            "EXCLUDE_FOLDERS": ["/Game/KeepOut"]})
        moves = _moves_by_path(plan)

        self.assertNotIn("/Game/KeepOut/T_Excl", moves)
        skip_reasons = dict((s["path"], s["reason"]) for s in plan["skips"])
        self.assertEqual(skip_reasons.get("/Game/KeepOut/T_Excl"), "excluded folder")
        # The kit still forms around what IS movable.
        self.assertEqual(moves["/Game/Stuff/SM_K"]["dest_path"],
                          "/Game/Meshes/K/SM_K")

    def test_verse_dependency_never_enters_a_kit(self):
        scan = _register([
            ("/Game/Stuff/SM_V", "StaticMesh", ["/Game/Stuff/VerseThing"]),
            ("/Game/Stuff/VerseThing", "VerseClass", []),
        ])
        plan = self._plan(scan)
        moves = _moves_by_path(plan)

        self.assertNotIn("/Game/Stuff/VerseThing", moves)
        skip_paths = [s["path"] for s in plan["skips"]]
        self.assertIn("/Game/Stuff/VerseThing", skip_paths)

    def test_anchor_without_prefix_uses_full_name_as_kit(self):
        scan = _register([
            ("/Game/Stuff/Boulder", "StaticMesh", ["/Game/Stuff/T_B"]),
            ("/Game/Stuff/T_B", "Texture2D", []),
        ])
        plan = self._plan(scan)
        moves = _moves_by_path(plan)

        self.assertEqual(moves["/Game/Stuff/Boulder"]["dest_path"],
                          "/Game/Meshes/Boulder/Boulder")
        self.assertEqual(moves["/Game/Stuff/T_B"]["dest_path"],
                          "/Game/Meshes/Boulder/Textures/T_B")

    def test_sort_root_honored_in_grouped_destinations(self):
        scan = _register([
            ("/Game/Stuff/SM_A", "StaticMesh", ["/Game/Stuff/T_A"]),
            ("/Game/Stuff/T_A", "Texture2D", []),
        ])
        plan = self._plan(scan, config_overrides={"SORT_ROOT": "_Organized"})
        moves = _moves_by_path(plan)

        self.assertEqual(moves["/Game/Stuff/SM_A"]["dest_path"],
                          "/Game/_Organized/Meshes/A/SM_A")
        self.assertEqual(moves["/Game/Stuff/T_A"]["dest_path"],
                          "/Game/_Organized/Meshes/A/Textures/T_A")


# ---------------------------------------------------------------------------
# Deterministic kit formation -- review fix (IMPORTANT): an anchor whose
# dependency chain reaches ANOTHER anchor of the same (or higher) priority
# class used to be order-dependent: scan order decided whether the second
# anchor formed its own kit, and when it did, the member-override loop
# clobbered its anchor destination and its deps got misrouted to Shared
# off a phantom double-count. Anchor-to-anchor edges are KIT BOUNDARIES.
# ---------------------------------------------------------------------------

class DeterministicKitFormationTests(unittest.TestCase):
    def _plan_for_order(self, entries):
        """Fresh module + fresh mock, assets registered AND scanned in the
        given order, plan built with grouping on."""
        sortilege = helpers.load_sortilege(
            config_overrides={"GROUP_BY_ASSET": True})
        scan = _register(entries)
        caps = sortilege.probe_capabilities()
        plan = sortilege.build_plan(scan, sortilege.CONFIG, caps)
        return plan

    def _bp_bp_m_entries(self):
        return [
            ("/Game/Stuff/BP_Alpha", "Blueprint", ["/Game/Stuff/BP_Beta"]),
            ("/Game/Stuff/BP_Beta", "Blueprint", ["/Game/Stuff/M_x"]),
            ("/Game/Stuff/M_x", "Material", []),
        ]

    def test_same_class_anchor_chain_identical_plans_both_scan_orders(self):
        entries = self._bp_bp_m_entries()
        plan_fwd = self._plan_for_order(entries)
        plan_rev = self._plan_for_order(list(reversed(entries)))

        dests_fwd = dict((m["path"], m["dest_path"]) for m in plan_fwd["moves"])
        dests_rev = dict((m["path"], m["dest_path"]) for m in plan_rev["moves"])
        self.assertEqual(dests_fwd, dests_rev)
        self.assertEqual(plan_fwd["grouping"], plan_rev["grouping"])

        # Two REAL kits: each Blueprint owns its own folder; the
        # anchor-to-anchor edge is a boundary, never an absorption.
        self.assertEqual(plan_fwd["grouping"]["kits"], 2)
        self.assertEqual(plan_fwd["grouping"]["shared"], 0)
        self.assertEqual(dests_fwd["/Game/Stuff/BP_Alpha"],
                          "/Game/Props/Alpha/BP_Alpha")
        # BP_Beta's own anchor destination is FINAL -- never clobbered by
        # BP_Alpha's member routing.
        self.assertEqual(dests_fwd["/Game/Stuff/BP_Beta"],
                          "/Game/Props/Beta/BP_Beta")
        # M_x lives inside BP_Beta's kit -- no phantom double-count, no
        # Shared misroute.
        self.assertEqual(dests_fwd["/Game/Stuff/M_x"],
                          "/Game/Props/Beta/Materials/M_x")
        for dest in dests_fwd.values():
            self.assertFalse(dest.startswith("/Game/Shared"),
                             "nothing here is genuinely shared: %s" % dest)

    def test_three_level_same_class_chain_deterministic(self):
        entries = [
            ("/Game/Stuff/BP_One", "Blueprint", ["/Game/Stuff/BP_Two"]),
            ("/Game/Stuff/BP_Two", "Blueprint", ["/Game/Stuff/BP_Three"]),
            ("/Game/Stuff/BP_Three", "Blueprint", []),
        ]
        plan_fwd = self._plan_for_order(entries)
        plan_rev = self._plan_for_order(list(reversed(entries)))

        dests_fwd = dict((m["path"], m["dest_path"]) for m in plan_fwd["moves"])
        dests_rev = dict((m["path"], m["dest_path"]) for m in plan_rev["moves"])
        self.assertEqual(dests_fwd, dests_rev)
        self.assertEqual(plan_fwd["grouping"]["kits"], 3)
        self.assertEqual(plan_fwd["grouping"]["shared"], 0)
        self.assertEqual(dests_fwd["/Game/Stuff/BP_One"],
                          "/Game/Props/One/BP_One")
        self.assertEqual(dests_fwd["/Game/Stuff/BP_Two"],
                          "/Game/Props/Two/BP_Two")
        self.assertEqual(dests_fwd["/Game/Stuff/BP_Three"],
                          "/Game/Props/Three/BP_Three")

    def test_lower_priority_anchor_class_still_absorbed_both_orders(self):
        """The boundary applies to same-or-HIGHER priority anchor classes
        only: a Blueprint still absorbs its StaticMesh (lower priority)
        regardless of scan order."""
        entries = [
            ("/Game/Stuff/BP_X", "Blueprint", ["/Game/Stuff/SM_Y"]),
            ("/Game/Stuff/SM_Y", "StaticMesh", []),
        ]
        for variant in (entries, list(reversed(entries))):
            plan = self._plan_for_order(variant)
            dests = dict((m["path"], m["dest_path"]) for m in plan["moves"])
            self.assertEqual(plan["grouping"]["kits"], 1)
            self.assertEqual(dests["/Game/Stuff/SM_Y"],
                              "/Game/Props/X/Meshes/SM_Y")

    def test_higher_priority_anchor_reached_from_lower_is_a_boundary(self):
        """A StaticMesh anchor whose chain reaches a Blueprint: the BP is
        higher priority -- boundary, own kit, never absorbed downward."""
        entries = [
            ("/Game/Stuff/SM_Base", "StaticMesh", ["/Game/Stuff/BP_Logic"]),
            ("/Game/Stuff/BP_Logic", "Blueprint", []),
        ]
        for variant in (entries, list(reversed(entries))):
            plan = self._plan_for_order(variant)
            dests = dict((m["path"], m["dest_path"]) for m in plan["moves"])
            self.assertEqual(plan["grouping"]["kits"], 2)
            self.assertEqual(dests["/Game/Stuff/BP_Logic"],
                              "/Game/Props/Logic/BP_Logic")
            self.assertEqual(dests["/Game/Stuff/SM_Base"],
                              "/Game/Meshes/Base/SM_Base")


# ---------------------------------------------------------------------------
# Deep-chain destination-length warning -- review fix (MINOR 2)
# ---------------------------------------------------------------------------

class LongDestinationWarningTests(GroupingTestBase):
    def _deep_chain_scan(self, hops):
        """Anchor + `hops` nested single-dep members with alternating
        categories (Materials / Audio) so no same-type collapse shortens
        the chain -- destinations grow ~10 chars per hop."""
        entries = []
        paths = ["/Game/Stuff/BP_Chain"]
        for i in range(hops):
            cls = "Material" if i % 2 == 0 else "SoundWave"
            prefix = "M_n" if i % 2 == 0 else "S_n"
            paths.append("/Game/Stuff/%s%03d" % (prefix, i))
        for i in range(len(paths)):
            cls = ("Blueprint" if i == 0
                   else ("Material" if (i - 1) % 2 == 0 else "SoundWave"))
            deps = [paths[i + 1]] if i + 1 < len(paths) else []
            entries.append((paths[i], cls, deps))
        return _register(entries)

    def test_forty_hop_chain_warns_with_correct_count(self):
        plan = self._plan(self._deep_chain_scan(40))
        moves = plan["moves"]
        long_count = sum(1 for m in moves if len(m["dest_path"]) > 200)
        self.assertGreater(long_count, 0)

        lines = self.sortilege.format_preview(plan)
        text = "\n".join(lines)
        self.assertIn(
            "%d destination path(s) are very long and may fail to move on "
            "this platform; consider flat mode or a shallower FOLDER_MAP"
            % long_count, text)
        # Each long item is marked in the table.
        marked = [l for l in lines if l.rstrip().endswith("!")]
        self.assertEqual(len(marked), long_count)

    def test_short_plans_have_no_length_warning(self):
        scan = _register([
            ("/Game/Stuff/SM_A", "StaticMesh", ["/Game/Stuff/T_A"]),
            ("/Game/Stuff/T_A", "Texture2D", []),
        ])
        plan = self._plan(scan)
        text = "\n".join(self.sortilege.format_preview(plan))
        self.assertNotIn("very long", text)
        self.assertNotIn(" !", text)


if __name__ == "__main__":
    unittest.main()
