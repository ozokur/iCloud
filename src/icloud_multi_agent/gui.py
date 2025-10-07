"""Simple Tkinter GUI for interacting with the mock iCloud helper."""
from __future__ import annotations

import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk
from typing import Optional

from .cli import DEFAULT_DATA_FILE, build_orchestrator
from .config import SETTINGS


class BackupGUI:
    """Graphical interface that wraps the orchestrator workflow."""

    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title("Mock iCloud Backup Helper")
        self.root.geometry("720x520")

        self.apple_id_var = tk.StringVar()
        self.code_var = tk.StringVar()
        self.allow_private_var = tk.BooleanVar(value=SETTINGS.allow_private_endpoints)
        self.data_file_var = tk.StringVar(value=str(DEFAULT_DATA_FILE))
        self.status_var = tk.StringVar(value="Hazır.")

        self._backups: list[tuple[str, str, str, int]] = []
        self._orchestrator = None
        self._cached_allow_private: Optional[bool] = None
        self._cached_data_file: Optional[Path] = None
        self._lock = threading.Lock()

        self._build_ui()

    # ------------------------------------------------------------------
    # UI construction helpers
    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        padding = {"padx": 10, "pady": 5}

        config_frame = ttk.LabelFrame(self.root, text="Ayarlar")
        config_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(config_frame, text="Veri dosyası:").grid(row=0, column=0, sticky=tk.W, **padding)
        data_entry = ttk.Entry(config_frame, textvariable=self.data_file_var, width=60)
        data_entry.grid(row=0, column=1, sticky=tk.W, **padding)
        ttk.Button(config_frame, text="Seç...", command=self._select_data_file).grid(row=0, column=2, **padding)
        ttk.Checkbutton(
            config_frame,
            text="Özel uç noktalara izin ver (riskli)",
            variable=self.allow_private_var,
            command=self._invalidate_orchestrator,
        ).grid(row=1, column=1, sticky=tk.W, **padding)

        config_frame.columnconfigure(1, weight=1)

        auth_frame = ttk.LabelFrame(self.root, text="Kimlik Doğrulama")
        auth_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Label(auth_frame, text="Apple ID:").grid(row=0, column=0, sticky=tk.W, **padding)
        ttk.Entry(auth_frame, textvariable=self.apple_id_var, width=30).grid(row=0, column=1, **padding)
        ttk.Label(auth_frame, text="2FA Kodu:").grid(row=0, column=2, sticky=tk.W, **padding)
        ttk.Entry(auth_frame, textvariable=self.code_var, width=10).grid(row=0, column=3, **padding)
        ttk.Button(auth_frame, text="Giriş Yap", command=self.on_login).grid(row=0, column=4, **padding)

        auth_frame.columnconfigure(1, weight=1)

        backup_frame = ttk.LabelFrame(self.root, text="Yedekler")
        backup_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        list_container = ttk.Frame(backup_frame)
        list_container.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.backup_list = tk.Listbox(list_container, height=10)
        scrollbar = ttk.Scrollbar(list_container, orient=tk.VERTICAL, command=self.backup_list.yview)
        self.backup_list.configure(yscrollcommand=scrollbar.set)
        self.backup_list.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        button_frame = ttk.Frame(backup_frame)
        button_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Button(button_frame, text="Yedekleri Yenile", command=self.on_refresh_backups).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Seçili Yedeği İndir", command=self.on_download_backup).pack(side=tk.LEFT, padx=5)

        status_frame = ttk.Frame(self.root)
        status_frame.pack(fill=tk.X, padx=10, pady=5)
        ttk.Label(status_frame, textvariable=self.status_var).pack(anchor=tk.W)

        log_frame = ttk.LabelFrame(self.root, text="Günlük")
        log_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        self.log_text = tk.Text(log_frame, height=10, state="disabled")
        self.log_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    # ------------------------------------------------------------------
    # Orchestrator helpers
    # ------------------------------------------------------------------
    def _select_data_file(self) -> None:
        selection = filedialog.askopenfilename(
            title="Mock verisini seç",
            initialdir=str(Path(self.data_file_var.get()).expanduser().parent),
            filetypes=[("JSON", "*.json"), ("Tümü", "*.*")],
        )
        if selection:
            self.data_file_var.set(selection)
            self._invalidate_orchestrator()

    def _invalidate_orchestrator(self) -> None:
        with self._lock:
            self._orchestrator = None
            self._cached_allow_private = None
            self._cached_data_file = None
        self.log("Yapılandırma değişti, ajanlar yeniden oluşturulacak.")

    def _get_orchestrator(self):
        allow_private = self.allow_private_var.get()
        data_file = Path(self.data_file_var.get()).expanduser()
        with self._lock:
            needs_rebuild = (
                self._orchestrator is None
                or allow_private != self._cached_allow_private
                or data_file != self._cached_data_file
            )
            if needs_rebuild:
                self.log("Ajanlar hazırlanıyor...")
                self._orchestrator = build_orchestrator(allow_private=allow_private, data_file=data_file)
                self._cached_allow_private = allow_private
                self._cached_data_file = data_file
        return self._orchestrator

    # ------------------------------------------------------------------
    # Utility methods
    # ------------------------------------------------------------------
    def log(self, message: str) -> None:
        def append() -> None:
            self.log_text.configure(state="normal")
            self.log_text.insert("end", message + "\n")
            self.log_text.see("end")
            self.log_text.configure(state="disabled")
            self.status_var.set(message)

        self.root.after(0, append)

    def handle_error(self, error: Exception) -> None:
        self.log(f"Hata: {error}")
        messagebox.showerror("Hata", str(error))

    def run_async(self, worker, on_success=None) -> None:
        def target() -> None:
            try:
                result = worker()
            except Exception as exc:  # noqa: BLE001 - kullanıcıya hata gösterilecek
                self.root.after(0, lambda: self.handle_error(exc))
                return
            if on_success:
                self.root.after(0, lambda: on_success(result))

        threading.Thread(target=target, daemon=True).start()

    @staticmethod
    def _format_size(num_bytes: int) -> str:
        step = 1024.0
        units = ["B", "KB", "MB", "GB", "TB"]
        value = float(num_bytes)
        for unit in units:
            if value < step:
                return f"{value:.1f} {unit}" if unit != "B" else f"{int(value)} {unit}"
            value /= step
        return f"{value:.1f} PB"

    def _update_backup_list(self, backups: list[tuple[str, str, str, int]]) -> None:
        self._backups = backups
        self.backup_list.delete(0, tk.END)
        if not backups:
            self.backup_list.insert(tk.END, "Yedek bulunamadı")
            self.status_var.set("Yedek bulunamadı")
            return
        for identifier, device, created_at, approx_size in backups:
            human_size = self._format_size(approx_size)
            display = f"{device} · {created_at} · {human_size} · ID: {identifier}"
            self.backup_list.insert(tk.END, display)
        self.status_var.set(f"{len(backups)} yedek listelendi")

    # ------------------------------------------------------------------
    # Command callbacks
    # ------------------------------------------------------------------
    def on_login(self) -> None:
        apple_id = self.apple_id_var.get().strip()
        if not apple_id:
            messagebox.showwarning("Eksik bilgi", "Apple ID girin")
            return
        code = self.code_var.get().strip()
        if not code:
            code = simpledialog.askstring("2FA", "2FA kodunu girin:", parent=self.root)
            if not code:
                return

        def worker():
            orchestrator = self._get_orchestrator()
            return orchestrator.ensure_session(apple_id=apple_id, two_factor_code=code)

        def on_success(session):
            self.log(f"{session.apple_id} için güvenilen oturum oluşturuldu.")
            messagebox.showinfo("Başarılı", f"Oturum belirteci: {session.session_token}")

        self.run_async(worker, on_success)

    def on_refresh_backups(self) -> None:
        def worker():
            orchestrator = self._get_orchestrator()
            return orchestrator.list_backups()

        def on_success(backups):
            self.log("Yedek listesi güncellendi.")
            self._update_backup_list(backups)

        self.run_async(worker, on_success)

    def on_download_backup(self) -> None:
        if not self._backups:
            messagebox.showwarning("Yedek yok", "Önce yedek listesini yenileyin")
            return
        selection = self.backup_list.curselection()
        if not selection:
            messagebox.showwarning("Seçim yok", "İndirilecek yedeği seçin")
            return
        backup = self._backups[selection[0]]
        identifier, device_name, created_at, _ = backup

        destination_dir = filedialog.askdirectory(
            title="İndirme klasörünü seç",
            initialdir=str(SETTINGS.download_dir.expanduser()),
        )
        if not destination_dir:
            return
        final_destination = Path(destination_dir) / f"{identifier}"

        def worker():
            orchestrator = self._get_orchestrator()
            plan, result, verification, report = orchestrator.download(identifier, final_destination)
            return plan, result, verification, report

        def on_success(result_tuple):
            plan, result, verification, report = result_tuple
            message = (
                f"{device_name} ({created_at}) yedeği {final_destination} klasörüne indirildi. "
                f"{result.downloaded_files}/{plan.total_files} dosya, durum: "
                f"{'OK' if verification.ok else 'HATALI'}"
            )
            self.log(message)
            messagebox.showinfo("İndirme tamamlandı", f"Rapor: {report}")

        self.run_async(worker, on_success)

    # ------------------------------------------------------------------
    def run(self) -> None:
        self.root.mainloop()


def main() -> int:
    app = BackupGUI()
    app.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
