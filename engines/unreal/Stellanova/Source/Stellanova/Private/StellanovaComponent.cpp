// Loads Stellanova plugins and answers their engine words. 1 unit = 1 metre; (h, v, d) = (Y, Z, X).
#include "StellanovaComponent.h"
#include "Components/MeshComponent.h"
#include "Components/PrimitiveComponent.h"
#include "Engine/Engine.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "GameFramework/Actor.h"
#include "GameFramework/PlayerController.h"
#include "HAL/FileManager.h"
#include "HAL/PlatformProcess.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"

DEFINE_LOG_CATEGORY_STATIC(LogStellanova, Log, All);

using FOutputFn = void (*)(const char* Text, int IsProblem);
using FEngineFn = double (*)(const char* Word, const double* Numbers, int Count, const char* Text, double* Answers, char* AnswerText, int Room);
using FStartFn = int (*)(FOutputFn, FEngineFn);
using FCallFn = int (*)(const char* Name, double Me, const double* Numbers, int Count, double* Answer);
using FHasFn = int (*)(const char* Name, int Count);

struct FStellanovaPlugin
{
	void* Handle = nullptr;
	FCallFn Call = nullptr;
	FHasFn Has = nullptr;
	TMap<FString, bool> Known;  // "every frame/1" -> does the program have it
};

namespace
{
	TMap<FString, FStellanovaPlugin*> Loaded;
	TMap<int32, TWeakObjectPtr<AActor>> ByNumber;  // each actor a program knows is a number (0 is none)
	TMap<uint32, int32> NumberOfId;  // an actor's unique id -> its number
	int32 Next = 1;
	TWeakObjectPtr<UWorld> World;  // the world of the call going on now
	constexpr double Metre = 100;

	double NumberOf(AActor* Actor)
	{
		if (!Actor)
			return 0;
		if (int32* Known = NumberOfId.Find(Actor->GetUniqueID()))
			return *Known;
		NumberOfId.Add(Actor->GetUniqueID(), Next);
		ByNumber.Add(Next, Actor);
		return Next++;
	}

	AActor* ActorOf(double Number)
	{
		TWeakObjectPtr<AActor>* Found = ByNumber.Find(static_cast<int32>(Number));
		return Found && Found->IsValid() ? Found->Get() : nullptr;
	}

	FString Folder() { return FPaths::ConvertRelativePathToFull(FPaths::ProjectDir() / TEXT("Stellanova")); }

	void Show(const char* Text, int IsProblem)
	{
		FString Said = UTF8_TO_TCHAR(Text);
		if (IsProblem)
		{
			UE_LOG(LogStellanova, Error, TEXT("Stellanova: %s"), *Said);
			if (GEngine)
				GEngine->AddOnScreenDebugMessage(-1, 10, FColor::Red, TEXT("Stellanova: ") + Said);
		}
		else
			UE_LOG(LogStellanova, Log, TEXT("%s"), *Said);
	}

	FKey KeyOf(const FString& Name)  // Key names Stellanova uses.
	{
		static const TMap<FString, FName> Named = {
			{TEXT("left"), TEXT("Left")}, {TEXT("right"), TEXT("Right")}, {TEXT("up"), TEXT("Up")}, {TEXT("down"), TEXT("Down")},
			{TEXT("space"), TEXT("SpaceBar")}, {TEXT("enter"), TEXT("Enter")}, {TEXT("escape"), TEXT("Escape")}, {TEXT("shift"), TEXT("LeftShift")},
			{TEXT("control"), TEXT("LeftControl")}, {TEXT("tab"), TEXT("Tab")}, {TEXT("backspace"), TEXT("BackSpace")},
			{TEXT("0"), TEXT("Zero")}, {TEXT("1"), TEXT("One")}, {TEXT("2"), TEXT("Two")}, {TEXT("3"), TEXT("Three")}, {TEXT("4"), TEXT("Four")},
			{TEXT("5"), TEXT("Five")}, {TEXT("6"), TEXT("Six")}, {TEXT("7"), TEXT("Seven")}, {TEXT("8"), TEXT("Eight")}, {TEXT("9"), TEXT("Nine")}};
		if (const FName* Found = Named.Find(Name))
			return FKey(*Found);
		return FKey(FName(*Name.ToUpper()));
	}

	bool ColourOf(const FString& Name, FLinearColor& Out)
	{
		static const TMap<FString, FString> Named = {
			{TEXT("black"), TEXT("000000")}, {TEXT("white"), TEXT("ffffff")}, {TEXT("red"), TEXT("ff0000")}, {TEXT("green"), TEXT("008000")},
			{TEXT("blue"), TEXT("0000ff")}, {TEXT("yellow"), TEXT("ffff00")}, {TEXT("orange"), TEXT("ffa500")}, {TEXT("purple"), TEXT("800080")},
			{TEXT("pink"), TEXT("ffc0cb")}, {TEXT("brown"), TEXT("a52a2a")}, {TEXT("grey"), TEXT("808080")}};
		FString Hex = Name.StartsWith(TEXT("#")) ? Name.Mid(1) : (Named.Contains(Name) ? Named[Name] : FString());
		if (Hex.Len() != 6)
			return false;
		Out = FLinearColor(FColor::FromHex(Hex));
		return true;
	}

	double Engine(const char* WordAt, const double* N, int Count, const char* TextAt, double* Answers, char* AnswerText, int Room)
	{
		FString Word = UTF8_TO_TCHAR(WordAt), Text = UTF8_TO_TCHAR(TextAt);
		UWorld* Here = World.Get();
		AActor* It = Count > 0 ? ActorOf(N[0]) : nullptr;
		if (!Here || (Count > 0 && !It))
			return 0;  // (an actor that has gone: its words do nothing)
		auto At = [&](int K) { return FVector(N[K + 2], N[K], N[K + 1]) * Metre; };  // (horizontal, vertical, depth) as Unreal's X, Y, Z
		APlayerController* Player = Here->GetFirstPlayerController();
		if (Word == TEXT("place"))
		{
			FVector P = It->GetActorLocation() / Metre;
			Answers[0] = P.Y, Answers[1] = P.Z, Answers[2] = P.X;
		}
		else if (Word == TEXT("put"))
			It->SetActorLocation(At(1), false, nullptr, ETeleportType::TeleportPhysics);
		else if (Word == TEXT("move"))
			It->AddActorWorldOffset(At(1), true);  // (swept: it stops at what it meets, and that counts as touching)
		else if (Word == TEXT("turn"))
			return It->GetActorRotation().Yaw;
		else if (Word == TEXT("turn by"))
			It->AddActorWorldRotation(FRotator(0, N[1], 0));
		else if (Word == TEXT("named"))
		{
			for (TActorIterator<AActor> Each(Here); Each; ++Each)
				if (Each->GetActorNameOrLabel() == Text)
					return NumberOf(*Each);
		}
		else if (Word == TEXT("name"))
		{
			FTCHARToUTF8 Bytes(*It->GetActorNameOrLabel());
			int32 Size = FMath::Min(Bytes.Length(), Room - 1);
			FMemory::Memcpy(AnswerText, Bytes.Get(), Size);
			AnswerText[Size] = 0;
		}
		else if (Word == TEXT("copy"))
		{
			FActorSpawnParameters How;
			How.Template = It;
			How.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
			FTransform Where(It->GetActorRotation(), At(1), It->GetActorScale3D());
			AActor* Made = Here->SpawnActor(It->GetClass(), &Where, How);
			if (Made)
			{
				Made->SetActorLocation(At(1), false, nullptr, ETeleportType::TeleportPhysics);
#if WITH_EDITOR
				Made->SetActorLabel(It->GetActorNameOrLabel());
#endif
				// The copy gets the program too.
				TArray<UStellanovaComponent*> Theirs, Copied;
				It->GetComponents(Theirs);
				Made->GetComponents(Copied);
				for (int32 K = Copied.Num(); K < Theirs.Num(); ++K)
				{
					UStellanovaComponent* Script = NewObject<UStellanovaComponent>(Made);
					Script->Program = Theirs[K]->Program;
					Script->RegisterComponent();
				}
			}
			return NumberOf(Made);
		}
		else if (Word == TEXT("remove"))
			It->Destroy();
		else if (Word == TEXT("colour"))
		{
			FLinearColor Colour;
			if (ColourOf(Text, Colour))
			{
				TArray<UMeshComponent*> Meshes;
				It->GetComponents(Meshes);
				for (UMeshComponent* Mesh : Meshes)
					if (UMaterialInstanceDynamic* Look = Mesh->CreateDynamicMaterialInstance(0))
					{
						Look->SetVectorParameterValue(TEXT("Color"), Colour);
						Look->SetVectorParameterValue(TEXT("BaseColor"), Colour);
					}
			}
		}
		else if (Word == TEXT("key held"))
			return Player && Player->IsInputKeyDown(KeyOf(Text)) ? 1 : 0;
		else if (Word == TEXT("key pressed"))
			return Player && Player->WasInputKeyJustPressed(KeyOf(Text)) ? 1 : 0;
		else if (Word == TEXT("frame time"))
			return Here->GetDeltaSeconds();
		return 0;
	}

#if WITH_EDITOR
	// In the editor, rebuild when the .stella file is newer.
	void BuildIfChanged(const FString& Name)
	{
		FString Script = Folder() / Name + TEXT(".stella"), Made = Folder() / Name + TEXT(".dll");
		IFileManager& Files = IFileManager::Get();
		if (!Files.FileExists(*Script) || (Files.FileExists(*Made) && Files.GetTimeStamp(*Made) >= Files.GetTimeStamp(*Script)))
			return;
		TArray<FString> Lines;  // home.txt: Stellanova's folder, then the Python that runs it
		FFileHelper::LoadFileToStringArray(Lines, *(Folder() / TEXT("home.txt")));
		FString Home = Lines.Num() > 0 ? Lines[0].TrimStartAndEnd() : FString();
		FString Python = Lines.Num() > 1 ? Lines[1].TrimStartAndEnd() : FString(TEXT("python"));
		if (Home.IsEmpty() || !Files.FileExists(*(Home / TEXT("stellanova.py"))))
		{
			Show("I can't find Stellanova: run 'stellanova unreal <this project's folder>' again.", 1);
			return;
		}
		int32 Code = 0;
		FString Out, Errors;
		FPlatformProcess::ExecProcess(*Python, *FString::Printf(TEXT("\"%s\" plugin \"%s\""), *(Home / TEXT("stellanova.py")), *Script), &Code, &Out, &Errors, *Folder());
		if (Code != 0)
			Show(TCHAR_TO_UTF8(*(Out + Errors).TrimStartAndEnd()), 1);
	}
#endif

	FStellanovaPlugin* Load(const FString& Name)
	{
		if (FStellanovaPlugin** Known = Loaded.Find(Name))
			return *Known;
		Loaded.Add(Name, nullptr);
#if WITH_EDITOR
		BuildIfChanged(Name);
#endif
		FString Path = Folder() / Name + TEXT(".dll");
		if (!IFileManager::Get().FileExists(*Path))
		{
			Show(TCHAR_TO_UTF8(*FString::Printf(TEXT("%s isn't built: put %s.stella in the project's Stellanova folder."), *Name, *Name)), 1);
			return nullptr;
		}
#if WITH_EDITOR
		// Loads a copy, so the program can be rebuilt.
		FString Copy = FPaths::ConvertRelativePathToFull(FPaths::ProjectIntermediateDir() / TEXT("Stellanova") /
			FString::Printf(TEXT("%s_%lld.dll"), *Name, FDateTime::Now().GetTicks()));
		IFileManager::Get().Copy(*Copy, *Path);
		Path = Copy;
#endif
		FStellanovaPlugin* Plugin = new FStellanovaPlugin;
		Plugin->Handle = FPlatformProcess::GetDllHandle(*Path);
		FStartFn Start = Plugin->Handle ? reinterpret_cast<FStartFn>(FPlatformProcess::GetDllExport(Plugin->Handle, TEXT("stellanova_start"))) : nullptr;
		if (!Start)
		{
			Show(TCHAR_TO_UTF8(*FString::Printf(TEXT("%s couldn't be loaded on this computer."), *Name)), 1);
			delete Plugin;
			return nullptr;
		}
		Plugin->Call = reinterpret_cast<FCallFn>(FPlatformProcess::GetDllExport(Plugin->Handle, TEXT("stellanova_call")));
		Plugin->Has = reinterpret_cast<FHasFn>(FPlatformProcess::GetDllExport(Plugin->Handle, TEXT("stellanova_has")));
		Loaded[Name] = Plugin;
		Start(Show, Engine);
		return Plugin;
	}

	void UnloadAll()
	{
		for (auto& Each : Loaded)
			if (Each.Value)
			{
				FPlatformProcess::FreeDllHandle(Each.Value->Handle);
				delete Each.Value;
			}
		Loaded.Empty();
		ByNumber.Empty();
		NumberOfId.Empty();
		Next = 1;
	}
}

UStellanovaComponent::UStellanovaComponent()
{
	PrimaryComponentTick.bCanEverTick = true;
}

void UStellanovaComponent::BeginPlay()
{
	Super::BeginPlay();
	World = GetWorld();
	Plugin = Program.IsEmpty() ? nullptr : Load(Program);
	if (!Plugin)
	{
		if (Program.IsEmpty())
			Show(TCHAR_TO_UTF8(*FString::Printf(TEXT("%s has a Stellanova Component without a program: name a .stella file."), *GetOwner()->GetActorNameOrLabel())), 1);
		SetComponentTickEnabled(false);
		return;
	}
	if (UPrimitiveComponent* Body = Cast<UPrimitiveComponent>(GetOwner()->GetRootComponent()))
		Body->SetNotifyRigidBodyCollision(true);  // (so bumping into things is noticed)
	GetOwner()->OnActorHit.AddDynamic(this, &UStellanovaComponent::Hit);
	GetOwner()->OnActorBeginOverlap.AddDynamic(this, &UStellanovaComponent::Overlap);
	CallCommand(TEXT("begin"), {});
}

void UStellanovaComponent::EndPlay(const EEndPlayReason::Type Why)
{
	Plugin = nullptr;
	if (Why == EEndPlayReason::EndPlayInEditor || Why == EEndPlayReason::Quit)
		UnloadAll();  // (the next play loads the newest builds)
	Super::EndPlay(Why);
}

void UStellanovaComponent::TickComponent(float Seconds, ELevelTick Tick, FActorComponentTickFunction* ThisTick)
{
	Super::TickComponent(Seconds, Tick, ThisTick);
	CallCommand(TEXT("every frame"), {Seconds});
}

void UStellanovaComponent::CallCommand(const FString& Command, const TArray<double>& Numbers)
{
	if (!Plugin)
		return;
	FString Key = FString::Printf(TEXT("%s/%d"), *Command, Numbers.Num());
	FTCHARToUTF8 Name(*Command);
	bool* There = Plugin->Known.Find(Key);
	if (!There)
		There = &Plugin->Known.Add(Key, Plugin->Has(Name.Get(), Numbers.Num()) == 1);
	if (*There)
	{
		World = GetWorld();
		double Answer = 0;
		Plugin->Call(Name.Get(), NumberOf(GetOwner()), Numbers.GetData(), Numbers.Num(), &Answer);
	}
}

void UStellanovaComponent::Hit(AActor* Me, AActor* Other, FVector Push, const FHitResult& Where)
{
	// Only a new touch counts (none for 0.25 s).
	static TMap<TPair<uint32, uint32>, double> Last;
	double Now = GetWorld()->GetTimeSeconds();
	double& Then = Last.FindOrAdd({Me->GetUniqueID(), Other->GetUniqueID()}, -1);
	bool Fresh = Then < 0 || Now - Then > 0.25;
	Then = Now;
	if (Fresh)
		CallCommand(TEXT("touched"), {NumberOf(Other)});
}

void UStellanovaComponent::Overlap(AActor* Me, AActor* Other)
{
	CallCommand(TEXT("touched"), {NumberOf(Other)});
}
