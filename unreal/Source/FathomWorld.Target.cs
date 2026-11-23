using UnrealBuildTool;

public class FathomWorldTarget : TargetRules
{
	public FathomWorldTarget(TargetInfo Target) : base(Target)
	{
		Type = TargetType.Game;
		DefaultBuildSettings = BuildSettingsVersion.Latest;
		IncludeOrderVersion = EngineIncludeOrderVersion.Latest;
		ExtraModuleNames.Add("FathomWorld");
	}
}
