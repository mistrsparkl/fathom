// What a program made into machine code (by machine.py) calls: plain C functions over stellanova.h.
// Compiled once into runtime/built/stellanova_machine.obj; a program's own code never becomes C++.
//
// Numbers are doubles and yes/no is a bool. Everything else (text, lists, tables, places, things) is a V*:
// made here, copied when stored (as Python and C++ copy), and shown and compared the way Python does.
#include "stellanova.h"
#include "machine.h"

#define WIN32_LEAN_AND_MEAN
#define NOMINMAX
#include <winsock2.h>
#include <windows.h>
#include <atomic>
#include <condition_variable>

// ---------------------------------------------------------------- freeing values
// Now and then, while values are being made, the values nobody can reach any more are freed (a collector).
// Reachable: what any thread holds on its stack or in its registers, the world's shared names (cn_root), the values
// made since a thread's current line began (cn_statement), and everything inside those.
// A thread stops for the collector only at safe points (making a value, starting a line). A thread inside a library
// word (waiting, reading the web...) is 'parked' with its registers kept, so the collector never waits for it.
namespace gc
{
	struct Thread
	{
		char* top = nullptr;  // where its stack starts (its highest address)
		CONTEXT regs{};
		char* sp = nullptr;
		std::atomic<int> state{0};  // 0 running, 1 stopped at a safe point, 2 parked
		std::vector<V*> young;  // made since its current line began
	};
	static std::mutex lock;  // every value, the roots, and each thread's young values
	static std::mutex stop_lock;  // the threads and their states
	static std::condition_variable stop_cv;
	static std::vector<Thread*> threads;
	static std::vector<V*> all;
	static std::vector<V*> spare;  // freed values, ready to be used again
	static std::vector<V*> spare_small;  // freed numbers and yes/no values
	static std::vector<std::pair<const char*, size_t>> roots;
	static const size_t least = std::getenv("STELLANOVA_COLLECT_OFTEN") ? 2 : 1 << 18;  // set it to test the collector hard
	static size_t made_since = 0, limit = least;
	static std::mutex collecting;
	static std::atomic<bool> stopping{false};

	struct Mine
	{
		Thread* t = nullptr;
		~Mine()  // the thread is ending
		{
			if (!t)
				return;
			{
				std::lock_guard<std::mutex> hold(stop_lock);
				threads.erase(std::find(threads.begin(), threads.end(), t));
				delete t;
			}
			stop_cv.notify_all();
		}
	};
	static thread_local Mine mine;

	static Thread* me()
	{
		if (!mine.t)
		{
			Thread* t = new Thread;
			ULONG_PTR low, high;
			GetCurrentThreadStackLimits(&low, &high);
			t->top = reinterpret_cast<char*>(high);
			t->sp = t->top;  // nothing to look at until its registers are kept
			std::lock_guard<std::mutex> hold(stop_lock);
			threads.push_back(t);
			mine.t = t;
		}
		return mine.t;
	}

	static void keep_registers(Thread* t)
	{
		RtlCaptureContext(&t->regs);
		t->sp = reinterpret_cast<char*>(t->regs.Rsp);
	}

	static void stop_here(Thread* t)
	{
		keep_registers(t);
		std::unique_lock<std::mutex> hold(stop_lock);
		t->state = 1;
		stop_cv.notify_all();
		stop_cv.wait(hold, [] { return !stopping.load(); });
		t->state = 0;
	}

	static void mark_and_sweep()
	{
		std::sort(all.begin(), all.end());
		std::vector<V*> work;
		auto reach = [&](V* c) {
			if (c && !c->marked)
			{
				c->marked = true;
				work.push_back(c);
			}
		};
		auto look = [&](const char* from, const char* to) {  // any word here that is a value's address
			const char* p = reinterpret_cast<const char*>((reinterpret_cast<uintptr_t>(from) + 7) & ~uintptr_t(7));
			for (; p + sizeof(V*) <= to; p += sizeof(V*))
			{
				V* c;
				std::memcpy(&c, p, sizeof c);
				auto it = std::lower_bound(all.begin(), all.end(), c);
				if (it != all.end() && *it == c)
					reach(c);
			}
		};
		for (Thread* x : threads)
		{
			look(reinterpret_cast<const char*>(&x->regs), reinterpret_cast<const char*>(&x->regs + 1));
			look(x->sp, x->top);
			for (V* v : x->young)
				reach(v);
		}
		for (const auto& [from, size] : roots)
			look(from, from + size);
		while (!work.empty())
		{
			V* v = work.back();
			work.pop_back();
			if (is_small(v->tag))
				continue;
			for (V* x : full(v)->items)
				reach(x);
			for (const auto& [key, x] : full(v)->table)
				reach(x);
		}
		size_t kept = 0;
		for (V* v : all)
			if (v->marked)
			{
				v->marked = false;
				all[kept++] = v;
			}
			else if (is_small(v->tag))
			{
				if (spare_small.size() < (1 << 20))
					spare_small.push_back(v);
				else
					delete v;
			}
			else if (spare.size() < (1 << 20))
			{
				Full* f = full(v);
				f->d = f->x = f->y = f->z = 0;
				if (f->s.capacity() > 4096)
					std::string().swap(f->s);
				f->s.clear();
				if (f->items.capacity() > 1024)
					std::vector<V*>().swap(f->items);
				f->items.clear();
				f->table.clear();
				f->kind = nullptr;
				f->command = nullptr;
				spare.push_back(v);
			}
			else
				delete full(v);
		all.resize(kept);
		made_since = 0;
		limit = std::getenv("STELLANOVA_COLLECT_OFTEN") ? least : std::max(least, kept);
	}

	static void collect(Thread* self)
	{
		std::unique_lock<std::mutex> one(collecting, std::try_to_lock);
		if (!one)  // another thread is collecting
		{
			if (stopping)
				stop_here(self);
			return;
		}
		keep_registers(self);
		std::unique_lock<std::mutex> hold(stop_lock);
		stopping = true;
		self->state = 1;
		stop_cv.wait(hold, [self] {
			for (Thread* x : threads)
				if (x != self && x->state == 0)
					return false;
			return true;
		});
		{
			std::lock_guard<std::mutex> heap(lock);
			mark_and_sweep();
		}
		self->state = 0;
		stopping = false;
		hold.unlock();
		stop_cv.notify_all();
	}

	static V* track(char tag)  // a new value (a freed one used again when there is one)
	{
		Thread* t = me();
		if (t->state == 0 && stopping)
			stop_here(t);
		bool full;
		V* v;
		{
			std::lock_guard<std::mutex> hold(lock);
			std::vector<V*>& ready = is_small(tag) ? spare_small : spare;
			if (!ready.empty())
			{
				v = ready.back();
				ready.pop_back();
			}
			else if (is_small(tag))
				v = new V;
			else
				v = new Full;
			v->tag = tag;
			all.push_back(v);
			t->young.push_back(v);
			full = ++made_since > limit;
		}
		if (full && t->state == 0)
			collect(t);
		return v;
	}
}

extern "C"
{
	void cn_statement()  // a line begins: values made for the line before are now only kept if something holds them
	{
		gc::Thread* t = gc::me();
		if (gc::stopping)
			gc::stop_here(t);
		t->young.clear();
	}
	void cn_park()  // going into a library word that may wait: the collector needn't wait for this thread
	{
		gc::Thread* t = gc::me();
		gc::keep_registers(t);
		t->state = 2;
		if (gc::stopping)  // a collector may be waiting for this thread
		{
			std::lock_guard<std::mutex> hold(gc::stop_lock);
			gc::stop_cv.notify_all();
		}
	}
	void cn_unpark()
	{
		gc::Thread* t = gc::me();
		t->state = 0;
		if (!gc::stopping)  // (both are seq_cst: a collector starting now sees this thread running and waits for it)
			return;
		gc::keep_registers(t);  // (a thread new to machine code has none kept yet)
		std::unique_lock<std::mutex> hold(gc::stop_lock);
		t->state = 2;  // not yet: wait until the collector is done
		gc::stop_cv.notify_all();
		gc::stop_cv.wait(hold, [] { return !gc::stopping.load(); });
		t->state = 0;
	}
	void cn_root(const char* from, long long size)  // the world's shared names: always kept
	{
		std::lock_guard<std::mutex> hold(gc::lock);
		gc::roots.push_back({from, static_cast<size_t>(size)});
	}
	void cn_hold_push(V* list, V* x)  // a library word filling a list (it may be parked while the collector looks)
	{
		std::lock_guard<std::mutex> hold(gc::lock);
		full(list)->items.push_back(x);
	}
	void cn_hold_put(V* table, const char* key, V* x)
	{
		std::lock_guard<std::mutex> hold(gc::lock);
		full(table)->table[key] = x;
	}
}

static void unroot(const char* from)
{
	std::lock_guard<std::mutex> hold(gc::lock);
	auto& r = gc::roots;
	r.erase(std::find_if(r.begin(), r.end(), [from](const auto& x) { return x.first == from; }));
}

struct Parked  // around anything in here that may wait
{
	Parked() { cn_park(); }
	~Parked() { cn_unpark(); }
};

static V* fresh(char tag)
{
	return gc::track(tag);
}
V* cn_make_text(std::string s)
{
	V* v = fresh('t');
	full(v)->s = std::move(s);
	return v;
}

// ---------------------------------------------------------------- problems
// A problem doesn't jump anywhere: it is kept here, and the machine code checks cn_failed() after each step that may fail,
// then goes to the 'if that went wrong:' lines, or leaves the command (and so on, up to the program, which reports it).
static thread_local bool failed = false;  // each command going alongside ('meanwhile') has its own
static thread_local stellanova::Problem pending;

void cn_set_problem(const stellanova::Problem& p)
{
	if (!failed)
		pending = p;
	failed = true;
}

void cn_rethrow()
{
	if (failed)
	{
		failed = false;
		throw stellanova::Problem(pending);
	}
}

#define GUARDED(fallback, body) try { body } catch (const stellanova::Problem& problem) { cn_set_problem(problem); return fallback; }

static std::string thing_name(const V* v);

static std::string show(const V* v);
static std::string part(const V* v)
{
	bool group = (v->tag == 'l' && !full(v)->items.empty()) || (v->tag == 'm' && !full(v)->table.empty());
	return group ? "(" + show(v) + ")" : show(v);
}
static std::string show(const V* v)
{
	switch (v->tag)
	{
	case 'n': return stellanova::text(v->d);
	case 'y': return v->d != 0 ? "yes" : "no";
	case 't': return full(v)->s;
	case 'p': return stellanova::text(full(v)->x) + " horizontal " + stellanova::text(full(v)->y) + " vertical " + stellanova::text(full(v)->z) + " depth";
	case 'f': return stellanova::text(full(v)->x) + " horizontal " + stellanova::text(full(v)->y) + " vertical";
	case 'c': return "a command";
	case 'l':
	{
		if (full(v)->items.empty())
			return "(nothing)";
		std::string out;
		for (size_t k = 0; k < full(v)->items.size(); ++k)
			out += (k ? ", " : "") + part(full(v)->items[k]);
		return out;
	}
	case 'm':
	{
		if (full(v)->table.empty())
			return "(nothing)";
		std::string out;
		for (const auto& [key, x] : full(v)->table)
			out += (out.empty() ? "" : ", ") + key + ": " + part(x);
		return out;
	}
	case 'k':
	{
		std::string out = "a " + full(v)->kind->name + " (";
		for (size_t k = 0; k < full(v)->items.size(); ++k)
			out += (k ? ", " : "") + full(v)->kind->fields[k] + ": " + show(full(v)->items[k]);
		return out + ")";
	}
	}
	return "?";
}

static bool same(const V* a, const V* b)
{
	if (a->tag != b->tag)
		return false;
	switch (a->tag)
	{
	case 'n': case 'y': return a->d == b->d;
	case 't': return full(a)->s == full(b)->s;
	case 'p': case 'f': return full(a)->x == full(b)->x && full(a)->y == full(b)->y && full(a)->z == full(b)->z;
	case 'k':
		if (full(a)->kind->name != full(b)->kind->name)
			return false;
		[[fallthrough]];
	case 'l':
		if (full(a)->items.size() != full(b)->items.size())
			return false;
		for (size_t k = 0; k < full(a)->items.size(); ++k)
			if (!same(full(a)->items[k], full(b)->items[k]))
				return false;
		return true;
	case 'm':
		if (full(a)->table.size() != full(b)->table.size())
			return false;
		for (const auto& [key, x] : full(a)->table)
		{
			auto it = full(b)->table.find(key);
			if (it == full(b)->table.end() || !same(x, it->second))
				return false;
		}
		return true;
	}
	return false;
}

static V* copy_of(const V* v)
{
	if (v->tag == 'n' || v->tag == 'y' || v->tag == 't' || v->tag == 'c')
		return const_cast<V*>(v);  // these never change, so they can be shared
	V* out = fresh(v->tag);
	*full(out) = *full(v);
	out->marked = false;
	for (auto& x : full(out)->items)
		x = copy_of(x);
	for (auto& [key, x] : full(out)->table)
		x = copy_of(x);
	return out;
}

// A value written out as JSON, as stellanova.h's save() writes it (a thing's parts by their names, in order).
static std::string saved_of(const V* v, int line)
{
	std::string out;
	switch (v->tag)
	{
	case 'n': stellanova::save(out, v->d, line); break;
	case 'y': stellanova::save(out, v->d != 0, line); break;
	case 't': stellanova::save(out, full(v)->s, line); break;
	case 'p': stellanova::save(out, FVector(full(v)->x, full(v)->y, full(v)->z), line); break;
	case 'f': stellanova::save(out, FVector2D(full(v)->x, full(v)->y), line); break;
	case 'c': stellanova::fail(line, "I can't save a command in a file."); break;
	case 'l':
		out += "[";
		for (size_t k = 0; k < full(v)->items.size(); ++k)
			out += (k ? ", " : "") + saved_of(full(v)->items[k], line);
		out += "]";
		break;
	default:  // a table, or a thing
	{
		out += "{";
		bool first = true;
		auto part = [&](const std::string& key, const V* x) {
			out += first ? "" : ", ";
			first = false;
			stellanova::save(out, key, line);
			out += ": " + saved_of(x, line);
		};
		if (v->tag == 'm')
			for (const auto& [key, x] : full(v)->table)
				part(key, x);
		else
			for (size_t k = 0; k < full(v)->items.size(); ++k)
				part(full(v)->kind->fields[k], full(v)->items[k]);
		out += "}";
	}
	}
	return out;
}

// 'load X from ...': saved data read into a new value shaped like shape (a list's or table's one item shows its items' kind)
static V* empty_like(const V* shape)
{
	if (shape->tag == 'l' || shape->tag == 'm')
		return fresh(shape->tag);
	V* v = copy_of(shape);
	if (v->tag == 'k')
		for (V*& x : full(v)->items)
			x = empty_like(x);
	return v;
}

static bool loaded_into(const stellanova::SavedData& d, const V* shape, V*& out)
{
	using D = stellanova::SavedData;
	switch (shape->tag)
	{
	case 'n': if (d.type != D::Number) return false; out = cn_box_number(d.number); return true;
	case 'y': if (d.type != D::YesNo) return false; out = cn_box_yesno(d.yes); return true;
	case 't': if (d.type != D::Text) return false; out = cn_make_text(d.words); return true;
	case 'p':
	case 'f':
	{
		size_t size = shape->tag == 'p' ? 3 : 2;
		if (d.type != D::List || d.items.size() != size)
			return false;
		for (const D& x : d.items)
			if (x.type != D::Number)
				return false;
		out = shape->tag == 'p' ? cn_place(d.items[0].number, d.items[1].number, d.items[2].number) : cn_flat(d.items[0].number, d.items[1].number);
		return true;
	}
	case 'l':
		if (d.type != D::List)
			return false;
		out = fresh('l');
		for (const D& x : d.items)
		{
			V* item = nullptr;
			if (!loaded_into(x, full(shape)->items[0], item))
				return false;
			full(out)->items.push_back(item);
		}
		return true;
	case 'm':
		if (d.type != D::Table)
			return false;
		out = fresh('m');
		for (const auto& [key, x] : d.parts)
		{
			V* item = nullptr;
			if (!loaded_into(x, full(shape)->table.begin()->second, item))
				return false;
			full(out)->table[key] = item;
		}
		return true;
	case 'k':
		if (d.type != D::Table)
			return false;
		out = empty_like(shape);  // a part the data doesn't have stays empty
		for (size_t k = 0; k < full(shape)->kind->fields.size(); ++k)
			if (const D* p = d.part(full(shape)->kind->fields[k]); p && p->type != D::Nothing && !loaded_into(*p, full(shape)->items[k], full(out)->items[k]))
				return false;
		return true;
	default:
		return false;  // a command can't be saved
	}
}

// A list's item number: counted from 1, as people count.
static size_t index_of(const V* list, double number, int line)
{
	if (number != std::floor(number) || number < 1 || number > static_cast<double>(full(list)->items.size()))
		stellanova::fail(line, "there is no item " + stellanova::text(number) + " in a list of " + stellanova::text(static_cast<double>(full(list)->items.size()))
			+ " item" + (full(list)->items.size() == 1 ? "" : "s") + ". Items are counted from 1.");
	return static_cast<size_t>(number) - 1;
}

extern "C"
{
	void cn_begin(int count, char** given) { stellanova::begin({}, count, given); }
	void cn_add_file(const char* name) { stellanova::files.push_back(name); }
	int cn_end()
	{
		if (!failed)
		{
			Parked waiting;
			stellanova::wait_for_others();
		}
		std::cout << std::flush;
		if (!failed)
			return 0;
		stellanova::report(pending);
		std::cerr << std::flush;
		std::_Exit(1);  // commands still going alongside stop too
	}
	void cn_meanwhile(void (*command)(void*), void* names, long long size)  // 'meanwhile ...': names holds its own copy of every name it uses
	{
		cn_root(static_cast<const char*>(names), size);  // kept until the command is done with them
		stellanova::meanwhile([command, names] {
			gc::me();
			command(names);
			unroot(static_cast<const char*>(names));
			std::free(names);
			if (failed)
				throw stellanova::Problem(pending);
		});
	}
	void cn_wait_for_others() { Parked waiting; stellanova::wait_for_others(); }

	bool cn_failed() { return failed; }
	void cn_raise(int line, V* message) { cn_set_problem({line, full(message)->s}); }
	V* cn_problem_text()  // what went wrong, inside 'if that went wrong:' (and the problem is dealt with)
	{
		failed = false;
		return cn_make_text(pending.message);
	}

	// text
	V* cn_text(const char* bytes, long long size) { return cn_make_text(std::string(bytes, static_cast<size_t>(size))); }
	V* cn_text_number(double d) { return cn_make_text(stellanova::text(d)); }
	V* cn_text_yesno(bool b) { return cn_make_text(b ? "yes" : "no"); }
	V* cn_show(V* v) { return cn_make_text(show(v)); }
	V* cn_join(V* a, V* b) { return cn_make_text(full(a)->s + full(b)->s); }
	bool cn_same_text(V* a, V* b) { return full(a)->s == full(b)->s; }
	void cn_say(V* t) { stellanova::say({full(t)->s}); }
	V* cn_ask_text(V* question)
	{
		std::string answer;
		{
			Parked waiting;
			answer = stellanova::ask_text(full(question)->s);
		}
		return cn_make_text(answer);
	}
	double cn_ask_number(V* question) { Parked waiting; return stellanova::ask_number(full(question)->s); }
	bool cn_ask_yes_no(V* question) { Parked waiting; return stellanova::ask_yes_no(full(question)->s); }
	double cn_letters(V* t) { return stellanova::letters(full(t)->s); }
	double cn_to_number(V* t, int line) { GUARDED(0.0, return stellanova::to_number(full(t)->s, line);) }

	// numbers
	long long cn_repeats(double count) { return std::isfinite(count) ? static_cast<long long>(count) : 0; }
	double cn_random(double lo, double hi, int line) { GUARDED(0.0, return stellanova::random(lo, hi, line);) }
	double cn_random_fraction() { return stellanova::random_fraction(); }
	double cn_rounded(double x, double places, int line) { GUARDED(0.0, return stellanova::rounded(x, places, line);) }

	// any value
	V* cn_box_number(double d)
	{
		V* v = fresh('n');
		v->d = d;
		return v;
	}
	V* cn_box_yesno(bool b)
	{
		V* v = fresh('y');
		v->d = b ? 1 : 0;
		return v;
	}
	double cn_unbox_number(V* v) { return v->d; }
	bool cn_unbox_yesno(V* v) { return v->d != 0; }
	V* cn_box_command(void* command)
	{
		V* v = fresh('c');
		full(v)->command = command;
		return v;
	}
	void* cn_unbox_command(V* v) { return full(v)->command; }
	void* cn_command_or_fail(void* command, int line)  // 'invoke f' when f holds no command yet
	{
		if (!command)
			cn_set_problem({line, "there is no command in it yet: set it to one first, like 'set f to the command double'."});
		return command;
	}
	V* cn_dup(V* v) { return copy_of(v); }
	bool cn_equal(V* a, V* b) { return same(a, b); }

	// lists and tables
	V* cn_list_new() { return fresh('l'); }
	V* cn_table_new() { return fresh('m'); }
	void cn_list_add(V* list, V* item) { full(list)->items.push_back(copy_of(item)); }
	V* cn_list_at(V* list, double number, int line) { GUARDED(cn_box_number(0), return full(list)->items[index_of(list, number, line)];) }
	V* cn_list_item(V* list, long long k) { return full(list)->items[static_cast<size_t>(k)]; }  // for 'for each': k is always there
	void cn_list_put(V* list, double number, V* item, int line) { GUARDED(, full(list)->items[index_of(list, number, line)] = copy_of(item);) }
	void cn_list_remove_item(V* list, double number, int line) { GUARDED(, full(list)->items.erase(full(list)->items.begin() + static_cast<long long>(index_of(list, number, line)));) }
	void cn_list_remove_value(V* list, V* item)
	{
		for (size_t k = 0; k < full(list)->items.size(); ++k)
			if (same(full(list)->items[k], item))
			{
				full(list)->items.erase(full(list)->items.begin() + static_cast<long long>(k));
				return;
			}
	}
	double cn_count(V* v) { return static_cast<double>(v->tag == 'm' ? full(v)->table.size() : full(v)->items.size()); }
	long long cn_count_whole(V* v) { return static_cast<long long>(full(v)->items.size()); }
	bool cn_list_contains(V* list, V* item)
	{
		for (V* x : full(list)->items)
			if (same(x, item))
				return true;
		return false;
	}
	bool cn_text_contains(V* t, V* part) { return full(t)->s.find(full(part)->s) != std::string::npos; }
	bool cn_table_has(V* table, V* key) { return full(table)->table.count(full(key)->s) > 0; }
	V* cn_list_random(V* list, int line)
	{
		GUARDED(cn_box_number(0),
			if (full(list)->items.empty())
				stellanova::fail(line, "the list is empty, so I can't pick a random item.");
			return full(list)->items[static_cast<size_t>(stellanova::random(1, static_cast<double>(full(list)->items.size()), line)) - 1];)
	}
	V* cn_list_last(V* list, int line)
	{
		GUARDED(cn_box_number(0),
			if (full(list)->items.empty())
				stellanova::fail(line, "the list is empty, so it has no last item.");
			return full(list)->items.back();)
	}
	double cn_list_stat(int which, V* list, int line)  // 0 sum, 1 average, 2 biggest, 3 smallest
	{
		static const char* names[] = {"sum", "average", "biggest", "smallest"};
		GUARDED(0.0,
			if (full(list)->items.empty() && which != 0)
				stellanova::fail(line, std::string("the list is empty, so it has no ") + names[which] + ".");
			double out = which == 2 ? -INFINITY : which == 3 ? INFINITY : 0;
			for (V* x : full(list)->items)  // one at a time, in order, as Python does
				out = which == 2 ? std::max(out, x->d) : which == 3 ? std::min(out, x->d) : out + x->d;
			return which == 1 ? out / static_cast<double>(full(list)->items.size()) : out;)
	}
	V* cn_entry(V* table, V* key, int line)
	{
		GUARDED(cn_box_number(0),
			auto it = full(table)->table.find(full(key)->s);
			if (it == full(table)->table.end())
				stellanova::fail(line, "there is no entry \"" + full(key)->s + "\" in the table.");
			return it->second;)
	}
	void cn_entry_put(V* table, V* key, V* x) { full(table)->table[full(key)->s] = copy_of(x); }
	void cn_entry_remove(V* table, V* key, int line)
	{
		GUARDED(,
			if (!full(table)->table.erase(full(key)->s))
				stellanova::fail(line, "there is no entry \"" + full(key)->s + "\" in the table to remove.");)
	}
	V* cn_keys(V* table)
	{
		V* out = fresh('l');
		for (const auto& [key, x] : full(table)->table)
			full(out)->items.push_back(cn_make_text(key));
		return out;
	}

	// places
	V* cn_place(double x, double y, double z)
	{
		V* v = fresh('p');
		full(v)->x = x, full(v)->y = y, full(v)->z = z;
		return v;
	}
	V* cn_flat(double x, double y)
	{
		V* v = fresh('f');
		full(v)->x = x, full(v)->y = y;
		return v;
	}
	double cn_part(V* v, int k) { return k == 0 ? full(v)->x : k == 1 ? full(v)->y : full(v)->z; }
	void cn_part_put(V* v, int k, double d) { (k == 0 ? full(v)->x : k == 1 ? full(v)->y : full(v)->z) = d; }
	V* cn_place_op(int op, V* a, V* b)  // 0 plus, 1 minus
	{
		V* v = fresh(a->tag);
		double s = op == 0 ? 1 : -1;
		full(v)->x = full(a)->x + s * full(b)->x, full(v)->y = full(a)->y + s * full(b)->y, full(v)->z = a->tag == 'p' ? full(a)->z + s * full(b)->z : 0;
		return v;
	}
	V* cn_place_scale(int op, V* a, double k)  // 0 times, 1 divided by
	{
		V* v = fresh(a->tag);
		auto by = [&](double x) { return op == 0 ? x * k : x / k; };
		full(v)->x = by(full(a)->x), full(v)->y = by(full(a)->y), full(v)->z = a->tag == 'p' ? by(full(a)->z) : 0;
		return v;
	}
	double cn_place_size(V* v) { return std::sqrt(full(v)->x * full(v)->x + full(v)->y * full(v)->y + full(v)->z * full(v)->z); }

	// things: spec is "pet\x01name\x01ages" (its kind, then the names of its parts)
	V* cn_thing(const char* spec)
	{
		static std::map<const char*, ThingKind*> kinds;
		static std::mutex kinds_lock;
		std::lock_guard<std::mutex> hold(kinds_lock);
		ThingKind*& kind = kinds[spec];
		if (!kind)
		{
			kind = new ThingKind;
			std::stringstream in(spec);
			std::string word;
			std::getline(in, kind->name, '\x01');
			while (std::getline(in, word, '\x01'))
				kind->fields.push_back(word);
		}
		V* v = fresh('k');
		full(v)->kind = kind;
		full(v)->items.resize(kind->fields.size());
		return v;
	}
	V* cn_load(V* from, V* shape, int is_file, V* kind, int line)  // from: the text itself, or the file's name
	{
		GUARDED(nullptr,
			std::string all = is_file ? stellanova::read_file(full(from)->s, line) : full(from)->s;
			stellanova::SavedReader reader{all};
			stellanova::SavedData d;
			V* out = nullptr;
			bool ok = reader.value(d);
			reader.space();
			if (!ok || reader.i != all.size() || !loaded_into(d, shape, out))
				stellanova::fail(line, (is_file ? "the file \"" + full(from)->s + "\"" : std::string("the text")) + " doesn't hold " + full(kind)->s + ".");
			return out;)
	}
	V* cn_saved_text(V* v, int line) { GUARDED(nullptr, return cn_make_text(saved_of(v, line));) }
	void cn_save_file(V* v, V* path, int line) { GUARDED(, stellanova::write_file(full(path)->s, saved_of(v, line) + "\n", line);) }
	V* cn_sorted_by(V* list, int k)  // 'sorted pets by age': a copy, in order of one part (a number or text), ties kept in order
	{
		V* out = copy_of(list);
		std::stable_sort(full(out)->items.begin(), full(out)->items.end(), [k](const V* a, const V* b) {
			const V* x = full(a)->items[static_cast<size_t>(k)];
			const V* y = full(b)->items[static_cast<size_t>(k)];
			return x->tag == 't' ? full(x)->s < full(y)->s : x->d < y->d;
		});
		return out;
	}
	V* cn_as_kind(V* thing, const char* spec)  // a dog given where a pet is wanted: a copy with just a pet's parts
	{
		V* v = cn_thing(spec);
		for (size_t k = 0; k < full(v)->kind->fields.size(); k++)
			for (size_t j = 0; j < full(thing)->kind->fields.size(); j++)
				if (full(thing)->kind->fields[j] == full(v)->kind->fields[k])
					full(v)->items[k] = copy_of(full(thing)->items[j]);
		return v;
	}
	V* cn_field(V* thing, int k) { return full(thing)->items[static_cast<size_t>(k)]; }
	void cn_field_put(V* thing, int k, V* x) { full(thing)->items[static_cast<size_t>(k)] = copy_of(x); }
	void cn_replace(V* thing, V* with)  // 'set ball to ...' inside a command for a ball: the caller's ball itself changes
	{
		V* fresh_copy = copy_of(with);
		*thing = *fresh_copy;
	}
}
