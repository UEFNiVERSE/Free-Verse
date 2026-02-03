# 🚀 UEFNiVERSE - Free-Verse Device Collection
Professional, production-ready Verse devices for UEFN creators. 100% free and open-source.
Community requests are aways welcome via the UEFNiVERSE Discord!

## Overview
UEFNiVERSE provides reusable, well-architected Verse devices built on a shared core architecture. Each device extends a common foundation, ensuring consistency, maintainability, and ease of integration.

All devices share the same **Core** system:
- `base_device.verse` - Foundation for all devices with debug logging and initialization
- `base_group_device.verse` - Group management system for team/class-based gameplay
- `Saved_Data.verse` - Persistence layer for cross-session data storage
- `utility.verse` - Shared helper functions and utilities

## Core Architecture
All UEFNiVERSE devices extend the same base classes for consistent behavior:

### base_device
Foundation class providing:
- Debug logging with custom identifiers
- Initialization trigger support
- Standardized Print methods

### base_group_device
Extends `base_device` with player group management:
- Dynamic group assignment/removal via triggers
- Per-group state isolation
- HUD message integration for group feedback
- Agent-to-group lookup utilities

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

**License:** MIT License - Free and Open Source
**Powered by:** [Project Moonlight](https://www.projectmoonlight.org/)
