// What an Imagination program (on its own thread) and Unreal (on the game thread) share.
#pragma once
#include "CoreMinimal.h"
#include <condition_variable>
#include <mutex>
#include <set>
#include <string>
#include <utility>
#include <vector>

namespace imagine_unreal
{
	struct Shape  // a 3D shape, in Imagination's metres: across, up, away
	{
		int kind;  // 0 a block, 1 a ball
		FVector at;
		FVector size;  // a block's width, height and depth; a ball's radius
		FLinearColor colour;
	};

	struct Flat  // flat drawing on top of the picture, in dots from the top left
	{
		int kind;  // 0 a box (x, y, width, height), 1 a circle (x, y, radius), 2 a line (x, y to w, h), 3 words (x, y, text size)
		float x, y, w, h;
		FLinearColor colour;
		std::string words;
	};

	struct Frame
	{
		std::vector<Shape> shapes;
		std::vector<Flat> flats;
		double eye[5] = {0, 1.5, -6, 0, 0};  // across, up, away, turn, tilt
		bool ground = false;
		FLinearColor ground_a = FLinearColor::Green, ground_b = FLinearColor::Green;
		FLinearColor sky = FLinearColor::Black;
	};

	struct Bridge
	{
		std::mutex lock;
		std::condition_variable changed;
		Frame building, ready;  // the frame the program is etching, and the one waiting for Unreal
		bool fresh = false;     // ready has not been taken by Unreal yet
		bool opened = false, open_asked = false, lives = true, end_asked = false;
		std::string title;
		int width = 800, height = 600;
		double width_now = 800, height_now = 600, mouse_x = 0, mouse_y = 0, mouse_down = 0, clicked_now = 0;
		std::set<std::string> held, pressed, pressed_fresh;
		bool click_fresh = false;
		std::vector<std::pair<std::string, bool>> messages;  // scrawled lines and problems, for the screen
	};

	inline Bridge& bridge()
	{
		static Bridge b;
		return b;
	}
}
