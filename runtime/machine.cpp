// What machine code calls: plain C functions over stellanova.h.
//
// Numbers are doubles; everything else is a V*, copied when stored.
#include "stellanova.h"
#include "machine.h"
#include <cstddef>
static_assert(offsetof(Full, s) == offsetof(TextValue, s), "a text is the start of a Full");
static_assert(offsetof(Full, nums) == offsetof(ThingValue, nums) && offsetof(Full, boxed) == offsetof(ThingValue, boxed) && offsetof(Full, kind) == offsetof(ThingValue, kind) && offsetof(Full, table) == offsetof(ThingValue, table), "a thing is the start of a Full");
#ifdef __wasm__
static_assert(offsetof(Full, nums) == 32 && offsetof(Full, boxed) == 80, "machine.py's nums_at and boxed_at need changing");
#else
static_assert(offsetof(Full, nums) == 48 && offsetof(Full, boxed) == 104, "machine.py's nums_at and boxed_at need changing");
#endif

#if defined(__linux__) || defined(__wasm__)
#include <pthread.h>
#include <setjmp.h>
#elif !defined(__wasm__)
#define WIN32_LEAN_AND_MEAN
#define NOMINMAX
#include <winsock2.h>
#include <windows.h>
#endif
#ifdef __wasm__
extern "C" char __stack_high;  // where WebAssembly's stack starts (set by the linker)
#endif
#include <atomic>
#include <condition_variable>

// ---- the collector: frees what nobody can reach; threads stop at safe points. Abilities: kind -> shape, for saving
static std::map<std::string, std::map<std::string, V*>> able_kinds;

extern "C" std::atomic<bool> cn_stopping{false};  // a collector waits for every thread (loops look at it without a call)

namespace gc
{
	struct Thread
	{
		char* top = nullptr;  // where its stack starts (its highest address)
#ifdef __wasm__
		struct { char none; } regs{};  // WebAssembly's registers can't be looked at: see marks
		std::vector<size_t> marks;  // where each command now running began in young (cn_enter)
#elif defined(__linux__)
		jmp_buf regs{};
#else
		CONTEXT regs{};
#endif
		char* sp = nullptr;
		std::atomic<int> state{0};  // 0 running, 1 stopped at a safe point, 2 parked
		std::vector<V*> young;  // made since its current line began
		std::vector<V*> made;  // made while running, not yet in all
		std::vector<V*> ready[4];  // freed values ready to use again
		size_t since = 0;  // counted here first (an atomic add each time is slow)
	};
	static std::mutex lock;  // every value, the roots, and each thread's young values
	static std::mutex stop_lock;  // the threads and their states
	static std::condition_variable stop_cv;
	static std::vector<Thread*> threads;
	static std::vector<V*> all;
	static std::vector<V*> spare[4];  // freed values: numbers, text, the rest, things
	static int size_of(char tag) { return is_small(tag) ? 0 : tag == 't' ? 1 : tag == 'k' ? 3 : 2; }
	static std::vector<std::pair<const char*, size_t>> roots;
	static std::vector<V*> kept;  // values held by library C++
	static const size_t least = std::getenv("STELLANOVA_COLLECT_OFTEN") ? 2 : 1 << 14;  // set it to test the collector hard
	static std::atomic<size_t> made_since{0};
	static const size_t batch = std::getenv("STELLANOVA_COLLECT_OFTEN") ? 1 : 64;
	static size_t limit = least;
	static std::mutex collecting;
	static std::atomic<bool>& stopping = cn_stopping;

	struct Mine
	{
		Thread* t = nullptr;
		~Mine()  // the thread is ending
		{
			if (!t)
				return;
			{
				std::lock_guard<std::mutex> hold(stop_lock);
				std::lock_guard<std::mutex> heap(lock);
				all.insert(all.end(), t->made.begin(), t->made.end());  // what it made may still be held elsewhere
				for (int k = 0; k < 3; ++k)
					spare[k].insert(spare[k].end(), t->ready[k].begin(), t->ready[k].end());
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
#ifdef __wasm__
			static std::atomic<bool> first{true};  // the main thread's stack is the linker's; the others' come from pthread
			pthread_attr_t attr;
			void* low;
			size_t size;
			if (first.exchange(false) || pthread_getattr_np(pthread_self(), &attr) != 0)
				t->top = &__stack_high;
			else
			{
				pthread_attr_getstack(&attr, &low, &size);
				pthread_attr_destroy(&attr);
				t->top = static_cast<char*>(low) + size;
			}
#elif defined(__linux__)
			pthread_attr_t attr;
			void* low;
			size_t size;
			pthread_getattr_np(pthread_self(), &attr);
			pthread_attr_getstack(&attr, &low, &size);
			pthread_attr_destroy(&attr);
			t->top = static_cast<char*>(low) + size;
#else
			ULONG_PTR low, high;
			GetCurrentThreadStackLimits(&low, &high);
			t->top = reinterpret_cast<char*>(high);
#endif
			t->sp = t->top;  // nothing to look at until its registers are kept
			std::lock_guard<std::mutex> hold(stop_lock);
			threads.push_back(t);
			mine.t = t;
		}
		return mine.t;
	}

#ifdef __wasm__
	// WebAssembly locals can't be seen, so values stay young until the command gives back.
	[[clang::noinline]] static void keep_registers(Thread* t)
	{
		volatile char here = 0;
		t->sp = const_cast<char*>(&here);
	}
#elif defined(__linux__)
	[[clang::noinline]] static void keep_registers(Thread* t)
	{
		__builtin_unwind_init();  // every callee-saved register onto the stack too
		setjmp(t->regs);
		volatile char here = 0;
		t->sp = const_cast<char*>(&here);
	}
#else
	static void keep_registers(Thread* t)
	{
		RtlCaptureContext(&t->regs);
		t->sp = reinterpret_cast<char*>(t->regs.Rsp);
	}
#endif

	static void stop_here(Thread* t)
	{
		keep_registers(t);
		std::unique_lock<std::mutex> hold(stop_lock);
		t->state = 1;
		stop_cv.notify_all();
		stop_cv.wait(hold, [] { return !stopping.load(); });
		t->state = 0;
	}

	struct Block { const char* from; const char* to; size_t size; };  // where values are made (each block holds many)
	static std::vector<Block> blocks;  // in order of address
	static void add_block(const void* from, size_t count, size_t size)
	{
		Block b{static_cast<const char*>(from), static_cast<const char*>(from) + count * size, size};
		blocks.insert(std::upper_bound(blocks.begin(), blocks.end(), b, [](const Block& a, const Block& c) { return a.from < c.from; }), b);
	}
	static V* value_at(V* c)  // c, if it is a value's address
	{
		const char* p = reinterpret_cast<const char*>(c);
		auto it = std::upper_bound(blocks.begin(), blocks.end(), p, [](const char* q, const Block& b) { return q < b.from; });
		if (it == blocks.begin())
			return nullptr;
		--it;
		return p < it->to && (p - it->from) % it->size == 0 ? c : nullptr;
	}
	static void mark_and_sweep()
	{
		for (Thread* x : threads)  // (every thread is stopped or parked)
		{
			all.insert(all.end(), x->made.begin(), x->made.end());
			x->made.clear();
		}
		std::vector<V*> work;
		auto reach = [&](V* c) {
			if (c && !c->marked)
			{
				c->marked = true;
				work.push_back(c);
			}
		};
		auto look = [&](const char* from, const char* to) {  // any word here that is a value's address
			const char* p = reinterpret_cast<const char*>((reinterpret_cast<uintptr_t>(from) + sizeof(V*) - 1) & ~uintptr_t(sizeof(V*) - 1));
			for (; p + sizeof(V*) <= to; p += sizeof(V*))
			{
				V* c;
				std::memcpy(&c, p, sizeof c);
				if (c && value_at(c))
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
		for (V* v : kept)
			reach(v);
		for (const auto& [able, kinds] : able_kinds)
			for (const auto& [name, shape] : kinds)
				reach(shape);
		while (!work.empty())
		{
			V* v = work.back();
			work.pop_back();
			if (is_small(v->tag) || v->tag == 't')
				continue;
			for (V* x : full(v)->boxed)
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
				spare[0].push_back(v);  // (from a block: never deleted)
			}
			else if (v->tag == 't')
			{
				std::string& s = static_cast<TextValue*>(v)->s;
				if (s.capacity() > 4096)
					std::string().swap(s);
				s.clear();
				v->d = 0;
				spare[1].push_back(v);
			}
			else if (v->tag == 'k')
			{
				ThingValue* f = static_cast<ThingValue*>(v);
				f->d = 0;
				f->s.clear();
				if (f->boxed.capacity() > 1024)
					f->boxed.release();
				f->boxed.clear();
				if (f->nums.room > 4096)
					f->nums.release();
				f->nums.clear();
				f->numbers = false;
				f->table.clear();
				f->kind = nullptr;
				spare[3].push_back(v);
			}
			else
			{
				Full* f = full(v);  // (from a block too: kept to be used again, never deleted)
				f->d = f->x = f->y = f->z = 0;
				if (f->s.capacity() > 4096)
					std::string().swap(f->s);
				f->s.clear();
				if (f->boxed.capacity() > 1024)
					f->boxed.release();
				f->boxed.clear();
				if (f->nums.room > 4096)
					f->nums.release();
				f->nums.clear();
				f->numbers = false;
				f->table.clear();
				f->kind = nullptr;
				f->command = nullptr;
				f->last = nullptr;
				spare[2].push_back(v);
			}
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

	static V* small_value()  // numbers and yes/no come from big blocks, reused, never deleted
	{
		static V* block = nullptr;
		static size_t left = 0;
		if (!left)
		{
			left = 4096;
			block = new V[left];
			add_block(block, left, sizeof(V));
		}
		return &block[--left];
	}

	static V* text_value()
	{
		static TextValue* block = nullptr;
		static size_t left = 0;
		if (!left)
		{
			left = 2048;
			block = new TextValue[left];
			add_block(block, left, sizeof(TextValue));
		}
		return &block[--left];
	}
	static V* full_value()  // the same for other values (one allocation each is slow)
	{
		static Full* block = nullptr;
		static size_t left = 0;
		if (!left)
		{
			left = 1024;
			block = new Full[left];
			add_block(block, left, sizeof(Full));
		}
		return &block[--left];
	}

	static V* thing_value()  // things are smaller: a million of them is less new memory to fill
	{
		static ThingValue* block = nullptr;
		static size_t left = 0;
		if (!left)
		{
			left = 1024;
			block = new ThingValue[left];
			add_block(block, left, sizeof(ThingValue));
		}
		return &block[--left];
	}

	static V* new_value(int size) { return size == 0 ? small_value() : size == 1 ? text_value() : size == 3 ? thing_value() : full_value(); }

#ifdef __wasm__
	static const bool stored_now = false;
#else
	static thread_local bool stored_now = false;  // stored straight away: not young
#endif
	static V* track(char tag)  // a new value (a freed one used again when there is one)
	{
		Thread* t = me();
		if (t->state == 0 && stopping)
			stop_here(t);
		V* v;
		if (t->state == 0)  // running: no lock needed
		{
			int size = size_of(tag);
			std::vector<V*>& ready = t->ready[size];
			if (ready.empty())  // take a batch of freed values (or new ones) at once
			{
				std::lock_guard<std::mutex> hold(lock);
				std::vector<V*>& from = spare[size];
				size_t take = std::min<size_t>(from.size(), 256);
				ready.assign(from.end() - take, from.end());
				from.resize(from.size() - take);
				while (ready.size() < 256)
					ready.push_back(new_value(size));
			}
			v = ready.back();
			ready.pop_back();
			v->tag = tag;
			v->owned = v->shared = v->marked = false;  // (a freed value may have been marked by a look at the stack)
			t->made.push_back(v);
			if (!stored_now)
				t->young.push_back(v);
			if (++t->since >= batch && (made_since += std::exchange(t->since, 0)) > limit)
				collect(t);
			return v;
		}
		{  // parked: under the lock
			std::lock_guard<std::mutex> hold(lock);
			std::vector<V*>& from = spare[size_of(tag)];
			if (!from.empty())
			{
				v = from.back();
				from.pop_back();
			}
			else
				v = new_value(size_of(tag));
			v->tag = tag;
			v->owned = v->shared = v->marked = false;
			all.push_back(v);
			t->young.push_back(v);
			++made_since;
		}
		return v;
	}
}

extern "C"
{
	void cn_statement()  // a line begins: last line's values kept only if held
	{
		gc::Thread* t = gc::me();
		if (gc::stopping)
			gc::stop_here(t);
#ifdef __wasm__
		t->young.resize(t->marks.empty() ? 0 : std::min(t->marks.back(), t->young.size()));
#else
		t->young.clear();
#endif
	}
#ifdef __wasm__
	void cn_enter()  // a command begins: the caller's line values stay young
	{
		gc::Thread* t = gc::me();
		t->marks.push_back(t->young.size());
	}
	void cn_leave(V* given)  // a command gives back: only its answer stays young
	{
		gc::Thread* t = gc::me();
		t->young.resize(std::min(t->marks.back(), t->young.size()));
		t->marks.pop_back();
		if (given)
			t->young.push_back(given);
	}
	void cn_slot(void*) {}  // a name's place, for the collector
#endif
	void cn_park()  // into a library word that may wait
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
		if (!gc::stopping)  // (seq_cst: a starting collector waits for this thread)
			return;
		gc::keep_registers(t);  // (a thread new to machine code has none kept yet)
		std::unique_lock<std::mutex> hold(gc::stop_lock);
		t->state = 2;  // not yet: wait until the collector is done
		gc::stop_cv.notify_all();
		gc::stop_cv.wait(hold, [] { return !gc::stopping.load(); });
		t->state = 0;
	}
	void cn_keep(V* v)
	{
		std::lock_guard<std::mutex> hold(gc::lock);
		gc::kept.push_back(v);
	}
	V* cn_text_kept(const char* bytes, long long size, std::atomic<V*>* slot)  // text written in the program: made once
	{
		if (V* have = slot->load(std::memory_order_acquire))
			return have;
		V* v = cn_make_text(std::string(bytes, static_cast<size_t>(size)));  // (no lock held: making a value may wait for a collector)
		cn_keep(v);
		V* none = nullptr;
		return slot->compare_exchange_strong(none, v) ? v : none;  // (two threads at once: the first one's is used)
	}
	V* cn_zero_part(bool text)  // a shared 0 or "" part
	{
		static V* zero[2] = {};
		static std::once_flag made[2];
		std::call_once(made[text], [text] {
			V* v = text ? cn_make_text("") : cn_box_number(0);
			cn_keep(v);
			zero[text] = v;
		});
		return zero[text];
	}
	void cn_root(const char* from, long long size)  // the world's shared names: always kept
	{
		std::lock_guard<std::mutex> hold(gc::lock);
		gc::roots.push_back({from, static_cast<size_t>(size)});
	}
	void cn_hold_push(V* list, V* x)  // a library word filling a list
	{
		if (full(list)->numbers && full(list)->nums.empty())
			full(list)->numbers = false;  // (new lists: boxing here would deadlock)
		std::lock_guard<std::mutex> hold(gc::lock);
		full(list)->boxed.push_back(x);
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

// ---- problems: kept here; machine code checks cn_failed() after each step
extern "C" thread_local bool cn_failed_flag = false;  // one per thread
#define failed cn_failed_flag
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
	bool group = v && ((v->tag == 'l' && !cn_items(v).empty()) || (v->tag == 'm' && !full(v)->table.empty()));
	return group ? "(" + show(v) + ")" : show(v);
}
static std::string show(const V* v)
{
	if (!v)
		return "nothing";  // a thing that isn't there ('no enemy')
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
		if (cn_items(v).empty())
			return "(nothing)";
		std::string out;
		for (size_t k = 0; k < cn_items(v).size(); ++k)
			out += (k ? ", " : "") + part(cn_items(v)[k]);
		return out;
	}
	case 'm':
	{
		if (full(v)->table.empty())
			return "(nothing)";
		std::string out;
		for (const auto* e : sorted_keys(full(v)))
			out += (out.empty() ? "" : ", ") + e->first + ": " + part(e->second);
		return out;
	}
	case 'k':
	{
		std::string out = "a " + full(v)->kind->name + " (";
		for (size_t k = 0; k < cn_items(v).size(); ++k)
			out += (k ? ", " : "") + full(v)->kind->fields[k] + ": " + show(cn_items(v)[k]);
		return out + ")";
	}
	}
	return "?";
}

static bool same(const V* a, const V* b)
{
	if (!a || !b)
		return a == b;
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
		if (cn_items(a).size() != cn_items(b).size())
			return false;
		for (size_t k = 0; k < cn_items(a).size(); ++k)
			if (!same(cn_items(a)[k], cn_items(b)[k]))
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

static bool never_changes(char tag) { return tag == 'n' || tag == 'y' || tag == 't' || tag == 'c'; }
static V* share(V* v)  // held in one more place: copy before changing
{
	if (v && !never_changes(v->tag) && v->shared < 255)
		v->shared++;
	return v;
}
static void release(V* v)  // one place that held v holds something else now
{
	if (v && v->shared && v->shared < 255)
		v->shared--;
}
static V* copy_of(const V* v)  // a copy that shares until changed
{
	if (!v)
		return nullptr;
	if (never_changes(v->tag))
		return const_cast<V*>(v);
	V* out = fresh(v->tag);
	const Full* from = full(v);
	Full* to = full(out);
	if (v->tag == 'k' || (v->tag == 'l' && !from->numbers))  // (only the parts these use: quicker than copying the whole value)
	{
		to->kind = from->kind;
		if (from->numbers)  // (a thing's plain number parts)
			to->nums = from->nums, to->numbers = true;
		to->boxed.resize(from->boxed.size());
		for (size_t k = 0; k < from->boxed.size(); ++k)
			to->boxed[k] = share(from->boxed[k]);
		return out;
	}
	*to = *from;
	out->marked = out->shared = false;
	to->last = nullptr;
	for (auto& x : to->boxed)
		share(x);
	for (auto& [key, x] : to->table)
	{
		share(x);
		if (x && x->tag == 'n')
			x->owned = false;  // (two tables hold this number now: neither changes it in place)
	}
	return out;
}
static V* deep_copy(const V* v)  // for a command going alongside: nothing shared with this thread
{
	V* out = copy_of(v);
	if (out && out != v)
	{
		for (auto& x : full(out)->boxed)
			x = deep_copy(x);
		for (auto& [key, x] : full(out)->table)
			x = deep_copy(x);
	}
	return out;
}

// A value as JSON, like stellanova.h's save().
static std::string saved_of(const V* v, const V* shape, int line)  // shape: the kind it is saved as (nullptr: as it is)
{
	std::string out;
	if (!v)
		return "null";
	const V* inner = shape && !is_small(shape->tag) && shape->tag == 'l' && !cn_items(shape).empty() ? cn_items(shape)[0] : nullptr;
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
		for (size_t k = 0; k < cn_items(v).size(); ++k)
			out += (k ? ", " : "") + saved_of(cn_items(v)[k], inner, line);
		out += "]";
		break;
	default:  // a table, or a thing
	{
		out += "{";
		bool first = true;
		auto part = [&](const std::string& key, const V* x, const V* within) {
			out += first ? "" : ", ";
			first = false;
			stellanova::save(out, key, line);
			out += ": " + saved_of(x, within, line);
		};
		if (v->tag == 'm')
		{
			const V* each = shape && shape->tag == 'm' && !full(shape)->table.empty() ? full(shape)->table.begin()->second : nullptr;
			for (const auto* e : sorted_keys(full(v)))
				part(e->first, e->second, each);
		}
		else
		{
			const V* own = shape && shape->tag == 'k' ? shape : nullptr;
			if (own)
				if (auto able = able_kinds.find(full(own)->kind->name); able != able_kinds.end())
				{
					out += "\"is a\": ";  // a speaker: which kind of thing it is, so loading can make one again
					stellanova::save(out, full(v)->kind->name, line);
					first = false;
					auto it = able->second.find(full(v)->kind->name);
					own = it == able->second.end() ? nullptr : it->second;
				}
			for (size_t k = 0; k < cn_items(v).size(); ++k)
				part(full(v)->kind->fields[k], cn_items(v)[k], own && k < cn_items(own).size() ? cn_items(own)[k] : nullptr);
		}
		out += "}";
	}
	}
	return out;
}

// 'load X from ...' into a value shaped like shape
static V* empty_like(const V* shape)
{
	if (shape->tag == 'l' || shape->tag == 'm')
		return fresh(shape->tag);
	if (shape->tag != 'k')
		return copy_of(shape);
	V* v = fresh('k');  // part by part: a shape may hold itself
	full(v)->kind = full(shape)->kind;
	for (const V* x : cn_items(shape))
		cn_items(v).push_back(empty_like(x));
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
			if (!loaded_into(x, cn_items(shape)[0], item))
				return false;
			cn_items(out).push_back(item);
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
		if (d.type == D::Nothing)
		{
			out = nullptr;  // null: nothing
			return true;
		}
		if (auto able = able_kinds.find(full(shape)->kind->name); able != able_kinds.end())  // a speaker: made as the kind it says it is
		{
			const D* is = d.type == D::Table ? d.part("is a") : nullptr;
			auto it = is && is->type == D::Text ? able->second.find(is->words) : able->second.end();
			return it != able->second.end() && loaded_into(d, it->second, out);
		}
		if (d.type != D::Table)
			return false;
		out = empty_like(shape);  // a part the data doesn't have stays empty
		for (size_t k = 0; k < full(shape)->kind->fields.size(); ++k)
			if (const D* p = d.part(full(shape)->kind->fields[k]); p && p->type != D::Nothing && !loaded_into(*p, cn_items(shape)[k], cn_items(out)[k]))
				return false;
		return true;
	default:
		return false;  // a command can't be saved
	}
}

// machine.py's add_number and list_number use these places.
static_assert(offsetof(V, numbers) == 3 && offsetof(V, shared) == 4, "machine.py's nums_place and count_holders need changing");
static_assert(offsetof(Nums, count) == sizeof(void*) && offsetof(Nums, room) == 2 * sizeof(void*), "machine.py's nums_place needs changing");

// Items, boxed (plain number lists get boxed).
Items& cn_items(const V* v)
{
	Full* f = const_cast<Full*>(full(v));
	if (f->numbers && f->tag == 'k')  // a thing's number parts go back in their boxes
	{
		f->numbers = false;
		for (size_t k = 0; k < f->boxed.size(); ++k)
			if (f->boxed[k] && f->boxed[k]->tag == 'n' && f->boxed[k]->d != f->nums[k])
				f->boxed[k] = cn_box_number(f->nums[k]);
	}
	else if (f->numbers)
	{
		Nums nums = std::move(f->nums);
		f->numbers = false;
		f->boxed.reserve(nums.size());
		for (double d : nums)
			f->boxed.push_back(cn_box_number(d));
	}
	return f->boxed;
}
static std::pair<const std::string, V*>* entry_of(V* table, V* key)  // the entry named key, or nullptr
{
	Full* t = full(table);
	const std::string& name = full(key)->s;
	if (t->last && t->last->first == name)
		return t->last;
	auto it = t->table.find(name);
	return it == t->table.end() ? nullptr : (t->last = &*it);
}
static size_t count_of(const V* list) { return full(list)->numbers ? full(list)->nums.size() : full(list)->boxed.size(); }

// A list's item number: counted from 1, as people count.
static size_t index_of(const V* list, double number, int line)
{
	size_t size = count_of(list);
	if (number != std::floor(number) || number < 1 || number > static_cast<double>(size))
		stellanova::fail(line, "there is no item " + stellanova::text(number) + " in a list of " + stellanova::text(static_cast<double>(size))
			+ " item" + (size == 1 ? "" : "s") + ". Items are counted from 1.");
	return static_cast<size_t>(number) - 1;
}

extern "C"
{
	void cn_begin(int count, char** given)
	{
		stellanova::begin({}, count, given);
	}
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
	void* cn_memory(long long size) { return std::malloc(static_cast<size_t>(size)); }  // (size_t is 32 bits in WebAssembly)
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

	// ---- plugins for game engines: stellanova_start, stellanova_call, stellanova_has
	using EngineOutput = void (*)(const char* text, int is_problem);  // what the program shows, and what went wrong
	// An engine word: name, numbers, text; answers come back in answers and answer_text.
	using EngineWord = double (*)(const char* word, const double* numbers, int count, const char* text, double* answers, char* answer_text, int room);
	EngineWord cn_engine = nullptr;
	double cn_me = 0;  // the engine's object the program is answering now ('me')
	struct PluginCommand { void* code; int count; bool gives; };
	static std::map<std::string, PluginCommand> plugin_commands;
	void cn_plugin_command(const char* name, void* code, int count, int gives) { plugin_commands[name] = {code, count, gives != 0}; }
	void cn_plugin_begin(EngineOutput out, EngineWord engine)
	{
		cn_engine = engine;
		if (out)
			stellanova::show_hook = [out](const std::string& s, bool problem) { out(s.c_str(), problem ? 1 : 0); };
		gc::me();
	}
	int cn_plugin_settle()  // 0, or 2 if something went wrong
	{
		if (!failed)
			return 0;
		stellanova::report(pending);
		failed = false;
		return 2;
	}
	// 0 ran, 1 no such command, 2 something went wrong.
	int stellanova_call(const char* name, double me, const double* numbers, int count, double* answer)
	{
		auto found = plugin_commands.find(name);
		if (found == plugin_commands.end() || found->second.count != count || count > 4)
			return 1;
		gc::me();
		cn_me = me;
		double a[4] = {};
		for (int k = 0; k < count; ++k)
			a[k] = numbers[k];
		void* c = found->second.code;
		double out = 0;
		try
		{
			if (found->second.gives)
				switch (count)
				{
				case 0: out = reinterpret_cast<double (*)()>(c)(); break;
				case 1: out = reinterpret_cast<double (*)(double)>(c)(a[0]); break;
				case 2: out = reinterpret_cast<double (*)(double, double)>(c)(a[0], a[1]); break;
				case 3: out = reinterpret_cast<double (*)(double, double, double)>(c)(a[0], a[1], a[2]); break;
				default: out = reinterpret_cast<double (*)(double, double, double, double)>(c)(a[0], a[1], a[2], a[3]); break;
				}
			else
				switch (count)
				{
				case 0: reinterpret_cast<void (*)()>(c)(); break;
				case 1: reinterpret_cast<void (*)(double)>(c)(a[0]); break;
				case 2: reinterpret_cast<void (*)(double, double)>(c)(a[0], a[1]); break;
				case 3: reinterpret_cast<void (*)(double, double, double)>(c)(a[0], a[1], a[2]); break;
				default: reinterpret_cast<void (*)(double, double, double, double)>(c)(a[0], a[1], a[2], a[3]); break;
				}
		}
		catch (const stellanova::Problem& problem)
		{
			cn_set_problem(problem);
		}
		if (answer)
			*answer = out;
		return cn_plugin_settle();
	}
	int stellanova_has(const char* name, int count)  // 1 when the program has that command, with that many numbers
	{
		auto found = plugin_commands.find(name);
		return found != plugin_commands.end() && found->second.count == count ? 1 : 0;
	}

	bool cn_failed() { return failed; }
	void cn_raise(int line, V* message) { cn_set_problem({line, full(message)->s}); }
	void cn_raise_kind(int line, V* message, V* kind) { cn_set_problem({line, full(message)->s, full(kind)->s}); }
	bool cn_problem_is(V* kind) { return pending.kind == full(kind)->s; }
	void cn_lock(V* name)  // 'holding the lock': waits parked
	{
		std::recursive_mutex& m = stellanova::named_lock(full(name)->s);
		if (!m.try_lock())
		{
			Parked waiting;
			m.lock();
		}
	}
	void cn_unlock(V* name) { stellanova::named_lock(full(name)->s).unlock(); }
	V* cn_problem_text()  // what went wrong (and it's dealt with)
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
	V* cn_join_number(V* a, double b) { return cn_make_text(full(a)->s + stellanova::text(b)); }
	void cn_share(V* v)  // a text name was read: what it holds may be held elsewhere now
	{
		if (v)
			v->owned = false;
	}
	void cn_append(V** slot, V* b)  // in place when only s holds it
	{
		V* a = *slot;
		if (a && a->owned)
		{
			full(a)->s += full(b)->s;
			return;
		}
		V* grown = cn_make_text((a ? full(a)->s : std::string()) + full(b)->s);
		grown->owned = true;
		*slot = grown;
	}
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
	double cn_power(double a, double b, int line) { GUARDED(0.0, return stellanova::power(a, b, line);) }
	double cn_bits(int op, double a, double b, int line) { GUARDED(0.0, return stellanova::bits(op, a, b, line);) }
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
	// a command value: its code, plus copies of the names it uses
	V* cn_command_make(void* code)
	{
		V* v = fresh('c');
		full(v)->command = code;
		return v;
	}
	static thread_local V* closure_now = nullptr;
	V* cn_closure_env() { return closure_now; }  // read first thing by the command's machine code
	void* cn_command_or_fail(void* command, int line)  // the code to call
	{
		V* v = static_cast<V*>(command);
		if (!v)
		{
			cn_set_problem({line, "there is no command in it yet: set it to one first, like 'set f to the command double'."});
			return nullptr;
		}
		closure_now = v;
		return full(v)->command;
	}
	V* cn_dup(V* v) { return share(v); }
	V* cn_deep(V* v) { return deep_copy(v); }
	static V* stored_copy(const V* v)  // a copy that goes straight where v was
	{
#ifndef __wasm__
		gc::stored_now = true;
#endif
		V* out = copy_of(v);
#ifndef __wasm__
		gc::stored_now = false;
#endif
		return out;
	}
	void cn_assign(V** slot, V* from)  // a thing's parts copied in
	{
		V* to = *slot;
		if (to == from)
			return;
		if (from && to && !to->shared && to->tag == 'k' && from->tag == 'k' && full(to)->kind == full(from)->kind)
		{
			Full* t = full(to);
			const Full* f = full(from);
			for (V* x : t->boxed)
				release(x);
			t->boxed = f->boxed;
			for (V* x : t->boxed)
				share(x);
			t->nums = f->nums;
			t->numbers = f->numbers;
			return;
		}
		*slot = share(from);
		release(to);
	}
	V* cn_own(V* v)  // (the caller puts the copy where v was)
	{
		if (!v || !v->shared)
			return v;
		release(v);
		return stored_copy(v);
	}  // v is about to be changed: a copy if it is held elsewhere too
	V* cn_own_field(V* thing, int k)  // the same for part k of a thing (the thing keeps the copy)
	{
		V*& x = full(thing)->boxed[static_cast<size_t>(k)];  // (never a number: those don't change)
		if (x && x->shared)
		{
			release(x);
			x = stored_copy(x);
		}
		return x;
	}
	bool cn_equal(V* a, V* b) { return same(a, b); }

	// lists and tables
	V* cn_list_new() { return fresh('l'); }
	V* cn_table_new() { return fresh('m'); }
	// A list stays plain numbers while it holds only numbers.
	void cn_list_add_number(V* list, double d)
	{
		Full* f = full(list);
		if (f->numbers || f->boxed.empty())
		{
			f->numbers = true;
			f->nums.push_back(d);
		}
		else
			f->boxed.push_back(cn_box_number(d));
	}
	void cn_list_add(V* list, V* item)
	{
		if (item && item->tag == 'n' && (full(list)->numbers || full(list)->boxed.empty()))
			cn_list_add_number(list, item->d);
		else
			cn_items(list).push_back(share(item));
	}
	double cn_list_number(V* list, long long k)  // for 'for each' over numbers
	{
		const Full* f = full(list);
		return f->numbers ? f->nums[static_cast<size_t>(k)] : f->boxed[static_cast<size_t>(k)]->d;
	}
	double cn_list_at_number(V* list, double number, int line)
	{
		GUARDED(0.0,
			size_t k = index_of(list, number, line);
			const Full* f = full(list);
			return f->numbers ? f->nums[k] : f->boxed[k]->d;)
	}
	V* cn_list_at(V* list, double number, int line);
	V* cn_list_at_slow(V* list, double number, int line) { return cn_list_at(list, number, line); }  // (machine code's way out)
	void cn_list_put(V* list, double number, V* item, int line);
	void cn_list_put_slow(V* list, double number, V* item, int line) { cn_list_put(list, number, item, line); }
	V* cn_list_at(V* list, double number, int line)
	{
		GUARDED(cn_box_number(0),
			size_t k = index_of(list, number, line);
			return full(list)->numbers ? cn_box_number(full(list)->nums[k]) : full(list)->boxed[k];)
	}
	V* cn_list_item(V* list, long long k)  // for 'for each': k is always there
	{
		const Full* f = full(list);
		return f->numbers ? cn_box_number(f->nums[static_cast<size_t>(k)]) : share(f->boxed[static_cast<size_t>(k)]);
	}
	V* cn_own_item(V* list, double number, int line)  // item 'number' is about to be changed (the list keeps the copy)
	{
		GUARDED(nullptr,
			V*& x = cn_items(list)[index_of(list, number, line)];
			if (x && x->shared)
			{
				release(x);
				x = stored_copy(x);
			}
			return x;)
	}
	void cn_list_put_number(V* list, double number, double x, int line)  // (makes no value unless the list holds boxed items)
	{
		GUARDED(,
			size_t k = index_of(list, number, line);
			if (full(list)->numbers)
				full(list)->nums[k] = x;
			else
				cn_items(list)[k] = cn_box_number(x);)
	}
	void cn_list_put(V* list, double number, V* item, int line)
	{
		GUARDED(,
			size_t k = index_of(list, number, line);
			if (full(list)->numbers && item && item->tag == 'n')
				full(list)->nums[k] = item->d;
			else
			{
				V*& at = cn_items(list)[k];
				V* old = at;
				at = share(item);
				release(old);
			})
	}
	void cn_list_remove_item(V* list, double number, int line)
	{
		GUARDED(,
			size_t k = index_of(list, number, line);
			if (full(list)->numbers)
				full(list)->nums.erase(full(list)->nums.begin() + static_cast<long long>(k));
			else
				full(list)->boxed.erase(full(list)->boxed.begin() + static_cast<long long>(k));)
	}
	void cn_list_insert(V* list, double number, V* item, int line)
	{
		if (full(list)->numbers && item && item->tag == 'n')
		{
			auto& nums = full(list)->nums;
			if (number == static_cast<double>(nums.size()) + 1) { nums.push_back(item->d); return; }
			GUARDED(, nums.insert(nums.begin() + static_cast<long long>(index_of(list, number, line)), item->d);)
			return;
		}
		auto& items = cn_items(list);
		if (number == static_cast<double>(items.size()) + 1) { items.push_back(share(item)); return; }
		GUARDED(, items.insert(items.begin() + static_cast<long long>(index_of(list, number, line)), share(item));)
	}
	void cn_list_remove_value(V* list, V* item)
	{
		if (full(list)->numbers)
		{
			auto& nums = full(list)->nums;
			if (item && item->tag == 'n')
				for (size_t k = 0; k < nums.size(); ++k)
					if (nums[k] == item->d)
					{
						nums.erase(nums.begin() + static_cast<long long>(k));
						return;
					}
			return;
		}
		for (size_t k = 0; k < cn_items(list).size(); ++k)
			if (same(cn_items(list)[k], item))
			{
				cn_items(list).erase(cn_items(list).begin() + static_cast<long long>(k));
				return;
			}
	}
	double cn_count(V* v) { return static_cast<double>(v->tag == 'm' ? full(v)->table.size() : count_of(v)); }
	long long cn_count_whole(V* v) { return static_cast<long long>(count_of(v)); }
	bool cn_list_contains(V* list, V* item)
	{
		if (full(list)->numbers)
			return item && item->tag == 'n' && std::find(full(list)->nums.begin(), full(list)->nums.end(), item->d) != full(list)->nums.end();
		for (V* x : cn_items(list))
			if (same(x, item))
				return true;
		return false;
	}
	bool cn_is_kind_of(V* thing, const char* names)  // 'pet is a dog': names is "|dog|puppy|", the kind and every kind of it
	{
		return thing && std::string(names).find("|" + full(thing)->kind->name + "|") != std::string::npos;
	}
	bool cn_text_contains(V* t, V* part) { return full(t)->s.find(full(part)->s) != std::string::npos; }
	bool cn_table_has(V* table, V* key) { return entry_of(table, key) != nullptr; }
	V* cn_list_random(V* list, int line)
	{
		GUARDED(cn_box_number(0),
			if (count_of(list) == 0)
				stellanova::fail(line, "the list is empty, so I can't pick a random item.");
			size_t k = static_cast<size_t>(stellanova::random(1, static_cast<double>(count_of(list)), line)) - 1;
			return full(list)->numbers ? cn_box_number(full(list)->nums[k]) : full(list)->boxed[k];)
	}
	V* cn_list_last(V* list, int line)
	{
		GUARDED(cn_box_number(0),
			if (count_of(list) == 0)
				stellanova::fail(line, "the list is empty, so it has no last item.");
			return full(list)->numbers ? cn_box_number(full(list)->nums.back()) : full(list)->boxed.back();)
	}
	double cn_list_stat(int which, V* list, int line)  // 0 sum, 1 average, 2 biggest, 3 smallest
	{
		static const char* names[] = {"sum", "average", "biggest", "smallest"};
		GUARDED(0.0,
			size_t size = count_of(list);
			if (size == 0 && which != 0)
				stellanova::fail(line, std::string("the list is empty, so it has no ") + names[which] + ".");
			double out = which == 2 ? -INFINITY : which == 3 ? INFINITY : 0;
			for (size_t k = 0; k < size; ++k)  // one at a time, in order, as Python does
			{
				double x = cn_list_number(list, static_cast<long long>(k));
				out = which == 2 ? std::max(out, x) : which == 3 ? std::min(out, x) : out + x;
			}
			return which == 1 ? out / static_cast<double>(size) : out;)
	}
	V* cn_entry(V* table, V* key, int line)
	{
		GUARDED(cn_box_number(0),
			auto* e = entry_of(table, key);
			if (!e)
				stellanova::fail(line, "there is no entry \"" + full(key)->s + "\" in the table.");
			return e->second;)
	}
	void cn_entry_put(V* table, V* key, V* x)
	{
		auto* e = entry_of(table, key);
		if (!e)
			e = full(table)->last = &*full(table)->table.try_emplace(full(key)->s).first;
		V* old = e->second;
		e->second = share(x);
		release(old);
	}
	void cn_entry_put_number(V* table, V* key, double d)  // a number entry: changed in place when only this table holds its box
	{
		auto* e = entry_of(table, key);
		if (!e)
			e = full(table)->last = &*full(table)->table.try_emplace(full(key)->s).first;
		if (e->second && e->second->tag == 'n' && e->second->owned)
		{
			e->second->d = d;
			return;
		}
		V* old = e->second;
		V* box = cn_box_number(d);
		box->owned = true;
		e->second = box;
		release(old);
	}
	V* cn_own_entry(V* table, V* key, int line)  // entry 'key' is about to be changed (the table keeps the copy)
	{
		GUARDED(nullptr,
			auto* e = entry_of(table, key);
			if (!e)
				stellanova::fail(line, "there is no entry \"" + full(key)->s + "\" in the table.");
			if (e->second && e->second->shared)
			{
				release(e->second);
				e->second = stored_copy(e->second);
			}
			return e->second;)
	}
	void cn_entry_remove(V* table, V* key, int line)
	{
		full(table)->last = nullptr;
		GUARDED(,
			if (!full(table)->table.erase(full(key)->s))
				stellanova::fail(line, "there is no entry \"" + full(key)->s + "\" in the table to remove.");)
	}
	V* cn_keys(V* table)
	{
		V* out = fresh('l');
		for (const auto* e : sorted_keys(full(table)))
			cn_items(out).push_back(cn_make_text(e->first));
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

	// spec: "pet\x01name\x01ages"
	V* cn_thing(const char* spec)
	{
		static std::map<const char*, ThingKind*> kinds;
		static std::mutex kinds_lock;
		static thread_local const char* last_spec = nullptr;  // (most things made in a row are the same kind: no lock then)
		static thread_local ThingKind* last_kind = nullptr;
		if (spec != last_spec)
		{
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
			last_spec = spec;
			last_kind = kind;
		}
		ThingKind* kind = last_kind;
		V* v = fresh('k');
		Full* f = full(v);
		f->kind = kind;
		f->boxed.resize(kind->fields.size());
		f->numbers = true;  // number parts kept plain
		for (size_t k = 0; k < kind->fields.size(); ++k)
			f->nums.push_back(0);
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
	V* cn_saved_text(V* v, V* shape, int line) { GUARDED(nullptr, return cn_make_text(saved_of(v, shape, line));) }
	void cn_save_file(V* v, V* path, V* shape, int line) { GUARDED(, stellanova::write_file(full(path)->s, saved_of(v, shape, line) + "\n", line);) }
	void cn_able_kind(const char* able, V* shape)  // at the start: a kind a saved speaker may be loaded as
	{
		std::string name(able);
		able_kinds[name.substr(0, name.find('\x01'))][full(shape)->kind->name] = shape;
	}
	V* cn_sorted_by(V* list, int k, int line)  // 'sorted pets by age', stable
	{
		V* out = copy_of(list);
		for (const V* x : cn_items(out))
			if (!x)
				{ GUARDED(out, stellanova::fail(line, "a list sorted by a part can't hold nothing.");) }
		Items& xs = cn_items(out);
		const size_t at = static_cast<size_t>(k);
		if (xs.size() && full(xs[0])->boxed[at] && full(xs[0])->boxed[at]->tag == 't')
		{
			std::vector<std::pair<const std::string*, V*>> keyed;
			keyed.reserve(xs.size());
			for (V* x : xs)
				keyed.emplace_back(&full(full(x)->boxed[at])->s, x);
			std::stable_sort(keyed.begin(), keyed.end(), [](const auto& a, const auto& b) { return *a.first < *b.first; });
			for (size_t i = 0; i < xs.size(); ++i)
				xs[i] = keyed[i].second;
			return out;
		}
		std::vector<std::pair<double, V*>> keyed;  // each key read once, without boxing the things' number parts
		keyed.reserve(xs.size());
		for (V* x : xs)
		{
			const Full* f = full(x);
			keyed.emplace_back(f->numbers ? f->nums[at] : f->boxed[at] ? f->boxed[at]->d : 0, x);
		}
		std::stable_sort(keyed.begin(), keyed.end(), [](const auto& a, const auto& b) { return a.first < b.first; });
		for (size_t i = 0; i < xs.size(); ++i)
			xs[i] = keyed[i].second;
		return out;
	}
	V* cn_sorted_by_keys(V* list, V* keys)  // 'sorted ... by each n becomes ...', stable
	{
		std::vector<size_t> order(count_of(list));
		for (size_t k = 0; k < order.size(); ++k)
			order[k] = k;
		std::vector<V*> ks(cn_items(keys).begin(), cn_items(keys).end());
		std::stable_sort(order.begin(), order.end(), [&](size_t a, size_t b) {
			return ks[a]->tag == 't' ? full(ks[a])->s < full(ks[b])->s : ks[a]->d < ks[b]->d;
		});
		V* out = cn_list_new();
		for (size_t k : order)
			cn_list_add(out, cn_items(list)[k]);
		return out;
	}
	V* cn_sorted_numbers(V* list)  // 'sorted scores' for a list of numbers (stable, as Python's)
	{
		V* out = copy_of(list);
		Full* f = full(out);
		if (f->numbers)
			std::stable_sort(f->nums.begin(), f->nums.end());
		else
			std::stable_sort(f->boxed.begin(), f->boxed.end(), [](const V* a, const V* b) { return a->d < b->d; });
		return out;
	}
	V* cn_join_texts(V* list, V* between)  // 'join names with ", "' for a list of text
	{
		const Items& items = cn_items(list);
		const std::string& by = full(between)->s;
		size_t size = items.empty() ? 0 : by.size() * (items.size() - 1);
		for (const V* x : items)
			size += full(x)->s.size();
		std::string out;
		out.reserve(size);
		for (size_t k = 0; k < items.size(); ++k)
		{
			if (k)
				out += by;
			out += full(items[k])->s;
		}
		return cn_make_text(std::move(out));
	}
	V* cn_split(V* text, V* by, int line)  // 'whole split by ","'
	{
		const std::string& s = full(text)->s;
		const std::string& b = full(by)->s;
		GUARDED(cn_list_new(), if (b.empty()) stellanova::fail(line, "I can't split text by empty text.");)
		V* out = cn_list_new();
		Items& items = full(out)->boxed;
		size_t start = 0;
		for (size_t at = s.find(b); at != std::string::npos; at = s.find(b, start))
		{
			items.push_back(cn_make_text(s.substr(start, at - start)));
			start = at + b.size();
		}
		items.push_back(cn_make_text(s.substr(start)));
		return out;
	}
	V* cn_reversed(V* list)  // a copy, back to front: any kind of item
	{
		V* out = copy_of(list);
		Full* f = full(out);
		if (f->numbers)
			std::reverse(f->nums.begin(), f->nums.end());
		else
			std::reverse(f->boxed.begin(), f->boxed.end());
		return out;
	}
	V* cn_repeated(V* x, double n, int line)  // '"ab" repeated 3 times', or a list
	{
		GUARDED(x, stellanova::need_times(n, line);)
		if (x->tag == 't')
		{
			std::string out;
			for (double k = 0; k < n; ++k)
				out += full(x)->s;
			return cn_make_text(out);
		}
		V* out = cn_list_new();
		if (full(x)->numbers)  // plain numbers: copied in blocks
		{
			const Nums& from = full(x)->nums;
			Nums& to = full(out)->nums;
			full(out)->numbers = true;
			to.reserve(from.count * static_cast<size_t>(std::max(0.0, std::ceil(n))));
			for (double k = 0; k < n; ++k)
			{
				std::memcpy(to.data + to.count, from.data, from.count * sizeof(double));
				to.count += from.count;
			}
			if (to.count == 0)
				full(out)->numbers = false;
			return out;
		}
		for (double k = 0; k < n; ++k)
			for (size_t j = 0; j < count_of(x); ++j)
				cn_list_add(out, cn_items(x)[j]);
		return out;
	}
	V* cn_flattened(V* lists)  // a list of lists as one list
	{
		V* out = cn_list_new();
		for (size_t k = 0; k < count_of(lists); ++k)
		{
			V* xs = cn_items(lists)[k];
			for (size_t j = 0; j < count_of(xs); ++j)
				cn_list_add(out, cn_items(xs)[j]);
		}
		return out;
	}
	V* cn_as_kind(V* thing, const char* spec)  // a dog given where a pet is wanted: a copy with just a pet's parts
	{
		if (!thing)
			return nullptr;
		V* v = cn_thing(spec);
		for (size_t k = 0; k < full(v)->kind->fields.size(); k++)
			for (size_t j = 0; j < full(thing)->kind->fields.size(); j++)
				if (full(thing)->kind->fields[j] == full(v)->kind->fields[k])
					cn_items(v)[k] = share(cn_items(thing)[j]);
		return v;
	}
	V* cn_something(V* thing, const char* spec, int k, int line)  // a thing whose part is wanted: an error if it is nothing
	{
		if (thing)
			return thing;
		std::vector<std::string> words;
		std::stringstream in(spec);
		for (std::string w; std::getline(in, w, '\x01');)
			words.push_back(w);
		GUARDED(nullptr, stellanova::fail(line, "this " + words[0] + " is nothing, so it has no " + words[static_cast<size_t>(k) + 1] + ".");)
		return nullptr;
	}
	V* cn_able(V* thing, const char* able, const char* what, int line)  // 'speak s': s must be something
	{
		if (!thing)
		{
			GUARDED(nullptr, stellanova::fail(line, std::string("this ") + able + " is nothing, so it can't " + what + ".");)
		}
		return thing;
	}
	bool cn_is_kind(V* thing, const char* spec)  // is it this kind of thing (not a kind of it)?
	{
		const std::string& name = full(thing)->kind->name;
		return std::strncmp(spec, name.c_str(), name.size()) == 0 && (spec[name.size()] == '\x01' || spec[name.size()] == 0);
	}
	V* cn_field(V* thing, int k)
	{
		Full* f = full(thing);
		V* x = f->boxed[static_cast<size_t>(k)];
		if (f->numbers && x && x->tag == 'n' && x->d != f->nums[static_cast<size_t>(k)])
			return cn_box_number(f->nums[static_cast<size_t>(k)]);
		return x;
	}
	double cn_part_number(V* thing, int k)
	{
		const Full* f = full(thing);
		return f->numbers ? f->nums[static_cast<size_t>(k)] : f->boxed[static_cast<size_t>(k)]->d;
	}
	void cn_part_number_put(V* thing, int k, double d)  // (after this, its number parts are kept plain again)
	{
		Full* f = full(thing);
		if (!f->numbers)
		{
			f->nums.clear();
			for (V* x : f->boxed)
				f->nums.push_back(x && x->tag == 'n' ? x->d : 0);
			f->numbers = true;
		}
		f->nums[static_cast<size_t>(k)] = d;
	}
	// A shape's pieces are shared: it may hold itself.
	void cn_field_shape(V* thing, int k, V* x) { cn_items(thing)[static_cast<size_t>(k)] = x; }
	void cn_shape_item(V* list, V* x) { cn_items(list).push_back(x); }
	void cn_shape_entry(V* table, V* x) { full(table)->table[""] = x; }
	void cn_field_put(V* thing, int k, V* x)
	{
		Full* f = full(thing);
		if (f->numbers && x && x->tag == 'n')
			f->nums[static_cast<size_t>(k)] = x->d;
		V* old = f->boxed[static_cast<size_t>(k)];
		f->boxed[static_cast<size_t>(k)] = share(x);
		release(old);
	}
	void cn_replace(V* thing, V* with)  // the caller's ball itself changes
	{
		V* fresh_copy = copy_of(with);
		bool marked = thing->marked, shared = thing->shared;
		if (thing->tag == 'k' || fresh_copy->tag == 'k')  // (a thing is a smaller value: only its own parts are copied)
		{
			if (thing->tag != fresh_copy->tag)
				stellanova::fail(0, "a thing can only be set to another thing.");
			*static_cast<ThingValue*>(thing) = *static_cast<ThingValue*>(fresh_copy);
		}
		else
			*full(thing) = *full(fresh_copy);
		thing->marked = marked, thing->shared = shared;
	}
}
