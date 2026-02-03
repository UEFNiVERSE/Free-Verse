#██╗   ██╗███████╗███████╗███╗   ██╗██╗██╗   ██╗███████╗██████╗ ███████╗███████╗
#██║   ██║██╔════╝██╔════╝████╗  ██║██║██║   ██║██╔════╝██╔══██╗██╔════╝██╔════╝
#██║   ██║█████╗  █████╗  ██╔██╗ ██║██║██║   ██║█████╗  ██████╔╝███████╗█████╗  
#██║   ██║██╔══╝  ██╔══╝  ██║╚██╗██║██║╚██╗ ██╔╝██╔══╝  ██╔══██╗╚════██║██╔══╝  
#╚██████╔╝███████╗██║     ██║ ╚████║██║ ╚████╔╝ ███████╗██║  ██║███████║███████╗
# ╚═════╝ ╚══════╝╚═╝     ╚═╝  ╚═══╝╚═╝  ╚═══╝  ╚══════╝╚═╝  ╚═╝╚══════╝╚══════╝

# ======================================================
# IMPORTS
# ======================================================

using { /Verse.org/Simulation }

# ======================================================
# SAVED DATA MODULE
# ======================================================

Saved_Data <public> := module:

    # === MODULE CONSTANTS ===

    VERSION <internal> : int = 0

    # === INTERNAL STATE ===

    var InternalTrackerData <internal> : weak_map(player, tracker_persistence_data) = map{}

    # ======================================================
    # DATA CLASSES
    # ======================================================

    tracker_progress_entry <public> := class<final><persistable><concrete>:
        Progress <public> : int = 0
        GroupIndex <public> : int = -1

    tracker_persistence_data <public> := class<final><persistable><concrete>:
        Version <public> : int = 0
        TrackerProgress <public> : []tracker_progress_entry = array{}

    # ======================================================
    # CONSTRUCTOR FUNCTIONS
    # ======================================================

    BuildTrackerData<internal><constructor>(OldData:tracker_persistence_data)<transacts>:=
        tracker_persistence_data:
            Version := OldData.Version
            TrackerProgress := OldData.TrackerProgress

    # ======================================================
    # INITIALIZATION FUNCTIONS
    # ======================================================

    NeedsTrackerData<public>(ActivePlayer:player)<transacts><decides>:void=
        ActivePlayer.IsActive[]
        not InternalTrackerData[ActivePlayer]

    InitializeTrackerData<public>(Player:player)<transacts><decides>:void=  
        Player.IsActive[]
        SaveData := tracker_persistence_data{}
        UploadTrackerData[Player, SaveData]

    # ======================================================
    # SAVE / LOAD FUNCTIONS
    # ======================================================

    UploadTrackerData<public>(Player:player, SaveData:tracker_persistence_data)<transacts><decides>:tracker_persistence_data=
        FitsInPlayerMap[SaveData]
        Player.IsActive[]
        set InternalTrackerData[Player] = SaveData
        return SaveData

    GlobalTrackerData<public>(Player:player)<transacts><decides>:tracker_persistence_data=
        Player.IsActive[]
        SaveData := InternalTrackerData[Player]
        return SaveData

    SaveTrackerProgress<public>(Player:player, TrackerIndex:int, NewProgress:int, GroupIndex:int)<transacts><decides>:void=
        CurrentSaveData := GlobalTrackerData[Player]
        var UpdatedProgress : []tracker_progress_entry = CurrentSaveData.TrackerProgress
        
        if(TrackerIndex >= UpdatedProgress.Length):
            var PaddingNeeded : int = (TrackerIndex + 1) - UpdatedProgress.Length
            for(I := 0..PaddingNeeded - 1):
                set UpdatedProgress += array{tracker_progress_entry{}}
        
        if(TrackerIndex >= 0, TrackerIndex < UpdatedProgress.Length):
            NewEntry := tracker_progress_entry{Progress := NewProgress, GroupIndex := GroupIndex}
            if(ReplacedArray := UpdatedProgress.ReplaceElement[TrackerIndex, NewEntry]):
                set UpdatedProgress = ReplacedArray
        
        NewSaveData := tracker_persistence_data:
            TrackerProgress := UpdatedProgress
            BuildTrackerData<constructor>(CurrentSaveData)
        
        SavedData := UploadTrackerData[Player, NewSaveData]

    GetTrackerProgressData<public>(Player:player, TrackerIndex:int)<transacts><decides>:tracker_progress_entry=
        CurrentSaveData := GlobalTrackerData[Player]
        var Result : tracker_progress_entry = tracker_progress_entry{}
        if(TrackerIndex >= 0, TrackerIndex < CurrentSaveData.TrackerProgress.Length):
            if(Entry := CurrentSaveData.TrackerProgress[TrackerIndex]):
                set Result = Entry
        Result

    # ======================================================
    # RESET FUNCTIONS
    # ======================================================

    ResetTrackerProgress<public>(Player:player, TrackerIndex:int)<transacts><decides>:void=
        CurrentSaveData := GlobalTrackerData[Player]
        var UpdatedProgress : []tracker_progress_entry = CurrentSaveData.TrackerProgress
        
        if(TrackerIndex >= 0, TrackerIndex < UpdatedProgress.Length):
            ResetEntry := tracker_progress_entry{}
            if(ReplacedArray := UpdatedProgress.ReplaceElement[TrackerIndex, ResetEntry]):
                set UpdatedProgress = ReplacedArray
            
                NewSaveData := tracker_persistence_data:
                    TrackerProgress := UpdatedProgress
                    BuildTrackerData<constructor>(CurrentSaveData)
                
                SavedData := UploadTrackerData[Player, NewSaveData]

    ResetAllTrackerData<public>(Player:player)<transacts><decides>:void=
        Player.IsActive[]
        FreshData := tracker_persistence_data{}
        UploadTrackerData[Player, FreshData]
