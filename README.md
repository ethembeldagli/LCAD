# LCAD (Lutris Cover Downloader) 🎮🖼️

![License](https://img.shields.io/github/license/ethembeldagli/lutris-cover-downloader?style=for-the-badge)
![GTK Version](https://img.shields.io/badge/GTK-4.0-blue?style=for-the-badge&logo=gtk)
![Platform](https://img.shields.io/badge/Platform-Linux-orange?style=for-the-badge&logo=linux)
![Architecture](https://img.shields.io/badge/Arch-x86__64-brightgreen?style=for-the-badge)

**LCAD** (Lutris Cover Downloader) is a modern, lightweight GTK4 application designed to automatically scan your Lutris library, fetch missing cover art, and organize your game grid effortlessly.

---

## ✨ Features

- 🔍 **Automated Library Scanning:** Automatically detects games installed via Lutris.
- 🎨 **High-Quality Cover Fetching:** Downloads matching banner and box artwork.
- 🐧 **Modern Linux UI:** Built using GTK4 and Libadwaita for a native GNOME desktop experience.
- ⚡ **Fast & Lightweight:** Minimal system resource usage with quick multi-threaded downloads.

---

## 📦 Installation

Pre-compiled packages for **x86_64** Linux systems are available on the [Releases Page](https://github.com/ethembeldagli/lutris-cover-downloader/releases).

### 🔷 Universal (Flatpak)
```bash
flatpak install ./lcad.flatpak
```

### 🌀 Debian / Ubuntu / Linux Mint (`.deb`)
```bash
sudo apt install ./lcad.deb
```

### 🔴 Fedora / RHEL / Bazzite (`.rpm`)
```bash
sudo dnf install ./lcad.rpm
```

---

## 🛠️ Building from Source

If you wish to run or build LCAD manually from source (e.g., on ARM/`aarch64` devices):

### 1. Prerequisites
Ensure you have Python 3.10+ and GTK4 installed on your system:

**Debian/Ubuntu:**
```bash
sudo apt install -y python3 python3-gi python3-gi-cairo libgtk-4-dev
```

**Fedora/Bazzite:**
```bash
sudo dnf install -y python3 python3-gobject gtk4
```

### 2. Clone & Run
```bash
# Clone the repository
git clone [https://github.com/ethembeldagli/lutris-cover-downloader.git](https://github.com/ethembeldagli/lutris-cover-downloader.git)
cd lutris-cover-downloader

# Install Python dependencies
pip install -r requirements.txt

# Run the app
python3 main.py
```

---

## 🤝 Contributing

Contributions, bug reports, and feature requests are welcome! 
Feel free to check out the [Issues Page](https://github.com/ethembeldagli/lutris-cover-downloader/issues) if you'd like to help improve LCAD.

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
