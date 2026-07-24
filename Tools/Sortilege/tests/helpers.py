"""Test bootstrap: injects mock_unreal as `unreal` and loads sortilege.py fresh.

Every test module that needs sortilege.py should call load_sortilege()
instead of importing sortilege directly, so each test gets a clean mock
project state and a freshly-executed module (no stale globals leaking
between tests).
"""
import importlib.util
import os
import sys

import mock_unreal


def load_sortilege(features=None, config_overrides=None):
    """Reset the mock, inject it as `unreal`, (re)load sortilege.py from the
    Sortilege project root, apply CONFIG overrides, and return the module.

    USE_GUI defaults to False here regardless of sortilege.py's own CONFIG
    default (True) unless a test explicitly overrides it -- this test
    environment can genuinely construct a real tk.Tk() (no headless
    display restriction), and main(mode="preview") would otherwise try to
    open a real window and block in mainloop() with nobody there to close
    it. Tests that specifically exercise the GUI layer pass
    config_overrides={"USE_GUI": True} (paired with either the tkinter-
    absent trick or a call that never reaches mainloop())."""
    mock_unreal.reset(features=features)
    sys.modules["unreal"] = mock_unreal

    sys.modules.pop("sortilege", None)

    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sortilege_path = os.path.join(project_root, "sortilege.py")

    spec = importlib.util.spec_from_file_location("sortilege", sortilege_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["sortilege"] = module
    spec.loader.exec_module(module)

    module.CONFIG["USE_GUI"] = False
    if config_overrides:
        module.CONFIG.update(config_overrides)

    return module
