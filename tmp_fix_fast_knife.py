from pathlib import Path
import re

p = Path(r"c:\Users\Daniel\Documents\Github\Key-Ops-Toolkit\operators\fast_knife.py")
text = p.read_text(encoding="utf-8")
pattern = re.compile(
    r"class FastKnifeOperator\(bpy\.types\.Operator\):\n(?P<body>.*?)(?:\nclass FastKnife\(FastKnifeOperator\):\n)(?P<tail>.*)\Z",
    re.S,
)
m = pattern.search(text)
if not m:
    raise SystemExit("Pattern not found")
new = "class FastKnife(bpy.types.Operator):\n" + m.group("body") + "\n" + m.group("tail")
p.write_text(new, encoding="utf-8")
print("patched")
