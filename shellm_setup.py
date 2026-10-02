# -*- coding: utf-8 -*-
"""SheLLM setup wizard.

"shellm --setup" (and the first start) runs this module through ai_helper.py:
    python3 ai_helper.py --setup

It asks for the interface language, the provider (Gemini, Claude, OpenAI, a
local model, or no model), the API key, the model, and whether the directory
context may be sent; it checks the choice with a test request and writes the
result to $XDG_CONFIG_HOME/shellm/config (or ~/.config/shellm/config) with mode
0600, so that only the user can read it.

All messages are bilingual: English by default, Turkish when the user picks
Turkish (SHELLM_LANG=tr). T(en, tr) from ai_helper selects the text.
"""
import getpass
import os
import sys
import tempfile

TTY = sys.stdout.isatty()
H = None   # the ai_helper module, set by run()


def T(en, tr):
    return H.T(en, tr)


def choices():
    return [
        {"id": "gemini", "name": "Google Gemini", "env": "GEMINI_API_KEY",
         "url": "https://aistudio.google.com/apikey", "model": "gemini-flash-lite-latest",
         "note": T("Has a free tier; on the free tier your inputs may be used to improve "
                   "Google's products.",
                   "Ücretsiz katmanı vardır; ücretsiz katmanda girdileriniz Google'ın "
                   "ürünlerini geliştirmek için kullanılabilir.")},
        {"id": "anthropic", "name": "Anthropic Claude", "env": "ANTHROPIC_API_KEY",
         "url": "https://platform.claude.com/settings/keys", "model": "claude-haiku-4-5",
         "note": T("Pay per use (about $0.45 per 1,000 suggestions at October 2026 prices).",
                   "Kullanım başına ücretlidir (Ekim 2026 fiyatlarıyla 1.000 öneri "
                   "yaklaşık 0,45 $).")},
        {"id": "openai", "name": "OpenAI GPT", "env": "OPENAI_API_KEY",
         "url": "https://platform.openai.com/api-keys", "model": "gpt-5.4-mini",
         "note": T("Pay per use (about $0.35 per 1,000 suggestions at October 2026 prices).",
                   "Kullanım başına ücretlidir (Ekim 2026 fiyatlarıyla 1.000 öneri "
                   "yaklaşık 0,35 $).")},
        {"id": "local", "name": T("Local model (Ollama or llama.cpp)",
                                  "Yerel model (Ollama ya da llama.cpp)"),
         "env": None, "url": "https://ollama.com", "model": "qwen2.5-coder:1.5b",
         "note": T("Your data never leaves the computer; slower and less accurate than "
                   "hosted models.",
                   "Veriler bilgisayarınızdan çıkmaz; barındırılan modellerden daha "
                   "yavaş ve daha az isabetlidir.")},
        {"id": "mock", "name": T("No model for now (simple typo correction only)",
                                 "Şimdilik modelsiz (yalnızca basit yazım hatası düzeltme)"),
         "env": None, "url": None, "model": None,
         "note": T("Needs no internet or key; cannot answer natural-language requests.",
                   "İnternet bağlantısı ve anahtar gerekmez; doğal dildeki isteklere "
                   "yanıt veremez.")},
    ]


def b(s):
    return "\033[1m%s\033[0m" % s if TTY else s


def dim(s):
    return "\033[2m%s\033[0m" % s if TTY else s


def ask(prompt, default=""):
    shown = "%s [%s]: " % (prompt, default) if default else "%s: " % prompt
    ans = input(shown).strip()
    return ans or default


def yes(prompt, default=True):
    d = T("Y/n", "E/h") if default else T("y/N", "e/H")
    while True:
        ans = input("%s [%s]: " % (prompt, d)).strip().lower()
        if not ans:
            return default
        if ans in ("y", "yes", "e", "evet"):
            return True
        if ans in ("n", "no", "h", "hayır", "hayir"):
            return False


def mask(key):
    return ("…" + key[-4:]) if key and len(key) > 8 else T("(short)", "(kısa)")


def explain_error(choice, text):
    t = text or ""
    if "401" in t or "403" in t:
        return T("invalid key, or no access to this model",
                 "anahtar geçersiz ya da bu modele erişim izni yok")
    if "404" in t:
        return T("model name not found", "model adı bulunamadı")
    if "429" in t:
        return T("quota or rate limit exceeded; try again later",
                 "kota ya da hız sınırı aşıldı; biraz sonra yeniden deneyin")
    if "URLError" in t or "ConnectionRefused" in t or "timeout" in t.lower() \
            or "TimeoutError" in t:
        if choice["id"] == "local":
            return T("could not connect to the local server (is Ollama running? "
                     "'ollama serve')",
                     "yerel sunucuya bağlanılamadı (Ollama çalışıyor mu? 'ollama serve')")
        return T("could not connect to the server (check your internet connection)",
                 "sunucuya bağlanılamadı (internet bağlantısını denetleyin)")
    return t


def try_request(choice, settings):
    """Sends a small test request with the chosen settings."""
    for k, v in settings.items():
        os.environ[k] = v
    req = {"input": "lss -la", "cwd": os.getcwd(), "exit_code": 127}
    print(dim(T("Sending a test request: 'lss -la' …",
                "Deneme isteği gönderiliyor: 'lss -la' …")))
    status, text, _ = H.generate(H.SYSTEM_PROMPT, H.user_message(req), deadline=25.0,
                                 max_attempts=2, provider=choice["id"])
    if status != "OK":
        return False, explain_error(choice, text)
    cmd = H.clean_reply(text)
    return True, cmd or "#NONE"


def write_config(path, settings):
    d = os.path.dirname(path)
    os.makedirs(d, mode=0o700, exist_ok=True)
    lines = ["# SheLLM settings, written by 'shellm --setup'.",
             "# This file may contain an API key; do not share it.",
             "# Environment variables take precedence over the values in this file."]
    for k in ("SHELLM_LANG", "SHELLM_BACKEND", "SHELLM_MODEL", "SHELLM_LOCAL_URL",
              "SHELLM_CONTEXT", "GEMINI_API_KEY", "ANTHROPIC_API_KEY", "OPENAI_API_KEY"):
        if k in settings:
            lines.append("%s=%s" % (k, settings[k]))
    fd, tmp = tempfile.mkstemp(prefix=".config.", dir=d)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def choose_language(current):
    """Asks for the interface language; the answer is saved as SHELLM_LANG."""
    if os.environ.get("SHELLM_LANG") and "SHELLM_LANG" not in current:
        return os.environ["SHELLM_LANG"].lower()[:2]   # set explicitly by the user
    default = "2" if H.lang_tr() else "1"
    while True:
        ans = ask("Interface language / Arayüz dili: 1) English  2) Türkçe", default)
        if ans in ("1", "2"):
            lang = "tr" if ans == "2" else "en"
            os.environ["SHELLM_LANG"] = lang
            return lang


def choose(current):
    opts = choices()
    print(b(T("Which language model would you like to use?",
              "Hangi dil modelini kullanmak istersiniz?")))
    for i, c in enumerate(opts, 1):
        print("  %d) %s" % (i, c["name"]))
        print("     " + dim(c["note"]))
    default = "1"
    for i, c in enumerate(opts, 1):
        if c["id"] == current.get("SHELLM_BACKEND"):
            default = str(i)
    while True:
        ans = ask(T("Your choice (1-%d)", "Seçiminiz (1-%d)") % len(opts), default)
        if ans.isdigit() and 1 <= int(ans) <= len(opts):
            return opts[int(ans) - 1]
        print(T("Please enter a number from 1 to %d.",
                "Lütfen 1 ile %d arasında bir sayı girin.") % len(opts))


def collect(choice, current):
    s = {"SHELLM_BACKEND": choice["id"]}
    if choice["id"] == "mock":
        return s
    if choice["env"]:
        old = current.get(choice["env"]) or os.environ.get(choice["env"], "")
        print()
        print(T("You can get an API key here: ", "API anahtarını şu sayfadan alabilirsiniz: ")
              + b(choice["url"]))
        key = ""
        if old and yes(T("A saved key was found (%s). Use it?",
                         "Kayıtlı anahtar bulundu (%s). Kullanılsın mı?") % mask(old)):
            key = old
        while not key:
            key = getpass.getpass(T("Paste the API key and press Enter (it is not shown): ",
                                    "API anahtarını yapıştırıp Enter'a basın "
                                    "(ekranda görünmez): ")).strip()
            if key and len(key) < 16:
                print(T("This key looks too short; please paste all of it.",
                        "Bu anahtar çok kısa görünüyor; lütfen tamamını yapıştırın."))
                key = ""
        s[choice["env"]] = key
    else:
        print()
        print(T("A local model needs an OpenAI-compatible server. With Ollama:",
                "Yerel model için OpenAI uyumlu bir sunucu gerekir. Ollama ile:"))
        print("  curl -fsSL https://ollama.com/install.sh | sh")
        print("  ollama pull qwen2.5-coder:1.5b")
        s["SHELLM_LOCAL_URL"] = ask(T("Server address", "Sunucu adresi"), current.get(
            "SHELLM_LOCAL_URL", "http://localhost:11434/v1")).rstrip("/")
    model_default = choice["model"]
    if current.get("SHELLM_BACKEND") == choice["id"] and current.get("SHELLM_MODEL"):
        model_default = current["SHELLM_MODEL"]
    s["SHELLM_MODEL"] = ask(T("Model (Enter: recommended)", "Model (Enter: önerilen)"),
                            model_default)
    print()
    print(T("Suggestions are clearly more accurate when the names of the files and folders",
            "Öneriler, bulunduğunuz dizindeki dosya ve klasör adları (en çok 50) ile"))
    print(T("in the current directory (at most 50) are sent along.",
            "birlikte gönderildiğinde belirgin biçimde daha isabetli olur."))
    ctx = yes(T("Send file names to the model?", "Dosya adları modele gönderilsin mi?"),
              current.get("SHELLM_CONTEXT", "1") != "0")
    s["SHELLM_CONTEXT"] = "1" if ctx else "0"
    return s


def run(helper):
    global H
    H = helper
    if not sys.stdin.isatty():
        print(T("The setup wizard must be run in a terminal: shellm --setup",
                "Kurulum sihirbazı bir terminalde çalıştırılmalıdır: shellm --setup"),
              file=sys.stderr)
        return 1
    path = H.config_path()
    current = H.read_config(path)
    choice = {}
    try:
        print()
        print(b("SheLLM %s setup" % H.VERSION))
        lang = choose_language(current)
        print()
        print(T("SheLLM asks a language model for one command suggestion when a command is",
                "SheLLM, bir komut bulunamadığında ya da satıra '#' ile başlayan bir istek"))
        print(T("not found or when you start a line with '#'. A suggestion runs only after you",
                "yazdığınızda bir dil modelinden tek bir komut önerisi alır. Öneri yalnızca"))
        print(T("confirm it; lines that contain passwords or keys are never sent.",
                "siz onaylarsanız çalışır; parola ya da anahtar içeren satırlar gönderilmez."))
        print()
        if current.get("SHELLM_BACKEND"):
            print(T("Current setting: %s, model %s", "Mevcut ayar: %s, model %s") % (
                current.get("SHELLM_BACKEND", "?"),
                current.get("SHELLM_MODEL", T("default", "varsayılan"))))
            if not yes(T("Do you want to change the settings?",
                         "Ayarları değiştirmek istiyor musunuz?")):
                if current.get("SHELLM_LANG", "") != lang:
                    current["SHELLM_LANG"] = lang
                    write_config(path, current)
                return 0
            print()
        while True:
            choice = choose(current)
            settings = collect(choice, current)
            if choice["id"] == "mock":
                break
            ok, msg = try_request(choice, settings)
            if ok:
                print(T("Test succeeded: suggestion for 'lss -la' → ",
                        "Deneme başarılı: 'lss -la' için öneri → ") + b(msg))
                break
            print(T("Test failed: ", "Deneme başarısız: ") + msg)
            ans = ask(T("[r]etry setup, [s]ave anyway, [q]uit",
                        "[t]ekrar ayarla, [k]aydet yine de, [v]azgeç"), T("r", "t")).lower()
            if ans[:1] in ("s", "k"):
                break
            if ans[:1] in ("q", "v"):
                print(T("Settings were not changed.", "Ayarlar değiştirilmedi."))
                return 1
            print()
        settings["SHELLM_LANG"] = lang
        write_config(path, settings)
    except (KeyboardInterrupt, EOFError):
        print(T("\nSetup cancelled; settings were not changed.",
                "\nKurulum iptal edildi; ayarlar değiştirilmedi."))
        return 130
    print()
    print(T("Settings saved: %s (readable only by you)",
            "Ayarlar kaydedildi: %s (yalnızca sizin okuyabileceğiniz izinlerle)") % path)
    env_key = choice.get("env")
    if env_key and env_key in H.ENV_OVERRIDES:
        print(T("Note: %s is set in your environment; that value takes precedence over "
                "this file.",
                "Not: ortamınızda %s tanımlı; o değer bu dosyanın önüne geçer.") % env_key)
    print(T("Start SheLLM with 'shellm'; change the settings with 'shellm --setup'.",
            "Kullanım: 'shellm' yazarak başlatın; ayarları değiştirmek için "
            "'shellm --setup'."))
    print()
    return 0
