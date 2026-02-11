import os
import re

# =========================================================
# CONFIG
# =========================================================
API_URL = "http://172.83.15.6:3000"  # IP VPS

# =========================================================
# LICENSE MANAGER
# =========================================================
def get_license_manager_code(plugin_class):
    return f"""
// ==================================================================
// 🔒 PREMIUM LICENSE MANAGER (INJECTED)
// ==================================================================
object LicenseManager {{
    private const val API_URL = "{API_URL}"
    private const val PREFS_NAME = "premium_prefs"
    private const val KEY_LICENSE = "license_key"
    
    private var cachedStatus: String? = null
    private var cacheTime: Long = 0
    private const val CACHE_MS = 5 * 60 * 1000L

    data class LicenseResponse(
        @com.fasterxml.jackson.annotation.JsonProperty("status") val status: String,
        @com.fasterxml.jackson.annotation.JsonProperty("message") val message: String
    )

    fun getSavedKey(): String {{
        val ctx = {plugin_class}.context ?: return ""
        val prefs = ctx.getSharedPreferences(PREFS_NAME, 0)
        return prefs.getString(KEY_LICENSE, "") ?: ""
    }}

    fun saveKey(key: String) {{
        val ctx = {plugin_class}.context ?: return
        ctx.getSharedPreferences(PREFS_NAME, 0).edit().putString(KEY_LICENSE, key).apply()
        cachedStatus = null
    }}

    suspend fun check(apiName: String) {{
        val key = getSavedKey()
        if (cachedStatus == "active" && System.currentTimeMillis() - cacheTime < CACHE_MS) return

        if (key.isBlank()) {{
            throw ErrorLoadingException("🔒 PREMIUM: Masukkan Key di Search (cari 'key:CS-XXXX')")
        }}

        try {{
            val ctx = {plugin_class}.context
            val deviceId = if (ctx != null) android.provider.Settings.Secure.getString(ctx.contentResolver, android.provider.Settings.Secure.ANDROID_ID) else "unknown"

            val response = app.post(
                "$API_URL/api/validate",
                json = mapOf("key" to key, "device_id" to deviceId),
                timeout = 10
            )

            val json = com.lagradost.cloudstream3.mapper.readValue<LicenseResponse>(response.text)
            
            if (json.status != "active") {{
                throw ErrorLoadingException("🔒 BLOCKED: ${{json.message}}")
            }}

            cachedStatus = "active"
            cacheTime = System.currentTimeMillis()

        }} catch (e: Exception) {{
            if (e is ErrorLoadingException) throw e
            if (cachedStatus == "active") return
            throw ErrorLoadingException("🔒 Gagal koneksi lisensi")
        }}
    }}
}}
"""

def inject_imports(content):
    imports = [
        "import android.provider.Settings",
        "import com.lagradost.cloudstream3.app",
        "import com.lagradost.cloudstream3.ErrorLoadingException",
        "import com.lagradost.cloudstream3.mapper",
        "import android.content.Context"
    ]
    
    # Check package line
    pkg_match = re.search(r"^package .*$", content, re.MULTILINE)
    if pkg_match:
        end_idx = pkg_match.end()
        # Add imports if missing
        to_add = []
        for imp in imports:
            if imp not in content:
                to_add.append(imp)
        
        if to_add:
            block = "\n" + "\n".join(to_add) + "\n"
            content = content[:end_idx] + block + content[end_idx:]
    return content

def inject_context_to_plugin(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Find class X : Plugin()
    # Regex: class \w+ : Plugin()
    match = re.search(r"class\s+(\w+)\s*:\s*Plugin\(\)", content)
    if not match:
        return None, content

    plugin_class = match.group(1)
    print(f"🧩 Found Plugin Class: {plugin_class} in {file_path}")

    # Inject companion object & load method override
    if "companion object" not in content:
        # Inject inside class
        # Find { after class declaration
        class_start = match.end()
        brace_idx = content.find("{", class_start)
        if brace_idx != -1:
            injection = f"""
    companion object {{
        var context: Context? = null
    }}
    override fun load(context: Context) {{
        super.load(context)
        {plugin_class}.context = context
    }}
            """
            # Check if load already exists
            if "override fun load" in content:
                 # Too complex to patch existing load, skip for now or append
                 print(f"⚠️ Warning: {plugin_class} has custom load, skipping context injection (might break)")
            else:
                 content = content[:brace_idx+1] + injection + content[brace_idx+1:]
                 content = inject_imports(content)

    return plugin_class, content

def inject_protection(file_path, plugin_class):
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    if ": MainAPI()" not in content:
        return content

    print(f"🛡️ Protecting: {file_path} (Using context from {plugin_class})")
    
    content = inject_imports(content)

    # Inject LicenseManager
    if "object LicenseManager" not in content:
        content += "\n" + get_license_manager_code(plugin_class)

    # Inject checks
    methods = ["getMainPage", "search", "load", "loadLinks"]
    for m in methods:
        matches = re.finditer(f"suspend\s+fun\s+{m}", content)
        for match in matches:
            start_idx = match.start()
            brace_idx = content.find("{", start_idx)
            if brace_idx != -1:
                if "LicenseManager.check" in content[brace_idx:brace_idx+200]: continue
                injection = '\n        LicenseManager.check(name)\n'
                content = content[:brace_idx+1] + injection + content[brace_idx+1:]

    # Inject Key Input in Search
    search_match = re.search(r"suspend\s+fun\s+search.*{", content)
    if search_match:
        s_end = search_match.end()
        # Find first brace
        brace_idx = content.find("{", search_match.start())
        if brace_idx != -1 and "key:" not in content[brace_idx:brace_idx+500]:
             logic = """
        if (query.startsWith("key:")) {
            val k = query.substringAfter("key:").trim()
            LicenseManager.saveKey(k)
            throw ErrorLoadingException("✅ Key Saved: $k")
        }
             """
             content = content[:brace_idx+1] + logic + content[brace_idx+1:]
    
    return content

# =========================================================
# MAIN
# =========================================================
# 1. Scan for Plugins & Inject Context
package_to_plugin = {}

for root, dirs, files in os.walk("."):
    for file in files:
        if file.endswith(".kt"):
            path = os.path.join(root, file)
            # Check for package
            with open(path, 'r', encoding='utf-8') as f:
                c = f.read()
            pkg_m = re.search(r"^package\s+([\w\.]+)", c, re.MULTILINE)
            if not pkg_m: continue
            pkg_name = pkg_m.group(1)

            # Try inject Plugin context
            p_class, new_content = inject_context_to_plugin(path)
            if p_class:
                package_to_plugin[pkg_name] = p_class
                with open(path, 'w', encoding='utf-8') as f:
                    f.write(new_content)

print(f"📦 Found Plugins: {package_to_plugin}")

# 2. Inject Protection using mapped Plugin classes
for root, dirs, files in os.walk("."):
    for file in files:
        if file.endswith(".kt"):
            path = os.path.join(root, file)
            with open(path, 'r', encoding='utf-8') as f:
                c = f.read()
            pkg_m = re.search(r"^package\s+([\w\.]+)", c, re.MULTILINE)
            if not pkg_m: continue
            pkg_name = pkg_m.group(1)

            if pkg_name in package_to_plugin:
                # Same package, safe to use plugin class directly
                new_c = inject_protection(path, package_to_plugin[pkg_name])
                if new_c != c:
                    with open(path, 'w', encoding='utf-8') as f:
                        f.write(new_c)

print("✅ ALL DONE")
