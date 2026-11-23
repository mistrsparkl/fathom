// Runs a Fathom program on this actor.
#pragma once

#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "FathomComponent.generated.h"

UCLASS(ClassGroup = (Scripting), meta = (BlueprintSpawnableComponent))
class FATHOM_API UFathomComponent : public UActorComponent
{
	GENERATED_BODY()

public:
	UFathomComponent();

	// The program's name in the project's Fathom folder (e.g. coin).
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Fathom")
	FString Program;

	// Calls a command for this actor, if the program has it.
	UFUNCTION(BlueprintCallable, Category = "Fathom")
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

	struct FFathomPlugin* Plugin = nullptr;
};
