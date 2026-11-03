# Audit Keamanan & Privasi: Aura

**Tanggal:** 3 November 2026
**Cakupan:** seluruh *working tree* di `main` (`b65ab52`) **dan seluruh riwayat git**
(12 commit, 1 branch). Semua blob di riwayat dipindai.
**Tujuan:** memastikan repo aman dijadikan portofolio publik.
**Branch perbaikan:** `security-audit-portfolio` (tidak ada perubahan di `main`).

> Dokumen ini sengaja **tidak** mencantumkan nilai rahasia atau data lokasi secara
> utuh supaya tidak ikut tersebar lagi.

---

## Ringkasan

| # | Temuan | Tingkat | Status |
|---|---|---|---|
| 1 | API key SiliconFlow asli ter-commit di riwayat git | 🔴 **Kritis** | ⚠️ **Perlu tindakan pemilik** (rotasi kunci + tulis ulang riwayat) |
| 2 | Foto pribadi dengan metadata GPS ter-commit di riwayat git | 🟠 Tinggi | ⚠️ Perlu tindakan pemilik (tulis ulang riwayat) |
| 3 | Gambar berhak cipta pihak ketiga di riwayat git | 🟡 Sedang | ⚠️ Ikut terhapus saat riwayat ditulis ulang |
| 4 | Aplikasi utama tanpa autentikasi; *gate* depan hanya kosmetik | 🟠 Tinggi (bila deploy publik) | 📝 Didokumentasikan, tidak diubah |
| 5 | Rate limit bisa di-bypass dengan memalsukan `X-Forwarded-For` | 🟡 Sedang | ✅ Diperbaiki |
| 6 | Tag sesi `/kelola` = hash polos password (terbaca di cookie) | 🟡 Sedang | ✅ Diperbaiki |
| 7 | `gunicorn==21.2.0` punya CVE *request smuggling* | 🟡 Sedang | ✅ Diperbaiki |
| 8 | Tidak ada header keamanan (clickjacking, MIME sniffing) | 🟢 Rendah | ✅ Diperbaiki |
| 9 | Pillow tanpa batas piksel ketat (*decompression bomb*) | 🟢 Rendah | ✅ Diperbaiki |
| 10 | Logout `/kelola` tanpa header anti-CSRF | 🟢 Rendah | ✅ Diperbaiki |
| 11 | Pola `onclick="fn('${esc(x)}')"` di frontend | ℹ️ Info | 📝 Tidak bisa dieksploitasi saat ini |
| 12 | Email pribadi di metadata commit | ℹ️ Info | 📝 Rekomendasi |
| 13 | Dokumentasi menyesatkan (README/.env.example) | ℹ️ Info | ✅ Diperbaiki |

Hasil yang **bersih**:

- **SQL injection:** tidak ditemukan. Semua query memakai placeholder `?`. Interpolasi
  f-string hanya untuk nama kolom/tabel dari konstanta atau whitelist (`media.KINDS`,
  `POST_COLS`, `_joined("likes"|"bookmarks")`). Input `LIKE` di-escape (`ESCAPE '\'`).
- **XSS:** tidak ditemukan. Tidak ada `|safe`, `Markup`, atau `render_template_string`;
  Jinja autoescape aktif. Di frontend, semua teks dari pengguna/AI (konten, komentar,
  nama tampilan, caption, bio) melewati `esc()` sebelum `innerHTML`. Teks berstatus
  dimasukkan lewat `textContent`.
- **CSRF:** cukup termitigasi. Endpoint tulis membaca body lewat `get_json()`, yang
  menolak `Content-Type` selain JSON, sehingga form lintas situs tidak bisa mengirim
  data. Cookie `/kelola` bersifat `SameSite=Strict`, dan semua POST dashboard wajib
  header `X-Kelola: 1` (memicu *preflight* CORS lintas situs). `DELETE` tidak bisa
  dikirim lewat form.
- **SECRET_KEY hardcoded:** tidak ada. `SECRET_KEY` dibaca dari env. Bila kosong,
  dibuat dengan `secrets.token_hex(32)` lalu disimpan di DB. Debug mode default **mati**
  (`FLASK_DEBUG=0`).
- **File rahasia di tree saat ini:** tidak ada `.env`, `*.db`, kunci privat, atau token.
  Kunci di `tests/` adalah dummy (`sk-test-dummy-key-…`).
- **Data pribadi di kode saat ini:** tidak ada. Persona AI di `personas.py` fiktif.

---

## Detail temuan

### 1. 🔴 API key SiliconFlow asli di riwayat git

- **Lokasi:** commit `f87cf4c` dan `b98fb49`, folder `Newbackup/FinalBckup/arsip/` dan
  `Newbackup/FinalBckup/aura/`. Kunci yang sama muncul di 12 file:
  `arsip/API.txt`, `arsip/app copy*.py` (5 file), `arsip/config.py`, `aura/config.py`, dll.
- **Nilai:** `sk-yaluv…` (51 karakter; disensor di sini).
- **Dihapus dari tree** di `2c19cab`, tetapi **tetap bisa diambil** dari riwayat:
  `git show b98fb49:Newbackup/FinalBckup/arsip/API.txt`.
- **Dampak:** repo `dwiahmaddzul/Aura` **sudah publik**. Kunci harus dianggap
  **sudah bocor**. Siapa pun bisa memakainya untuk memanggil model atas biaya pemilik akun.
  Bot pemindai GitHub biasanya menemukan kunci semacam ini dalam hitungan menit.

**Tindakan (urutan penting):**

1. **Cabut (revoke) kunci itu sekarang** di dashboard SiliconFlow → API Keys, buat
   kunci baru, dan simpan hanya di `.env` / env var Railway. Periksa riwayat pemakaian
   dan tagihan akun untuk aktivitas yang tidak dikenali.
2. Tulis ulang riwayat (lihat [Pembersihan riwayat git](#pembersihan-riwayat-git)).
   Langkah ini **tidak menggantikan** rotasi kunci: salinan lama bisa saja sudah ada di
   *fork*, *clone*, atau cache.

### 2. 🟠 Foto pribadi dengan GPS di riwayat git

- **Lokasi:** `Newbackup/FinalBckup/arsip/2021-06-20-07-45-50.jpg`
  (commit `f87cf4c`, `b98fb49`).
- **Isi metadata EXIF:** kamera iPhone X, tanggal pemotretan, dan **koordinat GPS
  presisi** (lintang/bujur, ketinggian, arah kamera; galat sekitar 6 m).
  Koordinat sengaja tidak ditulis di sini.
- **Dampak:** lokasi dan waktu keberadaan pemilik bisa dibaca siapa pun dengan `exiftool`.
- **Tindakan:** hapus dari riwayat (langkah yang sama dengan temuan 1).

> Catatan untuk app: unggahan pengguna disimpan apa adanya di `MEDIA_DIR/<kind>/<id>.orig`
> (termasuk EXIF). File `.orig` **tidak** disajikan lewat HTTP, dan varian WebP yang
> disajikan dibuat ulang lewat Pillow tanpa EXIF. Jadi tidak ada kebocoran lewat web.
> Namun, jangan pernah meng-commit folder `media/` (sudah ada di `.gitignore`).

### 3. 🟡 Gambar berhak cipta pihak ketiga

- `arsip/Resident_Evil_Requiem_-_Leon_S._Kennedy.jpg`,
  `arsip/pegatinas-coches-motos-emblema-assassins-creed.jpg`, foto berita
  `arsip/046166700_…gunungagung1.jpg`, `arsip/00XQ83…webp`.
- **Dampak:** kurang pantas untuk portofolio publik dan berisiko klaim DMCA. Ikut terhapus
  saat riwayat folder `Newbackup/` dibersihkan.

### 4. 🟠 Aplikasi utama tanpa autentikasi

- Semua endpoint `/api/*` (feed, DM, profil, mood, jurnal, buat post/komentar/story)
  bisa diakses tanpa login. "Kode rahasia" di `templates/index.html`
  (`rahasiakusaja`, ditampilkan di halaman) hanya disimpan di `localStorage`. Gate ini
  murni kosmetik dan bisa dilewati dengan `curl`.
- Yang sudah dilindungi: hapus post dan seluruh `/kelola` butuh sesi admin. Biaya AI
  dibatasi rem harian di `settings_rt.py` / `ai_engine/limits.py`.
- **Dampak:** pada deployment publik, isi jurnal dan DM pemilik bisa dibaca orang lain.
  Pihak luar juga bisa memicu panggilan AI berbayar sampai batas rem harian.
- **Mengapa tidak diubah:** menambahkan login ke app utama mengubah perilaku produk dan
  demo publik. Ini keputusan desain pemilik.
- **Rekomendasi:** untuk demo publik, gunakan database berisi data dummy saja. Untuk
  pemakaian pribadi, jalankan di `localhost` atau pasang Cloudflare Access / basic auth di
  reverse proxy. Bisa juga menambah env `APP_PASSWORD` yang memakai mekanisme sesi
  seperti `/kelola` untuk seluruh `/api/*`. Model ancaman ini kini dijelaskan di README.

### 5. ✅ Bypass rate limit via `X-Forwarded-For`

- **Sebelum:** `security._client_ip()` mengambil entri **paling kiri** dari
  `X-Forwarded-For`, yang sepenuhnya dikendalikan klien. Penyerang cukup mengirim header
  acak per request untuk menghindari limit 12 post/menit, 20 DM/menit, dan 6 login/5 menit.
  Akibatnya brute force password `/kelola` dan spam yang memicu biaya AI jadi mungkin.
- **Perbaikan:** env baru `TRUSTED_PROXY_HOPS` (default `1`). IP diambil dari entri ke-N
  **dari kanan**, yaitu alamat yang ditambahkan proxy tepercaya. Nilai `0` = abaikan
  header (akses langsung). Tanpa header, perilakunya tetap `remote_addr`.
- **Catatan deploy:** Railway saja → `1`. Cloudflare + Railway → `2`.

### 6. ✅ Tag sesi `/kelola` bisa di-brute-force offline

- **Sebelum:** `session["kelola"] = sha256("aura-kelola:" + ADMIN_PASSWORD)[:20]`.
  Cookie sesi Flask hanya **ditandatangani**, tidak dienkripsi, sehingga isinya terbaca
  oleh siapa pun yang memegang cookie (mis. dari perangkat bersama atau log). Dari hash
  itu, password lemah bisa ditebak offline tanpa terkena rate limit.
- **Perbaikan:** tag kini `HMAC-SHA256(secret_key, …)`. Tag tidak berguna tanpa
  `SECRET_KEY` server. Efek samping: sesi `/kelola` yang sedang aktif akan logout sekali.

### 7. ✅ Gunicorn rentan

- `gunicorn==21.2.0` terdampak CVE-2024-1135 dan CVE-2024-6827 (HTTP request
  smuggling, perbaikan di 22.0 / 23.0). Diubah ke `gunicorn>=23.0.0`. Opsi di `Procfile`
  tetap kompatibel.

### 8. ✅ Header keamanan

- Ditambahkan di `app.py`: `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`,
  `Referrer-Policy: strict-origin-when-cross-origin`, dan CSP minimal
  `frame-ancestors 'none'; object-src 'none'; base-uri 'self'`.
- CSP `script-src` penuh **belum** dipasang karena frontend memakai banyak handler
  `onclick` inline. Memindahkannya ke `addEventListener` adalah langkah lanjutan yang baik.

### 9. ✅ Decompression bomb

- `Image.MAX_IMAGE_PIXELS = 50_000_000` di `media.py`. PNG < 2 MB yang mengembang
  menjadi ratusan juta piksel kini ditolak, alih-alih dimuat ke RAM saat membuat thumbnail.

### 10. ✅ Logout tanpa header anti-CSRF

- `/api/kelola/logout` kini juga mewajibkan `X-Kelola: 1`, konsisten dengan endpoint
  lain. Frontend (`kelola.js`) sudah mengirim header itu, dan tes yang ada juga.

### 11. ℹ️ `onclick="fn('${esc(x)}')"`

- `esc()` mengubah `'` menjadi `&#39;`, yang **di-decode kembali** oleh parser HTML
  sebelum JavaScript atribut dieksekusi. Pola ini tidak aman untuk string bebas.
  Saat ini aman karena nilainya selalu `username` dari whitelist server (`me` atau id
  persona). Jangan pakai pola ini untuk data dari pengguna. Gunakan `data-*` +
  `addEventListener`.

### 12. ℹ️ Email pribadi di metadata commit

- 11 commit memakai email Gmail pribadi sebagai author. Ini lazim, tetapi bila ingin
  disembunyikan, aktifkan *Keep my email address private* di GitHub dan pakai
  `ID+username@users.noreply.github.com` untuk commit berikutnya. Mengubah commit lama
  bisa dilakukan sekaligus saat menulis ulang riwayat (`--mailmap`).

### 13. ✅ Dokumentasi

- README lama menyatakan "API key … never committed" (tidak benar untuk riwayat) dan
  "No auth … don't expose publicly", padahal app dideploy publik. README ditulis ulang
  dengan model ancaman yang jujur. `.env.example` dilengkapi (`SECRET_KEY`,
  `COOKIE_SECURE`, `TRUSTED_PROXY_HOPS`, `FLASK_DEBUG`, model) dan BOM UTF-8 di awal file
  dihapus. `.gitignore` ditambah `.env.*`, `*.pem`, `*.p12`, `API.txt`, `*copy*.py`.

---

## Pembersihan riwayat git

**Belum dilakukan** di branch ini karena butuh *force-push* ke `main` dan mengubah semua
SHA commit. Ini keputusan pemilik repo. Lakukan **setelah** kunci dirotasi.

```bash
pip install git-filter-repo
git clone --mirror https://github.com/dwiahmaddzul/Aura.git aura-mirror
cd aura-mirror

# Hapus seluruh folder cadangan lama (sumber kunci, foto GPS, gambar berhak cipta)
git filter-repo --invert-paths --path Newbackup/ --path aura/ --path arsip/

# Jaga-jaga: ganti sisa string kunci di mana pun bila masih ada
printf 'regex:sk-yaluv[a-z]{40,}==>REDACTED\n' > ../replacements.txt
git filter-repo --replace-text ../replacements.txt

# Verifikasi: kedua perintah harus kosong
git log --all -p | grep -cE 'sk-yaluv[a-z]{40}'
git log --all --name-only --format= | grep -E 'API\.txt|\.jpg$'

git push --force --mirror
```

Setelah itu:

- Branch `security-audit-portfolio` perlu di-*rebase* ke `main` yang baru (atau
  terapkan ulang perubahannya), karena SHA lama tidak lagi ada.
- Hapus/klon ulang semua *clone* lokal lama. Minta GitHub Support membersihkan cache
  *pull request* / *commit view* bila perlu (lihat dokumentasi GitHub "Removing sensitive
  data from a repository").
- Aktifkan **Secret scanning** dan **Push protection** di Settings → Code security.

---

## Checklist sebelum repo dipromosikan

- [ ] Kunci SiliconFlow lama dicabut, kunci baru hanya ada di env
- [ ] Riwayat git dibersihkan dan di-force-push
- [ ] Branch `security-audit-portfolio` di-review, `pytest -q` lulus, lalu di-merge
- [ ] Env produksi: `ADMIN_PASSWORD` kuat, `SECRET_KEY` diisi, `TRUSTED_PROXY_HOPS` sesuai
- [ ] Demo publik memakai database dummy (bukan jurnal pribadi), atau dipasang auth
- [ ] Secret scanning + push protection GitHub aktif

## Keterbatasan audit ini

- `pytest` **tidak dijalankan** di lingkungan audit (instalasi paket dari PyPI diblokir
  oleh kebijakan jaringan). Perubahan hanya diverifikasi dengan `py_compile` dan
  pembacaan kode. Jalankan `pytest -q` sebelum merge.
- Pemindaian rahasia memakai pola regex pada semua blob riwayat (kunci `sk-`, AWS,
  Google, GitHub, Slack, HuggingFace, Groq, JWT, kunci privat, `password=`/`token=`),
  bukan alat khusus seperti gitleaks. Disarankan menjalankan
  `gitleaks detect --log-opts="--all"` sebagai pemeriksaan kedua.
- Tidak ada uji penetrasi terhadap deployment yang sedang berjalan.
