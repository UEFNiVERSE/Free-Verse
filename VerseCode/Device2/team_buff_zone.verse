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

using { Core }

# ======================================================
# TOOLTIPS
# ======================================================

BuffZoneSettingsTip <public><localizes> :message = "Configure the buff zone behavior and activation requirements."
BuffZoneTip <public><localizes> :message = "The volume device that defines the buff zone area."
MinTeammatesRequiredTip <public><localizes> :message = "Minimum number of teammates that must be in the zone together to activate buffs."
BuffTiersTip <public><localizes> :message = "Define buff tiers that activate when specific numbers of teammates are in the zone."
BuffActivationDelayTip <public><localizes> :message = "Time (in seconds) teammates must remain in the zone before buffs activate."
BuffDeactivationDelayTip <public><localizes> :message = "Time (in seconds) after leaving the zone before buffs are removed."
ContinuousBuffTriggerTip <public><localizes> :message = "If enabled, the buff output will trigger continuously at the specified interval while active."
BuffTriggerIntervalTip <public><localizes> :message = "Interval (in seconds) between continuous buff triggers when enabled."
TierStackingModeTip <public><localizes> :message = "SingleTier = only the highest tier is active at once (lower tiers deactivate). MultipleTiers = players can have multiple tiers active simultaneously."
RequireAllGroupMembersTip <public><localizes> :message = "If enabled, all members of a group must be in the zone to activate buffs."
AllowMultipleGroupsTip <public><localizes> :message = "If enabled, members from different groups standing together will count towards the threshold."
TierActivationModeTip <public><localizes> :message = "PlayerCount = activate based on number of players. TimeInZone = activate based on time spent in zone."
TeammateMilestoneCountTip <public><localizes> :message = "Number of teammates required to activate this buff tier (PlayerCount mode only)."
TimeRequiredTip <public><localizes> :message = "Time (in seconds) required to activate this buff tier (TimeInZone mode only)."
BuffActivatedOutputTip <public><localizes> :message = "Triggered when this buff tier activates. Passes the agents in the zone for custom buff logic."
BuffDeactivatedOutputTip <public><localizes> :message = "Triggered when this buff tier deactivates. Passes the agents that were in the zone."
ZoneEnteredOutputTip <public><localizes> :message = "Triggered whenever any agent enters the zone. Passes the entering agent."
ZoneExitedOutputTip <public><localizes> :message = "Triggered whenever any agent exits the zone. Passes the exiting agent."
VisualsDevicesTip <public><localizes> :message = "Visual effect powerup devices to pickup when this tier activates to show VFX."
ClearVisualsDeviceTip <public><localizes> :message = "Visual effect powerup device to pickup when clearing all VFX (use empty powerup). Shared universally across all zones and tiers."

# ======================================================
# ENUMS
# ======================================================

buff_mode := enum:
    SingleTrigger
    Continuous

tier_activation_mode := enum:
    PlayerCount
    TimeInZone

tier_stacking_mode := enum:
    SingleTier
    MultipleTiers

# ======================================================
# BUFF TIER CLASS
# ======================================================

buff_tier := class<concrete><unique>:
    
    # === EDITABLE PROPERTIES ===
    @editable { ToolTip := LabelTip } Label <public>: string = ""
    @editable { ToolTip := TierActivationModeTip } ActivationMode <public>: tier_activation_mode = tier_activation_mode.PlayerCount
    @editable { ToolTip := TeammateMilestoneCountTip } TeammateCount <public>: int = 2
    @editable { ToolTip := TimeRequiredTip } TimeRequired <public>: float = 5.0
    @editable { ToolTip := BuffActivatedOutputTip } ActivatedOutput <public>: trigger_device = trigger_device{}
    @editable { ToolTip := BuffDeactivatedOutputTip } DeactivatedOutput <public>: trigger_device = trigger_device{}
    @editable { ToolTip := VisualsDevicesTip } VisualsDevices <public>: []visual_effect_powerup_device = array{}
    
    # === INTERNAL STATE ===
    var ActiveForGroup : [int]logic = map{}
    var ActivationTime : [int]float = map{}
    var ActiveForAgent : [agent]logic = map{}
    
    # === BUFF TIER METHODS ===
    
    IsActive<public>(GroupIndex: int)<transacts>:logic=
        if (Active := ActiveForGroup[GroupIndex]). Active else. false
    
    IsActiveForAgent<public>(Agent: agent)<transacts>:logic=
        if (Active := ActiveForAgent[Agent]). Active else. false
    
    Activate<public>(GroupIndex: int, GroupAgents: []agent, Manager: team_buff_zone, ApplyVFX: logic):void=
        var WasActive : logic = IsActive(GroupIndex)
        if (WasActive = false):
            if (set ActiveForGroup[GroupIndex] = true){}
            if (set ActivationTime[GroupIndex] = GetSimulationElapsedTime()){}
        
        for (Agent : GroupAgents):
            var AgentWasActive : logic = IsActiveForAgent(Agent)
            if (AgentWasActive = false):
                if (set ActiveForAgent[Agent] = true){}
                ActivatedOutput.Trigger(Agent)
                
                if (ApplyVFX = true):
                    if (Player := player[Agent]):
                        for (VFXDevice : VisualsDevices):
                            VFXDevice.Pickup(Player)
                
                if (WasActive = false):
                    Manager.Logger("Buff tier '{Label}' activated for group {GroupIndex}", ?Name := "Buff Tier")
                else:
                    Manager.Logger("Buff tier '{Label}' activated for new agent in group {GroupIndex}", ?Name := "Buff Tier")
    
    Deactivate<public>(GroupIndex: int, GroupAgents: []agent, Manager: team_buff_zone):void=
        var WasActive : logic = IsActive(GroupIndex)
        if (WasActive = true):
            if (set ActiveForGroup[GroupIndex] = false){}
        
        var DeactivatedAnyAgent : logic = false
        for (Agent : GroupAgents):
            var AgentWasActive : logic = IsActiveForAgent(Agent)
            if (AgentWasActive = true):
                var NewAgentMap : [agent]logic = map{}
                for (Key -> Value : ActiveForAgent, Key <> Agent):
                    if (set NewAgentMap[Key] = Value){}
                set ActiveForAgent = NewAgentMap
                
                set DeactivatedAnyAgent = true
                DeactivatedOutput.Trigger(Agent)
                
                Manager.Logger("Buff tier '{Label}' deactivated for agent", ?Name := "Buff Tier")
        
        if (WasActive = true, DeactivatedAnyAgent = false):
            Manager.Logger("Buff tier '{Label}' marked inactive for group {GroupIndex}", ?Name := "Buff Tier")
    
    DeactivateForAgent<public>(Agent: agent, Manager: team_buff_zone, ClearDevice: ?visual_effect_powerup_device):void=
        var WasActive : logic = IsActiveForAgent(Agent)
        if (WasActive = true):
            var NewAgentMap : [agent]logic = map{}
            for (Key -> Value : ActiveForAgent, Key <> Agent):
                if (set NewAgentMap[Key] = Value){}
            set ActiveForAgent = NewAgentMap
            
            DeactivatedOutput.Trigger(Agent)
            
            if (Player := player[Agent]):
                if (Clear := ClearDevice?):
                    Clear.Pickup(Player)
            
            Manager.Logger("Buff tier '{Label}' deactivated for agent", ?Name := "Buff Tier")
    
    GetActiveDuration<public>(GroupIndex: int)<transacts>:float=
        if (StartTime := ActivationTime[GroupIndex]):
            return GetSimulationElapsedTime() - StartTime
        0.0

# ======================================================
# BUFF ZONE SETTINGS CLASS
# ======================================================

buff_zone_settings := class<concrete>:
    
    # === EDITABLE PROPERTIES ===
    @editable { ToolTip := MinTeammatesRequiredTip } MinTeammatesRequired <public>: int = 2
    @editable { ToolTip := BuffActivationDelayTip } ActivationDelay <public>: float = 0.0
    @editable { ToolTip := BuffDeactivationDelayTip } DeactivationDelay <public>: float = 0.0
    @editable { ToolTip := RequireAllGroupMembersTip } RequireAllGroupMembers <public>: logic = false
    @editable { ToolTip := AllowMultipleGroupsTip } AllowMultipleGroups <public>: logic = false
    @editable { ToolTip := TierStackingModeTip } TierStackingMode <public>: tier_stacking_mode = tier_stacking_mode.SingleTier
    @editable { ToolTip := ContinuousBuffTriggerTip } BuffMode <public>: buff_mode = buff_mode.SingleTrigger
    @editable { ToolTip := BuffTriggerIntervalTip } ContinuousInterval <public>: float = 1.0

# ======================================================
# ZONE TRACKER CLASS
# ======================================================

zone_tracker := class<concrete><unique>:
    
    # === EDITABLE PROPERTIES ===
    @editable { ToolTip := LabelTip } Label <public>: string = ""
    @editable { ToolTip := BuffZoneTip } Zone <public>: volume_device = volume_device{}
    @editable { ToolTip := BuffZoneSettingsTip } Settings <public>: buff_zone_settings = buff_zone_settings{}
    @editable { ToolTip := BuffTiersTip } BuffTiers <public>: []buff_tier = array{}
    @editable { ToolTip := ZoneEnteredOutputTip } ZoneEnteredOutput <public>: trigger_device = trigger_device{}
    @editable { ToolTip := ZoneExitedOutputTip } ZoneExitedOutput <public>: trigger_device = trigger_device{}
    
    # === INTERNAL STATE ===
    var MaybeManager : ?team_buff_zone = false
    var Index : int = -1
    var ClearDevice : ?visual_effect_powerup_device = false
    var AgentsInZone : []agent = array{}
    var GroupAgentsInZone : [int][]agent = map{}
    var PendingActivation : [int]logic = map{}
    var ActivationStartTime : [int]float = map{}
    var GroupZoneStartTime : [int]float = map{}
    var TimeBasedMonitorActive : [int]logic = map{}
    var ContinuousLoopActive : [int]logic = map{}
    
    # === INITIALIZATION ===
    
    Init<public>(Manager: team_buff_zone, ZoneIdx: int, ClearVFXDevice: ?visual_effect_powerup_device):void=
        set MaybeManager = option{Manager}
        set Index = ZoneIdx
        set ClearDevice = ClearVFXDevice
        
        Zone.AgentEntersEvent.Subscribe(OnAgentEntered)
        Zone.AgentExitsEvent.Subscribe(OnAgentExited)
        
        Manager.Logger("Initialized Zone Tracker: {Index}: {Label}", ?Name := "Zone Tracker")
    
    # === EVENT HANDLERS ===
    
    OnAgentEntered(Agent: agent):void=
        if (Manager := MaybeManager?):
            if (not AgentsInZone.Find[Agent]):
                set AgentsInZone += array{Agent}
                ZoneEnteredOutput.Trigger(Agent)
                
                if (Group := Manager.GetGroup[Agent]):
                    var CurrentGroupAgents : []agent = array{}
                    if (Agents := GroupAgentsInZone[Group.Index]):
                        set CurrentGroupAgents = Agents
                    
                    if (not CurrentGroupAgents.Find[Agent]):
                        set CurrentGroupAgents += array{Agent}
                        if (set GroupAgentsInZone[Group.Index] = CurrentGroupAgents){}
                    
                    Manager.Logger("Agent entered zone '{Label}' (Group {Group.Index}: {Group.Label})", ?Name := "Zone {Index}")
                    Manager.Logger("Group now has {CurrentGroupAgents.Length} agents in zone", ?Name := "Zone {Index}")
                    
                    var ShouldStartZone : logic = false
                    if (CurrentGroupAgents.Length >= Settings.MinTeammatesRequired):
                        if (not GroupZoneStartTime[Group.Index]):
                            if (set GroupZoneStartTime[Group.Index] = GetSimulationElapsedTime()){}
                            set ShouldStartZone = true
                            Manager.Logger("Group {Group.Index} started zone timer", ?Name := "Zone {Index}")
                    
                    if (ShouldStartZone = true):
                        spawn{CheckBuffActivation(Group.Index)}
                    else:
                        spawn{ReevaluateTiers(Group.Index)}
                    
                    if (Settings.BuffMode = buff_mode.Continuous):
                        var IsLoopRunning : logic = false
                        if (LoopActive := ContinuousLoopActive[Group.Index]):
                            set IsLoopRunning = LoopActive
                        
                        if (IsLoopRunning = false):
                            if (set ContinuousLoopActive[Group.Index] = true){}
                            spawn{RunContinuousLoop(Group.Index)}
    
    OnAgentExited(Agent: agent):void=
        if (Manager := MaybeManager?):
            if (AgentsInZone.Find[Agent]):
                set AgentsInZone = for (A : AgentsInZone, A <> Agent). A
                ZoneExitedOutput.Trigger(Agent)
                
                for (Tier : BuffTiers):
                    Tier.DeactivateForAgent(Agent, Manager, ClearDevice)
                
                if (Group := Manager.GetGroup[Agent]):
                    var CurrentGroupAgents : []agent = array{}
                    if (Agents := GroupAgentsInZone[Group.Index]):
                        set CurrentGroupAgents = Agents
                    
                    set CurrentGroupAgents = for (A : CurrentGroupAgents, A <> Agent). A
                    if (set GroupAgentsInZone[Group.Index] = CurrentGroupAgents){}
                    
                    Manager.Logger("Agent exited zone '{Label}' (Group {Group.Index}: {Group.Label})", ?Name := "Zone {Index}")
                    Manager.Logger("Group now has {CurrentGroupAgents.Length} agents in zone", ?Name := "Zone {Index}")
                    
                    if (CurrentGroupAgents.Length < Settings.MinTeammatesRequired):
                        var NewTimeMap : [int]float = map{}
                        for (Key -> Value : GroupZoneStartTime, Key <> Group.Index):
                            if (set NewTimeMap[Key] = Value){}
                        set GroupZoneStartTime = NewTimeMap
                        if (set TimeBasedMonitorActive[Group.Index] = false){}
                        Manager.Logger("Group {Group.Index} lost minimum players, reset zone timer", ?Name := "Zone {Index}")
                        spawn{CheckBuffDeactivation(Group.Index)}
                    else:
                        spawn{ReevaluateTiers(Group.Index)}
    
    # === BUFF ACTIVATION LOGIC ===
    
    ReevaluateTiers(GroupIndex: int)<suspends>:void=
        if (Manager := MaybeManager?):
            var AgentsInZoneForGroup : []agent = array{}
            if (Agents := GroupAgentsInZone[GroupIndex]):
                set AgentsInZoneForGroup = Agents
            
            var TimeInZone : float = 0.0
            if (StartTime := GroupZoneStartTime[GroupIndex]):
                set TimeInZone = GetSimulationElapsedTime() - StartTime
            
            var HighestQualifyingTier : ?buff_tier = false
            var HighestPriority : int = -1
            
            for (TierIdx -> Tier : BuffTiers):
                var QualifiesForTier : logic = false
                
                if (Tier.ActivationMode = tier_activation_mode.PlayerCount):
                    if (AgentsInZoneForGroup.Length >= Tier.TeammateCount):
                        set QualifiesForTier = true
                else if (Tier.ActivationMode = tier_activation_mode.TimeInZone):
                    if (TimeInZone >= Tier.TimeRequired):
                        set QualifiesForTier = true
                
                if (QualifiesForTier = true):
                    if (TierIdx > HighestPriority):
                        set HighestPriority = TierIdx
                        set HighestQualifyingTier = option{Tier}
            
            if (Settings.TierStackingMode = tier_stacking_mode.SingleTier):
                for (TierIdx -> Tier : BuffTiers):
                    if (QualifyingTier := HighestQualifyingTier?):
                        if (Tier = QualifyingTier):
                            Tier.Activate(GroupIndex, AgentsInZoneForGroup, Manager, true)
                        else:
                            Tier.Deactivate(GroupIndex, AgentsInZoneForGroup, Manager)
                    else:
                        Tier.Deactivate(GroupIndex, AgentsInZoneForGroup, Manager)
            else:
                for (TierIdx -> Tier : BuffTiers):
                    var QualifiesForTier : logic = false
                    
                    if (Tier.ActivationMode = tier_activation_mode.PlayerCount):
                        if (AgentsInZoneForGroup.Length >= Tier.TeammateCount):
                            set QualifiesForTier = true
                    else if (Tier.ActivationMode = tier_activation_mode.TimeInZone):
                        if (TimeInZone >= Tier.TimeRequired):
                            set QualifiesForTier = true
                    
                    var IsHighestTier : logic = false
                    if (QualifyingTier := HighestQualifyingTier?):
                        if (Tier = QualifyingTier):
                            set IsHighestTier = true
                    
                    if (QualifiesForTier = true):
                        Tier.Activate(GroupIndex, AgentsInZoneForGroup, Manager, IsHighestTier)
                    else:
                        Tier.Deactivate(GroupIndex, AgentsInZoneForGroup, Manager)
    
    CheckBuffActivation(GroupIndex: int)<suspends>:void=
        if (Manager := MaybeManager?):
            var AgentsCount : int = 0
            if (Agents := GroupAgentsInZone[GroupIndex]):
                set AgentsCount = Agents.Length
            
            if (AgentsCount >= Settings.MinTeammatesRequired):
                if (Settings.ActivationDelay > 0.0):
                    if (set PendingActivation[GroupIndex] = true){}
                    if (set ActivationStartTime[GroupIndex] = GetSimulationElapsedTime()){}
                    
                    Manager.Logger("Group {GroupIndex} activation pending ({Settings.ActivationDelay}s delay)", ?Name := "Zone {Index}")
                    
                    Sleep(Settings.ActivationDelay)
                    
                    if (IsPending := PendingActivation[GroupIndex], IsPending?):
                        var StillInZone : int = 0
                        if (CurrentAgents := GroupAgentsInZone[GroupIndex]):
                            set StillInZone = CurrentAgents.Length
                        
                        if (StillInZone >= Settings.MinTeammatesRequired):
                            ReevaluateTiers(GroupIndex)
                            
                            var HasTimeTiers : logic = HasTimeBasedTiers()
                            if (HasTimeTiers = true):
                                spawn{MonitorTimeBasedTiers(GroupIndex)}
                        else:
                            if (set PendingActivation[GroupIndex] = false){}
                            Manager.Logger("Group {GroupIndex} activation cancelled - teammates left zone", ?Name := "Zone {Index}")
                else:
                    ReevaluateTiers(GroupIndex)
                    
                    var HasTimeTiers : logic = HasTimeBasedTiers()
                    if (HasTimeTiers = true):
                        spawn{MonitorTimeBasedTiers(GroupIndex)}
    
    HasTimeBasedTiers<private>():logic=
        for (Tier : BuffTiers):
            if (Tier.ActivationMode = tier_activation_mode.TimeInZone):
                return true
        return false
    
    MonitorTimeBasedTiers(GroupIndex: int)<suspends>:void=
        if (Manager := MaybeManager?):
            if (set TimeBasedMonitorActive[GroupIndex] = true){}
            
            loop:
                Sleep(0.5)
                
                var IsMonitorActive : logic = false
                if (Active := TimeBasedMonitorActive[GroupIndex]):
                    set IsMonitorActive = Active
                
                if (IsMonitorActive = false):
                    break
                
                var AgentsCount : int = 0
                if (Agents := GroupAgentsInZone[GroupIndex]):
                    set AgentsCount = Agents.Length
                
                if (AgentsCount < Settings.MinTeammatesRequired):
                    if (set TimeBasedMonitorActive[GroupIndex] = false){}
                    break
                
                if (StartTime := GroupZoneStartTime[GroupIndex]):
                    TimeInZone := GetSimulationElapsedTime() - StartTime
                    ReevaluateTiers(GroupIndex)
    
    CheckBuffDeactivation(GroupIndex: int)<suspends>:void=
        if (Manager := MaybeManager?):
            if (set PendingActivation[GroupIndex] = false){}
            
            if (Settings.DeactivationDelay > 0.0):
                Sleep(Settings.DeactivationDelay)
            
            var AgentsCount : int = 0
            if (Agents := GroupAgentsInZone[GroupIndex]):
                set AgentsCount = Agents.Length
            
            if (AgentsCount < Settings.MinTeammatesRequired):
                DeactivateAllBuffs(GroupIndex)
            else:
                ReevaluateTiers(GroupIndex)
    
    DeactivateAllBuffs(GroupIndex: int):void=
        if (Manager := MaybeManager?):
            if (set ContinuousLoopActive[GroupIndex] = false){}
            if (set TimeBasedMonitorActive[GroupIndex] = false){}
            
            var AgentsInZoneForGroup : []agent = array{}
            if (Agents := GroupAgentsInZone[GroupIndex]):
                set AgentsInZoneForGroup = Agents
            
            for (Tier : BuffTiers):
                Tier.Deactivate(GroupIndex, AgentsInZoneForGroup, Manager)
            
            if (ClearVFX := ClearDevice?):
                for (Agent : AgentsInZoneForGroup):
                    if (Player := player[Agent]):
                        ClearVFX.Pickup(Player)
    
    RunContinuousLoop(GroupIndex: int)<suspends>:void=
        if (Manager := MaybeManager?):
            loop:
                Sleep(Settings.ContinuousInterval)
                
                var IsLoopActive : logic = false
                if (LoopActive := ContinuousLoopActive[GroupIndex]):
                    set IsLoopActive = LoopActive
                
                if (IsLoopActive = false):
                    break
                
                if (Agents := GroupAgentsInZone[GroupIndex]):
                    for (Tier : BuffTiers):
                        var IsTierActive : logic = Tier.IsActive(GroupIndex)
                        if (IsTierActive = true):
                            for (Agent : Agents):
                                Tier.ActivatedOutput.Trigger(Agent)
                            
                            Manager.Logger("Continuous buff triggered for group {GroupIndex} (Tier: {Tier.Label})", ?Name := "Zone {Index}")
    
    # === CLEANUP ===
    
    OnGroupMemberLeft<public>(Agent: agent):void=
        if (AgentsInZone.Find[Agent]):
            OnAgentExited(Agent)

# ======================================================
# TEAM BUFF ZONE DEVICE
# ======================================================

team_buff_zone := class(Core.base_group_device):
    
    # === EDITABLE PROPERTIES ===
    @editable Zones <public>: []zone_tracker = array{}
    @editable { ToolTip := ClearVisualsDeviceTip } ClearVisualsDevice <public>: ?visual_effect_powerup_device = false
    
    # === CONFIGURATION ===
    LOGGER_NAME <override>: string = "Team Buff Zone"
    
    # === INITIALIZATION ===
    
    Initialize<override>()<suspends>:void=
        for (Idx -> Zone : Zones):
            Zone.Init(Self, Idx, ClearVisualsDevice)
        
        Logger("Initialized with {Zones.Length} zone(s)")
    
    # === LIFECYCLE EVENTS ===  
    
    OnAgentJoined<override>(Agent: agent):void=
        Logger("Agent joined game")
    
    OnAgentRespawned<override>(Agent: agent):void=
        Logger("Agent respawned")
    
    OnAgentLeft<override>(Agent: agent):void=
        for (Zone : Zones):
            Zone.OnGroupMemberLeft(Agent)
        
        Logger("Agent left game")
