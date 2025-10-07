# Changelog

All notable changes to this project will be documented in this file.

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
