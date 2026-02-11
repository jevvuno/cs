import os
import re

# =========================================================
# CONFIG
# =========================================================
API_URL = "http://172.83.15.6:3000"  # IP VPS Anda

# License Manager Code (Kotlin)
LICENSE_MANAGER_CODE = f"""
// ==================================================================
// 🔒 PREMIUM LICENSE MANAGER (INJECTED)
// ==================================================================
object LicenseManager {{
    private const val API_URL = "{API_URL}"
    private const val PREFS_NAME = "premium_prefs"
    private const val KEY_LICENSE = "license_key"
    
    // Simple Cache
    private var cachedStatus: String? = null
    private var cacheTime: Long = 0
    private const val CACHE_MS = 5 * 60 * 1000L // 5 menit

    data class LicenseResponse(
        @com.fasterxml.jackson.annotation.JsonProperty("status") val status: String,
        @com.fasterxml.jackson.annotation.JsonProperty("message") val message: String
    )

    fun getSavedKey(): String {{
        val ctx = com.lagradost.cloudstream3.extractors.PremiumStreamPlugin.context ?: return ""
        val prefs = ctx.getSharedPreferences(PREFS_NAME, 0)
        return prefs.getString(KEY_LICENSE, "") ?: ""
    }}

    fun saveKey(key: String) {{
        val ctx = com.lagradost.cloudstream3.extractors.PremiumStreamPlugin.context ?: return
        ctx.getSharedPreferences(PREFS_NAME, 0).edit().putString(KEY_LICENSE, key).apply()
        cachedStatus = null
    }}

    suspend fun check(apiName: String) {{
        val key = getSavedKey()
        
        // Cek Cache
        if (cachedStatus == "active" && System.currentTimeMillis() - cacheTime < CACHE_MS) return

        if (key.isBlank()) {{
            throw ErrorLoadingException("🔒 PREMIUM: Masukkan License Key di Settings (atau cari 'key:CS-XXXX')")
        }}

        try {{
            val deviceId = android.provider.Settings.Secure.getString(
                com.lagradost.cloudstream3.extractors.PremiumStreamPlugin.context!!.contentResolver,
                android.provider.Settings.Secure.ANDROID_ID
            ) ?: "unknown"

            val response = app.post(
                "$API_URL/api/validate",
                json = mapOf("key" to key, "device_id" to deviceId),
                timeout = 10
            )

            val json = com.lagradost.cloudstream3.mapper.readValue<LicenseResponse>(response.text)
            
            if (json.status != "active") {{
                throw ErrorLoadingException("🔒 BLOCKED: ${{json.message}}")
            }}

            // Valid
            cachedStatus = "active"
            cacheTime = System.currentTimeMillis()

        }} catch (e: Exception) {{
            if (e is ErrorLoadingException) throw e
            // If network error but cached valid, allow (offline mode somewhat)
            if (cachedStatus == "active") return
            throw ErrorLoadingException("🔒 Gagal terhubung ke server lisensi")
        }}
    }}
}}
"""

def inject_license_check(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Hanya inject ke class yang extends MainAPI
    if ": MainAPI()" not in content:
        return

    print(f"💉 Injecting license check to: {file_path}")

    # 1. Inject Imports
    imports = [
        "import android.provider.Settings",
        "import com.lagradost.cloudstream3.app",
        "import com.lagradost.cloudstream3.ErrorLoadingException",
        "import com.lagradost.cloudstream3.mapper"
    ]
    
    pkg_match = re.search(r"^package .*$", content, re.MULTILINE)
    if pkg_match:
        end_idx = pkg_match.end()
        import_block = "\n" + "\n".join(imports) + "\n"
        if "import com.lagradost.cloudstream3.ErrorLoadingException" not in content:
             content = content[:end_idx] + import_block + content[end_idx:]

    # 2. Inject LicenseManager Code (Append to end)
    if "object LicenseManager" not in content:
        content += "\n" + LICENSE_MANAGER_CODE

    # 3. Inject check() calls
    # Methods to patch (suspend functions)
    methods = ["getMainPage", "search", "load", "loadLinks"]
    
    for m in methods:
        # Find function start: check for 'suspend fun name'
        # We look for the opening brace {
        matches = re.finditer(f"suspend\s+fun\s+{m}", content)
        
        # This regex is tricky because of arguments. 
        # Easier approach: find the method signature, then find the first {
        
        for match in matches:
            start_idx = match.start()
            # Find the opening brace after this
            brace_idx = content.find("{", start_idx)
            if brace_idx != -1:
                # Check if already injected
                if "LicenseManager.check" in content[brace_idx:brace_idx+200]:
                    continue
                
                # Inject just after {
                injection = '\n        LicenseManager.check(name)\n'
                content = content[:brace_idx+1] + injection + content[brace_idx+1:]

    # 4. Inject Search Key Input
    # Special case for search method to allow setting key
    search_match = re.search(r"suspend\s+fun\s+search.*{", content)
    if search_match:
        s_end = search_match.end()
        if "key:" not in content[s_end:s_end+500]:
            search_logic = """
        if (query.startsWith("key:")) {
            val k = query.substringAfter("key:").trim()
            LicenseManager.saveKey(k)
            throw ErrorLoadingException("✅ Key tersimpan: $k")
        }
            """
            content = content[:s_end] + search_logic + content[s_end:]

    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)

# Run
for root, dirs, files in os.walk("."):
    for file in files:
        if file.endswith(".kt"):
            inject_license_check(os.path.join(root, file))

print("✅ Injection complete!")
