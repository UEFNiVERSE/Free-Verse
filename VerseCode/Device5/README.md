# Device5: Hype Beacon

**Part of:** [UEFNiVERSE Free-Verse Device Collection](https://github.com/UEFNiVERSE/Free-Verse)
**Extends:** `base_device` (Core architecture, groupless base)
**Dependencies:** `Core/base_device.verse`, `Core/base_group_device.verse`, `utility.verse`

---

## What It Does
Runs island-wide hype events on a schedule: loot rain, mystery drops, double reward hours, dance-offs. The device owns the timing, the countdown, the announcement and the celebration. It owns none of the reward, so every moment that matters fires an output trigger you wire to whatever you already built.

---

## Overview

The **Hype Beacon** is a scheduler. You describe a set of events, each with its own schedule, countdown and outputs, and the beacon runs them. Nothing about it assumes a game loop or a round, so it works the same in a persistent tycoon, a hub, or a steal map.

An event can name a **gather zone**. When it does, the beacon tracks how many players converge on it and fires **attendance tiers** as thresholds are crossed. That is the part that turns a scheduled reward into a scheduled *moment*: everyone in one place at one time.

**Primary Use Case:** Retention and spectacle. Give an island a heartbeat that players learn to show up for
**Architecture Pattern:** Configuration and runtime state split, one runner coroutine per configured event

---

## Quick Start

1. Copy `VerseCode/Device5/`, the `Core` folder, and `utility.verse` into your project
2. Add `Device5 <public> := module:` to your `module_access.verse` under the `VerseCode` block
3. Place one Hype Beacon device on your island
4. Add an event to the `Events` array and give it a `Label`
5. Assign a HUD Message device to `GlobalAnnounceHUD` so announcements have somewhere to go
6. Wire `StartedOutput` to whatever the event should actually do
7. Launch a session. The event announces, runs, and ends on its own

---

## Core Features

### 1. **Three Schedule Modes**
- **AtIslandStart:** runs once, `FirstEventDelay` seconds in
- **Repeating:** runs on a loop every `RepeatInterval`
- **TriggerOnly:** never runs on its own, only when `StartTrigger` fires

### 2. **Countdowns That Do Not Lie**
- Add as many countdown steps as you like, in any order, they are sorted automatically
- Countdown time is subtracted from the interval, so a 30 second warning on a 600 second loop fires at 570, not at 600 with the event 30 seconds late
- Each step has its own output trigger and optional custom text

### 3. **Attendance Tiers**
- Name a gather zone and define thresholds by player count
- Each tier fires once per run, passing every agent present, plus optional VFX
- Latecomers fire `AgentJoinedEventOutput` so they can still be rewarded

### 4. **Pulse Output**
- Set `PulseInterval` above zero and `PulseOutput` fires on that beat for the whole event
- This is the "double reward hour" case: one event, a reward every N seconds

### 5. **Manual Override**
- `StartTrigger` starts an event now, skipping the countdown, in any schedule mode
- `StopTrigger` ends one early
- Both are also available to Verse via `StartEvent(Index)` and `StopEvent(Index)`

### 6. **Overlap Control**
- `AllowOverlapping` off (the default) means an event that comes due while another is running is skipped and logged, rather than announcing over the top of it

---

## Properties

_TODO: fill the full property tables once the design is signed off, matching the Device4 README layout._

---

## Wiring It Into the Pro Social Feed

Hype Beacon has no compile-time dependency on Device4, so you can use either without the other. To put events into the feed, add a `feed_event_wire` on the Pro Social Feed for each Hype Beacon output you care about, and set the wire's message.

_TODO: worked example._

---

## Notes and Limits

- Announcement text goes through a HUD Message device, and `SetText` clamps to 150 characters
- Attendance is per session. Nothing about hype events persists across sessions
- An event with attendance tiers but no gather zone logs a warning at startup, because its tiers can never fire
- Attendance is recorded before outputs fire, so reading `GetPeakAttendance` from inside an `AgentJoinedEventOutput` handler already includes the player who just arrived
- `PeakAttendance` resets at the start of each run, not across runs. `GetRunCount` is the one counter that accumulates for the whole session

---

## Dependencies

- `Core/base_device.verse` and `Core/base_group_device.verse`. The two classes reference each other across the same `Core` module, so always include both
- `utility.verse` for `debug_settings`, `MakeMessage`, `LabelTip` and `DebugTip`
