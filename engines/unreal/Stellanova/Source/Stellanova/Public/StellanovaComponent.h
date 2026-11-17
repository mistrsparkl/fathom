// Runs a Stellanova program on this actor: 'to begin:' when play starts, 'to every frame, given seconds (a number):'
// each frame, and 'to touched, given other (a number):' when it hits or overlaps another actor.
#pragma once

#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "StellanovaComponent.generated.h"

UCLASS(ClassGroup = (Scripting), meta = (BlueprintSpawnableComponent))
class STELLANOVA_API UStellanovaComponent : public UActorComponent
{
	GENERATED_BODY()

public:
	UStellanovaComponent();

	// The program: a .stella file in the project's Stellanova folder, without '.stella' (e.g. coin).
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Stellanova")
	FString Program;

	// Calls one of the program's commands for this actor (nothing happens if the program hasn't got it).
	UFUNCTION(BlueprintCallable, Category = "Stellanova")
	void CallCommand(const FString& Command, const TArray<double>& Numbers);

protected:
	virtual void BeginPlay() override;
	virtual void EndPlay(const EEndPlayReason::Type Why) override;
	virtual void TickComponent(float Seconds, ELevelTick Tick, FActorComponentTickFunction* ThisTick) override;

private:
	UFUNCTION()
	void Hit(AActor* Me, AActor* Other, FVector Push, const FHitResult& Where);
	UFUNCTION()
	void Overlap(AActor* Me, AActor* Other);

	struct FStellanovaPlugin* Plugin = nullptr;
};
