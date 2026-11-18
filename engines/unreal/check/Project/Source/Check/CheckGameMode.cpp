// The check scene. Writes check.txt after 3 seconds.
#include "CheckGameMode.h"
#include "Engine/StaticMeshActor.h"
#include "Engine/StaticMesh.h"
#include "Components/StaticMeshComponent.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "EngineUtils.h"
#include "Misc/FileHelper.h"
#include "Misc/OutputDevice.h"
#include "Misc/Paths.h"
#include "StellanovaComponent.h"
#include "TimerManager.h"
#include "Modules/ModuleManager.h"

IMPLEMENT_PRIMARY_GAME_MODULE(FDefaultGameModuleImpl, Check, "Check");

// Keeps what the programs log.
struct FKeeper : FOutputDevice
{
	FString Said;
	virtual void Serialize(const TCHAR* Text, ELogVerbosity::Type Verbosity, const FName& Category) override
	{
		if (Category != TEXT("LogStellanova"))
			return;
		FString Line = Text;
		if (Verbosity == ELogVerbosity::Error && Line.RemoveFromStart(TEXT("Stellanova: ")))
			Said += TEXT("SAID problem: ") + Line + TEXT("\n");
		else if (Verbosity == ELogVerbosity::Error)
			Said += TEXT("BAD ") + Line + TEXT("\n");
		else
			Said += TEXT("SAID ") + Line + TEXT("\n");
	}
};
static FKeeper Keeper;

static AStaticMeshActor* Shape(UWorld* World, const TCHAR* Mesh, const TCHAR* Name, FVector At, bool Program)
{
	FActorSpawnParameters How;
	How.Name = Name;  // (a packaged game has no labels: the name is what the program sees)
	How.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
	AStaticMeshActor* Made = World->SpawnActor<AStaticMeshActor>(At, FRotator::ZeroRotator, How);
	Made->GetStaticMeshComponent()->SetMobility(EComponentMobility::Movable);
	Made->GetStaticMeshComponent()->SetStaticMesh(LoadObject<UStaticMesh>(nullptr, Mesh));
#if WITH_EDITOR
	Made->SetActorLabel(Name);
#endif
	if (Program)
	{
		UStellanovaComponent* Script = NewObject<UStellanovaComponent>(Made);
		Script->Program = TEXT("words");
		Script->RegisterComponent();
	}
	return Made;
}

void ACheckGameMode::BeginPlay()
{
	Super::BeginPlay();
	GLog->AddOutputDevice(&Keeper);
	// (h, v, d) metres are Unreal's (d, h, v) * 100
	Shape(GetWorld(), TEXT("/Engine/BasicShapes/Cube.Cube"), TEXT("Box"), FVector(0, 800, 0), false);
	Shape(GetWorld(), TEXT("/Engine/BasicShapes/Cube.Cube"), TEXT("Target"), FVector::ZeroVector, true);
	AStaticMeshActor* Ball = Shape(GetWorld(), TEXT("/Engine/BasicShapes/Sphere.Sphere"), TEXT("Player"), FVector(0, 0, 400), false);
	Ball->GetStaticMeshComponent()->SetSimulatePhysics(true);
	Ball->GetStaticMeshComponent()->SetNotifyRigidBodyCollision(true);
	Shape(GetWorld(), TEXT("/Engine/BasicShapes/Cube.Cube"), TEXT("Mover"), FVector(300, 100, 200), true);
	GetWorldTimerManager().SetTimer(Later, this, &ACheckGameMode::Report, 3.0f);
}

void ACheckGameMode::Report()
{
	GLog->RemoveOutputDevice(&Keeper);
	FString Said = Keeper.Said;
	for (TActorIterator<AStaticMeshActor> Each(GetWorld()); Each; ++Each)
	{
		FString Colour = TEXT("none");
		FLinearColor Value;
		UMaterialInstanceDynamic* Look = Cast<UMaterialInstanceDynamic>(Each->GetStaticMeshComponent()->GetMaterial(0));
		if (Look && Look->GetVectorParameterValue(FHashedMaterialParameterInfo(TEXT("Color")), Value))
			Colour = Value.Equals(FLinearColor(1, 0, 0)) ? TEXT("red") : Value.Equals(FLinearColor(0, 0, 1)) ? TEXT("blue") : TEXT("other");
		FVector P = Each->GetActorLocation() / 100;
		Said += FString::Printf(TEXT("CHECK %s|%f|%f|%f|%f|%s\n"), *Each->GetActorNameOrLabel(), P.Y, P.Z, P.X, Each->GetActorRotation().Yaw, *Colour);
	}
	FFileHelper::SaveStringToFile(Said, *(FPaths::ProjectDir() / TEXT("check.txt")));
	FGenericPlatformMisc::RequestExit(false);
}
