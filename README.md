# PremiumStream — CloudStream Extension dengan License Key

Extension CloudStream yang dilindungi license key. User harus input key untuk mengakses konten.

## 📁 Struktur Project

```
cs-premium-ext/            ← PUSH REPO INI KE GITHUB
├── .github/workflows/     ← Auto build saat push
├── PremiumStream/          ← Extension premium
│   └── src/main/kotlin/com/premiumstream/
│       ├── PremiumStreamPlugin.kt
│       ├── PremiumStream.kt         ← Provider + scraping
│       └── LicenseManager.kt        ← Validasi ke server
├── build.gradle.kts
├── settings.gradle.kts
├── repo.json
└── gradlew / gradlew.bat

backend/                    ← SERVER API (deploy terpisah ke VPS)
├── server.js
├── database.js
├── package.json
└── public/index.html       ← Admin dashboard
```

---

## 🚀 LANGKAH PASANG (Step-by-Step)

### Step 1: Deploy Backend ke VPS

```bash
# Upload folder backend/ ke VPS kamu
# Di VPS:
cd backend
npm install
npm install -g pm2
pm2 start server.js --name cs-premium
```

Buka `http://IP_VPS:3000` → Login: **admin** / **admin123** → **Ganti password!**

### Step 2: Edit API_URL di Extension

Buka file `PremiumStream/src/main/kotlin/com/premiumstream/LicenseManager.kt`

Ganti baris ini:
```kotlin
private const val API_URL = "http://10.0.2.2:3000"
```
Menjadi:
```kotlin
private const val API_URL = "http://IP_VPS_KAMU:3000"
```

### Step 3: Edit repo.json

Ganti `GANTI_USERNAME/GANTI_REPO` dengan username/repo GitHub kamu:
```json
"pluginLists": [
  "https://raw.githubusercontent.com/USERNAME/REPO/builds/plugins.json"
]
```

### Step 4: Edit build.gradle.kts (root)

Ganti `GANTI_USERNAME/GANTI_REPO` di baris `setRepo(...)`:
```kotlin
setRepo(System.getenv("GITHUB_REPOSITORY") ?: "USERNAME/REPO")
```

### Step 5: Push ke GitHub

```bash
git init
git add .
git commit -m "Initial commit"
git remote add origin https://github.com/USERNAME/REPO.git
git push -u origin main
```

**PENTING:** Buat branch `builds` dulu sebelum push:
```bash
git checkout --orphan builds
git rm -rf .
git commit --allow-empty -m "Initial builds"
git push origin builds
git checkout main
```

### Step 6: GitHub Actions Build

Setelah push ke `main`, GitHub Actions otomatis build dan hasilnya ada di branch `builds`.

### Step 7: Pasang di CloudStream

1. Buka CloudStream → Settings → Extensions → Add Repository
2. Paste URL: `https://raw.githubusercontent.com/USERNAME/REPO/main/repo.json`
3. Install **PremiumStream ⭐**

### Step 8: Generate Key & Input di Extension

1. Buka admin dashboard `http://IP_VPS:3000`
2. Generate key baru
3. Di CloudStream, buka **PremiumStream ⭐**
4. Akan muncul pesan "Masukkan License Key"
5. Pergi ke **Search** → ketik: `key:CS-XXXX-XXXX-XXXX-XXXX`
6. Akan muncul konfirmasi ✅ Key berhasil disimpan!
7. Kembali ke halaman utama → konten muncul!

---

## 💡 Cara User Input Key

User cukup **search** dengan format:
```
key:CS-1234-5678-ABCD-EFGH
```

Extension otomatis simpan key dan validasi. Simple!
