// What a program made into machine code (by machine.py) calls: plain C functions over cosmonova.h.
// Compiled once into runtime/built/cosmonova_machine.obj; a program's own code never becomes C++.
#include "cosmonova.h"

struct cn_text_value
{
	std::string s;
};
using T = cn_text_value*;

// shortcut: text values are never freed; upgrade to reference counting before long-running programs make text in loops.
static T made(std::string s) { return new cn_text_value{std::move(s)}; }

// A problem in one of these stops the program with its line, as a problem that isn't caught always does.
#define GUARDED(body) try { body } catch (const cosmonova::Problem& problem) { cosmonova::report(problem); std::exit(1); }

extern "C"
{
	void cn_begin(int count, char** given)
	{
		cosmonova::begin({}, count, given);
	}
	void cn_add_file(const char* name) { cosmonova::files.push_back(name); }
	void cn_end() { std::cout << std::flush; }

	T cn_text(const char* bytes, long long size) { return made(std::string(bytes, static_cast<size_t>(size))); }
	T cn_text_number(double d) { return made(cosmonova::text(d)); }
	T cn_text_yesno(bool b) { return made(cosmonova::text(b)); }
	T cn_join(T a, T b) { return made(a->s + b->s); }
	bool cn_same_text(T a, T b) { return a->s == b->s; }
	void cn_say(T t) { cosmonova::say({t->s}); }

	T cn_ask_text(T question) { return made(cosmonova::ask_text(question->s)); }
	double cn_ask_number(T question) { return cosmonova::ask_number(question->s); }
	bool cn_ask_yes_no(T question) { return cosmonova::ask_yes_no(question->s); }

	long long cn_repeats(double count)  // 'repeat N times': how many rounds (none for not a number or infinity)
	{
		return std::isfinite(count) ? static_cast<long long>(count) : 0;
	}
	double cn_random(double lo, double hi, int line)
	{
		GUARDED(return cosmonova::random(lo, hi, line);)
	}
	double cn_letters(T t) { return cosmonova::letters(t->s); }
	double cn_to_number(T t, int line)
	{
		GUARDED(return cosmonova::to_number(t->s, line);)
	}
	double cn_rounded(double x, double places, int line)
	{
		GUARDED(return cosmonova::rounded(x, places, line);)
	}
}
