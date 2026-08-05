# Device4: Pro Social Feed

**Part of:** [UEFNiVERSE Free-Verse Device Collection](https://github.com/UEFNiVERSE/Free-Verse)
**Extends:** `base_device` (Core architecture, groupless base)
**Dependencies:** `Core/base_device.verse`, `Core/base_group_device.verse`, `utility.verse`, plus the `WBP_SocialFeed` UMG widget (included in this repo under `UMG/Device4_SocialFeed/`)

---

## What It Does
Island-wide social feed on every player's screen, rendered through a custom UMG interface. Players watch island activity roll by in real time, request help from the whole island, and publicly thank each other. Fully modular, so any device can post to it.

---

## Overview

The **Pro Social Feed** puts a rolling text feed on each player's HUD. New entries appear at the top and push older ones down: joins, help requests, thanks, and anything you wire into it. Players press a configurable input to open the full feed, where two built-in social actions live: **Get Help** and **Give Thanks**.

The feed is island-wide. One device serves the whole island, and every player sees the same feed.

**Primary Use Case:** Social visibility. Make helping and thanking each other a visible, celebrated part of your island
**Architecture Pattern:** Central feed device driving a per-player UMG widget, with modular event intake and output triggers

---

## Quick Start

1. Copy the repo's `UMG/Device4_SocialFeed` folder into your project's Content drawer at `UMG/Device4_SocialFeed` (the path must match so the Verse import path `UMG.Device4_SocialFeed` resolves)
2. Copy `VerseCode/Device4/`, the `Core` folder, and `utility.verse` into your project, and make sure `module_access.verse` declares both the `VerseCode` modules and the `UMG` block (see this repo's `module_access.verse`)
3. Place one Pro Social Feed device on your island
4. Assign an Input Trigger device to `OpenFeedInput` so players can open the feed
5. Optionally add Help Options and Event Wires
6. Launch a session. The feed appears on each player's HUD and announces joins by default

---

## Core Features

### 1. **Rolling HUD Feed**
- Up to 25 entries visible, newest first
- New entries push older entries down; the oldest falls off the end
- Entries never expire on a timer, they only leave by rolling off
- The closed feed sits on screen without consuming any player input

### 2. **Openable Feed**
- Players press the configured input to open and close the feed
- While open, the feed captures input so its buttons are clickable
- The open view shows the scrollable feed plus the two social action buttons

### 3. **Help Requests**
- Players press **Get Help**
- With Help Options configured (up to 5), players pick what they need help with: the feed shows "[HELP] PlayerName needs help with Label"
- With none configured, a standard request posts instantly: "[HELP] PlayerName is requesting help!"
- Fires a global output trigger plus a per-option output trigger, both passing the requesting agent

### 4. **Thanks**
- Players press **Give Thanks** and pick from players currently on the island (up to 5 shown)
- Posts "[THANKS] PlayerA thanked PlayerB!" for the whole island
- Fires `ThanksGivenOutput` passing the thanked agent, so you can reward being helpful
- If no one else is on the island, an island-wide thank you posts instead

### 5. **Shared Action Cooldown**
- One per-player cooldown (default 30 seconds, editable) covers both help requests and thanks
- Using either button starts the cooldown for both
- Attempts during cooldown are ignored (visible in debug logs)

### 6. **Modular Event Intake**
- **Event Wires:** connect any trigger device to the feed with a custom message, no Verse required
- **Verse API:** other Verse devices call `PostEntry` and `PostPlayerEntry` directly
- This is how the rest of the UEFNiVERSE library pipes events into the feed

### 7. **Output Trigger System**
- **HelpRequestedOutput:** fires on any help request, passes the requesting agent
- **ThanksGivenOutput:** fires when thanks are given, passes the thanked agent
- **EntryPostedOutput:** fires on every feed entry, passes the related agent when there is one
- **Per Help Option outputs:** each help category has its own output trigger

---

## The Widget

The feed renders through a UMG Widget Blueprint named `WBP_SocialFeed`, driven by the `social_feed_widget` Verse wrapper. The widget and its textures ship in this repo under `UMG/Device4_SocialFeed/`, so most creators just copy the folder in and go. If you want to restyle it or build your own from scratch, the Verse expects these exposed members, with these exact names:

**Variables (set from Verse):**
- `Text_1` through `Text_25` (message): the feed lines, newest in `Text_1`
- `Visiblity_1` through `Visiblity_25` (logic): feed line visibility, default false in the widget
- `RequestText_1` through `RequestText_5` (message) and `RequestVisibility_1` through `RequestVisibility_5` (logic): the help option rows
- `UserText_1` through `UserText_5` (message) and `UserVisibility_1` through `UserVisibility_5` (logic): the thank list rows
- `StateIndex` (int): 0 feed, 1 help list, 2 thank list, driven through a Widget Switcher
- `Open` (logic): whether the feed is in its open state

**Events (fired to Verse):**
- `HelpClicked`, `ThanksClicked`: the two action buttons
- `RequestClicked_1` through `RequestClicked_5`: help row selection
- `UserClicked_1` through `UserClicked_5`: thank row selection

All visibilities should default to false inside the widget; the Verse only writes them to true when a line gains content. There is no back button: every action closes the feed. Selecting a help option or a player to thank posts and closes, and pressing Get Help or Give Thanks with nothing to pick from posts the generic version and closes. Views with nothing to show are never entered.

---

## Settings & Configuration

### Feed Settings

```verse
feed_settings := class<concrete>:
    ActionCooldown: float = 30.0       # Shared cooldown for help and thanks, per player
    ShowJoinMessages: logic = true     # Announce joins
    ShowLeaveMessages: logic = false   # Announce leaves
```

**ActionCooldown** (30.0 seconds)
- A player who requests help or gives thanks must wait this long before either action again
- Recommended: 20-60 seconds depending on how busy your island gets

### Help Options

```verse
help_option := class<concrete><unique>:
    Label: string = ""                    # Category shown to the requesting player
    CustomMessage: string = ""            # Optional custom feed text
    HelpRequestedOutput: trigger_device   # Fires when this category is requested
```

Leave `HelpOptions` empty for the single generic request flow. Add up to 5 options like "a revive", "materials", or "boss fight backup" so requests read naturally: "PlayerName needs help with a revive". If `CustomMessage` is set, the feed shows "[HELP] PlayerName: CustomMessage" instead. Every editable's tooltip shows its exact output format.

### Event Wires

```verse
feed_event_wire := class<concrete>:
    Label: string = ""                  # Organizational label
    SourceTrigger: trigger_device       # Trigger to listen to
    Message: string = ""                # Feed text posted when it fires
    ShowPlayerName: logic = true        # Prefix with the triggering player's name
```

Wire any device's output through a trigger into the feed. Example: wire an elimination manager's output with the message "just cleared the arena!" and `ShowPlayerName` enabled.

### Inputs

- **OpenFeedInput** (`?input_trigger_device`): the button players press to open and close the feed
- **OpenFeedTrigger** (`?trigger_device`): optional alternative open path for button or zone based setups

---

## Architecture & Implementation

### Device and Wrapper

`pro_social_feed` extends `base_device`, the groupless Core base: it inherits the lifecycle hooks, spawner discovery, and debug logging without the player group layer. The device owns the feed model and all logic; presentation lives entirely in the widget.

Each player gets a `social_feed_widget` wrapper instance holding their WBP, their canvas mount, and their open state:

```verse
var Widgets : [agent]social_feed_widget = map{}
```

### Input Model

The widget mounts at `InputMode.None` so the closed feed never captures input. Opening removes and re-adds the same canvas at `InputMode.All` so button clicks register; closing reverses it. The wrapper runs one listener per open session, racing the widget's click events against a stop signal.

### Entry Model

Every feed item is a `feed_entry` holding its type (General, HelpRequest, Thanks), the related agents, and text. Display text is composed through localized message functions at render time, so player names resolve correctly for every viewer. The entry list is capped at 25; a new entry past the cap drops the oldest.

### Update Discipline

The device only touches widgets when something changes: a posted entry refreshes the feed lines, opening a view populates its rows. Feed lines only ever go from hidden to visible, so the Verse never writes false to a feed line. The thank list is the one dynamic surface: it is rebuilt per open, and if a listed player leaves the island, every open thank list showing them is refreshed, hiding their row and resetting its text.

---

## Usage Examples

### Example 1: Plain Social Feed

**Goal:** Ambient island feed with joins and thanks only

**Setup:**
1. Place the device, assign `OpenFeedInput`
2. Leave `HelpOptions` and `EventWires` empty
3. Keep `ShowJoinMessages` enabled

**Result:**
- Players see joins roll by, can open the feed, and can thank each other
- Get Help posts the standard generic request

### Example 2: Categorized Help Desk

**Goal:** Players broadcast what kind of help they need

**Setup:**
1. Add Help Options: "a revive", "materials", "backup"
2. Wire each option's `HelpRequestedOutput` to a different HUD or audio cue
3. Raise `ActionCooldown` to 45.0 for a calmer feed

**Result:**
- Requests read naturally in the feed and each category can drive its own signposting

### Example 3: Reward Helpfulness

**Goal:** Being thanked earns something

**Setup:**
1. Wire `ThanksGivenOutput` to an Item Granter or score device
2. The output passes the thanked player, not the thanker

**Result:**
- Every public thank you delivers a reward to the player who helped

### Example 4: Whole-Island Event Feed

**Goal:** The feed announces gameplay moments from other devices

**Setup:**
1. Add an Event Wire per moment: capture points, boss kills, round wins
2. Point each wire's `SourceTrigger` at the device output for that moment
3. Write short punchy messages and enable `ShowPlayerName` where an agent is passed

**Result:**
- One feed carries the whole island's story with zero extra Verse

---

## Best Practices

**Feed volume:**
- Aggressive event wiring works well: the rolling window keeps the feed fresh without cleanup logic
- Keep wire messages short so lines do not wrap awkwardly at your chosen widget size

**Help options:**
- Word labels to follow "needs help with", so "a revive" beats "Need a revive"
- Maximum 5 options are shown; extra configured options are ignored and logged

**Cooldown:**
- Do not set `ActionCooldown` too low. A spammed feed teaches players to ignore it
- The cooldown is shared: one thank you also delays that player's next help request

**Placement:**
- One Pro Social Feed per island. It is designed as a single island-wide feed
- Groups from the Core architecture have no effect on this device; the feed does not scope through player groups

---

## Debugging & Troubleshooting

### Enable Debug Logging

Enable debug mode in the device's Debug settings. Key log messages:
- `"Initialized with X help option(s) and Y event wire(s)"` - device started
- `"Agent joined, ticker mounted"` - per-player widget creation
- `"Help request posted"` / `"Thanks posted"` - action went through
- `"Help request blocked by cooldown"` / `"Thanks blocked by cooldown"` - player on cooldown

### Common Issues

**Issue: Feed not visible on screen**
- Check: Is exactly one Pro Social Feed device placed?
- Check: Is `WBP_SocialFeed` present in the project with the expected bindings?
- Check: Did the player join after the device initialized?

**Issue: Feed opens but buttons do nothing**
- Check: Are the widget's click events (`HelpClicked`, `ThanksClicked`, `RequestClicked_*`, `UserClicked_*`) wired to the buttons inside the WBP?
- Check: Did the feed actually open (input captured), or is it still in the passive closed state?

**Issue: Help or thanks seems to do nothing**
- Check: The player may be on the shared cooldown. Enable debug logging to confirm
- Check: Are you expecting a per-option output that is not wired?

**Issue: Event wire posts nothing**
- Check: Is the wire's `SourceTrigger` the same trigger the source device actually fires?
- Check: Is `Message` empty? An empty message with no player name posts a blank line

---

## Integration with Other UEFNiVERSE Devices

### Shared Progress Tracker
- Wire milestone outputs into an Event Wire so progress moments hit the feed

### Team Buff Zone
- Announce buff activations through an Event Wire

### Advanced Revive System
- Wire `PlayerRevivedOutput` into an Event Wire with a message like "is back on their feet!"
- Follow a revive with a thank you and both moments appear in the feed

### Custom Verse Devices
```verse
# From any Verse device holding an @editable reference to the feed:
MyFeed.PostEntry("The storm is closing in!")
MyFeed.PostPlayerEntry(Agent, "found a legendary chest!")
MyFeed.RequestHelp(Agent)
MyFeed.GiveThanks(FromAgent, ToAgent)
```

---

## Technical Reference

### Public API

```verse
PostEntry(Text: string): void
    - Posts a plain feed entry

PostPlayerEntry(Agent: agent, Text: string): void
    - Posts an entry prefixed with the player's name

RequestHelp(Agent: agent): void
    - Posts a generic help request for the agent, honoring the shared cooldown

GiveThanks(From: agent, To: agent): void
    - Posts a thanks entry and fires ThanksGivenOutput, honoring the shared cooldown

GetTotalHelpRequests(): int
GetTotalThanksGiven(): int
    - Round-scoped counters, reset when the session ends
```

### Internal State

```verse
var FeedEntries: []feed_entry = array{}
    # Rolling feed history, capped at 25 entries

var Widgets: [agent]social_feed_widget = map{}
    # Per-player widget wrappers and open state

var LastActionAt: [agent]float = map{}
    # Shared cooldown tracking per player
```

### Stats

`GetTotalHelpRequests()` and `GetTotalThanksGiven()` are in-memory, round-scoped counters. They reset when the session ends and are not persisted. Wire the output triggers into your own tracking if you need persistent stats.

### Performance Characteristics

**Memory:** O(25) feed entries plus O(P) widget state per player

**CPU:** Fully event-driven. Widgets update only when an entry posts, a view opens, or a player joins or leaves. No polling loops.

---

## Version History

**v1.0** - Initial Release (August 2026)
- Island-wide rolling feed through a custom UMG interface
- Help requests with configurable categories and natural wording
- Thanks flow with current-player list and island-wide fallback
- Shared per-player action cooldown
- Event Wires for no-code intake and a public Verse API
- Built on the groupless base_device Core architecture

---

## Support

**Part of UEFNiVERSE** - Professional Verse devices for UEFN creators
**Developer:** PineFruit | **Organization:** Chartis / UEFNiVERSE

**Resources:**
- [Main Repository](https://github.com/UEFNiVERSE/Free-Verse) - Full device collection
- Source: `Device4/pro_social_feed.verse`, `Device4/social_feed_widget.verse`
- Dependencies: `Core/base_device.verse`, `Core/base_group_device.verse`, `utility.verse`
- Inline code documentation for detailed implementation

**Contact:**
- Discord: PineFruit
- Epic: PineFruitDev
- Twitter: @PineFruitDev

**Contributions:** See main repository for contribution guidelines

---

*Last Updated: August 2026*
*Documentation Version: 1.0*
*Device Version: 1.0*

**License:** [Apache 2.0](https://choosealicense.com/licenses/apache-2.0/) with [Commons Clause](https://commonsclause.com/)
**Powered by:** [Project Moonlight](https://www.projectmoonlight.org/)
