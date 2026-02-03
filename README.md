# UEFNiVERSE - Free-Verse Device Collection
Professional, production-ready Verse devices for UEFN creators. 100% free and open-source.
Community requests are aways welcome via the UEFNiVERSE Discord!

## Overview
UEFNiVERSE provides reusable, well-architected Verse devices built on a shared core architecture. Each device extends a common foundation, ensuring consistency, maintainability, and ease of integration.

All devices share the same **Core** system:
- `base_device.verse` - Foundation for all devices with debug logging and initialization
- `base_group_device.verse` - Group management system for team/class-based gameplay
- `Saved_Data.verse` - Persistence layer for cross-session data storage
- `utility.verse` - Shared helper functions and utilities

---

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
We welcome contributions from the UEFN community! Follow these guidelines to submit improvements.

### How to Contribute
1. **Fork the Repository**
   - Create your own fork of the UEFNiVERSE repo
2. **Create a Feature Branch**
   ```bash
   git checkout -b feature/your-feature-name
   ```
3. **Make Your Changes**
   - Follow existing code style and architecture patterns or suggest an improvement
   - Extend `base_device` or `base_group_device` for new devices
   - Add comprehensive inline documentation
   - Test thoroughly in UEFN before submitting
4. **Document Your Work**
   - Create a `README.md` in your device folder
   - Include: Overview, Features, Setup Guide, Configuration Reference, Examples
   - Update main README if adding new devices
5. **Submit a Pull Request**
   - Push your branch to your fork
   - Open a PR against the `main` branch
   - Provide clear description of changes and reasoning
   - Reference any related issues

### PR Review Process
- All PRs require review before merging
- Maintainers check for: code quality, architecture compliance, documentation completeness
- Expect feedback within 3-5 days
- Be responsive to review comments

### Code Standards
**Architecture:**
- Extend existing base classes (`base_device` or `base_group_device`)
- Use existing Core utilities (`Saved_Data`, `utility`)
- Follow DRY and SOLID principles

**Documentation:**
- Inline comments for complex logic
- Full device README with examples
- Clear parameter descriptions with tooltips

**Naming:**
- Classes: `snake_case` (Verse convention)
- Variables: `PascalCase` for public, `camelCase` for private
- Files: `snake_case.verse`

**Performance:**
- Minimize allocations in hot paths
- Use throttled loops for continuous operations
- Reuse data structures where possible

---

## Support
**Developers:** PineFruit, LastMade  
**Organization:** Chartis / UEFNiVERSE  
**License:** Open-Source (see LICENSE)

**Contact:**
- Discord: PineFruit
- Epic: PineFruitDev
- Twitter: @PineFruitDev

**Resources:**
- Each device has its own detailed README
- Core files contain comprehensive inline documentation
- Video walkthrough links for each device can be found in their README
---


---

*Powered by Project Moonlight*
