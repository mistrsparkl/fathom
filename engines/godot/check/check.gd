# The check scene: engines/check/words.stella on Mover and Target, and a ball falling onto Target. Run by check.py.
extends Node

var _time := 0.0


func _ready() -> void:
	add_child(_object("Box", Node3D.new(), Vector3(8, 0, 0), null, false))  # (first: Mover's 'begin' looks for it)
	add_child(_object("Target", Area3D.new(), Vector3.ZERO, BoxShape3D.new(), true))
	add_child(_object("Player", RigidBody3D.new(), Vector3(0, 4, 0), SphereShape3D.new(), false))
	add_child(_object("Mover", Node3D.new(), Vector3(1, 2, -3), null, true))


func _object(called: String, node: Node3D, at: Vector3, shape: Shape3D, program: bool) -> Node3D:
	node.name = called
	node.position = at
	node.add_child(MeshInstance3D.new())
	if shape:
		var outline := CollisionShape3D.new()
		outline.shape = shape
		node.add_child(outline)
	if program:
		var script := StellanovaScript.new()
		script.program = "res://words.stella"
		node.add_child(script)
	return node


func _process(seconds: float) -> void:
	_time += seconds
	if _time < 3:
		return
	for node in get_children():
		var look: StandardMaterial3D = node.get_child(0).material_override
		var colour := "none" if look == null else "red" if look.albedo_color == Color.RED else "blue" if look.albedo_color == Color.BLUE else "other"
		var p: Vector3 = node.global_position
		print("CHECK %s|%f|%f|%f|%f|%s" % [node.name, p.x, p.y, -p.z, -rad_to_deg(node.global_rotation.y), colour])
	get_tree().quit()
