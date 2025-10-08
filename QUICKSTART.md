# 🚀 Hızlı Başlangıç

Bu kılavuz, iCloud backup helper'ı **5 dakikada** çalıştırmanıza yardımcı olacak.

## macOS Kullanıcıları (En Kolay!)

### 1. Launcher'ı Çalıştırın
```bash
# Terminal'den:
cd /path/to/iCloud/Adsız
./macos-launcher.command

# Veya Finder'dan:
# macos-launcher.command dosyasına çift tıklayın
```

İlk çalıştırmada 30-60 saniye sürebilir (bağımlılıklar indiriliyor).

### 2. GUI'de Giriş Yapın
1. ✅ **"Özel uç noktalara izin ver"** kutusunu işaretleyin (zaten işaretli olmalı)
2. 📧 Apple ID'nizi girin
3. 🔑 Parolanızı girin ve **"Gönder"**'e tıklayın
4. 📱 iPhone/iPad'inizde beliren 6 haneli kodu girin
5. ✅ **"2FA Doğrula"** butonuna tıklayın

### 3. Backup'larınızı Görün
✨ Kimlik doğrulama başarılı olduğunda backup listesi **otomatik** yüklenecek!

### 4. Backup İndirin (Opsiyonel)
1. Listeden bir backup seçin
2. **"Seçili Yedeği İndir"** butonuna tıklayın
3. İndirme klasörünü seçin
4. Bekleyin... ☕

---

## Tüm Platformlar (CLI)

### 1. Python ve Bağımlılıkları Yükleyin
```bash
# Python 3.11+ gerekli
python3 --version

# Virtual environment oluşturun (önerilen)
python3 -m venv .venv
source .venv/bin/activate  # Linux/macOS
# veya
.venv\Scripts\activate  # Windows

# Bağımlılıkları yükleyin
pip install -e .
```

### 2. Giriş Yapın
```bash
python -m icloud_multi_agent.cli --allow-private auth-login \
  --apple-id sizin@email.com
```

Terminal parolanızı ve 2FA kodunuzu soracak.

### 3. Backup'ları Listeleyin
```bash
python -m icloud_multi_agent.cli --allow-private backup-list \
  --apple-id sizin@email.com
```

### 4. Backup İndirin
```bash
python -m icloud_multi_agent.cli --allow-private backup-download \
  --id <BACKUP_ID> \
  --dest ./my-backups \
  --apple-id sizin@email.com
```

---

## 🆘 Yardım

### Backup'larımı göremiyorum!
✅ **"Özel uç noktalara izin ver"** seçeneğini aktifleştirdiniz mi?
✅ Apple ID ile giriş yaptınız mı?
✅ 2FA doğrulaması tamamlandı mı?

Daha fazla bilgi için [README.md](README.md)'deki "Sık Karşılaşılan Sorunlar" bölümüne bakın.

### Launcher takılıyor!
İlk çalıştırmada 30-60 saniye sürer. Verbose modda çalıştırın:
```bash
VERBOSE=1 ./macos-launcher.command
```

### Daha fazla yardım
- [README.md](README.md) - Detaylı dokümantasyon
- [agents.md](agents.md) - Mimari ve teknik detaylar
- [CHANGELOG.md](CHANGELOG.md) - Değişiklik geçmişi

---

## ⚠️ Önemli Notlar

1. **Güvenlik:** Özel uç noktalar Apple'ın resmi API'si değildir. Kendi sorumluluğunuzda kullanın.
2. **İndirme sınırlaması:** iCloud backup'larını **listeleyebilir** ama **doğrudan indiremezsiniz**. Sadece USB/Finder yedekleri indirilebilir.
3. **Gizlilik:** Apple ID bilgileriniz sadece iCloud'a bağlanmak için kullanılır, hiçbir yere kaydedilmez (session token hariç).

---

**🎉 Artık hazırsınız!** Backup'larınızı görüntüleyin ve yönetin.

