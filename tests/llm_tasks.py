# -*- coding: utf-8 -*-
"""Task sets for the LLM experiment (E6).

A  Typos (100): two different, realistic typos are applied to the names of 50
   basic commands (deletion, adjacent key on the keyboard, insertion,
   transposition). The three examples from the report (lt, mkdr, cf) are
   included directly.
B  Turkish natural language requests (100): requests that can be executed in
   the experiment directory, each with a reference command and a check type.
E  English equivalents of set B (100): same reference commands and checks.
C  English NL2Bash examples (100): sampled at random from the corpus with a
   fixed seed; evaluated with syntactic metrics (NLC2CMD score) instead of
   execution.

Check types (out): text, ws, lines, lines_nonempty, set, ws_set,
lines_nohdr, names, grep, int, contains:<text>, diff; with None only the file
system state is compared. probe: a probe command run in the same session after
the suggestion (e.g. pwd for cd). The file system state is compared for every task.

The task data below (Turkish requests, reference commands, typo operation labels)
is stored in the result files and must not be changed.
"""
import os
import random
import shutil

BUILTINS = {"echo", "cd", "pwd", "export", "unset", "env", "exit"}

# ---------------------------------------------------------------------- set A
A_BASE = [
    ("ls", "names"), ("ls -la", "names"), ("ls belgeler", "names"),
    ("ls -R projeler", "names"), ("pwd", "text"), ("cat notlar.txt", "text"),
    ("head -n 3 veri.csv", "text"), ("tail -n 2 loglar/app.log", "text"),
    ("wc -l veri.csv", "int"), ("grep ERROR loglar/app.log", "grep"),
    ("grep -i hata loglar/sistem.log", "grep"), ("grep -c INFO loglar/app.log", "int"),
    ("sort isimler.txt", "lines"), ("sort -n sayilar.txt", "lines"),
    ("cut -d , -f 1 veri.csv", "lines"), ("tr a-z A-Z < notlar.txt", "text"),
    ("mkdir yedek", None), ("touch yeni.txt", None),
    ("cp notlar.txt notlar_yedek.txt", None), ("mv gecici/c.bak gecici/c.txt", None),
    ("rm gecici/a.tmp", None), ("echo merhaba", "text"), ("echo $HOME", "text"),
    ("cd belgeler", "pwd"), ("cd projeler", "pwd"), ("find . -name '*.py'", "names"),
    ("find belgeler -type f", "names"), ("du -s belgeler", "ws"),
    ("wc -w notlar.txt", "int"), ("file projeler/hesap.c", "ws"),
    ("stat -c %s veri.csv", "int"), ("basename projeler/hesap.c", "text"),
    ("dirname projeler/hesap.c", "text"), ("diff notlar.txt belgeler/notlar.txt", "diff"),
    ("seq 1 5", "text"), ("whoami", "text"), ("tac notlar.txt", "text"),
    ("nl notlar.txt", "ws"), ("awk -F , '{print $2}' veri.csv", "lines"),
    ("sed 's/INFO/BILGI/' loglar/app.log", "text"), ("chmod +x betik.sh", None),
    ("ln -s notlar.txt kisayol", None), ("ls -1 resimler", "names"),
    ("cat -n notlar.txt", "ws"), ("md5sum notlar.txt", "ws"),
    ("grep -rn main projeler", "grep"), ("python3 projeler/betik.py", "text"),
    ("uniq isimler.txt", "lines"), ("rev notlar.txt", "text"),
    ("tar -tzf arsiv.tar.gz", "set"),
]
A_FIXED = {"ls": "lt", "mkdir yedek": "mkdr", "cd belgeler": "cf"}

QWERTY = ["qwertyuiop", "asdfghjkl", "zxcvbnm"]


def _neighbors(c):
    for r, row in enumerate(QWERTY):
        i = row.find(c)
        if i < 0:
            continue
        out = set()
        for dr in (-1, 0, 1):
            rr = r + dr
            if 0 <= rr < len(QWERTY):
                for di in (-1, 0, 1):
                    j = i + di
                    if 0 <= j < len(QWERTY[rr]) and not (dr == 0 and di == 0):
                        out.add(QWERTY[rr][j])
        return sorted(out)
    return []


# Short command names that may be missing on this system but exist on common
# Unix systems; a typo that matches one of them is excluded, because it might
# not produce a command-not-found (127) status.
COMMON_COMMANDS = {"ed", "at", "sl", "ex", "dc", "pr", "od", "ld", "as", "cc", "ar",
                   "nm", "ps", "bc", "ip", "ss", "df", "su", "vi", "xz", "gs", "sg",
                   "mt", "ul", "w", "hd", "td", "tc", "rs", "js", "gc", "gv", "cu",
                   "ftp", "top", "man", "mc", "mcd", "nc", "pv", "lp", "tee", "la"}


def _is_command(word):
    return word in BUILTINS or word in COMMON_COMMANDS or shutil.which(word) is not None


def _typos(name, rng):
    """Generates the possible typos of a command name as (operation, result) pairs."""
    cands = []
    if len(name) >= 3:
        for i in range(len(name)):
            cands.append(("deletion", name[:i] + name[i + 1:]))
    for i, c in enumerate(name):
        for n in _neighbors(c):
            cands.append(("adjacent_key", name[:i] + n + name[i + 1:]))
    for i in range(len(name) + 1):
        for n in (_neighbors(name[i - 1]) if i > 0 else []) + ([name[i - 1]] if i > 0 else []):
            cands.append(("insertion", name[:i] + n + name[i:]))
    for i in range(len(name) - 1):
        if name[i] != name[i + 1]:
            cands.append(("transposition", name[:i] + name[i + 1] + name[i] + name[i + 2:]))
    seen, out = set(), []
    for op, w in cands:
        if w and w != name and w not in seen and not _is_command(w):
            seen.add(w)
            out.append((op, w))
    rng.shuffle(out)
    return out


# Typo operation labels (stored as typo_op); "from_project_report" marks the
# three typos taken from the project's original report (A_FIXED).
OPS = ["deletion", "adjacent_key", "insertion", "transposition"]


def build_a(seed=2026):
    """Two variants for each basic command; operation types are assigned in
    rotation across the whole set (if no candidate fits, the next type is used)."""
    rng = random.Random(seed)
    items = []
    cyc = 0
    for k, (cmd, chk) in enumerate(A_BASE):
        name, rest = (cmd.split(" ", 1) + [""])[:2]
        cands = _typos(name, rng)
        chosen = []
        if cmd in A_FIXED:
            chosen.append(("from_project_report", A_FIXED[cmd]))
        while len(chosen) < 2:
            picked = None
            for t in range(len(OPS)):
                want = OPS[(cyc + t) % len(OPS)]
                for op, w in cands:
                    if op == want and w not in {c[1] for c in chosen}:
                        picked = (op, w)
                        break
                if picked:
                    break
            cyc += 1
            if not picked:
                break
            chosen.append(picked)
        for j, (op, w) in enumerate(chosen):
            inp = w + ((" " + rest) if rest else "")
            it = {"id": "A%03d" % (2 * k + j + 1), "set": "A", "input": inp,
                  "ref": cmd, "check": chk, "typo_op": op}
            if chk == "pwd":
                it["probe"] = "pwd"
            items.append(it)
    return items


# ---------------------------------------------------------------------- set B
B_ITEMS = [
    # listing
    ("belgeler klasöründeki txt dosyalarını listele", "ls belgeler/*.txt", "names"),
    ("resimler klasöründeki png dosyalarını göster", "ls resimler/*.png", "names"),
    ("belgeler klasöründeki gizli dosyalar dahil her şeyi listele", "ls -A belgeler", "names"),
    ("projeler klasörünün içeriğini göster", "ls projeler", "names"),
    ("bu dizindeki sadece klasörleri listele", "ls -d */", "names"),
    ("belgeler klasöründeki tüm dosyaları alt klasörler dahil listele", "find belgeler -type f", "names"),
    ("tüm python dosyalarını bul", "find . -name '*.py'", "names"),
    ("projeler klasöründeki c ve h uzantılı dosyaları listele", "ls projeler/*.[ch]", "names"),
    ("resimler klasöründeki jpg ve jpeg dosyalarını listele", "ls resimler/*.jpg resimler/*.jpeg", "names"),
    ("gecici klasöründeki tmp dosyalarını listele", "ls gecici/*.tmp", "names"),
    ("loglar klasöründeki .log uzantılı dosyaları listele", "ls loglar/*.log", "names"),
    ("boş dosyaları bul", "find . -type f -empty", "names"),
    ("boyutu 100 KB'dan büyük dosyaları bul", "find . -type f -size +100k", "names"),
    ("son 1 gün içinde değiştirilen dosyaları bul", "find . -type f -mtime -1", "names"),
    ("adı rapor ile başlayan dosyaları bul", "find . -name 'rapor*'", "names"),
    ("adında test geçen python dosyalarını bul", "find . -name '*test*.py'", "names"),
    ("belgeler klasöründeki pdf dosyalarını listele", "ls belgeler/*.pdf", "names"),
    ("projeler klasöründeki dosyaları ayrıntılı olarak listele", "ls -l projeler", "names"),
    ("tüm gizli dosyaları bul", "find . -type f -name '.*'", "names"),
    ("uzantısı bak olan dosyaları bul", "find . -name '*.bak'", "names"),
    ("loglar klasöründe ERROR içeren dosyaların adlarını listele", "grep -l ERROR loglar/*", "names"),
    ("rapor.txt dosyasını bul", "find . -name rapor.txt", "names"),
    ("arsiv.tar.gz arşivinin içindeki dosyaları listele", "tar -tzf arsiv.tar.gz", "set"),
    # counting
    ("bu dizindeki dosya ve klasörlerin sayısını bul", "ls | wc -l", "int"),
    ("veri.csv dosyasında kaç satır var", "wc -l < veri.csv", "int"),
    ("notlar.txt kaç kelime içeriyor", "wc -w < notlar.txt", "int"),
    ("app.log dosyasında kaç tane ERROR satırı var", "grep -c ERROR loglar/app.log", "int"),
    ("projeler klasöründe kaç tane c dosyası var", "ls projeler/*.c | wc -l", "int"),
    ("isimler.txt dosyasında kaç farklı isim var", "sort -u isimler.txt | wc -l", "int"),
    ("resimler klasöründeki dosya sayısını bul", "ls resimler | wc -l", "int"),
    ("alt klasörler dahil kaç tane txt dosyası var", "find . -name '*.txt' | wc -l", "int"),
    ("veri.csv'de başlık satırı hariç kaç kayıt var", "tail -n +2 veri.csv | wc -l", "int"),
    ("notlar.txt dosyasının boyutunu bayt cinsinden göster", "wc -c < notlar.txt", "int"),
    ("sayilar.txt içindeki sayıların toplamını hesapla", "awk '{s+=$1} END {print s}' sayilar.txt", "int"),
    ("sayilar.txt içindeki en büyük sayıyı bul", "sort -n sayilar.txt | tail -n 1", "int"),
    ("sayilar.txt içinde 50'den büyük kaç sayı var", "awk '$1 > 50' sayilar.txt | wc -l", "int"),
    ("isimler.txt içinde Ayse kaç kez geçiyor", "grep -c Ayse isimler.txt", "int"),
    # viewing
    ("notlar.txt dosyasının içeriğini göster", "cat notlar.txt", "text"),
    ("veri.csv dosyasının ilk 5 satırını göster", "head -n 5 veri.csv", "text"),
    ("app.log dosyasının son 3 satırını göster", "tail -n 3 loglar/app.log", "text"),
    ("notlar.txt dosyasını satır numaralarıyla göster", "cat -n notlar.txt", "ws"),
    ("projeler klasöründeki README.md dosyasını göster", "cat projeler/README.md", "text"),
    ("veri.csv dosyasının 3. satırını göster", "sed -n 3p veri.csv", "text"),
    ("notlar.txt dosyasını son satırdan başlayarak tersten göster", "tac notlar.txt", "text"),
    ("sistem.log dosyasının ilk satırını göster", "head -n 1 loglar/sistem.log", "text"),
    ("belgeler/eski klasöründeki arsiv.dat dosyasını göster", "cat belgeler/eski/arsiv.dat", "text"),
    ("hesap.h dosyasının ilk 2 satırını göster", "head -n 2 projeler/hesap.h", "text"),
    ("app.log dosyasındaki boş olmayan satırları göster", "grep -v '^$' loglar/app.log", "text"),
    # searching
    ("app.log içinde ERROR geçen satırları göster", "grep ERROR loglar/app.log", "grep"),
    ("sistem.log içinde büyük küçük harf ayırmadan hata kelimesini ara", "grep -i hata loglar/sistem.log", "grep"),
    ("projeler klasöründeki dosyalarda main kelimesini ara", "grep -r main projeler", "grep"),
    ("app.log dosyasında WARN içermeyen satırları göster", "grep -v WARN loglar/app.log", "grep"),
    ("veri.csv içinde Ankara geçen satırları bul", "grep Ankara veri.csv", "grep"),
    ("loglar klasöründeki tüm dosyalarda timeout kelimesini ara", "grep -r timeout loglar", "grep"),
    ("hesap.c dosyasındaki include satırlarını göster", "grep include projeler/hesap.c", "grep"),
    ("notlar.txt içinde proje kelimesinin geçtiği satırları satır numaralarıyla göster", "grep -n proje notlar.txt", "ws"),
    ("isimler.txt içinde A harfiyle başlayan isimleri göster", "grep '^A' isimler.txt", "lines"),
    ("veri.csv'de İstanbul'da yaşayanları göster", "grep Istanbul veri.csv", "grep"),
    # text processing
    ("isimler.txt dosyasını alfabetik olarak sırala", "sort isimler.txt", "lines"),
    ("isimler.txt dosyasını tekrar eden satırları kaldırarak sırala", "sort -u isimler.txt", "lines"),
    ("sayilar.txt içindeki sayıları küçükten büyüğe sırala", "sort -n sayilar.txt", "lines"),
    ("sayilar.txt içindeki sayıları büyükten küçüğe sırala", "sort -nr sayilar.txt", "lines"),
    ("veri.csv dosyasının sadece ilk sütununu göster", "cut -d , -f 1 veri.csv", "lines"),
    ("veri.csv'deki şehirleri tekrarsız listele", "tail -n +2 veri.csv | cut -d , -f 2 | sort -u", "set"),
    ("notlar.txt içeriğini büyük harfe çevirerek göster", "tr a-z A-Z < notlar.txt", "text"),
    ("isimler.txt dosyasında her ismin kaç kez geçtiğini say", "sort isimler.txt | uniq -c", "ws_set"),
    ("veri.csv dosyasını virgüller yerine noktalı virgül kullanarak ekrana yazdır", "tr , ';' < veri.csv", "text"),
    ("app.log dosyasındaki INFO kelimelerini BILGI ile değiştirerek ekrana yazdır", "sed 's/INFO/BILGI/g' loglar/app.log", "text"),
    ("veri.csv'deki kayıtları yaşa göre küçükten büyüğe sırala", "tail -n +2 veri.csv | sort -t , -k 3 -n", "lines_nohdr"),
    ("notlar.txt ile belgeler/notlar.txt dosyaları arasındaki farkları göster", "diff notlar.txt belgeler/notlar.txt", "diff"),
    ("isimler.txt dosyasında tekrar eden isimleri göster", "sort isimler.txt | uniq -d", "set"),
    ("sayilar.txt dosyasındaki çift sayıları göster", "awk '$1 % 2 == 0' sayilar.txt", "lines"),
    ("veri.csv'de yaşı 30'dan büyük olanları göster", "awk -F , 'NR > 1 && $3 > 30' veri.csv", "lines_nohdr"),
    ("app.log dosyasındaki satırların sadece ilk kelimesini göster", "awk '{print $1}' loglar/app.log", "lines_nonempty"),
    ("notlar.txt dosyasındaki boşlukları alt çizgiyle değiştirerek göster", "tr ' ' '_' < notlar.txt", "text"),
    # file operations
    ("yedek adında bir klasör oluştur", "mkdir yedek", None),
    ("arsiv/2024/ocak klasör yapısını oluştur", "mkdir -p arsiv/2024/ocak", None),
    ("yeni.txt adında boş bir dosya oluştur", "touch yeni.txt", None),
    ("notlar.txt dosyasını yedek_notlar.txt olarak kopyala", "cp notlar.txt yedek_notlar.txt", None),
    ("belgeler klasörünü belgeler_yedek adıyla kopyala", "cp -r belgeler belgeler_yedek", None),
    ("belgeler klasöründeki taslak.txt dosyasının adını son.txt yap", "mv belgeler/taslak.txt belgeler/son.txt", None),
    ("resimler klasöründeki png dosyalarını belgeler klasörüne taşı", "mv resimler/*.png belgeler/", None),
    ("gecici klasöründeki tmp uzantılı dosyaları sil", "rm gecici/*.tmp", None),
    ("gecici klasörünü içindekilerle birlikte sil", "rm -r gecici", None),
    ("bos.txt dosyasını sil", "rm bos.txt", None),
    ("merhaba dünya yazısını selam.txt dosyasına yaz", "echo 'merhaba dünya' > selam.txt", None),
    ("notlar.txt dosyasının sonuna 'yeni not' satırını ekle", "echo 'yeni not' >> notlar.txt", None),
    ("betik.sh dosyasını çalıştırılabilir yap", "chmod +x betik.sh", None),
    ("notlar.txt için kisayol adında sembolik bağlantı oluştur", "ln -s notlar.txt kisayol", None),
    ("loglar klasörünü loglar.tar.gz adıyla arşivle", "tar -czf loglar.tar.gz loglar", None),
    ("arsiv.tar.gz arşivini bu dizine aç", "tar -xzf arsiv.tar.gz", None),
    # directory and system
    ("projeler klasörüne geç", "cd projeler", "pwd"),
    ("bir üst dizine çık", "cd ..", "pwd"),
    ("ev dizinine git", "cd", "pwd"),
    ("şu anki dizinin tam yolunu göster", "pwd", "text"),
    ("hangi kullanıcıyla oturum açtığımı göster", "whoami", "text"),
    ("HOME değişkeninin değerini yazdır", "echo $HOME", "text"),
    ("notlar.txt dosyasının izinlerini göster", "ls -l notlar.txt", "contains:-rw-r--r--"),
    ("hesap.c dosyasının türünü göster", "file projeler/hesap.c", "contains:C source"),
    ("projeler klasöründeki betik.py programını çalıştır", "python3 projeler/betik.py", "text"),
]


def build_b():
    items = []
    for k, (req, ref, chk) in enumerate(B_ITEMS):
        it = {"id": "B%03d" % (k + 1), "set": "B", "input": req, "ref": ref, "check": chk}
        if chk == "pwd":
            it["probe"] = "pwd"
        items.append(it)
    return items


# ---------------------------------------------------------------------- set E
# English equivalents of the requests in set B (same order, same reference
# command and check type). File and folder names keep their Turkish names from
# the experiment directory; only the language of the request changes.
E_TEXTS = [
    "list the txt files in the belgeler folder",
    "show the png files in the resimler folder",
    "list everything in the belgeler folder including hidden files",
    "show the contents of the projeler folder",
    "list only the folders in this directory",
    "list all files in the belgeler folder including subfolders",
    "find all python files",
    "list the files with c and h extensions in the projeler folder",
    "list the jpg and jpeg files in the resimler folder",
    "list the tmp files in the gecici folder",
    "list the files with the .log extension in the loglar folder",
    "find empty files",
    "find files larger than 100 KB",
    "find files modified in the last 1 day",
    "find files whose names start with rapor",
    "find python files with test in their name",
    "list the pdf files in the belgeler folder",
    "list the files in the projeler folder in detail",
    "find all hidden files",
    "find files with the bak extension",
    "list the names of the files in the loglar folder that contain ERROR",
    "find the rapor.txt file",
    "list the files inside the arsiv.tar.gz archive",
    "count the files and folders in this directory",
    "how many lines are in veri.csv",
    "how many words does notlar.txt contain",
    "how many ERROR lines are in app.log",
    "how many c files are in the projeler folder",
    "how many distinct names are in isimler.txt",
    "count the files in the resimler folder",
    "how many txt files are there including subfolders",
    "how many records are in veri.csv excluding the header line",
    "show the size of notlar.txt in bytes",
    "calculate the sum of the numbers in sayilar.txt",
    "find the largest number in sayilar.txt",
    "how many numbers in sayilar.txt are greater than 50",
    "how many times does Ayse appear in isimler.txt",
    "show the contents of notlar.txt",
    "show the first 5 lines of veri.csv",
    "show the last 3 lines of app.log",
    "show notlar.txt with line numbers",
    "show the README.md file in the projeler folder",
    "show the 3rd line of veri.csv",
    "show notlar.txt in reverse order, starting from the last line",
    "show the first line of sistem.log",
    "show the arsiv.dat file in the belgeler/eski folder",
    "show the first 2 lines of hesap.h",
    "show the non-empty lines of app.log",
    "show the lines containing ERROR in app.log",
    "search sistem.log for the word hata, ignoring case",
    "search for the word main in the files in the projeler folder",
    "show the lines of app.log that do not contain WARN",
    "find the lines containing Ankara in veri.csv",
    "search for the word timeout in all files in the loglar folder",
    "show the include lines in hesap.c",
    "show the lines of notlar.txt containing the word proje, with line numbers",
    "show the names in isimler.txt that start with the letter A",
    "show the people in veri.csv who live in İstanbul",
    "sort isimler.txt alphabetically",
    "sort isimler.txt and remove duplicate lines",
    "sort the numbers in sayilar.txt in ascending order",
    "sort the numbers in sayilar.txt in descending order",
    "show only the first column of veri.csv",
    "list the cities in veri.csv without duplicates",
    "show the contents of notlar.txt in uppercase",
    "count how many times each name appears in isimler.txt",
    "print veri.csv to the screen using semicolons instead of commas",
    "print app.log to the screen with INFO replaced by BILGI",
    "sort the records in veri.csv by age in ascending order",
    "show the differences between notlar.txt and belgeler/notlar.txt",
    "show the repeated names in isimler.txt",
    "show the even numbers in sayilar.txt",
    "show the people in veri.csv who are older than 30",
    "show only the first word of each line of app.log",
    "show notlar.txt with spaces replaced by underscores",
    "create a folder named yedek",
    "create the folder structure arsiv/2024/ocak",
    "create an empty file named yeni.txt",
    "copy notlar.txt as yedek_notlar.txt",
    "copy the belgeler folder under the name belgeler_yedek",
    "rename taslak.txt in the belgeler folder to son.txt",
    "move the png files in the resimler folder to the belgeler folder",
    "delete the files with the tmp extension in the gecici folder",
    "delete the gecici folder together with its contents",
    "delete the bos.txt file",
    "write the text merhaba dünya to selam.txt",
    "append the line 'yeni not' to the end of notlar.txt",
    "make betik.sh executable",
    "create a symbolic link named kisayol for notlar.txt",
    "archive the loglar folder as loglar.tar.gz",
    "extract the arsiv.tar.gz archive into this directory",
    "go to the projeler folder",
    "go up one directory",
    "go to the home directory",
    "show the full path of the current directory",
    "show which user I am logged in as",
    "print the value of the HOME variable",
    "show the permissions of notlar.txt",
    "show the type of the hesap.c file",
    "run the betik.py program in the projeler folder",
]
assert len(E_TEXTS) == len(B_ITEMS)


def build_e():
    items = []
    for k, ((_, ref, chk), req) in enumerate(zip(B_ITEMS, E_TEXTS)):
        it = {"id": "E%03d" % (k + 1), "set": "E", "input": req, "ref": ref,
              "check": chk, "pair": "B%03d" % (k + 1)}
        if chk == "pwd":
            it["probe"] = "pwd"
        items.append(it)
    return items


# ---------------------------------------------------------------------- set C
def build_c(nl_path, cm_path, n=100, seed=2026):
    nls = open(nl_path, encoding="utf-8", errors="replace").read().splitlines()
    cms = open(cm_path, encoding="utf-8", errors="replace").read().splitlines()
    seen, pairs = set(), []
    for nl, cm in zip(nls, cms):
        if cm in seen or not nl.strip() or not cm.strip():
            continue
        seen.add(cm)
        pairs.append((nl.strip(), cm.strip()))
    rng = random.Random(seed)
    sample = rng.sample(pairs, n)
    return [{"id": "C%03d" % (k + 1), "set": "C", "input": nl, "ref": cm, "check": "nlc2cmd"}
            for k, (nl, cm) in enumerate(sample)]


def build_all(nl_path, cm_path):
    return build_a() + build_b() + build_c(nl_path, cm_path)


if __name__ == "__main__":
    import collections
    here = os.path.dirname(os.path.abspath(__file__))
    data = os.path.join(here, "..", "data")
    items = build_all(os.path.join(data, "all.nl"), os.path.join(data, "all.cm"))
    print(collections.Counter(i["set"] for i in items))
    for i in items[:12]:
        print(i["id"], i.get("typo_op", ""), repr(i["input"]), "->", i["ref"])
