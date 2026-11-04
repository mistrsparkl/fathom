using UnrealBuildTool;

public class ImaginationWorldTarget : TargetRules
{
	public ImaginationWorldTarget(TargetInfo Target) : base(Target)
	{
		Type = TargetType.Game;
		DefaultBuildSettings = BuildSettingsVersion.Latest;
		IncludeOrderVersion = EngineIncludeOrderVersion.Latest;
		ExtraModuleNames.Add("ImaginationWorld");
	}
}
