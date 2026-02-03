#██╗   ██╗███████╗███████╗███╗   ██╗██╗██╗   ██╗███████╗██████╗ ███████╗███████╗
#██║   ██║██╔════╝██╔════╝████╗  ██║██║██║   ██║██╔════╝██╔══██╗██╔════╝██╔════╝
#██║   ██║█████╗  █████╗  ██╔██╗ ██║██║██║   ██║█████╗  ██████╔╝███████╗█████╗  
#██║   ██║██╔══╝  ██╔══╝  ██║╚██╗██║██║╚██╗ ██╔╝██╔══╝  ██╔══██╗╚════██║██╔══╝  
#╚██████╔╝███████╗██║     ██║ ╚████║██║ ╚████╔╝ ███████╗██║  ██║███████║███████╗
# ╚═════╝ ╚══════╝╚═╝     ╚═╝  ╚═══╝╚═╝  ╚═══╝  ╚══════╝╚═╝  ╚═╝╚══════╝╚══════╝

# ======================================================
# IMPORTS
# ======================================================

using { /Fortnite.com/Devices }
using { /UnrealEngine.com/Temporary/Diagnostics }
using { /Verse.org/Simulation }
using { /Verse.org/Simulation/Tags }

# ======================================================
# TAGS
# ======================================================

t_PlayerSpawner <public> := class(tag) {}

# ======================================================
# TOOLTIPS
# ======================================================

InitTriggerTip <public><localizes> :message = "If assigned, the device will wait for this trigger to be activated before initializing."
GroupTip <public><localizes> :message = "The player groups that will interact with this device (can be used as an extension of teams/ classes)."
GroupAssignTriggerTip <public><localizes> :message = "The trigger that will add players to this group when activated."
GroupRemoveTriggerTip <public><localizes> :message = "The trigger that will remove players from this group when activated."
GroupDisplayHUDTip <public><localizes> :message = "The HUD message device that will display for players when they are assigned to this group."

# ======================================================
# PLAYER GROUP CLASS
# ======================================================

player_group <public> := class<concrete>:
    
    # === EDITABLE PROPERTIES ===
    @editable { ToolTip := LabelTip } Label <public> : string = ""
    @editable { ToolTip := GroupAssignTriggerTip } AssignTrigger <public> : trigger_device = trigger_device{}
    @editable { ToolTip := GroupRemoveTriggerTip } RemoveTrigger <public> : trigger_device = trigger_device{}
    @editable { ToolTip := GroupDisplayHUDTip } GroupDisplayHUD <public> : hud_message_device = hud_message_device{}

    # === INTERNAL STATE ===
    var MaybeParent : ?base_group_device = false
    var Index <public>: int = -1
    var GroupAgents <public>: []agent = array{}

    # === CONFIGURATION ===
    LOGGER_NAME : string = "Player Group"

    # === INITIALIZATION ===

    Init<public>(Parent : base_group_device, GroupIdx : int):void=
        set MaybeParent = option. Parent
        set Index = GroupIdx
        AssignTrigger.TriggeredEvent.Subscribe(AssignAgent)
        RemoveTrigger.TriggeredEvent.Subscribe(RemoveAgent)
        Parent.Logger("Initialized Player Group: {Index}: {Label} ", ?Name := LOGGER_NAME)

    # === EVENT HANDLERS ===

    AssignAgent<public>(MaybeAgent : ?agent):void= if(Agent := MaybeAgent?). Agent.Assign()
    RemoveAgent<public>(MaybeAgent : ?agent):void= if(Agent := MaybeAgent?). Agent.Remove()

    # === GROUP MEMBERSHIP ===

    Check<public>(Agent: agent)<transacts>:logic= if(GroupAgents.Find[Agent]). true else. false

    (Agent: agent).Assign<public>():void=
        if(Parent := MaybeParent?):
            Parent.RemoveFromOtherGroups(Agent, Index)
            if (Check(Agent)?). Parent.Logger("Agent already in Group {Index}: {Label}", ?Name := LOGGER_NAME)
            else:
                set GroupAgents += array. Agent
                GroupDisplayHUD.Show(Agent)
                Parent.Logger("Assigned Agent to Group {Index}: {Label}", ?Name := LOGGER_NAME)

    (Agent: agent).Remove<public>():void=
        var NewGroupAgents : []agent = array{}
        if(Parent := MaybeParent?):
            if(Check(Agent)?):
                for (GroupAgent : GroupAgents, GroupAgent <> Agent). set NewGroupAgents += array. GroupAgent
                set GroupAgents = NewGroupAgents
                GroupDisplayHUD.Hide(Agent)
                Parent.Logger("Removed Agent from Group {Index}: {Label}", ?Name := LOGGER_NAME)
            else. Parent.Logger("Agent not found in Group {Index}: {Label}", ?Name := LOGGER_NAME)

# ======================================================
# BASE GROUP DEVICE CLASS
# ======================================================

base_group_device <public> := class(creative_device):
    
    # === EDITABLE PROPERTIES ===
    @editable { ToolTip := InitTriggerTip } InitTrigger <public> : ?trigger_device = false
    @editable { ToolTip := GroupTip } Groups <public> : []player_group = array{}
    @editable { ToolTip := DebugTip } Debug <public> : debug_settings = debug_settings{}

    # === INTERNAL STATE ===
    var Spawners : []player_spawner_device = array{}
    var ActivePlayers : []agent = array{}

    # === CONFIGURATION ===
    LOGGER_NAME<public>: string = "Base Device"

    # === INITIALIZATION ===

    OnBegin<override>()<suspends>:void=
        if (Trigger := InitTrigger?). Trigger.TriggeredEvent.Await()

        for (Index -> Group : Groups). Group.Init(Self, Index)

        Initialize()

        GetPlayspace().PlayerRemovedEvent().Subscribe(OnAgentRemoved)
        GetPlayspace().PlayerAddedEvent().Subscribe(OnAgentSpawned)

        SaveSpawnersFromTags()
        for (Spawner : Spawners). Spawner.SpawnedEvent.Subscribe(OnAgentSpawned)

        Logger("")

    # === LIFECYCLE EVENTS (PRIVATE) ===

    OnAgentSpawned<private>(Agent : agent):void=
        if (ActivePlayers.Find[Agent]). OnAgentRespawned(Agent)
        else:
            set ActivePlayers += array. Agent
            OnAgentJoined(Agent)

    OnAgentRemoved<private>(Agent : agent):void=
        var NewActivePlayers : []agent = array{}
        if (ActivePlayers.Find[Agent]):
            for (ActivePlayer : ActivePlayers, ActivePlayer <> Agent). set NewActivePlayers += array. ActivePlayer
            set ActivePlayers = NewActivePlayers
            OnAgentLeft(Agent)

    # === OVERRIDABLE LIFECYCLE HOOKS ===

    Initialize<public>()<suspends>:void={}
    OnAgentJoined<public>(Agent : agent):void={}
    OnAgentRespawned<public>(Agent : agent):void={}
    OnAgentLeft<public>(Agent : agent):void={}
    
    # === GROUP MANAGEMENT ===

    GetGroups<public>():[]player_group= Groups

    GetGroupIndex<public>(Agent : agent)<transacts>:int=
        var Return : int = -1
        for (Idx -> Group : Groups, Group.Check(Agent)?). set Return = Idx
        Return

    GetGroup<public>(Agent : agent)<decides><transacts>:player_group= Groups[GetGroupIndex(Agent)]

    RemoveFromOtherGroups<public>(Agent : agent, ExcludeGroupIdx : int):void=
        for (Idx -> Group : Groups, Idx <> ExcludeGroupIdx). Group.RemoveAgent(option. Agent)

    # === HELPER FUNCTIONS ===

    SaveSpawnersFromTags<private>():void=
        set Spawners = array{}
        TaggedSpawners := FindCreativeObjectsWithTag(t_PlayerSpawner{})
        for (Idx -> TaggedSpawner : TaggedSpawners, Spawner := player_spawner_device[TaggedSpawner]):
            set Spawners += array. Spawner

    Logger <public> (Message : string, ?Name : string = ""):void=
        var Label : string = ""
        if (Debug.EnableDebug?):
            set Label = LOGGER_NAME + " - " + Name
            if (Message = ""). Print("[{Label}] 👋 Hello World!")
            else. Print("[{Label}] {Message}")
