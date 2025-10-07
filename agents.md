# Codex — **agents.md**

> **Amaç:** iCloud hesabına oturum açıp **mevcut iOS cihaz yedeklerini** (iCloud Backups) *listeleyen*, kullanıcıya seçim yaptırıp **bilgisayara güvenli şekilde indiren** bir yardımcı programı, çok‑ajanlı (multi‑agent) mimariyle üretmek.

> **Kritik Not (Gerçekçilik ve Sınırlar):** Apple, **iCloud cihaz yedeklerini indirmek için resmi/genel bir API sunmaz**. iCloud.com ve iCloud for Windows **cihaz yedeği** (MobileBackup) dosyalarını doğrudan vermez; genellikle **yalnızca fotoğraflar, Drive dosyaları, notlar vs.** erişilebilir. Cihaz yedeğini *programatik* indirme, **özel/ters‑mühendislik** edilmiş uç noktalar ya da 3P araçlarla yapılır ve **hesap güvenliği ile kullanım şartlarına** takılabilir.
>
> **Güvenli ve uygulanabilir yaklaşımlar:**
>
> 1. **USB üstünden yerel yedek** (Finder/iTunes) — Resmi, stabil. (iCloud’dan değil; ama cihaz yedeğini indirilebilir hale getirir.)
> 2. **iCloud for Windows** + **MobileBackup klasörü yakalama** — Bazı senaryolarda ".mbdb/.mbdx" eşdeğerleri ve dosya parçaları lokal cache’e gelir; garanti değil.
> 3. **3P/Topluluk projeleri** (örn. *pyicloud* yalnızca Foto/Drive, **cihaz yedeği değil**). Özel API kullanan araçlar **hesap riski** doğurur.
>
> Bu belge, **Ajan tasarımı** ve **akış**ı tanımlar; gerçek indirme yeteneği, seçilen yaklaşımın teknik/etik kısıtlarına bağlıdır.

---

## 0) Hedefler

- iCloud hesabına güvenli kimlik doğrulama (Apple ID, 2FA, SRP/"Trust this browser").
- Kullanıcıya **mevcut yedek(ler)i** ve **cihaz/ tarih** bilgilerini gösterme.
- Seçilen yedeğin **indirilebilir içeriklerini** (mümkünse) **parçalı/kalıcı** (resumable) şekilde indirme.
- **Hash doğrulama**, **şifreli yedek** ise kullanıcı parolası ile **decrypt & verify**.
- İndirilen içeriği **klasör yapısına** yerleştirme, **disk kota/boş alan** kontrolü, **log & rapor**.

## 1) Mimari Genel Bakış (Multi‑Agent)

```
┌─────────────────┐     ┌────────────────────┐     ┌──────────────────────┐
│ UI/Orchestrator │◄──► │  Auth & 2FA Agent  │◄──►│   iCloud API Agent    │
└─────────────────┘     └────────────────────┘     └──────────────────────┘
         │                          │                          │
         ▼                          ▼                          ▼
┌──────────────────────┐   ┌────────────────────┐      ┌───────────────────┐
│ Backup Indexer Agent │   │ Download Manager   │      │ Crypto/Verify     │
└──────────────────────┘   └────────────────────┘      └───────────────────┘
         │                          │                          │
         ▼                          ▼                          ▼
┌───────────────────────┐  ┌──────────────────────┐   ┌─────────────────────┐
│ Storage/Quota Manager │  │ Integrity/Resume Log │   │ Report/Export Agent │
└───────────────────────┘  └──────────────────────┘   └─────────────────────┘
```

### 1.1 Ajanların Sorumlulukları

- **UI/Orchestrator**: Komut satırı/GUI; akışları tetikler, hata/geri kazanım stratejisini yönetir.
- **Auth & 2FA Agent**: Apple ID oturum, 2FA (SMS/Push/Kod), "Trust this browser" token’larının güvenli saklanması.
- **iCloud API Agent**: Seçilen yönteme göre iCloud kaynaklarını listeler (resmi erişilebilenler: Foto/Drive vs.); *cihaz yedeği* için özel uç noktalar seçilecekse **policy‑gate** uygular.
- **Backup Indexer Agent**: Ulaşılabilen yedeklerin **meta verisini çıkarır** (cihaz adı, iOS sürümü, tarih, yaklaşık boyut). *Not:* Bu, yönteme bağlı olarak **tam görünmeyebilir**.
- **Download Manager**: Parçalı indirme (range), **retries**, **checksum**, **resume**. Hız/kota/lokal disk yönetimi ile entegre.
- **Crypto/Verify**: Şifreli yedekler için parola ile **PBKDF**/Keybag çözümü (uygunsa), SHA‑256/xxhash doğrulama.
- **Storage/Quota Manager**: Boş alan, hedef dizin, dosya sistemi sınırları (NTFS uzun path, case sensitivity vs.).
- **Integrity/Resume Log**: JSONL/SQLite; hangi parçalar indi, hash’ler, son durum, tekrar başlatma.
- **Report/Export Agent**: Özet rapor (HTML/Markdown/JSON), log paketleme, hatalı parça listesi.

## 2) Politikalar ve Güvenlik

- **Kullanım Şartları Uyum**: Apple TOS ihlali riskine karşı **varsayılan olarak yalnızca resmi destekli akışlar** (*USB local backup* ya da iCloud içindeki **resmi erişilebilen veri sınıfları**) etkin.
- **Policy Gate**: Kullanıcı özel API modunu açmadan, cihaz yedeklerine erişmeye çalışılmaz. Açılırsa uyarı metni ve risk onayı gerekir.
- **Gizli Bilgiler**: `APPLE_ID`, `APP_SPECIFIC_PASSWORD` (gerekirse), 2FA tokenları, keychain benzeri kasada **OS‑safe** saklanır (Windows DPAPI, macOS Keychain).
- **Kayıtlar**: Hassas veriler log’a maskelenir. PII redaksiyon kuralları.

## 3) Kurulum / Ortam

- **OS**: Windows 10/11, macOS 12+ (USB local backup için macOS daha doğal).
- **Bağımlılıklar**:
  - Resmi akış: `iTunes/Finder` (USB backup), `Apple Mobile Device Support`.
  - iCloud içeriği (Foto/Drive) için: `iCloud for Windows` / macOS iCloud.
  - Opsiyonel: `pyicloud` (yalnızca Foto/Drive) \* cihaz yedeği değil.
  - Hash: `xxhash`, `openssl`/`cryptography`.
  - CLI/UI: `Python 3.11+`, `rich`/`textual` (CLI) veya `PySide6` (GUI).

## 4) Yapılandırma (ENV)

```
ICLOUD_REGION=default
DOWNLOAD_DIR=./outputs/icloud_backups
CHUNK_SIZE_MB=16
MAX_PARALLEL=4
HASH_ALGO=sha256
ALLOW_PRIVATE_ENDPOINTS=false
LOG_LEVEL=INFO
```

Mac/Win için gizli bilgiler **OS kasasında** tutulur; `.env` içine yazılmaz.

## 5) Kullanım Akışı

1. **Giriş**: UI → Apple ID girilir. Ajan 2FA isteğini yakalar.
2. **2FA**: Kod/Push doğrulanır, "Trust" token alınır ve kasaya yazılır.
3. **Yedek Keşfi**:
   - **Resmi**: USB bağla → yerel backup listesi çıkar → seç → kopyala/doğrula.
   - **iCloud İçeriği (resmi)**: Foto/Drive klasörleri listelenir ve indirilebilir.
   - **Özel (opsiyonel)**: *Policy‑gate* onaylı → iCloud **Device Backups** meta denemesi → dönen listeye göre devam.
4. **Seçim & Plan**: Hedef dizin, tahmini boyut, boş alan → **Quota check**.
5. **İndirme**: Parçalı, tekrar başlatılabilir. Her parça hash’lenir.
6. **Doğrulama**: Toplam hash, opsiyonel decrypt/parse (şifreli yedekse ve bilgi varsa).
7. **Rapor**: HTML/MD/JSON özet + CSV log.

## 6) Komutlar (CLI taslak)

```
# İlk giriş ve trust
codex-icloud auth login --apple-id user@example.com

# USB yerel yedekleri listele
codex-icloud backup list --source usb

# (Opsiyonel, riskli) iCloud cihaz yedekleri listele
codex-icloud backup list --source icloud --allow-private

# Seçileni indir
codex-icloud backup download --id <backup_id> \
  --dest "D:/Backups/iPhone_13_2024-10-01" \
  --resume --verify --report html,json
```

## 7) Ajan Arayüzleri (Pseudo‑API)

```ts
// Auth & 2FA Agent
interface AuthAgent {
  login(appleId: string): Promise<{ requires2FA: boolean }>
  submit2FA(code: string): Promise<{ trusted: boolean, sessionToken: string }>
  loadSession(): Promise<Session | null>
}

// iCloud API Agent (resmi/özel mod)
interface ICloudAgent {
  listPhotos(params): Promise<Item[]>
  listDrive(params): Promise<Item[]>
  // private endpoints (gated)
  listDeviceBackups(): Promise<BackupMeta[]> // may fail if not allowed
  planDownload(backupId: string): Promise<Plan>
  streamPart(plan: Plan, partIdx: number): AsyncIterable<ArrayBuffer>
}

// Download Manager
interface Downloader {
  run(plan: Plan, opts: { parallel: number, chunkMB: number }): Promise<Result>
}

// Crypto/Verify
interface Verifier {
  fileHash(path: string, algo: 'sha256'|'xxh3'): Promise<string>
  verifyPlan(plan: Plan): Promise<Report>
  decryptIfNeeded(plan: Plan, passphrase?: string): Promise<void>
}
```

## 8) Hata Yönetimi & Geri Kazanım

- **2FA süresi doldu** → tekrar kod iste, rate‑limit koruması.
- **Quota yetersiz** → indirme başlamadan uyarı (threshold: %15 boş alan kuralı).
- **Kısmi dosya** → checksum uyuşmazlığı → ilgili parçayı tekrar indir.
- **Bağlantı koptu** → exponential backoff, en fazla N tekrar.
- **Özel uç nokta kapandı** → kullanıcıya açıklama, resmi akışa düş.

## 9) Test Stratejisi

- **Dry‑run**: Sadece listeleme ve plan oluşturma; indirme yok.
- **Simülasyon**: Sahte 2FA, sahte yedek listesi ile akış testi.
- **Gerçek cihaz (USB)**: Küçük bir yerel yedek üstünde doğrulama.
- **Büyük dosya**: Parçalı indirme ve resume testi (ağ kesintisi enjekte et).
- **Hash/Decrypt**: Test vektörleri ile doğrulama.

## 10) Yol Haritası

- v0.1: Auth + USB yerel yedek liste/klon + rapor.
- v0.2: iCloud Foto/Drive indirici (resmi erişim) + resume.
- v0.3: (Gated) iCloud Device Backup meta keşfi, resmileşmeyen uç nokta kullanımı *opsiyonel*.
- v0.4: Şifreli yedek parse/decrypt (kullanıcı parolasıyla), derin doğrulama.
- v1.0: GUI, log/rapor iyileştirmeleri, çoklu cihaz desteği.

## 11) Uyumluluk & Etik

- Apple TOS ve yerel mevzuata uygunluk. Hesap güvenliğini tehlikeye atan yöntemler **varsayılan olarak kapalı**.
- Kullanıcı verisi **uçtan uca şifreli** saklanmalı, minimum yetki prensibi.

## 12) Sık Sorulanlar

- **Gerçekten iCloud cihaz yedeklerini indirebilir miyim?**
  - Resmi şekilde **doğrudan** değil. Yerel USB yedeği her zaman mümkün. iCloud tarafında ise resmi olarak **Foto/Drive** erişimi var. Cihaz yedeği için kullanılan özel uç noktalar kararsız/riskli olabilir.
- **Neden 2FA bu kadar önemli?**
  - Apple ekosistemi 2FA’yı zorunlu tutar; oturumun sürekliliği ve "trusted device" akışı bu yüzden kritik.

---

### Ekler

- **Rapor Formatı (JSON):** `start/end`, `device`, `backup_id`, `files_ok/failed`, `hashes`, `duration`, `retries`.
- **Log Formatı (JSONL):** her adım için `ts`, `level`, `event`, `ctx`.
- **Dizin Düzeni:**

```
outputs/icloud_backups/
  ├─ <device_name>_<date>/
  │   ├─ manifest.json
  │   ├─ files/...
  │   └─ hashes/
  └─ reports/
      ├─ session_<ts>.json
      └─ session_<ts>.html
```

