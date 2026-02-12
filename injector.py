    pattern = r"(version\s*=?\s*)(\d+)"
    def replace(m):
        prefix = m.group(1)
        version = int(m.group(2))
        return f"{prefix}{version + 1}"
    
    new_content = re.sub(pattern, replace, content)
    if new_content == content:
        pattern2 = r'("version"\s*:\s*)(\d+)'
        new_content = re.sub(pattern2, replace, content)
    return new_content


def process_plugins(workspace_dir):
    license_code = get_license_manager_code()
    plugin_count = 0
    
    for root, dirs, files in os.walk(workspace_dir):
        # Skip hidden dirs and common non-plugin dirs
        dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ['build', 'gradle']]
        
        for file in files:
            if file.endswith(".kt"):
                path = os.path.join(root, file)
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        content = f.read()
                    
                    # Detect if it's a plugin main class
                    if re.search(r"class\s+\w+Plugin\s*:\s*Plugin", content):
                        plugin_count += 1
                        print(f"Found plugin: {file}")
                        
                        modified = False
                        # 1. Bump version
                        old_content = content
                        content = bump_version(content)
                        if content != old_content:
                            modified = True
                        
                        # 2. Inject LicenseManager if missing
                        if "object LicenseManager" not in content:
                            package_match = re.search(r"^package\s+.*", content, re.MULTILINE)
                            if package_match:
                                end = package_match.end()
                                content = content[:end] + "\n\n" + license_code + content[end:]
                                modified = True
                        
                        # 3. Inject check calls into suspend functions
                        suspend_funs = re.findall(r"suspend\s+fun\s+(\w+)", content)
                        for m in suspend_funs:
                            if m not in ["check"]:
                                # Simplified pattern for injection
                                func_pattern = r"(suspend\s+fun\s+" + m + r"\s*\([^\{]*\)\s*\{)"
                                if f"LicenseManager.check('{m}')" not in content:
                                    content = re.sub(func_pattern, r'\1\n        LicenseManager.check("' + m + r'")', content)
                                    modified = True
                        
                        if modified:
                            with open(path, "w", encoding="utf-8") as f:
                                f.write(content)
                except Exception as e:
                    print(f"Error processing {file}: {e}")
    
    print(f"Found {plugin_count} unique metadata groups.")


if __name__ == '__main__':
    import sys
    workspace = sys.argv[1] if len(sys.argv) > 1 else "."
    process_plugins(workspace)

