"""Checks that the website's code has no syntax errors (a broken page would show nothing to readers)."""
import re, subprocess, sys, tempfile, os
bad = 0
for page in ["docs/index.html", "docs/community/index.html"]:
    html = open(page, encoding="utf-8").read()
    for i, js in enumerate(re.findall(r"<script>(.*?)</script>", html, re.S)):
        with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as f:
            f.write(js)
        r = subprocess.run(["node", "--check", f.name], capture_output=True, text=True)
        os.unlink(f.name)
        print(("PASS  " if r.returncode == 0 else "FAIL  ") + f"{page} script {i + 1}" + ("" if r.returncode == 0 else "\n" + r.stderr[:500]))
        bad += r.returncode != 0
sys.exit(1 if bad else 0)
