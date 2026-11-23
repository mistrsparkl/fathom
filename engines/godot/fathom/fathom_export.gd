## Adds every built .fathom program to the export. shortcut: builds for this computer's system only.
@tool
class_name FathomExport
extends EditorExportPlugin


func _get_name() -> String:
	return "Fathom"


func _export_begin(_features: PackedStringArray, _is_debug: bool, _path: String, _flags: int) -> void:
	for script in _fathom_files("res://"):
		var made := FathomScript.made_for(script)
		if made == "":
			push_error("Fathom: %s isn't in the exported game: look above for its mistakes." % script)
		else:
			add_shared_object(made, PackedStringArray(), "")


func _fathom_files(folder: String) -> Array[String]:
	var found: Array[String] = []
	for file in DirAccess.get_files_at(folder):
		if file.get_extension() == "fathom":
			found.append(folder.path_join(file))
	for inner in DirAccess.get_directories_at(folder):
		if not inner.begins_with("."):
			found.append_array(_fathom_files(folder.path_join(inner)))
	return found
