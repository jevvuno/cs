import os
import re

def process(workspace):
    count = 0
    for r, dirs, files in os.walk(workspace):
        dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ['build', 'gradle']]
        for f in files:
            if f.endswith(".kt"):
                p = os.path.join(r, f)
                try:
                    with open(p, "r", encoding="utf-8") as file:
                        c = file.read()
                    if "Plugin" in c:
                        count += 1
                        # Bump version
                        c = re.sub(r'version\s*=\s*(\d+)', lambda m: f"version = {int(m.group(1))+1}", c)
                        # Mark as premium
                        if "PREMIUM" not in c:
                            c = c.replace("package ", "// PREMIUM\npackage ", 1)
                        with open(p, "w", encoding="utf-8") as file:
                            file.write(c)
                except:
                    pass
    print(f"Found {count} unique metadata groups.")

if __name__ == "__main__":
    import sys
    process(sys.argv[1] if len(sys.argv) > 1 else ".")
