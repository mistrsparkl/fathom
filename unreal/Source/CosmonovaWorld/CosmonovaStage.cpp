#include "CosmonovaStage.h"
#include "CosmonovaBridge.h"
#include "cosmonova.h"
#include "Camera/CameraComponent.h"
#include "Components/DirectionalLightComponent.h"
#include "Components/InstancedStaticMeshComponent.h"
#include "Components/SkyAtmosphereComponent.h"
#include "Components/SkyLightComponent.h"
#include "Engine/Canvas.h"
#include "Engine/DirectionalLight.h"
#include "Engine/Engine.h"
#include "Engine/ExponentialHeightFog.h"
#include "Engine/Font.h"
#include "Engine/GameViewportClient.h"
#include "Engine/SkyLight.h"
#include "Engine/StaticMesh.h"
#include "GameFramework/GameUserSettings.h"
#include "GameFramework/PlayerController.h"
#include "InputCoreTypes.h"
#include "Kismet/KismetSystemLibrary.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "Widgets/SWindow.h"
#include <thread>

int CosmonovaMain();  // the program, from Generated/Program.cosmos.cpp

namespace
{
	cosmonova_unreal::Frame Shown;  // the frame on the screen now (game thread only)

	// Cosmonova's metres (across, up, away) to Unreal's centimetres (forward, right, up).
	FVector ToUnreal(double Across, double Up, double Away) { return FVector(Away * 100.0, Across * 100.0, Up * 100.0); }

	const TPair<const char*, FKey> Keys[] = {
		{"left", EKeys::Left}, {"right", EKeys::Right}, {"up", EKeys::Up}, {"down", EKeys::Down}, {"space", EKeys::SpaceBar},
		{"enter", EKeys::Enter}, {"escape", EKeys::Escape}, {"shift", EKeys::LeftShift}, {"control", EKeys::LeftControl},
		{"tab", EKeys::Tab}, {"backspace", EKeys::BackSpace}};
	const TCHAR* Digits[] = {TEXT("Zero"), TEXT("One"), TEXT("Two"), TEXT("Three"), TEXT("Four"), TEXT("Five"), TEXT("Six"), TEXT("Seven"), TEXT("Eight"), TEXT("Nine")};
}

ACosmonovaEye::ACosmonovaEye()
{
	PrimaryActorTick.bCanEverTick = true;
	PrimaryActorTick.TickGroup = TG_PrePhysics;
	bUseControllerRotationPitch = bUseControllerRotationYaw = bUseControllerRotationRoll = false;
	Camera = CreateDefaultSubobject<UCameraComponent>(TEXT("Eye"));
	RootComponent = Camera;
	static ConstructorHelpers::FObjectFinder<UStaticMesh> CubeMesh(TEXT("/Engine/BasicShapes/Cube.Cube"));
	static ConstructorHelpers::FObjectFinder<UStaticMesh> SphereMesh(TEXT("/Engine/BasicShapes/Sphere.Sphere"));
	static ConstructorHelpers::FObjectFinder<UStaticMesh> PlaneMesh(TEXT("/Engine/BasicShapes/Plane.Plane"));
	static ConstructorHelpers::FObjectFinder<UMaterialInterface> BasicPaint(TEXT("/Engine/BasicShapes/BasicShapeMaterial.BasicShapeMaterial"));
	Cube = CubeMesh.Object;
	Sphere = SphereMesh.Object;
	Plane = PlaneMesh.Object;
	Paint = BasicPaint.Object;
}

void ACosmonovaEye::BeginPlay()
{
	Super::BeginPlay();
	if (APlayerController* Player = GetWorld()->GetFirstPlayerController())
	{
		Player->bShowMouseCursor = true;
		Player->SetInputMode(FInputModeGameOnly());
	}
	cosmonova::show_hook = [](const std::string& Text, bool Problem)
	{
		auto& B = cosmonova_unreal::bridge();
		std::lock_guard<std::mutex> Hold(B.lock);
		B.messages.push_back({Text, Problem});
	};
	std::thread([]
	{
		CosmonovaMain();
		auto& B = cosmonova_unreal::bridge();
		std::lock_guard<std::mutex> Hold(B.lock);
		if (B.opened)  // a game that opened a world ends when its program does; otherwise its words stay on the screen
			B.end_asked = true;
	}).detach();  // the program runs on its own; 'reveal the frame' waits for Unreal
}

void ACosmonovaEye::EndPlay(const EEndPlayReason::Type Reason)
{
	auto& B = cosmonova_unreal::bridge();
	{
		std::lock_guard<std::mutex> Hold(B.lock);
		B.lives = false;  // 'the world lives' becomes no, and a waiting 'reveal the frame' goes on
	}
	B.changed.notify_all();
	Super::EndPlay(Reason);
}

UInstancedStaticMeshComponent* ACosmonovaEye::MeshFor(UStaticMesh* Mesh, const FLinearColor& Colour)
{
	FString Key = Mesh->GetName() + Colour.ToString();
	if (TObjectPtr<UInstancedStaticMeshComponent>* Found = Meshes.Find(Key))
		return *Found;
	UInstancedStaticMeshComponent* Made = NewObject<UInstancedStaticMeshComponent>(this);
	Made->SetUsingAbsoluteLocation(true);
	Made->SetUsingAbsoluteRotation(true);
	Made->SetUsingAbsoluteScale(true);
	Made->SetMobility(EComponentMobility::Movable);
	Made->SetStaticMesh(Mesh);
	UMaterialInstanceDynamic* Coat = UMaterialInstanceDynamic::Create(Paint, this);
	Coat->SetVectorParameterValue(TEXT("Color"), Colour);
	Made->SetMaterial(0, Coat);
	Made->SetupAttachment(RootComponent);
	Made->RegisterComponent();
	Made->SetWorldTransform(FTransform::Identity);
	Meshes.Add(Key, Made);
	return Made;
}

void ACosmonovaEye::ReadInput()  // with the bridge locked
{
	auto& B = cosmonova_unreal::bridge();
	APlayerController* Player = GetWorld()->GetFirstPlayerController();
	if (!Player)
		return;
	B.held.clear();
	auto Look = [&](const std::string& Name, const FKey& Key)
	{
		if (Player->IsInputKeyDown(Key))
			B.held.insert(Name);
		if (Player->WasInputKeyJustPressed(Key))
			B.pressed_fresh.insert(Name);
	};
	for (const auto& Pair : Keys)
		Look(Pair.Key, Pair.Value);
	for (char C = 'a'; C <= 'z'; ++C)
		Look(std::string(1, C), FKey(FName(FString::Chr(FChar::ToUpper(TCHAR(C))))));
	for (int D = 0; D < 10; ++D)
		Look(std::string(1, char('0' + D)), FKey(Digits[D]));
	B.mouse_down = Player->IsInputKeyDown(EKeys::LeftMouseButton) ? 1 : 0;
	if (Player->WasInputKeyJustPressed(EKeys::LeftMouseButton))
		B.click_fresh = true;
	float X = 0, Y = 0;
	if (Player->GetMousePosition(X, Y))
	{
		B.mouse_x = X;
		B.mouse_y = Y;
	}
	FVector2D Size;
	if (GEngine && GEngine->GameViewport)
	{
		GEngine->GameViewport->GetViewportSize(Size);
		if (Size.X > 0 && Size.Y > 0)
		{
			B.width_now = Size.X;
			B.height_now = Size.Y;
		}
	}
}

void ACosmonovaEye::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);
	auto& B = cosmonova_unreal::bridge();
	bool Got = false, Open = false, End = false;
	std::string Title;
	int Width = 0, Height = 0;
	std::vector<std::pair<std::string, bool>> Messages;
	{
		std::lock_guard<std::mutex> Hold(B.lock);
		Messages.swap(B.messages);
		if (B.open_asked)
		{
			B.open_asked = false;
			Open = true;
			Title = B.title;
			Width = B.width;
			Height = B.height;
		}
		End = B.end_asked;
		ReadInput();
		if (B.fresh)
		{
			Shown = std::move(B.ready);
			B.fresh = false;
			Got = true;
		}
	}
	if (Got)
		B.changed.notify_all();
	for (const auto& [Text, Problem] : Messages)
	{
		FString Line = UTF8_TO_TCHAR(Text.c_str());
		UE_LOG(LogTemp, Display, TEXT("Cosmonova: %s"), *Line);
		if (GEngine)
			GEngine->AddOnScreenDebugMessage(-1, Problem ? 600.f : 10.f, Problem ? FColor::Red : FColor::White, Line);
	}
	if (Open && GEngine)
	{
		if (UGameUserSettings* Settings = GEngine->GetGameUserSettings())
		{
			Settings->SetFullscreenMode(EWindowMode::Windowed);
			Settings->SetScreenResolution(FIntPoint(Width, Height));
			Settings->ApplyResolutionSettings(false);
		}
		if (GEngine->GameViewport && GEngine->GameViewport->GetWindow().IsValid())
			GEngine->GameViewport->GetWindow()->SetTitle(FText::FromString(UTF8_TO_TCHAR(Title.c_str())));
	}
	if (End)
	{
		UKismetSystemLibrary::QuitGame(this, nullptr, EQuitPreference::Quit, false);
		return;
	}
	if (!Got)
		return;

	// The eye: Cosmonova's turn is Unreal's yaw and its tilt is the pitch; 60 degrees from the top of the picture to the bottom.
	const double* E = Shown.eye;
	SetActorLocationAndRotation(ToUnreal(E[0], E[1], E[2]), FRotator(E[4], E[3], 0));
	double Aspect = B.width_now / FMath::Max(1.0, B.height_now);
	Camera->SetFieldOfView(FMath::RadiansToDegrees(2.0 * FMath::Atan(FMath::Tan(FMath::DegreesToRadians(30.0)) * Aspect)));

	TMap<UInstancedStaticMeshComponent*, TArray<FTransform>> Wanted;
	for (const auto& Pair : Meshes)
		Wanted.Add(Pair.Value.Get());
	for (const cosmonova_unreal::Shape& S : Shown.shapes)
	{
		FVector At = ToUnreal(S.at.X, S.at.Y, S.at.Z);
		FVector Scale = S.kind == 0 ? FVector(S.size.Z, S.size.X, S.size.Y) : FVector(2.0 * S.size.X);  // the meshes are 1 m across
		Wanted.FindOrAdd(MeshFor(S.kind == 0 ? Cube.Get() : Sphere.Get(), S.colour)).Add(FTransform(FRotator::ZeroRotator, At, Scale));
	}
	if (Shown.ground)  // a checkered floor of 2 m tiles around the eye
	{
		const int Reach = 25;
		int CX = FMath::FloorToInt(E[0] / 2.0), CZ = FMath::FloorToInt(E[2] / 2.0);
		UInstancedStaticMeshComponent* A = MeshFor(Plane.Get(), Shown.ground_a);
		UInstancedStaticMeshComponent* C = MeshFor(Plane.Get(), Shown.ground_b);
		for (int I = CX - Reach; I < CX + Reach; ++I)
			for (int J = CZ - Reach; J < CZ + Reach; ++J)
				Wanted.FindOrAdd(((I + J) & 1) ? C : A).Add(FTransform(FRotator::ZeroRotator, ToUnreal(I * 2.0 + 1.0, 0, J * 2.0 + 1.0), FVector(2.0, 2.0, 1.0)));
	}
	for (auto& [Mesh, Transforms] : Wanted)
	{
		int Have = Mesh->GetInstanceCount();
		for (int K = 0; K < Transforms.Num(); ++K)
		{
			if (K < Have)
				Mesh->UpdateInstanceTransform(K, Transforms[K], true, false, true);
			else
				Mesh->AddInstance(Transforms[K], true);
		}
		for (int K = Have - 1; K >= Transforms.Num(); --K)
			Mesh->RemoveInstance(K);
		Mesh->MarkRenderStateDirty();
	}
}

void ACosmonovaHUD::DrawHUD()
{
	Super::DrawHUD();
	if (Shown.shapes.empty() && !Shown.ground)  // a flat game: the background is the colour the window was consumed with
		DrawRect(Shown.sky, 0, 0, Canvas->SizeX, Canvas->SizeY);
	UFont* Font = GEngine ? GEngine->GetLargeFont() : nullptr;
	for (const cosmonova_unreal::Flat& F : Shown.flats)
	{
		switch (F.kind)
		{
		case 0:
			DrawRect(F.colour, F.x, F.y, F.w, F.h);
			break;
		case 1:
			Canvas->K2_DrawPolygon(nullptr, FVector2D(F.x, F.y), FVector2D(F.w, F.w), 32, F.colour);
			break;
		case 2:
			DrawLine(F.x, F.y, F.w, F.h, F.colour, 2.f);
			break;
		default:
			if (Font)
				DrawText(UTF8_TO_TCHAR(F.words.c_str()), F.colour, F.x, F.y, Font, F.w / FMath::Max(1, Font->GetMaxCharHeight()));
		}
	}
}

ACosmonovaGameMode::ACosmonovaGameMode()
{
	DefaultPawnClass = ACosmonovaEye::StaticClass();
	HUDClass = ACosmonovaHUD::StaticClass();
}

void ACosmonovaGameMode::BeginPlay()
{
	Super::BeginPlay();
	UWorld* World = GetWorld();
	// The sun shines from up, a little right and behind, as in the window's 3D.
	FVector Light = ToUnreal(-0.371, -0.743, 0.557).GetSafeNormal();  // the way the light travels: away from the sun
	ADirectionalLight* Sun = World->SpawnActor<ADirectionalLight>(FVector::ZeroVector, Light.Rotation());
	if (Sun)
	{
		Sun->SetActorRotation(Light.Rotation());  // spawning alone left it pointing straight down
		Sun->GetLightComponent()->SetMobility(EComponentMobility::Movable);
		if (UDirectionalLightComponent* SunLight = Cast<UDirectionalLightComponent>(Sun->GetLightComponent()))
			SunLight->SetAtmosphereSunLight(true);
	}
	World->SpawnActor<ASkyAtmosphere>();
	if (ASkyLight* Sky = World->SpawnActor<ASkyLight>())
	{
		USkyLightComponent* SkyLight = Sky->GetLightComponent();
		SkyLight->SetMobility(EComponentMobility::Movable);
		SkyLight->bRealTimeCapture = true;
		SkyLight->RecaptureSky();
	}
	World->SpawnActor<AExponentialHeightFog>();
}
