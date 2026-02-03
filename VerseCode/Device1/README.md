# Device1: Shared Progress Tracker

**Part of:** [UEFNiVERSE Free-Verse Device Collection](https://github.com/your-repo/UEFNiVERSE)  
**Extends:** `base_group_device` (Core architecture)  
**Dependencies:** `Core/base_device.verse`, `Core/base_group_device.verse`, `Core/Saved_Data.verse`, `utility.verse`

---

## What It Does
Tracks collective progress across player groups with persistence, milestones, and rewards.

---

## Key Features
✅ **Group-Based Progress** - Pool progress from multiple players  
✅ **Cross-Session Persistence** - Save/load progress between game sessions  
✅ **Milestone Rewards** - Trigger rewards at 25%, 50%, 75%, 100%, etc.  
✅ **Auto-Stat Tracking** - Connect tracker devices for automatic stat tracking  
✅ **Repeatable Objectives** - Reset and complete trackers infinitely  
✅ **Flexible Input** - Manual triggers OR tracker device events  

---

## Quick Setup
### Video Walkthrough:
https://www.youtube.com/watch?v=FMUW7PfTIcE

### Basic Team Objective (No Persistence)
1. Add `Shared Progress Tracker` device to your island
2. Create a `Group Tracker`:
   - **Label**: "Team Eliminations"
   - **Goal**: 50
   - **Change Amount**: 1
   - **Increment Trigger**: Connect to elimination manager
   - **Completed Output**: Connect to reward device
3. Add player groups (Team 1, Team 2, etc.)
4. Connect group assign triggers
### Auto-Stat Tracking (Using Tracker Device)
1. Place a `tracker_device`, set **Stat to Track** to "Eliminations"
2. In `Shared Progress Tracker`:
   - **Backend Tracker**: Assign your tracker device
   - Leave increment/decrement triggers empty
3. Progress auto-increments when players get eliminations
### Persistent Progress (Saves Between Sessions)
1. In `Group Tracker > Progress`:
   - **Persistence Scope**: Choose mode
     - `None` = No saving
     - `PlayerGroup` = Only loads when rejoining same group
     - `PerPlayer` = Loads into any group (portable progress)
### Repeatable Objectives
1. Set **Is Repeatable** to `Yes`
2. When goal is reached:
   - Rewards trigger ✅
   - Progress resets to 0 ✅
   - Saved data cleared ✅
   - Can complete again infinitely ✅

---

## Configuration Reference
### tracker_progress Class
| Field | Type | Description |
|-------|------|-------------|
| **Goal** | int | Target value to complete tracker |
| **Change Amount** | int | How much to add/subtract per trigger |
| **Is Repeatable** | logic | Auto-reset when completed |
| **Increment Trigger** | trigger_device | Manual increment trigger |
| **Decrement Trigger** | trigger_device | Manual decrement trigger |
| **Backend Tracker** | tracker_device | Auto-stat tracking source |
| **Completed Output** | trigger_device | Fires when goal reached |
| **Persistence Scope** | enum | None / PlayerGroup / PerPlayer |
| **Reset on Leave** | logic | Remove player progress when they disconnect |
### milestone_rewards Class
| Field | Type | Description |
|-------|------|-------------|
| **Type** | enum | Group (all players) or Player (individual) |
| **Goal Ratio** | float | % of goal (0.0 - 1.0) to trigger at |
| **Output Trigger** | trigger_device | Reward trigger device |

---

## Common Use Cases
### Scenario 1: Clan Wars
- **Setup**: Group tracking with PlayerGroup persistence
- **Result**: Clan progress saves, only loads for same clan members
### Scenario 2: Server-Wide Event
- **Setup**: One group, all players, repeatable tracker
- **Result**: Community completes objectives multiple times for rewards
### Scenario 3: Individual Contributions
- **Setup**: PerPlayer persistence, milestone rewards
- **Result**: Players keep progress even if switching groups
### Scenario 4: Hybrid Tracking
- **Setup**: Backend tracker for auto-stats + manual triggers for bonus
- **Result**: Auto-increments on eliminations, manual triggers for special events

---

## Debug Settings
Set **Debug > Enable Debug** to `Yes` to see console logs:
- Progress changes
- Save/load operations
- Group assignments
- Milestone triggers

---

## Tips & Best Practices
⚠️ **Don't enable both** `Reset on Leave` and `Persistence` - they conflict  
💡 **Backend Tracker ≠ Visual Tracker** - Use separate trackers to avoid double-counting  
💡 **Persistence saves every 5 seconds** - Throttled to reduce database load  
💡 **PlayerGroup mode** - Best for team-locked objectives  
💡 **PerPlayer mode** - Best for personal achievements across teams  

---

## Support
**Part of UEFNiVERSE** - Professional Verse devices for UEFN creators  
**Developers:** PineFruit, LastMade | **Organization:** Chartis, UEFNiVERSE

**Resources:**
- [Main Repository](https://github.com/UEFNiVERSE/Free-Verse) - Full device collection
- Inline code documentation for detailed implementation
- Example configurations throughout this README

**Contact:**
- Discord: PineFruit, LastMadeUEFN
- Epic: PineFruitDev, LastMadeMe
- Twitter: @PineFruitDev, @LastMadeUefn

**Contributions:** See main repository for contribution guidelines

---

**License:** MIT License - Free and Open Source
**Powered by:** [Project Moonlight](https://www.projectmoonlight.org/)