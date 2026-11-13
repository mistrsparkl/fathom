// The one kind of value machine code passes around for everything that isn't a number or yes/no (see machine.cpp).
// Library words made into machine code (machine.py's library wrappers) turn these into C++ values and back.
#pragma once
#include <functional>
#include <map>
#include <string>
#include <vector>

struct ThingKind
{
	std::string name;
	std::vector<std::string> fields;
};

struct V  // every value begins like this, and a number or a yes/no is only this (so a million numbers stay small)
{
	char tag = 'n';  // n number, y yes or no, t text, l list, m table, p place, f flat place, k thing, c command
	bool marked = false;  // the collector reached it
	double d = 0;  // a number, or 1 / 0 for yes / no
};

struct Full : V  // every other value: text, lists, tables, places, things and commands
{
	double x = 0, y = 0, z = 0;  // a place
	std::string s;  // text
	std::vector<V*> items;  // a list's items, or a thing's parts (in the order they were described)
	std::map<std::string, V*> table;
	const ThingKind* kind = nullptr;
	void* command = nullptr;  // a command kept in a list or a table: its machine code
};

inline bool is_small(char tag) { return tag == 'n' || tag == 'y'; }
inline Full* full(V* v) { return static_cast<Full*>(v); }  // only for a value that isn't a number or a yes/no
inline const Full* full(const V* v) { return static_cast<const Full*>(v); }

V* cn_make_text(std::string s);
namespace stellanova { struct Problem; }
void cn_set_problem(const stellanova::Problem& p);

extern "C"
{
	V* cn_box_number(double d);
	V* cn_box_yesno(bool b);
	V* cn_list_new();
	V* cn_table_new();
	V* cn_place(double x, double y, double z);
	V* cn_flat(double x, double y);
	void cn_park();
	void cn_unpark();
	void cn_hold_push(V* list, V* x);
	void cn_hold_put(V* table, const char* key, V* x);
}
struct CnParked  // around a library word's own C++: it may wait, so the collector needn't wait for it
{
	CnParked() { cn_park(); }
	~CnParked() { cn_unpark(); }
};

// ---------------------------------------------------------------- for library words
// A library word's own C++ takes C++ values (std::string, std::vector<double>, FVector, ...): these turn machine
// values into them and back. Only used where stellanova.h is included first.
#ifdef STELLANOVA_CONVERSIONS
template <typename T> struct cn_is_vector : std::false_type {};
template <typename T> struct cn_is_vector<std::vector<T>> : std::true_type { using item = T; };
template <typename T> struct cn_is_table : std::false_type {};
template <typename T> struct cn_is_table<std::map<std::string, T>> : std::true_type { using item = T; };

template <typename T> struct cn_is_function : std::false_type {};

template <typename T>
T cn_to_cpp(V* v)
{
	if constexpr (std::is_same_v<T, double>)
		return v->d;
	else if constexpr (std::is_same_v<T, bool>)
		return v->d != 0;
	else if constexpr (std::is_same_v<T, std::string>)
		return full(v)->s;
	else if constexpr (std::is_same_v<T, FVector>)
		return FVector(full(v)->x, full(v)->y, full(v)->z);
	else if constexpr (std::is_same_v<T, FVector2D>)
		return FVector2D(full(v)->x, full(v)->y);
	else if constexpr (cn_is_vector<T>::value)
	{
		T out;
		for (V* x : full(v)->items)
			out.push_back(cn_to_cpp<typename cn_is_vector<T>::item>(x));
		return out;
	}
	else if constexpr (cn_is_table<T>::value)
	{
		T out;
		for (const auto& [key, x] : full(v)->table)
			out[key] = cn_to_cpp<typename cn_is_table<T>::item>(x);
		return out;
	}
	else if constexpr (cn_is_function<T>::value)
		return cn_is_function<T>::make(v);
	else
		static_assert(sizeof(T) == 0, "this kind can't be given to a library word in machine code yet");
}

inline V* cn_from_cpp(double d) { return cn_box_number(d); }
inline V* cn_from_cpp(bool b) { return cn_box_yesno(b); }
inline V* cn_from_cpp(const std::string& s) { return cn_make_text(s); }
inline V* cn_from_cpp(const char* s) { return cn_make_text(s); }
inline V* cn_from_cpp(const FVector& p) { return cn_place(p.X, p.Y, p.Z); }
inline V* cn_from_cpp(const FVector2D& p) { return cn_flat(p.X, p.Y); }
template <typename T>
V* cn_from_cpp(const std::vector<T>& items)
{
	V* out = cn_list_new();
	for (const T& x : items)
		cn_hold_push(out, cn_from_cpp(x));
	return out;
}
template <typename T>
V* cn_from_cpp(const std::map<std::string, T>& table)
{
	V* out = cn_table_new();
	for (const auto& [key, x] : table)
		cn_hold_put(out, key.c_str(), cn_from_cpp(x));
	return out;
}

// A command given to a library word (like 'serve the web with (8080, the command answer)'): C++ calls its machine code.
extern "C" void* cn_command_or_fail(void* command, int line);
void cn_rethrow();  // a problem in the command: thrown again, as a C++ problem
template <typename T> struct cn_machine { using type = V*; };
template <> struct cn_machine<double> { using type = double; };
template <> struct cn_machine<bool> { using type = bool; };
template <typename T>
typename cn_machine<T>::type cn_to_machine(const T& x)
{
	if constexpr (std::is_same_v<T, double> || std::is_same_v<T, bool>)
		return x;
	else
		return cn_from_cpp(x);
}
template <typename R, typename... A>
struct cn_is_function<std::function<R(A...)>> : std::true_type
{
	static std::function<R(A...)> make(V* v)
	{
		using Gives = std::conditional_t<std::is_void_v<R>, void, typename cn_machine<std::conditional_t<std::is_void_v<R>, double, R>>::type>;
		auto target = reinterpret_cast<Gives (*)(typename cn_machine<A>::type...)>(full(v)->command);
		return [target](A... a) -> R {
			cn_unpark();  // machine code runs again: the collector waits for it as usual
			struct Again { ~Again() { cn_park(); } } again;
			cn_command_or_fail(reinterpret_cast<void*>(target), 0);
			cn_rethrow();
			if constexpr (std::is_void_v<R>)
			{
				target(cn_to_machine(a)...);
				cn_rethrow();
			}
			else
			{
				auto out = target(cn_to_machine(a)...);
				cn_rethrow();
				if constexpr (std::is_same_v<R, double> || std::is_same_v<R, bool>)
					return out;
				else
					return cn_to_cpp<R>(out);
			}
		};
	}
};
#endif
