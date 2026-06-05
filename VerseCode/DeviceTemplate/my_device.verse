# Replace "my_device" with your device name throughout this file
using { /Fortnite.com/Devices }
using { /Verse.org/Simulation }
using { /UnrealEngine.com/Temporary/Diagnostics }

# TODO: Update the module path to match your device folder name
my_device_module := module:
    my_device<public> := class(base_group_device):
        # ---- Editable properties ----
        @editable @tooltip("Example property — replace with your own")
        ExampleProperty<public> : int = 10

        # ---- Lifecycle hooks ----
        # Called once when the device starts (or when InitTrigger fires)
        Initialize<override>()<suspends> : void =
            Logger().Print("my_device initialized")
            # TODO: your setup logic here

        # Called when a player joins the group
        OnAgentJoined<override>(Agent : agent) : void =
            Logger().Print("Player joined: {Agent}")
            # TODO: your per-player join logic here

        # Called when a player respawns
        OnAgentRespawned<override>(Agent : agent) : void =
            # TODO: your respawn logic here

        # Called when a player leaves the group
        OnAgentLeft<override>(Agent : agent) : void =
            # TODO: your leave logic here
