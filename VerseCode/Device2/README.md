# Device2: Team Buff Zone

**Part of:** [UEFNiVERSE Free-Verse Device Collection](https://github.com/your-repo/UEFNiVERSE)  
**Extends:** `base_group_device` (Core architecture)  
**Dependencies:** `Core/base_device.verse`, `Core/base_group_device.verse`, `utility.verse`

---

## What It Does
Creates collaborative buff zones that reward players for standing together with tiered buffs based on player count or time.

---

## Overview

The **Team Buff Zone** device creates collaborative buff zones that reward players for standing together. Players receive buffs based on the number of teammates in the zone or the time spent together, encouraging teamwork and strategic positioning.

---

## Quick Start
### Video Walkthrough:
https://youtu.be/sy-JoLAqkZo

### Basic Setup
1. Add the `team_buff_zone` device to your island
2. Create one or more `zone_tracker` entries in the **Zones** array
3. Assign a `volume_device` to detect when players enter/exit
4. Configure buff tiers with activation requirements
5. Wire up output triggers for your custom rewards
6. Assign one empty VFX powerup to **ClearVisualsDevice** (main device level)

### Simple Example: 2-Tier Zone
```
Zone Settings:
├── MinTeammatesRequired: 1
├── TierStackingMode: SingleTier
└── BuffMode: SingleTrigger

Tier 1 (Speed Boost):
├── ActivationMode: PlayerCount
├── TeammateCount: 1
├── ActivatedOutput → Movement Modulator (150% speed)
└── VisualsDevices: [Speed VFX Powerup]

Tier 2 (Mega Speed):
├── ActivationMode: PlayerCount
├── TeammateCount: 2
├── ActivatedOutput → Movement Modulator (200% speed)
└── VisualsDevices: [Mega Speed VFX Powerup]
```

---

## Architecture

### Device Hierarchy
```
team_buff_zone (Main Device - extends base_group_device)
├── ClearVisualsDevice (Universal VFX clear powerup)
└── Zones: []zone_tracker
    ├── Zone (volume_device)
    ├── Settings (buff_zone_settings)
    ├── BuffTiers: []buff_tier
    │   ├── ActivationMode (PlayerCount or TimeInZone)
    │   ├── ActivatedOutput (trigger_device)
    │   ├── DeactivatedOutput (trigger_device)
    │   └── VisualsDevices (VFX powerups)
    ├── ZoneEnteredOutput (trigger_device)
    └── ZoneExitedOutput (trigger_device)
```

### Group Integration
- Uses `base_group_device` for player group management
- Each zone tracks players per group independently
- Groups are assigned via trigger devices (same as shared_progress_tracker)
- Supports team-based collaboration and isolated group progression

---

## Core Features

### 1. Tier Activation Modes

#### PlayerCount Mode
Tiers activate based on the number of teammates in the zone.

**Use Cases:**
- "Stand together" buffs
- Team size rewards
- Formation bonuses

**Example:**
```
Tier 1: 2 players → Small damage boost
Tier 2: 3 players → Medium damage boost
Tier 3: 4 players → Large damage boost
```

#### TimeInZone Mode
Tiers activate based on how long teammates have been in the zone together.

**Use Cases:**
- Capture point mechanics
- Charging stations
- Ritual casting zones

**Example:**
```
Tier 1: 5 seconds → Begin channeling
Tier 2: 15 seconds → Half charged
Tier 3: 30 seconds → Fully charged
```

#### Mixed Mode
Combine both modes in a single zone for complex mechanics.

**Example:**
```
Tier 1: 10 seconds (TimeInZone) → Warmup bonus
Tier 2: 2 players (PlayerCount) → Team synergy
Tier 3: 30 seconds (TimeInZone) → Ultimate power
```

---

### 2. Tier Stacking Modes

#### SingleTier Mode (Default)
Only the **highest qualifying tier** is active at once.

**Behavior:**
- Players climb tier ladder: Tier 1 → Tier 2 → Tier 3
- When a higher tier activates, lower tiers deactivate
- VFX and triggers fire only for the active tier
- When dropping down (player leaves), lower tier re-activates

**Example Flow:**
1. Player 1 enters → Gets Tier 1 (1 player required)
2. Player 2 enters → Both get Tier 2 (2 players required), Tier 1 deactivates
3. Player 2 leaves → Player 1 drops back to Tier 1

**Best For:**
- Progressive power systems
- Scaling buffs
- King-of-the-hill mechanics

#### MultipleTiers Mode
**All qualifying tiers** can be active simultaneously.

**Behavior:**
- Triggers fire for ALL qualifying tiers
- VFX applied only for the highest tier (prevents conflicts)
- Players can stack multiple buff effects

**Example:**
```
Player with 2 teammates in zone for 15 seconds gets:
✓ Tier 1 trigger (1 player) → +10% damage
✓ Tier 2 trigger (2 players) → +5% speed
✓ Tier 3 trigger (10 seconds) → Regeneration
✓ VFX: Only Tier 3 visuals shown
```

**Best For:**
- Stackable buff systems
- Multi-layered rewards
- Complex synergy mechanics

---

### 3. Buff Modes

#### SingleTrigger Mode
Outputs fire **once** when tier activates/deactivates.

**Best For:**
- One-time rewards (grant items, currency)
- Permanent buffs
- Achievement unlocks

#### Continuous Mode
Outputs fire **repeatedly** at specified interval while tier is active.

**Use Cases:**
- Healing zones (heal every 1 second)
- Damage zones (damage every 0.5 seconds)
- Resource generation (grant currency every 5 seconds)

**Settings:**
- `ContinuousInterval`: Time between triggers (seconds)

**Performance Note:**
- Uses **one loop per group** (not per tier) for efficiency
- All active tiers checked each interval

---

## Configuration Reference

### team_buff_zone (Main Device)

| Property | Type | Description |
|----------|------|-------------|
| `Groups` | `[]player_group` | Player groups (from base_group_device) |
| `Zones` | `[]zone_tracker` | Array of buff zones |
| `ClearVisualsDevice` | `?visual_effect_powerup_device` | Universal VFX clear powerup (empty powerup) |
| `Debug` | `debug_settings` | Debug logging settings |

---

### zone_tracker

| Property | Type | Description |
|----------|------|-------------|
| `Label` | `string` | Zone name for debugging |
| `Zone` | `volume_device` | Volume that defines the buff area |
| `Settings` | `buff_zone_settings` | Zone behavior configuration |
| `BuffTiers` | `[]buff_tier` | Array of buff tiers (ordered lowest to highest) |
| `ZoneEnteredOutput` | `trigger_device` | Fires when any agent enters (passes agent) |
| `ZoneExitedOutput` | `trigger_device` | Fires when any agent exits (passes agent) |

---

### buff_zone_settings

| Property | Type | Default | Description |
|----------|------|---------|-------------|
| `MinTeammatesRequired` | `int` | 2 | Minimum players needed to start zone |
| `ActivationDelay` | `float` | 0.0 | Delay (seconds) before buffs activate |
| `DeactivationDelay` | `float` | 0.0 | Delay (seconds) before buffs deactivate |
| `RequireAllGroupMembers` | `logic` | false | All group members must be present (future use) |
| `AllowMultipleGroups` | `logic` | false | Different groups can mix (future use) |
| `TierStackingMode` | `tier_stacking_mode` | SingleTier | SingleTier or MultipleTiers |
| `BuffMode` | `buff_mode` | SingleTrigger | SingleTrigger or Continuous |
| `ContinuousInterval` | `float` | 1.0 | Time between continuous triggers |

---

### buff_tier

| Property | Type | Default | Description |
|----------|------|---------|-------------|
| `Label` | `string` | "" | Tier name for debugging |
| `ActivationMode` | `tier_activation_mode` | PlayerCount | PlayerCount or TimeInZone |
| `TeammateCount` | `int` | 2 | Players required (PlayerCount mode) |
| `TimeRequired` | `float` | 5.0 | Seconds required (TimeInZone mode) |
| `ActivatedOutput` | `trigger_device` | - | Fires when tier activates (passes agents) |
| `DeactivatedOutput` | `trigger_device` | - | Fires when tier deactivates (passes agents) |
| `VisualsDevices` | `[]visual_effect_powerup_device` | [] | VFX powerups to show when active |

---

## Visual Effects (VFX) System

### How VFX Work
1. **Show VFX**: Player picks up powerups from `VisualsDevices` array
2. **Override**: New VFX automatically override old ones (no clear needed)
3. **Clear VFX**: Player picks up `ClearVisualsDevice` when leaving zone

### VFX Best Practices

#### Per-Tier VFX Setup
```
Tier 1: [Blue Aura Powerup]
Tier 2: [Green Aura Powerup]  ← Overrides Tier 1
Tier 3: [Gold Aura Powerup]   ← Overrides Tier 2
```

#### Universal Clear Device
```
Main Device:
└── ClearVisualsDevice: [Empty Powerup]
    (Used by all zones and tiers when clearing)
```

#### Multiple VFX Per Tier
You can layer multiple visual effects:
```
Tier 3 VisualsDevices:
├── [Particle Effect Powerup]
├── [Glow Effect Powerup]
└── [Aura Effect Powerup]
```

### VFX Application Rules

**SingleTier Mode:**
- Only highest tier gets VFX
- Lower tier VFX never show

**MultipleTiers Mode:**
- All tiers fire triggers
- Only highest tier gets VFX (prevents visual conflicts)

**When Player Leaves:**
- `ClearVisualsDevice` picked up
- All VFX removed

---

## Output Triggers

### Trigger Types

#### ActivatedOutput
Fires when tier becomes active for a player.

**Receives:** The agent(s) who activated this tier

**Common Uses:**
- Apply buffs (Movement Modulator, Health Granter)
- Grant items (Item Granter)
- Give currency (Economy Device)
- Trigger effects (Particle Emitter)

#### DeactivatedOutput
Fires when tier becomes inactive for a player.

**Receives:** The agent(s) who lost this tier

**Common Uses:**
- Remove buffs
- Take items
- Trigger removal effects

#### ZoneEnteredOutput
Fires when ANY agent enters the zone.

**Receives:** The entering agent

**Common Uses:**
- Welcome messages
- Sound effects
- Entry analytics

#### ZoneExitedOutput
Fires when ANY agent exits the zone.

**Receives:** The exiting agent

**Common Uses:**
- Farewell messages
- Exit sound effects
- Analytics tracking

---

## Example Setups

### Example 1: Healing Zone
**Concept:** Stand together to heal faster.

```
Zone Settings:
├── MinTeammatesRequired: 1
├── TierStackingMode: SingleTier
├── BuffMode: Continuous
└── ContinuousInterval: 1.0

Tier 1 (Slow Heal):
├── ActivationMode: PlayerCount
├── TeammateCount: 1
├── ActivatedOutput → Health Granter (+10 HP)
└── VisualsDevices: [Green Healing Particles]

Tier 2 (Fast Heal):
├── ActivationMode: PlayerCount
├── TeammateCount: 2
├── ActivatedOutput → Health Granter (+25 HP)
└── VisualsDevices: [Bright Green Healing Particles]

Tier 3 (Mega Heal):
├── ActivationMode: PlayerCount
├── TeammateCount: 3
├── ActivatedOutput → Health Granter (+50 HP)
└── VisualsDevices: [Golden Healing Particles]
```

---

### Example 2: Capture Point
**Concept:** Hold the point for 30 seconds to capture.

```
Zone Settings:
├── MinTeammatesRequired: 1
├── TierStackingMode: SingleTier
├── BuffMode: SingleTrigger
└── ActivationDelay: 0.0

Tier 1 (Capturing...):
├── ActivationMode: TimeInZone
├── TimeRequired: 10.0
├── ActivatedOutput → HUD Message "Capturing... 33%"
└── VisualsDevices: [Blue Capture Particles]

Tier 2 (Almost There...):
├── ActivationMode: TimeInZone
├── TimeRequired: 20.0
├── ActivatedOutput → HUD Message "Capturing... 66%"
└── VisualsDevices: [Purple Capture Particles]

Tier 3 (Captured!):
├── ActivationMode: TimeInZone
├── TimeRequired: 30.0
├── ActivatedOutput → HUD Message "Point Captured!"
├── ActivatedOutput → Item Granter (Victory Token)
└── VisualsDevices: [Gold Victory Particles]
```

---

### Example 3: Combat Synergy Zone
**Concept:** Stack multiple combat buffs.

```
Zone Settings:
├── MinTeammatesRequired: 1
├── TierStackingMode: MultipleTiers
└── BuffMode: SingleTrigger

Tier 1 (Damage):
├── ActivationMode: PlayerCount
├── TeammateCount: 1
├── ActivatedOutput → Damage Amplifier (+20%)
├── DeactivatedOutput → Damage Amplifier (Reset)
└── VisualsDevices: [Red Attack Aura]

Tier 2 (Speed):
├── ActivationMode: PlayerCount
├── TeammateCount: 2
├── ActivatedOutput → Movement Modulator (+30%)
├── DeactivatedOutput → Movement Modulator (Reset)
└── VisualsDevices: [Yellow Speed Trails]

Tier 3 (Shield):
├── ActivationMode: TimeInZone
├── TimeRequired: 10.0
├── ActivatedOutput → Shield Granter (+50 Shield)
├── DeactivatedOutput → (Shield naturally depletes)
└── VisualsDevices: [Blue Shield Bubble]

Result with 2 players after 10 seconds:
- All 3 triggers fire
- Player gets: +20% damage, +30% speed, +50 shield
- VFX: Only Blue Shield Bubble shows (highest tier)
```

---

### Example 4: King of the Hill
**Concept:** More players = more points per second.

```
Zone Settings:
├── MinTeammatesRequired: 1
├── TierStackingMode: SingleTier
├── BuffMode: Continuous
└── ContinuousInterval: 1.0

Tier 1 (1 Point/sec):
├── ActivationMode: PlayerCount
├── TeammateCount: 1
├── ActivatedOutput → Score Manager (+1 point)
└── VisualsDevices: [Silver Crown]

Tier 2 (3 Points/sec):
├── ActivationMode: PlayerCount
├── TeammateCount: 2
├── ActivatedOutput → Score Manager (+3 points)
└── VisualsDevices: [Gold Crown]

Tier 3 (5 Points/sec):
├── ActivationMode: PlayerCount
├── TeammateCount: 3
├── ActivatedOutput → Score Manager (+5 points)
└── VisualsDevices: [Diamond Crown]
```

---

## Advanced Usage

### Dynamic Tier Progression
The zone timer keeps running as long as minimum players are present. This enables:

**Scenario:**
```
Player 1 enters → Timer starts
Player 1 stays for 15 seconds → Gets Tier 2 (15s requirement)
Player 2 joins → INSTANTLY gets Tier 2 (time already elapsed)
Player 2 leaves, Player 3 joins → Player 3 INSTANTLY gets Tier 2
```

This creates a "zone progression" where the zone itself has a state, not just individual players.

---

### Mixed Activation Modes

Combine PlayerCount and TimeInZone tiers creatively:

```
Tier 1: 1 player → "Defender" buff
Tier 2: 5 seconds → "Focused" buff (stayed long enough)
Tier 3: 2 players → "Coordinated" buff
Tier 4: 20 seconds → "Dedicated" buff
Tier 5: 3 players → "Squad" buff

With SingleTier mode:
- Solo player gets Tier 1 → Tier 2 → Tier 4
- 2 players jump to Tier 3 → Tier 4
- 3 players jump to Tier 5
```

---

### Activation Delays

Use delays to prevent buff spam from rapid entry/exit:

```
Settings:
├── ActivationDelay: 2.0   ← Must stay 2s to activate
└── DeactivationDelay: 1.0 ← 1s grace period after leaving
```

**Use Cases:**
- Prevent "bunny hopping" for instant buffs
- Grace period for players to return to zone
- Smoother buff transitions

---

## Group Integration

### Group Setup
The device uses `base_group_device` for player groups:

```
Groups Array:
├── Group 0 (Team Red)
│   ├── AssignTrigger → (Trigger on red spawn)
│   └── RemoveTrigger → (Trigger on leave)
└── Group 1 (Team Blue)
    ├── AssignTrigger → (Trigger on blue spawn)
    └── RemoveTrigger → (Trigger on leave)
```

### Group Isolation
Each group's progress is tracked independently:
- Red team's timer is separate from Blue team's timer
- Groups can be in the same physical zone but track differently
- Perfect for team-based games

### Cross-Group Zones
Set `AllowMultipleGroups: true` to allow different groups to contribute to the same zone (future feature).

---

## Performance Considerations

### Optimization Features
1. **Single Continuous Loop**: One loop per group (not per tier)
2. **Efficient Tier Evaluation**: All tiers evaluated in one pass
3. **Per-Player Tracking**: Only tracks active players
4. **Minimal Allocations**: Reuses data structures

### Recommended Limits
- **Zones per device**: 1-10 zones
- **Tiers per zone**: 1-10 tiers
- **Players per group**: Tested up to 16 players
- **Continuous interval**: Minimum 0.1 seconds

---

## Debugging

### Debug Settings
Enable debug logging in the main device:

```
Debug Settings:
├── EnableDebug: true
└── Identifier: "Buff Zone"
```

### Debug Output Examples
```
[Buff Zone - Zone Tracker] Agent entered zone 'Healing Circle' (Group 0: Team Red)
[Buff Zone - Zone Tracker] Group now has 2 agents in zone
[Buff Zone - Buff Tier] Buff tier 'Mega Heal' activated for group 0 (requires 2 teammates)
[Buff Zone - Zone 0] Continuous buff triggered for group 0 (Tier: Mega Heal)
```

### Common Issues

**Issue: VFX not clearing**
- Check that `ClearVisualsDevice` is assigned at main device level
- Verify it's an empty visual effect powerup

**Issue: Tiers not activating**
- Check `MinTeammatesRequired` is met
- Verify tier requirements (TeammateCount or TimeRequired)
- Enable debug logging to see activation events

**Issue: Multiple VFX showing**
- This is expected in MultipleTiers mode
- Only highest tier VFX should show (by design)
- Check that tiers are using different VFX powerups

**Issue: Timer not progressing**
- Timer only runs when `MinTeammatesRequired` players are in zone
- Timer resets if players drop below minimum
- Check debug logs for "started zone timer" message

---

## Version History

**v1.0** - Initial Release (2024)
- PlayerCount and TimeInZone activation modes
- SingleTier and MultipleTiers stacking modes
- Per-player VFX system with universal clear device
- Single continuous loop optimization
- Group-based collaboration support

---

## Support

**Part of UEFNiVERSE** - Professional Verse devices for UEFN creators  
**Developers:** PineFruit, LastMade | **Organization:** Chartis / UEFNiVERSE

**Resources:**
- [Main Repository](https://github.com/your-repo/UEFNiVERSE) - Full device collection
- Inline code documentation for detailed implementation
- Example configurations throughout this README

**Contact:**
- Discord: PineFruit, LastMadeUEFN
- Epic: PineFruitDev, LastMadeMe
- Twitter: @PineFruitDev, @LastMadeUefn

**Contributions:** See main repository for contribution guidelines

---

**License:** [Apache 2.0](https://choosealicense.com/licenses/apache-2.0/) with [Commons Clause](https://commonsclause.com/)  
**Powered by:** [Project Moonlight](https://www.projectmoonlight.org/)
