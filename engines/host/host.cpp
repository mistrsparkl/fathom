// A tiny engine for a Stellanova plugin: the smallest example of what Unity, Unreal and Godot do with one.
// It loads the plugin, starts it, then calls its commands, answering its engine words (here by printing them).
// Build: clang++ -O1 host.cpp -o host.exe    Run: host.exe game.dll
#ifdef _WIN32
#include <windows.h>
#define OPEN(name) LoadLibraryA(name)
#define FIND(lib, name) GetProcAddress(static_cast<HMODULE>(lib), name)
#else
#include <dlfcn.h>
#define OPEN(name) dlopen(name, RTLD_NOW)
#define FIND(lib, name) dlsym(lib, name)
#endif
#include <cstdio>
#include <cstring>

using Output = void (*)(const char* text, int is_problem);
using EngineWord = double (*)(const char* word, const double* numbers, int count, const char* text, double* answers, char* answer_text, int room);
using Start = int (*)(Output, EngineWord);
using Call = int (*)(const char* command, double me, const double* numbers, int count, double* answer);

static void show(const char* text, int is_problem) { std::printf("%s%s\n", is_problem ? "problem: " : "", text); }

static double word(const char* w, const double* numbers, int count, const char* text, double* answers, char* answer_text, int room)
{
	std::printf("  [%s", w);
	for (int k = 0; k < count; ++k)
		std::printf(" %g", numbers[k]);
	if (*text)
		std::printf(" \"%s\"", text);
	std::printf("]\n");
	if (!std::strcmp(w, "place"))
		answers[0] = 1, answers[1] = 2, answers[2] = 3;
	if (!std::strcmp(w, "name"))
		std::snprintf(answer_text, room, "%s", numbers[0] == 7 ? "Player" : "Coin");
	if (!std::strcmp(w, "copy"))
		return 9;
	if (!std::strcmp(w, "frame time"))
		return 0.5;
	return 0;
}

int main(int count, char** given)
{
	void* plugin = OPEN(count > 1 ? given[1] : "game.dll");
	if (!plugin)
		return std::printf("can't load the plugin\n"), 1;
	auto start = reinterpret_cast<Start>(FIND(plugin, "stellanova_start"));
	auto call = reinterpret_cast<Call>(FIND(plugin, "stellanova_call"));
	std::printf("start %d\n", start(show, word));
	std::printf("begin %d\n", call("begin", 5, nullptr, 0, nullptr));
	double seconds = 0.5, other = 7, answer = 0;
	std::printf("every frame %d\n", call("every frame", 5, &seconds, 1, nullptr));
	std::printf("touched %d\n", call("touched", 5, &other, 1, nullptr));
	std::printf("doubled %d", call("doubled", 5, &seconds, 1, &answer));
	std::printf(" %g\n", answer);
	std::printf("missing %d\n", call("missing", 5, nullptr, 0, nullptr));
}
