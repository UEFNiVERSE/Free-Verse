#██╗   ██╗███████╗███████╗███╗   ██╗██╗██╗   ██╗███████╗██████╗ ███████╗███████╗
#██║   ██║██╔════╝██╔════╝████╗  ██║██║██║   ██║██╔════╝██╔══██╗██╔════╝██╔════╝
#██║   ██║█████╗  █████╗  ██╔██╗ ██║██║██║   ██║█████╗  ██████╔╝███████╗█████╗
#██║   ██║██╔══╝  ██╔══╝  ██║╚██╗██║██║╚██╗ ██╔╝██╔══╝  ██╔══██╗╚════██║██╔══╝
#╚██████╔╝███████╗██║     ██║ ╚████║██║ ╚████╔╝ ███████╗██║  ██║███████║███████╗
# ╚═════╝ ╚══════╝╚═╝     ╚═╝  ╚═══╝╚═╝  ╚═══╝  ╚══════╝╚═╝  ╚═╝╚══════╝╚══════╝

# ======================================================
# FILE: my_device.verse
# ------------------------------------------------------
# Starting point for a new UEFNiVERSE device. Replace
# "my_device" with your device name throughout, rename
# the folder and this file to match, and add the folder
# to module_access.verse.
#
# This template extends `base_group_device`, which adds
# the player group layer. If your device does not need
# groups, extend `Core.base_device` instead and drop the
# Groups property from your setup.
# ======================================================

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
# Tooltips are localized messages declared at file scope, then referenced
# from @editable properties. Core already provides LabelTip and DebugTip.

ExamplePropertyTip <public><localizes> :message = "Replace this with a description of your own property."

# ======================================================
# MY DEVICE
# ======================================================

my_device := class(Core.base_group_device):

    # === EDITABLE PROPERTIES ===
    @editable { ToolTip := ExamplePropertyTip } ExampleProperty <public>: int = 10

    # === CONFIGURATION ===
    # Prefixes every debug line this device logs.
    LOGGER_NAME <override>: string = "My Device"

    # === INITIALIZATION ===
    # Runs once at startup, or after InitTrigger fires if one is assigned.
    # base_device has already swept players who were present before this
    # device started, so there is no need to do that here.

    Initialize<override>()<suspends>:void=
        Logger("Initialized with ExampleProperty = {ExampleProperty}")

    # === LIFECYCLE EVENTS ===
    # Logger's second argument is optional and labels the line's source,
    # which is useful once a device logs from more than one place.

    OnAgentJoined<override>(Agent : agent):void=
        Logger("Agent joined the island", ?Name := "Lifecycle")

    OnAgentRespawned<override>(Agent : agent):void=
        Logger("Agent respawned", ?Name := "Lifecycle")

    OnAgentLeft<override>(Agent : agent):void=
        Logger("Agent left the island", ?Name := "Lifecycle")
