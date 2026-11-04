"""Скачать Redis connector из выбранного релиза Stream Reactor."""

import io
import json
import pathlib
import tarfile
import urllib.request
import zipfile


VERSION = "10.0.1"
# Dockerfile.connect копирует эти JAR-файлы в образ Kafka Connect.
DEST = pathlib.Path(__file__).parent / "plugins" / "redis"
DEST.mkdir(parents=True, exist_ok=True)

headers = {"User-Agent": "practice01-lab4", "Accept": "application/vnd.github+json"}
# GitHub API сообщает точное имя архива Redis для выбранной версии.
api = f"https://api.github.com/repos/lensesio/stream-reactor/releases/tags/{VERSION}"
with urllib.request.urlopen(urllib.request.Request(api, headers=headers), timeout=30) as response:
    release = json.load(response)
assets = release.get("assets", [])
# Не брать исходники и архивы других коннекторов.
matches = [
    asset for asset in assets
    if "redis" in asset["name"].lower()
    and asset["name"].lower().endswith((".zip", ".tar.gz", ".tgz"))
]
asset = matches[0]
# Скачать найденный архив плагина.
print(f"Downloading {asset['name']} from {asset['browser_download_url']}")
with urllib.request.urlopen(
    urllib.request.Request(asset["browser_download_url"], headers=headers), timeout=180
) as response:
    archive = response.read()

jar_count = 0
# Извлечь только JAR-файлы в отдельную папку для Kafka Connect.
if asset["name"].lower().endswith(".zip"):
    with zipfile.ZipFile(io.BytesIO(archive)) as package:
        for member in package.infolist():
            if member.filename.lower().endswith(".jar") and not member.is_dir():
                (DEST / pathlib.Path(member.filename).name).write_bytes(package.read(member))
                jar_count += 1
else:
    with tarfile.open(fileobj=io.BytesIO(archive), mode="r:gz") as package:
        for member in package.getmembers():
            if member.name.lower().endswith(".jar") and member.isfile():
                source = package.extractfile(member)
                if source is not None:
                    (DEST / pathlib.Path(member.name).name).write_bytes(source.read())
                    jar_count += 1
if not jar_count:
    raise SystemExit(f"No JAR files found in {asset['name']}")
print(f"Installed {jar_count} JAR files into {DEST}")
