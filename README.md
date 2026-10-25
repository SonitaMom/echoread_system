# EchoRead

## Run locally on Windows

### 1. Install the Python dependencies

From the project folder, create and activate a virtual environment, then install the packages:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### 2. Install Tesseract OCR

Download and install the Windows version of Tesseract from the
[UB Mannheim Tesseract installer page](https://github.com/UB-Mannheim/tesseract/wiki).
Use the default installation folder:

```text
C:\Program Files\Tesseract-OCR
```

### 3. Add Khmer OCR data

Download [`khm.traineddata`](https://github.com/tesseract-ocr/tessdata/raw/main/khm.traineddata)
and save it in Tesseract's `tessdata` folder:

```text
C:\Program Files\Tesseract-OCR\tessdata\khm.traineddata
```

You can download it directly from an elevated PowerShell window:

```powershell
Invoke-WebRequest `
  -Uri "https://github.com/tesseract-ocr/tessdata/raw/main/khm.traineddata" `
  -OutFile "C:\Program Files\Tesseract-OCR\tessdata\khm.traineddata"
```

Confirm that Tesseract can see both languages:

```powershell
& "C:\Program Files\Tesseract-OCR\tesseract.exe" --list-langs
```

The output should include `eng` and `khm`.

The app uses `eng+khm` for OCR by default. If Tesseract or its language data
is installed elsewhere, set `TESSERACT_CMD` to the full path to `tesseract.exe`
and `TESSDATA_DIR` to the folder containing the traineddata files before
starting the app.

### 4. Start EchoRead

With the virtual environment active, run the database migrations and start the
local Django server:

```powershell
python manage.py migrate
python manage.py runserver
```

Open [http://127.0.0.1:8000/register/](http://127.0.0.1:8000/register/) to
create an account, then sign in and open
[http://127.0.0.1:8000/reader/](http://127.0.0.1:8000/reader/). Upload a PDF
there to read it. Scanned or image-only pages are processed with Tesseract;
PDFs with selectable text use their existing text.
