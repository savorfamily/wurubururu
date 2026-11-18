"""앱 아이콘 만들기: packaging/build/icon.png, icon.icns(맥), icon.ico(윈도우)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from wurubururu.tray import icon_image  # noqa: E402

out = Path(__file__).resolve().parent / "build"
out.mkdir(exist_ok=True)
img = icon_image(1024)
img.save(out / "icon.png")
img.save(out / "icon.ico", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
try:
    img.save(out / "icon.icns")
except Exception as e:  # ICNS 저장은 일부 환경에서만 지원
    print("icns 생략:", e)
print("아이콘 생성:", sorted(p.name for p in out.iterdir()))
