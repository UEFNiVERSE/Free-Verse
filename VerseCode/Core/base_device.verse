#██╗   ██╗███████╗███████╗███╗   ██╗██╗██╗   ██╗███████╗██████╗ ███████╗███████╗
#██║   ██║██╔════╝██╔════╝████╗  ██║██║██║   ██║██╔════╝██╔══██╗██╔════╝██╔════╝
#██║   ██║█████╗  █████╗  ██╔██╗ ██║██║██║   ██║█████╗  ██████╔╝███████╗█████╗  
#██║   ██║██╔══╝  ██╔══╝  ██║╚██╗██║██║╚██╗ ██╔╝██╔══╝  ██╔══██╗╚════██║██╔══╝  
#╚██████╔╝███████╗██║     ██║ ╚████║██║ ╚████╔╝ ███████╗██║  ██║███████║███████╗
# ╚═════╝ ╚══════╝╚═╝     ╚═╝  ╚═══╝╚═╝  ╚═══╝  ╚══════╝╚═╝  ╚═╝╚══════╝╚══════╝

# ======================================================
# FILE: base_device.verse
# ------------------------------------------------------
# Defines the `player_group` class plus the shared Core tags
# and tooltips used by the group system.
#
# The `base_group_device` class was moved to its own file,
# base_group_device.verse. Both files are part of the Core
# module, so `player_group` and `base_group_device` continue
# to reference each other across files without any changes.
# ======================================================

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

# NOTE: The `base_group_device` class that previously lived here has been
# moved to base_group_device.verse (same Core module).
