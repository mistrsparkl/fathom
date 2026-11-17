// The check: a coin with a Stellanova program, and a ball that falls onto it.
#include "CheckGameMode.h"
#include "Engine/StaticMeshActor.h"
#include "Engine/StaticMesh.h"
#include "Components/StaticMeshComponent.h"
#include "EngineUtils.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "StellanovaComponent.h"
#include "TimerManager.h"
#include "Modules/ModuleManager.h"

IMPLEMENT_PRIMARY_GAME_MODULE(FDefaultGameModuleImpl, Check, "Check");

static AStaticMeshActor* Shape(UWorld* World, const TCHAR* Mesh, const TCHAR* Name, FVector At)
{
	FActorSpawnParameters How;
	How.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
	AStaticMeshActor* Made = World->SpawnActor<AStaticMeshActor>(At, FRotator::ZeroRotator, How);
	Made->GetStaticMeshComponent()->SetMobility(EComponentMobility::Movable);
	Made->GetStaticMeshComponent()->SetStaticMesh(LoadObject<UStaticMesh>(nullptr, Mesh));
	Made->SetActorLabel(Name);
	return Made;
}

void ACheckGameMode::BeginPlay()
{
	Super::BeginPlay();
	AStaticMeshActor* Coin = Shape(GetWorld(), TEXT("/Engine/BasicShapes/Cube.Cube"), TEXT("Coin"), FVector::ZeroVector);
	UStellanovaComponent* Script = NewObject<UStellanovaComponent>(Coin);
	Script->Program = TEXT("coin");
	Script->RegisterComponent();
	AStaticMeshActor* Floor = Shape(GetWorld(), TEXT("/Engine/BasicShapes/Cube.Cube"), TEXT("Floor"), FVector(0, 0, -600));
	Floor->SetActorScale3D(FVector(10, 10, 1));
	AStaticMeshActor* Ball = Shape(GetWorld(), TEXT("/Engine/BasicShapes/Sphere.Sphere"), TEXT("Player"), FVector(0, 0, 400));
	Ball->GetStaticMeshComponent()->SetSimulatePhysics(true);
	GetWorldTimerManager().SetTimer(Later, this, &ACheckGameMode::Report, 3.0f);
}

void ACheckGameMode::Report()
{
	FString Said;
	for (TActorIterator<AStaticMeshActor> Each(GetWorld()); Each; ++Each)
		Said += FString::Printf(TEXT("%s at %s turn %.0f\n"), *Each->GetActorNameOrLabel(), *(Each->GetActorLocation() / 100).ToString(), Each->GetActorRotation().Yaw);
	FFileHelper::SaveStringToFile(Said, *(FPaths::ProjectDir() / TEXT("check.txt")));
	FGenericPlatformMisc::RequestExit(false);
}
