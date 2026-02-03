#_____________ DEBUG / LOGGING _______________________________________

# Custom Priority Levels:
debug_type <public> := enum{General, Important, Init, Error, Warning, Success, Alter}

# Custom Log Channel Class:
debug_display  <public> := class<concrete>:
    @editable Enable : logic = false
    @editable Type : debug_type = debug_type.General
    @editable Specifier : string = ""
    @editable Color : color = NamedColors.White
    @editable Duration : float = 5.0

    # If enabled, print the given message with the specified color and duration
    Log(Message : string) <transacts>: void =
        if (Enable?){Print("{Specifier} | {Message}", ?Color := Color, ?Duration := Duration)}

# Custom exposed debug settings class to put in every device:
debug_settings <public> := class<concrete>:
    @editable EnableDebug  <public> : logic = false
    @editable Identifier  <public> : string = "Device"
    @editable Channels  <public> : []debug_display = array:
        debug_display:
            Enable := true
            Type := debug_type.General
            Specifier := "❔"
            Color := NamedColors.White
            Duration := 1.0
        debug_display:
            Enable := true
            Type := debug_type.Error
            Specifier := "💔"
            Color := NamedColors.Red
            Duration := 10.0
        debug_display:
            Enable := true
            Type := debug_type.Warning
            Specifier := "🧡"
            Color := NamedColors.Orange
            Duration := 5.0
        debug_display:
            Enable := true
            Type := debug_type.Alter
            Specifier := "💛"
            Color := NamedColors.Yellow
            Duration := 0.0
        debug_display:
            Enable := true
            Type := debug_type.Success
            Specifier := "💚"
            Color := NamedColors.Green
            Duration := 1.0
        debug_display:
            Enable := true
            Type := debug_type.Init
            Specifier := "💙"
            Color := NamedColors.Blue
            Duration := 3.0
        debug_display:
            Enable := true
            Type := debug_type.Important
            Specifier := "💜"
            Color := NamedColors.Purple
            Duration := 7.5

    # Log Function that allows me to pass in the message and an optional custom type
    Log <public> (Message : string, ?Type: debug_type = debug_type.General)<transacts>:void=
        if (EnableDebug?):
            case (Type):
                debug_type.General => for (Channel : Channels, Channel.Enable? and Channel.Type = debug_type.General) {Channel.Log(Identifier + Message)}
                debug_type.Important => for (Channel : Channels, Channel.Enable? and Channel.Type = debug_type.Important) {Channel.Log(Identifier + Message)}
                debug_type.Init => for (Channel : Channels, Channel.Enable? and Channel.Type = debug_type.Init) {Channel.Log(Identifier + Message)}
                debug_type.Error => for (Channel : Channels, Channel.Enable? and Channel.Type = debug_type.Error) {Channel.Log(Identifier + Message)}
                debug_type.Warning => for (Channel : Channels, Channel.Enable? and Channel.Type = debug_type.Warning) {Channel.Log(Identifier + Message)}
                debug_type.Alter => for (Channel : Channels, Channel.Enable? and Channel.Type = debug_type.Alter) {Channel.Log(Identifier + Message)}
                debug_type.Success => for (Channel : Channels, Channel.Enable? and Channel.Type = debug_type.Success) {Channel.Log(Identifier + Message)}

#_____________ MESSAGE FORMATTING _______________________________________

# - Make Message of Player Name from passed in Agent
MakeName <public><localizes> (Agent:agent):message = "{Agent}"
# - Make Message from String Value
MakeMessage <public><localizes> (value:string) : message = "{value}"

#_____________ TOOLTIP _______________________________________

# - Debug ToolTip
DebugTip  <public><localizes> :message ="Display Settings for Debug Logs"
# - Label ToolTip
LabelTip <public><localizes> :message = "A custom label for organizational purposes. Interanl Use Only."