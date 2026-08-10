#██╗   ██╗███████╗███████╗███╗   ██╗██╗██╗   ██╗███████╗██████╗ ███████╗███████╗
#██║   ██║██╔════╝██╔════╝████╗  ██║██║██║   ██║██╔════╝██╔══██╗██╔════╝██╔════╝
#██║   ██║█████╗  █████╗  ██╔██╗ ██║██║██║   ██║█████╗  ██████╔╝███████╗█████╗
#██║   ██║██╔══╝  ██╔══╝  ██║╚██╗██║██║╚██╗ ██╔╝██╔══╝  ██╔══██╗╚════██║██╔══╝
#╚██████╔╝███████╗██║     ██║ ╚████║██║ ╚████╔╝ ███████╗██║  ██║███████║███████╗
# ╚═════╝ ╚══════╝╚═╝     ╚═╝  ╚═══╝╚═╝  ╚═══╝  ╚══════╝╚═╝  ╚═╝╚══════╝╚══════╝

# ======================================================
# FILE: hype_beacon.verse
# ------------------------------------------------------
# Scheduled island-wide hype events: loot rain, mystery
# drops, double reward hours, dance-offs. The device owns
# the timing, the countdown, the announcement and the
# attendance tiers. It owns none of the reward: every
# moment that matters fires a trigger the creator wires
# to whatever they already built.
#
# Configuration and runtime state are deliberately split.
# `hype_event` is pure editable configuration. Each one
# gets a `hype_event_runner` created at startup that holds
# the mutable state and the coroutines, the same way
# Device4 pairs `pro_social_feed` with `social_feed_widget`.
# ======================================================

# ======================================================
# IMPORTS
# ======================================================

using { /Fortnite.com/Devices }
using { /UnrealEngine.com/Temporary/Diagnostics }
using { /Verse.org/Simulation }

using { Core }

# ======================================================
# TOOLTIPS
# ======================================================

EventsTip <public><localizes> :message = "The hype events this beacon runs. Each one keeps its own schedule, countdown and outputs."
EventSettingsTip <public><localizes> :message = "Timing and mode for this event."
ScheduleModeTip <public><localizes> :message = "AtIslandStart = runs once, FirstEventDelay after the island starts.\nRepeating = runs on a loop every RepeatInterval.\nTriggerOnly = never runs on its own, only when StartTrigger fires."
FirstEventDelayTip <public><localizes> :message = "Seconds before the first run. Countdown announcements happen inside this window, not on top of it."
RepeatIntervalTip <public><localizes> :message = "Seconds between runs when ScheduleMode is Repeating. Measured from the end of one run to the start of the next countdown."
EndModeTip <public><localizes> :message = "FixedDuration = the event ends by itself after Duration.\nUntilTriggered = the event runs until StopTrigger fires."
DurationTip <public><localizes> :message = "How long the event lasts, in seconds. FixedDuration only."
PulseIntervalTip <public><localizes> :message = "If above zero, PulseOutput fires on this interval for the whole event. Use it for repeating rewards like a double reward hour. Set to 0 to disable."
RequireMinimumAttendanceTip <public><localizes> :message = "Players who must be in the gather zone before attendance tiers can fire. The event still starts and still announces. Set to 0 to disable."
CountdownStepsTip <public><localizes> :message = "Announcements before the event starts. List as many as you like, in any order, they are sorted automatically."
SecondsBeforeTip <public><localizes> :message = "How many seconds before the start this announcement fires."
CountdownMessageTip <public><localizes> :message = "Text for this announcement. Leave empty for the standard wording.\nFormat: \"\{LABEL\} starts in \{SECONDS\} seconds!\""
CountdownOutputTip <public><localizes> :message = "Triggered when this countdown step fires. No agent is passed, the countdown is island-wide."
GatherZoneTip <public><localizes> :message = "Optional volume that defines where players gather. Attendance tiers need it. Without one the event still runs, it just cannot measure who turned up."
AttendanceTiersTip <public><localizes> :message = "Rewards for how many players converge on the gather zone. Each tier fires once per run."
PlayersRequiredTip <public><localizes> :message = "Players who must be in the gather zone at the same time to reach this tier."
TierReachedOutputTip <public><localizes> :message = "Triggered once when this tier is reached, one fire per agent present. Passes each agent."
TierVisualsTip <public><localizes> :message = "Visual effect powerup devices picked up by everyone present when this tier is reached."
StartTriggerTip <public><localizes> :message = "Starts this event immediately, skipping the countdown. Works in every schedule mode."
StopTriggerTip <public><localizes> :message = "Ends this event early. Required if EndMode is UntilTriggered."
AnnounceHUDTip <public><localizes> :message = "HUD message device this event announces through. Falls back to the beacon's shared device when empty."
StartedOutputTip <public><localizes> :message = "Triggered when this event starts."
EndedOutputTip <public><localizes> :message = "Triggered when this event ends, whether it timed out or was stopped."
PulseOutputTip <public><localizes> :message = "Triggered repeatedly while the event runs, on PulseInterval."
AgentJoinedEventOutputTip <public><localizes> :message = "Triggered when a player enters the gather zone during a running event. Passes the arriving agent, so latecomers can still be rewarded."
ClearVisualsDeviceTip <public><localizes> :message = "Visual effect powerup device picked up to clear tier VFX when an event ends (use an empty powerup). Shared across every event on this beacon."
GlobalAnnounceHUDTip <public><localizes> :message = "HUD message device used by any event that does not name its own."
AllowOverlappingTip <public><localizes> :message = "If enabled, several events can run at once. If disabled, an event that comes due while another is running is skipped and logged."
AnyEventStartedOutputTip <public><localizes> :message = "Triggered when any event on this beacon starts."
AnyEventEndedOutputTip <public><localizes> :message = "Triggered when any event on this beacon ends."

# ======================================================
# LOCALIZED ANNOUNCEMENT TEXT
# ======================================================

LocCountdown <localizes> (Label : string, Seconds : string):message = "{Label} starts in {Seconds} seconds!"
LocEventStarted <localizes> (Label : string):message = "{Label} has begun!"
LocEventEnded <localizes> (Label : string):message = "{Label} has ended."

# ======================================================
# CONSTANTS
# ======================================================

# Idle heartbeat for a race branch that must stay alive without doing
# anything. Long enough to cost nothing, short enough to stay readable.
IDLE_TICK <public>: float = 60.0

# ======================================================
# ENUMS
# ======================================================

hype_schedule_mode := enum:
    AtIslandStart
    Repeating
    TriggerOnly

hype_end_mode := enum:
    FixedDuration
    UntilTriggered

# ======================================================
# COUNTDOWN STEP
# ======================================================

hype_countdown_step := class<concrete><unique>:

    # === EDITABLE PROPERTIES ===
    @editable { ToolTip := LabelTip } Label <public>: string = ""
    @editable { ToolTip := SecondsBeforeTip } SecondsBefore <public>: float = 30.0
    @editable { ToolTip := CountdownMessageTip } Message <public>: string = ""
    @editable { ToolTip := CountdownOutputTip } CountdownOutput <public>: trigger_device = trigger_device{}

# ======================================================
# ATTENDANCE TIER
# ======================================================
# Deliberately simpler than Device2's buff_tier. A tier fires once per run
# and is reset when the next run starts, so there is no per-agent activation
# map and no deactivation bookkeeping to leak.

hype_attendance_tier := class<concrete><unique>:

    # === EDITABLE PROPERTIES ===
    @editable { ToolTip := LabelTip } Label <public>: string = ""
    @editable { ToolTip := PlayersRequiredTip } PlayersRequired <public>: int = 2
    @editable { ToolTip := TierReachedOutputTip } ReachedOutput <public>: trigger_device = trigger_device{}
    @editable { ToolTip := TierVisualsTip } VisualsDevices <public>: []visual_effect_powerup_device = array{}

# ======================================================
# EVENT SETTINGS
# ======================================================

hype_event_settings := class<concrete>:

    # === EDITABLE PROPERTIES ===
    @editable { ToolTip := ScheduleModeTip } ScheduleMode <public>: hype_schedule_mode = hype_schedule_mode.Repeating
    @editable { ToolTip := FirstEventDelayTip } FirstEventDelay <public>: float = 120.0
    @editable { ToolTip := RepeatIntervalTip } RepeatInterval <public>: float = 600.0
    @editable { ToolTip := EndModeTip } EndMode <public>: hype_end_mode = hype_end_mode.FixedDuration
    @editable { ToolTip := DurationTip } Duration <public>: float = 60.0
    @editable { ToolTip := PulseIntervalTip } PulseInterval <public>: float = 0.0
    @editable { ToolTip := RequireMinimumAttendanceTip } RequireMinimumAttendance <public>: int = 0

# ======================================================
# EVENT CONFIGURATION
# ======================================================
# Pure configuration. No mutable state and no events live here, so nothing
# in this class depends on what the editor is willing to serialize.

hype_event := class<concrete><unique>:

    # === EDITABLE PROPERTIES ===
    @editable { ToolTip := LabelTip } Label <public>: string = "Hype Event"
    @editable { ToolTip := EventSettingsTip } Settings <public>: hype_event_settings = hype_event_settings{}
    @editable { ToolTip := CountdownStepsTip } CountdownSteps <public>: []hype_countdown_step = array{}
    @editable { ToolTip := GatherZoneTip } GatherZone <public>: ?volume_device = false
    @editable { ToolTip := AttendanceTiersTip } AttendanceTiers <public>: []hype_attendance_tier = array{}
    @editable { ToolTip := StartTriggerTip } StartTrigger <public>: ?trigger_device = false
    @editable { ToolTip := StopTriggerTip } StopTrigger <public>: ?trigger_device = false
    @editable { ToolTip := AnnounceHUDTip } AnnounceHUD <public>: ?hud_message_device = false
    @editable { ToolTip := StartedOutputTip } StartedOutput <public>: trigger_device = trigger_device{}
    @editable { ToolTip := EndedOutputTip } EndedOutput <public>: trigger_device = trigger_device{}
    @editable { ToolTip := PulseOutputTip } PulseOutput <public>: trigger_device = trigger_device{}
    @editable { ToolTip := AgentJoinedEventOutputTip } AgentJoinedEventOutput <public>: trigger_device = trigger_device{}

# ======================================================
# EVENT RUNNER
# ======================================================
# One per configured event, created at startup. Holds every piece of mutable
# state and every coroutine. Never exposed to the editor.

hype_event_runner := class:

    # === CONSTRUCTION ===
    Config <public>: hype_event
    Manager <public>: hype_beacon
    Index <public>: int
    ClearDevice <public>: ?visual_effect_powerup_device

    # === INTERNAL STATE ===
    var SortedSteps : []hype_countdown_step = array{}
    var IsRunning <public>: logic = false
    var StartedAt : float = 0.0
    var AgentsInZone <public>: []agent = array{}
    var PeakAttendance <public>: int = 0
    var RunCount <public>: int = 0
    var TiersFired : [int]logic = map{}
    StopSignal : event() = event(){}

    # === INITIALIZATION ===

    Init<public>():void=
        set SortedSteps = SortStepsDescending(Config.CountdownSteps)

        if (Zone := Config.GatherZone?):
            Zone.AgentEntersEvent.Subscribe(OnAgentEntered)
            Zone.AgentExitsEvent.Subscribe(OnAgentExited)
        else if (Config.AttendanceTiers.Length > 0):
            Log("has attendance tiers but no gather zone, tiers can never fire", ?Name := "Init")

        if (Trigger := Config.StartTrigger?):
            Trigger.TriggeredEvent.Subscribe(OnStartTriggered)

        if (Trigger := Config.StopTrigger?):
            Trigger.TriggeredEvent.Subscribe(OnStopTriggered)
        else if (Config.Settings.EndMode = hype_end_mode.UntilTriggered):
            Log("EndMode is UntilTriggered but no StopTrigger is assigned, this event will never end", ?Name := "Init")

        Log("Initialized '{Config.Label}' with {SortedSteps.Length} countdown step(s) and {Config.AttendanceTiers.Length} tier(s)", ?Name := "Init")

    # Countdown steps are sorted longest-first so the creator can list them in
    # any order. There is nothing to lean on for this, hence the hand-rolled
    # insertion sort. The lists are a handful of entries, so this is free.
    SortStepsDescending<private>(Steps : []hype_countdown_step)<transacts>:[]hype_countdown_step=
        var Sorted : []hype_countdown_step = array{}
        for (Step : Steps):
            var Inserted : logic = false
            var Rebuilt : []hype_countdown_step = array{}
            for (Existing : Sorted):
                if (Inserted = false, Step.SecondsBefore > Existing.SecondsBefore):
                    set Rebuilt += array{Step}
                    set Inserted = true
                set Rebuilt += array{Existing}
            if (Inserted = false):
                set Rebuilt += array{Step}
            set Sorted = Rebuilt
        Sorted

    LongestCountdown<private>()<transacts>:float=
        var Longest : float = 0.0
        for (Step : SortedSteps, Step.SecondsBefore > Longest):
            set Longest = Step.SecondsBefore
        Longest

    # Sleep durations are clamped so a countdown longer than the interval that
    # contains it cannot produce a negative wait.
    ClampLow<private>(Value : float, Floor : float)<transacts>:float=
        if (Value < Floor). Floor else. Value

    # === SCHEDULING ===

    RunSchedule<public>()<suspends>:void=
        Lead := LongestCountdown()

        if (Config.Settings.FirstEventDelay < Lead):
            Log("countdown is longer than FirstEventDelay, the first run announces immediately", ?Name := "Schedule")

        Sleep(ClampLow(Config.Settings.FirstEventDelay - Lead, 0.0))

        loop:
            RunCountdown()
            RunEvent()

            if (Config.Settings.ScheduleMode <> hype_schedule_mode.Repeating):
                break

            if (Config.Settings.RepeatInterval < Lead):
                Log("countdown is longer than RepeatInterval, runs will announce back to back", ?Name := "Schedule")

            Sleep(ClampLow(Config.Settings.RepeatInterval - Lead, 0.0))

    # Steps are already sorted longest-first, so this walks the gaps between
    # them and then the final gap down to zero.
    RunCountdown<private>()<suspends>:void=
        var PrevSeconds : float = LongestCountdown()
        for (Step : SortedSteps):
            Wait := PrevSeconds - Step.SecondsBefore
            if (Wait > 0.0):
                Sleep(Wait)
            FireCountdownStep(Step)
            set PrevSeconds = Step.SecondsBefore

        if (PrevSeconds > 0.0):
            Sleep(PrevSeconds)

    FireCountdownStep<private>(Step : hype_countdown_step):void=
        Step.CountdownOutput.Trigger()
        if (Step.Message <> ""):
            Announce(Step.Message)
        else:
            AnnounceMessage(LocCountdown(Config.Label, "{Step.SecondsBefore}"))
        Log("countdown step at {Step.SecondsBefore}s", ?Name := "Countdown")

    # === RUNNING AN EVENT ===

    RunEvent<private>()<suspends>:void=
        if (IsRunning?):
            Log("'{Config.Label}' is already running, skipping this run", ?Name := "Schedule")
            return

        if (Manager.AllowOverlapping = false, Manager.AnyEventRunning()?):
            Log("another event is already running and overlapping is disabled, skipping '{Config.Label}'", ?Name := "Schedule")
            return

        set IsRunning = true
        set StartedAt = GetSimulationElapsedTime()
        set RunCount += 1
        set TiersFired = map{}
        set PeakAttendance = AgentsInZone.Length

        AnnounceMessage(LocEventStarted(Config.Label))
        Config.StartedOutput.Trigger()
        Manager.AnyEventStartedOutput.Trigger()
        Log("'{Config.Label}' started (run {RunCount})", ?Name := "Event")

        EvaluateTiers()

        # The pulse loop is a racer rather than a spawned coroutine, so it dies
        # with the race and there is no "is the loop still alive" flag to leak.
        #
        # The timer branch must never fall through. A race ends as soon as any
        # branch completes, so an `if` with no else would finish instantly in
        # UntilTriggered mode and end the event the moment it began. In that
        # mode the branch waits on the stop signal instead, which is exactly
        # what the mode means.
        race:
            block:
                if (Config.Settings.EndMode = hype_end_mode.FixedDuration):
                    Sleep(Config.Settings.Duration)
                else:
                    StopSignal.Await()
            StopSignal.Await()
            RunPulseLoop()

        set IsRunning = false
        ClearTierVisuals()
        AnnounceMessage(LocEventEnded(Config.Label))
        Config.EndedOutput.Trigger()
        Manager.AnyEventEndedOutput.Trigger()
        Log("'{Config.Label}' ended after {GetSimulationElapsedTime() - StartedAt}s, peak attendance {PeakAttendance}", ?Name := "Event")

    RunPulseLoop<private>()<suspends>:void=
        if (Config.Settings.PulseInterval > 0.0):
            loop:
                Sleep(Config.Settings.PulseInterval)
                Config.PulseOutput.Trigger()
        else:
            # No pulse configured, but this branch still must never complete or
            # it would end the race and with it the event. It idles rather than
            # awaiting StopSignal, because that signal is already awaited by a
            # sibling branch and two subscriptions to one event inside a single
            # race is an assumption not worth making. The stop path is unaffected.
            loop:
                Sleep(IDLE_TICK)

    # === ATTENDANCE ===
    # The zone is tracked whether or not an event is running, so a creator can
    # watch it fill during the countdown. Tiers are only evaluated mid-event.

    # Attendance bookkeeping happens on arrival, before any output fires, so a
    # creator reading GetPeakAttendance from inside an AgentJoinedEventOutput
    # handler sees the arrival that caused it rather than the previous peak.
    OnAgentEntered<private>(Agent : agent):void=
        if (not AgentsInZone.Find[Agent]):
            set AgentsInZone += array{Agent}
            if (AgentsInZone.Length > PeakAttendance):
                set PeakAttendance = AgentsInZone.Length
            if (IsRunning?):
                Config.AgentJoinedEventOutput.Trigger(Agent)
                EvaluateTiers()

    OnAgentExited<private>(Agent : agent):void=
        if (AgentsInZone.Find[Agent]):
            set AgentsInZone = for (Present : AgentsInZone, Present <> Agent). Present

    # Called by the device when a player disconnects, so a stale agent cannot
    # sit in the list inflating attendance forever.
    OnAgentLeftIsland<public>(Agent : agent):void=
        OnAgentExited(Agent)

    EvaluateTiers<private>():void=
        if (AgentsInZone.Length < Config.Settings.RequireMinimumAttendance):
            return

        for (Idx -> Tier : Config.AttendanceTiers, AgentsInZone.Length >= Tier.PlayersRequired):
            var AlreadyFired : logic = false
            if (Fired := TiersFired[Idx], Fired?):
                set AlreadyFired = true

            if (AlreadyFired = false):
                if (set TiersFired[Idx] = true){}
                for (Agent : AgentsInZone):
                    Tier.ReachedOutput.Trigger(Agent)
                    if (Player := player[Agent]):
                        for (VFX : Tier.VisualsDevices):
                            VFX.Pickup(Player)
                Log("tier '{Tier.Label}' reached with {AgentsInZone.Length} player(s)", ?Name := "Attendance")

    ClearTierVisuals<private>():void=
        if (Clear := ClearDevice?):
            for (Agent : AgentsInZone, Player := player[Agent]):
                Clear.Pickup(Player)

    # === TRIGGER HANDLERS ===

    OnStartTriggered<private>(MaybeAgent : ?agent):void=
        spawn{StartNow()}

    OnStopTriggered<private>(MaybeAgent : ?agent):void=
        Stop()

    # A manual start skips the countdown entirely. That is the point of a
    # start trigger: the creator wants it now.
    StartNow<public>()<suspends>:void=
        RunEvent()

    Stop<public>():void=
        if (IsRunning?):
            StopSignal.Signal()

    # === ANNOUNCEMENTS ===

    Announce<private>(Text : string):void=
        AnnounceMessage(MakeMessage(Text))

    AnnounceMessage<private>(Msg : message):void=
        if (HUD := Config.AnnounceHUD?):
            HUD.SetText(Msg)
            HUD.Show()
        else if (HUD := Manager.GlobalAnnounceHUD?):
            HUD.SetText(Msg)
            HUD.Show()

    Log<private>(Message : string, ?Name : string = ""):void=
        Manager.Logger(Message, ?Name := Name)

# ======================================================
# HYPE BEACON DEVICE
# ======================================================

hype_beacon := class(Core.base_device):

    # === EDITABLE PROPERTIES ===
    @editable { ToolTip := EventsTip } Events <public>: []hype_event = array{}
    @editable { ToolTip := ClearVisualsDeviceTip } ClearVisualsDevice <public>: ?visual_effect_powerup_device = false
    @editable { ToolTip := GlobalAnnounceHUDTip } GlobalAnnounceHUD <public>: ?hud_message_device = false
    @editable { ToolTip := AllowOverlappingTip } AllowOverlapping <public>: logic = false
    @editable { ToolTip := AnyEventStartedOutputTip } AnyEventStartedOutput <public>: trigger_device = trigger_device{}
    @editable { ToolTip := AnyEventEndedOutputTip } AnyEventEndedOutput <public>: trigger_device = trigger_device{}

    # === CONFIGURATION ===
    LOGGER_NAME <override>: string = "Hype Beacon"

    # === INTERNAL STATE ===
    var Runners <public>: []hype_event_runner = array{}

    # === INITIALIZATION ===

    Initialize<override>()<suspends>:void=
        var Built : []hype_event_runner = array{}
        for (Idx -> Event : Events):
            Runner := hype_event_runner:
                Config := Event
                Manager := Self
                Index := Idx
                ClearDevice := ClearVisualsDevice
            Runner.Init()
            set Built += array{Runner}
        set Runners = Built

        for (Runner : Runners, Runner.Config.Settings.ScheduleMode <> hype_schedule_mode.TriggerOnly):
            spawn{Runner.RunSchedule()}

        Logger("Initialized with {Runners.Length} event(s)")

    # === LIFECYCLE EVENTS ===

    OnAgentLeft<override>(Agent : agent):void=
        for (Runner : Runners):
            Runner.OnAgentLeftIsland(Agent)

    # === PUBLIC API FOR OTHER VERSE DEVICES ===

    AnyEventRunning <public>()<transacts>:logic=
        for (Runner : Runners, Runner.IsRunning?):
            return true
        false

    StartEvent <public>(Index : int):void=
        if (Runner := Runners[Index]):
            spawn{Runner.StartNow()}

    StopEvent <public>(Index : int):void=
        if (Runner := Runners[Index]):
            Runner.Stop()

    IsEventRunning <public>(Index : int)<transacts>:logic=
        if (Runner := Runners[Index]):
            Runner.IsRunning
        else:
            false

    GetAttendance <public>(Index : int)<transacts>:int=
        if (Runner := Runners[Index]):
            Runner.AgentsInZone.Length
        else:
            0

    GetPeakAttendance <public>(Index : int)<transacts>:int=
        if (Runner := Runners[Index]):
            Runner.PeakAttendance
        else:
            0

    GetRunCount <public>(Index : int)<transacts>:int=
        if (Runner := Runners[Index]):
            Runner.RunCount
        else:
            0
