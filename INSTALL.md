# SheLLM installation and user guide

SheLLM is a Unix shell that asks a language model for **one command suggestion** in two cases:

- a command you typed cannot be found;
- you start a line with `#`.

The suggestion is shown on screen and runs only after you confirm it. (A Turkish translation of this guide is in [docs/INSTALL.tr.md](docs/INSTALL.tr.md).)

```text
🎀 sheLLM mkdr backup
shellm: mkdr: command not found

  ┃ ◆ shellm suggestion
  ┃ mkdir backup
  ┃
  ┃ [y] run   [n] skip
```

**Requirements**

- Linux (Ubuntu or Debian recommended), or Windows 10/11 with WSL.
- A model to ask, one of:
  - a hosted model (Gemini, Claude, OpenAI), which needs an internet connection and an API key;
  - a local model running on your computer, in which case your data never leaves the machine.

---

## 1. On Windows: install WSL

SheLLM is a Linux shell; on Windows it runs inside WSL, Microsoft's Linux subsystem.

1. In the **Start** menu, right-click *PowerShell*, choose **Run as administrator**, and type:
   ```powershell
   wsl --install -d Ubuntu
   ```
2. Restart the computer.
3. Open **Ubuntu** from the Start menu and choose a Linux user name and password when asked.

Do all remaining steps in this **Ubuntu window**. Your Windows files are under `/mnt/c/Users/<your Windows user name>/`.

## 2. Install SheLLM

There are two ways. Option A is the easiest on Ubuntu, Debian or WSL.

### A) Package (Ubuntu, Debian, WSL)

Download the package from the [releases page](https://github.com/sametkaya/shellm/releases) and install it:

```bash
wget https://github.com/sametkaya/shellm/releases/download/v1.0.0/shellm_1.0.0_amd64.deb
sudo apt install ./shellm_1.0.0_amd64.deb
```

If you downloaded it with a browser on Windows instead, it is in your *Downloads* folder; run this in the Ubuntu window:

```bash
cd /mnt/c/Users/<your Windows user name>/Downloads
sudo apt install ./shellm_1.0.0_amd64.deb
```

The required libraries (readline, python3) are installed with the package.

### B) From source (any Linux distribution)

```bash
git clone https://github.com/sametkaya/shellm.git
cd shellm
./install.sh
```

The source archive `shellm-1.0.0.tar.gz` from the releases page works the same way (`tar xzf shellm-1.0.0.tar.gz && cd shellm-1.0.0 && ./install.sh`).

- The script installs SheLLM for your user only, to `~/.local/bin/shellm`, and does not need administrator rights.
- If a compiler, readline, or python3 is missing, it says which packages are needed and installs them with your consent (this step uses `sudo`).

| Option | What it does |
|---|---|
| `--system` | install for all users (`/usr/local`, needs `sudo`) |
| `--prefix DIR` | install under a custom location |
| `--deps` | install missing packages without asking |
| `--no-setup` | skip the setup wizard |
| `--uninstall` | remove SheLLM |

## 3. First start: the setup wizard

```bash
shellm
```

On first start, or later with `shellm --setup`, a wizard opens.

**Step 1: interface language.** It first asks for the interface language: English or Türkçe. The answer is saved, and you can change it at any time with `SHELLM_LANG=en` or `SHELLM_LANG=tr`.

**Step 2: model.** Then it asks which model to use:

| Option | Where to get an API key | Note |
|---|---|---|
| 1. Google Gemini | https://aistudio.google.com/apikey | Has a free tier; on the free tier your inputs may be used to improve Google's products. |
| 2. Anthropic Claude | https://platform.claude.com/settings/keys | Paid; about $0.45 per 1,000 suggestions (October 2026). |
| 3. OpenAI GPT | https://platform.openai.com/api-keys | Paid; about $0.35 per 1,000 suggestions (October 2026). |
| 4. Local model | — (see Section 5) | Your data never leaves the computer; slower and less accurate. |
| 5. No model for now | — | Simple typo correction only; no internet needed. |

**Step 3: key and test.** The wizard:

- reads the API key without showing it;
- sends one test request (`lss -la` → `ls -la`) to check that everything works;
- saves the settings to `~/.config/shellm/config`, readable only by you.

The key never enters the shell's environment, so programs you start from SheLLM cannot see it.

## 4. Using SheLLM

| What you type | What happens |
|---|---|
| `mkdr backup` | The command is not found → suggestion: `mkdir backup` |
| `list the txt files in the belgeler folder` | Natural-language request → suggestion: `ls belgeler/*.txt` |
| `notlar.txt'yi sil` | Turkish request with an apostrophe still gets a suggestion; deletion is risky, so a warning is shown |
| `# find all python files` | A line starting with `#` is not run but sent straight to the model. English requests often begin with a program name (here `find`) and need this prefix. |

**Confirming a suggestion**

- Type `y` and press Enter to run it.
- **Risky** suggestions (deletion, overwriting, permission changes, running scripts from the network, …) run only after you type the full word `yes`.
- Any other answer skips the suggestion.

In the Turkish interface the keys are `e` and `evet`; both languages accept both sets.

**Good to know**

- Lines that contain a password or an access key are never sent to the model.
- SheLLM is a teaching shell. It does not support constructs such as `;`, `&&`, `||` or `$( )`, and suggestions are generated accordingly.
- Do not make it your login shell; start it with `shellm` when you need it and leave it with `exit`.

## 5. Local model (optional; your data stays on the computer)

In the Ubuntu/WSL window, install [Ollama](https://ollama.com) and download a small code model:

```bash
curl -fsSL https://ollama.com/install.sh | sh
ollama pull qwen2.5-coder:1.5b
shellm --setup          # 4) Local model; address: http://localhost:11434/v1
```

- `qwen2.5-coder:1.5b` (about 1 GB) runs on an ordinary laptop.
- Larger models (`qwen2.5-coder:7b`, about 4.7 GB) give better suggestions but need more memory and are slower.
- In our tests, the 1.5B model was clearly less accurate than the hosted models.

## 6. Privacy

If you chose a hosted model, the following is sent to the provider:

- the line that failed;
- the path of the current directory;
- up to 50 file and folder names in that directory. You can turn this off in the wizard, but suggestions become less accurate.

File contents are never sent. With a local model nothing leaves the computer.

## 7. A SheLLM profile in Windows Terminal (optional)

1. In Windows Terminal, go to **Settings → Add a new profile → New empty profile**.
2. Set **Name** to *SheLLM*.
3. Set **Command line** to:
   ```text
   wsl.exe -d Ubuntu --cd ~ -- bash -lc shellm
   ```

## 8. Updating and uninstalling

| Installed with | Update | Uninstall |
|---|---|---|
| Package (A) | Install the new `.deb` with the same command | `sudo apt remove shellm` |
| Source (B) | `git pull`, then `./install.sh` (or run it in the new version's folder) | `./install.sh --uninstall` |

The settings file is kept when you uninstall. To delete it: `rm -r ~/.config/shellm`

## 9. Troubleshooting

| Symptom | Fix |
|---|---|
| `shellm: command not found` | Open a new terminal, or run `source ~/.bashrc`. A source install puts the program in `~/.local/bin`. |
| The top bar shows `off (… is not set)` | No API key: run `shellm --setup` |
| `off (helper did not start)` | `python3` is missing: `sudo apt install python3` |
| No suggestion, "timed out" | Check your internet connection, or for a local model that `ollama serve` is running |
| `quota or rate limit exceeded` | The free tier's daily limit may be used up; try later or switch to a paid tier |
| `readline/readline.h` not found while building | `sudo apt install libreadline-dev` (or `./install.sh --deps`) |

You can also edit the settings file by hand (`~/.config/shellm/config`, `KEY=value` lines). Environment variables (e.g. `export GEMINI_API_KEY=…`) take precedence over the file. All variables are listed in `README.md`.
