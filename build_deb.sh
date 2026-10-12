#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PACKAGE_NAME="cleanux"
VERSION="1.0.0"
ARCH="all"
BUILD_DIR="${SCRIPT_DIR}/build/${PACKAGE_NAME}_${VERSION}_${ARCH}"
OUTPUT_DEB="${SCRIPT_DIR}/${PACKAGE_NAME}_${VERSION}_${ARCH}.deb"

echo "=== Construindo pacote .deb para Cleanux v${VERSION} ==="

# 1. Limpa diretório de build anterior
rm -rf "${SCRIPT_DIR}/build"
mkdir -p "${BUILD_DIR}/DEBIAN"
mkdir -p "${BUILD_DIR}/usr/bin"
mkdir -p "${BUILD_DIR}/usr/lib/python3/dist-packages/cleanux"
mkdir -p "${BUILD_DIR}/usr/lib/cleanux/cleanux"
mkdir -p "${BUILD_DIR}/usr/share/applications"
mkdir -p "${BUILD_DIR}/usr/share/icons/hicolor"
chmod 755 "${BUILD_DIR}/DEBIAN"

# 2. Copia arquivos de código-fonte excluindo caches
find "${SCRIPT_DIR}/cleanux" -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find "${SCRIPT_DIR}/cleanux" -name "*.pyc" -delete 2>/dev/null || true

cp -r "${SCRIPT_DIR}/cleanux"/* "${BUILD_DIR}/usr/lib/python3/dist-packages/cleanux/"
cp -r "${SCRIPT_DIR}/cleanux"/* "${BUILD_DIR}/usr/lib/cleanux/cleanux/"

# 3. Cria executável do sistema /usr/bin/cleanux
cat << 'EOF' > "${BUILD_DIR}/usr/bin/cleanux"
#!/usr/bin/env python3
import sys
import os

# Adiciona bibliotecas do Cleanux ao path
for p in ["/usr/lib/cleanux", "/usr/lib/python3/dist-packages"]:
    if os.path.exists(p) and p not in sys.path:
        sys.path.insert(0, p)

try:
    from cleanux.app import main
    sys.exit(main())
except Exception as e:
    print(f"Erro ao iniciar o Cleanux: {e}", file=sys.stderr)
    sys.exit(1)
EOF
chmod 755 "${BUILD_DIR}/usr/bin/cleanux"

# 4. Copia atalho .desktop
cp "${SCRIPT_DIR}/data/io.github.cleanux.desktop" "${BUILD_DIR}/usr/share/applications/io.github.cleanux.desktop"
chmod 644 "${BUILD_DIR}/usr/share/applications/io.github.cleanux.desktop"

# 5. Copia ícones
cp -r "${SCRIPT_DIR}/data/icons/hicolor"/* "${BUILD_DIR}/usr/share/icons/hicolor/"

# Ajusta permissões
find "${BUILD_DIR}/usr" -type d -exec chmod 755 {} +
find "${BUILD_DIR}/usr" -type f -exec chmod 644 {} +
chmod 755 "${BUILD_DIR}/usr/bin/cleanux"

# 6. Cria arquivo DEBIAN/control
cat << EOF > "${BUILD_DIR}/DEBIAN/control"
Package: ${PACKAGE_NAME}
Version: ${VERSION}
Section: utils
Priority: optional
Architecture: ${ARCH}
Maintainer: Luiz <cleanux@localhost>
Depends: python3, python3-gi, gir1.2-gtk-4.0, gir1.2-adw-1
Installed-Size: 150
Description: Limpador de Sistema e Analisador de Disco Nativo para Linux
 Cleanux e um aplicativo moderno com interface GTK 4 e Libadwaita
 para analise de armazenamento em disco, deteccao dos 10 maiores
 aplicativos instalados e limpeza segura de logs e pacotes nao utilizados.
EOF
chmod 644 "${BUILD_DIR}/DEBIAN/control"

# 7. Cria scripts pós-instalação e pós-remoção
cat << 'EOF' > "${BUILD_DIR}/DEBIAN/postinst"
#!/bin/sh
set -e
if command -v update-desktop-database > /dev/null 2>&1; then
    update-desktop-database -q /usr/share/applications || true
fi
if command -v gtk-update-icon-cache > /dev/null 2>&1; then
    gtk-update-icon-cache -q -t -f /usr/share/icons/hicolor || true
fi
exit 0
EOF
chmod 755 "${BUILD_DIR}/DEBIAN/postinst"

cat << 'EOF' > "${BUILD_DIR}/DEBIAN/postrm"
#!/bin/sh
set -e
if command -v update-desktop-database > /dev/null 2>&1; then
    update-desktop-database -q /usr/share/applications || true
fi
if command -v gtk-update-icon-cache > /dev/null 2>&1; then
    gtk-update-icon-cache -q -t -f /usr/share/icons/hicolor || true
fi
exit 0
EOF
chmod 755 "${BUILD_DIR}/DEBIAN/postrm"

# 8. Empacota com dpkg-deb
echo "Gerando pacote com dpkg-deb..."
dpkg-deb --build --root-owner-group "${BUILD_DIR}" "${OUTPUT_DEB}"

echo "Pacote .deb gerado com sucesso em: ${OUTPUT_DEB}"
ls -lh "${OUTPUT_DEB}"
