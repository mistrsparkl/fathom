// What every Imagination program can use. Included by the C++ that imagination.py writes.
#pragma once
#include <algorithm>
#include <cmath>
#include <filesystem>
#include <fstream>
#include <initializer_list>
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

namespace imagine
{
	inline std::string text(const std::string& s) { return s; }
	inline std::string text(bool b) { return b ? "yes" : "no"; }
	inline std::string text(double d)
	{
		// Whole numbers show as "5", not "5.0" or "5e+00".
		if (std::floor(d) == d && std::fabs(d) < 1e15)
			return std::to_string(static_cast<long long>(d));
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

	// Something went wrong while the program ran: say which line, in plain words, and stop.
	[[noreturn]] inline void fail(int line, const std::string& message)
	{
		std::cout << std::flush;
		std::cerr << "Line " << line << ": " << message << std::endl;
		std::exit(1);
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

	// 'for each' walks a copy, so changing the list inside the loop is safe.
	template <typename T>
	std::vector<T> copy(const std::vector<T>& items) { return items; }

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

	inline double random(double lo, double hi)
	{
		static std::mt19937_64 engine{std::random_device{}()};
		long long a = static_cast<long long>(std::ceil(std::min(lo, hi)));
		long long b = static_cast<long long>(std::floor(std::max(lo, hi)));
		return static_cast<double>(std::uniform_int_distribution<long long>(a, b)(engine));
	}
}
