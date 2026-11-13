using UnrealBuildTool;

public class StellanovaWorldTarget : TargetRules
{
	public StellanovaWorldTarget(TargetInfo Target) : base(Target)
	{
		Type = TargetType.Game;
		DefaultBuildSettings = BuildSettingsVersion.Latest;
		IncludeOrderVersion = EngineIncludeOrderVersion.Latest;
		ExtraModuleNames.Add("StellanovaWorld");
	}
}
