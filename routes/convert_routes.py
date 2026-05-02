import os
import io
import shutil
import zipfile
import uuid
import time
import threading
import platform
import subprocess
import tempfile
from flask import Blueprint, request, jsonify, send_file, current_app, render_template
from werkzeug.utils import secure_filename

convert_bp = Blueprint('convert', __name__)

# ─── In-memory download registry: token → {path, filename, expires} ───────────
_download_registry = {}

def register_download(path, filename, ttl=300):
    """Store a file path under a token for later retrieval."""
    token = uuid.uuid4().hex
    _download_registry[token] = {
        'path': path,
        'filename': filename,
        'expires': time.time() + ttl
    }
    # Schedule cleanup
    def _cleanup():
        time.sleep(ttl + 5)
        entry = _download_registry.pop(token, None)
        if entry and os.path.exists(entry['path']):
            try:
                os.remove(entry['path'])
            except Exception:
                pass
    threading.Thread(target=_cleanup, daemon=True).start()
    return token

def register_bytes_download(data: bytes, filename: str, ttl=300):
    """Store in-memory bytes as a temp file and register it."""
    output_folder = 'outputs'
    os.makedirs(output_folder, exist_ok=True)
    ext = filename.rsplit('.', 1)[-1] if '.' in filename else 'bin'
    temp_path = os.path.join(output_folder, f"{uuid.uuid4().hex}.{ext}")
    with open(temp_path, 'wb') as fh:
        fh.write(data)
    return register_download(temp_path, filename, ttl)

def get_upload_path(filename):
    upload_folder = current_app.config['UPLOAD_FOLDER']
    unique_name = f"{uuid.uuid4().hex}_{secure_filename(filename)}"
    return os.path.join(upload_folder, unique_name)

def get_output_path(filename):
    output_folder = current_app.config['OUTPUT_FOLDER']
    os.makedirs(output_folder, exist_ok=True)
    return os.path.join(output_folder, filename)

def save_upload(f):
    path = get_upload_path(f.filename)
    f.save(path)
    # Auto-delete upload after 5 min
    def _del():
        time.sleep(300)
        try:
            os.remove(path)
        except Exception:
            pass
    threading.Thread(target=_del, daemon=True).start()
    return path

# ─── SMART OFFICE CONVERTER ──────────────────────────────────────────────────

def find_libreoffice():
    """Find the LibreOffice / soffice executable path on any OS."""
    # Common names tried via PATH
    for cmd in ['libreoffice', 'soffice']:
        found = shutil.which(cmd)
        if found:
            return found
    # Windows fallback: check common install paths
    if platform.system() == 'Windows':
        win_paths = [
            r'C:\Program Files\LibreOffice\program\soffice.exe',
            r'C:\Program Files (x86)\LibreOffice\program\soffice.exe',
        ]
        for p in win_paths:
            if os.path.exists(p):
                return p
    return None


def _convert_with_ms_office(input_path: str, out_dir: str, app_type: str):
    """
    Convert Office file to PDF using Microsoft Office COM automation.
    Only available on Windows with MS Office installed.
    Returns (success: bool, pdf_path_or_error: str)
    """
    if platform.system() != 'Windows':
        return False, 'MS Office COM automation hanya tersedia di Windows.'
    try:
        import win32com.client
        abs_input  = os.path.abspath(input_path)
        abs_out    = os.path.abspath(out_dir)
        base_stem  = os.path.splitext(os.path.basename(input_path))[0]
        out_pdf    = os.path.join(abs_out, base_stem + '.pdf')

        if app_type == 'word':
            app = win32com.client.Dispatch('Word.Application')
            app.Visible = False
            doc = app.Documents.Open(abs_input)
            doc.SaveAs(out_pdf, FileFormat=17)   # 17 = wdFormatPDF
            doc.Close(False)
            app.Quit()
        elif app_type == 'excel':
            app = win32com.client.Dispatch('Excel.Application')
            app.Visible = False
            wb = app.Workbooks.Open(abs_input)
            wb.ExportAsFixedFormat(0, out_pdf)   # 0 = xlTypePDF
            wb.Close(False)
            app.Quit()
        elif app_type == 'ppt':
            app = win32com.client.Dispatch('PowerPoint.Application')
            app.Visible = 1
            pres = app.Presentations.Open(abs_input, WithWindow=False)
            pres.SaveAs(out_pdf, 32)             # 32 = ppSaveAsPDF
            pres.Close()
            app.Quit()
        else:
            return False, f'app_type tidak dikenal: {app_type}'

        if os.path.exists(out_pdf):
            return True, out_pdf
        return False, 'File PDF tidak terbentuk oleh MS Office.'
    except ImportError:
        return False, 'pywin32 tidak terinstall.'
    except Exception as e:
        return False, str(e)


def _convert_with_libreoffice(input_path: str, out_dir: str):
    """
    Convert Office file to PDF using LibreOffice in headless mode.
    Works on Linux (hosting) and Windows (if LibreOffice is installed).
    Returns (success: bool, pdf_path_or_error: str)
    """
    lo = find_libreoffice()
    if not lo:
        return False, (
            'LibreOffice tidak ditemukan. '
            'Install LibreOffice (Linux: apt install libreoffice / '
            'Windows: https://www.libreoffice.org).'
        )
    try:
        abs_input = os.path.abspath(input_path)
        abs_out   = os.path.abspath(out_dir)
        result = subprocess.run(
            [lo, '--headless', '--convert-to', 'pdf', '--outdir', abs_out, abs_input],
            capture_output=True, text=True, timeout=120
        )
        base_stem = os.path.splitext(os.path.basename(input_path))[0]
        out_pdf   = os.path.join(abs_out, base_stem + '.pdf')
        if result.returncode != 0 or not os.path.exists(out_pdf):
            err = result.stderr or result.stdout or 'LibreOffice gagal.'
            return False, err
        return True, out_pdf
    except subprocess.TimeoutExpired:
        return False, 'Konversi timeout (120 detik). File mungkin terlalu besar.'
    except Exception as e:
        return False, str(e)


def office_to_pdf(input_path: str, app_type: str = 'word'):
    """
    Smart converter: MS Office (win32com) first on Windows, else LibreOffice headless.
    app_type: 'word' | 'excel' | 'ppt'
    Returns (success: bool, pdf_path_or_error: str)
    Caller is responsible for cleaning up the temp_dir.
    """
    # Use a dedicated temp dir inside outputs so LibreOffice writes there
    output_folder = current_app.config.get('OUTPUT_FOLDER', 'outputs')
    os.makedirs(output_folder, exist_ok=True)
    temp_dir = tempfile.mkdtemp(dir=output_folder)

    # 1️⃣  Try Microsoft Office (Windows only)
    if platform.system() == 'Windows':
        success, result = _convert_with_ms_office(input_path, temp_dir, app_type)
        if success:
            # Move to a UUID-named file to avoid collisions
            final = os.path.join(output_folder, f'{uuid.uuid4().hex}.pdf')
            shutil.move(result, final)
            shutil.rmtree(temp_dir, ignore_errors=True)
            return True, final
        # MS Office not available / failed → fall through to LibreOffice

    # 2️⃣  Fallback: LibreOffice headless
    success, result = _convert_with_libreoffice(input_path, temp_dir)
    if success:
        final = os.path.join(output_folder, f'{uuid.uuid4().hex}.pdf')
        shutil.move(result, final)
        shutil.rmtree(temp_dir, ignore_errors=True)
        return True, final

    shutil.rmtree(temp_dir, ignore_errors=True)
    return False, result

# ─── ROUTES ──────────────────────────────────────────────────────────────────

@convert_bp.route('/')
def index():
    return render_template('index.html')

# ── Download endpoint (token-based) ──────────────────────────────────────────
@convert_bp.route('/download/<token>')
def download_file(token):
    entry = _download_registry.get(token)
    if not entry:
        return "File tidak ditemukan atau sudah kedaluwarsa.", 404
    if time.time() > entry['expires']:
        _download_registry.pop(token, None)
        return "Link download sudah kedaluwarsa.", 410
    path = entry['path']
    filename = entry['filename']
    if not os.path.exists(path):
        return "File tidak tersedia.", 404
    return send_file(path, as_attachment=True, download_name=filename)

# ── PDF → JPG / PNG ──────────────────────────────────────────────────────────
@convert_bp.route('/convert/pdf-to-image', methods=['POST'])
def pdf_to_image():
    try:
        import fitz
    except ImportError:
        return jsonify({'error': 'PyMuPDF not installed. Run: pip install pymupdf'}), 500

    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    f = request.files['file']
    fmt = request.form.get('format', 'jpg').lower()
    dpi = int(request.form.get('dpi', 150))
    if not f.filename.lower().endswith('.pdf'):
        return jsonify({'error': 'File harus berupa PDF'}), 400

    input_path = save_upload(f)

    try:
        doc = fitz.open(input_path)
        if len(doc) == 1:
            page = doc[0]
            mat = fitz.Matrix(dpi / 72, dpi / 72)
            pix = page.get_pixmap(matrix=mat)
            out_name = f"{uuid.uuid4().hex}.{fmt}"
            out_path = get_output_path(out_name)
            pix.save(out_path, output='jpeg' if fmt in ('jpg', 'jpeg') else fmt)
            doc.close()
            dl_name = f"hasil_pdf.{fmt}"
            token = register_download(out_path, dl_name)
            return jsonify({'token': token, 'filename': dl_name})
        else:
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
                for i, page in enumerate(doc):
                    mat = fitz.Matrix(dpi / 72, dpi / 72)
                    pix = page.get_pixmap(matrix=mat)
                    img_bytes = pix.tobytes(output='jpeg' if fmt in ('jpg', 'jpeg') else fmt)
                    zf.writestr(f"halaman_{i+1}.{fmt}", img_bytes)
            doc.close()
            dl_name = 'hasil_pdf_semua_halaman.zip'
            token = register_bytes_download(zip_buffer.getvalue(), dl_name)
            return jsonify({'token': token, 'filename': dl_name})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ── JPG / PNG → PDF ──────────────────────────────────────────────────────────
@convert_bp.route('/convert/image-to-pdf', methods=['POST'])
def image_to_pdf():
    try:
        import fitz
        from PIL import Image as PILImage
    except ImportError:
        return jsonify({'error': 'Butuh: pip install pymupdf pillow'}), 500

    files = request.files.getlist('file')
    if not files or files[0].filename == '':
        return jsonify({'error': 'Tidak ada file yang dipilih'}), 400

    saved = []
    for f in files:
        ext = f.filename.rsplit('.', 1)[-1].lower()
        if ext not in ('jpg', 'jpeg', 'png', 'bmp', 'gif', 'tiff', 'webp'):
            return jsonify({'error': f'Format tidak didukung: {f.filename}'}), 400
        saved.append(save_upload(f))

    try:
        doc = fitz.open()
        for img_path in saved:
            img_doc = fitz.open(img_path)
            pdfbytes = img_doc.convert_to_pdf()
            img_doc.close()
            img_pdf = fitz.open("pdf", pdfbytes)
            doc.insert_pdf(img_pdf)
            img_pdf.close()

        out_name = f"{uuid.uuid4().hex}.pdf"
        out_path = get_output_path(out_name)
        doc.save(out_path)
        doc.close()

        dl_name = 'gambar_ke_pdf.pdf'
        token = register_download(out_path, dl_name)
        return jsonify({'token': token, 'filename': dl_name})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ── Word (DOCX) → PDF ────────────────────────────────────────────────────────
@convert_bp.route('/convert/word-to-pdf', methods=['POST'])
def word_to_pdf():
    if 'file' not in request.files:
        return jsonify({'error': 'Tidak ada file'}), 400
    f = request.files['file']
    if not f.filename.lower().endswith(('.doc', '.docx')):
        return jsonify({'error': 'File harus .doc atau .docx'}), 400

    input_path = save_upload(f)
    success, result = office_to_pdf(input_path, app_type='word')
    if not success:
        return jsonify({'error': result}), 500

    dl_name = 'dokumen_word.pdf'
    token = register_download(result, dl_name)
    return jsonify({'token': token, 'filename': dl_name})

# ── Word (DOCX) → Image ───────────────────────────────────────────────────────
@convert_bp.route('/convert/word-to-image', methods=['POST'])
def word_to_image():
    if 'file' not in request.files:
        return jsonify({'error': 'Tidak ada file'}), 400
    f = request.files['file']
    fmt = request.form.get('format', 'jpg').lower()
    dpi = int(request.form.get('dpi', 150))
    if not f.filename.lower().endswith(('.doc', '.docx')):
        return jsonify({'error': 'File harus .doc atau .docx'}), 400

    input_path = save_upload(f)

    # Step 1: DOCX → PDF (MS Office or LibreOffice)
    success, pdf_path = office_to_pdf(input_path, app_type='word')
    if not success:
        return jsonify({'error': pdf_path}), 500

    # Step 2: PDF → Images via PyMuPDF
    try:
        import fitz
        doc = fitz.open(pdf_path)
        zip_buf = io.BytesIO()
        with zipfile.ZipFile(zip_buf, 'w', zipfile.ZIP_DEFLATED) as zf:
            for i, page in enumerate(doc):
                mat = fitz.Matrix(dpi / 72, dpi / 72)
                pix = page.get_pixmap(matrix=mat)
                img_bytes = pix.tobytes(output='jpeg' if fmt in ('jpg', 'jpeg') else fmt)
                zf.writestr(f"halaman_{i+1}.{fmt}", img_bytes)
        doc.close()
        try:
            os.remove(pdf_path)
        except Exception:
            pass
        dl_name = 'word_ke_gambar.zip'
        token = register_bytes_download(zip_buf.getvalue(), dl_name)
        return jsonify({'token': token, 'filename': dl_name})
    except ImportError:
        return jsonify({'error': 'PyMuPDF tidak terinstall. Run: pip install pymupdf'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ── Excel → PDF ──────────────────────────────────────────────────────────────
@convert_bp.route('/convert/excel-to-pdf', methods=['POST'])
def excel_to_pdf():
    if 'file' not in request.files:
        return jsonify({'error': 'Tidak ada file'}), 400
    f = request.files['file']
    if not f.filename.lower().endswith(('.xls', '.xlsx')):
        return jsonify({'error': 'File harus .xls atau .xlsx'}), 400

    input_path = save_upload(f)
    success, result = office_to_pdf(input_path, app_type='excel')
    if not success:
        return jsonify({'error': result}), 500

    dl_name = 'spreadsheet.pdf'
    token = register_download(result, dl_name)
    return jsonify({'token': token, 'filename': dl_name})

# ── PowerPoint → PDF ─────────────────────────────────────────────────────────
@convert_bp.route('/convert/ppt-to-pdf', methods=['POST'])
def ppt_to_pdf():
    if 'file' not in request.files:
        return jsonify({'error': 'Tidak ada file'}), 400
    f = request.files['file']
    if not f.filename.lower().endswith(('.ppt', '.pptx')):
        return jsonify({'error': 'File harus .ppt atau .pptx'}), 400

    input_path = save_upload(f)
    success, result = office_to_pdf(input_path, app_type='ppt')
    if not success:
        return jsonify({'error': result}), 500

    dl_name = 'presentasi.pdf'
    token = register_download(result, dl_name)
    return jsonify({'token': token, 'filename': dl_name})

# ── Image → Image ─────────────────────────────────────────────────────────────
@convert_bp.route('/convert/image-to-image', methods=['POST'])
def image_to_image():
    try:
        from PIL import Image as PILImage
    except ImportError:
        return jsonify({'error': 'Pillow tidak terinstall. Run: pip install pillow'}), 500

    if 'file' not in request.files:
        return jsonify({'error': 'Tidak ada file'}), 400
    f = request.files['file']
    target_fmt = request.form.get('format', 'png').lower()
    quality = int(request.form.get('quality', 90))

    input_path = save_upload(f)

    try:
        img = PILImage.open(input_path)
        if img.mode in ('RGBA', 'LA', 'P') and target_fmt in ('jpg', 'jpeg'):
            img = img.convert('RGB')
        save_fmt = 'JPEG' if target_fmt in ('jpg', 'jpeg') else target_fmt.upper()
        out_name = f"{uuid.uuid4().hex}.{target_fmt}"
        out_path = get_output_path(out_name)
        if save_fmt == 'JPEG':
            img.save(out_path, format=save_fmt, quality=quality)
        else:
            img.save(out_path, format=save_fmt)
        dl_name = f"gambar_konversi.{target_fmt}"
        token = register_download(out_path, dl_name)
        return jsonify({'token': token, 'filename': dl_name})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ── TXT → PDF ─────────────────────────────────────────────────────────────────
@convert_bp.route('/convert/txt-to-pdf', methods=['POST'])
def txt_to_pdf():
    try:
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import A4
    except ImportError:
        return jsonify({'error': 'reportlab tidak terinstall. Run: pip install reportlab'}), 500

    if 'file' not in request.files:
        return jsonify({'error': 'Tidak ada file'}), 400
    f = request.files['file']
    if not f.filename.lower().endswith('.txt'):
        return jsonify({'error': 'File harus .txt'}), 400

    input_path = save_upload(f)
    out_name = f"{uuid.uuid4().hex}.pdf"
    out_path = get_output_path(out_name)

    try:
        with open(input_path, 'r', encoding='utf-8', errors='replace') as rf:
            lines = rf.readlines()
        c = canvas.Canvas(out_path, pagesize=A4)
        width, height = A4
        margin = 50
        y = height - margin
        c.setFont("Helvetica", 11)
        for line in lines:
            text = line.rstrip('\n')
            c.drawString(margin, y, text[:110])
            y -= 16
            if y < margin:
                c.showPage()
                c.setFont("Helvetica", 11)
                y = height - margin
        c.save()
        dl_name = 'teks_ke_pdf.pdf'
        token = register_download(out_path, dl_name)
        return jsonify({'token': token, 'filename': dl_name})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ── PDF → TXT ─────────────────────────────────────────────────────────────────
@convert_bp.route('/convert/pdf-to-txt', methods=['POST'])
def pdf_to_txt():
    try:
        import fitz
    except ImportError:
        return jsonify({'error': 'PyMuPDF tidak terinstall. Run: pip install pymupdf'}), 500

    if 'file' not in request.files:
        return jsonify({'error': 'Tidak ada file'}), 400
    f = request.files['file']
    if not f.filename.lower().endswith('.pdf'):
        return jsonify({'error': 'File harus PDF'}), 400

    input_path = save_upload(f)

    try:
        doc = fitz.open(input_path)
        text_parts = [page.get_text() for page in doc]
        doc.close()
        full_text = '\n'.join(text_parts)
        dl_name = 'teks_dari_pdf.txt'
        token = register_bytes_download(full_text.encode('utf-8'), dl_name)
        return jsonify({'token': token, 'filename': dl_name})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ── Compress Image ─────────────────────────────────────────────────────────────
@convert_bp.route('/convert/compress-image', methods=['POST'])
def compress_image():
    try:
        from PIL import Image as PILImage
    except ImportError:
        return jsonify({'error': 'Pillow tidak terinstall. Run: pip install pillow'}), 500

    if 'file' not in request.files:
        return jsonify({'error': 'Tidak ada file'}), 400
    f = request.files['file']
    quality = int(request.form.get('quality', 60))
    max_width = int(request.form.get('max_width', 1920))
    orig_name = f.filename

    input_path = save_upload(f)

    try:
        img = PILImage.open(input_path)
        if img.width > max_width:
            ratio = max_width / img.width
            img = img.resize((max_width, int(img.height * ratio)), PILImage.LANCZOS)

        ext = orig_name.rsplit('.', 1)[-1].lower()
        save_fmt = 'JPEG' if ext in ('jpg', 'jpeg') else ext.upper()
        if save_fmt == 'JPEG' and img.mode in ('RGBA', 'P'):
            img = img.convert('RGB')

        out_name = f"{uuid.uuid4().hex}.{ext}"
        out_path = get_output_path(out_name)
        if save_fmt == 'JPEG':
            img.save(out_path, format='JPEG', quality=quality, optimize=True)
        else:
            img.save(out_path, format=save_fmt, optimize=True)

        base = orig_name.rsplit('.', 1)[0]
        dl_name = f"{base}_compressed.{ext}"
        token = register_download(out_path, dl_name)
        return jsonify({'token': token, 'filename': dl_name})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
