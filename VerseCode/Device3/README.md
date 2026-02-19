# Device3: Advanced Revive System

**Part of:** [UEFNiVERSE Free-Verse Device Collection](https://github.com/your-repo/UEFNiVERSE)  
**Extends:** `base_group_device` (Core architecture)  
**Dependencies:** `Core/base_device.verse`, `Core/base_group_device.verse`, `utility.verse`

---

## What It Does
Professional collaborative revival system with dynamic button tracking, multi-tier rewards based on teamwork, and group-based cooperation mechanics.

---

## Overview

The **Advanced Revive System** is a professional collaborative revival device that rewards group cooperation when reviving downed teammates. When a player is downed, the system dynamically assigns a button that follows them, allowing teammates to interact and revive them. The more teammates that participate in the revival, the higher the reward tier achieved.

**Primary Use Case:** Team-based revival mechanics with configurable reward tiers  
**Architecture Pattern:** Group-based collaborative gameplay with output triggers

---

## Quick Start
### Video Walkthrough:
https://youtu.be/aJBSzEx4XQg

---

## Core Features

### 1. **Dynamic Button Assignment**
- When a player is downed, a free button from the group's pool is automatically assigned
- The button teleports to stay on top of the downed player
- Configurable teleport interval and height offset for smooth tracking
- Buttons are automatically returned to the pool when the player is revived or leaves

### 2. **Multi-Tier Revival System**
- Define unlimited revival tiers based on number of teammates reviving
- Each tier has its own output trigger for custom rewards
- Higher tiers require more teammates to participate simultaneously
- Tiers activate only once per revival (won't trigger multiple times)

### 3. **Automatic Timeout & Force Revive**
- Configurable time limit for teammates to revive the downed player
- Optional automatic revival at the highest tier reached when timeout expires
- Can disable auto-revive to leave players downed if not enough teammates help

### 4. **Group-Based Architecture**
- Fully integrated with `base_group_device` for team/class functionality
- Each group has its own pool of revival buttons
- Players can only revive members of their own group
- Optional self-revive support (can be enabled/disabled)

### 5. **Output Trigger System**
- **Per-Tier Outputs:** Wire custom rewards for each revival tier
- **Player Downed Output:** Triggered when any player goes down
- **Player Revived Output:** Triggered when player is successfully revived
- All triggers pass the relevant agent for custom logic

---

## Settings & Configuration

### Main Device Settings

#### **Revive Settings**
```verse
revive_settings := class<concrete>:
    TimeToRevive: float = 30.0                    # Seconds before auto-revive or timeout
    AllowSelfRevive: logic = false                # Can downed player revive themselves?
    TeleportInterval: float = 0.1                 # How often button repositions (seconds)
    ButtonHeightOffset: float = 1.5               # Height above player (meters)
    ForceReviveOnTimeout: logic = true            # Auto-revive on timeout?
```

**TimeToRevive** (30.0 seconds)
- How long teammates have to revive the downed player before timeout
- Shorter times create urgency; longer times are more forgiving
- Recommended: 15-45 seconds depending on game difficulty

**AllowSelfRevive** (false)
- If `true`: Downed player can interact with their own button to contribute
- If `false`: Only teammates can revive (more collaborative)
- Recommended: `false` for team-focused gameplay

**TeleportInterval** (0.1 seconds)
- How frequently the button repositions on the downed player
- Lower = more accurate tracking, but higher performance cost
- Recommended: 0.1-0.2 seconds for smooth tracking

**ButtonHeightOffset** (1.5 meters)
- Vertical distance to place button above the downed player
- Prevents button from being inside player model or ground
- Recommended: 1.0-2.0 meters

**ForceReviveOnTimeout** (true)
- If `true`: Player auto-revives at highest tier reached when timeout expires
- If `false`: Player stays downed (cleanup happens, no revival)
- Recommended: `true` to prevent permanent down state

#### **Revive Buttons**
```verse
@editable ReviveButtons: []button_device = array{}
```
Array of button devices that will be assigned to downed players. You need at least one button per group. If you have 3 groups and want to support 2 simultaneous downed players per group, you need 6 buttons total.

**Setup:**
1. Place button devices in your map
2. Disable them by default (device will enable/disable automatically)
3. Add all buttons to this array
4. System will distribute them across groups evenly

#### **Down But Not Out Device**
```verse
@editable DownButNotOutDevice: down_but_not_out_device
```
The Fortnite device that manages the "down but not out" player state. This device:
- Detects when players are downed
- Handles the actual revival when triggered
- Required for the system to function

#### **Output Triggers**

**PlayerDownedOutput**
- Triggered when any player in any group is downed
- Passes the downed agent
- Use for: Sound effects, UI notifications, stats tracking

**PlayerRevivedOutput**
- Triggered when a player is successfully revived
- Passes the revived agent
- Use for: Sound effects, visual effects, XP rewards, stats

---

## Revive Tiers

### Tier Configuration

Each tier represents a reward level based on how many teammates are reviving:

```verse
revive_tier := class<concrete><unique>:
    Label: string = ""                           # Descriptive name (e.g., "Bronze Revive")
    ReviverCount: int = 1                        # Teammates needed for this tier
    TierActivatedOutput: trigger_device          # Output trigger for rewards
```

**Example Tier Setup:**

| Tier | Label | ReviverCount | Reward Example |
|------|-------|--------------|----------------|
| 0 | Solo Revive | 1 | 50 XP, Basic Health |
| 1 | Team Revive | 2 | 100 XP, Full Health |
| 2 | Squad Revive | 3 | 200 XP, Full Health + Shield |
| 3 | Heroic Revive | 4 | 500 XP, Full Health + Shield + Speed Boost |

### Tier Activation Logic

- Tiers activate based on **simultaneous** revivers, not cumulative
- Once a tier is reached, it's recorded as the highest tier for that revival
- Higher tiers do NOT deactivate lower tiers (only one tier fires per revival)
- When timeout occurs, player revives at the **highest tier reached**

**Example Scenario:**
1. Player is downed
2. 1 teammate starts reviving → Tier 0 activates (Solo Revive)
3. 2nd teammate joins → Tier 1 activates (Team Revive) 
4. 1st teammate leaves, only 1 reviver now → Still counts as Tier 1 (highest reached)
5. Timeout expires → Player revives, Tier 1 rewards are applied

---

## Architecture & Implementation

### Button Pooling System

**Problem:** Button devices can't be used as map keys (not comparable)  
**Solution:** Store button indices (int) instead of button references

```verse
# Internal State
var AvailableButtonsPerGroup: [int][]int = map{}        # GroupIndex → [ButtonIndices]
var ButtonIndexToDownedAgent: [int]agent = map{}        # ButtonIndex → DownedAgent
```

**Flow:**
1. On init, create array of button indices `[0, 1, 2, 3, ...]`
2. Distribute indices evenly across all groups
3. When player downed, get free index from group's pool
4. Use index to lookup actual button: `ReviveButtons[Index]`
5. When revival complete, return index to pool

### Downed Player Tracking

Each downed player gets a tracker instance:

```verse
downed_player_tracker := class:
    DownedAgent: agent                    # Who is downed
    GroupIndex: int                       # Which group they belong to
    AssignedButtonIndex: int              # Which button is assigned
    CurrentRevivers: []agent              # Who is currently reviving
    HighestTierReached: int              # Best tier achieved so far
    TimeoutTaskActive: logic             # Is timeout running?
    TeleportTaskActive: logic            # Is button tracking active?
```

### Concurrent Task Management

**Three concurrent tasks per downed player:**

1. **Timeout Task** (`StartReviveTimeout`)
   - Waits for `TimeToRevive` seconds
   - Checks if still active, then auto-revives or cleans up

2. **Teleport Task** (`StartButtonTeleportLoop`)
   - Loops every `TeleportInterval` seconds
   - Gets player's FortCharacter position
   - Teleports button to position + height offset

3. **Revive Evaluation** (`HandleReviverProgress`)
   - Triggered when teammate interacts with button
   - Evaluates all tiers to find highest qualifying tier
   - Activates tier output if it's a new highest tier

**Task Cancellation:**
- Tasks check their active flags each iteration
- `CleanupDownedPlayer()` sets all flags to `false`
- Tasks detect cancellation and exit gracefully

---

## Usage Examples

### Example 1: Basic 2-Tier Revival

**Goal:** Simple revival with bonus for 2+ teammates

**Setup:**
1. Create 2 button devices, add to `ReviveButtons`
2. Create 2 revive tiers:
   - Tier 0: ReviverCount = 1, wire to "Basic Health" item granter
   - Tier 1: ReviverCount = 2, wire to "Full Health + Shield" item granter
3. Set `TimeToRevive` = 20 seconds
4. Enable `ForceReviveOnTimeout`

**Result:**
- Solo revive = Basic health restoration
- Team revive = Full health + shields
- After 20 seconds, auto-revives at whatever tier was reached

### Example 2: No Auto-Revive (Hardcore Mode)

**Goal:** Players must have teammate support or they stay downed

**Setup:**
1. Set `ForceReviveOnTimeout` = `false`
2. Set `TimeToRevive` = 30 seconds
3. Create single tier:
   - Tier 0: ReviverCount = 1, wire to health restoration

**Result:**
- If no teammates revive within 30 seconds, player cleanup happens but no revival
- Forces high teamwork requirement

### Example 3: Self-Revive with Penalty

**Goal:** Players can revive themselves but get lower rewards

**Setup:**
1. Set `AllowSelfRevive` = `true`
2. Create 2 tiers:
   - Tier 0: ReviverCount = 1, wire to "Half Health" item granter
   - Tier 1: ReviverCount = 2, wire to "Full Health + Bonus" item granter

**Result:**
- Downed player can self-revive → Tier 0 (half health)
- If teammate helps → Tier 1 (full health + bonus)
- Encourages teamwork but allows solo play

### Example 4: Multi-Group Setup

**Goal:** 3 teams, each can revive independently

**Setup:**
1. Create 3 player groups in base_group_device
2. Create 6 buttons (2 per group for simultaneous downs)
3. Each group gets equal share of button pool automatically

**Result:**
- Group 0 buttons: indices [0, 1]
- Group 1 buttons: indices [2, 3]
- Group 2 buttons: indices [4, 5]
- Teams revive independently without interfering

---

## Best Practices

### Performance Optimization

**Button Count:**
- Minimum: 1 per group
- Recommended: 2-3 per group (handles multiple simultaneous downs)
- Maximum: Based on expected max simultaneous downed players

**Teleport Interval:**
- Lower values (0.05s) = smoother tracking but more CPU
- Higher values (0.2s) = jerkier but better performance
- Recommended: 0.1s for 60 FPS smooth tracking

**Tier Count:**
- Keep tiers to 3-5 maximum for clarity
- More tiers = more granular rewards but complex setup

### Design Considerations

**Reviver Count Scaling:**
- Don't require more revivers than typical team size
- Example: 4-player teams → max tier should be 3-4 revivers
- Leave room for one player to defend while others revive

**Timeout Duration:**
- Should account for: finding downed player + travel time + revival
- Recommended: 20-30 seconds for medium maps
- Adjust based on map size and movement speed

**Reward Balancing:**
- Higher tiers should feel meaningfully better
- Don't make solo revive too punishing (discourages play)
- Consider non-combat rewards (XP, cosmetics) for lower tiers

### Common Pitfalls

❌ **Not enough buttons**
- If all buttons in use, new downed players can't be revived
- Solution: Add 1-2 extra buttons as buffer

❌ **Timeout too short**
- Players can't reach each other in time
- Solution: Test with actual gameplay, adjust accordingly

❌ **Tier gaps too large**
- Example: Tier 0 = 1 reviver, Tier 1 = 5 revivers (skips 2-4)
- Solution: Create gradual progression (1, 2, 3, 4)

❌ **Forgetting to assign Down But Not Out Device**
- System won't detect downs or perform revivals
- Solution: Always wire the DBNO device in UEFN

---

## Debugging & Troubleshooting

### Enable Debug Logging

In the device settings, enable debug mode:
```verse
Debug.EnableDebug = true
```

**Key Log Messages:**
- `"Agent downed in Group X"` - Player detected as downed
- `"Assigned button to downed player"` - Button successfully assigned
- `"No free buttons available"` - All buttons in use (add more)
- `"Revive tier 'X' activated"` - Tier triggered
- `"Timeout reached, force reviving"` - Auto-revive occurred
- `"Cleaned up downed player tracker"` - Revival completed

### Common Issues

**Issue: Buttons don't appear on downed players**
- Check: Are buttons added to `ReviveButtons` array?
- Check: Is `DownButNotOutDevice` assigned?
- Check: Are there free buttons in the pool?

**Issue: Tiers not activating**
- Check: Are teammates in the same group as downed player?
- Check: Is `ReviverCount` set correctly (1, 2, 3...)?
- Check: Are output triggers wired to actual devices?

**Issue: Button stays in world after revival**
- Check: Is `CleanupDownedPlayer()` being called?
- Check: Are task active flags being reset?
- This is a critical bug - check debug logs

**Issue: Self-revive not working**
- Check: Is `AllowSelfRevive` set to `true`?
- Check: Is downed player in a valid group?

---

## Integration with Other UEFNiVERSE Devices

### Shared Progress Tracker
- Wire `PlayerRevivedOutput` → Tracker Increment
- Track total team revives as a milestone
- Reward teams that revive frequently

### Team Buff Zone
- Place revive button spawn zones near buff zones
- Create synergy: revive in buff zone for bonus tier
- Use buff zone VFX to highlight safe revival areas

### Custom Devices
- Use `PlayerDownedOutput` to trigger custom "man down" alerts
- Use tier outputs to grant custom items, effects, or abilities
- Integrate with progression systems using agent data

---

## Technical Reference

### Key Methods

**Public Methods:**
```verse
Initialize()<suspends>:void
    - Sets up button pools per group
    - Subscribes to down but not out events
    - Initializes button interaction handlers

OnAgentDowned(Agent: agent):void
    - Triggered by DBNO device
    - Assigns free button from group pool
    - Starts timeout and teleport tasks

OnButtonInteracted(Agent: agent):void
    - Checks if agent can revive (same group, not self)
    - Adds agent to CurrentRevivers list
    - Evaluates tiers for tier activation

PerformRevive(DownedAgent: agent)<suspends>:void
    - Uses DBNO device to actually revive player
    - Fires PlayerRevivedOutput
    - Calls cleanup

CleanupDownedPlayer(Agent: agent):void
    - Stops all concurrent tasks
    - Returns button to pool
    - Resets tier activation states
    - Removes from tracking maps
```

### Internal State

```verse
var DownedPlayers: [agent]downed_player_tracker = map{}
    # Maps each downed agent to their tracker instance

var AvailableButtonsPerGroup: [int][]int = map{}
    # Maps group index to array of available button indices

var ButtonIndexToDownedAgent: [int]agent = map{}
    # Maps button index to the agent it's assigned to
```

### Performance Characteristics

**Memory:**
- O(1) per downed player (single tracker instance)
- O(B) for button pool where B = total buttons
- O(D) for active downed players where D = current downed count

**CPU:**
- O(D × T) per interval where T = teleport interval
- O(R) per button interaction where R = tier count
- Minimal overhead when no players downed

---

## Version History

**v1.0** - Initial Release (February 2026)
- Group-based button pooling system
- Multi-tier revival mechanics
- Timeout and auto-revive functionality
- Output trigger integration
- Full UEFNiVERSE architecture compliance

---

## Support

**Part of UEFNiVERSE** - Professional Verse devices for UEFN creators  
**Developers:** PineFruit, LastMade | **Organization:** Chartis / UEFNiVERSE

**Resources:**
- [Main Repository](https://github.com/your-repo/UEFNiVERSE) - Full device collection
- Source: `Device3/advanced_revive_system.verse`
- Dependencies: `Core/base_device.verse`, `Core/base_group_device.verse`, `utility.verse`
- Inline code documentation for detailed implementation

**Contact:**
- Discord: PineFruit, LastMadeUEFN
- Epic: PineFruitDev, LastMadeMe
- Twitter: @PineFruitDev, @LastMadeUefn

**Contributions:** See main repository for contribution guidelines

---

*Last Updated: February 2026*  
*Documentation Version: 1.0*  
*Device Version: 1.0*

**License:** [Apache 2.0](https://choosealicense.com/licenses/apache-2.0/) with [Commons Clause](https://commonsclause.com/)  
**Powered by:** [Project Moonlight](https://www.projectmoonlight.org/)
