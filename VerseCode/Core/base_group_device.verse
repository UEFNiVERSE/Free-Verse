#██╗   ██╗███████╗███████╗███╗   ██╗██╗██╗   ██╗███████╗██████╗ ███████╗███████╗
#██║   ██║██╔════╝██╔════╝████╗  ██║██║██║   ██║██╔════╝██╔══██╗██╔════╝██╔════╝
#██║   ██║█████╗  █████╗  ██╔██╗ ██║██║██║   ██║█████╗  ██████╔╝███████╗█████╗
#██║   ██║██╔══╝  ██╔══╝  ██║╚██╗██║██║╚██╗ ██╔╝██╔══╝  ██╔══██╗╚════██║██╔══╝
#╚██████╔╝███████╗██║     ██║ ╚████║██║ ╚████╔╝ ███████╗██║  ██║███████║███████╗
# ╚═════╝ ╚══════╝╚═╝     ╚═╝  ╚═══╝╚═╝  ╚═══╝  ╚══════╝╚═╝  ╚═╝╚══════╝╚══════╝

# ======================================================
# FILE: base_group_device.verse
# ------------------------------------------------------
# Defines `base_group_device`: extends `base_device` and
# adds the player group layer. All lifecycle, spawner,
# and logging behavior is inherited from base_device
# (base_device.verse); this class only owns groups.
#
# The companion `player_group` class lives in
# base_device.verse. Both files are part of the Core
# module, so they reference each other freely.
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

base_group_device <public> := class(base_device):

    # === EDITABLE PROPERTIES ===
    @editable { ToolTip := GroupTip } Groups <public> : []player_group = array{}

    # === INITIALIZATION ===

    # Groups initialize before the subclass's Initialize() runs,
    # preserving the original base_group_device startup order.
    PreInitialize<override>():void=
        for (Index -> Group : Groups). Group.Init(Self, Index)

    # === GROUP MANAGEMENT ===

    GetGroups<public>():[]player_group= Groups

    GetGroupIndex<public>(Agent : agent)<transacts>:int=
        var Return : int = -1
        for (Idx -> Group : Groups, Group.Check(Agent)?). set Return = Idx
        Return

    GetGroup<public>(Agent : agent)<decides><transacts>:player_group= Groups[GetGroupIndex(Agent)]

    RemoveFromOtherGroups<public>(Agent : agent, ExcludeGroupIdx : int):void=
        for (Idx -> Group : Groups, Idx <> ExcludeGroupIdx). Group.RemoveAgent(option. Agent)
