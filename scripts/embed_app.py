#!/usr/bin/env python3
"""Copy app/app.py into the launch template user data in infrastructure/main.yaml.

The application ships inside the CloudFormation template so the stack has no
dependency on an external artifact store. Edit app/app.py, then run:

    python3 scripts/embed_app.py
"""
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
TEMPLATE = ROOT / "infrastructure" / "main.yaml"
APP = ROOT / "app" / "app.py"
START = "# >>> app/app.py (inserted by scripts/embed_app.py)"
END = "# <<< app/app.py"

app = APP.read_text()
if "${" in app:
    sys.exit("app.py must not contain '${' - CloudFormation !Sub would try to substitute it")

text = TEMPLATE.read_text()
match = re.search(r"^( *)" + re.escape(START) + r"\n.*?^\1" + re.escape(END) + r"\n",
                  text, re.S | re.M)
if not match:
    sys.exit("markers not found in " + str(TEMPLATE))
indent = match.group(1)
body = "".join((indent + line).rstrip() + "\n" for line in app.splitlines())
block = f"{indent}{START}\n{body}{indent}{END}\n"
TEMPLATE.write_text(text[:match.start()] + block + text[match.end():])
print(f"embedded {len(app.splitlines())} lines into {TEMPLATE.relative_to(ROOT)} "
      f"({TEMPLATE.stat().st_size} bytes)")
