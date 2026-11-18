// Runs a Stellanova program on this actor.
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

	// The program's name in the project's Stellanova folder (e.g. coin).
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Stellanova")
	FString Program;

	// Calls a command for this actor, if the program has it.
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
