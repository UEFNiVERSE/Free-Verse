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
using { Saved_Data }

# ======================================================
# TOOLTIPS
# ======================================================

GroupTrackerTip <public><localizes> :message = "Custom Trackers that keep track of progress across player groups."
TrackerProgressTip <public><localizes> :message = "The progress settings for this tracker."
MilestoneRewardsTip <public><localizes> :message = "The rewards given when certain milestones are reached."
ProgressGoalTip <public><localizes> :message = "The target goal for this progress tracker."
ProgressChangeAmountTip <public><localizes> :message = "The amount to increment or decrement the progress by when triggered."
ProgressIncrementTip <public><localizes> :message = "The trigger device that will increment the progress when activated."
ProgressDecrementTip <public><localizes> :message = "The trigger device that will decrement the progress when activated."
ProgressCompleteOutputTip <public><localizes> :message = "The trigger device that will activate when the progress goal is reached. Does not pass along any agents."
ProgressResetOnLeaveTip <public><localizes> :message = "If enabled, the agent's progress will be removed from their groups total when they leave the game. WARNING: Do not enable with persistence - it will conflict with saved progress."
PersistenceScopeTip <public><localizes> :message = "None = No persistence. PlayerGroup = Progress only loads when rejoining the same group. PerPlayer = Progress loads into any group (player can switch groups)."
IsRepeatableTip <public><localizes> :message = "If enabled, when the tracker reaches its goal it will reset progress and clear saved data, allowing players to complete it again for rewards."
BackendTrackerTip <public><localizes> :message = "Optional tracker to increment on tracker events. Separate from Visual Tracker."
MilestoneGoalRatioTip <public><localizes> :message = "The % amount of goal that is needed to reach this milestone reward."
MilestoneOutputTrigger <public><localizes> :message = "The trigger device that will activate when this milestone is reached. Plug your rewards into its on triggered event. (Passes along the Agent(s) in the group.)"
VisualTrackerTip <public><localizes> :message = "Optional tracker device to display progress to players visually. Add a title and description in the tracker device settings or use a HUD widget. Verse will update the progress values automatically."

# ======================================================
# ENUMS
# ======================================================

milestone_type := enum { Group, Player }

persistence_scope := enum:
    None
    PlayerGroup
    PerPlayer

# ======================================================
# MILESTONE REWARDS CLASS
# ======================================================

milestone_rewards := class<concrete><unique>:
    @editable Type : milestone_type = milestone_type.Group
    @editable_slider(float):
        ToolTip := MilestoneGoalRatioTip
        MinValue := option. 0.0
        MaxValue := option. 1.0
    GoalRatio <public>: float = 0.5
    @editable { ToolTip := MilestoneOutputTrigger } OutputTrigger <public>: trigger_device = trigger_device{}
    var AgentsAwardedPerGroup : [int][]agent = map{}

    Award(GroupIndex : int, Agent: agent):void=
        var Awarded : []agent = array{}
        if(AgentsAwarded := AgentsAwardedPerGroup[GroupIndex]). set Awarded = AgentsAwarded

        if(Awarded.Find[Agent]){}
        else:
            set Awarded += array. Agent
            OutputTrigger.Trigger(Agent)

        option. set AgentsAwardedPerGroup[GroupIndex] = Awarded

    Award(GroupIndex : int, AgentList : []agent):void=
        var Awarded : []agent = array{}
        if(AgentsAwarded := AgentsAwardedPerGroup[GroupIndex]). set Awarded = AgentsAwarded

        for (Agent : AgentList):
            if(Awarded.Find[Agent]){}
            else:
                set Awarded += array. Agent
                OutputTrigger.Trigger(Agent)

        option. set AgentsAwardedPerGroup[GroupIndex] = Awarded

# ======================================================
# TRACKER PROGRESS CLASS
# ======================================================

tracker_progress := class<concrete>:
    @editable { ToolTip := ProgressGoalTip } Goal <public>: int = 10
    @editable { ToolTip := ProgressChangeAmountTip } ChangeAmount <public>: int = 1
    
    @editable { ToolTip := ProgressIncrementTip } IncrementTrigger <public>: ?trigger_device = false
    @editable { ToolTip := ProgressDecrementTip } DecrementTrigger <public>: ?trigger_device = false
    @editable { ToolTip := BackendTrackerTip } BackendTracker <public>: ?tracker_device = false
    
    @editable { ToolTip := ProgressCompleteOutputTip } CompletedOutputTrigger <public>: trigger_device = trigger_device{}
    
    @editable { ToolTip := IsRepeatableTip } IsRepeatable <public>: logic = false
    @editable { ToolTip := ProgressResetOnLeaveTip } ResetAgentProgessOnLeave <public>: logic = false
    @editable { ToolTip := PersistenceScopeTip } PersistenceScope <public>: persistence_scope = persistence_scope.None

# ======================================================
# GROUP TRACKER CLASS
# ======================================================

group_tracker := class<concrete><unique>:
    
    # === EDITABLE PROPERTIES ===
    @editable { ToolTip := LabelTip } Label <public>: string = ""
    @editable { ToolTip := TrackerProgressTip } Progress <public>: tracker_progress = tracker_progress{}
    @editable { ToolTip := MilestoneRewardsTip } MilestoneRewards <public>: []milestone_rewards = array{}
    @editable { ToolTip := VisualTrackerTip } VisualTracker <public>: ?tracker_device = false
    
    # === INTERNAL STATE ===
    var MaybeManager : ?shared_progress_tracker = false
    var Index : int = -1
    var ProgressByAgent <public>: [agent]int = map{}
    var ProgressByGroup <public>: [int]int = map{}
    var GroupHasCompleted : [int]logic = map{}
    var PlayerGroupIndex : [agent]int = map{}
    var LastSaveTime : [agent]float = map{}
    var LastTrackerValue : [agent]int = map{}
    var TrackerPollActive : [agent]logic = map{}
    SaveThrottleSeconds : float = 5.0

    # === INITIALIZATION ===

    Init(Manager : shared_progress_tracker, TrackerIdx : int, PlayerGroups : []player_group):void=
        set MaybeManager = option. Manager
        set Index = TrackerIdx
        
        if(IncrementTrig := Progress.IncrementTrigger?):
            IncrementTrig.TriggeredEvent.Subscribe(OnIncrementTriggered)
        
        if(DecrementTrig := Progress.DecrementTrigger?):
            DecrementTrig.TriggeredEvent.Subscribe(OnDecrementTriggered)
        
        if (Tracker := VisualTracker?). Tracker.SetTarget(Progress.Goal)
        
        for (Group : PlayerGroups):
            Group.AssignTrigger.TriggeredEvent.Subscribe(OnGroupAssignment)

    # === EVENT HANDLERS ===

    OnGroupAssignment(MaybeAgent : ?agent):void=
        if(Agent := MaybeAgent?):
            spawn{LoadProgress(Agent)}
            if(Progress.BackendTracker?):
                spawn{StartTrackerPolling(Agent)}

    LoadProgress(Agent: agent)<suspends>:void=
        Sleep(0.2)
        if(Manager := MaybeManager?):
            if(Group := Manager.GetGroup[Agent]):
                if(set PlayerGroupIndex[Agent] = Group.Index){}
        LoadPlayerProgress(Agent)

    OnIncrementTriggered(MaybeAgent : ?agent):void=
        if(Manager := MaybeManager?, Agent := MaybeAgent?):
            if(BackendTracker := Progress.BackendTracker?):
                CurrentValue := BackendTracker.GetValue(Agent)
                BackendTracker.SetValue(Agent, CurrentValue + Progress.ChangeAmount)
            else:
                if(Group := Manager.GetGroup[Agent]). Group.Increment(Agent)
                else. Manager.Logger("Agent not in any group, cannot increment progress.", ?Name := "Tracker {Index}: {Label}")

    OnDecrementTriggered(MaybeAgent : ?agent):void=
        if(Manager := MaybeManager?, Agent := MaybeAgent?):
            if(BackendTracker := Progress.BackendTracker?):
                CurrentValue := BackendTracker.GetValue(Agent)
                NewValue := Max(CurrentValue - Progress.ChangeAmount, 0)
                BackendTracker.SetValue(Agent, NewValue)
            else:
                if(Group := Manager.GetGroup[Agent]). Group.Decrement(Agent)
                else. Manager.Logger("Agent not in any group, cannot decrement progress.", ?Name := "Tracker {Index}: {Label}")

    # === PROGRESS GETTERS / SETTERS ===

    (Agent: agent).GetProgress<public>()<transacts><decides>:int= ProgressByAgent[Agent]
    (Agent: agent).SetProgress<public>(NewProgress: int)<transacts><decides>:void= set ProgressByAgent[Agent] = Max(Min(NewProgress, Progress.Goal), 0)

    (Group : player_group).GetProgress<public>()<transacts><decides>:int= ProgressByGroup[Group.Index]
    (Group : player_group).SetProgress<public>(NewProgress: int)<transacts><decides>:void= set ProgressByGroup[Group.Index] = Max(Min(NewProgress, Progress.Goal), 0)

    # === PERSISTENCE METHODS ===

    ShouldSaveProgress(Agent: agent)<transacts>:logic=
        CurrentTime := GetSimulationElapsedTime()
        var LastSave : float = 0.0
        if(Last := LastSaveTime[Agent]):
            set LastSave = Last
        
        TimeSinceLastSave := CurrentTime - LastSave
        if(TimeSinceLastSave >= SaveThrottleSeconds):
            return true
        return false

    SaveProgressThrottled(Agent: agent, NewProgress: int):void=
        if(Progress.PersistenceScope = persistence_scope.None):
            return
        
        if(Player := player[Agent]):
            var ShouldSave : logic = false
            if(ShouldSaveProgress(Agent)?):
                set ShouldSave = true
            
            if(ShouldSave?):
                var GroupIdx : int = -1
                if(GIdx := PlayerGroupIndex[Agent]):
                    set GroupIdx = GIdx
                
                var SaveSucceeded : logic = false
                block:
                    if:
                        Saved_Data.SaveTrackerProgress[Player, Index, NewProgress, GroupIdx]
                    then:
                        set SaveSucceeded = true
                
                if(SaveSucceeded?):
                    CurrentTime := GetSimulationElapsedTime()
                    if(set LastSaveTime[Agent] = CurrentTime){}
                    if(Manager := MaybeManager?):
                        Manager.Logger("Saved progress: {NewProgress} for Group: {GroupIdx}", ?Name := "Tracker {Index}: {Label}")

    LoadPlayerProgress<public>(Agent: agent):void=
        if(Progress.PersistenceScope = persistence_scope.None):
            return
        
        if(Player := player[Agent], Manager := MaybeManager?):
            block:
                if:
                    Saved_Data.NeedsTrackerData[Player]
                    Saved_Data.InitializeTrackerData[Player]
                then:
                    Manager.Logger("Initialized tracker data", ?Name := "Tracker {Index}: {Label}")
            
            var SavedProgress : int = 0
            var SavedGroupIndex : int = -1
            
            if(SavedData := Saved_Data.GetTrackerProgressData[Player, Index]):
                set SavedProgress = SavedData.Progress
                set SavedGroupIndex = SavedData.GroupIndex
            
            if(SavedProgress > 0):
                var ShouldLoadProgress : logic = false
                
                if(Progress.PersistenceScope = persistence_scope.PerPlayer):
                    set ShouldLoadProgress = true
                    Manager.Logger("PerPlayer mode: Will load {SavedProgress} into any group", ?Name := "Tracker {Index}: {Label}")
                else if(Progress.PersistenceScope = persistence_scope.PlayerGroup):
                    if(CurrentGroupIndex := PlayerGroupIndex[Agent]):
                        Manager.Logger("PlayerGroup mode: Current group {CurrentGroupIndex}, Saved group {SavedGroupIndex}", ?Name := "Tracker {Index}: {Label}")
                        if(SavedGroupIndex = CurrentGroupIndex):
                            set ShouldLoadProgress = true
                            Manager.Logger("Groups match, will load progress", ?Name := "Tracker {Index}: {Label}")
                
                if(ShouldLoadProgress = true):
                    option. Agent.SetProgress[SavedProgress]
                    
                    if(Group := Manager.GetGroup[Agent]):
                        var CurrentGroupProgress : int = 0
                        if (Prog := Group.GetProgress[]). set CurrentGroupProgress = Prog
                        
                        NewGroupProgress := CurrentGroupProgress + SavedProgress
                        option. Group.SetProgress[NewGroupProgress]
                        
                        if(Tracker := VisualTracker?):
                            for(GroupAgent : Group.GroupAgents):
                                Tracker.SetValue(GroupAgent, NewGroupProgress)
                        
                        Manager.Logger("Loaded player progress: {SavedProgress}, added to group {Group.Index} (Group total now: {NewGroupProgress})", ?Name := "Tracker {Index}: {Label}")
                    else:
                        Manager.Logger("Failed to load: Agent not in a group yet", ?Name := "Tracker {Index}: {Label}")

    ForceSaveProgress(Agent: agent):void=
        if(Progress.PersistenceScope = persistence_scope.None):
            return
        
        if(Player := player[Agent]):
            if(CurrentProgress := Agent.GetProgress[]):
                var GroupIdx : int = -1
                if(GIdx := PlayerGroupIndex[Agent]):
                    set GroupIdx = GIdx
                
                block:
                    if:
                        Saved_Data.SaveTrackerProgress[Player, Index, CurrentProgress, GroupIdx]
                    then:
                        if(Manager := MaybeManager?):
                            Manager.Logger("Force saved progress on leave: {CurrentProgress} for Group: {GroupIdx}", ?Name := "Tracker {Index}: {Label}")

    StartTrackerPolling(Agent: agent)<suspends>:void=
        if(BackendTracker := Progress.BackendTracker?):
            if(set TrackerPollActive[Agent] = true){}
            
            BackendTracker.Assign(Agent)
            CurrentValue := BackendTracker.GetValue(Agent)
            if(set LastTrackerValue[Agent] = CurrentValue){}
            
            if(Manager := MaybeManager?):
                Manager.Logger("Started polling backend tracker for agent, initial value: {CurrentValue}", ?Name := "Tracker {Index}: {Label}")
            
            loop:
                Sleep(1.0)
                
                if(Active := TrackerPollActive[Agent]):
                    if(not Active?):
                        break
                else:
                    break
                
                NewValue := BackendTracker.GetValue(Agent)
                var OldValue : int = 0
                if(Last := LastTrackerValue[Agent]):
                    set OldValue = Last
                
                if(NewValue > OldValue):
                    Delta := NewValue - OldValue
                    if(set LastTrackerValue[Agent] = NewValue){}
                    
                    if(Manager := MaybeManager?):
                        Manager.Logger("Backend tracker increased by {Delta} (Old: {OldValue}, New: {NewValue})", ?Name := "Tracker {Index}: {Label}")
                        if(Group := Manager.GetGroup[Agent]):
                            for(I := 1..Delta):
                                Group.Increment(Agent)
                        else:
                            Manager.Logger("Agent not in a group, cannot increment from backend tracker", ?Name := "Tracker {Index}: {Label}")

    # === PROGRESS INCREMENT / DECREMENT ===

    (Group : player_group).Increment<public>(Agent: agent):void=
        if(Manager := MaybeManager?):
            var CurrentAgentProgress : int = 0
            var CurrentGroupProgress : int = 0

            if (Prog := Agent.GetProgress[]). set CurrentAgentProgress = Prog
            if (Prog := Group.GetProgress[]). set CurrentGroupProgress = Prog
            
            var WasAlreadyComplete : logic = false
            if(HasCompleted := GroupHasCompleted[Group.Index]):
                set WasAlreadyComplete = HasCompleted
            
            NewAgentProgress := CurrentAgentProgress + Progress.ChangeAmount
            NewGroupProgress := CurrentGroupProgress + Progress.ChangeAmount

            option. Agent.SetProgress[NewAgentProgress]
            option. Group.SetProgress[NewGroupProgress]
                
            if(Tracker := VisualTracker?):
                for(GroupAgent : Group.GroupAgents):
                    Tracker.SetValue(GroupAgent, NewGroupProgress)

            if(WasAlreadyComplete = false):
                if(NewGroupProgress >= Progress.Goal):
                    if(set GroupHasCompleted[Group.Index] = true){}
                    
                    Progress.CompletedOutputTrigger.Trigger()
                    
                    if(Progress.IsRepeatable?):
                        spawn{ResetTrackerForRepeat(Group, Agent)}
                
                CheckGroupMilestones(NewGroupProgress, Group)
                CheckPlayerMilestones(NewAgentProgress, Group, Agent)

            SaveProgressThrottled(Agent, NewAgentProgress)

            Manager.Logger("Agent incremented progress in Group {Group.Index}: {Group.Label}.", ?Name := "Tracker {Index}: {Label}")
            Manager.Logger("Agent - Before: {CurrentAgentProgress}, After: {NewAgentProgress}", ?Name := "Tracker {Index}: {Label}")
            Manager.Logger("Group - Before: {CurrentGroupProgress}, After: {NewGroupProgress}", ?Name := "Tracker {Index}: {Label}")

    (Group : player_group).Decrement<public>(Agent: agent):void=
        if(Manager := MaybeManager?):
            var CurrentAgentProgress : int = 0
            var CurrentGroupProgress : int = 0

            if (Prog := Agent.GetProgress[]). set CurrentAgentProgress = Prog
            if (Prog := Group.GetProgress[]). set CurrentGroupProgress = Prog
            
            NewAgentProgress := CurrentAgentProgress - Progress.ChangeAmount
            NewGroupProgress := CurrentGroupProgress - Progress.ChangeAmount

            option. Agent.SetProgress[NewAgentProgress]
            option. Group.SetProgress[NewGroupProgress]

            if(Tracker := VisualTracker?):
                for(GroupAgent : Group.GroupAgents):
                    Tracker.SetValue(GroupAgent, NewGroupProgress)

            SaveProgressThrottled(Agent, NewAgentProgress)

            Manager.Logger("Agent decremented progress in Group {Index}: {Group.Label}.", ?Name := "Tracker {Index}: {Label}")
            Manager.Logger("Agent - Before: {CurrentAgentProgress}, After: {NewAgentProgress}", ?Name := "Tracker {Index}: {Label}")
            Manager.Logger("Group - Before: {CurrentGroupProgress}, After: {NewGroupProgress}", ?Name := "Tracker {Index}: {Label}")

    # === MILESTONE CHECKING ===

    CheckGroupMilestones(NewProgress : int, Group : player_group):void=
        if(Manager := MaybeManager?):
            for:
                Milestone : MilestoneRewards
                Milestone.Type = milestone_type.Group
                NewProgress * 1.0 >= (Progress.Goal * Milestone.GoalRatio)
            do:
                Milestone.Award(Group.Index, Group.GroupAgents)
                Manager.Logger("Group {Group.Index}: {Group.Label} reached milestone at {Milestone.GoalRatio*100}% progress.", ?Name := "Tracker {Index}: {Label}")

    CheckPlayerMilestones(NewProgress : int, Group : player_group, Agent : agent):void=
        if(Manager := MaybeManager?):
            for:
                Milestone : MilestoneRewards
                Milestone.Type = milestone_type.Player
                NewProgress * 1.0 >= (Progress.Goal * Milestone.GoalRatio)
            do:
                Milestone.Award(Group.Index, Agent)
                Manager.Logger("Agent in Group {Group.Index}: {Group.Label} reached milestone at {Milestone.GoalRatio*100}% progress.", ?Name := "Tracker {Index}: {Label}")

    # === PLAYER LEAVE HANDLING ===

    ResetTrackerForRepeat(Group : player_group, CompletingAgent : agent)<suspends>:void=
        Sleep(0.1)
        
        if(Manager := MaybeManager?):
            Manager.Logger("Tracker completed and is repeatable, resetting progress for all agents in group", ?Name := "Tracker {Index}: {Label}")
            
            for(Agent : Group.GroupAgents):
                option. Agent.SetProgress[0]
                
                if(Player := player[Agent]):
                    block:
                        if:
                            Saved_Data.ResetTrackerProgress[Player, Index]
                        then:
                            Manager.Logger("Cleared saved data for agent", ?Name := "Tracker {Index}: {Label}")
                
                if(BackendTracker := Progress.BackendTracker?):
                    BackendTracker.SetValue(Agent, 0)
                    if(set LastTrackerValue[Agent] = 0){}
            
            option. Group.SetProgress[0]
            
            if(set GroupHasCompleted[Group.Index] = false){}
            
            if(Tracker := VisualTracker?):
                for(Agent : Group.GroupAgents):
                    Tracker.SetValue(Agent, 0)
            
            Manager.Logger("Tracker reset complete, ready for next cycle", ?Name := "Tracker {Index}: {Label}")

    StopTrackerPolling(Agent: agent):void=
        if(set TrackerPollActive[Agent] = false){}

    DecrementAgentFromGroup(Agent : agent, Group : player_group):void=
        if(Manager := MaybeManager?):
            var CurrentAgentProgress : int = 0
            var CurrentGroupProgress : int = 0

            if (Prog := Agent.GetProgress[]). set CurrentAgentProgress = Prog
            if (Prog := Group.GetProgress[]). set CurrentGroupProgress = Prog
            
            NewGroupProgress := CurrentGroupProgress - CurrentAgentProgress
            option. Group.SetProgress[NewGroupProgress]

            Manager.Logger("Agent left the game, decrementing their progress from Group {Group.Index}: {Group.Label}.", ?Name := "Tracker {Index}: {Label}")
            Manager.Logger("Group - Before: {CurrentGroupProgress}, After: {NewGroupProgress}", ?Name := "Tracker {Index}: {Label}")

# ======================================================
# SHARED PROGRESS TRACKER DEVICE
# ======================================================

shared_progress_tracker := class(Core.base_group_device):
    
    # === EDITABLE PROPERTIES ===
    @editable { ToolTip := GroupTrackerTip } Trackers <public>: []group_tracker = array{}

    # === CONFIGURATION ===
    LOGGER_NAME <override>: string = "Shared Progress Tracker"

    # === INITIALIZATION ===

    Initialize<override>()<suspends>:void=
        PlayerGroups := GetGroups()
        for (Idx -> Tracker : Trackers). Tracker.Init(Self, Idx, PlayerGroups)

    # === LIFECYCLE EVENTS ===

    OnAgentJoined<override>(Agent : agent):void={}
    OnAgentRespawned<override>(Agent : agent):void={}

    OnAgentLeft<override>(Agent : agent):void=
        for(Tracker : Trackers):
            Tracker.StopTrackerPolling(Agent)
            Tracker.ForceSaveProgress(Agent)
        
        for:
            Tracker : Trackers
            Tracker.Progress.ResetAgentProgessOnLeave?
            Group := GetGroup[Agent]
        do. Tracker.DecrementAgentFromGroup(Agent, Group)
