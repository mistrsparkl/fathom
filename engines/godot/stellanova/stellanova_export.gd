## Adds every built .stella program to the export. shortcut: builds for this computer's system only.
@tool
class_name StellanovaExport
extends EditorExportPlugin


func _get_name() -> String:
	return "Stellanova"


func _export_begin(_features: PackedStringArray, _is_debug: bool, _path: String, _flags: int) -> void:
	for script in _stella_files("res://"):
		var made := StellanovaScript.made_for(script)
		if made == "":
			push_error("Stellanova: %s isn't in the exported game: look above for its mistakes." % script)
		else:
			add_shared_object(made, PackedStringArray(), "")


func _stella_files(folder: String) -> Array[String]:
	var found: Array[String] = []
	for file in DirAccess.get_files_at(folder):
		if file.get_extension() == "stella":
			found.append(folder.path_join(file))
	for inner in DirAccess.get_directories_at(folder):
		if not inner.begins_with("."):
			found.append_array(_stella_files(folder.path_join(inner)))
	return found
