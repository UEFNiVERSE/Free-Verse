#██╗   ██╗███████╗███████╗███╗   ██╗██╗██╗   ██╗███████╗██████╗ ███████╗███████╗
#██║   ██║██╔════╝██╔════╝████╗  ██║██║██║   ██║██╔════╝██╔══██╗██╔════╝██╔════╝
#██║   ██║█████╗  █████╗  ██╔██╗ ██║██║██║   ██║█████╗  ██████╔╝███████╗█████╗
#██║   ██║██╔══╝  ██╔══╝  ██║╚██╗██║██║╚██╗ ██╔╝██╔══╝  ██╔══██╗╚════██║██╔══╝
#╚██████╔╝███████╗██║     ██║ ╚████║██║ ╚████╔╝ ███████╗██║  ██║███████║███████╗
# ╚═════╝ ╚══════╝╚═╝     ╚═╝  ╚═══╝╚═╝  ╚═══╝  ╚══════╝╚═╝  ╚═╝╚══════╝╚══════╝

# ======================================================
# FILE: pro_social_feed.verse
# ------------------------------------------------------
# Island-wide live text feed rendered through the
# WBP_SocialFeed UMG widget. Presentation lives in the
# widget (and social_feed_widget.verse); this device owns
# the feed model, help/thanks logic, event intake, and
# output triggers.
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

FeedSettingsTip <public><localizes> :message = "Configure feed behavior."
HelpOptionsTip <public><localizes> :message = "Help categories players can pick from when requesting help (up to 5 shown). Leave empty to use a single generic help request.\nGeneric format: \"[HELP] \{Agent\} is requesting help!\""
EventWiresTip <public><localizes> :message = "Wire any trigger into the feed. When the trigger fires, its message is posted to the feed."
OpenFeedInputTip <public><localizes> :message = "Input trigger that opens and closes the feed for the pressing player."
OpenFeedTriggerTip <public><localizes> :message = "Optional trigger device that opens the feed for the activating player. Useful for button or zone based setups."
HelpRequestedOutputTip <public><localizes> :message = "Triggered whenever any help request is posted. Passes the requesting agent."
ThanksGivenOutputTip <public><localizes> :message = "Triggered whenever thanks are given. Passes the thanked agent for custom reward logic."
EntryPostedOutputTip <public><localizes> :message = "Triggered whenever any entry is posted to the feed. Passes the related agent when there is one."
ActionCooldownTip <public><localizes> :message = "Seconds a player must wait between social actions. Shared by the help and thanks buttons."
ShowJoinMessagesTip <public><localizes> :message = "If enabled, the feed announces when a player joins the island.\nFormat: \"\{Agent\} joined the island!\""
ShowLeaveMessagesTip <public><localizes> :message = "If enabled, the feed announces when a player leaves the island.\nFormat: \"\{Agent\} left the island.\""
HelpOptionLabelTip <public><localizes> :message = "Category shown to the requesting player in the help list.\nFormat: \"[HELP] \{Agent\} needs help with \{LABEL_HERE\}\""
HelpOptionMessageTip <public><localizes> :message = "Optional custom feed text for this help category. Leave empty to use the standard help wording with the label.\nFormat: \"[HELP] \{Agent\}: \{CUSTOM_TEXT_HERE\}\""
HelpOptionOutputTip <public><localizes> :message = "Triggered when a player requests help with this category. Passes the requesting agent."
WireMessageTip <public><localizes> :message = "Feed text posted when the wired trigger fires.\nFormat: \"\{Agent\} \{MESSAGE_HERE\}\" when the player name is shown, otherwise \"\{MESSAGE_HERE\}\""
WireShowNameTip <public><localizes> :message = "If enabled and the trigger passes an agent, the player's name is shown in front of the message."

# ======================================================
# ENUMS
# ======================================================

feed_entry_type := enum:
    General
    HelpRequest
    Thanks

# ======================================================
# LOCALIZED FEED TEXT
# ======================================================

LocPlain <localizes> (Text : string):message = "{Text}"
LocPlayerText <localizes> (Agent : agent, Text : string):message = "{Agent} {Text}"
LocHelpDefault <localizes> (Agent : agent):message = "[HELP] {Agent} is requesting help!"
LocHelpLabel <localizes> (Agent : agent, Label : string):message = "[HELP] {Agent} needs help with {Label}"
LocHelpCustom <localizes> (Agent : agent, Text : string):message = "[HELP] {Agent}: {Text}"
LocThanks <localizes> (From : agent, To : agent):message = "[THANKS] {From} thanked {To}!"
LocThanksAll <localizes> (From : agent):message = "[THANKS] {From} sends thanks to everyone!"

# ======================================================
# CONSTANTS
# ======================================================

FEED_LINES <public>: int = 25
REQUEST_SLOTS <public>: int = 5
USER_SLOTS <public>: int = 5

# WBP StateIndex values
STATE_FEED <public>: int = 0
STATE_HELP <public>: int = 1
STATE_THANKS <public>: int = 2

# ======================================================
# FEED SETTINGS CLASS
# ======================================================

feed_settings := class<concrete>:

    # === EDITABLE PROPERTIES ===
    @editable { ToolTip := ActionCooldownTip } ActionCooldown <public>: float = 30.0
    @editable { ToolTip := ShowJoinMessagesTip } ShowJoinMessages <public>: logic = true
    @editable { ToolTip := ShowLeaveMessagesTip } ShowLeaveMessages <public>: logic = false

# ======================================================
# HELP OPTION CLASS
# ======================================================

help_option := class<concrete><unique>:

    # === EDITABLE PROPERTIES ===
    @editable { ToolTip := HelpOptionLabelTip } Label <public>: string = ""
    @editable { ToolTip := HelpOptionMessageTip } CustomMessage <public>: string = ""
    @editable { ToolTip := HelpOptionOutputTip } HelpRequestedOutput <public>: trigger_device = trigger_device{}

# ======================================================
# EVENT WIRE CLASS
# ======================================================

feed_event_wire := class<concrete>:

    # === EDITABLE PROPERTIES ===
    @editable { ToolTip := LabelTip } Label <public>: string = ""
    @editable { ToolTip := EventWiresTip } SourceTrigger <public>: trigger_device = trigger_device{}
    @editable { ToolTip := WireMessageTip } Message <public>: string = ""
    @editable { ToolTip := WireShowNameTip } ShowPlayerName <public>: logic = true

# ======================================================
# FEED ENTRY CLASS
# ======================================================

feed_entry := class:

    Kind <public>: feed_entry_type = feed_entry_type.General
    MaybeAgent <public>: ?agent = false
    MaybeTarget <public>: ?agent = false
    Text <public>: string = ""
    HelpLabel <public>: string = ""
    UseCustomHelpText <public>: logic = false
    PostedAt <public>: float = 0.0

    GetDisplayMessage <public>():message=
        if (From := MaybeAgent?, To := MaybeTarget?, Kind = feed_entry_type.Thanks):
            LocThanks(From, To)
        else if (From := MaybeAgent?, Kind = feed_entry_type.Thanks):
            LocThanksAll(From)
        else if (From := MaybeAgent?, Kind = feed_entry_type.HelpRequest):
            if (UseCustomHelpText?):
                LocHelpCustom(From, Text)
            else if (HelpLabel <> ""):
                LocHelpLabel(From, HelpLabel)
            else:
                LocHelpDefault(From)
        else if (From := MaybeAgent?):
            LocPlayerText(From, Text)
        else:
            LocPlain(Text)

# ======================================================
# WIRE LISTENER CLASS
# ======================================================

wire_listener := class:
    Feed : pro_social_feed
    Wire : feed_event_wire

    OnTriggered(MaybeAgent : ?agent):void=
        if (Agent := MaybeAgent?, Wire.ShowPlayerName?):
            Feed.PostPlayerEntry(Agent, Wire.Message)
        else:
            Feed.PostEntry(Wire.Message)

# ======================================================
# PRO SOCIAL FEED DEVICE
# ======================================================

pro_social_feed := class(Core.base_device):

    # === EDITABLE PROPERTIES ===
    @editable { ToolTip := FeedSettingsTip } Settings <public>: feed_settings = feed_settings{}
    @editable { ToolTip := HelpOptionsTip } HelpOptions <public>: []help_option = array{}
    @editable { ToolTip := EventWiresTip } EventWires <public>: []feed_event_wire = array{}
    @editable { ToolTip := OpenFeedInputTip } OpenFeedInput <public>: ?input_trigger_device = false
    @editable { ToolTip := OpenFeedTriggerTip } OpenFeedTrigger <public>: ?trigger_device = false
    @editable { ToolTip := HelpRequestedOutputTip } HelpRequestedOutput <public>: trigger_device = trigger_device{}
    @editable { ToolTip := ThanksGivenOutputTip } ThanksGivenOutput <public>: trigger_device = trigger_device{}
    @editable { ToolTip := EntryPostedOutputTip } EntryPostedOutput <public>: trigger_device = trigger_device{}

    # === CONFIGURATION ===
    LOGGER_NAME <override>: string = "Pro Social Feed"

    # === INTERNAL STATE ===
    var FeedEntries : []feed_entry = array{}
    var Widgets : [agent]social_feed_widget = map{}
    var TrackedPlayers : []agent = array{}
    var LastActionAt : [agent]float = map{}
    var TotalHelpRequests : int = 0
    var TotalThanksGiven : int = 0

    # === INITIALIZATION ===

    Initialize<override>()<suspends>:void=
        if (OpenInput := OpenFeedInput?):
            OpenInput.PressedEvent.Subscribe(OnOpenFeedPressed)

        if (OpenTrigger := OpenFeedTrigger?):
            OpenTrigger.TriggeredEvent.Subscribe(OnOpenFeedTriggered)

        for (Wire : EventWires):
            Listener := wire_listener{Feed := Self, Wire := Wire}
            Wire.SourceTrigger.TriggeredEvent.Subscribe(Listener.OnTriggered)

        if (HelpOptions.Length > REQUEST_SLOTS):
            Logger("More than {REQUEST_SLOTS} help options configured, only the first {REQUEST_SLOTS} are shown", ?Name := "Init")

        Logger("Initialized with {HelpOptions.Length} help option(s) and {EventWires.Length} event wire(s)")

    # === PUBLIC API FOR OTHER VERSE DEVICES ===

    PostEntry <public>(Text : string):void=
        AddEntry(feed_entry{Text := Text, PostedAt := GetSimulationElapsedTime()}, false)

    PostPlayerEntry <public>(Agent : agent, Text : string):void=
        AddEntry(feed_entry{MaybeAgent := option{Agent}, Text := Text, PostedAt := GetSimulationElapsedTime()}, false)

    RequestHelp <public>(Agent : agent):void=
        PostHelpRequest(Agent, -1)

    GiveThanks <public>(From : agent, To : agent):void=
        PostThanks(From, To)

    GetTotalHelpRequests <public>():int= TotalHelpRequests

    GetTotalThanksGiven <public>():int= TotalThanksGiven

    # === LIFECYCLE EVENTS ===

    OnAgentJoined<override>(Agent : agent):void=
        set TrackedPlayers += array{Agent}
        CreateWidgetFor(Agent)
        if (Settings.ShowJoinMessages?):
            AddJoinLeaveEntry(Agent, true)
        Logger("Agent joined, feed mounted ({TrackedPlayers.Length} tracked)")

    OnAgentRespawned<override>(Agent : agent):void=
        if (not Widgets[Agent]):
            CreateWidgetFor(Agent)

    OnAgentLeft<override>(Agent : agent):void=
        RemoveWidgetFor(Agent)
        set TrackedPlayers = for (Tracked : TrackedPlayers, Tracked <> Agent). Tracked
        if (Settings.ShowLeaveMessages?):
            AddJoinLeaveEntry(Agent, false)
        RefreshThanksListsAfterLeave(Agent)
        Logger("Agent left, feed removed ({TrackedPlayers.Length} tracked)")

    # When a player leaves, any thanks list that was showing them gets its
    # targets recomputed so their card is hidden and its text reset. A player
    # left staring at an emptied thanks view has the feed closed for them.
    RefreshThanksListsAfterLeave<private>(Departed : agent):void=
        for (Key -> Widget : Widgets):
            if (Widget.ThanksTargets.Find[Departed]):
                Targets := GetThanksTargets(Widget.OwnerAgent)
                PopulateUserList(Widget, Targets)
                if (Targets.Length = 0, Widget.IsOpen?):
                    Widget.CloseFeed()

    # === WIDGET MANAGEMENT ===

    CreateWidgetFor<private>(Agent : agent):void=
        if (Player := player[Agent]):
            Widget := social_feed_widget:
                OwnerAgent := Agent
                OwnerPlayer := Player
                Feed := Self
            if (set Widgets[Agent] = Widget){}
            Widget.ShowUI()
            RefreshFeedFor(Widget)

    RemoveWidgetFor<private>(Agent : agent):void=
        if (Widget := Widgets[Agent]):
            Widget.HideUI()
            var NewWidgets : [agent]social_feed_widget = map{}
            for (Key -> Value : Widgets, Key <> Agent):
                if (set NewWidgets[Key] = Value){}
            set Widgets = NewWidgets

    # === INPUT HANDLERS ===

    OnOpenFeedPressed(Agent : agent):void=
        ToggleFeed(Agent)

    OnOpenFeedTriggered(MaybeAgent : ?agent):void=
        if (Agent := MaybeAgent?):
            ToggleFeed(Agent)

    ToggleFeed<private>(Agent : agent):void=
        if (Widget := Widgets[Agent]):
            if (Widget.IsOpen?):
                Widget.CloseFeed()
            else:
                Widget.OpenFeed()

    # === WIDGET CALLBACKS ===

    # Every terminal action closes the feed. While the feed is open it
    # captures input, so the open toggle cannot fire; closing on action is
    # the exit path.
    OnHelpPressed <public>(Widget : social_feed_widget):void=
        if (HelpOptions.Length = 0):
            PostHelpRequest(Widget.OwnerAgent, -1)
            Widget.CloseFeed()
        else:
            PopulateRequestList(Widget)
            Widget.SetState(STATE_HELP)

    OnRequestSelected <public>(Widget : social_feed_widget, SlotIndex : int):void=
        if (HelpOptions.Length = 0):
            PostHelpRequest(Widget.OwnerAgent, -1)
        else if (HelpOptions[SlotIndex]):
            PostHelpRequest(Widget.OwnerAgent, SlotIndex)
        Widget.CloseFeed()

    OnThanksPressed <public>(Widget : social_feed_widget):void=
        Targets := GetThanksTargets(Widget.OwnerAgent)
        if (Targets.Length = 0):
            PostThanksAll(Widget.OwnerAgent)
            Widget.CloseFeed()
        else:
            PopulateUserList(Widget, Targets)
            Widget.SetState(STATE_THANKS)

    OnUserSelected <public>(Widget : social_feed_widget, SlotIndex : int):void=
        if (Target := Widget.ThanksTargets[SlotIndex]):
            PostThanks(Widget.OwnerAgent, Target)
        Widget.CloseFeed()

    # === LIST POPULATION ===

    # Request slot visibilities default to false in the WBP and help options
    # do not change at runtime, so only configured slots are ever written.
    PopulateRequestList<private>(Widget : social_feed_widget):void=
        for (Slot := 1..REQUEST_SLOTS):
            if (Option := HelpOptions[Slot - 1]):
                Widget.SetRequestLine(Slot, MakeMessage(Option.Label), true)

    GetThanksTargets<private>(Requester : agent):[]agent=
        var Targets : []agent = array{}
        for (Tracked : TrackedPlayers):
            if (Tracked <> Requester, Targets.Length < USER_SLOTS):
                set Targets += array{Tracked}
        Targets

    # The user list is dynamic (players join and leave between opens), so
    # slots without a target are explicitly hidden and their text reset.
    PopulateUserList<private>(Widget : social_feed_widget, Targets : []agent):void=
        set Widget.ThanksTargets = Targets
        for (Slot := 1..USER_SLOTS):
            if (Target := Targets[Slot - 1]):
                Widget.SetUserLine(Slot, MakeName(Target), true)
            else:
                Widget.SetUserLine(Slot, MakeMessage(" "), false)

    # === ENTRY POSTING ===

    AddJoinLeaveEntry<private>(Agent : agent, Joined : logic):void=
        var EntryText : string = "left the island."
        if (Joined?). set EntryText = "joined the island!"
        Entry := feed_entry:
            MaybeAgent := option{Agent}
            Text := EntryText
            PostedAt := GetSimulationElapsedTime()
        AddEntry(Entry, false)

    # Shared cooldown for the help and thanks buttons. Returns true and records
    # the action time when the player is allowed to act, false while cooling down.
    TryStartAction<private>(Agent : agent)<transacts>:logic=
        Now := GetSimulationElapsedTime()
        var Allowed : logic = true
        if (Last := LastActionAt[Agent], Now - Last < Settings.ActionCooldown):
            set Allowed = false
        if (Allowed?):
            if (set LastActionAt[Agent] = Now){}
        Allowed

    PostHelpRequest<private>(Agent : agent, OptionIndex : int):void=
        Now := GetSimulationElapsedTime()
        if (not TryStartAction(Agent)?):
            Logger("Help request blocked by cooldown", ?Name := "Help")
        else:
            set TotalHelpRequests += 1

            var Entry : feed_entry = feed_entry:
                Kind := feed_entry_type.HelpRequest
                MaybeAgent := option{Agent}
                PostedAt := Now

            if (Option := HelpOptions[OptionIndex]):
                if (Option.CustomMessage <> ""):
                    set Entry = feed_entry:
                        Kind := feed_entry_type.HelpRequest
                        MaybeAgent := option{Agent}
                        Text := Option.CustomMessage
                        UseCustomHelpText := true
                        PostedAt := Now
                else:
                    set Entry = feed_entry:
                        Kind := feed_entry_type.HelpRequest
                        MaybeAgent := option{Agent}
                        HelpLabel := Option.Label
                        PostedAt := Now
                Option.HelpRequestedOutput.Trigger(Agent)

            AddEntry(Entry, true)
            HelpRequestedOutput.Trigger(Agent)
            Logger("Help request posted", ?Name := "Help")

    PostThanks<private>(From : agent, To : agent):void=
        if (not TryStartAction(From)?):
            Logger("Thanks blocked by cooldown", ?Name := "Thanks")
        else:
            set TotalThanksGiven += 1
            Entry := feed_entry:
                Kind := feed_entry_type.Thanks
                MaybeAgent := option{From}
                MaybeTarget := option{To}
                PostedAt := GetSimulationElapsedTime()
            AddEntry(Entry, true)
            ThanksGivenOutput.Trigger(To)
            Logger("Thanks posted", ?Name := "Thanks")

    # Fired when there is no one else on the island to thank. Posts an
    # island-wide thank you and fires the output with no specific agent.
    PostThanksAll<private>(From : agent):void=
        if (not TryStartAction(From)?):
            Logger("Thanks blocked by cooldown", ?Name := "Thanks")
        else:
            set TotalThanksGiven += 1
            Entry := feed_entry:
                Kind := feed_entry_type.Thanks
                MaybeAgent := option{From}
                PostedAt := GetSimulationElapsedTime()
            AddEntry(Entry, true)
            ThanksGivenOutput.Trigger()
            Logger("Island-wide thanks posted", ?Name := "Thanks")

    AddEntry<private>(Entry : feed_entry, TriggerHasAgent : logic):void=
        set FeedEntries += array{Entry}

        if (FeedEntries.Length > FEED_LINES):
            Overflow := FeedEntries.Length - FEED_LINES
            set FeedEntries = for (Idx -> Kept : FeedEntries, Idx >= Overflow). Kept

        RefreshAllFeeds()

        if (TriggerHasAgent?, Agent := Entry.MaybeAgent?):
            EntryPostedOutput.Trigger(Agent)
        else:
            EntryPostedOutput.Trigger()

    # === FEED REFRESH ===
    # The feed is a rolling window: the newest entry renders in Text_1 and
    # pushes older entries down until they fall off after Text_25. Entries
    # never expire on a timer; they only leave by rolling off the end.

    RefreshAllFeeds<private>():void=
        for (Key -> Widget : Widgets):
            RefreshFeedFor(Widget)

    # Line visibilities default to false in the WBP, and the feed only ever
    # grows, so lines are written (and flipped visible) only when they hold
    # an entry. Empty lines are never touched.
    # Module-visible so the widget wrapper can repopulate after a fresh mount.
    RefreshFeedFor(Widget : social_feed_widget):void=
        for (Line := 1..FEED_LINES):
            ReverseIdx := FeedEntries.Length - Line
            if (Entry := FeedEntries[ReverseIdx]):
                Widget.SetFeedLine(Line, Entry.GetDisplayMessage(), true)
