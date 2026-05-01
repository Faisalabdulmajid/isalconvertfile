<div align="center">
  <img src="static/icons/icon-192.png" alt="IsalConvertFile Logo" width="100"/>
  <h1>⚡ IsalConvertFile</h1>
  <p>Aplikasi Konversi Berbagai Format File Secara Mudah, Cepat, dan Offline (PWA).</p>
</div>

---

## ✨ Fitur Utama

- **Konversi Lengkap (10+ Tools):**
  - PDF ↔ Gambar (JPG/PNG)
  - Word (DOC/DOCX) ↔ PDF & Gambar
  - Excel (XLS/XLSX) ↔ PDF
  - PowerPoint (PPT/PPTX) ↔ PDF
  - Gambar ↔ Gambar (Ubah format)
  - Kompresi Gambar
  - Teks (TXT) ↔ PDF
- **Progressive Web App (PWA):** Dapat di-install langsung dari browser layaknya aplikasi desktop native.
- **Offline Mode:** Karena berjalan di atas *localhost*, semua file diproses langsung di komputer Anda tanpa koneksi internet (Privasi 100% terjaga).
- **Auto-Cleanup:** File hasil konversi dan unggahan sementara akan dihapus secara otomatis dari server setelah 5 menit untuk menghemat penyimpanan.
- **UI Modern:** Menggunakan desain *Dark Mode* bergaya *Glassmorphism* yang elegan dan sangat responsif di PC maupun Smartphone.

## 🛠 Teknologi

- **Backend:** Python (Flask)
- **Pemrosesan File:** `PyMuPDF` (PDF), `Pillow` (Gambar), `docx2pdf` (Word), `pywin32` (Office automation), `reportlab` (PDF generation).
- **Frontend:** HTML5, CSS3, Vanilla JS, Service Workers (PWA).

## 🚀 Cara Instalasi & Menjalankan

### Persyaratan Sistem
- Python 3.8 atau lebih baru.
- Microsoft Office (Word, Excel, PowerPoint) terinstal di sistem Windows Anda (Wajib untuk mengonversi dokumen office ke PDF/Image).

### Langkah-langkah
1. **Clone repositori ini:**
   ```bash
   git clone git@github.com:Faisalabdulmajid/isalconvertfile.git
   cd isalconvertfile
   ```

2. **Install dependensi (Library Python):**
   ```bash
   pip install -r requirements.txt
   ```

3. **Jalankan Aplikasi:**
   - **Bagi pengguna Windows:** Cukup klik ganda file `start.bat`.
   - **Secara manual via terminal:**
     ```bash
     python app.py
     ```

4. **Akses & Install PWA:**
   Buka browser Anda dan navigasikan ke `http://127.0.0.1:5000`. Klik tombol **"📲 Install App"** di pojok kanan atas untuk mengubahnya menjadi aplikasi desktop native.

---
*Dibuat dengan ❤️ oleh [Faisal Abdul Majid](mailto:faisalabdulmajid.dev@gmail.com).*
