# Device5: Hype Beacon

**Part of:** [UEFNiVERSE Free-Verse Device Collection](https://github.com/UEFNiVERSE/Free-Verse)
**Extends:** `base_device` (Core architecture, groupless base)
**Dependencies:** `Core/base_device.verse`, `Core/base_group_device.verse`, `utility.verse`

---

## What It Does
Runs island-wide hype events on a schedule: loot rain, mystery drops, double reward hours, dance-offs. The device owns the timing, the countdown, the announcement and the celebration. It owns none of the reward, so every moment that matters fires an output trigger you wire to whatever you already built.

---

## Overview

The **Hype Beacon** is a scheduler. You describe a set of events, each with its own schedule, countdown, gather zone and outputs, and the beacon runs them for the lifetime of the session. Nothing about it assumes a game loop or a round, so it behaves the same in a persistent tycoon, a social hub, or a steal map.

An event can name a **gather zone**. When it does, the beacon tracks how many players converge on it and fires **attendance tiers** as thresholds are crossed. That is what turns a scheduled reward into a scheduled *moment*: everyone in one place, at one time, watching the same thing happen.

**Primary Use Case:** Retention and spectacle. Give an island a heartbeat that players learn to show up for
**Architecture Pattern:** Editable configuration separated from runtime state, one scheduler coroutine per configured event

---

## Quick Start

1. Copy `VerseCode/Device5/`, the `Core` folder, and `utility.verse` into your project
2. Add `Device5 <public> := module:` to your `module_access.verse` under the `VerseCode` block
3. Place one Hype Beacon device on your island
4. Assign a HUD Message device to `GlobalAnnounceHUD` so announcements have somewhere to go
5. Add an entry to the `Events` array and give it a `Label`, for example "Loot Rain"
6. Wire that event's `StartedOutput` to whatever the event should actually do
7. Launch a session. After `FirstEventDelay` the event announces, runs for `Duration`, and ends

One beacon can run every event on your island. You do not need one device per event.

---

## Core Features

### 1. **Three Schedule Modes**
- **AtIslandStart:** runs once, `FirstEventDelay` seconds after the island starts
- **Repeating:** runs on a loop, `RepeatInterval` seconds between runs
- **TriggerOnly:** never runs on its own, only when `StartTrigger` fires
- Modes are per event, so one beacon can hold a repeating loot rain and a trigger-only boss spawn

### 2. **Countdowns That Do Not Lie**
- Add as many countdown steps as you like, in any order, they are sorted longest-first automatically
- Countdown time is subtracted from the interval containing it, so a 30 second warning on a 600 second loop fires at 570, not at 600 with the event running 30 seconds late
- Each step has its own output trigger and optional custom text
- A countdown longer than the interval it sits in is clamped and logged rather than silently shifting the schedule

### 3. **Attendance Tiers**
- Name a gather zone volume and define thresholds by concurrent player count
- Each tier fires once per run, passing every agent present, with optional VFX powerups
- Tiers reset at the start of the next run
- Latecomers fire `AgentJoinedEventOutput`, so arriving after a tier has fired can still be rewarded

### 4. **Pulse Output**
- Set `PulseInterval` above zero and `PulseOutput` fires on that beat for the whole event
- This is the "double reward hour" case: one long event, a reward every N seconds
- Set it to zero and the event is a single start and end, nothing in between

### 5. **Manual Override**
- `StartTrigger` starts an event immediately, skipping the countdown, in any schedule mode
- `StopTrigger` ends a running event early
- Both are available to Verse as `StartEvent(Index)` and `StopEvent(Index)`

### 6. **Overlap Control**
- `AllowOverlapping` off (the default) means an event that comes due while another is running is skipped and logged, rather than announcing over the top of it
- Turn it on when events are independent and stacking them is the point

### 7. **Output Trigger System**
- **Per event:** `StartedOutput`, `EndedOutput`, `PulseOutput`, `AgentJoinedEventOutput`
- **Per countdown step:** `CountdownOutput`
- **Per attendance tier:** `ReachedOutput`
- **Per beacon:** `AnyEventStartedOutput`, `AnyEventEndedOutput`

---

## Settings & Configuration

### Main Device Settings

| Property | Type | Default | Description |
|---|---|---|---|
| `Events` | `[]hype_event` | `array{}` | The events this beacon runs. Each keeps its own schedule, countdown and outputs |
| `ClearVisualsDevice` | `?visual_effect_powerup_device` | `false` | Empty powerup picked up to clear tier VFX when an event ends. Shared across every event |
| `GlobalAnnounceHUD` | `?hud_message_device` | `false` | HUD message device used by any event that does not name its own |
| `AllowOverlapping` | `logic` | `false` | Whether several events may run at once |
| `AnyEventStartedOutput` | `trigger_device` | `trigger_device{}` | Fires when any event on this beacon starts |
| `AnyEventEndedOutput` | `trigger_device` | `trigger_device{}` | Fires when any event on this beacon ends |

Inherited from `base_device`: `InitTrigger` (wait for a trigger before initializing) and `Debug` (the shared `debug_settings` block).

### Event Settings (`hype_event.Settings`)

| Property | Type | Default | Description |
|---|---|---|---|
| `ScheduleMode` | `hype_schedule_mode` | `Repeating` | `AtIslandStart`, `Repeating` or `TriggerOnly` |
| `FirstEventDelay` | `float` | `120.0` | Seconds before the first run. Countdown happens inside this window |
| `RepeatInterval` | `float` | `600.0` | Seconds between runs, `Repeating` only |
| `EndMode` | `hype_end_mode` | `FixedDuration` | `FixedDuration` ends by itself, `UntilTriggered` waits for `StopTrigger` |
| `Duration` | `float` | `60.0` | How long the event lasts. `FixedDuration` only |
| `PulseInterval` | `float` | `0.0` | Seconds between `PulseOutput` fires. `0.0` disables pulsing |
| `RequireMinimumAttendance` | `int` | `0` | Players needed in the zone before tiers may fire. `0` disables the gate |

### Event Properties (`hype_event`)

| Property | Type | Default | Description |
|---|---|---|---|
| `Label` | `string` | `"Hype Event"` | Name used in announcements and debug logs |
| `Settings` | `hype_event_settings` | `hype_event_settings{}` | The timing block above |
| `CountdownSteps` | `[]hype_countdown_step` | `array{}` | Announcements before the start |
| `GatherZone` | `?volume_device` | `false` | Where players converge. Attendance tiers need it |
| `AttendanceTiers` | `[]hype_attendance_tier` | `array{}` | Convergence rewards |
| `StartTrigger` | `?trigger_device` | `false` | Starts this event now, skipping the countdown |
| `StopTrigger` | `?trigger_device` | `false` | Ends this event early. Required for `UntilTriggered` |
| `AnnounceHUD` | `?hud_message_device` | `false` | Per event HUD. Falls back to `GlobalAnnounceHUD` |
| `StartedOutput` | `trigger_device` | `trigger_device{}` | Fires when the event starts |
| `EndedOutput` | `trigger_device` | `trigger_device{}` | Fires when the event ends, however it ended |
| `PulseOutput` | `trigger_device` | `trigger_device{}` | Fires on `PulseInterval` while running |
| `AgentJoinedEventOutput` | `trigger_device` | `trigger_device{}` | Fires when a player enters the zone mid-event. Passes the agent |

### Countdown Step Properties (`hype_countdown_step`)

| Property | Type | Default | Description |
|---|---|---|---|
| `Label` | `string` | `""` | Organisational only, never shown to players |
| `SecondsBefore` | `float` | `30.0` | How long before the start this fires |
| `Message` | `string` | `""` | Custom text. Empty uses `"{Label} starts in {Seconds} seconds!"` |
| `CountdownOutput` | `trigger_device` | `trigger_device{}` | Fires at this step. No agent, the countdown is island-wide |

### Attendance Tier Properties (`hype_attendance_tier`)

| Property | Type | Default | Description |
|---|---|---|---|
| `Label` | `string` | `""` | Used in debug logs |
| `PlayersRequired` | `int` | `2` | Concurrent players in the zone to reach this tier |
| `ReachedOutput` | `trigger_device` | `trigger_device{}` | Fires once per tier per run, once per agent present |
| `VisualsDevices` | `[]visual_effect_powerup_device` | `array{}` | Picked up by everyone present when reached |

---

## Events and Scheduling

### How a run unfolds

For a `Repeating` event with `FirstEventDelay 300`, `RepeatInterval 600`, `Duration 60`, and countdown steps at 60 and 10 seconds:

```
T+240   countdown step at 60s fires   "Loot Rain starts in 60 seconds!"
T+290   countdown step at 10s fires   "Loot Rain starts in 10 seconds!"
T+300   event starts                  StartedOutput, tiers evaluated
T+360   event ends                    EndedOutput, tier VFX cleared
T+900   next countdown begins         (600 after the previous countdown started)
```

The first countdown fires at 240, not 300, because the longest countdown step is subtracted from the delay. The announced time is the truth.

### Tier activation logic

Tiers are evaluated when the event starts and again whenever a player enters the zone mid-event. A tier fires when all of the following hold:

1. The event is running
2. Attendance is at or above `RequireMinimumAttendance` (skipped when that is `0`)
3. Attendance is at or above the tier's `PlayersRequired`
4. The tier has not already fired during this run

All qualifying tiers fire, not just the highest. A run that jumps from two players to ten fires every tier it passed through, in array order. This is deliberate: a tier is a milestone that was reached, not a state the group is in, which is the main way this differs from Device2's buff tiers.

Tiers never deactivate. They reset when the next run begins.

---

## Architecture & Implementation

### Configuration and runtime are separate classes

`hype_event` is pure editable configuration: no mutable state, no events, nothing the editor has to serialize beyond plain properties and device references. Each configured event gets a `hype_event_runner` built during `Initialize`, and the runner owns every `var` and every coroutine.

```
# Built once per configured event, never exposed to the editor
Runner := hype_event_runner:
    Config := Event
    Manager := Self
    Index := Idx
    ClearDevice := ClearVisualsDevice
```

This mirrors how Device4 pairs `pro_social_feed` with `social_feed_widget`. The practical reason is that `event()` fields are only known to work on plain Verse classes: Device4's `Stop : event()` lives on a class the editor never sees, while Device2's editable `zone_tracker` holds only `var` state and device references. Keeping the signal off the editable class avoids the question entirely.

### The event race

A running event is a three-way `race`:

```
race:
    block:
        if (Settings.EndMode = hype_end_mode.FixedDuration):
            Sleep(Settings.Duration)
        else:
            StopSignal.Await()
    StopSignal.Await()
    RunPulseLoop()
```

Two details matter and both are easy to get wrong. A race ends as soon as **any** branch completes, so the timer branch must never fall through: an `if` with no `else` would finish instantly in `UntilTriggered` mode and end the event the moment it started. And `RunPulseLoop` idles on a fixed tick when no pulse is configured rather than awaiting the stop signal a second time, because two subscriptions to one event inside one race is not an assumption worth making.

Putting the pulse loop inside the race is what keeps the bookkeeping small. Device2 spawns its continuous loop and has to carry a `ContinuousLoopActive` map to shut it down later. Here the loop dies with the race, so there is no liveness flag to leak.

### Attendance storage

Attendance and tier state live behind accessors (`Attendees`, `AttendanceCount`, `IsAttending`, `AddAttendee`, `RemoveAttendee`, `HasTierFired`, `MarkTierFired`, `ResetTiersFired`). Nothing outside those methods touches the underlying list or map.

Events here are island-wide, so a flat `[]agent` and a flat `[int]logic` is all they need. Should group filtering ever be added, those become `[int][]agent` and `[int][int]logic` keyed by group index and only the accessor bodies change, rather than every call site.

### Countdown sorting

Steps are sorted longest-first at startup with an insertion sort, so creators can list them in any order. `RunCountdown` then walks the gaps between consecutive steps and finally the gap down to zero, which means the number of `Sleep` calls scales with the number of steps rather than with wall-clock time.

---

## Usage Examples

### Example 1: Loot rain every ten minutes

```
Events:
  [0] Label: "Loot Rain"
      Settings: ScheduleMode Repeating, FirstEventDelay 300, RepeatInterval 600,
                EndMode FixedDuration, Duration 45
      CountdownSteps: [ SecondsBefore 60 ], [ SecondsBefore 10 ]
      StartedOutput -> item spawner devices
      EndedOutput   -> item spawner disable
```

No gather zone, so no tiers. The simplest useful configuration.

### Example 2: Double rewards for one hour, pulsing

```
      Settings: ScheduleMode Repeating, RepeatInterval 3600,
                EndMode FixedDuration, Duration 3600, PulseInterval 30
      PulseOutput -> your score multiplier or item grant
```

An event as long as its own interval, effectively always on, pulsing a reward twice a minute.

### Example 3: Community gathering with convergence tiers

```
      Settings: ScheduleMode Repeating, RepeatInterval 900, Duration 120,
                RequireMinimumAttendance 3
      GatherZone: the plaza volume
      AttendanceTiers:
        [0] Label "Crowd",  PlayersRequired 5,  ReachedOutput -> small reward
        [1] Label "Rally",  PlayersRequired 10, ReachedOutput -> big reward + VFX
      AgentJoinedEventOutput -> latecomer consolation
```

The prosocial configuration: the reward scales with how many strangers turned up together.

### Example 4: Creator-controlled boss spawn

```
      Settings: ScheduleMode TriggerOnly, EndMode UntilTriggered
      StartTrigger: a button or your own Verse device
      StopTrigger:  fired when the boss dies
```

The beacon handles the announcement, countdown and cleanup, and your logic decides when.

---

## Best Practices

### Performance Optimization
- One beacon per island is enough. Each event costs one scheduler coroutine, not one device
- Long `PulseInterval` values are cheap; very short ones fire a trigger on every beat for every event, so keep them above a second unless you mean it
- Attendance is recomputed only on zone entry and at event start, not on a timer

### Design Considerations
- Announce more than once. A single warning at 10 seconds is not enough time for a player across the map to reach a gather zone
- `RepeatInterval` is measured from the start of one countdown to the start of the next, so it is a true cycle length and not affected by `Duration`
- Give every event a distinct `Label`. It appears in announcements and in every debug line
- If you want players to be *moved* rather than *invited*, wire `StartedOutput` to a teleporter. The beacon deliberately never moves anyone

### Common Pitfalls
- **Attendance tiers with no gather zone.** They can never fire. The device logs a warning at startup
- **`UntilTriggered` with no `StopTrigger`.** The event never ends. Also logged at startup
- **A countdown longer than the interval containing it.** Clamped to zero and logged, but the schedule is not what you intended
- **Expecting tiers to deactivate.** They are milestones, not states. Use Device2's Team Buff Zone if you want buffs that come and go with the crowd
- **Announcements over 150 characters.** `hud_message_device.SetText` clamps them

---

## Debugging & Troubleshooting

### Enable Debug Logging

Set `Debug.EnableDebug` to true on the device. Lines are prefixed `[Hype Beacon - <source>]` where the source is `Init`, `Schedule`, `Countdown`, `Event` or `Attendance`.

```
[Hype Beacon - Init] Initialized 'Loot Rain' with 2 countdown step(s) and 0 tier(s)
[Hype Beacon - Countdown] countdown step at 60s
[Hype Beacon - Event] 'Loot Rain' started (run 1)
[Hype Beacon - Event] 'Loot Rain' ended after 45.000000s, peak attendance 0
```

Countdown seconds are rendered as whole numbers in both announcements and logs. Elapsed times in the end-of-event line are raw floats, since they are diagnostic rather than player facing.

### Common Issues

| Symptom | Likely cause |
|---|---|
| Nothing ever happens | `ScheduleMode` is `TriggerOnly` with no `StartTrigger` assigned, or an `InitTrigger` is set and never fired |
| Event ends immediately | `Duration` is at or near zero with `EndMode FixedDuration` |
| Event never ends | `EndMode` is `UntilTriggered` with no `StopTrigger`. Check the startup warning |
| Announcements do not appear | No HUD message device on either `AnnounceHUD` or `GlobalAnnounceHUD` |
| Tiers never fire | No `GatherZone`, or `RequireMinimumAttendance` is above the player count |
| Second event never runs | `AllowOverlapping` is off and the first event is still running. Check the skip line in the log |
| Countdown fires late | Expected. The countdown is inside the interval, not added to it |

---

## Integration with Other UEFNiVERSE Devices

### Pro Social Feed (Device4)

Hype Beacon has **no compile-time dependency** on Device4, so either works without the other. To put events into the feed, add a `feed_event_wire` on the Pro Social Feed for each Hype Beacon output you care about:

| Feed wire `SourceTrigger` | Suggested `Message` | `ShowPlayerName` |
|---|---|---|
| Event `StartedOutput` | `"Loot Rain has begun!"` | off |
| Countdown step `CountdownOutput` | `"Loot Rain starts in 60 seconds!"` | off |
| Tier `ReachedOutput` | `"joined the rally!"` | on |
| Event `EndedOutput` | `"Loot Rain is over."` | off |

Wire messages are fixed text, so one wire per countdown step gives each its own line. For fully dynamic feed text, a Verse device holding both can call `PostEntry` directly.

### Team Buff Zone (Device2)

Wire a Hype Beacon `StartedOutput` into a buff zone's `InitTrigger`, or point both at the same volume so an event window is also a buff window. Hype Beacon handles when, Team Buff Zone handles what the crowd gets while it lasts.

### Shared Progress Tracker (Device1)

Wire `PulseOutput` or a tier's `ReachedOutput` into a tracker milestone so island-wide events feed a shared goal.

### Custom Devices

```
# Any Verse device holding a reference can drive the beacon
Beacon.StartEvent(0)
if (Beacon.IsEventRunning(0)?):
    Count := Beacon.GetAttendance(0)
```

---

## Technical Reference

### Key Methods

| Method | Returns | Description |
|---|---|---|
| `StartEvent(Index : int)` | `void` | Starts the event now, skipping the countdown |
| `StopEvent(Index : int)` | `void` | Ends a running event early. No effect if it is not running |
| `IsEventRunning(Index : int)` | `logic` | Whether that event is currently running |
| `AnyEventRunning()` | `logic` | Whether any event on this beacon is running |
| `GetAttendance(Index : int)` | `int` | Players currently in that event's gather zone |
| `GetPeakAttendance(Index : int)` | `int` | Highest concurrent attendance during the current or last run |
| `GetRunCount(Index : int)` | `int` | How many times that event has run this session |

### Internal State

```
# hype_beacon
var Runners : []hype_event_runner    # one per configured event, built at Initialize

# hype_event_runner
var SortedSteps    : []hype_countdown_step   # countdown, longest first
var IsRunning      : logic                   # event currently active
var StartedAt      : float                   # GetSimulationElapsedTime at start
var PeakAttendance : int                     # reset each run
var RunCount       : int                     # accumulates for the session
var AgentsInZone   : []agent                 # behind accessors only
var TiersFired     : [int]logic              # behind accessors only, reset each run
StopSignal         : event()                 # ends the event race
```

### Performance Characteristics

- One coroutine per event with a schedule, plus one race per running event
- Zone events are subscription driven, so attendance costs nothing while idle
- Tier evaluation is linear in the number of tiers, and only runs on zone entry or event start
- Countdown sorting is an insertion sort over a handful of entries, once, at startup

---

## Version History

| Version | Change |
|---|---|
| v2.2.0 | Initial release |

---

## Support

**Part of UEFNiVERSE** - Professional Verse devices for UEFN creators
**Developer:** PineFruit | **Organization:** Chartis / UEFNiVERSE

**Resources:**
- [Main Repository](https://github.com/UEFNiVERSE/Free-Verse) - Full device collection
- Source: `Device5/hype_beacon.verse`
- Dependencies: `Core/base_device.verse`, `Core/base_group_device.verse`, `utility.verse`
- Inline code documentation for detailed implementation

**Contact:**
- Discord: https://discord.gg/UEFNiVERSE
- Epic: PineFruitDev
- Twitter: @PineFruitDev

**Contributions:** See main repository for contribution guidelines

---

**License:** [Apache 2.0](https://choosealicense.com/licenses/apache-2.0/) with [Commons Clause](https://commonsclause.com/)
**Powered by:** [Project Moonlight](https://www.projectmoonlight.org/)
