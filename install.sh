#!/bin/bash

# LCAD Multi-Distro Installation Script (v1.1.0)
# Detects distribution, checks/installs prerequisites (like Flatpak), and installs LCAD.

REPO_URL="https://github.com/ethembeldagli/lcad/releases/download/v1.1.0"

# Detect distribution
if [ -f /etc/os-release ]; then
    . /etc/os-release
    OS_ID="$ID"
    OS_LIKE="$ID_LIKE"
else
    echo "Could not detect distribution via /etc/os-release."
    exit 1
fi

echo "Detected operating system: $NAME ($OS_ID)"
echo "--------------------------------------------------"

# Function to ensure flatpak is installed based on distro type
ensure_flatpak() {
    if ! command -v flatpak &> /dev/null; then
        echo "Flatpak is not installed. Attempting to install Flatpak..."
        if [[ "$OS_ID" == "fedora" ]] || [[ "$OS_LIKE" =~ "fedora" ]] || [[ "$OS_ID" == "bazzite" ]]; then
            sudo dnf install -y flatpak
        elif [[ "$OS_ID" == "debian" ]] || [[ "$OS_ID" == "ubuntu" ]] || [[ "$OS_LIKE" =~ "debian" ]] || [[ "$OS_LIKE" =~ "ubuntu" ]]; then
            sudo apt update && sudo apt install -y flatpak
        elif [[ "$OS_ID" == "opensuse" ]] || [[ "$OS_LIKE" =~ "suse" ]]; then
            sudo zypper install -y flatpak
        else
            echo "Warning: Could not automatically install Flatpak for this distro. Please install it manually."
        fi
    fi
    
    # Ensure Flathub repository is added
    if command -v flatpak &> /dev/null; then
        flatpak remote-add --if-not-exists flathub https://dl.flathub.org/repo/flathub.flatpakrepo
    fi
}

# Function for user choice prompt
prompt_choice() {
    echo "Choose installation format:"
    echo "1) Flatpak (Universal)"
    echo "2) $1"
    read -p "Enter choice [1 or 2]: " choice
}

# Bazzite / Atomic Fedora-based handling
if [[ "$OS_ID" == "bazzite" ]] || [[ "$OS_LIKE" =~ "fedora" ]] && command -v rpm-ostree &> /dev/null; then
    echo "Detected an immutable/OSTree-based Fedora/Bazzite system."
    prompt_choice "RPM (via rpm-ostree)"
    
    if [ "$choice" == "1" ]; then
        ensure_flatpak
        echo "Installing via Flatpak..."
        curl -LO "$REPO_URL/lcad-x86-universal.flatpak"
        flatpak install --user -y ./lcad-x86-universal.flatpak
        rm -f lcad-x86-universal.flatpak
    elif [ "$choice" == "2" ]; then
        echo "Installing RPM via rpm-ostree..."
        curl -LO "$REPO_URL/lcad-x86-fedora-opensuse.rpm"
        rpm-ostree install ./lcad-x86-fedora-opensuse.rpm
        rm -f lcad-x86-fedora-opensuse.rpm
    else
        echo "Invalid selection."
    fi

# Standard Fedora / RHEL / openSUSE handling
elif [[ "$OS_ID" == "fedora" ]] || [[ "$OS_LIKE" =~ "fedora" ]] || [[ "$OS_ID" == "rhel" ]] || [[ "$OS_ID" == "opensuse" ]] || [[ "$OS_LIKE" =~ "suse" ]]; then
    prompt_choice "RPM"
    
    if [ "$choice" == "1" ]; then
        ensure_flatpak
        echo "Installing via Flatpak..."
        curl -LO "$REPO_URL/lcad-x86-universal.flatpak"
        flatpak install --user -y ./lcad-x86-universal.flatpak
        rm -f lcad-x86-universal.flatpak
    elif [ "$choice" == "2" ]; then
        echo "Installing RPM..."
        curl -LO "$REPO_URL/lcad-x86-fedora-opensuse.rpm"
        sudo dnf install -y ./lcad-x86-fedora-opensuse.rpm
        rm -f lcad-x86-fedora-opensuse.rpm
    else
        echo "Invalid selection."
    fi

# Debian / Ubuntu / Linux Mint handling
elif [[ "$OS_ID" == "debian" ]] || [[ "$OS_ID" == "ubuntu" ]] || [[ "$OS_LIKE" =~ "debian" ]] || [[ "$OS_LIKE" =~ "ubuntu" ]]; then
    prompt_choice "DEB"
    
    if [ "$choice" == "1" ]; then
        ensure_flatpak
        echo "Installing via Flatpak..."
        curl -LO "$REPO_URL/lcad-x86-universal.flatpak"
        flatpak install --user -y ./lcad-x86-universal.flatpak
        rm -f lcad-x86-universal.flatpak
    elif [ "$choice" == "2" ]; then
        echo "Installing DEB..."
        curl -LO "$REPO_URL/lcad-x86-debian-ubuntu-mint.deb"
        sudo apt update && sudo apt install -y ./lcad-x86-debian-ubuntu-mint.deb
        rm -f lcad-x86-debian-ubuntu-mint.deb
    else
        echo "Invalid selection."
    fi

# Fallback for unrecognized distros
else
    echo "Unsupported or unrecognized distribution: $OS_ID"
    echo "Defaulting to Flatpak installation..."
    ensure_flatpak
    curl -LO "$REPO_URL/lcad-x86-universal.flatpak"
    flatpak install --user -y ./lcad-x86-universal.flatpak
    rm -f lcad-x86-universal.flatpak
fi

echo "--------------------------------------------------"
echo "Installation process completed!"