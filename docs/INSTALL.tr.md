# SheLLM kurulum ve kullanım kılavuzu

SheLLM, yazdığınız bir komut bulunamadığında ya da satıra `#` ile başlayan bir istek yazdığınızda bir dil modelinden **tek bir komut önerisi** alan bir Unix kabuğudur. Öneri ekranda gösterilir ve yalnızca siz onaylarsanız çalışır.

Bu kılavuz İngilizce kılavuzun ([INSTALL.md](../INSTALL.md)) Türkçesidir. SheLLM'in arayüzü varsayılan olarak İngilizcedir; Türkçe arayüz için kurulum sihirbazının ilk sorusunda **Türkçe**'yi seçin (ya da `SHELLM_LANG=tr` tanımlayın). Aşağıdaki örnekler Türkçe arayüzü gösterir.

```text
🎀 sheLLM mkdr yedek
shellm: mkdr: command not found

  ┃ ◆ shellm önerisi
  ┃ mkdir yedek
  ┃
  ┃ [e] çalıştır   [h] geç
```

**Gerekenler**

- Linux (Ubuntu ya da Debian önerilir) veya Windows 10/11 üzerinde WSL
- Barındırılan bir model (Gemini, Claude, OpenAI) için internet bağlantısı ve bir API anahtarı. Ya da bilgisayarınızda çalışan yerel bir model; bu durumda veriler dışarı çıkmaz.

---

## 1. Windows kullanıyorsanız: WSL'yi kurun

SheLLM bir Linux kabuğudur. Windows'ta Microsoft'un Linux alt sistemi WSL içinde çalışır.

1. **Başlat** menüsünde *PowerShell*'e sağ tıklayıp **Yönetici olarak çalıştır**'ı seçin ve şunu yazın:
   ```powershell
   wsl --install -d Ubuntu
   ```
2. Bilgisayarı yeniden başlatın.
3. Başlat menüsünden **Ubuntu**'yu açın ve sizden istenen Linux kullanıcı adını ve parolasını belirleyin.

Bundan sonraki bütün adımlar bu **Ubuntu penceresinde** yapılır. Windows'taki dosyalarınıza Ubuntu içinden `/mnt/c/Users/<Windows kullanıcı adınız>/` yoluyla ulaşabilirsiniz.

## 2. SheLLM'i kurun

İki yol var. Ubuntu/Debian/WSL kullanıyorsanız A yolu en kolayıdır.

### A) Hazır paketle (Ubuntu, Debian, WSL)

Paketi [sürümler sayfasından](https://github.com/sametkaya/shellm/releases) indirip kurun:

```bash
wget https://github.com/sametkaya/shellm/releases/download/v1.0.0/shellm_1.0.0_amd64.deb
sudo apt install ./shellm_1.0.0_amd64.deb
```

Dosyayı Windows'ta tarayıcıyla indirdiyseniz *İndirilenler* klasöründedir; Ubuntu penceresinde:

```bash
cd /mnt/c/Users/<Windows kullanıcı adınız>/Downloads
sudo apt install ./shellm_1.0.0_amd64.deb
```

Gerekli kitaplıklar (readline, python3) paketle birlikte kurulur.

### B) Kaynak koddan (bütün Linux dağıtımları)

```bash
git clone https://github.com/sametkaya/shellm.git
cd shellm
./install.sh
```

Sürümler sayfasındaki `shellm-1.0.0.tar.gz` kaynak arşivi de aynı şekilde kullanılabilir (`tar xzf shellm-1.0.0.tar.gz && cd shellm-1.0.0 && ./install.sh`).

- Betik SheLLM'i yalnızca sizin kullanıcınız için `~/.local/bin/shellm` konumuna kurar ve yönetici yetkisi istemez.
- Derleyici, readline ya da python3 eksikse hangi paketlerin gerektiğini söyler ve onayınızla kurar; bu adım için `sudo` gerekir.
- Bütün kullanıcılara kurmak için: `./install.sh --system`

## 3. İlk açılış: ayar sihirbazı

```bash
shellm
```

İlk açılışta (ya da sonradan istediğinizde `shellm --setup` ile) bir sihirbaz açılır.

**1. adım: arayüz dili.** Sihirbaz önce arayüz dilini sorar: *English* ya da *Türkçe*. Seçiminiz ayar dosyasına kaydedilir.

**2. adım: model.** Ardından hangi modeli kullanacağınızı sorar:

| Seçenek | API anahtarı nereden alınır? | Not |
|---|---|---|
| 1. Google Gemini | https://aistudio.google.com/apikey | Ücretsiz katmanı vardır; ücretsiz katmanda girdiler Google'ın ürünlerini geliştirmek için kullanılabilir. |
| 2. Anthropic Claude | https://platform.claude.com/settings/keys | Ücretli; 1.000 öneri yaklaşık 0,45 $ (Ekim 2026). |
| 3. OpenAI GPT | https://platform.openai.com/api-keys | Ücretli; 1.000 öneri yaklaşık 0,35 $ (Ekim 2026). |
| 4. Yerel model | — (bkz. Bölüm 5) | Veriler bilgisayardan çıkmaz; daha yavaş ve daha az isabetli. |
| 5. Şimdilik modelsiz | — | Yalnızca basit yazım hatası düzeltme; internet gerekmez. |

**3. adım: anahtar ve deneme.** Sihirbaz şu adımları izler:

- API anahtarını ekranda göstermeden alır.
- Bir deneme isteği gönderir (`lss -la` → `ls -la`) ve ayarın çalıştığını doğrular.
- Ayarları `~/.config/shellm/config` dosyasına yalnızca sizin okuyabileceğiniz izinlerle yazar.

Anahtar kabuğun ortamına hiç girmez; SheLLM'den çalıştırdığınız programlar onu göremez.

## 4. Kullanım

| Ne yazarsınız | Ne olur |
|---|---|
| `mkdr yedek` | Komut bulunamaz → öneri: `mkdir yedek` |
| `belgeler klasöründeki txt dosyalarını listele` | Türkçe istek → öneri: `ls belgeler/*.txt` |
| `notlar.txt'yi sil` | Kesme işareti olsa da öneri gelir; silme riskli olduğu için uyarı gösterilir |
| `# find all python files` | `#` ile başlayan satır çalıştırılmaz, doğrudan modele gönderilir. Program adıyla başlayan İngilizce istekler için gereklidir. |

**Öneriyi onaylamak**

- `e` yazıp Enter'a basmak öneriyi çalıştırır.
- **Riskli** önerilerde (silme, üzerine yazma, yetki değişikliği, ağdan betik çalıştırma …) yalnızca `evet` kabul edilir.
- Başka her yanıt öneriyi atlar.

İngilizce arayüzde tuşlar `y` ve `yes`'tir; iki arayüz de her ikisini kabul eder.

**Bilmeniz gerekenler**

- Parola ya da erişim anahtarı içeren satırlar modele hiç gönderilmez.
- SheLLM öğretim amaçlı bir kabuktur. `;`, `&&`, `||`, `$( )` gibi yapıları desteklemez; öneriler buna göre üretilir.
- Oturum kabuğu (login shell) olarak ayarlamayın; ihtiyaç duyduğunuzda `shellm` yazarak açın, `exit` ile çıkın.

## 5. Yerel model (isteğe bağlı, veri dışarı çıkmaz)

Ubuntu/WSL penceresinde [Ollama](https://ollama.com)'yı kurup küçük bir kod modelini indirin:

```bash
curl -fsSL https://ollama.com/install.sh | sh
ollama pull qwen2.5-coder:1.5b
shellm --setup          # 4) Yerel model; adres: http://localhost:11434/v1
```

`qwen2.5-coder:1.5b` sıradan bir dizüstü bilgisayarda da çalışır (yaklaşık 1 GB). Daha isabetli öneriler için daha büyük modeller (`qwen2.5-coder:7b`, yaklaşık 4,7 GB) daha fazla bellek ister ve daha yavaştır. Testlerimizde 1,5B model, barındırılan modellerden belirgin biçimde daha az isabetliydi.

## 6. Gizlilik

Barındırılan bir model seçtiyseniz sağlayıcıya şunlar gönderilir:

- Başarısız olan satır
- Bulunduğunuz dizinin yolu
- Bu dizindeki en çok 50 dosya ve klasör adı. Sihirbazda bunu kapatabilirsiniz; ancak öneriler daha az isabetli olur.

Dosya içerikleri gönderilmez. Yerel model seçildiğinde hiçbir şey bilgisayardan çıkmaz.

## 7. Windows Terminal'e SheLLM profili (isteğe bağlı)

1. Windows Terminal'i açın ve **Ayarlar → Yeni profil ekle → Yeni boş profil** yolunu izleyin.
2. **Ad** alanına *SheLLM* yazın.
3. **Komut satırı** alanına şunu yazın:
   ```text
   wsl.exe -d Ubuntu --cd ~ -- bash -lc shellm
   ```

## 8. Güncelleme ve kaldırma

| Kurulum | Güncelleme | Kaldırma |
|---|---|---|
| Paket (A) | Yeni `.deb` dosyasını aynı komutla kurun | `sudo apt remove shellm` |
| Kaynak (B) | `git pull`, ardından `./install.sh` (ya da yeni sürümün klasöründe `./install.sh`) | `./install.sh --uninstall` |

Ayar dosyası kaldırmada korunur. Silmek için: `rm -r ~/.config/shellm`

## 9. Sorun giderme

| Belirti | Çözüm |
|---|---|
| `shellm: command not found` | Yeni bir terminal açın; olmazsa `source ~/.bashrc`. Kaynak kurulumunda program `~/.local/bin` altındadır. |
| Üst çubukta `kapalı (… tanımlı değil)` | API anahtarı yok: `shellm --setup` |
| `kapalı (yardımcı süreç başlamadı)` | `python3` kurulu değil: `sudo apt install python3` |
| Öneri gelmiyor, "zaman aşımı" | İnternet bağlantısını ya da yerel modelde `ollama serve`'ün çalıştığını denetleyin |
| `kota ya da hız sınırı aşıldı` | Ücretsiz katmanın günlük sınırı dolmuş olabilir; daha sonra deneyin ya da ücretli katmana geçin |
| Derleme sırasında `readline/readline.h` bulunamadı | `sudo apt install libreadline-dev` (ya da `./install.sh --deps`) |

Ayarları elle de düzenleyebilirsiniz (`~/.config/shellm/config`, `ANAHTAR=değer` satırları). Ortam değişkenleri (ör. `export GEMINI_API_KEY=…`) bu dosyadaki değerlerin önüne geçer. Tüm değişkenlerin listesi `README.md` içindedir.
