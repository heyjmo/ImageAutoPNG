# ImageAutoPNG

Free Windows **system-tray** utility that watches a folder (default: Downloads) and **silently converts** `.webp`, `.heic`, `.heif`, and `.avif` images to `.png`.

**Website:** [heyjmo.com/AutoPNG](https://heyjmo.com/AutoPNG/)  
**Author:** [heyjmo](https://github.com/heyjmo)  
**License:** MIT  

If this saves you time, optional tips are welcome via [PayPal](https://paypal.me/heyjmo). Never required.

## Download

Grab the latest **Setup** build from [Releases](https://github.com/heyjmo/ImageAutoPNG/releases/latest):

- `ImageAutoPNG-Setup.exe` — recommended installer  
- `ImageAutoPNG.exe` — portable (optional)

Windows may show SmartScreen (“Unknown publisher”) because the app is not code-signed. Choose **More info → Run anyway**. That is normal for free tools from independent authors.

## Features

- Tray icon only  
- Instant convert when matching files appear  
- Choose any watch folder  
- Optional delete originals after convert  
- Start with Windows  
- Per-user install (no admin)  
- Uninstall from Settings → Apps  

## Build from source

Requires Python 3.10+ on Windows.

```powershell
pip install -r requirements.txt
python app.py
```

Installer EXE:

```powershell
python build_exe.py
```

Outputs land in `release/`.

## Config & log

`%USERPROFILE%\.imageautopng\config.json`  
`%USERPROFILE%\.imageautopng\convert.log`

## Publishing / website

See [PUBLISHING.md](PUBLISHING.md) for GitHub, donations, and FTP re-upload of the one-pager.

## Privacy

All conversion is local. No accounts, no telemetry, no upload of your images.
