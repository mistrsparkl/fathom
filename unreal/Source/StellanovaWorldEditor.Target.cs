using UnrealBuildTool;

public class StellanovaWorldEditorTarget : TargetRules
{
	public StellanovaWorldEditorTarget(TargetInfo Target) : base(Target)
	{
		Type = TargetType.Editor;
		DefaultBuildSettings = BuildSettingsVersion.Latest;
		IncludeOrderVersion = EngineIncludeOrderVersion.Latest;
		ExtraModuleNames.Add("StellanovaWorld");
	}
}
