package com.premiumstream

import com.lagradost.cloudstream3.*
import com.lagradost.cloudstream3.utils.*
import org.jsoup.nodes.Element

/**
 * PremiumStream — Extension CloudStream SIAP PAKAI dengan license key system.
 * 
 * Extension ini scrape dari OtakuDesu sebagai contoh.
 * User HARUS input license key yang valid untuk bisa mengakses konten.
 * 
 * ⚠️ Untuk ganti website target, edit mainUrl dan logic scraping di bawah.
 */
class PremiumStream : MainAPI() {
    override var mainUrl = "https://otakudesu.cloud"
    override var name = "PremiumStream ⭐"
    override val hasMainPage = true
    override var lang = "id"
    override val supportedTypes = setOf(TvType.Anime, TvType.AnimeMovie)

    companion object {
        private const val PREFS_NAME = "premium_stream_prefs"
        private const val KEY_LICENSE = "license_key"
    }

    override val mainPage = mainPageOf(
        "" to "Ongoing Anime",
    )

    // ============================================================
    // LICENSE KEY MANAGEMENT
    // ============================================================

    /**
     * Ambil license key yang tersimpan di SharedPreferences
     */
    private fun getLicenseKey(): String {
        val ctx = PremiumStreamPlugin.context ?: return ""
        val prefs = ctx.getSharedPreferences(PREFS_NAME, 0)
        return prefs.getString(KEY_LICENSE, "") ?: ""
    }

    /**
     * Simpan license key ke SharedPreferences
     */
    private fun saveLicenseKey(key: String) {
        val ctx = PremiumStreamPlugin.context ?: return
        ctx.getSharedPreferences(PREFS_NAME, 0).edit().putString(KEY_LICENSE, key).apply()
    }

    /**
     * Cek license — throw error jika tidak valid
     */
    private suspend fun checkLicense() {
        val key = getLicenseKey()
        val result = LicenseManager.validate(key)

        if (!result.isActive) {
            val msg = buildString {
                append("🔒 PREMIUM EXTENSION\n\n")
                append("${result.message}\n\n")
                if (key.isBlank()) {
                    append("📝 Cara input key:\n")
                    append("1. Buka link berikut di browser:\n")
                    append("   cloudstreamapp://input-key\n")
                    append("2. Atau masukkan key via search\n")
                    append("   Ketik: key:CS-XXXX-XXXX-XXXX-XXXX\n\n")
                }
                append("❓ Hubungi admin untuk key premium")
            }
            throw ErrorLoadingException(msg)
        }
    }

    // ============================================================
    // SEARCH — juga digunakan untuk INPUT KEY!
    // User ketik "key:CS-XXXX-XXXX-XXXX-XXXX" di search untuk set key
    // ============================================================

    override suspend fun search(query: String): List<SearchResponse> {
        // ⭐ FITUR: Input key via search bar!
        // User ketik: key:CS-1234-5678-ABCD-EFGH
        if (query.lowercase().startsWith("key:")) {
            val newKey = query.substringAfter("key:").trim()
            if (newKey.isNotEmpty()) {
                saveLicenseKey(newKey)
                LicenseManager.clearCache()
                
                // Validasi langsung
                val result = LicenseManager.validate(newKey)
                if (result.isActive) {
                    throw ErrorLoadingException(
                        "✅ KEY BERHASIL DISIMPAN!\n\n" +
                        "Key: $newKey\n" +
                        "Status: ACTIVE ✅\n" +
                        "Sisa: ${result.daysLeft} hari\n" +
                        "Device: ${result.currentDevices}/${result.maxDevices}\n\n" +
                        "Sekarang kembali ke halaman utama extension."
                    )
                } else {
                    throw ErrorLoadingException(
                        "❌ KEY TIDAK VALID\n\n" +
                        "Key: $newKey\n" +
                        "Error: ${result.message}\n\n" +
                        "Periksa key kamu atau hubungi admin."
                    )
                }
            }
        }

        // Normal search — validasi dulu
        checkLicense()

        val document = app.get("$mainUrl/?s=$query&post_type=anime").document
        return document.select("ul.childs li").mapNotNull {
            val a = it.selectFirst("a") ?: return@mapNotNull null
            val title = a.selectFirst("h2")?.text() ?: return@mapNotNull null
            val href = a.attr("href")
            val poster = it.selectFirst("img")?.attr("src")
            newAnimeSearchResponse(title, href, TvType.Anime) {
                this.posterUrl = poster
            }
        }
    }

    // ============================================================
    // MAIN PAGE
    // ============================================================

    override suspend fun getMainPage(page: Int, request: MainPageRequest): HomePageResponse {
        checkLicense()

        val document = app.get(mainUrl).document
        val items = document.select("div.detpost").mapNotNull {
            val a = it.selectFirst("div.thumb a") ?: return@mapNotNull null
            val title = it.selectFirst("div.jdlflm")?.text() ?: return@mapNotNull null
            val href = a.attr("href")
            val poster = it.selectFirst("img")?.attr("src")
            newAnimeSearchResponse(title, href, TvType.Anime) {
                this.posterUrl = poster
            }
        }

        return newHomePageResponse(
            HomePageList(request.name, items),
            hasNext = false
        )
    }

    // ============================================================
    // LOAD DETAIL
    // ============================================================

    override suspend fun load(url: String): LoadResponse {
        checkLicense()

        val document = app.get(url).document

        val title = document.selectFirst("div.infozingle span:contains(Judul)")
            ?.text()?.substringAfter(":")?.trim()
            ?: document.selectFirst("h1.jdlrx")?.text()
            ?: ""

        val poster = document.selectFirst("div.fotoanime img")?.attr("src")
        val description = document.selectFirst("div.sinopc")?.text()

        val genre = document.select("div.infozingle span:contains(Genre) a").map { it.text() }

        val episodes = document.select("div.episodelist ul li").mapNotNull { ep ->
            val a = ep.selectFirst("a") ?: return@mapNotNull null
            val epTitle = a.text()
            val epUrl = a.attr("href")
            newEpisode(epUrl) {
                this.name = epTitle
            }
        }.reversed()

        return newAnimeLoadResponse(title, url, TvType.Anime) {
            this.posterUrl = poster
            this.plot = description
            this.tags = genre
            addEpisodes(DubStatus.Subbed, episodes)
        }
    }

    // ============================================================
    // LOAD LINKS
    // ============================================================

    override suspend fun loadLinks(
        data: String,
        isCasting: Boolean,
        subtitleCallback: (SubtitleFile) -> Unit,
        callback: (ExtractorLink) -> Unit
    ): Boolean {
        checkLicense()

        val document = app.get(data).document

        // Ambil semua mirror/quality
        document.select("div.mirrorstream ul li a").forEach { mirror ->
            val nonce = mirror.attr("data-nonce")
            val action = mirror.attr("data-action") ?: "2a3505c93b0035d3f455b6b9571f7e77"

            try {
                val response = app.post(
                    "$mainUrl/wp-admin/admin-ajax.php",
                    data = mapOf(
                        "nonce" to nonce,
                        "action" to action
                    ),
                    referer = data
                )

                val iframeUrl = Regex("src=\"([^\"]+)\"").find(response.text)?.groupValues?.get(1)
                if (iframeUrl != null) {
                    loadExtractor(iframeUrl, "$mainUrl/", subtitleCallback, callback)
                }
            } catch (_: Exception) {}
        }

        return true
    }
}
