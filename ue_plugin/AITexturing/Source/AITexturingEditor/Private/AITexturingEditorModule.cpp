#include "CoreMinimal.h"
#include "DesktopPlatformModule.h"
#include "Dom/JsonObject.h"
#include "Framework/Docking/TabManager.h"
#include "IDesktopPlatform.h"
#include "Interfaces/IPluginManager.h"
#include "IPythonScriptPlugin.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Modules/ModuleManager.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"
#include "Styling/CoreStyle.h"
#include "ToolMenus.h"
#include "Widgets/Docking/SDockTab.h"
#include "Widgets/Input/SButton.h"
#include "Widgets/Input/SEditableTextBox.h"
#include "Widgets/Input/SMultiLineEditableTextBox.h"
#include "Widgets/Layout/SBorder.h"
#include "Widgets/Layout/SScrollBox.h"
#include "Widgets/SBoxPanel.h"
#include "Widgets/Text/STextBlock.h"

#include <initializer_list>

#define LOCTEXT_NAMESPACE "FAITexturingEditorModule"

namespace AITexturingEditor
{
static const FName TabName("AITexturingEditor");

struct FSettings
{
    FString ServerUrl = TEXT("http://127.0.0.1:8000");
    FString JobId;
    FString LocalPackagePath;
};

static FString SettingsPath()
{
    return FPaths::Combine(FPaths::ProjectSavedDir(), TEXT("Config"), TEXT("AITexturingEditor.json"));
}

static FString PluginScriptDir()
{
    TSharedPtr<IPlugin> Plugin = IPluginManager::Get().FindPlugin(TEXT("AITexturing"));
    if (!Plugin.IsValid())
    {
        return FString();
    }
    return FPaths::ConvertRelativePathToFull(FPaths::Combine(Plugin->GetBaseDir(), TEXT("Scripts")));
}

static FString PythonQuote(const FString& Value)
{
    FString Escaped = Value;
    Escaped.ReplaceInline(TEXT("\\"), TEXT("\\\\"));
    Escaped.ReplaceInline(TEXT("'"), TEXT("\\'"));
    return FString::Printf(TEXT("'%s'"), *Escaped);
}

static bool LoadSettings(FSettings& OutSettings)
{
    FString Text;
    if (!FFileHelper::LoadFileToString(Text, *SettingsPath()))
    {
        return false;
    }

    TSharedPtr<FJsonObject> Root;
    const TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(Text);
    if (!FJsonSerializer::Deserialize(Reader, Root) || !Root.IsValid())
    {
        return false;
    }

    Root->TryGetStringField(TEXT("server_url"), OutSettings.ServerUrl);
    Root->TryGetStringField(TEXT("job_id"), OutSettings.JobId);
    Root->TryGetStringField(TEXT("local_package_path"), OutSettings.LocalPackagePath);
    return true;
}

static bool SaveSettings(const FSettings& Settings)
{
    TSharedRef<FJsonObject> Root = MakeShared<FJsonObject>();
    Root->SetStringField(TEXT("server_url"), Settings.ServerUrl);
    Root->SetStringField(TEXT("job_id"), Settings.JobId);
    Root->SetStringField(TEXT("local_package_path"), Settings.LocalPackagePath);

    FString Text;
    const TSharedRef<TJsonWriter<>> Writer = TJsonWriterFactory<>::Create(&Text);
    FJsonSerializer::Serialize(Root, Writer);

    IFileManager::Get().MakeDirectory(*FPaths::GetPath(SettingsPath()), true);
    return FFileHelper::SaveStringToFile(Text, *SettingsPath());
}

class SAITexturingPanel : public SCompoundWidget
{
public:
    SLATE_BEGIN_ARGS(SAITexturingPanel) {}
    SLATE_END_ARGS()

    void Construct(const FArguments& InArgs)
    {
        LoadSettings(Settings);

        ChildSlot
        [
            SNew(SBorder)
            .Padding(12.0f)
            [
                SNew(SScrollBox)
                + SScrollBox::Slot()
                [
                    SNew(SVerticalBox)
                    + SVerticalBox::Slot().AutoHeight().Padding(0, 0, 0, 10)
                    [
                        SNew(STextBlock)
                        .Text(LOCTEXT("Title", "AI Texturing"))
                        .Font(FCoreStyle::GetDefaultFontStyle("Bold", 16))
                    ]
                    + SVerticalBox::Slot().AutoHeight()
                    [
                        MakeLabeledTextBox(LOCTEXT("ServerUrl", "Server URL"), ServerUrlBox, Settings.ServerUrl)
                    ]
                    + SVerticalBox::Slot().AutoHeight()
                    [
                        MakeLabeledTextBox(LOCTEXT("JobId", "Job ID"), JobIdBox, Settings.JobId)
                    ]
                    + SVerticalBox::Slot().AutoHeight()
                    [
                        MakePackagePathRow()
                    ]
                    + SVerticalBox::Slot().AutoHeight().Padding(0, 8)
                    [
                        MakeButtonGrid()
                    ]
                    + SVerticalBox::Slot().AutoHeight().Padding(0, 8, 0, 2)
                    [
                        SNew(STextBlock).Text(LOCTEXT("LogLabel", "Log"))
                    ]
                    + SVerticalBox::Slot().MinHeight(180)
                    [
                        SAssignNew(LogBox, SMultiLineEditableTextBox)
                        .IsReadOnly(true)
                        .AutoWrapText(true)
                        .Text(FText::FromString(TEXT("Ready.\n")))
                    ]
                ]
            ]
        ];
    }

private:
    FSettings Settings;
    TSharedPtr<SEditableTextBox> ServerUrlBox;
    TSharedPtr<SEditableTextBox> JobIdBox;
    TSharedPtr<SEditableTextBox> PackagePathBox;
    TSharedPtr<SMultiLineEditableTextBox> LogBox;

    struct FButtonSpec
    {
        FText Label;
        FString Action;
    };

    TSharedRef<SWidget> MakeLabeledTextBox(const FText& Label, TSharedPtr<SEditableTextBox>& OutBox, const FString& Value)
    {
        return SNew(SVerticalBox)
            + SVerticalBox::Slot().AutoHeight().Padding(0, 4, 0, 2)
            [
                SNew(STextBlock).Text(Label)
            ]
            + SVerticalBox::Slot().AutoHeight().Padding(0, 0, 0, 6)
            [
                SAssignNew(OutBox, SEditableTextBox)
                .Text(FText::FromString(Value))
            ];
    }

    TSharedRef<SWidget> MakePackagePathRow()
    {
        return SNew(SVerticalBox)
            + SVerticalBox::Slot().AutoHeight().Padding(0, 4, 0, 2)
            [
                SNew(STextBlock).Text(LOCTEXT("PackagePath", "Local Package Path"))
            ]
            + SVerticalBox::Slot().AutoHeight().Padding(0, 0, 0, 6)
            [
                SNew(SHorizontalBox)
                + SHorizontalBox::Slot().FillWidth(1.0f)
                [
                    SAssignNew(PackagePathBox, SEditableTextBox)
                    .Text(FText::FromString(Settings.LocalPackagePath))
                ]
                + SHorizontalBox::Slot().AutoWidth().Padding(6, 0, 0, 0)
                [
                    SNew(SButton)
                    .Text(LOCTEXT("Browse", "Browse"))
                    .OnClicked(this, &SAITexturingPanel::OnBrowsePackage)
                ]
            ];
    }

    FButtonSpec MakeButtonSpec(const FText& Label, const FString& Action) const
    {
        FButtonSpec Spec;
        Spec.Label = Label;
        Spec.Action = Action;
        return Spec;
    }

    TSharedRef<SWidget> MakeButtonRow(std::initializer_list<FButtonSpec> Specs)
    {
        TSharedRef<SHorizontalBox> Row = SNew(SHorizontalBox);
        for (const FButtonSpec& Spec : Specs)
        {
            Row->AddSlot()
            .FillWidth(1.0f)
            .Padding(0, 3, 6, 3)
            [
                SNew(SButton)
                .Text(Spec.Label)
                .HAlign(HAlign_Center)
                .OnClicked_Lambda([this, Action = Spec.Action]()
                {
                    HandleAction(Action);
                    return FReply::Handled();
                })
            ];
        }
        return Row;
    }

    TSharedRef<SWidget> MakeButtonGrid()
    {
        return SNew(SVerticalBox)
            + SVerticalBox::Slot().AutoHeight()
            [
                MakeButtonRow({
                    MakeButtonSpec(LOCTEXT("SaveSettings", "Save Settings"), TEXT("save_settings")),
                    MakeButtonSpec(LOCTEXT("CreateJob", "Create Job"), TEXT("create_job")),
                    MakeButtonSpec(LOCTEXT("PollStatus", "Poll Status"), TEXT("poll_status"))
                })
            ]
            + SVerticalBox::Slot().AutoHeight()
            [
                MakeButtonRow({
                    MakeButtonSpec(LOCTEXT("UploadReference", "Upload Reference"), TEXT("upload_reference")),
                    MakeButtonSpec(LOCTEXT("GenerateReference", "Generate Reference"), TEXT("generate_reference")),
                    MakeButtonSpec(LOCTEXT("SubmitAssignment", "Submit Assignment"), TEXT("submit_assignment"))
                })
            ]
            + SVerticalBox::Slot().AutoHeight()
            [
                MakeButtonRow({
                    MakeButtonSpec(LOCTEXT("UploadMask", "Upload Mask"), TEXT("upload_mask")),
                    MakeButtonSpec(LOCTEXT("AutoSAM", "Auto SAM Candidates"), TEXT("auto_sam")),
                    MakeButtonSpec(LOCTEXT("ConfirmSAM", "Confirm SAM Masks"), TEXT("confirm_sam_masks"))
                })
            ]
            + SVerticalBox::Slot().AutoHeight()
            [
                MakeButtonRow({
                    MakeButtonSpec(LOCTEXT("StartPBR", "Start Mock/Real PBR Generation"), TEXT("start_pbr")),
                    MakeButtonSpec(LOCTEXT("DownloadPackage", "Download Package"), TEXT("download_package")),
                    MakeButtonSpec(LOCTEXT("ImportPackage", "Import Local Package"), TEXT("import_none"))
                })
            ]
            + SVerticalBox::Slot().AutoHeight()
            [
                MakeButtonRow({
                    MakeButtonSpec(LOCTEXT("AssignSelected", "Assign To Selected Actors"), TEXT("import_selected")),
                    MakeButtonSpec(LOCTEXT("AssignAll", "Assign To All Level Actors"), TEXT("import_all"))
                })
            ];
    }

    FReply OnBrowsePackage()
    {
        void* ParentWindowHandle = nullptr;
        IDesktopPlatform* DesktopPlatform = FDesktopPlatformModule::Get();
        if (!DesktopPlatform)
        {
            AppendLog(TEXT("DesktopPlatform unavailable."));
            return FReply::Handled();
        }

        TArray<FString> Files;
        const FString DefaultPath = FPaths::ProjectSavedDir();
        const bool bOpened = DesktopPlatform->OpenFileDialog(
            ParentWindowHandle,
            TEXT("Choose AI Texturing Package"),
            DefaultPath,
            TEXT(""),
            TEXT("AI Texturing Package (*.zip;manifest.json)|*.zip;manifest.json|All Files (*.*)|*.*"),
            EFileDialogFlags::None,
            Files
        );

        if (bOpened && Files.Num() > 0)
        {
            FString Chosen = Files[0];
            if (FPaths::GetCleanFilename(Chosen).Equals(TEXT("manifest.json"), ESearchCase::IgnoreCase))
            {
                Chosen = FPaths::GetPath(Chosen);
            }
            PackagePathBox->SetText(FText::FromString(Chosen));
            SaveCurrentSettings();
        }
        return FReply::Handled();
    }

    void HandleAction(const FString& Action)
    {
        SaveCurrentSettings();
        if (Action == TEXT("save_settings"))
        {
            AppendLog(FString::Printf(TEXT("Saved settings to %s"), *SettingsPath()));
            return;
        }
        if (Action == TEXT("import_none"))
        {
            ExecuteImport(TEXT("none"));
            return;
        }
        if (Action == TEXT("import_selected"))
        {
            ExecuteImport(TEXT("selected"));
            return;
        }
        if (Action == TEXT("import_all"))
        {
            ExecuteImport(TEXT("all"));
            return;
        }
        ExecuteServerAction(Action);
    }

    void SaveCurrentSettings()
    {
        Settings.ServerUrl = ServerUrlBox.IsValid() ? ServerUrlBox->GetText().ToString() : Settings.ServerUrl;
        Settings.JobId = JobIdBox.IsValid() ? JobIdBox->GetText().ToString() : Settings.JobId;
        Settings.LocalPackagePath = PackagePathBox.IsValid() ? PackagePathBox->GetText().ToString() : Settings.LocalPackagePath;
        SaveSettings(Settings);
    }

    void ExecuteImport(const FString& AssignMode)
    {
        if (Settings.LocalPackagePath.IsEmpty())
        {
            AppendLog(TEXT("Local Package Path is empty."));
            return;
        }
        const FString ScriptDir = PluginScriptDir();
        if (ScriptDir.IsEmpty())
        {
            AppendLog(TEXT("Could not find AITexturing plugin script directory."));
            return;
        }

        const FString Command = FString::Printf(
            TEXT("import sys\nsys.path.append(%s)\nimport import_ai_materials\nimport_ai_materials.run(%s, assign_mode=%s)"),
            *PythonQuote(ScriptDir),
            *PythonQuote(Settings.LocalPackagePath),
            *PythonQuote(AssignMode)
        );
        AppendLog(FString::Printf(TEXT("Running importer with assign_mode=%s"), *AssignMode));
        ExecutePython(Command);
    }

    void ExecuteServerAction(const FString& Action)
    {
        const FString ScriptDir = PluginScriptDir();
        if (ScriptDir.IsEmpty())
        {
            AppendLog(TEXT("Could not find AITexturing plugin script directory."));
            return;
        }

        const FString Command = FString::Printf(
            TEXT("import sys\nsys.path.append(%s)\nimport ai_texturing_ui_actions\nai_texturing_ui_actions.run_action(%s, %s, %s, %s)"),
            *PythonQuote(ScriptDir),
            *PythonQuote(Action),
            *PythonQuote(Settings.ServerUrl),
            *PythonQuote(Settings.JobId),
            *PythonQuote(Settings.LocalPackagePath)
        );
        AppendLog(FString::Printf(TEXT("Running server action: %s"), *Action));
        ExecutePython(Command);
    }

    void ExecutePython(const FString& Command)
    {
        IPythonScriptPlugin* Python = IPythonScriptPlugin::Get();
        if (!Python)
        {
            AppendLog(TEXT("PythonScriptPlugin is not available. Enable the Python Editor Script Plugin."));
            return;
        }
        Python->ExecPythonCommand(*Command);
    }

    void AppendLog(const FString& Line)
    {
        UE_LOG(LogTemp, Log, TEXT("[AITexturing] %s"), *Line);
        if (!LogBox.IsValid())
        {
            return;
        }
        const FString Existing = LogBox->GetText().ToString();
        LogBox->SetText(FText::FromString(Existing + Line + TEXT("\n")));
    }
};
} // namespace AITexturingEditor

class FAITexturingEditorModule : public IModuleInterface
{
public:
    virtual void StartupModule() override
    {
        FGlobalTabmanager::Get()->RegisterNomadTabSpawner(
            AITexturingEditor::TabName,
            FOnSpawnTab::CreateRaw(this, &FAITexturingEditorModule::SpawnTab)
        )
        .SetDisplayName(LOCTEXT("TabTitle", "AI Texturing"))
        .SetMenuType(ETabSpawnerMenuType::Hidden);

        UToolMenus::RegisterStartupCallback(
            FSimpleMulticastDelegate::FDelegate::CreateRaw(this, &FAITexturingEditorModule::RegisterMenus)
        );
    }

    virtual void ShutdownModule() override
    {
        if (UToolMenus::IsToolMenuUIEnabled())
        {
            UToolMenus::UnRegisterStartupCallback(this);
            UToolMenus::UnregisterOwner(this);
        }
        FGlobalTabmanager::Get()->UnregisterNomadTabSpawner(AITexturingEditor::TabName);
    }

private:
    TSharedRef<SDockTab> SpawnTab(const FSpawnTabArgs& Args)
    {
        return SNew(SDockTab)
            .TabRole(ETabRole::NomadTab)
            [
                SNew(AITexturingEditor::SAITexturingPanel)
            ];
    }

    void RegisterMenus()
    {
        FToolMenuOwnerScoped OwnerScoped(this);
        UToolMenu* Menu = UToolMenus::Get()->ExtendMenu(TEXT("LevelEditor.MainMenu.Window"));
        FToolMenuSection& Section = Menu->FindOrAddSection(TEXT("WindowLayout"));
        Section.AddMenuEntry(
            TEXT("OpenAITexturing"),
            LOCTEXT("OpenAITexturing", "AI Texturing"),
            LOCTEXT("OpenAITexturingTooltip", "Open the AI Texturing editor panel."),
            FSlateIcon(),
            FUIAction(FExecuteAction::CreateRaw(this, &FAITexturingEditorModule::OpenPanel))
        );
    }

    void OpenPanel()
    {
        FGlobalTabmanager::Get()->TryInvokeTab(AITexturingEditor::TabName);
    }
};

IMPLEMENT_MODULE(FAITexturingEditorModule, AITexturingEditor)

#undef LOCTEXT_NAMESPACE
