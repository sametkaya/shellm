# -*- coding: utf-8 -*-
"""Fixed experiment directory and file system snapshot for the LLM experiment (E6).

Every call to create() builds this layout with the same contents, permissions
and timestamps:

    /home/kullanici/                     HOME
    /home/kullanici/Masaustu/calisma/    directory where commands are run (cwd)

Because the absolute paths are the same on every run, model suggestions that
contain absolute paths can be compared as well. The directory is rebuilt from
scratch before every execution.

The Turkish file/folder names and file contents below are fixture data that the
tasks refer to; they must not be changed.
"""
import hashlib
import io
import os
import tarfile
import time

OLD = 1735725600          # 2025-01-01 10:00 (fixed time for old files)

NOTES_TXT = ("Pazartesi proje toplantisi saat 10:00\n"
          "Rapor taslagi Carsamba gunu teslim edilecek\n"
          "Yeni proje icin butce onayi bekleniyor\n"
          "Cuma gunu sunum provasi yapilacak\n")
DOCS_NOTES_TXT = ("Pazartesi proje toplantisi saat 10:00\n"
                "Rapor taslagi Persembe gunu teslim edilecek\n"
                "Yeni proje icin butce onayi bekleniyor\n")
DATA_CSV = ("ad,sehir,yas\n"
        "Ayse,Istanbul,34\nMehmet,Ankara,28\nZeynep,Izmir,41\nAli,Istanbul,25\n"
        "Elif,Bursa,37\nCan,Ankara,31\nDeniz,Antalya,22\nBurak,Izmir,45\n"
        "Selin,Istanbul,29\nEmre,Ankara,39\n")
NAMES_TXT = "Mehmet\nAyse\nZeynep\nAli\nAyse\nCan\nElif\nMehmet\nAhmet\nAyse\n"
NUMBERS_TXT = "42\n7\n19\n88\n3\n56\n21\n64\n10\n95\n"
APP_LOG = ("2025-01-01 10:00:01 INFO Sunucu baslatildi\n"
           "2025-01-01 10:00:02 INFO Veritabanina baglanildi\n"
           "\n"
           "2025-01-01 10:05:13 WARN Yavas sorgu: 1200 ms\n"
           "2025-01-01 10:07:44 ERROR Baglanti zaman asimi (timeout)\n"
           "2025-01-01 10:08:00 INFO Yeniden deneniyor\n"
           "\n"
           "2025-01-01 10:09:30 ERROR Kullanici bulunamadi: id=17\n"
           "2025-01-01 10:10:02 INFO Istek tamamlandi\n")
SYSTEM_LOG = ("Disk kullanimi normal\n"
              "HATA: yedekleme betigi calismadi\n"
              "Bellek kullanimi yuzde 63\n"
              "hata kodu 5 kaydedildi\n"
              "Ag baglantisi timeout nedeniyle yenilendi\n")
CALC_C = ('#include <stdio.h>\n#include "hesap.h"\n\n'
           "int topla(int a, int b)\n{\n\treturn (a + b);\n}\n")
MAIN_C = ('#include <stdio.h>\n#include "hesap.h"\n\n'
          'int main(void)\n{\n\tprintf("%d\\n", topla(2, 3));\n\treturn (0);\n}\n')
CALC_H = "#ifndef HESAP_H\n# define HESAP_H\n\nint topla(int a, int b);\n\n#endif\n"
SCRIPT_PY = 'print("merhaba SheLLM")\n'
TEST_PY = "from betik import *\n\ndef test_ornek():\n    assert True\n"
MAKEFILE = "all:\n\tcc main.c hesap.c -o hesap\n"
README = "# Hesap\n\nIki sayiyi toplayan ornek program.\n"
SCRIPT_SH = '#!/bin/sh\necho "betik calisti"\n'


def _w(path, content, mode=0o644, mtime=OLD):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    data = content if isinstance(content, bytes) else content.encode("utf-8")
    with open(path, "wb") as f:
        f.write(data)
    os.chmod(path, mode)
    os.utime(path, (mtime, mtime))


def _tar_bytes():
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as t:
        for name, txt in (("paket/oku.txt", "arsivdeki dosya\n"),
                          ("paket/liste.txt", "bir\niki\n")):
            data = txt.encode()
            ti = tarfile.TarInfo(name)
            ti.size = len(data)
            ti.mtime = OLD
            ti.mode = 0o644
            t.addfile(ti, io.BytesIO(data))
    return buf.getvalue()


TAR_GZ = _tar_bytes()


HOME = "/home/kullanici"
LAB = HOME + "/Masaustu/calisma"


def create(owner_uid=None, owner_gid=None):
    home, lab = HOME, LAB
    import shutil
    shutil.rmtree(home, ignore_errors=True)
    os.makedirs(lab, exist_ok=True)
    now = int(time.time())
    recent = now - 2 * 3600
    L = lambda *p: os.path.join(lab, *p)  # noqa: E731
    _w(L("notlar.txt"), NOTES_TXT, mtime=recent)
    _w(L("veri.csv"), DATA_CSV)
    _w(L("isimler.txt"), NAMES_TXT)
    _w(L("sayilar.txt"), NUMBERS_TXT)
    _w(L("bos.txt"), "")
    _w(L("betik.sh"), SCRIPT_SH, mode=0o644)
    _w(L("buyuk.bin"), bytes(range(256)) * 600)          # 153,600 bytes
    _w(L("arsiv.tar.gz"), TAR_GZ)
    _w(L("belgeler", "rapor.txt"), "2024 yili faaliyet raporu\n")
    _w(L("belgeler", "notlar.txt"), DOCS_NOTES_TXT)
    _w(L("belgeler", "taslak.txt"), "taslak metin\n")
    _w(L("belgeler", "sunum.pdf"), b"%PDF-1.4\n%sahte\n")
    _w(L("belgeler", "ozet.docx"), b"PK\x03\x04sahte")
    _w(L("belgeler", ".gizli"), "gizli ayar\n")
    _w(L("belgeler", "eski", "arsiv.dat"), "eski kayitlar\n")
    _w(L("resimler", "tatil.jpg"), b"\xff\xd8\xff\xe0sahte")
    _w(L("resimler", "kapak.jpeg"), b"\xff\xd8\xff\xe0sahte2")
    _w(L("resimler", "profil.png"), b"\x89PNG\r\n\x1a\nsahte")
    _w(L("resimler", "logo.png"), b"\x89PNG\r\n\x1a\nsahte2")
    _w(L("projeler", "hesap.c"), CALC_C)
    _w(L("projeler", "main.c"), MAIN_C)
    _w(L("projeler", "hesap.h"), CALC_H)
    _w(L("projeler", "betik.py"), SCRIPT_PY)
    _w(L("projeler", "test_betik.py"), TEST_PY)
    _w(L("projeler", "Makefile"), MAKEFILE)
    _w(L("projeler", "README.md"), README)
    _w(L("loglar", "app.log"), APP_LOG, mtime=recent)
    _w(L("loglar", "sistem.log"), SYSTEM_LOG)
    _w(L("loglar", "eski.log.1"), "eski log kaydi\n")
    _w(L("gecici", "a.tmp"), "a\n")
    _w(L("gecici", "b.tmp"), "b\n")
    _w(L("gecici", "c.bak"), "c\n")
    _w(L("gecici", "onemli.txt"), "silinmemeli\n")
    for d in ("belgeler/eski", "belgeler", "resimler", "projeler", "loglar", "gecici", "."):
        os.utime(L(d), (OLD, OLD))
    if owner_uid is not None:
        for dp, dns, fns in os.walk(home):
            os.chown(dp, owner_uid, owner_gid)
            for f in fns:
                os.chown(os.path.join(dp, f), owner_uid, owner_gid)
    return lab, home


ARCHIVE_EXT = (".gz", ".tgz", ".zip", ".bz2", ".xz", ".tar")


def snapshot(lab):
    """Converts the file system state under lab into a comparable dictionary.
    Text contents are hashed with trailing whitespace stripped; for archives only
    existence and non-emptiness are checked (because of embedded timestamps)."""
    snap = {}
    for dp, dns, fns in os.walk(lab):
        rel_dir = os.path.relpath(dp, lab)
        for d in dns:
            p = os.path.join(dp, d)
            rel = os.path.normpath(os.path.join(rel_dir, d))
            snap[rel] = ("L", os.readlink(p)) if os.path.islink(p) else ("D",)
        for f in fns:
            p = os.path.join(dp, f)
            rel = os.path.normpath(os.path.join(rel_dir, f))
            if os.path.islink(p):
                snap[rel] = ("L", os.readlink(p))
                continue
            try:
                with open(p, "rb") as fh:
                    data = fh.read()
            except OSError:
                snap[rel] = ("F?",)
                continue
            execb = bool(os.stat(p).st_mode & 0o100)
            if f.endswith(ARCHIVE_EXT):
                snap[rel] = ("A", len(data) > 0)
            else:
                snap[rel] = ("F", hashlib.sha1(data.rstrip()).hexdigest()[:12], execb)
    return snap


def names(lab_template_root):
    """All file/directory base names in the experiment directory (for output normalization)."""
    out = set()
    for dp, dns, fns in os.walk(lab_template_root):
        out.update(dns)
        out.update(fns)
    return out
