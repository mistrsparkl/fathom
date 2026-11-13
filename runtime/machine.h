// The one kind of value machine code passes around for everything that isn't a number or yes/no (see machine.cpp).
// Library words made into machine code (machine.py's library wrappers) turn these into C++ values and back.
#pragma once
#include <map>
#include <string>
#include <vector>

struct ThingKind
{
	std::string name;
	std::vector<std::string> fields;
};

struct V
{
	char tag = 'n';  // n number, y yes or no, t text, l list, m table, p place, f flat place, k thing, c command
	double d = 0;  // a number, or 1 / 0 for yes / no
	double x = 0, y = 0, z = 0;  // a place
	std::string s;  // text
	std::vector<V*> items;  // a list's items, or a thing's parts (in the order they were described)
	std::map<std::string, V*> table;
	const ThingKind* kind = nullptr;
	void* command = nullptr;  // a command kept in a list or a table: its machine code
};

V* cn_make_text(std::string s);
namespace cosmonova { struct Problem; }
void cn_set_problem(const cosmonova::Problem& p);

extern "C"
{
	V* cn_box_number(double d);
	V* cn_box_yesno(bool b);
	V* cn_list_new();
	V* cn_table_new();
	V* cn_place(double x, double y, double z);
	V* cn_flat(double x, double y);
}

// ---------------------------------------------------------------- for library words
// A library word's own C++ takes C++ values (std::string, std::vector<double>, FVector, ...): these turn machine
// values into them and back. Only used where cosmonova.h is included first.
#ifdef COSMONOVA_CONVERSIONS
template <typename T> struct cn_is_vector : std::false_type {};
template <typename T> struct cn_is_vector<std::vector<T>> : std::true_type { using item = T; };
template <typename T> struct cn_is_table : std::false_type {};
template <typename T> struct cn_is_table<std::map<std::string, T>> : std::true_type { using item = T; };

template <typename T>
T cn_to_cpp(V* v)
{
	if constexpr (std::is_same_v<T, double>)
		return v->d;
	else if constexpr (std::is_same_v<T, bool>)
		return v->d != 0;
	else if constexpr (std::is_same_v<T, std::string>)
		return v->s;
	else if constexpr (std::is_same_v<T, FVector>)
		return FVector(v->x, v->y, v->z);
	else if constexpr (std::is_same_v<T, FVector2D>)
		return FVector2D(v->x, v->y);
	else if constexpr (cn_is_vector<T>::value)
	{
		T out;
		for (V* x : v->items)
			out.push_back(cn_to_cpp<typename cn_is_vector<T>::item>(x));
		return out;
	}
	else if constexpr (cn_is_table<T>::value)
	{
		T out;
		for (const auto& [key, x] : v->table)
			out[key] = cn_to_cpp<typename cn_is_table<T>::item>(x);
		return out;
	}
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
		out->items.push_back(cn_from_cpp(x));
	return out;
}
template <typename T>
V* cn_from_cpp(const std::map<std::string, T>& table)
{
	V* out = cn_table_new();
	for (const auto& [key, x] : table)
		out->table[key] = cn_from_cpp(x);
	return out;
}
#endif
