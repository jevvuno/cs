package com.premiumstream

import android.content.Context
import com.lagradost.cloudstream3.plugins.CloudstreamPlugin
import com.lagradost.cloudstream3.plugins.Plugin

@CloudstreamPlugin
class PremiumStreamPlugin : Plugin() {
    companion object {
        var context: Context? = null
    }

    override fun load(context: Context) {
        PremiumStreamPlugin.context = context
        registerMainAPI(PremiumStream())
    }
}
