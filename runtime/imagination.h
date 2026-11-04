// What every Imagination program can use. Included by the C++ that imagination.py writes.
#pragma once
#include <algorithm>
#include <cmath>
#include <initializer_list>
#include <iostream>
#include <random>
#include <sstream>
#include <string>

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
