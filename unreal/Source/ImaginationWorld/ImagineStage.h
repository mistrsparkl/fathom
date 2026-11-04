// The Unreal side of an Imagination program: the eye (camera) that shows each frame, the flat drawing on top, and the game mode.
#pragma once
#include "CoreMinimal.h"
#include "GameFramework/GameModeBase.h"
#include "GameFramework/HUD.h"
#include "GameFramework/Pawn.h"
#include "ImagineStage.generated.h"

class UCameraComponent;
class UInstancedStaticMeshComponent;
class UMaterialInterface;
class UStaticMesh;

UCLASS()
class AImagineEye : public APawn
{
	GENERATED_BODY()

public:
	AImagineEye();
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
class AImagineHUD : public AHUD
{
	GENERATED_BODY()

public:
	virtual void DrawHUD() override;
};

UCLASS()
class AImagineGameMode : public AGameModeBase
{
	GENERATED_BODY()

public:
	AImagineGameMode();
	virtual void BeginPlay() override;
};
