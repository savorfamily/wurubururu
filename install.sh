#!/bin/bash
# 우르부르르 맥 설치·업데이트
#   curl -fsSL https://raw.githubusercontent.com/savorfamily/wurubururu/main/install.sh | bash
#
# GitHub 최신 릴리스에서 이 맥에 맞는 dmg를 받아 응용 프로그램 폴더에 설치(덮어쓰기)하고 실행합니다.
# curl로 받은 파일에는 macOS의 '인터넷에서 받은 파일' 표시가 붙지 않아 따로 '그래도 열기'를 누를 필요가 없습니다.
set -euo pipefail

REPO="savorfamily/wurubururu"
APP="/Applications/wurubururu.app"

if [ "$(uname -s)" != "Darwin" ]; then
  echo "이 스크립트는 맥 전용입니다. Windows는 릴리스 페이지의 설치 파일을 쓰세요."; exit 1
fi

case "$(uname -m)" in
  arm64) KIND="mac-apple-silicon" ;;
  x86_64)
    if [ "$(sysctl -in sysctl.proc_translated 2>/dev/null || echo 0)" = "1" ]; then KIND="mac-apple-silicon"; else KIND="mac-intel"; fi ;;
  *) echo "알 수 없는 CPU: $(uname -m)"; exit 1 ;;
esac

echo "▶ 최신 버전 찾는 중…"
URL=$(curl -fsSL "https://api.github.com/repos/$REPO/releases/latest" \
  | grep -o '"browser_download_url": *"[^"]*'"$KIND"'\.dmg"' | head -1 | sed 's/.*"\(https[^"]*\)"/\1/')
if [ -z "$URL" ]; then echo "내려받을 파일을 찾지 못했습니다: https://github.com/$REPO/releases"; exit 1; fi
echo "  $(basename "$URL")"

TMP=$(mktemp -d)
MNT="$TMP/mnt"
cleanup() { hdiutil detach "$MNT" -quiet 2>/dev/null || true; rm -rf "$TMP"; }
trap cleanup EXIT

echo "▶ 내려받는 중…"
curl -fL --progress-bar -o "$TMP/app.dmg" "$URL"

echo "▶ 설치하는 중…"
mkdir -p "$MNT"
hdiutil attach "$TMP/app.dmg" -nobrowse -quiet -mountpoint "$MNT"
if [ ! -d "$MNT/wurubururu.app" ]; then echo "dmg 안에 앱이 없습니다"; exit 1; fi

if pgrep -f "wurubururu.app/Contents/MacOS/wurubururu" >/dev/null; then
  echo "  켜져 있는 우르부르르를 끕니다"
  pkill -f "wurubururu.app/Contents/MacOS/wurubururu" || true
  sleep 1
fi

if [ -w /Applications ]; then
  rm -rf "$APP"
  ditto "$MNT/wurubururu.app" "$APP"
else
  echo "  응용 프로그램 폴더에 쓰려면 맥 암호가 필요합니다"
  sudo rm -rf "$APP"
  sudo ditto "$MNT/wurubururu.app" "$APP"
fi
xattr -dr com.apple.quarantine "$APP" 2>/dev/null || true

VER=$(defaults read "$APP/Contents/Info.plist" CFBundleShortVersionString 2>/dev/null || echo "?")
echo "▶ 우르부르르 $VER 설치 완료. 실행합니다."
open "$APP"
