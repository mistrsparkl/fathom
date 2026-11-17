// Godot's side of Stellanova: a GDExtension giving GDScript the class Stellanova, whose static methods load a program
// made with 'stellanova plugin', call its commands, and hand its engine words to a Callable (stellanova_script.gd).
// Every input and answer is a Variant, so Godot's own types never need to be laid out here.
// 'stellanova godot <project>' builds this into stellanova_godot.dll with clang.
#include "gdextension_interface.h"
#include <cstring>
#include <string>
#include <vector>
#ifdef _WIN32
#include <windows.h>
#else
#include <dlfcn.h>
#endif

namespace
{
	struct Variant { alignas(8) unsigned char bytes[64]; };  // (room for any Variant, single or double precision)
	struct Opaque { alignas(8) unsigned char bytes[16]; };  // a String or StringName

	using OutputFn = void (*)(const char*, int);
	using EngineFn = double (*)(const char*, const double*, int, const char*, double*, char*, int);
	using StartFn = int (*)(OutputFn, EngineFn);
	using CallFn = int (*)(const char*, double, const double*, int, double*);
	using HasFn = int (*)(const char*, int);
	struct Program { void* library; CallFn call; HasFn has; };
	std::vector<Program> programs;  // a program's number is its place here, from 1

	GDExtensionInterfaceGetProcAddress find;
	GDExtensionClassLibraryPtr library;
	GDExtensionInterfaceVariantCall variant_call;
	GDExtensionInterfaceVariantNewCopy variant_copy;
	GDExtensionInterfaceVariantDestroy variant_destroy;
	GDExtensionInterfaceVariantGetType variant_type;
	GDExtensionInterfaceVariantGetIndexed variant_indexed;
	GDExtensionInterfaceGetVariantFromTypeConstructor from_type;
	GDExtensionInterfaceGetVariantToTypeConstructor to_type;
	GDExtensionInterfaceVariantGetPtrDestructor destructor;
	GDExtensionInterfaceStringNewWithUtf8Chars string_new;
	GDExtensionInterfaceStringToUtf8Chars string_utf8;
	GDExtensionInterfaceStringNameNewWithUtf8Chars name_new;
	Variant engine;  // the Callable answering engine words
	bool have_engine = false;

	Opaque name_of(const char* s) { Opaque n; name_new(&n, s); return n; }  // (StringNames live as long as the extension)

	double number_of(GDExtensionConstVariantPtr v)
	{
		GDExtensionVariantType t = variant_type(v);
		if (t == GDEXTENSION_VARIANT_TYPE_FLOAT)
		{
			double d = 0;
			to_type(GDEXTENSION_VARIANT_TYPE_FLOAT)(&d, const_cast<GDExtensionVariantPtr>(v));
			return d;
		}
		if (t == GDEXTENSION_VARIANT_TYPE_INT)
		{
			int64_t n = 0;
			to_type(GDEXTENSION_VARIANT_TYPE_INT)(&n, const_cast<GDExtensionVariantPtr>(v));
			return static_cast<double>(n);
		}
		if (t == GDEXTENSION_VARIANT_TYPE_BOOL)
		{
			GDExtensionBool b = 0;
			to_type(GDEXTENSION_VARIANT_TYPE_BOOL)(&b, const_cast<GDExtensionVariantPtr>(v));
			return b ? 1 : 0;
		}
		return 0;
	}

	std::string text_of(GDExtensionConstVariantPtr v)
	{
		if (variant_type(v) != GDEXTENSION_VARIANT_TYPE_STRING)
			return "";
		Opaque s;
		to_type(GDEXTENSION_VARIANT_TYPE_STRING)(&s, const_cast<GDExtensionVariantPtr>(v));
		std::string out(static_cast<size_t>(string_utf8(&s, nullptr, 0)), '\0');
		string_utf8(&s, out.data(), static_cast<GDExtensionInt>(out.size()));
		destructor(GDEXTENSION_VARIANT_TYPE_STRING)(&s);
		return out;
	}

	void make_number(GDExtensionUninitializedVariantPtr into, double d) { from_type(GDEXTENSION_VARIANT_TYPE_FLOAT)(into, &d); }
	void make_int(GDExtensionUninitializedVariantPtr into, int64_t n) { from_type(GDEXTENSION_VARIANT_TYPE_INT)(into, &n); }
	void make_text(GDExtensionUninitializedVariantPtr into, const char* s)
	{
		Opaque str;
		string_new(&str, s);
		from_type(GDEXTENSION_VARIANT_TYPE_STRING)(into, &str);
		destructor(GDEXTENSION_VARIANT_TYPE_STRING)(&str);
	}

	// The engine's answer to a word: engine.call(word, count, a, b, c, d, text) gives a number, a Vector3 or a String.
	double ask(const char* word, const double* n, int count, const char* text, double* answers, char* answer_text, int room)
	{
		if (!have_engine)
			return 0;
		Variant args[7];
		make_text(&args[0], word);
		make_int(&args[1], count);
		for (int k = 0; k < 4; ++k)
			make_number(&args[2 + k], k < count ? n[k] : 0);
		make_text(&args[6], text ? text : "");
		GDExtensionConstVariantPtr given[7];
		for (int k = 0; k < 7; ++k)
			given[k] = &args[k];
		static Opaque call = name_of("call");
		Variant back;
		GDExtensionCallError error{};
		variant_call(&engine, &call, given, 7, &back, &error);
		for (Variant& a : args)
			variant_destroy(&a);
		double out = 0;
		GDExtensionVariantType t = variant_type(&back);
		if (t == GDEXTENSION_VARIANT_TYPE_VECTOR3)
			for (int k = 0; k < 3; ++k)
			{
				Variant part;
				GDExtensionBool valid = 0, outside = 0;
				variant_indexed(&back, k, &part, &valid, &outside);
				answers[k] = number_of(&part);
				variant_destroy(&part);
			}
		else if (t == GDEXTENSION_VARIANT_TYPE_STRING)
		{
			std::string s = text_of(&back);
			size_t size = s.size() < static_cast<size_t>(room > 0 ? room - 1 : 0) ? s.size() : static_cast<size_t>(room > 0 ? room - 1 : 0);
			if (room > 0)
			{
				std::memcpy(answer_text, s.data(), size);
				answer_text[size] = 0;
			}
		}
		else
			out = number_of(&back);
		variant_destroy(&back);
		return out;
	}

	void show(const char* text, int is_problem)
	{
		double none[1] = {};
		char nothing[1] = {};
		ask(is_problem ? "problem" : "say", none, 0, text, none, nothing, 0);
	}

	void* open_library(const std::string& path)
	{
#ifdef _WIN32
		int size = MultiByteToWideChar(CP_UTF8, 0, path.c_str(), -1, nullptr, 0);
		std::wstring wide(static_cast<size_t>(size), L'\0');
		MultiByteToWideChar(CP_UTF8, 0, path.c_str(), -1, wide.data(), size);
		return LoadLibraryW(wide.c_str());
#else
		return dlopen(path.c_str(), RTLD_NOW);
#endif
	}
	void* find_in(void* lib, const char* name)
	{
#ifdef _WIN32
		return reinterpret_cast<void*>(GetProcAddress(static_cast<HMODULE>(lib), name));
#else
		return dlsym(lib, name);
#endif
	}

	const Program* program_of(GDExtensionConstVariantPtr v)
	{
		size_t k = static_cast<size_t>(number_of(v));
		return k >= 1 && k <= programs.size() && programs[k - 1].library ? &programs[k - 1] : nullptr;
	}

	// The methods. Each gets its inputs as Variants and puts its answer into r.
	void open(const GDExtensionConstVariantPtr* a, GDExtensionVariantPtr r)  // open(path) -> the program's number, or 0
	{
		void* lib = open_library(text_of(a[0]));
		StartFn start = lib ? reinterpret_cast<StartFn>(find_in(lib, "stellanova_start")) : nullptr;
		if (!start)
			return make_int(r, 0);
		programs.push_back({lib, reinterpret_cast<CallFn>(find_in(lib, "stellanova_call")), reinterpret_cast<HasFn>(find_in(lib, "stellanova_has"))});
		int64_t number = static_cast<int64_t>(programs.size());
		start(show, ask);
		make_int(r, number);
	}
	void call_command(const GDExtensionConstVariantPtr* a, GDExtensionVariantPtr r)  // (program, name, me, count, a, b, c, d) -> 0, 1 or 2
	{
		const Program* p = program_of(a[0]);
		if (!p)
			return make_int(r, 1);
		double n[4] = {number_of(a[4]), number_of(a[5]), number_of(a[6]), number_of(a[7])};
		double answer = 0;
		make_int(r, p->call(text_of(a[1]).c_str(), number_of(a[2]), n, static_cast<int>(number_of(a[3])), &answer));
	}
	void has_command(const GDExtensionConstVariantPtr* a, GDExtensionVariantPtr r)  // (program, name, count) -> 1 or 0
	{
		const Program* p = program_of(a[0]);
		make_int(r, p && p->has(text_of(a[1]).c_str(), static_cast<int>(number_of(a[2]))) == 1 ? 1 : 0);
	}
	void set_engine(const GDExtensionConstVariantPtr* a, GDExtensionVariantPtr r)  // (callable)
	{
		if (have_engine)
			variant_destroy(&engine);
		variant_copy(&engine, a[0]);
		have_engine = true;
		make_int(r, 0);
	}
	void close_all(const GDExtensionConstVariantPtr*, GDExtensionVariantPtr r)
	{
		for (Program& p : programs)
		{
#ifdef _WIN32
			FreeLibrary(static_cast<HMODULE>(p.library));
#else
			dlclose(p.library);
#endif
			p.library = nullptr;
		}
		programs.clear();
		make_int(r, 0);
	}

	using Method = void (*)(const GDExtensionConstVariantPtr*, GDExtensionVariantPtr);
	void call_any(void* m, GDExtensionClassInstancePtr, const GDExtensionConstVariantPtr* a, GDExtensionInt, GDExtensionVariantPtr r, GDExtensionCallError* e)
	{
		e->error = GDEXTENSION_CALL_OK;
		reinterpret_cast<Method>(m)(a, r);
	}
	void ptrcall_any(void* m, GDExtensionClassInstancePtr, const GDExtensionConstTypePtr* a, GDExtensionTypePtr r)
	{
		// (every input and the answer are Variants, so a pointer call holds Variants too; the answer is made fresh, then copied in)
		Variant made;
		reinterpret_cast<Method>(m)(reinterpret_cast<const GDExtensionConstVariantPtr*>(a), &made);
		variant_destroy(r);
		variant_copy(r, &made);
		variant_destroy(&made);
	}

	void add_method(const char* name, Method m, uint32_t count)
	{
		static Opaque any = name_of(""), blank;
		static bool made = false;
		if (!made)
		{
			string_new(&blank, "");
			made = true;
		}
		std::vector<GDExtensionPropertyInfo> args(count);
		std::vector<Opaque> names(count);
		std::vector<GDExtensionClassMethodArgumentMetadata> meta(count, GDEXTENSION_METHOD_ARGUMENT_METADATA_NONE);
		for (uint32_t k = 0; k < count; ++k)
		{
			names[k] = name_of(("input" + std::to_string(k + 1)).c_str());
			args[k] = {GDEXTENSION_VARIANT_TYPE_NIL, &names[k], &any, 0, &blank, 131072};  // (any Variant: PROPERTY_USAGE_NIL_IS_VARIANT)
		}
		Opaque method = name_of(name), back = name_of("");
		GDExtensionPropertyInfo answer = {GDEXTENSION_VARIANT_TYPE_NIL, &back, &any, 0, &blank, 131072};
		GDExtensionClassMethodInfo info{};
		info.name = &method;
		info.method_userdata = reinterpret_cast<void*>(m);
		info.call_func = call_any;
		info.ptrcall_func = ptrcall_any;
		info.method_flags = GDEXTENSION_METHOD_FLAG_STATIC;
		info.has_return_value = 1;
		info.return_value_info = &answer;
		info.return_value_metadata = GDEXTENSION_METHOD_ARGUMENT_METADATA_NONE;
		info.argument_count = count;
		info.arguments_info = args.data();
		info.arguments_metadata = meta.data();
		static Opaque cls = name_of("Stellanova");
		reinterpret_cast<GDExtensionInterfaceClassdbRegisterExtensionClassMethod>(find("classdb_register_extension_class_method"))(library, &cls, &info);
	}

	void free_instance(void*, GDExtensionClassInstancePtr) {}
	GDExtensionClassCallVirtual no_virtual(void*, GDExtensionConstStringNamePtr, uint32_t) { return nullptr; }  // (it overrides nothing)

	void initialize(void*, GDExtensionInitializationLevel level)
	{
		if (level != GDEXTENSION_INITIALIZATION_SCENE)
			return;
		static Opaque cls = name_of("Stellanova"), parent = name_of("Object");
		static Opaque no_icon;
		string_new(&no_icon, "");
		GDExtensionClassCreationInfo4 info{};
		info.is_abstract = 1;
		info.is_exposed = 1;
		info.icon_path = &no_icon;  // (Godot reads it, so it can't be left out)
		info.create_instance_func = nullptr;  // (abstract: nothing is made of it, only its static methods are called)
		info.free_instance_func = free_instance;
		info.get_virtual_func = no_virtual;
		reinterpret_cast<GDExtensionInterfaceClassdbRegisterExtensionClass4>(find("classdb_register_extension_class4"))(library, &cls, &parent, &info);
		add_method("open", open, 1);
		add_method("call_command", call_command, 8);
		add_method("has_command", has_command, 3);
		add_method("set_engine", set_engine, 1);
		add_method("close_all", close_all, 0);
	}
	void deinitialize(void*, GDExtensionInitializationLevel) {}
}

extern "C"
#ifdef _WIN32
__declspec(dllexport)
#endif
GDExtensionBool stellanova_godot_init(GDExtensionInterfaceGetProcAddress get, GDExtensionClassLibraryPtr lib, GDExtensionInitialization* init)
{
	find = get;
	library = lib;
	variant_call = reinterpret_cast<GDExtensionInterfaceVariantCall>(get("variant_call"));
	variant_copy = reinterpret_cast<GDExtensionInterfaceVariantNewCopy>(get("variant_new_copy"));
	variant_destroy = reinterpret_cast<GDExtensionInterfaceVariantDestroy>(get("variant_destroy"));
	variant_type = reinterpret_cast<GDExtensionInterfaceVariantGetType>(get("variant_get_type"));
	variant_indexed = reinterpret_cast<GDExtensionInterfaceVariantGetIndexed>(get("variant_get_indexed"));
	from_type = reinterpret_cast<GDExtensionInterfaceGetVariantFromTypeConstructor>(get("get_variant_from_type_constructor"));
	to_type = reinterpret_cast<GDExtensionInterfaceGetVariantToTypeConstructor>(get("get_variant_to_type_constructor"));
	destructor = reinterpret_cast<GDExtensionInterfaceVariantGetPtrDestructor>(get("variant_get_ptr_destructor"));
	string_new = reinterpret_cast<GDExtensionInterfaceStringNewWithUtf8Chars>(get("string_new_with_utf8_chars"));
	string_utf8 = reinterpret_cast<GDExtensionInterfaceStringToUtf8Chars>(get("string_to_utf8_chars"));
	name_new = reinterpret_cast<GDExtensionInterfaceStringNameNewWithUtf8Chars>(get("string_name_new_with_utf8_chars"));
	init->minimum_initialization_level = GDEXTENSION_INITIALIZATION_SCENE;
	init->initialize = initialize;
	init->deinitialize = deinitialize;
	init->userdata = nullptr;
	return 1;
}
