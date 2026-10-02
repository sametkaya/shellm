# -*- coding: utf-8 -*-
"""Independent (held-out) validation suite.

Written after the v2 fixes were complete, without seeing v2's output on these
tests; neither the tests nor the code were changed in response to the results.
The purpose is to check for overfitting to the main test suite. The category
letters are the same as in the main suite.
"""
from cases import CATEGORIES  # noqa: F401

_CASES = [
    ("Ah01", "echo a b c | wc -w"),
    ("Ah02", "cd d > o.txt\npwd"),
    ("Ah03", "export V=1\nexport V=2\necho $V"),
    ("Ah04", 'echo -n ""'),
    ("Ah05", "cd ..\ncd -\npwd"),
    ("Ah06", "env | grep -c ZVAR"),
    ("Ah07", "exit 256"),
    ("Ah08", "exit -1"),
    ("Bh01", "ls -1 d | head -1"),
    ("Bh02", "/usr/bin/env | grep ZVAR"),
    ("Bh03", "./run.sh > o.txt\ncat o.txt"),
    ("Bh04", "sh -c 'exit 300'\necho $?"),
    ("Bh05", "cd d\n../run.sh\necho $?"),
    ("Bh06", "boyle_bir_komut_yok arg1 arg2\necho $?"),
    ("Ch01", "echo x | cat | wc -l"),
    ("Ch02", "ls d | grep c | wc -l"),
    ("Ch03", "cat a.txt | head -2 | tail -1"),
    ("Ch04", "echo abc | cat > o.txt | cat\ncat o.txt"),
    ("Ch05", "cd d | pwd"),
    ("Ch06", "export Z=1 | env | grep -c ^Z="),
    ("Ch07", "false\necho $? | cat"),
    ("Ch08", "cat < a.txt | sort | head -1"),
    ("Dh01", "echo a > o.txt\ncat < o.txt > o2.txt\ncat o2.txt"),
    ("Dh02", 'echo $ZVAR > "$ZVAR.txt"\ncat zzz.txt'),
    ("Dh03", "wc -l < a.txt > o.txt\ncat o.txt"),
    ("Dh04", "echo hi > o.txt extra\ncat o.txt"),
    ("Dh05", "cat < d\necho $?"),
    ("Dh06", "echo x >> new.txt\necho y >> new.txt\ncat new.txt"),
    ("Dh07", "ls > o.txt\ngrep -c txt o.txt"),
    ("Eh01", "cat << END | tr a-z A-Z\nmerhaba\nEND"),
    ("Eh02", "cat << EOF\n$HOME\nEOF"),
    ("Eh03", "cat << E1 > o.txt\nsatir\nE1\nwc -l < o.txt"),
    ("Eh04", "cat << EOF\na b   c\nEOF"),
    ("Eh05", "grep elma << EOF\nelma\narmut\nEOF"),
    ("Fh01", "echo \"$ZVAR\"'$ZVAR'\"$ZVAR\""),
    ("Fh02", 'echo "a|b"'),
    ("Fh03", "echo 'a > b'"),
    ("Fh04", 'echo "$ZVAR" | cat'),
    ("Fh05", 'echo "   " | wc -c'),
    ("Fh06", "echo $ZVAR$YOK$ZVAR"),
    ("Fh07", 'echo "$?"'),
    ("Fh08", "echo x\"y\"'z'"),
    ("Hh01", "cat <"),
    ("Hh02", "echo a | >"),
    ("Hh03", "ls >>"),
    ("Ih01", "export P=/tmp\ncd $P\npwd"),
    ("Ih02", "unset HOME\ncd\necho $?"),
    ("Ih03", "export A=x\nsh -c 'echo $A'"),
    ("Ih04", "unset ZVAR AAA_FIRST\nenv | grep -c -e ZVAR -e AAA_FIRST"),
    ("Ih05", "export EMPTY=\nenv | grep EMPTY"),
    ("Jh01", "ls *.txt | wc -l"),
    ("Jh02", "echo d/*.[ch]"),
    ("Jh03", "cat ~/Desktop/*.txt"),
    ("Jh04", "echo ~/Desktop"),
    ("Jh05", "echo '~/x'"),
    ("Jh06", "echo x*y"),
    ("Jh07", "cd ~/Desktop\nls"),
]

CASES = [{"id": cid, "cat": cid[0], "script": s + "\n"} for cid, s in _CASES]
