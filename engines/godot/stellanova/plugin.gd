## Puts each .stella program, made into a plugin, next to an exported game (StellanovaScript loads it from there).
@tool
extends EditorPlugin

var _export: StellanovaExport


func _enter_tree() -> void:
	_export = StellanovaExport.new()
	add_export_plugin(_export)


func _exit_tree() -> void:
	remove_export_plugin(_export)
