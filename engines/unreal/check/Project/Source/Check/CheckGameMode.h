#pragma once
#include "CoreMinimal.h"
#include "GameFramework/GameModeBase.h"
#include "CheckGameMode.generated.h"

UCLASS()
class ACheckGameMode : public AGameModeBase
{
	GENERATED_BODY()
protected:
	virtual void BeginPlay() override;
	void Report();
	FTimerHandle Later;
};
