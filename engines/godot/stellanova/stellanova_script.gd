## Runs a Stellanova program on its parent node. Places: X, Y, -Z.
class_name StellanovaScript
extends Node

## A .stella file. Rebuilt when the game starts, if changed.
@export_file("*.stella") var program: String

static var _programs := {}  # a .stella path -> its program's number (0: it couldn't be loaded)
static var _nodes := {}  # each node a program knows is a number (0 is none)
static var _numbers := {}  # a node's instance id -> its number
static var _next := 1
static var _answers: Answers
static var _keys := {}  # key -> [frame asked, held before, held now]

var _program := 0
var _has := {}  # "every frame/1" -> does the program have it


func _ready() -> void:
	if program == "":
		push_error("Stellanova: %s has a Stellanova Script without a program: choose a .stella file." % get_parent().name)
		return
	if _answers == null:
		_answers = Answers.new()
		Stellanova.set_engine(_answers.answer)
	_answers.tree = get_tree()
	_program = _load(program)
	if _program == 0:
		return
	var me := get_parent()
	if me is RigidBody3D:
		me.contact_monitor = true
		me.max_contacts_reported = maxi(me.max_contacts_reported, 4)
	if me.has_signal("body_entered"):
		me.body_entered.connect(func(other): _call("touched", [number_of(other)]))
	if me.has_signal("area_entered"):
		me.area_entered.connect(func(other): _call("touched", [number_of(other)]))
	_call("begin", [])


func _process(seconds: float) -> void:
	if _program != 0:
		_call("every frame", [seconds])


func _call(command: String, numbers: Array) -> void:
	var key := "%s/%d" % [command, numbers.size()]
	if not _has.has(key):
		_has[key] = Stellanova.has_command(_program, command, numbers.size()) == 1
	if _has[key]:
		var n := numbers + [0.0, 0.0, 0.0, 0.0]
		Stellanova.call_command(_program, command, number_of(get_parent()), numbers.size(), float(n[0]), float(n[1]), float(n[2]), float(n[3]))


static func number_of(node: Node) -> float:
	if node == null:
		return 0
	var id := node.get_instance_id()
	if not _numbers.has(id):
		_numbers[id] = _next
		_nodes[_next] = node
		_next += 1
	return _numbers[id]


static func node_of(number: float) -> Node:
	var node = _nodes.get(int(number))
	return node if is_instance_valid(node) else null


static func _load(path: String) -> int:
	if _programs.has(path):
		return _programs[path]
	var made := made_for(path) if OS.has_feature("editor") else \
		OS.get_executable_path().get_base_dir().path_join(path.get_file().get_basename() + _suffix())  # (an exported game keeps them next to itself)
	var number := 0
	if made != "" and FileAccess.file_exists(made):
		number = Stellanova.open(made)
	if number == 0:
		push_error("Stellanova: %s isn't built: look above for its mistakes." % path)
	_programs[path] = number
	return number


static func _suffix() -> String:
	return ".dll" if OS.get_name() == "Windows" else ".so"


## The built plugin for a .stella file, or "".
static func made_for(path: String) -> String:
	var script := ProjectSettings.globalize_path(path)
	var made := script.get_basename() + _suffix()
	if FileAccess.file_exists(script) and (not FileAccess.file_exists(made) or FileAccess.get_modified_time(made) < FileAccess.get_modified_time(script)):
		_build(script)
	return made if FileAccess.file_exists(made) else ""


static func _build(script: String) -> void:
	var note := FileAccess.get_file_as_string("res://addons/stellanova/home.txt").split("\n")
	if note.size() < 2 or not FileAccess.file_exists(note[0].strip_edges().path_join("stellanova.py")):
		push_error("Stellanova: I can't find Stellanova: run 'stellanova godot <this project's folder>' again.")
		return
	var said := []
	if OS.execute(note[1].strip_edges(), [note[0].strip_edges().path_join("stellanova.py"), "plugin", script], said, true) != 0:
		push_error("Stellanova: " + "".join(said).strip_edges())


static func _key_of(name: String) -> Key:
	match name:
		"left": return KEY_LEFT
		"right": return KEY_RIGHT
		"up": return KEY_UP
		"down": return KEY_DOWN
		"space": return KEY_SPACE
		"enter": return KEY_ENTER
		"escape": return KEY_ESCAPE
		"shift": return KEY_SHIFT
		"control": return KEY_CTRL
		"tab": return KEY_TAB
		"backspace": return KEY_BACKSPACE
	return OS.find_keycode_from_string(name.to_upper())


static func _pressed(name: String) -> bool:  # held now, but not the frame before
	var code := _key_of(name)
	var now := Input.is_physical_key_pressed(code)
	var seen: Array = _keys.get(code, [-1, false, false])
	var frame := Engine.get_process_frames()
	if seen[0] != frame:
		seen = [frame, seen[2], now]
		_keys[code] = seen
	return now and not seen[1]


## The engine words of 'use: engine', for every program.
class Answers:
	var tree: SceneTree

	func answer(word: String, _count: int, a: float, b: float, c: float, d: float, text: String) -> Variant:
		match word:
			"say":
				print(text)
				return 0
			"problem":
				push_error("Stellanova: " + text)
				return 0
			"named":
				return StellanovaScript.number_of(tree.root.find_child(text, true, false))
			"key held":
				return 1 if Input.is_physical_key_pressed(StellanovaScript._key_of(text)) else 0
			"key pressed":
				return 1 if StellanovaScript._pressed(text) else 0
			"frame time":
				return tree.root.get_process_delta_time()
		var it := StellanovaScript.node_of(a)
		if it == null:
			return 0  # (a node that has gone: its words do nothing)
		match word:
			"name":
				return String(it.name)
			"remove":
				it.queue_free()
				return 0
		if not it is Node3D:
			return 0
		var spot := it as Node3D
		match word:
			"place":
				var p := spot.global_position
				return Vector3(p.x, p.y, -p.z)
			"put":
				spot.global_position = Vector3(b, c, -d)
			"move":
				spot.global_position += Vector3(b, c, -d)
			"turn":
				return -rad_to_deg(spot.global_rotation.y)
			"turn by":
				spot.global_rotate(Vector3.UP, deg_to_rad(-b))
			"copy":
				var made := spot.duplicate() as Node3D
				var at := Vector3(b, c, -d)
				var holder := spot.get_parent()
				made.position = (holder as Node3D).to_local(at) if holder is Node3D else at  # (placed first: its 'begin' runs as it is added)
				holder.add_child(made, true)
				return StellanovaScript.number_of(made)
			"colour":
				var look := StandardMaterial3D.new()
				look.albedo_color = Color.from_string(text, Color.WHITE)
				for mesh in [spot] + spot.find_children("*", "MeshInstance3D", true, false):  # (false: made while running too)
					if mesh is MeshInstance3D:
						mesh.material_override = look
		return 0
