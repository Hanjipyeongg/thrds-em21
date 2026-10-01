# thrds-em21

Gambar infografik untuk akun Threads , dirender otomatis dari tab "Data Gambar" di sheet Metrik Mingguan.

- `templates/`: tiga layout (checklist, langkah, perbandingan) ukuran 1080 × 1350 px.
- `render.py`: membaca data (JSON) dan menyimpan PNG ke `images/<Minggu ke>/<Post ID>.png`, plus `manifest.json` berisi link raw untuk Buffer.
- `fonts/`: Plus Jakarta Sans (SIL Open Font License, lihat `fonts/OFL-LICENSE.txt`).

```
python3 render.py data.json
```

Repo ini publik supaya Buffer bisa membaca gambarnya. Jangan simpan file lain di sini.
