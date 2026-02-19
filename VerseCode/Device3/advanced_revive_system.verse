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
using { /Fortnite.com/Characters }
using { /UnrealEngine.com/Temporary/Diagnostics }
using { /UnrealEngine.com/Temporary/SpatialMath }
using { /Verse.org/Simulation }

using { Core }

# ======================================================
# TOOLTIPS
# ======================================================

ReviveSettingsTip <public><localizes> :message = "Configure the revive system behavior and timing requirements."
ReviveTiersTip <public><localizes> :message = "Define revive tiers that activate based on number of teammates reviving the downed player."
ReviveButtonsTip <public><localizes> :message = "Array of button devices used for reviving downed players. One button per group will be used and teleported to downed players."
DownButNotOutDeviceTip <public><localizes> :message = "The down but not out device that detects when players are downed and handles revives."
TimeToReviveTip <public><localizes> :message = "Time (in seconds) the group has to revive the downed player before automatic revival at the current tier."
AllowSelfReviveTip <public><localizes> :message = "If enabled, the downed player can contribute to their own revival by interacting with the button."
ReviverCountTip <public><localizes> :message = "Number of teammates required to be reviving simultaneously to activate this tier."
TierActivatedOutputTip <public><localizes> :message = "Triggered when this revive tier is activated. Passes the revived agent for custom reward logic."
PlayerDownedOutputTip <public><localizes> :message = "Triggered when a player is downed. Passes the downed agent for custom logic."
PlayerRevivedOutputTip <public><localizes> :message = "Triggered when a player is revived at any tier. Passes the revived agent."

# ======================================================
# ENUMS
# ======================================================

revive_state := enum:
    Idle
    Downed
    BeingRevived
    Revived

# ======================================================
# REVIVE TIER CLASS
# ======================================================

revive_tier := class<concrete><unique>:
    
    # === EDITABLE PROPERTIES ===
    @editable { ToolTip := LabelTip } Label <public>: string = ""
    @editable { ToolTip := ReviverCountTip } ReviverCount <public>: int = 1
    @editable { ToolTip := TierActivatedOutputTip } TierActivatedOutput <public>: trigger_device = trigger_device{}
    
    # === INTERNAL STATE ===
    var ActivatedForAgent : [agent]logic = map{}
    
    # === REVIVE TIER METHODS ===
    
    HasBeenActivatedFor<public>(Agent: agent)<transacts>:logic=
        if (Activated := ActivatedForAgent[Agent]). Activated else. false
    
    Activate<public>(Agent: agent, Manager: advanced_revive_system):void=
        var WasActivated : logic = HasBeenActivatedFor(Agent)
        if (WasActivated = false):
            if (set ActivatedForAgent[Agent] = true){}
            TierActivatedOutput.Trigger(Agent)
            Manager.Logger("Revive tier '{Label}' activated for agent ({ReviverCount} revivers)", ?Name := "Revive Tier")
    
    Reset<public>(Agent: agent):void=
        var NewAgentMap : [agent]logic = map{}
        for (Key -> Value : ActivatedForAgent, Key <> Agent):
            if (set NewAgentMap[Key] = Value){}
        set ActivatedForAgent = NewAgentMap

# ======================================================
# REVIVE SETTINGS CLASS
# ======================================================

revive_settings := class<concrete>:
    
    # === EDITABLE PROPERTIES ===
    @editable { ToolTip := TimeToReviveTip } TimeToRevive <public>: float = 30.0
    @editable { ToolTip := AllowSelfReviveTip } AllowSelfRevive <public>: logic = false
    
    # === CONSTANTS ===
    TeleportInterval <public>: float = 0.033
    ButtonHeightOffset <public>: float = 0.0
    ForceReviveOnTimeout <public>: logic = true

# ======================================================
# DOWNED PLAYER TRACKER CLASS
# ======================================================

downed_player_tracker := class:
    
    DownedAgent <public>: agent
    GroupIndex <public>: int
    AssignedButtonIndex <public>: int
    var CurrentRevivers <public>: []agent = array{}
    var State <public>: revive_state = revive_state.Idle
    var HighestTierReached <public>: int = -1
    var TimeoutTaskActive : logic = false
    var TeleportTaskActive : logic = false
    
    SetState<public>(NewState: revive_state):void=
        set State = NewState
    
    AddReviver<public>(Agent: agent):void=
        if (not CurrentRevivers.Find[Agent]):
            set CurrentRevivers += array{Agent}
    
    RemoveReviver<public>(Agent: agent):void=
        set CurrentRevivers = for (A : CurrentRevivers, A <> Agent). A
    
    GetReviverCount<public>():int=
        CurrentRevivers.Length
    
    SetTimeoutTaskActive<public>(Active: logic):void=
        set TimeoutTaskActive = Active
    
    IsTimeoutTaskActive<public>():logic=
        TimeoutTaskActive
    
    SetTeleportTaskActive<public>(Active: logic):void=
        set TeleportTaskActive = Active
    
    IsTeleportTaskActive<public>():logic=
        TeleportTaskActive

# ======================================================
# ADVANCED REVIVE SYSTEM DEVICE
# ======================================================

advanced_revive_system := class(Core.base_group_device):
    
    # === EDITABLE PROPERTIES ===
    @editable { ToolTip := ReviveSettingsTip } Settings <public>: revive_settings = revive_settings{}
    @editable { ToolTip := ReviveTiersTip } ReviveTiers <public>: []revive_tier = array{}
    @editable { ToolTip := ReviveButtonsTip } ReviveButtons <public>: []button_device = array{}
    @editable { ToolTip := DownButNotOutDeviceTip } DownButNotOutDevice <public>: down_but_not_out_device = down_but_not_out_device{}
    @editable { ToolTip := PlayerDownedOutputTip } PlayerDownedOutput <public>: trigger_device = trigger_device{}
    @editable { ToolTip := PlayerRevivedOutputTip } PlayerRevivedOutput <public>: trigger_device = trigger_device{}
    
    # === CONFIGURATION ===
    LOGGER_NAME <override>: string = "Advanced Revive System"
    
    # === INTERNAL STATE ===
    var DownedPlayers : [agent]downed_player_tracker = map{}
    var AvailableButtonsPerGroup : [int][]int = map{}
    var ButtonIndexToDownedAgent : [int]agent = map{}
    
    # === INITIALIZATION ===
    
    Initialize<override>()<suspends>:void=
        InitializeButtonPools()
        DisableAllButtons()
        
        DownButNotOutDevice.AgentDownedEvent.Subscribe(OnAgentDowned)
        DownButNotOutDevice.AgentRevivedEvent.Subscribe(OnAgentRevived)
        
        for (Button : ReviveButtons):
            Button.InteractedWithEvent.Subscribe(OnButtonInteracted)
        
        Logger("Initialized with {ReviveTiers.Length} tier(s) and {ReviveButtons.Length} button(s)")
    
    DisableAllButtons<private>():void=
        for (Button : ReviveButtons):
            Button.Disable()
        Logger("Disabled all revive buttons", ?Name := "Init")
    
    InitializeButtonPools<private>():void=
        PlayerGroups := GetGroups()
        var ButtonIndices : []int = array{}
        for (Idx -> Button : ReviveButtons):
            set ButtonIndices += array{Idx}
        
        for (Idx -> Group : PlayerGroups):
            if (set AvailableButtonsPerGroup[Idx] = ButtonIndices){}
            Logger("Initialized button pool for Group {Idx}: {Group.Label} with {ReviveButtons.Length} buttons", ?Name := "Init")
    
    # === EVENT HANDLERS ===
    
    OnAgentDowned(Agent: agent):void=
        if (Group := GetGroup[Agent]):
            Logger("Agent downed in Group {Group.Index}: {Group.Label}", ?Name := "Player Downed")
            
            if (DownedPlayers[Agent]):
                Logger("Agent already has active downed tracker, cleaning up old one", ?Name := "Player Downed")
                CleanupDownedPlayer(Agent)
            
            MaybeFreeButtonIdx := GetFreeButton(Group.Index)
            if (FreeButtonIdx := MaybeFreeButtonIdx?):
                Tracker := downed_player_tracker:
                    DownedAgent := Agent
                    GroupIndex := Group.Index
                    AssignedButtonIndex := FreeButtonIdx
                
                Tracker.SetState(revive_state.Downed)
                
                if (set DownedPlayers[Agent] = Tracker){}
                if (set ButtonIndexToDownedAgent[FreeButtonIdx] = Agent){}
                
                if (AssignedButton := ReviveButtons[FreeButtonIdx]):
                    AssignedButton.Enable()
                
                spawn{StartButtonTeleportLoop(Agent)}
                
                PlayerDownedOutput.Trigger(Agent)
                
                Logger("Assigned button {FreeButtonIdx} to downed player and enabled it", ?Name := "Player Downed")
            else:
                Logger("No free buttons available for Group {Group.Index}", ?Name := "Player Downed")
        else:
            Logger("Downed agent not in any group, cannot handle revive", ?Name := "Player Downed")
    
    OnAgentRevived(Agent: agent):void=
        Logger("Agent revived by game system", ?Name := "Player Revived")
    
    OnButtonInteracted(Agent: agent):void=
        for (ButtonIdx -> Button : ReviveButtons):
            if (DownedAgent := ButtonIndexToDownedAgent[ButtonIdx]):
                if (Tracker := DownedPlayers[DownedAgent]):
                    var CanRevive : logic = true
                    
                    if (Settings.AllowSelfRevive = false):
                        if (Agent = DownedAgent):
                            set CanRevive = false
                            Logger("Self-revive not allowed", ?Name := "Button Interaction")
                    
                    if (CanRevive = true):
                        if (Group := GetGroup[Agent]):
                            if (Group.Index = Tracker.GroupIndex):
                                Tracker.AddReviver(Agent)
                                Logger("Agent started reviving (Total: {Tracker.GetReviverCount()})", ?Name := "Button Interaction")
                                spawn{HandleReviverProgress(Agent, DownedAgent)}
                            else:
                                Logger("Agent from different group cannot revive", ?Name := "Button Interaction")
                        else:
                            Logger("Reviving agent not in any group", ?Name := "Button Interaction")
    
    # === REVIVE LOGIC ===
    
    HandleReviverProgress(ReviverAgent: agent, DownedAgent: agent)<suspends>:void=
        if (Tracker := DownedPlayers[DownedAgent]):
            var WasBeingRevived : logic = false
            if (Tracker.State = revive_state.BeingRevived):
                set WasBeingRevived = true
            
            Tracker.SetState(revive_state.BeingRevived)
            
            if (WasBeingRevived = false):
                var TimeoutActive : logic = Tracker.IsTimeoutTaskActive()
                if (TimeoutActive = false):
                    spawn{StartReviveTimeout(DownedAgent)}
                    Logger("First reviver started, revive timer beginning", ?Name := "Revive Started")
            
            EvaluateReviveTiers(DownedAgent)
    
    EvaluateReviveTiers(DownedAgent: agent)<suspends>:void=
        if (Tracker := DownedPlayers[DownedAgent]):
            CurrentReviverCount := Tracker.GetReviverCount()
            
            var HighestQualifyingTierIdx : int = -1
            
            for (TierIdx -> Tier : ReviveTiers):
                if (CurrentReviverCount >= Tier.ReviverCount):
                    if (TierIdx > HighestQualifyingTierIdx):
                        set HighestQualifyingTierIdx = TierIdx
            
            if (HighestQualifyingTierIdx > Tracker.HighestTierReached):
                set Tracker.HighestTierReached = HighestQualifyingTierIdx
                
                if (QualifyingTier := ReviveTiers[HighestQualifyingTierIdx]):
                    Logger("New highest tier reached: {QualifyingTier.Label} ({CurrentReviverCount} revivers)", ?Name := "Tier Evaluation")
    
    StartReviveTimeout(DownedAgent: agent)<suspends>:void=
        if (Tracker := DownedPlayers[DownedAgent]):
            Tracker.SetTimeoutTaskActive(true)
            
            Logger("Starting revive timeout: {Settings.TimeToRevive}s", ?Name := "Timeout")
            
            Sleep(Settings.TimeToRevive)
            
            if (ActiveTracker := DownedPlayers[DownedAgent]):
                if (ActiveTracker.TimeoutTaskActive = true):
                    Logger("Timeout reached, force reviving at tier {ActiveTracker.HighestTierReached}", ?Name := "Timeout")
                    PerformRevive(DownedAgent)
    
    PerformRevive(DownedAgent: agent)<suspends>:void=
        if (Tracker := DownedPlayers[DownedAgent]):
            Tracker.SetState(revive_state.Revived)
            
            if (Tracker.HighestTierReached >= 0):
                if (AchievedTier := ReviveTiers[Tracker.HighestTierReached]):
                    AchievedTier.Activate(DownedAgent, Self)
                    Logger("Triggering tier output: {AchievedTier.Label}", ?Name := "Revive Complete")
            
            DownButNotOutDevice.Revive(DownedAgent)
            
            PlayerRevivedOutput.Trigger(DownedAgent)
            
            Logger("Player revived successfully at tier {Tracker.HighestTierReached}", ?Name := "Revive Complete")
            
            CleanupDownedPlayer(DownedAgent)
    
    StartButtonTeleportLoop(DownedAgent: agent)<suspends>:void=
        if (Tracker := DownedPlayers[DownedAgent]):
            Tracker.SetTeleportTaskActive(true)
            
            if (AssignedButton := ReviveButtons[Tracker.AssignedButtonIndex]):
                loop:
                    Sleep(Settings.TeleportInterval)
                    
                    if (ActiveTracker := DownedPlayers[DownedAgent]):
                        if (ActiveTracker.TeleportTaskActive = false):
                            break
                        
                        if (FortChar := DownedAgent.GetFortCharacter[]):
                            CharTransform := FortChar.GetTransform()
                            CharLocation := CharTransform.Translation
                            
                            OffsetLocation := vector3:
                                X := CharLocation.X
                                Y := CharLocation.Y
                                Z := CharLocation.Z + Settings.ButtonHeightOffset
                            
                            block:
                                if (AssignedButton.TeleportTo[OffsetLocation, CharTransform.Rotation]){}
                                else{}

                    else:
                        break
    
    CleanupDownedPlayer(Agent: agent):void=
        if (Tracker := DownedPlayers[Agent]):
            Tracker.SetTimeoutTaskActive(false)
            Tracker.SetTeleportTaskActive(false)
            
            ReturnButtonIdx := Tracker.AssignedButtonIndex
            GroupIdx := Tracker.GroupIndex
            
            if (AssignedButton := ReviveButtons[ReturnButtonIdx]):
                AssignedButton.Disable()
            
            var CurrentButtonIndices : []int = array{}
            if (Indices := AvailableButtonsPerGroup[GroupIdx]):
                set CurrentButtonIndices = Indices
            
            set CurrentButtonIndices += array{ReturnButtonIdx}
            if (set AvailableButtonsPerGroup[GroupIdx] = CurrentButtonIndices){}
            
            var NewButtonMap : [int]agent = map{}
            for (Key -> Value : ButtonIndexToDownedAgent, Key <> ReturnButtonIdx):
                if (set NewButtonMap[Key] = Value){}
            set ButtonIndexToDownedAgent = NewButtonMap
            
            for (Tier : ReviveTiers):
                Tier.Reset(Agent)
            
            var NewDownedMap : [agent]downed_player_tracker = map{}
            for (Key -> Value : DownedPlayers, Key <> Agent):
                if (set NewDownedMap[Key] = Value){}
            set DownedPlayers = NewDownedMap
            
            Logger("Cleaned up downed player tracker, disabled button {ReturnButtonIdx}, and returned to pool", ?Name := "Cleanup")
    
    GetFreeButton(GroupIndex: int)<transacts>:?int=
        var Result : ?int = false
        if (ButtonIndices := AvailableButtonsPerGroup[GroupIndex]):
            if:
                ButtonIndices.Length > 0
                FreeButtonIdx := ButtonIndices[0]
            then:
                var NewIndices : []int = array{}
                for (Idx -> ButtonIdx : ButtonIndices, Idx > 0):
                    set NewIndices += array{ButtonIdx}
                
                if (set AvailableButtonsPerGroup[GroupIndex] = NewIndices){}
                
                set Result = option{FreeButtonIdx}
        Result
    
    # === LIFECYCLE EVENTS ===
    
    OnAgentJoined<override>(Agent: agent):void=
        Logger("Agent joined game")
    
    OnAgentRespawned<override>(Agent: agent):void=
        Logger("Agent respawned")
        CleanupDownedPlayer(Agent)
    
    OnAgentLeft<override>(Agent: agent):void=
        CleanupDownedPlayer(Agent)
        Logger("Agent left game")
