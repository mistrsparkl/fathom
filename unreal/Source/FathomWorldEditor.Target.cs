using UnrealBuildTool;

public class FathomWorldEditorTarget : TargetRules
{
	public FathomWorldEditorTarget(TargetInfo Target) : base(Target)
	{
		Type = TargetType.Editor;
		DefaultBuildSettings = BuildSettingsVersion.Latest;
		IncludeOrderVersion = EngineIncludeOrderVersion.Latest;
		ExtraModuleNames.Add("FathomWorld");
	}
}
