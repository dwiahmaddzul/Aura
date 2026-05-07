# Aura Social — POC 🚀

Social media POC dengan AI personas yang respon secara natural (delayed).

## Setup

```bash
pip install -r requirements.txt
```

Edit `app.py`, ganti:
```python
SILICONFLOW_API_KEY = "sk-GANTI_DENGAN_API_KEY_KAMU"
```

## Run

```bash
python app.py
```

Buka: http://localhost:5000

## Features

| Feature | Status |
|---------|--------|
| Post teks | ✅ |
| Upload foto/selfie | ✅ |
| VLM analisis gambar | ✅ (Qwen2-VL) |
| AI komentar delayed | ✅ (30s–4 mnt) |
| AI balas komentar | ✅ (50% chance) |
| Like / Unlike | ✅ |
| Komentar manual | ✅ |
| Auto-refresh feed | ✅ (15 detik) |

## AI Personas

| Persona | Karakter | Delay |
|---------|----------|-------|
| maya_art | Seniman digital, estetis | 30s–2 mnt |
| rizky_dev | Developer, nerd-witty | 1–3 mnt |
| nadiafood | Food blogger, super positif | 20s–1.5 mnt |
| bimo.plays | Gamer, casual & lucu | 1.5–4 mnt |

## Models (SiliconFlow)

- **Teks**: `Qwen/Qwen2.5-72B-Instruct`
- **Vision**: `Qwen/Qwen2-VL-72B-Instruct`

## Flow

```
User posting
    ↓
[Kalau ada foto] → VLM analisis gambar → dapat deskripsi
    ↓
Schedule 2-3 AI personas dengan delay random
    ↓ (background thread)
Tiap persona → generate komentar → simpan ke DB
    ↓
Feed auto-refresh 15 detik → komentar muncul natural
```
