using UnrealBuildTool;

public class AITexturingEditor : ModuleRules
{
    public AITexturingEditor(ReadOnlyTargetRules Target) : base(Target)
    {
        PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;

        PrivateDependencyModuleNames.AddRange(
            new string[]
            {
                "Core",
                "CoreUObject",
                "DesktopPlatform",
                "Engine",
                "InputCore",
                "Json",
                "Projects",
                "PythonScriptPlugin",
                "Slate",
                "SlateCore",
                "ToolMenus",
                "UnrealEd"
            }
        );
    }
}
