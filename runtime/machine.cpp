// What a program made into machine code (by machine.py) calls: plain C functions over stellanova.h.
// Compiled once into runtime/built/stellanova_machine.obj; a program's own code never becomes C++.
//
// Numbers are doubles and yes/no is a bool. Everything else (text, lists, tables, places, things) is a V*:
// made here, copied when stored (as Python and C++ copy), and shown and compared the way Python does.
#include "stellanova.h"
#include "machine.h"

// shortcut: values are never freed; upgrade to reference counting before long-running programs make values in loops.
static V* fresh(char tag)
{
	V* v = new V;
	v->tag = tag;
	return v;
}
V* cn_make_text(std::string s)
{
	V* v = fresh('t');
	v->s = std::move(s);
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
	bool group = (v->tag == 'l' && !v->items.empty()) || (v->tag == 'm' && !v->table.empty());
	return group ? "(" + show(v) + ")" : show(v);
}
static std::string show(const V* v)
{
	switch (v->tag)
	{
	case 'n': return stellanova::text(v->d);
	case 'y': return v->d != 0 ? "yes" : "no";
	case 't': return v->s;
	case 'p': return stellanova::text(v->x) + " horizontal " + stellanova::text(v->y) + " vertical " + stellanova::text(v->z) + " depth";
	case 'f': return stellanova::text(v->x) + " horizontal " + stellanova::text(v->y) + " vertical";
	case 'c': return "a command";
	case 'l':
	{
		if (v->items.empty())
			return "(nothing)";
		std::string out;
		for (size_t k = 0; k < v->items.size(); ++k)
			out += (k ? ", " : "") + part(v->items[k]);
		return out;
	}
	case 'm':
	{
		if (v->table.empty())
			return "(nothing)";
		std::string out;
		for (const auto& [key, x] : v->table)
			out += (out.empty() ? "" : ", ") + key + ": " + part(x);
		return out;
	}
	case 'k':
	{
		std::string out = "a " + v->kind->name + " (";
		for (size_t k = 0; k < v->items.size(); ++k)
			out += (k ? ", " : "") + v->kind->fields[k] + ": " + show(v->items[k]);
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
	case 't': return a->s == b->s;
	case 'p': case 'f': return a->x == b->x && a->y == b->y && a->z == b->z;
	case 'k':
		if (a->kind->name != b->kind->name)
			return false;
		[[fallthrough]];
	case 'l':
		if (a->items.size() != b->items.size())
			return false;
		for (size_t k = 0; k < a->items.size(); ++k)
			if (!same(a->items[k], b->items[k]))
				return false;
		return true;
	case 'm':
		if (a->table.size() != b->table.size())
			return false;
		for (const auto& [key, x] : a->table)
		{
			auto it = b->table.find(key);
			if (it == b->table.end() || !same(x, it->second))
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
	V* out = new V(*v);
	for (auto& x : out->items)
		x = copy_of(x);
	for (auto& [key, x] : out->table)
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
	case 't': stellanova::save(out, v->s, line); break;
	case 'p': stellanova::save(out, FVector(v->x, v->y, v->z), line); break;
	case 'f': stellanova::save(out, FVector2D(v->x, v->y), line); break;
	case 'c': stellanova::fail(line, "I can't save a command in a file."); break;
	case 'l':
		out += "[";
		for (size_t k = 0; k < v->items.size(); ++k)
			out += (k ? ", " : "") + saved_of(v->items[k], line);
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
			for (const auto& [key, x] : v->table)
				part(key, x);
		else
			for (size_t k = 0; k < v->items.size(); ++k)
				part(v->kind->fields[k], v->items[k]);
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
		for (V*& x : v->items)
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
			if (!loaded_into(x, shape->items[0], item))
				return false;
			out->items.push_back(item);
		}
		return true;
	case 'm':
		if (d.type != D::Table)
			return false;
		out = fresh('m');
		for (const auto& [key, x] : d.parts)
		{
			V* item = nullptr;
			if (!loaded_into(x, shape->table.begin()->second, item))
				return false;
			out->table[key] = item;
		}
		return true;
	case 'k':
		if (d.type != D::Table)
			return false;
		out = empty_like(shape);  // a part the data doesn't have stays empty
		for (size_t k = 0; k < shape->kind->fields.size(); ++k)
			if (const D* p = d.part(shape->kind->fields[k]); p && !loaded_into(*p, shape->items[k], out->items[k]))
				return false;
		return true;
	default:
		return false;  // a command can't be saved
	}
}

// A list's item number: counted from 1, as people count.
static size_t index_of(const V* list, double number, int line)
{
	if (number != std::floor(number) || number < 1 || number > static_cast<double>(list->items.size()))
		stellanova::fail(line, "there is no item " + stellanova::text(number) + " in a list of " + stellanova::text(static_cast<double>(list->items.size()))
			+ " item" + (list->items.size() == 1 ? "" : "s") + ". Items are counted from 1.");
	return static_cast<size_t>(number) - 1;
}

extern "C"
{
	void cn_begin(int count, char** given) { stellanova::begin({}, count, given); }
	void cn_add_file(const char* name) { stellanova::files.push_back(name); }
	int cn_end()
	{
		if (!failed)
			stellanova::wait_for_others();
		std::cout << std::flush;
		if (!failed)
			return 0;
		stellanova::report(pending);
		std::cerr << std::flush;
		std::_Exit(1);  // commands still going alongside stop too
	}
	void cn_meanwhile(void (*command)(void*), void* names)  // 'meanwhile ...': names holds its own copy of every name it uses
	{
		stellanova::meanwhile([command, names] {
			command(names);
			if (failed)
				throw stellanova::Problem(pending);
		});
	}
	void cn_wait_for_others() { stellanova::wait_for_others(); }

	bool cn_failed() { return failed; }
	void cn_raise(int line, V* message) { cn_set_problem({line, message->s}); }
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
	V* cn_join(V* a, V* b) { return cn_make_text(a->s + b->s); }
	bool cn_same_text(V* a, V* b) { return a->s == b->s; }
	void cn_say(V* t) { stellanova::say({t->s}); }
	V* cn_ask_text(V* question) { return cn_make_text(stellanova::ask_text(question->s)); }
	double cn_ask_number(V* question) { return stellanova::ask_number(question->s); }
	bool cn_ask_yes_no(V* question) { return stellanova::ask_yes_no(question->s); }
	double cn_letters(V* t) { return stellanova::letters(t->s); }
	double cn_to_number(V* t, int line) { GUARDED(0.0, return stellanova::to_number(t->s, line);) }

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
		v->command = command;
		return v;
	}
	void* cn_unbox_command(V* v) { return v->command; }
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
	void cn_list_add(V* list, V* item) { list->items.push_back(copy_of(item)); }
	V* cn_list_at(V* list, double number, int line) { GUARDED(cn_box_number(0), return list->items[index_of(list, number, line)];) }
	V* cn_list_item(V* list, long long k) { return list->items[static_cast<size_t>(k)]; }  // for 'for each': k is always there
	void cn_list_put(V* list, double number, V* item, int line) { GUARDED(, list->items[index_of(list, number, line)] = copy_of(item);) }
	void cn_list_remove_item(V* list, double number, int line) { GUARDED(, list->items.erase(list->items.begin() + static_cast<long long>(index_of(list, number, line)));) }
	void cn_list_remove_value(V* list, V* item)
	{
		for (size_t k = 0; k < list->items.size(); ++k)
			if (same(list->items[k], item))
			{
				list->items.erase(list->items.begin() + static_cast<long long>(k));
				return;
			}
	}
	double cn_count(V* v) { return static_cast<double>(v->tag == 'm' ? v->table.size() : v->items.size()); }
	long long cn_count_whole(V* v) { return static_cast<long long>(v->items.size()); }
	bool cn_list_contains(V* list, V* item)
	{
		for (V* x : list->items)
			if (same(x, item))
				return true;
		return false;
	}
	bool cn_text_contains(V* t, V* part) { return t->s.find(part->s) != std::string::npos; }
	bool cn_table_has(V* table, V* key) { return table->table.count(key->s) > 0; }
	V* cn_list_random(V* list, int line)
	{
		GUARDED(cn_box_number(0),
			if (list->items.empty())
				stellanova::fail(line, "the list is empty, so I can't pick a random item.");
			return list->items[static_cast<size_t>(stellanova::random(1, static_cast<double>(list->items.size()), line)) - 1];)
	}
	V* cn_list_last(V* list, int line)
	{
		GUARDED(cn_box_number(0),
			if (list->items.empty())
				stellanova::fail(line, "the list is empty, so it has no last item.");
			return list->items.back();)
	}
	double cn_list_stat(int which, V* list, int line)  // 0 sum, 1 average, 2 biggest, 3 smallest
	{
		static const char* names[] = {"sum", "average", "biggest", "smallest"};
		GUARDED(0.0,
			if (list->items.empty() && which != 0)
				stellanova::fail(line, std::string("the list is empty, so it has no ") + names[which] + ".");
			double out = which == 2 ? -INFINITY : which == 3 ? INFINITY : 0;
			for (V* x : list->items)  // one at a time, in order, as Python does
				out = which == 2 ? std::max(out, x->d) : which == 3 ? std::min(out, x->d) : out + x->d;
			return which == 1 ? out / static_cast<double>(list->items.size()) : out;)
	}
	V* cn_entry(V* table, V* key, int line)
	{
		GUARDED(cn_box_number(0),
			auto it = table->table.find(key->s);
			if (it == table->table.end())
				stellanova::fail(line, "there is no entry \"" + key->s + "\" in the table.");
			return it->second;)
	}
	void cn_entry_put(V* table, V* key, V* x) { table->table[key->s] = copy_of(x); }
	void cn_entry_remove(V* table, V* key, int line)
	{
		GUARDED(,
			if (!table->table.erase(key->s))
				stellanova::fail(line, "there is no entry \"" + key->s + "\" in the table to remove.");)
	}
	V* cn_keys(V* table)
	{
		V* out = fresh('l');
		for (const auto& [key, x] : table->table)
			out->items.push_back(cn_make_text(key));
		return out;
	}

	// places
	V* cn_place(double x, double y, double z)
	{
		V* v = fresh('p');
		v->x = x, v->y = y, v->z = z;
		return v;
	}
	V* cn_flat(double x, double y)
	{
		V* v = fresh('f');
		v->x = x, v->y = y;
		return v;
	}
	double cn_part(V* v, int k) { return k == 0 ? v->x : k == 1 ? v->y : v->z; }
	void cn_part_put(V* v, int k, double d) { (k == 0 ? v->x : k == 1 ? v->y : v->z) = d; }
	V* cn_place_op(int op, V* a, V* b)  // 0 plus, 1 minus
	{
		V* v = fresh(a->tag);
		double s = op == 0 ? 1 : -1;
		v->x = a->x + s * b->x, v->y = a->y + s * b->y, v->z = a->tag == 'p' ? a->z + s * b->z : 0;
		return v;
	}
	V* cn_place_scale(int op, V* a, double k)  // 0 times, 1 divided by
	{
		V* v = fresh(a->tag);
		auto by = [&](double x) { return op == 0 ? x * k : x / k; };
		v->x = by(a->x), v->y = by(a->y), v->z = a->tag == 'p' ? by(a->z) : 0;
		return v;
	}
	double cn_place_size(V* v) { return std::sqrt(v->x * v->x + v->y * v->y + v->z * v->z); }

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
		v->kind = kind;
		v->items.resize(kind->fields.size());
		return v;
	}
	V* cn_load(V* from, V* shape, int is_file, V* kind, int line)  // from: the text itself, or the file's name
	{
		GUARDED(nullptr,
			std::string all = is_file ? stellanova::read_file(from->s, line) : from->s;
			stellanova::SavedReader reader{all};
			stellanova::SavedData d;
			V* out = nullptr;
			bool ok = reader.value(d);
			reader.space();
			if (!ok || reader.i != all.size() || !loaded_into(d, shape, out))
				stellanova::fail(line, (is_file ? "the file \"" + from->s + "\"" : std::string("the text")) + " doesn't hold " + kind->s + ".");
			return out;)
	}
	V* cn_saved_text(V* v, int line) { GUARDED(nullptr, return cn_make_text(saved_of(v, line));) }
	void cn_save_file(V* v, V* path, int line) { GUARDED(, stellanova::write_file(path->s, saved_of(v, line) + "\n", line);) }
	V* cn_sorted_by(V* list, int k)  // 'sorted pets by age': a copy, in order of one part (a number or text), ties kept in order
	{
		V* out = copy_of(list);
		std::stable_sort(out->items.begin(), out->items.end(), [k](const V* a, const V* b) {
			const V* x = a->items[static_cast<size_t>(k)];
			const V* y = b->items[static_cast<size_t>(k)];
			return x->tag == 't' ? x->s < y->s : x->d < y->d;
		});
		return out;
	}
	V* cn_as_kind(V* thing, const char* spec)  // a dog given where a pet is wanted: a copy with just a pet's parts
	{
		V* v = cn_thing(spec);
		for (size_t k = 0; k < v->kind->fields.size(); k++)
			for (size_t j = 0; j < thing->kind->fields.size(); j++)
				if (thing->kind->fields[j] == v->kind->fields[k])
					v->items[k] = copy_of(thing->items[j]);
		return v;
	}
	V* cn_field(V* thing, int k) { return thing->items[static_cast<size_t>(k)]; }
	void cn_field_put(V* thing, int k, V* x) { thing->items[static_cast<size_t>(k)] = copy_of(x); }
	void cn_replace(V* thing, V* with)  // 'set ball to ...' inside a command for a ball: the caller's ball itself changes
	{
		V* fresh_copy = copy_of(with);
		*thing = *fresh_copy;
	}
}
