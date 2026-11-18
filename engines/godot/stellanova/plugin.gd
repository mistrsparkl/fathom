## Puts the built programs next to an exported game.
@tool
extends EditorPlugin

var _export: StellanovaExport


func _enter_tree() -> void:
	_export = StellanovaExport.new()
	add_export_plugin(_export)


func _exit_tree() -> void:
	remove_export_plugin(_export)
