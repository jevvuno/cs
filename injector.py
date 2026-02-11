import os
import re

# =========================================================
# CONFIG - Ganti IP VPS Anda
# =========================================================
API_URL = "http://172.83.15.6:3000"

# =========================================================
# LICENSE MANAGER CODE (IP-BASED AUTH)
# =========================================================
def get_license_manager_code():
    return f"""
// ===================================
// PREMIUM LICENSE MANAGER (IP-BASED)
// ===================================
var premiumContext: android.content.Context? = null

object LicenseManager {{

    private const val API_URL = "{API_URL}"
    
    private var cachedStatus: String? = null
    private var cacheTime: Long = 0
    private const val CACHE_MS = 30 * 1000L

    data class LicenseResponse(
        @com.fasterxml.jackson.annotation.JsonProperty("status") val status: String = "",
        @com.fasterxml.jackson.annotation.JsonProperty("message") val message: String = ""
    )

    suspend fun check(apiName: String) {{
        if (cachedStatus == "active" && System.currentTimeMillis() - cacheTime < CACHE_MS) return

        try {{
            // Get unique Android Device ID
            val ctx = premiumContext
            val deviceId = if (ctx != null) android.provider.Settings.Secure.getString(ctx.contentResolver, android.provider.Settings.Secure.ANDROID_ID) else "unknown"

            // Call API to check if THIS IP + Device is authorized
            val response = com.lagradost.cloudstream3.app.get(
                "$API_URL/api/check-ip?device_id=$deviceId",
                timeout = 10
            )

            val json = com.lagradost.cloudstream3.utils.AppUtils.tryParseJson<LicenseResponse>(response.text)

            if (json == null) {{
                cachedStatus = null
                throw com.lagradost.cloudstream3.ErrorLoadingException("Gagal koneksi ke server lisensi")
            }}

            if (json.status != "active") {{
                cachedStatus = null
                val msg = json.message
                if (msg.contains("IP belum terdaftar")) {{
                    throw com.lagradost.cloudstream3.ErrorLoadingException("Akses Ditolak: Silakan REFRESH Repository Anda untuk aktivasi ulang.")
                }}
                throw com.lagradost.cloudstream3.ErrorLoadingException("BLOCKED: $msg")
            }}

            cachedStatus = "active"
            cacheTime = System.currentTimeMillis()

        }} catch (e: Exception) {{
            // ALWAYS block on error - never allow bypass
            cachedStatus = null
            if (e is com.lagradost.cloudstream3.ErrorLoadingException) throw e
            throw com.lagradost.cloudstream3.ErrorLoadingException("Gagal cek lisensi: " + e.message)
        }}
    }}
}}
"""

# =========================================================
# HELPER FUNCTIONS
# =========================================================
def inject_imports(content):
    imports = [
        "import android.content.Context",
    ]
    pkg_match = re.search(r"^package\\s+.*$", content, re.MULTILINE)
    if pkg_match:
        end_idx = pkg_match.end()
        to_add = [imp for imp in imports if imp not in content]
        if to_add:
            content = content[:end_idx] + "\\n" + "\\n".join(to_add) + "\\n" + content[end_idx:]
    return content

def inject_plugin_code(content, plugin_class):
    if "object LicenseManager" not in content:
        content += "\\n" + get_license_manager_code()

    # Robust Plugin class detection (handles spaces, open, abstract)
    match = re.search(r"(?:open\\s+|abstract\\s+)?class\\s+" + re.escape(plugin_class) + r"\\s*:\\s*Plugin\\(\\)", content)
    
    if match:
        brace_idx = content.find("{", match.end())
        if brace_idx != -1:
            # Check for load method
            if "override fun load(" in content:
                if "premiumContext" not in content:
                    # BLOCK 1: Try replacing super.load(context)
                    if "super.load(context)" in content:
                        content = content.replace(
                            "super.load(context)",
                            "super.load(context)\\n        premiumContext = context"
                        )
                    else:
                        # BLOCK 2: No super.load call — force insertion
                        # Find 'override fun load' start
                        load_match = re.search(r"override\\s+fun\\s+load\\s*\\(", content)
                        if load_match:
                            load_brace = content.find("{", load_match.start())
                            if load_brace != -1:
                                content = content[:load_brace+1] + "\\n        premiumContext = context" + content[load_brace+1:]
            else:
                # No load method at all - inject one
                injection = """
    override fun load(context: Context) {
        super.load(context)
        premiumContext = context
    }
"""
                content = content[:brace_idx+1] + injection + content[brace_idx+1:]
    return content

def inject_provider_checks(content):
    methods = ["getMainPage", "search", "load", "loadLinks"]
    for m in methods:
        pattern = r"suspend\\s+fun\\s+" + m + r"\\b"
        matches = list(re.finditer(pattern, content))
        for match in reversed(matches):
            brace_idx = content.find("{", match.start())
            if brace_idx != -1:
                if "LicenseManager.check" in content[brace_idx:brace_idx+200]:
                    continue
                injection = '\\n        LicenseManager.check(name)\\n'
                content = content[:brace_idx+1] + injection + content[brace_idx+1:]
    return content

# =========================================================
# MAIN
# =========================================================
# KEY CHANGE: Group by (Package Name, Module Root) to prevent collisions
package_map = {}

print("Scanning for Kotlin files...")
for root, dirs, files in os.walk("."):
    for file in files:
        if file.endswith(".kt"):
            path = os.path.join(root, file)
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    content = f.read()
            except:
                continue

            pkg_m = re.search(r"^package\\s+([\\w\\.]+)", content, re.MULTILINE)
            if not pkg_m:
                continue
            pkg = pkg_m.group(1)

            # Determine Module Root (heuristic: assume 'src' is the boundary)
            parts = os.path.normpath(path).split(os.sep)
            module_root = root # default
            if "src" in parts:
                idx = parts.index("src")
                module_root = os.sep.join(parts[:idx])
            
            # Unique Key for this plugin module
            key = (pkg, module_root)

            if key not in package_map:
                package_map[key] = {'plugin': None, 'providers': []}

            # Identify Plugin Class
            if " : Plugin()" in content or ":Plugin()" in content or ": Plugin()" in content:
                cm = re.search(r"(?:open\\s+)?class\\s+(\\w+)\\s*:\\s*Plugin\\(\\)", content)
                if cm:
                    package_map[key]['plugin'] = (path, cm.group(1))

            # Identify Provider Class
            if ": MainAPI()" in content:
                package_map[key]['providers'].append(path)

print("Found {} unique metadata groups".format(len(package_map)))

for key, data in package_map.items():
    pkg, mod_root = key
    plugin_info = data['plugin']
    providers = data['providers']

    if plugin_info:
        plugin_path, plugin_class = plugin_info
        print(f"Injecting into Plugin: {plugin_path} (Class: {plugin_class})")
        with open(plugin_path, 'r', encoding='utf-8') as f:
            c = f.read()
        c = inject_imports(c)
        c = inject_plugin_code(c, plugin_class)
        with open(plugin_path, 'w', encoding='utf-8') as f:
            f.write(c)

        for provider_path in providers:
            print(f"  Protecting Provider: {provider_path}")
            with open(provider_path, 'r', encoding='utf-8') as f:
                c = f.read()
            c = inject_provider_checks(c)
            with open(provider_path, 'w', encoding='utf-8') as f:
                f.write(c)
    else:
        if len(providers) > 0:
            print(f"WARNING: No Plugin class found for {pkg} in {mod_root}. {len(providers)} providers skipped.")

print("ALL DONE")
