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
- `base_device.verse` - Defines the groupless `base_device` foundation class every device extends, plus the `player_group` class and the shared Core tags and tooltips
- `base_group_device.verse` - Defines the `base_group_device` class: extends `base_device` and adds the player group layer for devices that need groups
- `Saved_Data.verse` - Persistence layer for cross-session data storage
- `utility.verse` - Shared helper functions and utilities

> **Note:** `base_device.verse` and `base_group_device.verse` are both part of the `Core` module. The two classes reference each other across files, so always include both.

## Devices

| Device | Name | What It Does | Release |
|---|---|---|---|
| Device1 | Shared Progress Tracker | Group progress tracking with milestones and rewards | v1.1.0 |
| Device2 | Team Buff Zone | Zone-based tiered team buffs with VFX | v1.2.0 |
| Device3 | Advanced Revive System | Collaborative revives with multi-tier rewards | v1.3.0 |
| Device4 | Pro Social Feed | Island-wide social feed with help requests and thanks | v2.1.0 |

Each device folder has its own README with full setup, configuration, and examples.

## Core Architecture
All UEFNiVERSE devices extend the same Core foundation for consistent behavior. The foundation is split across two files in the `Core` module:

### base_device (`base_device.verse`)
The groupless foundation device. Provides:
- Initialization trigger support and overridable lifecycle hooks (`PreInitialize`, `Initialize`, `OnAgentJoined`, `OnAgentRespawned`, `OnAgentLeft`)
- Debug logging with custom identifiers via `Logger`
- Automatic spawner discovery via tags

### base_group_device (`base_group_device.verse`)
Extends `base_device` for devices that need player groups. Adds:
- The `Groups` editable array
- Agent-to-group lookup utilities (`GetGroup`, `GetGroupIndex`, `GetGroups`)
- Group initialization ahead of device startup via `PreInitialize`

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
