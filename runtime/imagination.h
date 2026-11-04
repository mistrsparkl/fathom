// What every Imagination program can use. Included by the C++ that imagination.py writes.
#pragma once
#include <algorithm>
#include <cmath>
#include <cstdio>
#include <filesystem>
#include <fstream>
#include <initializer_list>
#include <map>
#include <iostream>
#include <random>
#include <sstream>
#include <string>
#include <vector>

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

extern "C" __declspec(dllimport) int __stdcall SetConsoleOutputCP(unsigned int);
extern "C" __declspec(dllimport) int __stdcall SetConsoleCP(unsigned int);

namespace imagine
{
	inline std::vector<std::string> files;  // the program's script, then each script it uses

	// Called first by every program: text is UTF-8, so the console should show it as UTF-8.
	inline void begin(std::initializer_list<std::string> scripts)
	{
		files = scripts;
		SetConsoleOutputCP(65001);
		SetConsoleCP(65001);
	}

	inline std::string text(const std::string& s) { return s; }
	inline std::string text(double d);
	inline std::string text(const FVector& v) { return "(" + text(v.X) + ", " + text(v.Y) + ", " + text(v.Z) + ")"; }
	inline std::string text(const FVector2D& v) { return "(" + text(v.X) + ", " + text(v.Y) + ")"; }
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

	template <typename T>
	std::string text(const std::vector<T>& items)
	{
		if (items.empty())
			return "(nothing)";
		std::string out;
		for (size_t k = 0; k < items.size(); ++k)
			out += (k ? ", " : "") + text(items[k]);
		return out;
	}

	template <typename T>
	std::string text(const std::map<std::string, T>& table)
	{
		if (table.empty())
			return "(nothing)";
		std::string out;
		for (const auto& [key, value] : table)
			out += (out.empty() ? "" : ", ") + key + ": " + text(value);
		return out;
	}

	// Something went wrong while the program ran: say which line, in plain words, and stop.
	// What went wrong, and on which line. 'try:' can catch it; otherwise the program stops and reports it.
	struct Problem
	{
		int line;
		std::string message;
	};

	[[noreturn]] inline void fail(int line, const std::string& message)
	{
		throw Problem{line, message};
	}

	inline void report(const Problem& problem)
	{
		std::cout << std::flush;
		if (problem.line < 100000 || problem.line / 100000 >= static_cast<int>(files.size()))
			std::cerr << "Line " << problem.line;
		else
			std::cerr << files[problem.line / 100000] << " line " << problem.line % 100000;
		std::cerr << ": " << problem.message << std::endl;
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

	template <typename T>
	const T& at(const std::vector<T>& items, double number, int line) { return items[index_of(items, number, line)]; }

	template <typename T>
	void remove_item(std::vector<T>& items, double number, int line) { items.erase(items.begin() + index_of(items, number, line)); }

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

	template <typename T>
	std::vector<T> reversed(std::vector<T> items)
	{
		std::reverse(items.begin(), items.end());
		return items;
	}

	inline void say(std::initializer_list<std::string> parts)
	{
		for (const std::string& p : parts)
			std::cout << p;
		std::cout << std::endl;
	}

	inline std::string ask_text(const std::string& question)
	{
		std::cout << question << std::flush;
		std::string line;
		if (!std::getline(std::cin, line))
			std::exit(0);  // nobody is left to answer (input closed)
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

	inline double random(double lo, double hi, int line)
	{
		static std::mt19937_64 engine{std::random_device{}()};
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

	// How many letters text has (not bytes: "é" is one letter).
	inline double letters(const std::string& s)
	{
		double count = 0;
		for (unsigned char c : s)
			count += (c & 0xC0) != 0x80;
		return count;
	}
}
