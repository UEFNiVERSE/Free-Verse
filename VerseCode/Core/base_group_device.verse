# ======================================================
# FILE: base_group_device.verse
# ------------------------------------------------------
# Defines the `base_group_device` class — the group-aware
# foundation device that all UEFNiVERSE group devices extend.
#
# The companion `player_group` class (used by the Groups
# property below) lives in base_device.verse. Both files are
# part of the Core module, so they reference each other freely.
# ======================================================

# ======================================================
# IMPORTS
# ======================================================

using { /Fortnite.com/Devices }
using { /UnrealEngine.com/Temporary/Diagnostics }
using { /Verse.org/Simulation }
using { /Verse.org/Simulation/Tags }

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
