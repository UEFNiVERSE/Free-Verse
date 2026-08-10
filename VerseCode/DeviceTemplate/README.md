# Device Name Here

One-sentence description of what this device does.

## What It Does

Describe the gameplay mechanic or system this device implements.

## Properties

| Property | Type | Default | Description |
|---|---|---|---|
| ExampleProperty | int | 10 | Replace with your actual properties |

## Setup

1. Copy the `DeviceTemplate/` folder into your UEFN project's `VerseCode/` directory
2. Rename the folder and `.verse` file to match your device name
3. Rename the `my_device` class to match, and update `LOGGER_NAME`
4. Add the new folder to `module_access.verse` (for example `MyDevice <public> := module:`) so Verse can reach it
5. Drag the device into your map in UEFN
6. Configure the properties in the Details panel

The template extends `base_group_device`, which adds the player group layer. If your device does not
need groups, extend `Core.base_device` instead.

## Dependencies

- Requires `Core/base_device.verse` and `Core/base_group_device.verse` to be present in your project.
  The two classes reference each other across the same `Core` module, so always include both
- Requires `utility.verse`, which provides `debug_settings`, `LabelTip` and `DebugTip`
