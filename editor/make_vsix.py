"""Packs editor/vscode into stellanova.vsix, so VS Code can install it:  code --install-extension editor/stellanova.vsix"""
import json
import zipfile
from pathlib import Path

HERE = Path(__file__).parent
SRC = HERE / "vscode"
info = json.loads((SRC / "package.json").read_text(encoding="utf-8"))

manifest = f"""<?xml version="1.0" encoding="utf-8"?>
<PackageManifest Version="2.0.0" xmlns="http://schemas.microsoft.com/developer/vsx-schema/2011">
  <Metadata>
    <Identity Language="en-US" Id="{info['name']}" Version="{info['version']}" Publisher="{info['publisher']}"/>
    <DisplayName>{info['displayName']}</DisplayName>
    <Description xml:space="preserve">{info['description']}</Description>
    <Categories>{','.join(info['categories'])}</Categories>
    <Properties>
      <Property Id="Microsoft.VisualStudio.Code.Engine" Value="{info['engines']['vscode']}"/>
    </Properties>
  </Metadata>
  <Installation><InstallationTarget Id="Microsoft.VisualStudio.Code"/></Installation>
  <Dependencies/>
  <Assets><Asset Type="Microsoft.VisualStudio.Code.Manifest" Path="extension/package.json" Addressable="true"/></Assets>
</PackageManifest>
"""
types = """<?xml version="1.0" encoding="utf-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension=".json" ContentType="application/json"/>
  <Default Extension=".vsixmanifest" ContentType="text/xml"/>
</Types>
"""
out = HERE / "stellanova.vsix"
with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
    z.writestr("[Content_Types].xml", types)
    z.writestr("extension.vsixmanifest", manifest)
    for f in sorted(SRC.rglob("*")):
        if f.is_file():
            z.write(f, "extension/" + f.relative_to(SRC).as_posix())
print(f"Made {out}")
