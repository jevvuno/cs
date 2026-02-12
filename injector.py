import os
import re

# =========================================================
# CONFIG
# =========================================================
API_URL = "http://172.83.15.6:3000"

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
            val ctx = premiumContext
            val androidId = if (ctx != null) {{
                android.provider.Settings.Secure.getString(ctx.contentResolver, android.provider.Settings.Secure.ANDROID_ID)
            }} else "unknown"

            val url = java.net.URL("$API_URL/check?api=$apiName&device=$androidId")
            val connection = url.openConnection() as java.net.HttpURLConnection
            connection.requestMethod = "GET"
            connection.connectTimeout = 5000
            connection.readTimeout = 5000

            if (connection.responseCode == 200) {{
                val responseText = connection.inputStream.bufferedReader().readText()
                val mapper = com.fasterxml.jackson.databind.ObjectMapper()
                val resp = mapper.readValue(responseText, LicenseResponse::class.java)
                
                if (resp.status == "active") {{
                    cachedStatus = "active"
                    cacheTime = System.currentTimeMillis()
                }} else {{
                    throw Exception("License inactive: {resp.message}")
                }}
            }}
        }} catch (e: Exception) {{
            # Fail-open for now
        }}
    }}
}}
"""

def bump_version(content):
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
        dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ['build', 'gradle']]
        for file in files:
            if file.endswith(".kt"):
                path = os.path.join(root, file)
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        content = f.read()
                    
                    if re.search(r"class\s+\w+Plugin\s*:\s*Plugin", content):
                        plugin_count += 1
                        print(f"Found plugin: {file}")
                        
                        modified = False
                        old_content = content
                        content = bump_version(content)
                        if content != old_content:
                            modified = True
                        
                        if "object LicenseManager" not in content:
                            package_match = re.search(r"^package\s+.*", content, re.MULTILINE)
                            if package_match:
                                end = package_match.end()
                                content = content[:end] + "\n\n" + license_code + content[end:]
                                modified = True
                        
                        suspend_funs = re.findall(r"suspend\s+fun\s+(\w+)", content)
                        for m in suspend_funs:
                            if m not in ["check"]:
                                func_pattern = r"(suspend\s+fun\s+" + m + r"(\s*\([^\}]*\)\s*\{))"
                                if f"LicenseManager.check('{m}')" not in content:
                                    content = re.sub(func_pattern, r'\1\n        LicenseManager.check(\'' + m + '\'')', content)
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
