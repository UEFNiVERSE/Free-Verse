# Sortilege

Sortilege is a single file (`sortilege.py`) that you run inside UEFN. It scans your project's Content Drawer (the panel that lists every asset in your project, also called the Content Browser), figures out what type each asset is, and sorts everything into tidy folders: Meshes, Materials, Textures, Audio, Animations, Props, UI, VFX, and Other.

By default it only shows you a preview of what it *would* do. It changes nothing until you deliberately flip one setting and re-run it.

This README is written for someone who does not write code. Every technical term used below gets a one-line plain-language explanation the first time it shows up.

---

## What this does

1. Scans your project's assets (meshes, materials, textures, sounds, animations, blueprints, widgets, VFX, and so on).
2. Sorts each one into a matching folder (for example, all Static Meshes go into a "Meshes" folder).
3. Shows you a full preview of every move before touching anything (this is called a "dry run", meaning a rehearsal with nothing actually happening).
4. Only makes real changes after you flip one setting in the file and confirm a second time.
5. Moves assets using the engine's own safe move tool, so anything else in your project that points at those assets keeps working.
6. Cleans up the small leftover "pointer" files (called redirectors, explained below) that Unreal creates after a move, on a best-effort basis.
7. Writes a plain-text report after every run listing exactly what moved, what was skipped, and why.
8. Can undo an entire run later if you change your mind.
9. When your Verse code refers to a moved asset by its folder-qualified name, rewrites that reference in your `.verse` files automatically, and can undo that too (see "Fixing Verse references" below).

---

## Before you start

**Back up your project first.** Either make a copy of your project folder, or use Unreal Revision Control (Epic's built-in version control, similar to a save-history for your project) if you already have it set up. Epic themselves recommend pairing any Python scripting with source control, specifically in case a script makes a mistake. Sortilege has been tested carefully, but you should never run a tool that moves your assets around without a safety net.

**Enable the Python plugin.** Sortilege runs on UEFN's built-in Python support, which is off by default. To turn it on:

1. Open your project in UEFN.
2. Go to **Edit > Project Settings**.
3. Find **Plugins** in the left-hand list.
4. Turn on **Python Editor Script Plugin**.
5. Turn on **Editor Scripting Utilities** as well (this is the plugin that provides the safe asset-move functions Sortilege relies on).
6. Restart UEFN when it asks you to.

### IMPORTANT: an access note before you assume it's broken

Epic currently gates Python behind an account-level allowlist for some accounts, on top of the plugin checkbox above. This means that even after you follow the steps above, Python may still not be available to you, and that is an Epic account permission gate, not a bug in Sortilege and not something you did wrong.

How to tell if this is happening to you:

- The **Python Editor Script Plugin** checkbox is missing entirely from Project Settings, or
- After enabling it, your Output Log (the scrolling text log window in UEFN, where the editor prints status messages) shows a line like: `LogPython: Python disabled via CVar`

If you see either of those, your account does not currently have Python access from Epic's side. There is nothing to fix in the script itself. You would need to wait for Epic to widen access, or use a different account that already has it.

---

## Quick start

Once Python is enabled and working:

1. Open the **Output Log** panel in UEFN (Window > Output Log if it isn't already visible).
2. Make sure it is in **Cmd mode**, not Python mode (Cmd mode is the default; it is the mode where you type a single command line, versus Python mode which is a line-by-line code console). There is a small mode switch near the log's input box.
3. Get the file's path (a "path" is the full address of a file on your computer, like `C:/Users/You/Desktop/sortilege.py`). The easy way: in File Explorer, hold **Shift** and right-click `sortilege.py`, then choose **Copy as path**. That copies the full address, already wrapped in quotation marks. You do not need to remove those quotes; the command below needs them anyway. Forward slashes and backslashes both work fine in this command.
4. In the Output Log, type `py ` (with a space after it), paste the path you just copied, and press Enter. The result should look like this:

```
py "C:/path/to/sortilege.py"
```

Running it with no extra word after it always previews only. Nothing is changed by this command.

---

## The preview window

If your UEFN build's Python supports it, running the plain preview command above also opens a window titled "Sortilege - dry run preview" on top of the Output Log text. It shows the exact same scan results as the log, laid out for easier reading:

- A header with the scan counts and the content root.
- A "Planned moves" tab: every move, in a sortable table with full paths, grouped by category.
- A "Skipped" tab: every asset left alone, grouped by reason.
- A "Verse edits" tab: every proposed Verse-reference rewrite (see "Fixing Verse references" below), one row per edit with the file, line number, old reference, new reference, and a note column that reads "bare name - review" or "skipped - fix manually" exactly like the console preview. Updates the moment you click "Re-scan with these mappings", same as the other tabs.
- A "Folder mapping" tab: an editable box for each destination folder (Meshes, Materials, Textures, and so on) plus the sort root, pre-filled with your current settings. Change any of them and click "Re-scan with these mappings" to rebuild the plan right there in the window, no file editing or re-running needed. Bad folder names (empty, or containing characters folders cannot use) are rejected with an on-screen message instead of crashing anything.
- A checkbox at the bottom: "I understand this will modify my project." The Apply button stays greyed out until you tick it. This checkbox is the deliberate confirm for this run; it replaces both the file-editing step and the confirmation popup described under "How to execute for real" below, only for a run started from this window.
- Once you tick the box and click Apply, the window disables itself while it works, then shows a short results line (how many moved, how many failed, redirector cleanup results, and how many Verse references were updated when any were) with a report file path and an "Undo this run" button, so you can back out immediately if something looks wrong.
- A status line near the bottom stays live for the whole run, not just while assets are actively moving: "Moving assets...", "Fixing references...", "Cleaning up redirectors...", "Rewriting Verse references...", "Removing empty folders...", "Verifying...", "Writing report...", each with a live count on the slower passes (for example "Cleaning up redirectors 45/210..."). The window also stays pinned on top of the editor for the entire run instead of being able to slip behind it, so a long apply never leaves you wondering whether it froze.
- A "Logs:" line near the bottom shows the exact folder every plan, report, undo, and trace file from this run is written to.

This is entirely optional and off to the side of the console flow: if your UEFN build's Python cannot open this window for any reason, or if you set `"USE_GUI": False` in the CONFIG section near the top of `sortilege.py`, everything falls back automatically to the plain console preview described below, with no window at all. Nothing about the console flow changes either way.

A note on how this window behaves: it is unofficial. Epic has never documented tkinter (the toolkit this window is built with) as part of UEFN's embedded Python, so treat it as a convenience layer, not a guaranteed feature of every build. If it does not appear, the console preview and the usual apply steps still work exactly as always.

---

## Reading the preview

After you run the command above, the Output Log will print a report that looks roughly like this:

```
======================================================================
Sortilege - dry run preview
======================================================================
Content root: /YourProject    Sort root: (none)
Scanned 214 asset(s).
38 asset(s) to move (0 will also be renamed), 0 rename-in-place, 12 skipped
By category: Materials: 6, Meshes: 14, Textures: 18

-- Meshes (14) --
  StaticMesh  move  /YourProject/Rock01 -> /YourProject/Meshes/Rock01
  ...

-- Skipped (12) --
  already sorted (9):
    /YourProject/Meshes/OldTree [StaticMesh]
  protected system folder (3):
    ...

----------------------------------------------------------------------
DRY RUN - nothing was changed. To execute: open sortilege.py, set
I_UNDERSTAND_THIS_MODIFIES_MY_PROJECT = True in the CONFIG section
near the top of the file, save, and re-run this script with 'apply'
(py "path/to/sortilege.py" apply).

NOTE: referencer data is cached by the engine; counts can include
false positives until assets are loaded and re-saved.
CAUTION: if your Verse code references assets by folder-qualified
name (Asset Reflection), moving those assets requires updating
that Verse code. Redirectors do not rewrite Verse source.
```

Read the sections top to bottom:

- **Header**: how many assets were scanned and a category breakdown.
- **Category tables**: exactly which asset goes from which folder to which folder, and whether it will be moved, renamed, or both.
- **Skipped section**: every asset Sortilege is deliberately leaving alone, grouped by reason (for example "already sorted" or "protected system folder").
- **Footer**: a reminder that nothing changed yet, plus two caution notes worth actually reading (explained more below).

This same preview is also saved to a file (`sortilege_plan_<timestamp>.json`) every time you run it, even in preview mode, so you always have a written record of what a run would have done.

---

## How to execute for real

If the preview window described above opened for you, you can skip straight to its checkbox and Apply button instead of the steps below; they do the same job. The steps below are the console-only flow, and always work exactly as described here regardless of whether the window is available.

Once you have read the preview and you are happy with it, doing the real thing takes two steps: editing one line in the file, and re-running with a different word.

1. Open `sortilege.py` in any text editor (Notepad works fine).
2. Near the top of the file, find the **CONFIG** section. Inside it, find this exact line:

```python
"I_UNDERSTAND_THIS_MODIFIES_MY_PROJECT": False,
```

3. Change `False` to `True`, so it reads:

```python
"I_UNDERSTAND_THIS_MODIFIES_MY_PROJECT": True,
```

4. Save the file.
5. Go back to UEFN's Output Log and run:

```
py "C:/path/to/sortilege.py" apply
```

If your UEFN build supports it, a Yes/No confirmation window will pop up one more time, telling you exactly how many moves and renames are about to happen, before anything actually runs. This is a second, independent safety check on top of the flag you just flipped. If your build does not support that dialog, flipping the flag and running "apply" is enough by itself, since that is a deliberate, on-purpose action you took.

While it is applying, if your build shows a progress bar with a Cancel button, you can stop the run partway through. Anything already moved before you cancel stays moved (and is fully recorded in the undo log described further down), everything after the cancel point is left untouched.

When it is done, the Output Log prints a short summary and the location of the full report file.

**To go back to preview-only mode**, just set the flag back to `False`. As long as it says `False`, running the script (with no word, or with "preview") can never change anything.

---

## After the sort

Once everything has moved, the folders the assets came from are often left empty. Sortilege sweeps those up automatically at the end of a run (and after an undo, for the sorted folders the restore vacated): any source folder left completely empty is removed, and so are parent folders that empty out once their children go. A folder is only removed when truly nothing remains inside it. If it still holds assets, a leftover redirector that could not be cleaned, or any subfolder (even an empty one you made on purpose), it is kept and listed in the run report with the reason. If you would rather keep every folder exactly where it is, set `CLEAN_EMPTY_FOLDERS` to `False` in CONFIG. Protected system folders, excluded folders, and the project root itself are never touched by this sweep.

---

## Changing where things go

Near the top of `sortilege.py`, inside CONFIG, is a section called `FOLDER_MAP`. This decides what each category of asset gets renamed to as a destination folder. By default, everything keeps its own name as its folder (Meshes go to a folder called "Meshes", and so on).

You can rename the destination on the right-hand side of any line. For example, if you want all your Textures to land in a folder called "Art/Textures" instead of just "Textures", change this line:

Before:
```python
"Textures": "Textures",
```

After:
```python
"Textures": "Art/Textures",
```

The folder is created automatically if it does not already exist. You do not need to create it yourself first. Save the file and re-run in preview mode to confirm the new destination looks right before applying.

There is also a `SORT_ROOT` setting a little further down in the same CONFIG block (look for the line starting with `"SORT_ROOT"`). Leaving it as `""` (empty) sorts folders straight into the root of your project. Setting it to something like `"_Organized"` nests every sorted folder under one parent folder instead, leaving anything else already at your project root untouched.

---

## Keeping kits together (group by asset)

Imported props usually arrive as small KITS: one mesh plus its material plus that material's textures. A real example: a folder holding `SM_Alessio`, its material instance `MI_Bone_Alessio`, and three textures (`T_Bone_Position`, `T_Bone_Rotation`, `T_Bone_Weights`). Multiply that by ninety props and the default per-type sorting scatters every kit across `/Meshes`, `/Materials`, and `/Textures`, which is tidy by type but impossible to navigate by prop.

Group-by-asset mode keeps each kit together instead. Turn it on by changing this line in CONFIG:

```python
"GROUP_BY_ASSET": False,
```

to `True` (or pick "By asset (keep kits together)" on the preview window's Folder mapping tab and click Re-scan). With it on, Sortilege follows each anchor asset's dependencies and nests the whole kit under one folder named after the anchor, with the folder chain following the dependency chain. For the Alessio kit that means:

```
/Meshes/Alessio/SM_Alessio
/Meshes/Alessio/Materials/MI_Bone_Alessio
/Meshes/Alessio/Materials/Textures/T_Bone_Position
```

Each step in the dependency chain adds that asset's type folder. A deeper example with a Blueprint on top: `BP_LuckyBlock` uses a mesh, the mesh uses a material instance, the material instance uses a texture:

```
/Props/LuckyBlock/BP_LuckyBlock
/Props/LuckyBlock/Meshes/SM_LuckyBlock
/Props/LuckyBlock/Meshes/Materials/MI_LuckyBlock
/Props/LuckyBlock/Meshes/Materials/Textures/T_LuckyBlock_D
```

Details worth knowing:

- **Which asset owns a kit** is decided by `GROUP_ANCHOR_CLASSES` in CONFIG, in priority order. A mesh referenced by a Blueprint belongs to the Blueprint's kit rather than starting its own. The kit folder is named after the anchor with its type prefix stripped (`SM_Alessio` becomes `Alessio`).
- **Assets used by two or more kits** go to a folder named by `GROUP_SHARED_FOLDER` (default `Shared`), in normal per-type subfolders, since they belong to no single kit.
- **Assets in no kit at all** sort flat, exactly as in the default mode.
- **Two assets of the same type in a row** share one folder level: a material function used by a material sits right beside that material, not in a Materials folder inside another Materials folder.
- **All the usual safety rules still apply**: protected and excluded assets never join a kit, previews stay previews, and every move shows in the preview table before anything runs.

This mode needs a dependency-lookup API from the editor's Python. If your build does not expose it, Sortilege prints a note and quietly falls back to the normal flat sorting, and the preview window disables the by-asset option with an explanation. When grouping is active the preview header shows a summary line like `Grouping: by asset (90 kits, 4 shared, 12 loose)`.

---

## Prefix renaming (optional, bonus feature)

Some creators like their assets named with a short prefix that shows the asset type at a glance, like `SM_Rock` for a Static Mesh or `T_Grass` for a Texture. Sortilege can do this for you automatically.

This is off by default. To turn it on, find this line in CONFIG:

```python
"ENABLE_PREFIX_RENAME": False,
```

and change it to `True`. The prefix used for each asset type is listed in the `PREFIX_MAP` section higher up in the same CONFIG block (look for the lines starting with `"PREFIX_MAP"`), and you can edit those prefixes too.

This obeys the exact same preview-first, flag-then-confirm process as everything else. Nothing renames until you flip `I_UNDERSTAND_THIS_MODIFIES_MY_PROJECT` to `True` and run "apply".

---

## Sorting just one folder

If you don't want to sort your whole project, you can point Sortilege at specific folders only. Find `SCOPE_FOLDERS` in CONFIG:

```python
"SCOPE_FOLDERS": [],
```

An empty list means "scan everything". To limit it, list the folder paths you want, for example:

```python
"SCOPE_FOLDERS": ["/YourProject/OldStuff"],
```

Note: folder names in `SCOPE_FOLDERS` and `EXCLUDE_FOLDERS` must match the Content Drawer's capitalization exactly. Folder paths are case-sensitive, so `/YourProject/OldStuff` and `/YourProject/oldstuff` are treated as two different folders.

There is also a `USE_SELECTION` setting that tries to automatically use whatever folder you have selected in the Content Drawer at the moment you run the script, instead of you typing a folder path by hand. This is marked **experimental**: it depends on a feature that is not confirmed to work reliably across every UEFN build. If it can't read your selection, it automatically falls back to `SCOPE_FOLDERS` above, so nothing breaks if it doesn't work for you, it just quietly falls back.

---

## Undo

Every real run (an "apply") writes its own undo file, so you can reverse it later if needed. To undo the most recent run:

```
py "C:/path/to/sortilege.py" undo
```

This goes through the exact same two safety gates as applying: the `I_UNDERSTAND_THIS_MODIFIES_MY_PROJECT` flag must be `True`, and (if your build supports it) a Yes/No confirmation dialog appears before anything is restored. It prints exactly what it is about to restore first, so you can read it over before confirming.

**Why not just use UEFN's normal Ctrl+Z?** Because the editor's built-in Undo History is not reliable across the kind of asset move/rename operations this tool performs; Epic's own documentation notes some of these operations can clear the undo history entirely. That is exactly why Sortilege keeps its own separate undo file on disk instead of relying on the editor's undo.

If you have run Sortilege more than once and want to undo a specific earlier run instead of the latest one, you can point it directly at that run's undo file:

```
py "C:/path/to/sortilege.py" undo "C:/path/to/sortilege_undo_20260101-120000.json"
```

The undoing process itself makes its own new, freshly timestamped record files (its own undo log and its own report), so the original run's files are never overwritten, and you could theoretically undo the undo if you really needed to.

---

## Where the log files go

Every run writes files: a plan file (what was found/planned), a report file (what actually happened), and, for real runs, an undo file. By default these land in your project's "Saved" folder if UEFN can find it, otherwise in the same folder the script itself is saved in, and as a last resort in whatever folder the command happened to be run from. You can also force a specific location by setting `LOG_DIR` in CONFIG to any folder path you want.

The three file names always look like this:
- `sortilege_plan_<timestamp>.json`
- `sortilege_report_<timestamp>.txt`
- `sortilege_undo_<timestamp>.json`

If a real run rewrites any Verse references (see "Fixing Verse references" above), two more show up alongside them: a `verse_backup_<timestamp>/` folder holding an untouched copy of every `.verse` file it edited, and a `sortilege_verse_undo_<timestamp>.json` index tying those backups back to their real paths. `undo` restores from these automatically; you never need to open them by hand unless something goes wrong.

---

## Reference safety

Sortilege's whole design goal is that nothing you move ever ends up with a broken reference. Here is what actually happens, in order, every time you apply:

1. **The move itself** uses the engine's own safe rename API, which leaves a small "pointer" file (a redirector, explained above) at the old location, so anything already pointing there keeps resolving correctly.
2. **Soft references get repointed project-wide.** Some references (the kind Verse-visible assets and similar dynamically-looked-up content use) are not fixed up automatically by the move itself. Right after every apply, Sortilege checks every asset under your project (not just the ones it can already prove are connected to what moved) and repoints any of these that point at something that moved. This is deliberately broader than just checking "known" connections, because real-world testing found that a narrower check can miss one.
3. **A leftover pointer file is only ever deleted when double-confirmed safe.** Before removing any leftover pointer file, Sortilege checks TWICE, with two different engine queries, whether anything still points at it. Only when BOTH checks agree nothing does is the pointer file actually removed. If either check finds something, either check fails to run cleanly, or your UEFN build does not support the second check at all, the pointer file is deliberately left in place and listed in the run report under redirector cleanup, rather than risk removing something still in use. (This extra check is controlled by `CONSERVATIVE_REDIRECTORS` in CONFIG, on by default; turning it off is not recommended.)
4. **The final verify pass proves it.** After everything above, Sortilege checks whether anything is left pointing at a location that no longer exists at all (no asset there, no pointer file either). If it ever finds one, it is called out explicitly, by name, in the run report and the preview window's results line as a "BROKEN soft reference" -- with steps 2 and 3 above in place, this should always come back empty.

The one thing none of this can cover is Verse source code that names an asset directly -- see the caution below. That lives entirely outside the asset system Sortilege scans, so no check against the asset system, however thorough, can see it.

---

## What it will never touch

Regardless of your settings, Sortilege always leaves the following alone. These are checked before any other rule, so no config combination (including STRICT_MODE or group-by-asset mode) can ever cause one of them to move:

- **Your project's GameFeatureData asset.** This is the file that makes your project a project at all; a live test run once moved it by mistake and the project came back broken with "missing its GameFeatureData" until it was restored. Sortilege now protects this asset by name, unconditionally.
- **Levels and maps** (the World/Level assets that make up your actual island), plus their MapBuildData (the precomputed lighting/reflection data every level carries) and World Partition data layers. Moving any of these could break the island, so they are always skipped.
- **Verse files** (your `.verse` code files) and any compiled asset whose engine class name is linked to Verse. These live in a completely separate system (Verse Explorer) from the asset system Sortilege scans, and are never part of any move.
- **System folders that start with a double underscore**, like `__ExternalActors__` and `__ExternalObjects__`. These are engine-managed bookkeeping folders, not real content, and reorganizing them can cause problems.
- Anything you add yourself to `EXCLUDE_FOLDERS` in CONFIG.

This also applies inside group-by-asset (kit-sorting) mode: if a Blueprint or other kit anchor depends on your GameFeatureData asset, a level, or anything else on this list, that dependency is left exactly where it is instead of being pulled into the kit's folder.

Every single one of these is recorded in the skipped section of the preview and the final report, with the specific reason why, so nothing disappears silently.

You may notice there is no "Verse" folder in the destination `FOLDER_MAP`, even though compiled assets that are linked to Verse code are scanned and classified like everything else. This is a deliberate safety decision, not a missing feature. Epic's asset-move APIs do not rewrite Verse source code that references an asset by its folder-qualified name, so moving a Verse-linked asset could silently break your Verse code, with no redirector left behind to catch the mistake (unlike a normal moved asset, which does get a redirector). Rather than relocate something that could break in a way nothing warns you about, Sortilege classifies Verse-linked assets, reports them in the skipped section of every preview and report, and leaves them exactly where they are.

This is separate from, and does not conflict with, the "Fixing Verse references" feature described below: that feature updates your `.verse` source files after an ORDINARY (non-Verse-linked) asset moves, so any Verse code that names it stays correct. Verse-linked assets themselves still never move, for the reason above.

---

## Fixing Verse references

If your Verse code refers to an asset by its folder-qualified name (this happens automatically through a feature called Asset Reflection, where Verse can see and reference your content assets directly), moving that asset changes its qualified name in Verse too -- for example, moving `/YourProject/PowersWheelAssets/Models/Textures/T_Hex` to `/YourProject/Textures/T_Hex` changes the Verse-side name Asset Reflection generates for it from `PowersWheelAssets.Models.Textures.T_Hex` to just `Textures.T_Hex`. Left alone, that mismatch stops your project compiling the next time you build Verse code.

Sortilege now fixes this automatically, on by default (`CONFIG["FIX_VERSE_REFERENCES"]`). After working out each asset's old and new Verse-qualified name, it searches your real `.verse` source files for that exact name and rewrites it, the same folder-qualified name -> folder-qualified name change Asset Reflection itself would produce. It also updates a `using { /Old/Folder/Path }` line (the Verse import statement that lets you drop a qualification prefix) when a whole folder's contents moved together, as long as every asset that used to live in that folder agrees on the very same new folder -- if a folder's contents scattered to two different destinations in one run, its `using` statement is left alone rather than guessed at.

Every rewrite matches the FULL name as a whole token, never a fragment of a longer one -- moving `T_Hex` never touches `T_Hex2` or an unrelated `Foo.T_Hex` that happens to end in the same name, and it is applied to your actual project files, not a copy. Before touching anything, every affected `.verse` file is backed up, so `py "path/to/sortilege.py" undo` restores your Verse source right alongside the assets it moved.

**Finding your `.verse` files.** Sortilege auto-detects your project's real directory from one of your own scanned assets' on-disk path (`unreal.SystemLibrary.get_system_path()`), then searches that folder's `.verse` files. This is deliberately NOT `unreal.Paths.project_dir()` -- a live diagnostic proved that call resolves to the Fortnite ENGINE directory inside UEFN, not your project, which used to make this feature silently scan the wrong folder and find (and fix) nothing, even with a genuine reference sitting right there in your own `.verse` code. Every preview and report always prints "Verse fixup: N .verse file(s) found under X" so you can see exactly which directory it used; if it ever looks wrong for your setup, set `CONFIG["VERSE_SEARCH_DIR"]` to your project's folder (the one containing your `.uefnproject`) and that override always wins, no auto-detection involved. Honesty note: `unreal.SystemLibrary.get_system_path()`'s exact behavior on asset objects has not been confirmed against a live UEFN session as part of this fix (only against the test mock) -- the design stays safe either way, because among every candidate directory it tries, it picks whichever one demonstrably has real `.verse` files under it (never a blind guess), and the override above is always there as a manual escape hatch.

A few things worth knowing:

- **A root-level asset name (no folder qualification, just `T_Hex`) is flagged in the preview as "(bare name - review)".** A bare name is a plain word with nothing to distinguish it from an unrelated identifier that merely happens to match, so a rewrite of one is worth a quick manual look in the preview before you apply, even though the same whole-token matching still protects it from a partial-word false hit.
- **`CONFIG["FIX_VERSE_BARE_NAMES"]` (default `True`) controls whether a bare name actually gets rewritten.** Left `True`, a bare name is rewritten (and flagged, as above) exactly like a qualified one. Set it to `False` and Sortilege will still rewrite every qualified (dotted) reference automatically -- the common, provably-safe case -- but will SKIP a bare-name rewrite entirely, listing it in the preview and report instead under "skipped (bare name - fix manually): N" so you know exactly which ones to update by hand. This lets you keep the automatic fixup for the safe majority of references while staying hands-on for the riskier bare ones.
- **Python cannot compile Verse -- that is a UEFN-only action.** This fixup keeps your qualified names correct, which is what makes your project *able* to compile again, but Sortilege itself can never prove the result actually compiles. Always run **Build Verse Code** in UEFN after an apply that rewrote Verse references, the same way you always should after any manual Verse edit.
- Turn this off entirely with `"FIX_VERSE_REFERENCES": False` in CONFIG if you would rather review and update your Verse code by hand; see the caution below for what that means in practice.
- A normal preview shows a "-- Verse reference edits --" section (and a headline count) listing every rewrite it would make, exactly like the asset-move table above it, before anything is touched. The preview window (see "The preview window" above) shows the same list in its own "Verse edits" tab, not just the Output Log.

---

## A caution about Verse asset references

Even with the automatic fixup above turned on, this remains a documented limitation, not a gap in effort: Asset Reflection is a project-wide setting with no per-asset marker Sortilege (or any Python script) can query to ask "is this specific asset one my Verse code names directly?" -- so finding every reference is a text search over your real `.verse` files, not a query against the asset system the rest of this tool's reference-safety checks (see "Reference safety" above) rely on. A reference built dynamically at runtime (a string assembled from parts, rather than typed out literally) will not be found by a text search and will not be rewritten. If `FIX_VERSE_REFERENCES` is turned off, none of this runs at all, and you are back to updating Verse code by hand.

The verify pass's "BROKEN soft reference" detection will never catch a broken Verse-source reference either way, for the same reason: it can only ever prove the asset system itself stayed intact, not your Verse source. That is exactly why the fixup above exists as its own separate pass, and why Build Verse Code afterward is the only real confirmation that your project still compiles.

This caution is printed at the bottom of every preview, so you will see it every single time, not just here.

---

## Troubleshooting

**"Python disabled via CVar" in the Output Log, or the plugin checkbox is missing.** This is the Epic account allowlist gate described above, not a bug in Sortilege. There is nothing in the script to fix.

**I'm not sure Python is even working, before I try sorting anything.** Run probe mode, which only reads information and never changes or plans anything:

```
py "C:/path/to/sortilege.py" probe
```

This prints your Python version, your project's content root, a list of which optional engine features this specific UEFN build supports, a quick headline count of what would be found if you scanned right now, and where log files would be written. It is the safest possible way to sanity-check your setup before running a real preview or apply.

**An asset didn't move where I expected, or didn't move at all.** Open the report file (`sortilege_report_<timestamp>.txt`) from your last run and check the "Skipped" section. Every skipped asset is listed there together with the exact reason it was skipped (for example "already sorted", "protected system folder", "destination occupied", or "invalid target name"). This is the first place to look any time a result surprises you.

**Nothing happened when I ran "apply".** Check that you actually saved `sortilege.py` after changing `I_UNDERSTAND_THIS_MODIFIES_MY_PROJECT` to `True`. If it is still `False`, apply mode always blocks and prints instructions instead of moving anything, on purpose.

**A few redirectors are still hanging around after applying.** Cleanup is best-effort: Sortilege tries to resave everything that points at a moved asset and then remove the leftover redirector, but it can only do this for things it can safely load and resave in your current session. Anything it could not clean up is listed by name in the report under the redirector cleanup section, so you can decide whether to handle those manually (for example, by opening the affected assets once and resaving them yourself). Some of these will be listed with the reason "kept: still referenced (possible soft reference)" -- that is the double-check described in "Reference safety" above declining to delete a pointer file it could not fully confirm was safe to remove. That is working as intended: a leftover pointer file is clutter, not a broken reference, and Sortilege would always rather leave one behind than risk removing one still in use.

**My map/island won't open, or something looks broken after a run.** Restore your backup, or run undo mode as described above. Then check the report file's Skipped and Failed sections for anything unusual before trying again.

---

## FAQ

**Does this touch my Verse code?** Your `.verse` files themselves are never moved, renamed, or reorganized, and any compiled asset linked to Verse code is never moved either (see "What it will never touch" above). What Sortilege DOES touch, by default, is the TEXT inside your `.verse` files: if one of them refers to a moved asset by its folder-qualified name, that reference is rewritten in place so it matches the asset's new location -- see "Fixing Verse references" above. Turn `CONFIG["FIX_VERSE_REFERENCES"]` off if you would rather your `.verse` files were never edited at all.

**Will this break references to my assets?** Sortilege moves assets using the engine's own official move function (the same underlying mechanism as manually dragging an asset in the Content Drawer), which is designed to keep references intact, and it repoints references project-wide (not just the ones it can already prove are connected) right after every move -- see "Reference safety" above. It also runs a verification pass after every real run to double-check nothing came up missing or broken, including a dedicated check for any reference left pointing at nothing. Direct Verse code that names an asset by its folder-qualified path is now automatically rewritten too (see "Fixing Verse references" above) -- the one thing that fixup still cannot do is prove your project compiles afterward, since Python cannot invoke Verse's compiler; always run Build Verse Code in UEFN to confirm.

**What if I run it by accident with the flag already set to True from a previous session?** Preview mode (running with no extra word, or with "preview") never changes anything no matter what the flag is set to. Only "apply" mode acts on the flag, and even then it still shows you the same dry-run preview first, before the confirm gates are even checked.

**Can I change the categories themselves, like what counts as an "Animations" asset?** Yes, that is the `CLASSIFICATION` section in CONFIG, immediately below FOLDER_MAP. It maps each engine asset type to a category. Anything not listed there falls back to the "Other" folder by default (or gets skipped entirely if you turn on `STRICT_MODE`).

**Does it delete anything?** Only the small leftover redirector "pointer" files after a confirmed-safe cleanup check, and only if `CLEAN_REDIRECTORS` is left on (the default). Your real assets are moved, never deleted. If you also turn on `CLEAN_EMPTY_FOLDERS`, folders left completely empty after sorting are removed too; this is off by default.
