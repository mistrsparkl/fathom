// The value machine code passes for everything but numbers and yes/no.
#pragma once
#include <algorithm>
#include <functional>
#include <map>
#include <memory>
#include <unordered_map>
#include <string>
#include <vector>

#include <atomic>
struct V;
union Part { double d; V* v; };  // a thing's slot: a number part kept plain (numbers is true), or any other part
struct ThingKind
{
	std::string name;
	std::vector<std::string> fields;
	std::string types;  // 'n' for each number part (kept plain), 't' text, '-' anything else; set once, before typed
	std::vector<Part> start;  // a new thing's parts: 0, "" or nothing (set with types)
	std::atomic<bool> typed{false};
};

struct V  // every value starts like this; numbers are only this
{
	char tag = 'n';  // n number, y yes/no, t text, l list, m table, p place, f flat place, k thing, c command
	bool marked = false;  // the collector reached it
	bool owned = false;  // text only one name holds (cn_append): it may grow in place
	bool numbers = false;  // plain numbers kept in Full's nums
	unsigned char shared = 0;  // how many more places hold it (255: many)
	bool live = false;  // handed out (the collector looks at these only)
	unsigned short slots = 0;  // a thing's room for parts (fixed by where it was made)
	double d = 0;  // a number, or 1 / 0 for yes / no
};

#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
template <typename T>
struct Few  // numbers or values, laid out for machine code
{
	T* data = few;  // (a few kept here, with no allocation)
	uint32_t count = 0, room = 4;  // (32 bits: a smaller value; machine code reads them as i32)
	T few[4];
	Few() = default;
	Few(const Few& o) { *this = o; }
	Few(Few&& o) noexcept
	{
		if (o.data == o.few)
			std::memcpy(few, o.few, sizeof few), count = o.count;
		else
			data = o.data, count = o.count, room = o.room;
		o.data = o.few, o.count = 0, o.room = 4;
	}
	Few& operator=(const Few& o)
	{
		if (this != &o)
		{
			clear();
			reserve(o.count);
			if (o.count)
				std::memcpy(data, o.data, o.count * sizeof(T));
			count = o.count;
		}
		return *this;
	}
	~Few() { if (data != few) std::free(data); }
	static void too_many()
	{
		std::fputs("Fathom: a list can't hold more than 2147483647 items.\n", stderr);
		std::abort();
	}
	void reserve(size_t n)
	{
		if (n <= room)
			return;
		if (n > 0x7fffffffu)  // (machine code indexes with signed 32 bits)
		{
			if (room == 0x7fffffffu)
				too_many();
			n = 0x7fffffffu;
		}
		room = static_cast<uint32_t>(n < 8 ? 8 : n);
		if (data == few)
		{
			T* bigger = static_cast<T*>(std::malloc(room * sizeof(T)));
			std::memcpy(bigger, few, count * sizeof(T));
			data = bigger;
		}
		else
			data = static_cast<T*>(std::realloc(data, room * sizeof(T)));
	}
	void push_back(T x)
	{
		if (count == room)
			reserve(static_cast<size_t>(room) * 2);
		data[count++] = x;
	}
	void insert(T* at, T x)
	{
		size_t k = static_cast<size_t>(at - data);
		push_back(T());
		std::memmove(data + k + 1, data + k, (count - 1 - k) * sizeof(T));
		data[k] = x;
	}
	void erase(T* at)
	{
		std::memmove(at, at + 1, static_cast<size_t>(data + count - at - 1) * sizeof(T));
		--count;
	}
	void resize(size_t n)
	{
		if (n > 0x7fffffffu)
			too_many();
		reserve(n);
		for (size_t k = count; k < n; ++k)
			data[k] = T();
		count = static_cast<uint32_t>(n);
	}
	void clear() { count = 0; }
	void release() { if (data != few) std::free(data); data = few, count = 0, room = 4; }
	size_t size() const { return count; }
	size_t capacity() const { return room; }
	bool empty() const { return count == 0; }
	T& operator[](size_t k) { return data[k]; }
	const T& operator[](size_t k) const { return data[k]; }
	T& back() { return data[count - 1]; }
	const T& back() const { return data[count - 1]; }
	T* begin() const { return data; }
	T* end() const { return data + count; }
};
using Nums = Few<double>;  // a list's plain numbers, or a thing's number parts
using Items = Few<V*>;  // a list's items, or a thing's parts

struct Table  // made when the first entry is put in
{
	using Map = std::unordered_map<std::string, V*>;
	std::unique_ptr<Map> m;
	Table() = default;
	Table(const Table& o) { *this = o; }
	Table& operator=(const Table& o)
	{
		if (this == &o)
			return *this;
		if (o.empty())
			clear();
		else if (m)
			*m = *o.m;
		else
			m = std::make_unique<Map>(*o.m);
		return *this;
	}
	static Map& none() { static Map nothing; return nothing; }  // (never changed)
	Map& have() const { return m ? *m : none(); }
	bool empty() const { return !m || m->empty(); }
	size_t size() const { return m ? m->size() : 0; }
	void clear() { if (m) m->clear(); }
	Map::iterator begin() const { return have().begin(); }
	Map::iterator end() const { return have().end(); }
	Map::iterator find(const std::string& k) const { return have().find(k); }
	size_t count(const std::string& k) const { return m ? m->count(k) : 0; }
	size_t erase(const std::string& k) { return m ? m->erase(k) : 0; }
	V*& operator[](const std::string& k) { return made()[k]; }
	std::pair<Map::iterator, bool> try_emplace(const std::string& k) { return made().try_emplace(k); }
	Map& made() { if (!m) m = std::make_unique<Map>(); return *m; }
};

struct Full : V  // every other value: text, lists, tables, places, things and commands
{
	Nums nums;  // plain numbers, at a fixed place
	Items boxed;  // items or parts, in order: use cn_items
	const ThingKind* kind = nullptr;  // a list of things laid flat: their kind (each thing's parts side by side in nums)
	Table table;  // (in no order: sorted_keys gives them in order)
	double x = 0, y = 0, z = 0;  // a place
	void* command = nullptr;  // a command kept in a list or a table: its machine code
	std::pair<const std::string, V*>* last = nullptr;  // a table's entry found last (most lines use one entry twice or more)
	const V* last_key = nullptr;  // the text it was found with (forgotten at each collection: that text may be freed); set only with last
	V** last_slot = nullptr;  // &last->second (machine code reads it when it has last_key)
};

inline std::vector<const std::pair<const std::string, V*>*> sorted_keys(const Full* f)  // a table's entries, in order of name
{
	std::vector<const std::pair<const std::string, V*>*> out;
	out.reserve(f->table.size());
	for (const auto& e : f->table)
		out.push_back(&e);
	std::sort(out.begin(), out.end(), [](auto* a, auto* b) { return a->first < b->first; });
	return out;
}
struct TextValue : V { std::string s; };  // a text: its own small value (Full has no text)
struct ThingValue : V  // a thing: its kind, then a slot for each part
{
	const ThingKind* kind = nullptr;
	Items* side = nullptr;  // every part boxed, for C++ that wants them so (numbers is false then)
};
inline ThingValue* thing_of(const V* v) { return static_cast<ThingValue*>(const_cast<V*>(v)); }
inline Part* parts_of(const V* v) { return reinterpret_cast<Part*>(reinterpret_cast<char*>(const_cast<V*>(v)) + sizeof(ThingValue)); }
inline bool is_small(char tag) { return tag == 'n' || tag == 'y'; }
inline Full* full(V* v) { return static_cast<Full*>(v); }  // only for a value that isn't a number or a yes/no
inline std::string& text_of(V* v) { return static_cast<TextValue*>(v)->s; }  // a text value's words
inline const std::string& text_of(const V* v) { return static_cast<const TextValue*>(v)->s; }
inline const Full* full(const V* v) { return static_cast<const Full*>(v); }

V* cn_make_text(std::string s);
Items& cn_items(const V* v);  // items, boxed
namespace fathom { struct Problem; }
void cn_set_problem(const fathom::Problem& p);

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
struct CnParked  // around a library word that may wait
{
	CnParked() { cn_park(); }
	~CnParked() { cn_unpark(); }
};

// ---- turning machine values into C++ values for library words, and back
#ifdef FATHOM_CONVERSIONS
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
		return text_of(v);
	else if constexpr (std::is_same_v<T, FVector>)
		return FVector(full(v)->x, full(v)->y, full(v)->z);
	else if constexpr (std::is_same_v<T, FVector2D>)
		return FVector2D(full(v)->x, full(v)->y);
	else if constexpr (cn_is_vector<T>::value)
	{
		T out;
		if constexpr (std::is_same_v<T, std::vector<double>>)
			if (v->numbers)
				return T(full(v)->nums.begin(), full(v)->nums.end());
		for (V* x : cn_items(v))
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

// A command given to a library word.
extern "C" void* cn_command_or_fail(void* command, int line);
extern "C" void cn_keep(V* v);  // held by C++ from now on: the collector keeps it
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
		using Code = Gives (*)(typename cn_machine<A>::type...);
		cn_keep(v);
		return [v](A... a) -> R {
			cn_unpark();  // machine code runs again: the collector waits for it as usual
			struct Again { ~Again() { cn_park(); } } again;
			auto target = reinterpret_cast<Code>(cn_command_or_fail(v, 0));  // each time: it says which names it keeps
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

#ifdef __wasm__
#include <system_error>
// threads in WebAssembly
#define ONE_THREAD "this word starts threads of its own, and a WebAssembly program has only one thread."
#endif
