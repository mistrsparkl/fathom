# The check: a coin with a Stellanova program, and a ball that falls into it. Run by check.py.
extends SceneTree

var _time := 0.0


func _initialize() -> void:
	var coin := Area3D.new()
	coin.name = "Coin"
	var box := CollisionShape3D.new()
	box.shape = BoxShape3D.new()
	coin.add_child(box)
	var script := StellanovaScript.new()
	script.program = "res://coin.stella"
	coin.add_child(script)
	root.add_child(coin)
	var ball := RigidBody3D.new()
	ball.name = "Player"
	var round := CollisionShape3D.new()
	round.shape = SphereShape3D.new()
	ball.add_child(round)
	ball.add_child(MeshInstance3D.new())
	ball.position = Vector3(0, 4, 0)
	root.add_child(ball)


func _process(seconds: float) -> bool:
	_time += seconds
	if _time < 3:
		return false
	for node in root.get_children():
		if node is Node3D:
			print("CHECK %s at %s turn %d" % [node.name, node.global_position, roundi(-node.global_rotation_degrees.y)])
	return true
