# Mock server compatible with the v1 protocol: TCP 127.0.0.1:12345, a single recv(1024)
import socket, difflib, os, time
names=set(["echo","cd","pwd","export","unset","env","exit"])
for d in os.environ.get("PATH","").split(":"):
    try:
        for n in os.listdir(d): names.add(n)
    except OSError: pass
names=sorted(names)
delay=float(os.environ.get("SHELLM_MOCK_DELAY","0"))
big=int(os.environ.get("MOCK_BIG","0"))
s=socket.socket(); s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR,1)
s.bind(("127.0.0.1",12345)); s.listen(5)
while True:
    c,_=s.accept(); data=c.recv(1024).decode()
    if delay: time.sleep(delay)
    w=data.split(" ",1); m=difflib.get_close_matches(w[0],names,n=1,cutoff=0.6)
    # "#ERROR: yok" ("none") is the reply v1 receives when nothing matches; kept as is
    out=(" ".join([m[0]]+w[1:]) if m else "#ERROR: yok")
    if big: out = "echo " + "x"*big
    if os.environ.get("MOCK_FIXED"): out = os.environ["MOCK_FIXED"]
    c.send(out.encode()); c.close()
