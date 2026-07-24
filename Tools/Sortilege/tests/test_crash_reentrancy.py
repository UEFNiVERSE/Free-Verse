"""Regression tests for the GUI-vs-native-progress-UI reentrancy crash.

Field failure (2026-07-23): a GUI-driven Apply froze for a few seconds then
instantly hard-crashed UEFN with no crash reporter. Cause: the tkinter window
runs its own event loop on the editor's single main thread, and the apply
path ALSO spun up UEFN's native unreal.ScopedSlowTask modal progress dialog.
Two UI event loops reentering each other on one thread is an instant native
crash. Fix: when a run is GUI-driven (extra_progress is not None), skip the
native ScopedSlowTask entirely -- the tkinter window is the progress UI. A
console run (extra_progress is None) still uses the native progress bar.
"""
import os
import sys
import tempfile
import shutil
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import helpers
import mock_unreal


def _asset(path, class_name):
    folder, name = path.rsplit("/", 1)
    return {"path": path, "name": name, "folder": folder, "class_name": class_name}


class GuiSkipsNativeSlowTaskTests(unittest.TestCase):
    def setUp(self):
        self.s = helpers.load_sortilege()
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _plan_and_log(self):
        mock_unreal.add_asset("/Game/Stuff/Rock", "StaticMesh")
        assets = [_asset("/Game/Stuff/Rock", "StaticMesh")]
        plan = self.s.build_plan(assets, self.s.CONFIG, self.s.probe_capabilities())
        undo = self.s.UndoLog.begin(self.tmp, plan)
        return plan, undo

    def test_gui_run_never_enters_native_scoped_slow_task(self):
        """extra_progress present (GUI) -> the native ScopedSlowTask scope is
        never even entered, so the two UI loops can never collide."""
        caps = self.s.probe_capabilities()
        self.assertTrue(caps.scoped_slow_task)  # available on this build
        plan, undo = self._plan_and_log()
        pumped = []

        self.s._run_with_progress(plan, caps, undo,
                                  extra_progress=lambda m: pumped.append(m))

        log = "\n".join(mock_unreal.get_state()["log"])
        self.assertNotIn("ScopedSlowTask enter", log)
        # ...but the GUI progress hook still fired (the window still repaints).
        self.assertTrue(pumped)
        # ...and the move still actually happened.
        self.assertTrue(unreal_moved("/Game/Meshes/Rock"))

    def test_console_run_still_uses_native_scoped_slow_task(self):
        """extra_progress is None (console) -> the native progress bar is kept
        exactly as before; this is the path that showed the working progress
        bar in the field."""
        caps = self.s.probe_capabilities()
        plan, undo = self._plan_and_log()

        self.s._run_with_progress(plan, caps, undo, extra_progress=None)

        log = "\n".join(mock_unreal.get_state()["log"])
        self.assertIn("ScopedSlowTask enter", log)
        self.assertTrue(unreal_moved("/Game/Meshes/Rock"))


def unreal_moved(path):
    return mock_unreal.EditorAssetLibrary.does_asset_exist(path)


if __name__ == "__main__":
    unittest.main()
