# Peça Studio source snapshot — 1.9.1

This directory contains the application's Python and browser source, tests, brand assets and Windows packaging files. The installed product and update manifest remain at the repository root/releases.

`SOURCE-MANIFEST.json` identifies the source commit and SHA-256 of each copied upstream file. Internal project history/reports, personal libraries, credentials, virtual environments and compiled binaries are excluded. Documentation in this file was written for this public snapshot.

## Run locally

Requirements: Python 3.12 and a current Chrome/Edge browser. Extended media/OCR/export features also use the dependencies and tools described below.

```powershell
cd codigo-fonte
python -m venv .runtime
.runtime\Scripts\python.exe -m pip install -r requirements-local.txt -r packaging/requirements-integralis.txt
.runtime\Scripts\python.exe server.py
```

Open `http://127.0.0.1:17865`. On Windows, `Preparar-recursos-locais.cmd` prepares local feature dependencies and `Abrir.cmd` starts the browser version. Do not open `index.html` directly.

The source has a local development mode. Commercial Windows packages use the Integralis configuration and validate identity, product entitlement and session. No credentials or access to a paid account are supplied by this snapshot. AI integrations require the user's own provider configuration; provider usage is separate from the product subscription.

## Tests

Node.js 22 and Python 3.12 are used by CI.

```powershell
npm test
$env:PYTHONUTF8='1'
.runtime\Scripts\python.exe -m unittest discover -s tests -p 'test_*.py'
```

The full local suite uses Pillow/OpenCV/PDF libraries and feature dependencies from `requirements-local.txt`. OCR/media checks may additionally need Tesseract (English/Portuguese data) and FFmpeg on the machine. The hosted workflow runs JavaScript and the isolated native OAuth/refresh regression on Windows and Linux.

## Windows build

Install `packaging/requirements-desktop.txt`, Inno Setup 6, FFmpeg/ffprobe and Tesseract with the language data required by `packaging/build_desktop.py`.

```powershell
.runtime\Scripts\python.exe -m pip install -r packaging/requirements-desktop.txt
.runtime\Scripts\python.exe packaging/build_desktop.py --build-root ../build-local --output ../installer-local
```

For a commercial build, prepare a private configuration using `packaging/commercial-config.example.json` and pass its path with `--commercial-config`. Do not publish the populated configuration or credentials. Review tool discovery paths in the build script for the build machine. The current 1.9.1 public installer is unsigned; trusted Authenticode is pending TI work.

## Maintenance and distribution

- [Application listing](https://integralislabs.com/marketplace/peca-studio)
- [Installers](https://github.com/integralislabs/peca-studio-distribuicao/releases)
- [Stripe LIVE task](https://github.com/integralislabs/integralis/issues/582)
- [Authenticode task](https://github.com/integralislabs/integralis/issues/583)

The two TI tasks are in a private repository and require access. This snapshot is versioned with its upstream commit; it does not automatically synchronize future changes. Existing third-party license/provenance files are preserved in `brand/` and `packaging/licenses/`. Publishing this snapshot does not add a new open-source license.
