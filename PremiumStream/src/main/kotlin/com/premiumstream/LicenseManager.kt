package com.premiumstream

import android.provider.Settings
import android.util.Log
import com.lagradost.cloudstream3.app
import com.fasterxml.jackson.annotation.JsonProperty
import com.fasterxml.jackson.module.kotlin.readValue
import com.lagradost.cloudstream3.mapper

/**
 * LicenseManager — Handles license validation with backend server
 * 
 * ⚠️ GANTI API_URL dengan URL server kamu setelah deploy!
 */
object LicenseManager {
    private const val TAG = "LicenseManager"

    // ================================================================
    // ⚠️⚠️⚠️ API URL (Jangan lupa ganti ini jika IP berubah!)
    private const val API_URL = "http://172.83.15.6:3000"
    
    // Cache 5 menit
    private const val CACHE_MS = 5 * 60 * 1000L
    private var cached: LicenseResponse? = null
    private var cacheTime: Long = 0
    private var cacheKey: String = ""

    data class LicenseResponse(
        @JsonProperty("status") val status: String,
        @JsonProperty("message") val message: String,
        @JsonProperty("expired_at") val expiredAt: String? = null,
        @JsonProperty("days_left") val daysLeft: Int? = null,
        @JsonProperty("max_devices") val maxDevices: Int? = null,
        @JsonProperty("current_devices") val currentDevices: Int? = null
    ) {
        val isActive: Boolean get() = status == "active"
    }

    suspend fun validate(licenseKey: String): LicenseResponse {
        if (licenseKey.isBlank()) {
            return LicenseResponse(
                status = "error",
                message = "Masukkan License Key di Settings extension ini"
            )
        }

        // Cek cache
        if (licenseKey == cacheKey && cached != null) {
            if (System.currentTimeMillis() - cacheTime < CACHE_MS) {
                return cached!!
            }
        }

        return try {
            val deviceId = getDeviceId()
            val deviceName = getDeviceName()

            val response = app.post(
                "$API_URL/api/validate",
                json = mapOf(
                    "key" to licenseKey,
                    "device_id" to deviceId,
                    "device_name" to deviceName
                ),
                timeout = 15
            )

            val result = mapper.readValue<LicenseResponse>(response.text)

            // Cache
            cacheKey = licenseKey
            cached = result
            cacheTime = System.currentTimeMillis()

            result
        } catch (e: Exception) {
            Log.e(TAG, "Validation error: ${e.message}")
            if (cached?.isActive == true && licenseKey == cacheKey) {
                return cached!!
            }
            LicenseResponse(
                status = "error",
                message = "Gagal terhubung ke server. Pastikan server berjalan."
            )
        }
    }

    private fun getDeviceId(): String {
        val ctx = PremiumStreamPlugin.context ?: return "unknown"
        return try {
            Settings.Secure.getString(ctx.contentResolver, Settings.Secure.ANDROID_ID) ?: "unknown"
        } catch (e: Exception) { "unknown" }
    }

    private fun getDeviceName(): String {
        return try {
            "${android.os.Build.MANUFACTURER} ${android.os.Build.MODEL}"
        } catch (e: Exception) { "Unknown Device" }
    }

    fun clearCache() {
        cached = null
        cacheTime = 0
        cacheKey = ""
    }
}
