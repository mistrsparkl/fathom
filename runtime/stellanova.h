// What every Stellanova program can use. Included by the C++ that stellanova.py writes.
#pragma once
#include <algorithm>
#include <cmath>
#include <cstdio>
#include <filesystem>
#include <fstream>
#include <initializer_list>
#include <map>
#include <cstring>
#include <charconv>
#include <type_traits>
#include <iostream>
#include <random>
#include <sstream>
#include <string>
#include <functional>
#include <mutex>
#include <thread>
#include <vector>

#ifdef STELLANOVA_IN_UNREAL
#include "CoreMinimal.h"  // Unreal's own FVector, FVector2D and FMath
#pragma warning(disable: 4702)  // Unreal treats warnings as mistakes; a command's last 'return' can be one nobody reaches
#else
// The same maths names Unreal has, so a script means the same thing in a program and in Unreal.
namespace FMath
{
	inline double Clamp(double x, double lo, double hi) { return std::min(std::max(x, lo), hi); }
	inline double Min(double a, double b) { return std::min(a, b); }
	inline double Max(double a, double b) { return std::max(a, b); }
	inline double Sqrt(double x) { return std::sqrt(x); }
	inline double Abs(double x) { return std::fabs(x); }
	inline double Atan2(double y, double x) { return std::atan2(y, x); }
	inline double RadiansToDegrees(double r) { return r * 180.0 / 3.14159265358979323846; }
	inline double UnwindDegrees(double a)
	{
		a = std::fmod(a, 360.0);
		if (a > 180.0) a -= 360.0;
		if (a < -180.0) a += 360.0;
		return a;
	}
}

// Places, with the same names Unreal uses, so a script means the same thing in a program and in Unreal.
struct FVector
{
	double X = 0, Y = 0, Z = 0;
	FVector() = default;
	FVector(double x, double y, double z) : X(x), Y(y), Z(z) {}
	static const FVector ZeroVector;
	double Size() const { return std::sqrt(X * X + Y * Y + Z * Z); }
	FVector operator+(const FVector& o) const { return {X + o.X, Y + o.Y, Z + o.Z}; }
	FVector operator-(const FVector& o) const { return {X - o.X, Y - o.Y, Z - o.Z}; }
	FVector operator*(double k) const { return {X * k, Y * k, Z * k}; }
	FVector operator/(double k) const { return {X / k, Y / k, Z / k}; }
	FVector operator-() const { return {-X, -Y, -Z}; }
	bool operator==(const FVector&) const = default;
};
inline const FVector FVector::ZeroVector{};

struct FVector2D
{
	double X = 0, Y = 0;
	FVector2D() = default;
	FVector2D(double x, double y) : X(x), Y(y) {}
	explicit FVector2D(const FVector& v) : X(v.X), Y(v.Y) {}
	static const FVector2D ZeroVector;
	double Size() const { return std::sqrt(X * X + Y * Y); }
	FVector2D operator+(const FVector2D& o) const { return {X + o.X, Y + o.Y}; }
	FVector2D operator-(const FVector2D& o) const { return {X - o.X, Y - o.Y}; }
	FVector2D operator*(double k) const { return {X * k, Y * k}; }
	FVector2D operator/(double k) const { return {X / k, Y / k}; }
	FVector2D operator-() const { return {-X, -Y}; }
	bool operator==(const FVector2D&) const = default;
};
inline const FVector2D FVector2D::ZeroVector{};

#ifndef __wasm__
extern "C" __declspec(dllimport) int __stdcall SetConsoleOutputCP(unsigned int);
extern "C" __declspec(dllimport) int __stdcall SetConsoleCP(unsigned int);
#endif
#endif

namespace stellanova
{
	inline std::vector<std::string> files;  // the program's script, then each script it uses

	// Called first by every program: text is UTF-8, so the console should show it as UTF-8.
	inline std::vector<std::string> arguments;  // the words typed after the program's name
	// Where scrawl's lines and problems go when there is no console (in Unreal): text, and whether it is a problem.
	inline std::function<void(const std::string&, bool)> show_hook;
	inline void begin(std::initializer_list<std::string> scripts, int count = 0, char** given = nullptr)
	{
		files = scripts;
		for (int k = 1; k < count; ++k)
			arguments.push_back(given[k]);
#if !defined(STELLANOVA_IN_UNREAL) && !defined(__wasm__)
		SetConsoleOutputCP(65001);
		SetConsoleCP(65001);
#endif
	}

	inline std::string text(const std::string& s) { return s; }
	inline std::string text(double d);
	inline std::string text(const FVector& v) { return text(v.X) + " horizontal " + text(v.Y) + " vertical " + text(v.Z) + " depth"; }
	inline std::string text(const FVector2D& v) { return text(v.X) + " horizontal " + text(v.Y) + " vertical"; }
	inline std::string text(bool b) { return b ? "yes" : "no"; }
	inline std::string text(double d)
	{
		if (std::isnan(d))
			return "not a number";
		if (std::isinf(d))
			return d > 0 ? "infinity" : "-infinity";
		// Whole numbers show as "5", not "5.0" or "5e+00".
		if (std::floor(d) == d && std::fabs(d) < 1e21)
		{
			if (d == 0)
				return "0";  // not "-0"
			char digits[32];
			std::snprintf(digits, sizeof digits, "%.0f", d);
			return digits;
		}
		std::ostringstream out;
		out.precision(15);
		out << d;
		return out.str();
	}

	template <typename T> std::string text(const std::vector<T>& items);
	template <typename R, typename... A> std::string text(const std::function<R(A...)>&) { return "a command"; }
	template <typename T> std::string text(const std::map<std::string, T>& table);
	template <typename T> struct is_group : std::false_type {};
	template <typename T> struct is_group<std::vector<T>> : std::true_type {};
	template <typename T> struct is_group<std::map<std::string, T>> : std::true_type {};

	// A list or table inside another one is shown in brackets, so its items stay together.
	template <typename T>
	std::string part_text(const T& x)
	{
		if constexpr (is_group<T>::value)
			return x.empty() ? text(x) : "(" + text(x) + ")";
		else
			return text(x);
	}

	template <typename T>
	std::string text(const std::vector<T>& items)
	{
		if (items.empty())
			return "(nothing)";
		std::string out;
		for (size_t k = 0; k < items.size(); ++k)
			out += (k ? ", " : "") + part_text(items[k]);
		return out;
	}

	template <typename T>
	std::string text(const std::map<std::string, T>& table)
	{
		if (table.empty())
			return "(nothing)";
		std::string out;
		for (const auto& [key, value] : table)
			out += (out.empty() ? "" : ", ") + key + ": " + part_text(value);
		return out;
	}

	// Something went wrong while the program ran: say which line, in plain words, and stop.
	// What went wrong, and on which line. 'try:' can catch it; otherwise the program stops and reports it.
	struct Problem
	{
		int line;
		std::string message;
		std::string kind;  // a kind of problem of the program's own ('raise a fuel problem with'), or ""
	};

	inline std::recursive_mutex& named_lock(const std::string& name)  // 'holding the lock "total":'
	{
		static std::mutex guard;
		static std::map<std::string, std::unique_ptr<std::recursive_mutex>> locks;
		std::lock_guard<std::mutex> hold(guard);
		auto& at = locks[name];
		if (!at)
			at = std::make_unique<std::recursive_mutex>();
		return *at;
	}

	struct Held  // holds a named lock until the end of the lines it is for
	{
		std::recursive_mutex& m;
		explicit Held(const std::string& name) : m(named_lock(name)) { m.lock(); }
		~Held() { m.unlock(); }
		Held(const Held&) = delete;
	};

	[[noreturn]] inline void fail(int line, const std::string& message, const std::string& kind = "")
	{
		throw Problem{line, message, kind};
	}

	template <typename F, typename... A>
	auto invoke(const F& f, int line, A&&... a)
	{
		if (!f)
			fail(line, "there is no command in it yet: set it to one first, like 'set f to the command double'.");
		return f(std::forward<A>(a)...);
	}
	template <typename R, typename T, typename F>
	std::vector<R> changed_by(const std::vector<T>& items, const F& f, int line)
	{
		std::vector<R> out;
		for (const T& x : items)
			out.push_back(invoke(f, line, x));
		return out;
	}
	template <typename T, typename F>
	std::vector<T> kept_by(const std::vector<T>& items, const F& f, int line)
	{
		std::vector<T> out;
		for (const T& x : items)
			if (invoke(f, line, x))
				out.push_back(x);
		return out;
	}

	inline void report(const Problem& problem)
	{
		if (show_hook)
		{
			std::string where = problem.line < 100000 || problem.line / 100000 >= static_cast<int>(files.size())
				? "Line " + std::to_string(problem.line) : files[problem.line / 100000] + " line " + std::to_string(problem.line % 100000);
			show_hook(where + ": " + problem.message, true);
			return;
		}
		std::cout << std::flush;
		if (problem.line < 100000 || problem.line / 100000 >= static_cast<int>(files.size()))
			std::cerr << "Line " << problem.line;
		else
			std::cerr << files[problem.line / 100000] << " line " << problem.line % 100000;
		std::cerr << ": " << problem.message << std::endl;
	}
	inline std::vector<std::thread> others;  // commands running alongside the rest ('meanwhile ...')
	inline std::mutex others_lock;
	template <typename F>
	void meanwhile(F f)
	{
		std::lock_guard<std::mutex> hold(others_lock);
		others.emplace_back([f]()
		{
			try
			{
				f();
			}
			catch (const Problem& problem)
			{
				report(problem);
				std::fflush(stdout);
				std::_Exit(1);
			}
		});
	}
	inline void wait_for_others()
	{
		for (;;)
		{
			std::thread other;
			{
				std::lock_guard<std::mutex> hold(others_lock);
				auto it = std::find_if(others.begin(), others.end(), [](const std::thread& t) { return t.get_id() != std::this_thread::get_id(); });
				if (it == others.end())
					return;
				other = std::move(*it);
				others.erase(it);
			}
			other.join();
		}
	}

	template <typename T>
	size_t index_of(const std::vector<T>& items, double number, int line)
	{
		if (std::floor(number) != number || number < 1 || number > static_cast<double>(items.size()))
			fail(line, "there is no item " + text(number) + " in a list of " + text(static_cast<double>(items.size())) +
				(items.size() == 1 ? " item." : " items.") + " Items are counted from 1.");
		return static_cast<size_t>(number) - 1;
	}

	template <typename T>
	T& at(std::vector<T>& items, double number, int line) { return items[index_of(items, number, line)]; }

	inline double power(double a, double b, int line)
	{
		double out = std::pow(a, b);
		if (std::isinf(out) || std::isnan(out))
			fail(line, text(a) + " to the power " + text(b) + " can't be worked out (it is too big, or not a real number).");
		return out;
	}

	inline double bits(int op, double a, double b, int line)  // and, or, exclusive or, shift left, shift right
	{
		const double limit = 9007199254740992.0;
		for (double x : {a, b})
			if (x != std::floor(x) || std::fabs(x) >= limit)
				fail(line, "bits need whole numbers smaller than 9007199254740992, not " + text(x) + ".");
		long long x = static_cast<long long>(a), y = static_cast<long long>(b);
		if ((op == 3 || op == 4) && (y < 0 || y > 63))
			fail(line, "I can shift by 0 to 63 places, not " + std::to_string(y) + ".");
		long double out = op == 0 ? x & y : op == 1 ? x | y : op == 2 ? x ^ y : op == 3 ? static_cast<long double>(x) * std::pow(2.0L, static_cast<long double>(y)) : static_cast<long double>(x >> y);
		if (std::fabs(out) >= limit)
			fail(line, "that makes a number too big for bits (" + text(static_cast<double>(out)) + ").");
		return static_cast<double>(out);
	}

	template <typename T>
	const T& at(const std::vector<T>& items, double number, int line) { return items[index_of(items, number, line)]; }

	template <typename T>
	void remove_item(std::vector<T>& items, double number, int line) { items.erase(items.begin() + index_of(items, number, line)); }
	template <typename T>
	void insert_item(std::vector<T>& items, double number, const T& x, int line)
	{
		if (number == static_cast<double>(items.size()) + 1) items.push_back(x);
		else items.insert(items.begin() + index_of(items, number, line), x);
	}

	template <typename T>
	void remove_value(std::vector<T>& items, const T& value)
	{
		auto found = std::find(items.begin(), items.end(), value);
		if (found != items.end())
			items.erase(found);
	}

	template <typename T>
	bool contains(const std::vector<T>& items, const T& value) { return std::find(items.begin(), items.end(), value) != items.end(); }

	inline bool contains(const std::string& text, const std::string& part) { return text.find(part) != std::string::npos; }

	template <typename T>
	T& entry(std::map<std::string, T>& table, const std::string& key, int line)
	{
		auto found = table.find(key);
		if (found == table.end())
			fail(line, "there is no entry \"" + key + "\" in the table.");
		return found->second;
	}

	template <typename T>
	const T& entry(const std::map<std::string, T>& table, const std::string& key, int line)
	{
		auto found = table.find(key);
		if (found == table.end())
			fail(line, "there is no entry \"" + key + "\" in the table.");
		return found->second;
	}

	template <typename T>
	void remove_entry(std::map<std::string, T>& table, const std::string& key, int line)
	{
		if (!table.erase(key))
			fail(line, "there is no entry \"" + key + "\" in the table to remove.");
	}

	template <typename T>
	bool contains(const std::map<std::string, T>& table, const std::string& key) { return table.count(key) > 0; }

	template <typename T>
	std::vector<std::string> keys(const std::map<std::string, T>& table)
	{
		std::vector<std::string> out;
		for (const auto& kv : table)
			out.push_back(kv.first);
		return out;
	}

	// 'for each' walks a copy, so changing the list inside the loop is safe.
	template <typename T>
	std::vector<T> copy(const std::vector<T>& items) { return items; }

	inline double rounded(double x, double places, int line)
	{
		if (std::floor(places) != places || places < 0 || places > 15)
			fail(line, "I can round to 0 to 15 places, not " + text(places) + ".");
		if (!std::isfinite(x))
			return x;
		double scale = std::pow(10.0, places);  // halves go away from zero, as taught at school
		return std::copysign(std::floor(std::fabs(x) * scale + 0.5) / scale, x);
	}

	inline double to_number(const std::string& s, int line)
	{
		std::istringstream in(s);
		double d;
		char extra;
		if (in >> d && !(in >> extra))
			return d;
		fail(line, "\"" + s + "\" is not a number.");
	}

	inline std::vector<std::string> lines_of(const std::string& s)
	{
		std::vector<std::string> out;
		std::istringstream in(s);
		std::string line;
		while (std::getline(in, line))
		{
			if (!line.empty() && line.back() == '\r')
				line.pop_back();
			out.push_back(line);
		}
		return out;
	}

	inline std::vector<std::string> words_of(const std::string& s)
	{
		std::vector<std::string> out;
		std::istringstream in(s);
		std::string word;
		while (in >> word)
			out.push_back(word);
		return out;
	}

	inline bool file_exists(const std::string& path) { return std::filesystem::is_regular_file(std::filesystem::u8path(path)); }

	inline std::string read_file(const std::string& path, int line)
	{
		std::ifstream in(std::filesystem::u8path(path), std::ios::binary);
		if (!in)
			fail(line, "there is no file called \"" + path + "\" (or it can't be opened).");
		std::ostringstream all;
		all << in.rdbuf();
		return all.str();
	}

	inline std::vector<std::string> read_lines(const std::string& path, int line) { return lines_of(read_file(path, line)); }

	inline void write_file(const std::string& path, const std::string& s, int line)
	{
		std::ofstream out(std::filesystem::u8path(path), std::ios::binary);
		if (!(out << s))
			fail(line, "I couldn't write the file \"" + path + "\".");
	}

	// ---- saving and loading (save ... to file / load ... from file), as JSON, written exactly as the direct way writes it.
	inline std::string saved_number(double x, int line)
	{
		if (!std::isfinite(x))
			fail(line, "I can't save infinity or not a number.");
		char b[64];
		if (x == std::floor(x) && std::fabs(x) < 1e16)
		{
			std::snprintf(b, sizeof b, "%.0f", x == 0 ? 0.0 : x);
			return b;
		}
		// Shortest digits that read back the same, laid out the way Python's repr does.
		auto r = std::to_chars(b, b + sizeof b, x, std::chars_format::scientific);
		std::string sci(b, r.ptr);
		size_t e = sci.find('e');
		int exp = std::atoi(sci.c_str() + e + 1);
		std::string sign = sci[0] == '-' ? "-" : "", digits;
		for (size_t k = sign.size(); k < e; ++k)
			if (sci[k] != '.')
				digits += sci[k];
		if (exp >= -4 && exp < 16)
		{
			if (exp < 0)
				return sign + "0." + std::string(-exp - 1, '0') + digits;
			return sign + digits.substr(0, exp + 1) + "." + digits.substr(exp + 1);
		}
		char tail[16];
		std::snprintf(tail, sizeof tail, "e%c%02d", exp < 0 ? '-' : '+', std::abs(exp));
		return sign + digits.substr(0, 1) + (digits.size() > 1 ? "." + digits.substr(1) : "") + tail;
	}

	inline void save(std::string& out, double x, int line) { out += saved_number(x, line); }
	inline void save(std::string& out, bool x, int) { out += x ? "true" : "false"; }
	inline void save(std::string& out, const std::string& s, int)
	{
		out += '"';
		for (unsigned char c : s)
		{
			switch (c)
			{
			case '"': out += "\\\""; break;
			case '\\': out += "\\\\"; break;
			case '\n': out += "\\n"; break;
			case '\r': out += "\\r"; break;
			case '\t': out += "\\t"; break;
			case '\b': out += "\\b"; break;
			case '\f': out += "\\f"; break;
			default:
				if (c < 0x20)
				{
					char u[8];
					std::snprintf(u, sizeof u, "\\u%04x", c);
					out += u;
				}
				else
					out += static_cast<char>(c);
			}
		}
		out += '"';
	}
	inline void save(std::string& out, const FVector& v, int line) { out += "[" + saved_number(v.X, line) + ", " + saved_number(v.Y, line) + ", " + saved_number(v.Z, line) + "]"; }
	inline void save(std::string& out, const FVector2D& v, int line) { out += "[" + saved_number(v.X, line) + ", " + saved_number(v.Y, line) + "]"; }
	template <typename R, typename... A> void save(std::string&, const std::function<R(A...)>&, int line) { fail(line, "I can't save a command in a file."); }
	template <typename T> void save(std::string& out, const std::vector<T>& items, int line);
	template <typename T> void save(std::string& out, const std::map<std::string, T>& table, int line);
	template <typename T> void save(std::string& out, const std::vector<T>& items, int line)
	{
		out += "[";
		for (size_t k = 0; k < items.size(); ++k)
		{
			if (k)
				out += ", ";
			save(out, items[k], line);
		}
		out += "]";
	}
	template <typename T> void save(std::string& out, const std::map<std::string, T>& table, int line)
	{
		out += "{";
		bool first = true;
		for (const auto& [key, value] : table)
		{
			if (!first)
				out += ", ";
			first = false;
			save(out, key, line);
			out += ": ";
			save(out, value, line);
		}
		out += "}";
	}

	// JSON read back in, before it is turned into a value of the right kind.
	struct SavedData
	{
		enum Type { Nothing, Number, YesNo, Text, List, Table } type = Nothing;
		double number = 0;
		bool yes = false;
		std::string words;
		std::vector<SavedData> items;
		std::vector<std::pair<std::string, SavedData>> parts;
		const SavedData* part(const std::string& key) const
		{
			for (auto it = parts.rbegin(); it != parts.rend(); ++it)  // the last one wins, as in Python
				if (it->first == key)
					return &it->second;
			for (auto it = parts.rbegin(); it != parts.rend(); ++it)  // a web service's "windSpeed" or "wind_speed" is 'wind speed'
				if (loose(it->first) == loose(key))
					return &it->second;
			return nullptr;
		}
		static std::string loose(const std::string& key)
		{
			std::string out;
			for (char c : key)
				if (c != ' ' && c != '_' && c != '-')
					out += static_cast<char>(c >= 'A' && c <= 'Z' ? c - 'A' + 'a' : c);
			return out;
		}
	};

	struct SavedReader
	{
		const std::string& s;
		size_t i = 0;
		int depth = 0;

		void space()
		{
			while (i < s.size() && (s[i] == ' ' || s[i] == '\t' || s[i] == '\n' || s[i] == '\r'))
				++i;
		}
		bool word(const char* w)
		{
			size_t n = std::strlen(w);
			if (s.compare(i, n, w) != 0)
				return false;
			i += n;
			return true;
		}
		bool hex4(unsigned& u)
		{
			if (i + 4 > s.size())
				return false;
			u = 0;
			for (int k = 0; k < 4; ++k)
			{
				char c = s[i++];
				int v = c >= '0' && c <= '9' ? c - '0' : c >= 'a' && c <= 'f' ? c - 'a' + 10 : c >= 'A' && c <= 'F' ? c - 'A' + 10 : -1;
				if (v < 0)
					return false;
				u = u * 16 + v;
			}
			return true;
		}
		bool text(std::string& out)
		{
			++i;
			while (i < s.size() && s[i] != '"')
			{
				unsigned char c = s[i++];
				if (c < 0x20)
					return false;
				if (c != '\\')
				{
					out += static_cast<char>(c);
					continue;
				}
				if (i >= s.size())
					return false;
				char e = s[i++];
				switch (e)
				{
				case '"': out += '"'; break;
				case '\\': out += '\\'; break;
				case '/': out += '/'; break;
				case 'b': out += '\b'; break;
				case 'f': out += '\f'; break;
				case 'n': out += '\n'; break;
				case 'r': out += '\r'; break;
				case 't': out += '\t'; break;
				case 'u':
				{
					unsigned u;
					if (!hex4(u))
						return false;
					if (u >= 0xD800 && u < 0xDC00 && s.compare(i, 2, "\\u") == 0)
					{
						size_t back = i;
						i += 2;
						unsigned low;
						if (hex4(low) && low >= 0xDC00 && low < 0xE000)
							u = 0x10000 + ((u - 0xD800) << 10) + (low - 0xDC00);
						else
							i = back;
					}
					if (u < 0x80)
						out += static_cast<char>(u);
					else if (u < 0x800)
						out += {static_cast<char>(0xC0 | (u >> 6)), static_cast<char>(0x80 | (u & 63))};
					else if (u < 0x10000)
						out += {static_cast<char>(0xE0 | (u >> 12)), static_cast<char>(0x80 | ((u >> 6) & 63)), static_cast<char>(0x80 | (u & 63))};
					else
						out += {static_cast<char>(0xF0 | (u >> 18)), static_cast<char>(0x80 | ((u >> 12) & 63)),
								static_cast<char>(0x80 | ((u >> 6) & 63)), static_cast<char>(0x80 | (u & 63))};
					break;
				}
				default: return false;
				}
			}
			if (i >= s.size())
				return false;
			++i;
			return true;
		}
		bool digits()
		{
			size_t from = i;
			while (i < s.size() && s[i] >= '0' && s[i] <= '9')
				++i;
			return i > from;
		}
		bool value(SavedData& d)
		{
			if (++depth > 5000)
				return false;
			space();
			if (i >= s.size())
				return false;
			char c = s[i];
			bool ok = true;
			if (c == '{')
			{
				d.type = SavedData::Table;
				++i;
				space();
				if (i < s.size() && s[i] == '}')
					++i;
				else
					for (;;)
					{
						space();
						std::string key;
						SavedData part;
						if (i >= s.size() || s[i] != '"' || !text(key))
							return false;
						space();
						if (i >= s.size() || s[i++] != ':' || !value(part))
							return false;
						d.parts.emplace_back(std::move(key), std::move(part));
						space();
						if (i < s.size() && s[i] == ',')
						{
							++i;
							continue;
						}
						if (i < s.size() && s[i] == '}')
						{
							++i;
							break;
						}
						return false;
					}
			}
			else if (c == '[')
			{
				d.type = SavedData::List;
				++i;
				space();
				if (i < s.size() && s[i] == ']')
					++i;
				else
					for (;;)
					{
						SavedData item;
						if (!value(item))
							return false;
						d.items.push_back(std::move(item));
						space();
						if (i < s.size() && s[i] == ',')
						{
							++i;
							continue;
						}
						if (i < s.size() && s[i] == ']')
						{
							++i;
							break;
						}
						return false;
					}
			}
			else if (c == '"')
			{
				d.type = SavedData::Text;
				ok = text(d.words);
			}
			else if (word("true") || word("false"))
			{
				d.type = SavedData::YesNo;
				d.yes = s[i - 1] == 'e' && s[i - 2] == 'u';
			}
			else if (word("null"))
				d.type = SavedData::Nothing;
			else
			{
				size_t from = i;
				if (s[i] == '-')
					++i;
				if (i < s.size() && s[i] == '0')
					++i;
				else if (!digits())
					return false;
				if (i < s.size() && s[i] == '.')
				{
					++i;
					if (!digits())
						return false;
				}
				if (i < s.size() && (s[i] == 'e' || s[i] == 'E'))
				{
					++i;
					if (i < s.size() && (s[i] == '+' || s[i] == '-'))
						++i;
					if (!digits())
						return false;
				}
				d.type = SavedData::Number;
				d.number = std::strtod(s.substr(from, i - from).c_str(), nullptr);
			}
			--depth;
			return ok;
		}
	};

	template <typename R, typename... A> bool load(const SavedData&, std::function<R(A...)>&) { return false; }
	inline bool load(const SavedData& d, double& x) { if (d.type != SavedData::Number) return false; x = d.number; return true; }
	inline bool load(const SavedData& d, bool& x) { if (d.type != SavedData::YesNo) return false; x = d.yes; return true; }
	inline bool load(const SavedData& d, std::string& x) { if (d.type != SavedData::Text) return false; x = d.words; return true; }
	inline bool load(const SavedData& d, FVector& v)
	{
		if (d.type != SavedData::List || d.items.size() != 3)
			return false;
		return load(d.items[0], v.X) && load(d.items[1], v.Y) && load(d.items[2], v.Z);
	}
	inline bool load(const SavedData& d, FVector2D& v)
	{
		if (d.type != SavedData::List || d.items.size() != 2)
			return false;
		return load(d.items[0], v.X) && load(d.items[1], v.Y);
	}
	template <typename T> bool load(const SavedData& d, std::vector<T>& items);
	template <typename T> bool load(const SavedData& d, std::map<std::string, T>& table);
	template <typename T> bool load(const SavedData& d, std::vector<T>& items)
	{
		if (d.type != SavedData::List)
			return false;
		items.assign(d.items.size(), T{});
		for (size_t k = 0; k < d.items.size(); ++k)
			if (!load(d.items[k], items[k]))
				return false;
		return true;
	}
	template <typename T> bool load(const SavedData& d, std::map<std::string, T>& table)
	{
		if (d.type != SavedData::Table)
			return false;
		table.clear();
		for (const auto& [key, part] : d.parts)
		{
			T value{};
			if (!load(part, value))
				return false;
			table[key] = std::move(value);
		}
		return true;
	}

	template <typename T>
	void save_file(const T& value, const std::string& path, int line)
	{
		std::string out;
		save(out, value, line);
		write_file(path, out + "\n", line);
	}

	template <typename T>
	std::string saved_text(const T& value, int line)
	{
		std::string out;
		save(out, value, line);
		return out;
	}

	template <typename T>
	void load_text(T& into, const std::string& all, const std::string& kind, int line)
	{
		SavedReader reader{all};
		SavedData d;
		T value{};
		bool ok = reader.value(d);
		reader.space();
		if (!ok || reader.i != all.size() || !load(d, value))
			fail(line, "the text doesn't hold " + kind + ".");
		into = std::move(value);
	}

	template <typename T>
	void load_file(T& into, const std::string& path, const std::string& kind, int line)
	{
		std::string all = read_file(path, line);
		SavedReader reader{all};
		SavedData d;
		T value{};
		bool ok = reader.value(d);
		reader.space();
		if (!ok || reader.i != all.size() || !load(d, value))
			fail(line, "the file \"" + path + "\" doesn't hold " + kind + ".");
		into = std::move(value);
	}

	inline void add_line(const std::string& path, const std::string& s, int line)
	{
		std::ofstream out(std::filesystem::u8path(path), std::ios::binary | std::ios::app);
		if (!(out << s << "\n"))
			fail(line, "I couldn't add to the file \"" + path + "\".");
	}

	inline double letters(const std::string& s);

	// Text is UTF-8; these split it into letters (not bytes), so "é" is one letter.
	inline std::vector<std::string> letters_in(const std::string& s)
	{
		std::vector<std::string> out;
		for (unsigned char c : s)
		{
			if ((c & 0xC0) != 0x80 || out.empty())
				out.emplace_back();
			out.back() += static_cast<char>(c);
		}
		return out;
	}

	inline std::string trimmed(const std::string& s)
	{
		size_t from = s.find_first_not_of(" \t\r\n");
		return from == std::string::npos ? "" : s.substr(from, s.find_last_not_of(" \t\r\n") - from + 1);
	}
	inline bool begins_with(const std::string& s, const std::string& part) { return s.compare(0, part.size(), part) == 0 && s.size() >= part.size(); }
	inline bool ends_with(const std::string& s, const std::string& part) { return s.size() >= part.size() && s.compare(s.size() - part.size(), part.size(), part) == 0; }
	inline std::string upper(std::string s)
	{
		for (char& c : s)
			if (c >= 'a' && c <= 'z') c = static_cast<char>(c - 'a' + 'A');
		return s;
	}

	inline std::string lower(std::string s)
	{
		for (char& c : s)
			if (c >= 'A' && c <= 'Z') c = static_cast<char>(c - 'A' + 'a');
		return s;
	}

	inline std::string letter(const std::string& s, double number, int line)
	{
		std::vector<std::string> all = letters_in(s);
		if (std::floor(number) != number || number < 1 || number > static_cast<double>(all.size()))
			fail(line, "there is no letter " + text(number) + " in text of " + text(static_cast<double>(all.size())) + " letters.");
		return all[static_cast<size_t>(number) - 1];
	}

	inline std::string letters_from(const std::string& s, double first, double last, int line)
	{
		std::vector<std::string> all = letters_in(s);
		double size = static_cast<double>(all.size());
		if (std::floor(first) != first || std::floor(last) != last || first < 1 || last > size || first > last + 1)
			fail(line, "there are no letters " + text(first) + " to " + text(last) + " in text of " + text(size) + " letters.");
		std::string out;
		for (size_t k = static_cast<size_t>(first) - 1; k < static_cast<size_t>(last); ++k)
			out += all[k];
		return out;
	}

	inline double position(const std::string& s, const std::string& part)
	{
		size_t at = s.find(part);
		return at == std::string::npos ? 0.0 : letters(s.substr(0, at)) + 1;
	}

	template <typename T>
	double position(const std::vector<T>& items, const T& item)
	{
		for (size_t k = 0; k < items.size(); ++k)
			if (items[k] == item)
				return static_cast<double>(k + 1);
		return 0.0;
	}

	template <typename T>
	std::vector<T> items_from(const std::vector<T>& items, double first, double last, int line)
	{
		double size = static_cast<double>(items.size());
		if (std::floor(first) != first || std::floor(last) != last || first < 1 || last > size || first > last + 1)
			fail(line, "there are no items " + text(first) + " to " + text(last) + " in a list of " + text(size) + " items.");
		return std::vector<T>(items.begin() + static_cast<size_t>(first) - 1, items.begin() + static_cast<size_t>(last));
	}

	inline size_t how_many(double count, double size, int line)
	{
		if (std::floor(count) != count || count < 0)
			fail(line, "I can't take " + text(count) + " of something: it must be a whole number, 0 or more.");
		return static_cast<size_t>(std::min(count, size));
	}

	template <typename T>
	std::vector<T> first_of(const std::vector<T>& items, double count, int line)
	{
		return std::vector<T>(items.begin(), items.begin() + how_many(count, static_cast<double>(items.size()), line));
	}

	template <typename T>
	std::vector<T> last_of(const std::vector<T>& items, double count, int line)
	{
		return std::vector<T>(items.end() - how_many(count, static_cast<double>(items.size()), line), items.end());
	}

	inline std::string first_of(const std::string& s, double count, int line)
	{
		std::vector<std::string> all = letters_in(s), part = first_of(all, count, line);
		std::string out;
		for (const auto& x : part)
			out += x;
		return out;
	}

	inline std::string last_of(const std::string& s, double count, int line)
	{
		std::vector<std::string> all = letters_in(s), part = last_of(all, count, line);
		std::string out;
		for (const auto& x : part)
			out += x;
		return out;
	}

	template <typename T>
	std::vector<T> unique(const std::vector<T>& items)
	{
		std::vector<T> out;
		for (const auto& x : items)
			if (std::find(out.begin(), out.end(), x) == out.end())
				out.push_back(x);
		return out;
	}

	// '1234567 with commas' is "1,234,567"; '7 padded to 3 digits' is "007".
	inline std::string with_commas(double n)
	{
		std::string s = text(n), sign;
		if (!s.empty() && s[0] == '-')
			sign = "-", s = s.substr(1);
		size_t dot = s.find('.');
		std::string whole = s.substr(0, dot), rest = dot == std::string::npos ? "" : s.substr(dot);
		if (whole.empty() || whole.find_first_not_of("0123456789") != std::string::npos)
			return sign + s;
		std::string out;
		for (size_t k = 0; k < whole.size(); ++k)
		{
			if (k && (whole.size() - k) % 3 == 0)
				out += ',';
			out += whole[k];
		}
		return sign + out + rest;
	}

	inline std::string padded(double n, double digits, int line)
	{
		if (std::floor(digits) != digits || digits < 0)
			fail(line, "I can't pad to " + text(digits) + " digits: it must be a whole number, 0 or more.");
		std::string s = text(n), sign;
		if (!s.empty() && s[0] == '-')
			sign = "-", s = s.substr(1);
		size_t dot = s.find('.');
		std::string whole = s.substr(0, dot), rest = dot == std::string::npos ? "" : s.substr(dot);
		if (whole.size() < static_cast<size_t>(digits))
			whole = std::string(static_cast<size_t>(digits) - whole.size(), '0') + whole;
		return sign + whole + rest;
	}

	inline std::string replace_all(std::string s, const std::string& from, const std::string& to, int line)
	{
		if (from.empty())
			fail(line, "I can't replace empty text.");
		for (size_t at = s.find(from); at != std::string::npos; at = s.find(from, at + to.size()))
			s.replace(at, from.size(), to);
		return s;
	}

	inline std::vector<std::string> split(const std::string& s, const std::string& by, int line)
	{
		if (by.empty())
			fail(line, "I can't split text by empty text.");
		std::vector<std::string> out;
		size_t start = 0;
		for (size_t at = s.find(by); at != std::string::npos; at = s.find(by, start))
		{
			out.push_back(s.substr(start, at - start));
			start = at + by.size();
		}
		out.push_back(s.substr(start));
		return out;
	}

	template <typename T>
	std::string join(const std::vector<T>& items, const std::string& between)
	{
		std::string out;
		for (size_t k = 0; k < items.size(); ++k)
			out += (k ? between : std::string()) + text(items[k]);
		return out;
	}

	template <typename T>
	const T& last(const std::vector<T>& items, int line)
	{
		if (items.empty())
			fail(line, "the list is empty, so it has no last item.");
		return items.back();
	}

	template <typename T>
	std::vector<T> sorted(std::vector<T> items)
	{
		std::stable_sort(items.begin(), items.end());
		return items;
	}

	// 'a is within 30 of b': the distance between them is 30 or less.
	inline bool within(double a, double b, double reach) { return std::fabs(a - b) <= reach; }
	inline bool within(const FVector& a, const FVector& b, double reach) { return (a - b).Size() <= reach; }
	inline bool within(const FVector2D& a, const FVector2D& b, double reach) { return (a - b).Size() <= reach; }

	// Setting a thing's birth puts its existence there too.
	template <typename T>
	void born(T& birth, T& existence, const T& where)
	{
		birth = where;
		existence = where;
	}

	template <typename T, typename Part>
	std::vector<T> sorted_by(std::vector<T> items, Part part, int = 0)
	{
		std::stable_sort(items.begin(), items.end(), [&](const T& a, const T& b) { return part(a) < part(b); });
		return items;
	}

	inline double sum_of(const std::vector<double>& items, int)
	{
		double total = 0;
		for (double x : items)
			total += x;
		return total;
	}

	inline double average_of(const std::vector<double>& items, int line)
	{
		if (items.empty())
			fail(line, "the list is empty, so it has no average.");
		return sum_of(items, line) / static_cast<double>(items.size());
	}

	inline double biggest_of(const std::vector<double>& items, int line)
	{
		if (items.empty())
			fail(line, "the list is empty, so it has no biggest.");
		return *std::max_element(items.begin(), items.end());
	}

	inline double smallest_of(const std::vector<double>& items, int line)
	{
		if (items.empty())
			fail(line, "the list is empty, so it has no smallest.");
		return *std::min_element(items.begin(), items.end());
	}

	template <typename T>
	std::vector<T> reversed(std::vector<T> items)
	{
		std::reverse(items.begin(), items.end());
		return items;
	}

	inline void say(std::initializer_list<std::string> parts)
	{
		if (show_hook)
		{
			std::string all;
			for (const std::string& p : parts)
				all += p;
			show_hook(all, false);
			return;
		}
		for (const std::string& p : parts)
			std::cout << p;
		std::cout << std::endl;
	}

	inline std::string ask_text(const std::string& question)
	{
		if (show_hook)
			throw Problem{0, "'ask' doesn't work in Unreal yet (there is nowhere to type)."};
		std::cout << question << std::flush;
		std::string line;
		if (!std::getline(std::cin, line))
			std::exit(0);  // nobody is left to answer (input closed)
		if (!line.empty() && line.back() == '\r')  // (typed on Windows, read where nothing takes it away: WebAssembly)
			line.pop_back();
		return line;
	}

	inline bool ask_yes_no(const std::string& question)
	{
		for (;;)
		{
			std::string answer = lower(ask_text(question));
			answer.erase(0, answer.find_first_not_of(" \t"));
			answer.erase(answer.find_last_not_of(" \t") + 1);
			if (answer == "yes" || answer == "y")
				return true;
			if (answer == "no" || answer == "n")
				return false;
			std::cout << "Please type yes or no." << std::endl;
		}
	}

	inline double ask_number(const std::string& question)
	{
		for (;;)
		{
			std::string line = ask_text(question);
			std::istringstream in(line);
			double d;
			char extra;
			if (in >> d && !(in >> extra))
				return d;
			std::cout << "Please type a number." << std::endl;
		}
	}

	template <typename T>
	const T& random_item(const std::vector<T>& items, int line);

	inline std::mt19937_64& random_engine()
	{
		static std::mt19937_64 engine{std::random_device{}()};
		return engine;
	}
	inline double random_fraction() { return std::uniform_real_distribution<double>(0.0, 1.0)(random_engine()); }

	inline double random(double lo, double hi, int line)
	{
		auto& engine = random_engine();
		double a = std::ceil(std::min(lo, hi)), b = std::floor(std::max(lo, hi));
		if (a > b)
			fail(line, "there is no whole number from " + text(lo) + " to " + text(hi) + ".");
		return static_cast<double>(std::uniform_int_distribution<long long>(static_cast<long long>(a), static_cast<long long>(b))(engine));
	}

	template <typename T>
	const T& random_item(const std::vector<T>& items, int line)
	{
		if (items.empty())
			fail(line, "the list is empty, so I can't pick a random item.");
		return items[static_cast<size_t>(random(1, static_cast<double>(items.size()), line)) - 1];
	}

	template <typename T>
	std::vector<T> shuffled(std::vector<T> items)
	{
		std::shuffle(items.begin(), items.end(), random_engine());
		return items;
	}

	// How many letters text has (not bytes: "é" is one letter).
	inline double letters(const std::string& s)
	{
		double count = 0;
		for (unsigned char c : s)
			count += (c & 0xC0) != 0x80;
		return count;
	}
}
