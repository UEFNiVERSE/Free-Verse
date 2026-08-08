# CLAUDE.md

Orientation for any Claude session working in this repo. Keep it tight; link out rather than inline.

## Project

Free-Verse, the UEFNiVERSE collection of free, modular Verse devices for UEFN creators. Public repo
under the `UEFNiVERSE` org. There is no build, no test runner, and no package manager: the
deliverable is Verse source that creators copy into their own UEFN project, plus `.uasset` UMG
widgets for the devices that ship UI.

## Layout

- `VerseCode/Core/` shared foundation. `base_device.verse` (the groupless base plus `player_group`),
  `base_group_device.verse` (the group layer every group device extends), `Saved_Data.verse`
  (persistence). The two base files reference each other across the same `Core` module, so a
  consumer always needs both.
- `VerseCode/Device1/` .. `DeviceN/` one folder per shipped device, each with its own `README.md`.
- `VerseCode/DeviceTemplate/` starting point for a new device.
- `VerseCode/utility.verse` and root `module_access.verse` shared helpers and the module access
  shim consumers edit to match their own folder structure.
- `UMG/` UI assets, named per device (`UMG/Device4_SocialFeed/`).

## Verifying a change

There is nothing to run locally. **Verse compiles in UEFN, not here.** Any device change has to be
compiled and exercised in a real UEFN project before it ships. Do not claim a Verse change is
working because it looks right; say plainly that it is untested if it has not been through UEFN.

## Versioning: `phase.device.bugfix`

This is the part people get wrong. The version is **not** semver.

- **`phase`** is the contract or work phase. It increments when a new phase starts.
- **`device`** is the device index **within the current phase**, and it **restarts at 1** each time
  the phase increments.
- **`bugfix`** increments for fixes to an already-released device.

**Device folder numbering does not restart.** Folders keep counting up across phases forever, so
`Device4` is the fourth device in the repo, not the fourth device of phase 2. Released history shows
both rules at once:

| Tag | Device folder | Meaning |
|---|---|---|
| `v1.1.0` | `Device1` | phase 1, first device |
| `v1.2.0` | `Device2` | phase 1, second device |
| `v1.3.0` | `Device3` | phase 1, third device |
| `v2.1.0` | `Device4` | phase 2, **first** device of that phase |

So the next device of phase 2 is `v2.2.0` in `Device5`. Check the latest tag and the highest device
folder separately; do not derive one from the other.

## Release notes

One paragraph, then a `Files added:` list. No headings, no bullet-point feature lists, no marketing
block. The paragraph says what the device does, names the notable behaviours and limits (cooldowns,
history size, what persists), mentions any Core change that shipped alongside it, and points at the
device's own README for setup. Then:

```
Files added:

- VerseCode/DeviceN/<device>.verse
- UMG/DeviceN_<Name>/<Widget>.uasset
```

Match the voice of the existing releases rather than inventing a new format. `gh release view
v2.1.0` is the reference.

## Licensing

Apache 2.0 **plus the Commons Clause**. In plain terms, and this is exactly how the README puts it
to creators:

- Free to use in any UEFN map, published or private, monetized or not.
- Forking and contributing back is welcome.
- You may **not** sell the library itself, or a product or service whose value derives primarily
  from it (for example reselling these devices as a paid pack).

Every new device inherits this. Do not add code under a different license, and do not soften or
restate the license terms in a device README in a way that conflicts with `LICENSE`.

Branch protection on `main`: PR required with **1 approving review**. That means a session cannot
merge its own PR here; leave it open for Sky.

## House rules

- **Never commit to `main`.** Branch, open a PR, squash-merge with `--delete-branch`. This holds for
  one-line doc fixes too.
- **No em dashes** anywhere: code, comments, docs, commit messages, PR bodies, release notes, device
  READMEs. Use a comma, a colon, or parentheses.
- **No AI-collaboration tells.** No `Co-Authored-By` trailer, no "Generated with", no mention of
  Claude or any assistant in commit messages, PR bodies, code comments, docs, or release notes. This
  is a public community project under Sky's name and it reads as his own work.
- **Check the existing devices before building a new one.** Several devices already solve group
  assignment, persistence, and HUD messaging through `Core`. Extend `base_device` or
  `base_group_device` rather than writing a standalone device from scratch. `CONTRIBUTING.md` says
  the same thing for outside contributors.
- Stage explicit paths. No `git add -A` and no `git add .`.

## Constraints

- Do not restructure `Core` without checking every device that extends it. Consumers copy folders by
  hand, so a rename is a breaking change for every creator who already shipped a map with it.
- Do not claim a Verse change compiles unless it has been compiled in UEFN.
- Do not commit client or contract material. `proposals/` and the SOW PDF at the repo root are
  business documents; do not surface their contents in public-facing docs or release notes.
