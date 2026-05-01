// ── Tool Config ────────────────────────────────────────────────────────────
// downloadName: function(formData) => string — builds the output filename
const TOOLS = {
  'pdf-to-image': {
    title: 'PDF ke Gambar',
    endpoint: '/convert/pdf-to-image',
    accept: '.pdf',
    multiple: false,
    downloadName: (fd) => `hasil_pdf.${fd.get('format') || 'jpg'}`,
    options: [
      { id: 'format', label: 'Format Output', type: 'select', choices: ['jpg','png'] },
      { id: 'dpi',    label: 'Kualitas (DPI)', type: 'select', choices: ['72','96','150','200','300'], default: '150' }
    ]
  },
  'image-to-pdf': {
    title: 'Gambar ke PDF',
    endpoint: '/convert/image-to-pdf',
    accept: '.jpg,.jpeg,.png,.bmp,.tiff,.webp',
    multiple: true,
    downloadName: () => 'gambar_ke_pdf.pdf',
    options: []
  },
  'word-to-pdf': {
    title: 'Word ke PDF',
    endpoint: '/convert/word-to-pdf',
    accept: '.doc,.docx',
    multiple: false,
    downloadName: () => 'dokumen_word.pdf',
    options: []
  },
  'word-to-image': {
    title: 'Word ke Gambar',
    endpoint: '/convert/word-to-image',
    accept: '.doc,.docx',
    multiple: false,
    downloadName: (fd) => `word_ke_gambar.zip`,
    options: [
      { id: 'format', label: 'Format Output', type: 'select', choices: ['jpg','png'] },
      { id: 'dpi',    label: 'Kualitas (DPI)', type: 'select', choices: ['72','96','150','200','300'], default: '150' }
    ]
  },
  'excel-to-pdf': {
    title: 'Excel ke PDF',
    endpoint: '/convert/excel-to-pdf',
    accept: '.xls,.xlsx',
    multiple: false,
    downloadName: () => 'spreadsheet.pdf',
    options: []
  },
  'ppt-to-pdf': {
    title: 'PowerPoint ke PDF',
    endpoint: '/convert/ppt-to-pdf',
    accept: '.ppt,.pptx',
    multiple: false,
    downloadName: () => 'presentasi.pdf',
    options: []
  },
  'image-to-image': {
    title: 'Konversi Format Gambar',
    endpoint: '/convert/image-to-image',
    accept: '.jpg,.jpeg,.png,.bmp,.gif,.tiff,.webp',
    multiple: false,
    downloadName: (fd) => `gambar_konversi.${fd.get('format') || 'png'}`,
    options: [
      { id: 'format',  label: 'Format Output', type: 'select', choices: ['png','jpg','webp','bmp','tiff'] },
      { id: 'quality', label: 'Kualitas (1-100)', type: 'number', min: 1, max: 100, default: '90' }
    ]
  },
  'txt-to-pdf': {
    title: 'TXT ke PDF',
    endpoint: '/convert/txt-to-pdf',
    accept: '.txt',
    multiple: false,
    downloadName: () => 'teks_ke_pdf.pdf',
    options: []
  },
  'pdf-to-txt': {
    title: 'PDF ke TXT (Ekstrak Teks)',
    endpoint: '/convert/pdf-to-txt',
    accept: '.pdf',
    multiple: false,
    downloadName: () => 'teks_dari_pdf.txt',
    options: []
  },
  'compress-image': {
    title: 'Kompres Gambar',
    endpoint: '/convert/compress-image',
    accept: '.jpg,.jpeg,.png,.webp',
    multiple: false,
    downloadName: (fd) => {
      const orig = selectedFiles[0]?.name || 'gambar';
      const ext  = orig.split('.').pop();
      const base = orig.replace(/\.[^.]+$/, '');
      return `${base}_compressed.${ext}`;
    },
    options: [
      { id: 'quality',   label: 'Kualitas (1-100)', type: 'number', min: 1, max: 100, default: '60' },
      { id: 'max_width', label: 'Lebar Maks (px)',  type: 'number', min: 100, max: 8000, default: '1920' }
    ]
  }
};

// ── State ──────────────────────────────────────────────────────────────────
let currentTool = null;
let selectedFiles = [];

// ── DOM refs ───────────────────────────────────────────────────────────────
const panel       = document.getElementById('converter-panel');
const panelTitle  = document.getElementById('panel-title');
const dropzone    = document.getElementById('dropzone');
const fileInput   = document.getElementById('file-input');
const filePreview = document.getElementById('file-preview');
const fileInfo    = document.getElementById('file-info');
const btnRemove   = document.getElementById('btn-remove');
const optionsRow  = document.getElementById('options-row');
const btnConvert  = document.getElementById('btn-convert');
const btnLabel    = document.getElementById('btn-label');
const spinner     = document.getElementById('spinner');
const errorBox    = document.getElementById('error-box');
const closeBtn    = document.getElementById('close-panel');

// ── Open panel ─────────────────────────────────────────────────────────────
document.querySelectorAll('.tool-card').forEach(card => {
  card.addEventListener('click', () => {
    const key = card.dataset.tool;
    openPanel(key);
  });
});

function openPanel(key) {
  currentTool = TOOLS[key];
  if (!currentTool) return;

  panelTitle.textContent = currentTool.title;
  fileInput.accept  = currentTool.accept;
  fileInput.multiple = currentTool.multiple;

  // reset state
  selectedFiles = [];
  filePreview.style.display = 'none';
  dropzone.style.display    = 'block';
  errorBox.style.display    = 'none';
  errorBox.textContent      = '';
  btnConvert.disabled       = true;

  // build options
  optionsRow.innerHTML = '';
  currentTool.options.forEach(opt => {
    const grp = document.createElement('div');
    grp.className = 'opt-group';
    grp.innerHTML = `<label for="opt-${opt.id}">${opt.label}</label>`;
    let input;
    if (opt.type === 'select') {
      input = document.createElement('select');
      input.id = `opt-${opt.id}`;
      input.name = opt.id;
      opt.choices.forEach(c => {
        const o = document.createElement('option');
        o.value = c; o.textContent = c.toUpperCase();
        if (c === (opt.default || opt.choices[0])) o.selected = true;
        input.appendChild(o);
      });
    } else {
      input = document.createElement('input');
      input.type = opt.type;
      input.id   = `opt-${opt.id}`;
      input.name = opt.id;
      input.min  = opt.min; input.max = opt.max;
      input.value = opt.default || '';
    }
    grp.appendChild(input);
    optionsRow.appendChild(grp);
  });

  panel.style.display = 'block';
  panel.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

// ── Close ──────────────────────────────────────────────────────────────────
closeBtn.addEventListener('click', () => {
  panel.style.display = 'none';
});

// ── Dropzone events ────────────────────────────────────────────────────────
dropzone.addEventListener('dragover', e => { e.preventDefault(); dropzone.classList.add('drag-over'); });
dropzone.addEventListener('dragleave', () => dropzone.classList.remove('drag-over'));
dropzone.addEventListener('drop', e => {
  e.preventDefault(); dropzone.classList.remove('drag-over');
  handleFiles(e.dataTransfer.files);
});
dropzone.addEventListener('click', () => fileInput.click());
fileInput.addEventListener('change', () => handleFiles(fileInput.files));

function handleFiles(files) {
  if (!files || files.length === 0) return;
  selectedFiles = Array.from(files);
  const names = selectedFiles.map(f => `${f.name} (${formatSize(f.size)})`).join(', ');
  fileInfo.textContent = selectedFiles.length > 1
    ? `${selectedFiles.length} file dipilih: ${names}`
    : names;
  dropzone.style.display    = 'none';
  filePreview.style.display = 'flex';
  btnConvert.disabled       = false;
  errorBox.style.display    = 'none';
}

btnRemove.addEventListener('click', () => {
  selectedFiles = [];
  fileInput.value = '';
  filePreview.style.display = 'none';
  dropzone.style.display    = 'block';
  btnConvert.disabled       = true;
});

function formatSize(bytes) {
  if (bytes < 1024) return bytes + ' B';
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
}

// ── Convert ────────────────────────────────────────────────────────────────
btnConvert.addEventListener('click', async () => {
  if (!currentTool || selectedFiles.length === 0) return;

  setLoading(true);
  errorBox.style.display = 'none';

  const fd = new FormData();
  if (currentTool.multiple) {
    selectedFiles.forEach(f => fd.append('file', f));
  } else {
    fd.append('file', selectedFiles[0]);
  }

  // collect options
  currentTool.options.forEach(opt => {
    const el = document.getElementById(`opt-${opt.id}`);
    if (el) fd.append(opt.id, el.value);
  });

  try {
    const res = await fetch(currentTool.endpoint, { method: 'POST', body: fd });
    const json = await res.json();

    if (!res.ok || json.error) {
      throw new Error(json.error || `HTTP ${res.status}`);
    }

    // Server returned a token → redirect browser to /download/<token>
    // This uses native browser download — reliable on all browsers
    if (json.token) {
      window.location.href = `/download/${json.token}`;
    } else {
      throw new Error('Respons server tidak valid');
    }
  } catch (err) {
    showError(err.message);
  } finally {
    setLoading(false);
  }
});

function setLoading(on) {
  btnConvert.disabled = on;
  btnLabel.style.display  = on ? 'none' : 'inline';
  spinner.style.display   = on ? 'inline-block' : 'none';
}

function showError(msg) {
  errorBox.textContent = `❌ Error: ${msg}`;
  errorBox.style.display = 'block';
}

// ── FAQ accordion ──────────────────────────────────────────────────────────
document.querySelectorAll('.faq-q').forEach(btn => {
  btn.addEventListener('click', () => {
    const answer = btn.nextElementSibling;
    const isOpen = btn.classList.contains('open');
    document.querySelectorAll('.faq-q.open').forEach(b => {
      b.classList.remove('open');
      b.nextElementSibling.classList.remove('open');
    });
    if (!isOpen) { btn.classList.add('open'); answer.classList.add('open'); }
  });
});
