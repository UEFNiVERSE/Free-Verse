#██╗   ██╗███████╗███████╗███╗   ██╗██╗██╗   ██╗███████╗██████╗ ███████╗███████╗
#██║   ██║██╔════╝██╔════╝████╗  ██║██║██║   ██║██╔════╝██╔══██╗██╔════╝██╔════╝
#██║   ██║█████╗  █████╗  ██╔██╗ ██║██║██║   ██║█████╗  ██████╔╝███████╗█████╗
#██║   ██║██╔══╝  ██╔══╝  ██║╚██╗██║██║╚██╗ ██╔╝██╔══╝  ██╔══██╗╚════██║██╔══╝
#╚██████╔╝███████╗██║     ██║ ╚████║██║ ╚████╔╝ ███████╗██║  ██║███████║███████╗
# ╚═════╝ ╚══════╝╚═╝     ╚═╝  ╚═══╝╚═╝  ╚═══╝  ╚══════╝╚═╝  ╚═╝╚══════╝╚══════╝

# ======================================================
# FILE: social_feed_widget.verse
# ------------------------------------------------------
# Per-player Verse wrapper around WBP_SocialFeed (UMG).
# Owns the canvas mount, drives the widget bindings, and
# forwards click events to the pro_social_feed device.
#
# WBP states: 0 = feed feed, 1 = help request list,
# 2 = thank user list. The WBP owns all visuals; this
# wrapper only writes bindings and listens for events.
# ======================================================

# ======================================================
# IMPORTS
# ======================================================

using { /Fortnite.com/UI }
using { /UnrealEngine.com/Temporary/SpatialMath }
using { /UnrealEngine.com/Temporary/UI }
using { /Verse.org/Simulation }

using { UMG.Device4_SocialFeed }

# ======================================================
# ACTION CODES
# ======================================================

FEED_ACTION_STOP : int = 0
FEED_ACTION_HELP : int = 1
FEED_ACTION_THANKS : int = 2
FEED_ACTION_REQUEST_BASE : int = 10
FEED_ACTION_USER_BASE : int = 20

# ======================================================
# SOCIAL FEED WIDGET WRAPPER
# ======================================================

social_feed_widget := class:

    OwnerAgent <public>: agent
    OwnerPlayer <public>: player
    Feed <public>: pro_social_feed
    var WBP <public>: WBP_SocialFeed = WBP_SocialFeed{}

    var M_Canvas : ?canvas = false
    var UiOnScreen <public>: logic = false
    var IsOpen <public>: logic = false
    var ThanksTargets <public>: []agent = array{}
    Stop <public>: event() = event(){}

    # === MOUNTING ===
    # Re-adding a previously mounted widget instance leaves stale layout
    # state behind (text lines pile up at the same position), so every
    # mount builds a FRESH widget instance and canvas, then repopulates
    # the feed lines from the device.

    ShowUI <public>():void=
        if (UiOnScreen?). return
        MountFresh(ui_input_mode.None, false)

    HideUI <public>():void=
        Stop.Signal()
        set IsOpen = false
        set UiOnScreen = false
        if (PlayerUI := GetPlayerUI[OwnerPlayer], Canvas := M_Canvas?):
            PlayerUI.RemoveWidget(Canvas)
        set M_Canvas = false

    MountFresh <private>(Mode : ui_input_mode, OpenState : logic):void=
        if (PlayerUI := GetPlayerUI[OwnerPlayer]):
            if (OldCanvas := M_Canvas?):
                PlayerUI.RemoveWidget(OldCanvas)

            set WBP = WBP_SocialFeed{}
            set WBP.Open = OpenState
            set WBP.StateIndex = STATE_FEED

            NewCanvas := canvas:
                Slots := array:
                    canvas_slot:
                        Anchors := anchors:
                            Minimum := vector2{X := 0.0, Y := 0.0}
                            Maximum := vector2{X := 1.0, Y := 1.0}
                        Offsets := margin{Top := 0.0, Left := 0.0, Right := 0.0, Bottom := 0.0}
                        Alignment := vector2{X := 0.5, Y := 0.5}
                        Widget := WBP
            set M_Canvas = option{NewCanvas}

            PlayerUI.AddWidget(NewCanvas, player_ui_slot{ZOrder := 5, InputMode := Mode})
            set UiOnScreen = true

            Feed.RefreshFeedFor(Self)

    # === OPEN / CLOSE ===

    OpenFeed <public>():void=
        if (IsOpen?). return
        set IsOpen = true
        MountFresh(ui_input_mode.All, true)
        spawn{ListenForInput()}

    CloseFeed <public>():void=
        Stop.Signal()
        set IsOpen = false
        MountFresh(ui_input_mode.None, false)

    SetState <public>(State : int):void=
        set WBP.StateIndex = State

    # === INPUT LOOP ===

    ListenForInput <private>()<suspends>:void=
        loop:
            if (not IsOpen?). break
            Action := AwaitNextAction()
            if (Action = FEED_ACTION_STOP):
                break
            else if (Action = FEED_ACTION_HELP):
                Feed.OnHelpPressed(Self)
            else if (Action = FEED_ACTION_THANKS):
                Feed.OnThanksPressed(Self)
            else if (Action >= FEED_ACTION_USER_BASE):
                Feed.OnUserSelected(Self, Action - FEED_ACTION_USER_BASE)
            else if (Action >= FEED_ACTION_REQUEST_BASE):
                Feed.OnRequestSelected(Self, Action - FEED_ACTION_REQUEST_BASE)

    AwaitNextAction <private>()<suspends>:int=
        race:
            block:
                Stop.Await()
                FEED_ACTION_STOP
            block:
                WBP.HelpClicked.Await()
                FEED_ACTION_HELP
            block:
                WBP.ThanksClicked.Await()
                FEED_ACTION_THANKS
            block:
                WBP.RequestClicked_1.Await()
                FEED_ACTION_REQUEST_BASE + 0
            block:
                WBP.RequestClicked_2.Await()
                FEED_ACTION_REQUEST_BASE + 1
            block:
                WBP.RequestClicked_3.Await()
                FEED_ACTION_REQUEST_BASE + 2
            block:
                WBP.RequestClicked_4.Await()
                FEED_ACTION_REQUEST_BASE + 3
            block:
                WBP.RequestClicked_5.Await()
                FEED_ACTION_REQUEST_BASE + 4
            block:
                WBP.UserClicked_1.Await()
                FEED_ACTION_USER_BASE + 0
            block:
                WBP.UserClicked_2.Await()
                FEED_ACTION_USER_BASE + 1
            block:
                WBP.UserClicked_3.Await()
                FEED_ACTION_USER_BASE + 2
            block:
                WBP.UserClicked_4.Await()
                FEED_ACTION_USER_BASE + 3
            block:
                WBP.UserClicked_5.Await()
                FEED_ACTION_USER_BASE + 4

    # === FEED LINE BINDINGS ===
    # Note: Visiblity_N spelling matches the WBP bindings exactly.

    SetFeedLine <public>(Index : int, Msg : message, Vis : logic):void=
        if (Index = 1). SetLine1(Msg, Vis)
        else if (Index = 2). SetLine2(Msg, Vis)
        else if (Index = 3). SetLine3(Msg, Vis)
        else if (Index = 4). SetLine4(Msg, Vis)
        else if (Index = 5). SetLine5(Msg, Vis)
        else if (Index = 6). SetLine6(Msg, Vis)
        else if (Index = 7). SetLine7(Msg, Vis)
        else if (Index = 8). SetLine8(Msg, Vis)
        else if (Index = 9). SetLine9(Msg, Vis)
        else if (Index = 10). SetLine10(Msg, Vis)
        else if (Index = 11). SetLine11(Msg, Vis)
        else if (Index = 12). SetLine12(Msg, Vis)
        else if (Index = 13). SetLine13(Msg, Vis)
        else if (Index = 14). SetLine14(Msg, Vis)
        else if (Index = 15). SetLine15(Msg, Vis)
        else if (Index = 16). SetLine16(Msg, Vis)
        else if (Index = 17). SetLine17(Msg, Vis)
        else if (Index = 18). SetLine18(Msg, Vis)
        else if (Index = 19). SetLine19(Msg, Vis)
        else if (Index = 20). SetLine20(Msg, Vis)
        else if (Index = 21). SetLine21(Msg, Vis)
        else if (Index = 22). SetLine22(Msg, Vis)
        else if (Index = 23). SetLine23(Msg, Vis)
        else if (Index = 24). SetLine24(Msg, Vis)
        else if (Index = 25). SetLine25(Msg, Vis)

    SetLine1 <private>(Msg : message, Vis : logic):void=
        set WBP.Text_1 = Msg
        set WBP.Visiblity_1 = Vis
    SetLine2 <private>(Msg : message, Vis : logic):void=
        set WBP.Text_2 = Msg
        set WBP.Visiblity_2 = Vis
    SetLine3 <private>(Msg : message, Vis : logic):void=
        set WBP.Text_3 = Msg
        set WBP.Visiblity_3 = Vis
    SetLine4 <private>(Msg : message, Vis : logic):void=
        set WBP.Text_4 = Msg
        set WBP.Visiblity_4 = Vis
    SetLine5 <private>(Msg : message, Vis : logic):void=
        set WBP.Text_5 = Msg
        set WBP.Visiblity_5 = Vis
    SetLine6 <private>(Msg : message, Vis : logic):void=
        set WBP.Text_6 = Msg
        set WBP.Visiblity_6 = Vis
    SetLine7 <private>(Msg : message, Vis : logic):void=
        set WBP.Text_7 = Msg
        set WBP.Visiblity_7 = Vis
    SetLine8 <private>(Msg : message, Vis : logic):void=
        set WBP.Text_8 = Msg
        set WBP.Visiblity_8 = Vis
    SetLine9 <private>(Msg : message, Vis : logic):void=
        set WBP.Text_9 = Msg
        set WBP.Visiblity_9 = Vis
    SetLine10 <private>(Msg : message, Vis : logic):void=
        set WBP.Text_10 = Msg
        set WBP.Visiblity_10 = Vis
    SetLine11 <private>(Msg : message, Vis : logic):void=
        set WBP.Text_11 = Msg
        set WBP.Visiblity_11 = Vis
    SetLine12 <private>(Msg : message, Vis : logic):void=
        set WBP.Text_12 = Msg
        set WBP.Visiblity_12 = Vis
    SetLine13 <private>(Msg : message, Vis : logic):void=
        set WBP.Text_13 = Msg
        set WBP.Visiblity_13 = Vis
    SetLine14 <private>(Msg : message, Vis : logic):void=
        set WBP.Text_14 = Msg
        set WBP.Visiblity_14 = Vis
    SetLine15 <private>(Msg : message, Vis : logic):void=
        set WBP.Text_15 = Msg
        set WBP.Visiblity_15 = Vis
    SetLine16 <private>(Msg : message, Vis : logic):void=
        set WBP.Text_16 = Msg
        set WBP.Visiblity_16 = Vis
    SetLine17 <private>(Msg : message, Vis : logic):void=
        set WBP.Text_17 = Msg
        set WBP.Visiblity_17 = Vis
    SetLine18 <private>(Msg : message, Vis : logic):void=
        set WBP.Text_18 = Msg
        set WBP.Visiblity_18 = Vis
    SetLine19 <private>(Msg : message, Vis : logic):void=
        set WBP.Text_19 = Msg
        set WBP.Visiblity_19 = Vis
    SetLine20 <private>(Msg : message, Vis : logic):void=
        set WBP.Text_20 = Msg
        set WBP.Visiblity_20 = Vis
    SetLine21 <private>(Msg : message, Vis : logic):void=
        set WBP.Text_21 = Msg
        set WBP.Visiblity_21 = Vis
    SetLine22 <private>(Msg : message, Vis : logic):void=
        set WBP.Text_22 = Msg
        set WBP.Visiblity_22 = Vis
    SetLine23 <private>(Msg : message, Vis : logic):void=
        set WBP.Text_23 = Msg
        set WBP.Visiblity_23 = Vis
    SetLine24 <private>(Msg : message, Vis : logic):void=
        set WBP.Text_24 = Msg
        set WBP.Visiblity_24 = Vis
    SetLine25 <private>(Msg : message, Vis : logic):void=
        set WBP.Text_25 = Msg
        set WBP.Visiblity_25 = Vis

    # === REQUEST LIST BINDINGS ===

    SetRequestLine <public>(Index : int, Msg : message, Vis : logic):void=
        if (Index = 1):
            set WBP.RequestText_1 = Msg
            set WBP.RequestVisibility_1 = Vis
        else if (Index = 2):
            set WBP.RequestText_2 = Msg
            set WBP.RequestVisibility_2 = Vis
        else if (Index = 3):
            set WBP.RequestText_3 = Msg
            set WBP.RequestVisibility_3 = Vis
        else if (Index = 4):
            set WBP.RequestText_4 = Msg
            set WBP.RequestVisibility_4 = Vis
        else if (Index = 5):
            set WBP.RequestText_5 = Msg
            set WBP.RequestVisibility_5 = Vis

    # === USER LIST BINDINGS ===

    SetUserLine <public>(Index : int, Msg : message, Vis : logic):void=
        if (Index = 1):
            set WBP.UserText_1 = Msg
            set WBP.UserVisibility_1 = Vis
        else if (Index = 2):
            set WBP.UserText_2 = Msg
            set WBP.UserVisibility_2 = Vis
        else if (Index = 3):
            set WBP.UserText_3 = Msg
            set WBP.UserVisibility_3 = Vis
        else if (Index = 4):
            set WBP.UserText_4 = Msg
            set WBP.UserVisibility_4 = Vis
        else if (Index = 5):
            set WBP.UserText_5 = Msg
            set WBP.UserVisibility_5 = Vis
