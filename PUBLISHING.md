# Publishing checklist (personal / donationware)

## Already filled in for you

| Item | Value |
|------|--------|
| GitHub user | [heyjmo](https://github.com/heyjmo) |
| Suggested repo | `ImageAutoPNG` → https://github.com/heyjmo/ImageAutoPNG |
| Website | https://heyjmo.com/AutoPNG/ |
| Publisher name in app | `heyjmo` |
| License | MIT (`LICENSE`) |
| Donate link | https://paypal.me/heyjmo |

## What you still need to do

### 1. Create the GitHub repository

1. Sign in at https://github.com/heyjmo  
2. **New repository** → name: `ImageAutoPNG`  
3. Public · no README (we already have one)  
4. Create repository  

Then on your PC (GitHub CLI or Git):

```powershell
cd c:\users\flagstone\downloads\webp-heic-converter
git init
git add .
git commit -m "Initial ImageAutoPNG release"
git branch -M main
git remote add origin https://github.com/heyjmo/ImageAutoPNG.git
git push -u origin main
```

(You will be asked to log in to GitHub the first time.)

### 2. Donations (PayPal)

Already set to **https://paypal.me/heyjmo** in:

- `version_info.py` (tray menu + About)
- `website/AutoPNG/index.html`

To change later, edit `DONATE_URL` and re-upload the site / rebuild the EXE.

### 3. Build and publish a Release download

```powershell
cd c:\users\flagstone\downloads\webp-heic-converter
python build_exe.py
```

On GitHub: **Releases → Draft a new release**

- Tag: `v1.3.0`
- Title: `ImageAutoPNG 1.3.0`
- Upload from `release\`:
  - `ImageAutoPNG-Setup.exe`
  - `ImageAutoPNG.exe` (optional portable)
- Publish

The website “Download” button already points at:

`https://github.com/heyjmo/ImageAutoPNG/releases/latest`

### 4. Website (done if FTP upload succeeded)

Live page: **https://heyjmo.com/AutoPNG/**

Local files: `website/AutoPNG/`

To re-upload after edits:

```powershell
python upload_website.py
```

(You will be prompted for the FTP password — do not store it in the repo.)

### 5. Security: change your FTP password

You shared the FTP password in chat. **Change it in cPanel** after publishing:

cPanel → FTP Accounts / Password → set a new password.

Never commit passwords into GitHub.

## Tray menu links

After rebuild, the app menu includes:

- **Website** → heyjmo.com/AutoPNG  
- **GitHub** → github.com/heyjmo/ImageAutoPNG  
- **Donate…** → sponsors link (or your Ko-fi once set)
