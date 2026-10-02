# -*- coding: utf-8 -*-
"""Differential compatibility test suite comparing SheLLM with Bash.

Each test is a script fed on standard input to Bash and to SheLLM in the same
fixture directory. Standard output, the last exit status and whether standard
error is empty are compared.

Categories:
  A  Builtin commands
  B  External commands, PATH and exit statuses
  C  Pipelines
  D  Redirections
  E  Here documents (heredoc)
  F  Quoting and variable expansion
  H  Syntax errors
  I  Environment variables
  J  Tilde (~) and glob expansion               [feature added in v2]
  L  Out-of-scope Bash syntax                   [supported by neither version]
"""

CATEGORIES = {
    "A": "Builtin commands",
    "B": "External commands and exit statuses",
    "C": "Pipelines",
    "D": "Redirections",
    "E": "Here documents (heredoc)",
    "F": "Quoting and expansion",
    "H": "Syntax errors",
    "I": "Environment variables",
    "J": "Tilde and glob expansion",
    "L": "Out-of-scope Bash syntax",
}

# (id, script); the scripts and their Turkish words are test data
_CASES = [
    # ---------------- A: builtin commands ----------------
    ("A01", "echo merhaba dünya"),
    ("A02", "echo -n abc"),
    ("A03", "echo -n -n -nnn x"),
    ("A04", "echo -nx y"),
    ("A05", "echo"),
    ("A06", 'echo "a   b"   c'),
    ("A07", "pwd"),
    ("A08", "cd d\npwd"),
    ("A09", "cd d\ncd ..\npwd"),
    ("A10", "cd /olmayan_dizin\necho $?"),
    ("A11", "cd\npwd"),
    ("A12", "cd a.txt\necho $?"),
    ("A13", "cd d\ncd -\npwd"),
    ("A14", "export X=42\necho $X"),
    ("A15", "export A=1 B=2\necho $A$B"),
    ("A16", "export 1A=x\necho $?"),
    ("A17", 'unset ZVAR\necho "[$ZVAR]"'),
    ("A18", "echo bir\nexit 7\necho iki"),
    ("A19", "ls olmayan_dosya\nexit"),
    ("A20", "exit abc"),
    ("A21", "exit 1 2\necho devam"),
    ("A22", "env | grep ZVAR"),
    ("A23", "cd d e\necho $?"),
    # ---------------- B: external commands ----------------
    ("B01", "ls d"),
    ("B02", "/bin/echo mutlak yol"),
    ("B03", "./run.sh\necho $?"),
    ("B04", "boyle_bir_komut_yok"),
    ("B05", "boyle_bir_komut_yok\necho $?"),
    ("B06", "./noexec.sh\necho $?"),
    ("B07", "./d\necho $?"),
    ("B08", "./yok.sh\necho $?"),
    ("B09", "wc -l a.txt"),
    ("B10", 'echo x\n""\necho $?'),
    ("B11", "sh -c 'exit 5'\necho $?"),
    ("B12", "sh -c 'kill -TERM $$'\necho $?"),
    ("B13", "sh -c 'kill -KILL $$'\necho $?"),
    ("B14", "unset PATH\nls\necho $?"),
    ("B15", "/bin/echo a | /bin/cat"),
    ("B16", "./run.sh | cat"),
    ("B17", "./noexec.sh | cat\necho $?"),
    # ---------------- C: pipelines ----------------
    ("C01", "cat a.txt | grep elma"),
    ("C02", "cat a.txt | sort | uniq -c"),
    ("C03", "cat a.txt | grep -c elma"),
    ("C04", "echo a | cat | cat | cat | cat"),
    ("C05", "ls d | wc -l"),
    ("C06", "echo merhaba | tr a-z A-Z"),
    ("C07", "false | true\necho $?"),
    ("C08", "true | false\necho $?"),
    ("C09", "boyle_bir_komut_yok | cat\necho $?"),
    ("C10", "cat a.txt | boyle_bir_komut_yok\necho $?"),
    ("C11", "yes | head -3"),
    ("C12", "echo test | cat > out.txt\ncat out.txt"),
    ("C13", "export | grep ZVAR"),
    ("C14", "pwd | cat"),
    ("C15", "echo abc | wc -c"),
    ("C16", "cat < a.txt | head -1"),
    # ---------------- D: redirections ----------------
    ("D01", "echo x > o.txt\ncat o.txt"),
    ("D02", "echo 1 > o.txt\necho 2 >> o.txt\ncat o.txt"),
    ("D03", "echo 1 > o.txt\necho 2 > o.txt\ncat o.txt"),
    ("D04", "wc -l < a.txt"),
    ("D05", "cat < yok.txt\necho $?"),
    ("D06", "< a.txt cat"),
    ("D07", "> o.txt echo hi\ncat o.txt"),
    ("D08", "echo hi > o1.txt > o2.txt\ncat o1.txt o2.txt"),
    ("D09", "cat < a.txt > o.txt\ncat o.txt"),
    ("D10", "echo hi > d\necho $?"),
    ("D11", "> bos.txt\nls bos.txt"),
    ("D12", "echo hi >> a.txt\ntail -1 a.txt"),
    ("D13", "cat a.txt b.txt > o.txt\nwc -l < o.txt"),
    ("D14", "pwd > o.txt\ncat o.txt"),
    ("D15", 'echo a > "bosluklu ad.txt"\ncat "bosluklu ad.txt"'),
    ("D16", "cat < yok.txt > o.txt\nls o.txt"),
    # ---------------- E: heredoc ----------------
    ("E01", "cat << EOF\na\nb\nEOF"),
    ("E02", "cat << EOF\n$ZVAR\nEOF"),
    ("E03", "cat << 'EOF'\n$ZVAR\nEOF"),
    ("E04", 'cat << "EOF"\n$ZVAR\nEOF'),
    ("E05", "cat << EOF | wc -l\n1\n2\nEOF"),
    ("E06", "cat << A << B\nx\nA\ny\nB"),
    ("E07", "cat << EOF > o.txt\nz\nEOF\ncat o.txt"),
    ("E08", "cat << EOF\nson satir"),
    ("E09", "cat << EOF\n\"$ZVAR\" '$ZVAR'\nEOF"),
    # ---------------- F: quoting and expansion ----------------
    ("F01", "echo 'tek $ZVAR'"),
    ("F02", 'echo "cift $ZVAR"'),
    ("F03", "echo \"$ZVAR\"x'$ZVAR'"),
    ("F04", "echo $YOK_DEGISKEN a"),
    ("F05", 'echo "[$YOK]"'),
    ("F06", "echo $"),
    ("F07", 'echo "$"'),
    ("F08", "false\necho $?"),
    ("F09", "echo '\"' \"'\""),
    ("F10", "echo \"a'b'c\""),
    ("F11", "echo ''"),
    ("F12", 'echo a""b'),
    ("F13", 'echo "$ZVAR$ZVAR"'),
    ("F14", "echo $1"),
    ("F15", "echo $ZVAR.txt"),
    ("F16", 'echo "$ZVAR\'"'),
    ("F17", "echo $HOME/x"),
    ("F18", 'echo "$USER"'),
    ("F19", 'echo "kapanmayan'),
    # ---------------- H: syntax errors ----------------
    ("H01", "| ls"),
    ("H02", "ls | | wc"),
    ("H03", "echo >"),
    ("H04", "echo > > o.txt"),
    ("H05", "cat <<"),
    ("H06", "echo tamam\n| ls"),
    ("H07", "<"),
    # ---------------- I: environment variables ----------------
    ("I01", "unset AAA_FIRST\necho $HOME"),
    ("I02", "unset AAA_FIRST\nenv | grep ZVAR"),
    ("I03", "export YENI=5\nenv | grep YENI"),
    ("I04", "export YENI\nenv | grep -c YENI"),
    ("I05", "export ZVAR=yeni\necho $ZVAR"),
    ("I06", "export ZVAR=yeni\nsh -c 'echo $ZVAR'"),
    ("I07", "unset ZVAR\nsh -c 'echo [$ZVAR]'"),
    ("I08", 'export A=1\nunset A\necho "[$A]"'),
    ("I09", "export | grep AAA_FIRST"),
    ("I10", "cd d\necho $PWD"),
    ("I11", "cd d\nsh -c pwd"),
    ("I12", "unset AAA_FIRST\nexport YENI=1\nenv | grep YENI"),
    # ---------------- J: tilde and glob ----------------
    ("J01", "echo ~"),
    ("J02", "ls ~/Desktop"),
    ("J03", "echo *.txt"),
    ("J04", "ls d/*.c"),
    ("J05", 'echo "*.txt"'),
    ("J06", "echo '*'"),
    ("J07", "echo *.yok"),
    ("J08", 'find ~/Desktop -name "*.pdf"'),
    ("J09", "cat ~/Desktop/not.txt"),
    ("J10", "echo d/?.c"),
    ("J11", 'echo "~"'),
    ("J12", 'echo ~/a"b"'),
    ("J13", "cd ~\npwd"),
    ("J14", "echo [ab].txt"),
    ("J15", "echo *.txt d/*.c"),
    # ---------------- L: out-of-scope Bash syntax ----------------
    ("L01", "echo a; echo b"),
    ("L02", "true && echo ok"),
    ("L03", "false || echo yedek"),
    ("L04", "echo $(echo ic)"),
    ("L05", "ls yok 2> /dev/null\necho $?"),
    ("L06", "(cd d; pwd)"),
    ("L07", 'export Q="a   b"\necho $Q'),
    ("L08", "echo \\$ZVAR"),
    ("L09", "echo {a,b}"),
    ("L10", "x=5\necho $x"),
    ("L11", "echo `echo ic`"),
]

CASES = [{"id": cid, "cat": cid[0], "script": s + "\n"} for cid, s in _CASES]
