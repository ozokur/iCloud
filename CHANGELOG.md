# Changelog

All notable changes to this project will be documented in this file.

## [0.3.0] - 2025-10-09
### Added
- `CloudBackupICloudAPI` ile Apple'ın özel yedek listeleme uç noktasına bağlanarak gerçek iCloud cihaz
  yedeklerini GUI ve CLI üzerinden gösterme desteği.
- `backup-list`, `backup-plan` ve `backup-download` komutlarına Apple ID/şifre/2FA parametreleri eklenerek
  oturum yenilemesinin tek adımda yapılabilmesi.

### Changed
- README güncellendi; iCloud bulut yedeklerinin nasıl listelendiği ve neden indirilemediği açıklığa kavuşturuldu.

### Fixed
- MobileSync dizini bulunamadığında mock veriye düşmek yerine bulut listesini önceliklendirerek "iCloud'da yedek yok" algısını ortadan kaldırma.

## [0.2.1] - 2025-10-08
### Fixed
- "Yedekleri listele" isteği politika nedeniyle engellendiğinde CLI ve GUI'de kullanıcıya açık rehberlik sağlayan hata mesajları eklendi.
- Orkestratör artık politika ihlallerini günlükleyip `--allow-private` bayrağı veya GUI'deki kutucuğu etkinleştirme yönünde rehberlik ediyor.

## [0.2.0] - 2025-10-07
### Added
- Gerçek Apple kimlik doğrulamasını sağlayan `icloudpy` tabanlı ajan ve 2FA/2SA kod gönderim desteği.

### Changed
- CLI ve GUI artık mock depolar yerine gerçek iCloud oturum açma akışını kullanıyor; orkestratör anında güvenilir oturumları tanır.

## [0.1.2] - 2024-05-31
### Added
- Mock kimlik doğrulama deposuna yanlış Apple ID/parola girişlerini yakalayan denetimler ve kullanıcıya açık geri bildirimler.
- Başarısız giriş ve 2FA denemeleri için JSONL günlüklemeye detaylı kayıtlar.

### Changed
- GUI hata işleme akışına sahte oturum deposu denetimleri eklendi; yanlış kimlik bilgilerinde durum günlüğe yansıtılır.

## [0.1.1] - 2024-05-30
### Added
- Introduced a two aşamalı (two-step) GUI kimlik doğrulama akışı; Apple ID ve parola girildikten sonra "Gönder" ile 2FA kodu talep edilir ve ayrı bir doğrulama düğmesi ile tamamlanır.
- Başlangıçta 2FA girişini devre dışı bırakıp kod gönderimi sonrasında etkinleştirerek kullanıcı deneyimini iyileştiren durum yönetimi eklendi.

### Changed
- Orchestrator'a giriş başlatma ve 2FA tamamlama yardımcıları eklenerek CLI ve GUI yüzeylerinde tutarlı bir akış sağlandı.

## [0.1.0] - 2024-05-20
- İlk sürüm.
