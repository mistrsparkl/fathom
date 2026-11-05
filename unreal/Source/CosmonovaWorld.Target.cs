using UnrealBuildTool;

public class CosmonovaWorldTarget : TargetRules
{
	public CosmonovaWorldTarget(TargetInfo Target) : base(Target)
	{
		Type = TargetType.Game;
		DefaultBuildSettings = BuildSettingsVersion.Latest;
		IncludeOrderVersion = EngineIncludeOrderVersion.Latest;
		ExtraModuleNames.Add("CosmonovaWorld");
	}
}
