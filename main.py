# Widevine CDM Grabber
# Copyright (c) 2026 David López Borrego
# Licencia MIT
"""Descarga el paquete oficial de Google Chrome para Linux y extrae libwidevinecdm.so."""

from __future__ import annotations

import gzip
import hashlib
import io
import lzma
import os
import shutil
import sys
import tarfile
import threading
import urllib.request
import tkinter as tk
from tkinter import messagebox, ttk
from pathlib import Path

APP_NAME = "Widevine CDM Grabber"
VERSION = "1.0"

ROOT = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent
OUTPUTS = ROOT / "outputs"
DEB_NAME = "google-chrome-stable_current_amd64.deb"
DEB_PATH = ROOT / DEB_NAME
CHROME_DEB_URL = f"https://dl.google.com/linux/direct/{DEB_NAME}"
AR_MAGIC = b"!<arch>\n"


def ensure_dirs() -> None:
    OUTPUTS.mkdir(parents=True, exist_ok=True)


# ----------------------------------------------------------------------
# Lectura y extracción de DEB (ar + tar.{xz,gz,zst})
# ----------------------------------------------------------------------
def read_ar_members(path: Path) -> dict[str, bytes]:
    """Lee todos los miembros de un archivo ar (formato DEB)."""
    members: dict[str, bytes] = {}
    with path.open("rb") as f:
        if f.read(8) != AR_MAGIC:
            raise ValueError("El archivo no es un DEB/ar válido.")
        long_names = b""
        while True:
            header = f.read(60)
            if len(header) < 60:
                break
            raw_name = header[0:16].decode("ascii", errors="replace").strip()
            size_field = header[48:58].decode("ascii", errors="replace").strip()
            try:
                size = int(size_field)
            except ValueError:
                break
            data = f.read(size)
            if raw_name == "//":
                long_names = data
            elif raw_name.startswith("/") and raw_name[1:].isdigit():
                offset = int(raw_name[1:])
                end = long_names.find(b"/\n", offset)
                if end == -1:
                    name = long_names[offset:].decode("ascii", errors="replace").rstrip("/")
                else:
                    name = long_names[offset:end].decode("ascii", errors="replace")
            else:
                name = raw_name.rstrip("/")
            if name:
                members[name] = data
            if size % 2:
                f.read(1)
    return members


def decompress_member(key: str, data: bytes) -> bytes:
    if key.endswith(".xz"):
        return lzma.decompress(data)
    if key.endswith(".gz"):
        return gzip.decompress(data)
    if key.endswith(".zst"):
        try:
            import zstandard  # type: ignore
        except ImportError:
            raise RuntimeError(
                "Este DEB usa compresión zstd. Instálala con: pip install zstandard"
            )
        return zstandard.ZstdDecompressor().decompress(data, max_output_size=800 * 1024 * 1024)
    raise RuntimeError(f"Formato de compresión no soportado: {key}")


def get_chrome_version(deb_path: Path) -> str | None:
    try:
        members = read_ar_members(deb_path)
        control_key = next((k for k in members if k.startswith("control.tar")), None)
        if not control_key:
            return None
        data = decompress_member(control_key, members[control_key])
        with tarfile.open(fileobj=io.BytesIO(data)) as tar:
            for m in tar.getmembers():
                if m.name.lstrip("./") == "control":
                    f = tar.extractfile(m)
                    if f:
                        for line in f.read().decode("utf-8", errors="replace").splitlines():
                            if line.startswith("Version:"):
                                return line.split(":", 1)[1].strip()
    except Exception:
        return None
    return None


def extract_so(deb_path: Path, output_dir: Path, log) -> tuple[Path, str]:
    log(f"Leyendo {deb_path.name}…")
    members = read_ar_members(deb_path)

    data_key = next((k for k in members if k.startswith("data.tar")), None)
    if not data_key:
        raise RuntimeError("No se encontró data.tar en el DEB.")

    log(f"Descomprimiendo {data_key}…")
    data = decompress_member(data_key, members[data_key])
    log(f"Buscando libwidevinecdm.so en {len(data) // (1024 * 1024)} MB…")

    best_member = None
    best_score = -1
    with tarfile.open(fileobj=io.BytesIO(data)) as tar:
        for m in tar.getmembers():
            if m.name.endswith("libwidevinecdm.so"):
                score = 0
                if "linux_x64" in m.name:
                    score += 10
                if "_platform_specific" in m.name:
                    score += 5
                if score > best_score:
                    best_score = score
                    best_member = m

        if best_member is None:
            raise RuntimeError("No se encontró libwidevinecdm.so en el paquete.")

        src = tar.extractfile(best_member)
        if src is None:
            raise RuntimeError("No se pudo leer el archivo desde el tar.")

        out_path = output_dir / "libwidevinecdm.so"
        with out_path.open("wb") as out:
            shutil.copyfileobj(src, out)
        src.close()

    digest = hashlib.sha256(out_path.read_bytes()).hexdigest()
    size_kb = out_path.stat().st_size // 1024
    log(f"Extraído: {out_path.name} ({size_kb} KB)")
    log(f"Ruta original: {best_member.name}")
    log(f"SHA-256: {digest}")
    return out_path, digest


# ----------------------------------------------------------------------
# Interfaz gráfica
# ----------------------------------------------------------------------
class WidevineGrabber:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.busy = False
        self._closing = False
        self.root.title(f"{APP_NAME} v{VERSION}")
        self.root.geometry("580x480")
        self.root.resizable(False, False)
        style = ttk.Style()
        try:
            style.theme_use("vista")
        except tk.TclError:
            pass
        style.configure("Title.TLabel", font=("Segoe UI", 20, "bold"))
        style.configure("Action.TButton", font=("Segoe UI", 12, "bold"), padding=(20, 14))
        self._build()

    def _build(self) -> None:
        outer = ttk.Frame(self.root, padding=24)
        outer.pack(fill="both", expand=True)

        header = ttk.Frame(outer)
        header.pack(fill="x")
        ttk.Label(header, text="Widevine CDM Grabber", style="Title.TLabel").pack(side="left", anchor="w")

        buttons = ttk.Frame(header)
        buttons.pack(side="right", anchor="e")
        self.data_button = ttk.Button(buttons, text="Datos", command=self.open_data_dir)
        self.data_button.pack(side="left", padx=(0, 6))
        self.delete_button = ttk.Button(buttons, text="Borrar", command=self.delete_all)
        self.delete_button.pack(side="left")

        ttk.Label(
            outer,
            text="Descarga el paquete oficial de Chrome para Linux y extrae libwidevinecdm.so.",
            foreground="#5b6573",
            wraplength=520,
        ).pack(anchor="w", pady=(3, 6))
        ttk.Label(
            outer,
            text=f"Archivos en: {ROOT}",
            foreground="#8a94a3",
            font=("Segoe UI", 8),
            wraplength=520,
        ).pack(anchor="w", pady=(0, 20))

        self.download_button = ttk.Button(
            outer, text="Descargar DEB de Chrome",
            style="Action.TButton", command=self.download_deb,
        )
        self.download_button.pack(fill="x", pady=(0, 8))
        self.extract_button = ttk.Button(
            outer, text="Extraer libwidevinecdm.so",
            style="Action.TButton", command=self.extract,
        )
        self.extract_button.pack(fill="x")

        self.status = ttk.Label(
            outer,
            text="Pulsa Descargar para bajar el DEB, luego Extraer para obtener el archivo.",
            wraplength=520,
        )
        self.status.pack(anchor="w", pady=(18, 8))
        self.log_view = tk.Text(
            outer, height=8, wrap="word", state="disabled",
            font=("Consolas", 9), background="#f4f6f8",
        )
        self.log_view.pack(fill="both", expand=True)

    # -- helpers ---------------------------------------------------------
    def open_data_dir(self) -> None:
        try:
            os.startfile(str(OUTPUTS))  # type: ignore[attr-defined]
        except Exception as exc:
            messagebox.showerror(APP_NAME, f"No se pudo abrir {OUTPUTS}:\n{exc}", parent=self.root)

    def log(self, message: str) -> None:
        if self._closing:
            return
        try:
            self.root.after(0, self._append_log, message)
        except tk.TclError:
            pass

    def _append_log(self, message: str) -> None:
        if self._closing:
            return
        self.log_view.configure(state="normal")
        self.log_view.insert("end", message.rstrip() + "\n")
        self.log_view.see("end")
        self.log_view.configure(state="disabled")

    def set_status(self, message: str) -> None:
        if self._closing:
            return
        try:
            self.root.after(0, lambda: self.status.configure(text=message) if not self._closing else None)
        except tk.TclError:
            pass

    def task(self, label: str, work, done=None) -> None:
        if self.busy:
            return
        self.busy = True
        for btn in (self.download_button, self.extract_button, self.delete_button, self.data_button):
            btn.configure(state="disabled")
        self.set_status(label)

        def runner() -> None:
            result = error = None
            try:
                result = work()
            except Exception as exc:
                error = str(exc)
                self.log(f"ERROR: {error}")

            def finish() -> None:
                if self._closing:
                    return
                self.busy = False
                for btn in (self.download_button, self.extract_button, self.delete_button, self.data_button):
                    btn.configure(state="normal")
                if error:
                    self.set_status("La operación terminó con un error.")
                    messagebox.showerror(APP_NAME, error, parent=self.root)
                else:
                    self.set_status("Listo")
                    if done:
                        done(result)

            if self._closing:
                return
            try:
                self.root.after(0, finish)
            except tk.TclError:
                pass

        threading.Thread(target=runner, daemon=True).start()

    # -- acciones --------------------------------------------------------
    def download_deb(self) -> None:
        if DEB_PATH.exists():
            if not messagebox.askyesno(
                APP_NAME,
                f"Ya existe {DEB_PATH.name}.\n¿Quieres volver a descargarlo?",
                parent=self.root,
            ):
                return
        self.task("Descargando DEB oficial de Chrome…", self._download_work, self._downloaded)

    def _download_work(self) -> Path:
        ensure_dirs()
        request = urllib.request.Request(CHROME_DEB_URL, headers={"User-Agent": APP_NAME})
        tmp_path = DEB_PATH.with_suffix(".deb.part")
        log_every = 10 * 1024 * 1024
        next_log = log_every
        with urllib.request.urlopen(request, timeout=300) as response:
            total = int(response.headers.get("Content-Length", 0) or 0)
            downloaded = 0
            with tmp_path.open("wb") as out:
                while True:
                    chunk = response.read(1024 * 1024)
                    if not chunk:
                        break
                    out.write(chunk)
                    downloaded += len(chunk)
                    if downloaded >= next_log:
                        if total:
                            pct = downloaded * 100 // total
                            self.log(f"  Descargando: {pct}%  ({downloaded // 1024 // 1024} MB / {total // 1024 // 1024} MB)")
                        else:
                            self.log(f"  Descargando: {downloaded // 1024 // 1024} MB")
                        next_log += log_every

        if tmp_path.stat().st_size == 0:
            tmp_path.unlink(missing_ok=True)
            raise RuntimeError("La descarga produjo un archivo vacío.")

        with tmp_path.open("rb") as f:
            if f.read(8) != AR_MAGIC:
                tmp_path.unlink(missing_ok=True)
                raise RuntimeError("El archivo descargado no es un DEB válido.")

        if DEB_PATH.exists():
            DEB_PATH.unlink()
        tmp_path.rename(DEB_PATH)
        return DEB_PATH

    def _downloaded(self, path: Path) -> None:
        size_mb = path.stat().st_size / (1024 * 1024)
        version = get_chrome_version(path)
        msg = f"DEB descargado: {path.name} ({size_mb:.1f} MB)"
        if version:
            msg += f"  ·  Chrome {version}"
        self.log(msg)
        self.set_status(msg)

    def extract(self) -> None:
        if not DEB_PATH.exists():
            messagebox.showinfo(
                APP_NAME,
                f"Primero descarga el DEB con el botón Descargar.\n\nFalta: {DEB_PATH}",
                parent=self.root,
            )
            return
        self.task("Extrayendo libwidevinecdm.so…", self._extract_work, self._extracted)

    def _extract_work(self) -> tuple[Path, str]:
        ensure_dirs()
        return extract_so(DEB_PATH, OUTPUTS, self.log)

    def _extracted(self, result: tuple[Path, str]) -> None:
        path, digest = result
        msg = f"libwidevinecdm.so guardado en:\n{path}\n\nSHA-256: {digest[:24]}…"
        self.set_status(f"Extraído: {path.name}")
        messagebox.showinfo(APP_NAME, msg, parent=self.root)

    def delete_all(self) -> None:
        if not DEB_PATH.exists():
            messagebox.showinfo(
                APP_NAME,
                "No hay archivos temporales que borrar.",
                parent=self.root,
            )
            return
        if not messagebox.askyesno(
            APP_NAME,
            "¿Borrar los archivos temporales descargados?\n\n"
            "Los archivos de outputs/ se conservan.",
            parent=self.root,
        ):
            return
        self.task("Borrando archivos temporales…", self._delete_work,
                  lambda _: self.set_status("Archivos temporales borrados."))

    def _delete_work(self) -> None:
        if DEB_PATH.exists():
            DEB_PATH.unlink()
            self.log("Archivos temporales eliminados.")


def main() -> None:
    ensure_dirs()
    root = tk.Tk()
    
    app = WidevineGrabber(root)

    def on_close() -> None:
        app._closing = True
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_close)
    root.mainloop()


if __name__ == "__main__":
    main()