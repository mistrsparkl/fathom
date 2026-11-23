// The Unreal side: the eye, flat drawing, the game mode.
#pragma once
#include "CoreMinimal.h"
#include "GameFramework/GameModeBase.h"
#include "GameFramework/HUD.h"
#include "GameFramework/Pawn.h"
#include "FathomStage.generated.h"

class UCameraComponent;
class UInstancedStaticMeshComponent;
class UMaterialInterface;
class UStaticMesh;

UCLASS()
class AFathomEye : public APawn
{
	GENERATED_BODY()

public:
	AFathomEye();
	virtual void BeginPlay() override;
	virtual void EndPlay(const EEndPlayReason::Type Reason) override;
	virtual void Tick(float DeltaSeconds) override;

	UPROPERTY()
	TObjectPtr<UCameraComponent> Camera;

	UPROPERTY()
	TMap<FString, TObjectPtr<UInstancedStaticMeshComponent>> Meshes;  // one for each shape and colour

	UPROPERTY()
	TObjectPtr<UStaticMesh> Cube;

	UPROPERTY()
	TObjectPtr<UStaticMesh> Sphere;

	UPROPERTY()
	TObjectPtr<UStaticMesh> Plane;

	UPROPERTY()
	TObjectPtr<UMaterialInterface> Paint;

private:
	UInstancedStaticMeshComponent* MeshFor(UStaticMesh* Mesh, const FLinearColor& Colour);
	void ReadInput();
};

UCLASS()
class AFathomHUD : public AHUD
{
	GENERATED_BODY()

public:
	virtual void DrawHUD() override;
};

UCLASS()
class AFathomGameMode : public AGameModeBase
{
	GENERATED_BODY()

public:
	AFathomGameMode();
	virtual void BeginPlay() override;
};
