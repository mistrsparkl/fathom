## Puts the built programs next to an exported game.
@tool
extends EditorPlugin

var _export: FathomExport


func _enter_tree() -> void:
	_export = FathomExport.new()
	add_export_plugin(_export)


func _exit_tree() -> void:
	remove_export_plugin(_export)
