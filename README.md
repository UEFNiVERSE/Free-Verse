# 🚀 UEFNiVERSE - Free-Verse Device Collection
Professional, modular Verse devices for UEFN creators. 100% free and open-source.
Community requests are always welcome via the UEFNiVERSE Discord or Issue Requests!

## License Note
This project is licensed under **[Apache 2.0](https://choosealicense.com/licenses/apache-2.0/) + the [Commons Clause](https://commonsclause.com/)**. In plain terms:

- ✅ **Free to use in your UEFN maps.** Drop these devices into any island — published or private, monetized or not — at no cost.
- ✅ **Forking and contributing is welcome.** Fork the repo, modify the code, and open a PR. Community contributions are encouraged.
- ❌ **You cannot sell the library itself.** The Commons Clause means you may not sell a product or service whose value derives *primarily* from this library (for example, reselling these devices as a paid pack or paid support service for them).

In short: build whatever you want *with* these devices — just don't sell *them*. See [LICENSE](LICENSE) for the full terms.

## Overview
UEFNiVERSE provides reusable, well-architected Verse devices built on a shared core architecture. Each device extends a common foundation, ensuring consistency, maintainability, and ease of integration.

All devices share the same **Core** system:
- `base_device.verse` - Defines the `player_group` class plus the shared Core tags and tooltips used by the group system
- `base_group_device.verse` - Defines the `base_group_device` class: the group-management foundation device that all group devices extend
- `Saved_Data.verse` - Persistence layer for cross-session data storage
- `utility.verse` - Shared helper functions and utilities

> **Note:** `base_device.verse` and `base_group_device.verse` are both part of the `Core` module. The two classes reference each other across files, so always include both.

## Core Architecture
All UEFNiVERSE devices extend the same Core foundation for consistent behavior. The foundation is split across two files in the `Core` module:

### base_group_device (`base_group_device.verse`)
The group-management foundation device that all group devices subclass. Provides:
- Initialization trigger support and overridable lifecycle hooks (`Initialize`, `OnAgentJoined`, `OnAgentRespawned`, `OnAgentLeft`)
- Debug logging with custom identifiers via `Logger`
- Agent-to-group lookup utilities (`GetGroup`, `GetGroupIndex`, `GetGroups`)
- Automatic spawner discovery via tags

### player_group (`base_device.verse`)
The companion class used by `base_group_device`'s `Groups` property. Provides:
- Dynamic group assignment/removal via triggers
- Per-group state isolation (tracks the agents in each group)
- HUD message integration for group feedback

> `player_group` and `base_group_device` live in separate files but the same `Core` module, so they reference each other directly.

### Persistence System
Centralized save/load system using:
- `persistence_scope` enum (None/PlayerGroup/PerPlayer)
- Automatic save throttling (5-second intervals)
- Key generation utilities for data organization

---

## Installation
### For UEFN Projects:
1. Download the device folder(s) you need
2. Copy to your UEFN project's Verse directory
3. Include the `Core` folder (required for all devices)
4. Include `module_access.verse` and `utility.verse` 
   - Put `module_access.verse` in your content folder directly and update with your existing folder structure as needed to resolve access errors
5. Compile, setup your new device(s) and launch!
   - You should be good to go but if you have any errors and need assistance, reach out to us on Discord!

---

## Contributing
We welcome contributions from the UEFN community!

**👉 Read our [CONTRIBUTING.md](CONTRIBUTING.md) for complete guidelines:**
- How to report bugs
- How to suggest features  
- Development prerequisites
- Contribution workflow (fork, branch, PR)
- Coding standards and best practices
- PR review process

**Quick Start:** Fork → Create feature branch → Make changes → Submit PR

---

## 🧰 Community Tools
Third-party tooling from the wider UEFN community. These projects are **not part of this library** and are **not covered by this repository's license**. Each one is maintained by its own author, under whatever terms that author sets. They are listed here because they are useful to the same creators these devices are for.

### Verse Field Tool
**By Supreme** ([@supremeuefn](https://github.com/supremeuefn)) · [supremeuefn/uefn-python-tools](https://github.com/supremeuefn/uefn-python-tools)

A standalone in-editor GUI for creating, managing, and MVVM-binding Verse-exposed variables ("Verse fields") on UEFN Widget Blueprints. Run it inside UEFN via **Tools > Execute Python Script**.

- **Create fields** of any supported type (float, int, logic, string, message, color, color_alpha, material, texture, event), organized into categories
- **Bulk-bind** a widget's Verse fields to engine widget properties, to the Verse fields of embedded child-widget instances, or to button events (OnClicked, OnHovered, and similar)
- **Event parameters**, where each binding carries its own value, so a single Verse handler can tell which button called it
- **Manage fields** with crash-safe deletion of freshly-created fields

Creating and binding Verse fields by hand is error-prone and can crash UEFN. This tool wraps the whole create, patch, compile, verify, bind workflow behind a UI. Requires only `unreal`, the Python standard library, and PySide6.

> ⚠️ **Licensing:** `uefn-python-tools` currently ships **no license file**, so it grants no reuse terms. Treat it as all rights reserved: use the tool as published, and speak to Supreme directly before redistributing it or building on its source. Listing it here is a credit and a link, not a sublicense, and it does **not** place his work under this repository's Apache 2.0 + Commons Clause.

Listed with Supreme's permission. Please raise issues and feature requests for this tool on its own repository, not here.

---

## Support

**Developers:** PineFruit, LastMade  
**Organization:** Chartis / UEFNiVERSE  
**License:** Open-Source (see LICENSE)

**Contact:**
- Discord: PineFruit, LastMadeUEFN
- Epic: PineFruitDev, LastMadeMe
- Twitter: @PineFruitDev, @LastMadeUefn

**Resources:**
- Each device has its own detailed README
- Core files contain comprehensive inline documentation
- Reach out on discord if you need anything: https://discord.gg/UEFNiVERSE
- [CONTRIBUTING.md](CONTRIBUTING.md) for development guidelines

---

**License:** [Apache 2.0](https://choosealicense.com/licenses/apache-2.0/) with [Commons Clause](https://commonsclause.com/)
**Powered by:** [Project Moonlight](https://www.projectmoonlight.org/)
