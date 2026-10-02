#include "minishell.h"

/*
** risk_reason(): Öneri geri alınması zor bir zarara yol açabilecekse kısa bir
** gerekçe döndürür; bu önerilerde onay için "evet" yazılması istenir.
**
** Kurallar beş sınıfta toplanır:
**   silme      rm, unlink, shred, find -delete / -exec rm, xargs rm, rsync --delete
**   üzerine    > ile ya da cp/mv/ln -f/tee/curl -o/wget -O ile VAR OLAN bir
**   yazma      dosyanın üzerine yazma, sed -i/perl -i, truncate, yıkıcı git işlemleri
**   yetki      sudo/su/doas, özyinelemeli ya da herkese yazılabilir izinler, setuid
**   sistem     disk araçları, /etc /dev /boot /usr yazımı, kapatma, süreç
**              sonlandırma, kullanıcı/güvenlik duvarı/servis/bağlama işlemleri
**   ağ         yerel dosyaları dışarı gönderme (curl -T/-d @, wget --post-file,
**              scp/rsync uzak hedef, nc), indirilen içeriği yorumlayıcıda
**              çalıştırma, başlangıç dosyalarını ve ~/.ssh'yi değiştirme
**
** "Var olan dosya" denetimi, onay istendiği anda kabuğun çalışma dizininde
** stat(2) ile yapılır; yeni bir dosyaya yazmak uyarı üretmez.
** env, nice, nohup, time, timeout ve xargs sarmalayıcılarının içindeki komut
** da aynı kurallarla denetlenir.
*/

#define MAXW 128
#define OP_PIPE 1
#define OP_OUT 2
#define OP_APP 3
#define OP_IN 4
#define OP_HEREDOC 5

typedef struct s_words
{
	char	*w[MAXW];
	int		op[MAXW];
	int		n;
}	t_words;

typedef struct s_seg
{
	char	*a[MAXW];
	int		n;
	int		piped_in;
}	t_seg;

/* ---------------------------------------------------------- sözcüklere bölme */

static void	push(t_words *w, char *buf, int *len, int op)
{
	static const char	*names[] = {"", "|", ">", ">>", "<", "<<"};

	if (w->n >= MAXW)
		return ;
	if (op)
	{
		w->w[w->n] = ft_strdup(names[op]);
		w->op[w->n++] = op;
		return ;
	}
	if (*len == 0)
		return ;
	buf[*len] = '\0';
	w->w[w->n] = ft_strdup(buf);
	w->op[w->n++] = 0;
	*len = 0;
}

static int	op_at(const char *s, int i, int *adv)
{
	*adv = 1;
	if (s[i] == '|')
		return (OP_PIPE);
	if (s[i] == '>' && s[i + 1] == '>')
		return (*adv = 2, OP_APP);
	if (s[i] == '>')
		return (OP_OUT);
	if (s[i] == '<' && s[i + 1] == '<')
		return (*adv = 2, OP_HEREDOC);
	if (s[i] == '<')
		return (OP_IN);
	return (0);
}

/* Tırnakları kaldırarak sözcüklere ve işleçlere böler. */
static void	split_words(const char *s, t_words *w, char *buf)
{
	int		i;
	int		len;
	int		op;
	int		adv;
	char	q;

	i = 0;
	len = 0;
	q = 0;
	w->n = 0;
	while (s[i])
	{
		adv = 1;
		if (q && s[i] == q)
			q = 0;
		else if (q)
			buf[len++] = s[i];
		else if (s[i] == '\'' || s[i] == '"')
			q = s[i];
		else if (s[i] == ' ' || s[i] == '\t' || op_at(s, i, &adv))
		{
			op = op_at(s, i, &adv);
			push(w, buf, &len, 0);
			if (op)
				push(w, buf, &len, op);
		}
		else
			buf[len++] = s[i];
		i += adv;
	}
	push(w, buf, &len, 0);
}

static void	words_free(t_words *w)
{
	while (w->n > 0)
		free(w->w[--w->n]);
}

/* ------------------------------------------------------------- yardımcılar */

static const char	*base(const char *p)
{
	const char	*b;

	b = ft_strrchr(p, '/');
	if (b && b[1])
		return (b + 1);
	return (p);
}

static int	is(const char *a, const char *b)
{
	return (a && b && !ft_strcmp(a, b));
}

static int	in_list(const char *w, const char **list)
{
	int	i;

	i = 0;
	while (list[i])
		if (is(w, list[i++]))
			return (1);
	return (0);
}

static int	starts(const char *w, const char *p)
{
	return (!ft_strncmp(w, p, ft_strlen(p)));
}

/* Kısa seçenek kümesinde (ör. -rf) verilen harflerden biri var mı? */
static int	has_opt(t_seg *g, int from, const char *chars, const char *lng)
{
	int	i;
	int	j;

	i = from;
	while (++i < g->n)
	{
		if (lng && (is(g->a[i], lng)
				|| (starts(g->a[i], lng) && g->a[i][ft_strlen(lng)] == '=')))
			return (1);
		if (g->a[i][0] == '-' && g->a[i][1] && g->a[i][1] != '-')
		{
			j = 0;
			while (g->a[i][++j])
				if (ft_strchr(chars, g->a[i][j]))
					return (1);
		}
	}
	return (0);
}

static int	has_word(t_seg *g, int from, const char *word)
{
	while (++from < g->n)
		if (is(g->a[from], word))
			return (1);
	return (0);
}

/* ~/ ile başlayan yolu HOME ile genişletir (buf en az PATH_MAX). */
static const char	*expand_home(const char *p, char *buf, size_t sz)
{
	const char	*h;

	if (p[0] == '~' && (p[1] == '/' || !p[1]))
	{
		h = getenv("HOME");
		if (!h)
			return (p);
		snprintf(buf, sz, "%s%s", h, p + 1);
		return (buf);
	}
	return (p);
}

static int	existing_file(const char *p)
{
	struct stat	st;
	char		buf[4096];

	p = expand_home(p, buf, sizeof(buf));
	return (stat(p, &st) == 0 && S_ISREG(st.st_mode));
}

static int	existing_dir(const char *p)
{
	struct stat	st;
	char		buf[4096];

	p = expand_home(p, buf, sizeof(buf));
	return (stat(p, &st) == 0 && S_ISDIR(st.st_mode));
}

/* Sistem yolu ya da kullanıcının başlangıç/yapılandırma dosyası mı? */
static const char	*sensitive_path(const char *p)
{
	static const char	*sys[] = {"/etc/", "/boot", "/dev/sd", "/dev/nvme",
		"/dev/hd", "/dev/mmcblk", "/dev/vd", "/usr/", "/bin/", "/sbin/",
		"/lib", "/var/lib/", "/sys/", "/proc/", NULL};
	int					i;
	const char			*b;

	i = 0;
	while (sys[i])
		if (starts(p, sys[i++]))
			return ("sistem dosyasının ya da diskin üzerine yazma");
	if (ft_strnstr(p, ".ssh/", ft_strlen(p)) || is(base(p), ".ssh"))
		return ("SSH anahtarlarını ya da ayarlarını değiştirme");
	b = base(p);
	if (starts(b, "id_rsa") || starts(b, "id_dsa") || starts(b, "id_ecdsa")
		|| starts(b, "id_ed25519") || is(b, "authorized_keys"))
		return ("SSH anahtarlarını ya da ayarlarını değiştirme");
	if (b[0] == '.' && b[1] && b[1] != '.' && b[1] != '/'
		&& (starts(p, "~/") || starts(p, "$HOME/") || b == p
			|| starts(p, "./")))
		return ("başlangıç ya da yapılandırma dosyasını değiştirme");
	return (NULL);
}

/* Bir dosyaya yazılacak (hedef) yol için risk: hassas yol ya da var olan dosya. */
static const char	*write_target(const char *p, int overwrite)
{
	const char	*r;

	if (!p || !*p || is(p, "/dev/null") || is(p, "-")
		|| starts(p, "/dev/std") || starts(p, "/dev/tty"))
		return (NULL);
	r = sensitive_path(p);
	if (r)
		return (r);
	if (overwrite && existing_file(p))
		return ("var olan bir dosyanın üzerine yazma");
	return (NULL);
}

/* ------------------------------------------------------------ komut kuralları */

static const char	*risk_of_seg(t_seg *g, int s, int depth);

/* env, nice, nohup, time, timeout, stdbuf gibi sarmalayıcıları atlar. */
static int	skip_wrappers(t_seg *g, int s)
{
	static const char	*plain[] = {"nohup", "time", "command", "exec",
		"builtin", NULL};
	const char			*c;

	while (s < g->n)
	{
		c = base(g->a[s]);
		if (in_list(c, plain))
			s++;
		else if (is(c, "env") || is(c, "nice") || is(c, "stdbuf")
			|| is(c, "ionice") || is(c, "timeout"))
		{
			s++;
			while (s < g->n && (g->a[s][0] == '-' || ft_strchr(g->a[s], '=')
					|| (is(c, "timeout") && ft_isdigit(g->a[s][0]))))
				s++;
		}
		else
			break ;
	}
	return (s);
}

static const char	*risk_xargs(t_seg *g, int s, int depth)
{
	static const char	*witharg[] = {"-I", "-n", "-P", "-d", "-L", "-s", "-a",
		"-E", "-i", NULL};
	int					i;

	i = s + 1;
	while (i < g->n && g->a[i][0] == '-')
	{
		if (in_list(g->a[i], witharg) && !is(g->a[i], "-i"))
			i++;
		i++;
	}
	if (i >= g->n || depth > 3)
		return (NULL);
	return (risk_of_seg(g, i, depth + 1));
}

/* find -exec/-execdir/-ok ile verilen iç komutu ayrı bir parça olarak denetler. */
static const char	*risk_find(t_seg *g, int s, int depth)
{
	static const char	*bad[] = {"rm", "shred", "unlink", "truncate", "mv",
		NULL};
	t_seg				in;
	const char			*r;
	int					i;

	if (has_word(g, s, "-delete"))
		return ("toplu dosya silme (find -delete)");
	i = s;
	while (++i < g->n)
	{
		if (!(is(g->a[i], "-exec") || is(g->a[i], "-execdir")
				|| is(g->a[i], "-ok") || is(g->a[i], "-okdir")) || i + 1 >= g->n)
			continue ;
		if (in_list(base(g->a[i + 1]), bad))
			return ("toplu dosya silme ya da değiştirme (find -exec)");
		ft_bzero(&in, sizeof(in));
		while (++i < g->n && !is(g->a[i], ";") && !is(g->a[i], "\\;")
			&& !is(g->a[i], "+"))
			in.a[in.n++] = g->a[i];
		r = risk_of_seg(&in, 0, depth + 1);
		if (r)
			return (r);
	}
	return (NULL);
}

static const char	*risk_git(t_seg *g, int s)
{
	if ((has_word(g, s, "reset") && has_word(g, s, "--hard"))
		|| (has_word(g, s, "clean") && has_opt(g, s, "f", "--force"))
		|| (has_word(g, s, "push") && (has_opt(g, s, "f", "--force")
				|| has_word(g, s, "--force-with-lease")))
		|| (has_word(g, s, "checkout") && (has_word(g, s, "--")
				|| has_opt(g, s, "f", "--force") || has_word(g, s, ".")))
		|| has_word(g, s, "restore") || has_word(g, s, "filter-branch")
		|| (has_word(g, s, "branch") && has_opt(g, s, "D", NULL))
		|| (has_word(g, s, "stash") && (has_word(g, s, "drop")
				|| has_word(g, s, "clear"))))
		return ("geri alınamaz git işlemi");
	return (NULL);
}

/* Son işlenen (seçenek olmayan) sözcükler: cp/mv/ln/install hedefi. */
static const char	*risk_copy(t_seg *g, int s, const char *c)
{
	int			ops[MAXW];
	int			n;
	int			i;
	char		p[4096];
	const char	*r;

	if (has_opt(g, s, is(c, "ln") ? "ib" : "nib", "--no-clobber")
		|| has_word(g, s, "--interactive")
		|| has_word(g, s, "--backup") || (is(c, "ln")
			&& !has_opt(g, s, "f", "--force")))
		return (NULL);
	n = 0;
	i = s;
	while (++i < g->n)
		if (g->a[i][0] != '-')
			ops[n++] = i;
	if (n < 2)
		return (NULL);
	r = write_target(g->a[ops[n - 1]], 1);
	if (r || !existing_dir(g->a[ops[n - 1]]))
		return (r);
	i = -1;
	while (++i < n - 1)
	{
		snprintf(p, sizeof(p), "%s/%s", g->a[ops[n - 1]], base(g->a[ops[i]]));
		if (existing_file(p) && !is(p, g->a[ops[i]]))
			return ("var olan bir dosyanın üzerine yazma");
	}
	return (NULL);
}

static const char	*risk_tee(t_seg *g, int s)
{
	const char	*r;
	int			app;
	int			i;

	app = has_opt(g, s, "a", "--append");
	i = s;
	while (++i < g->n)
	{
		if (g->a[i][0] == '-')
			continue ;
		r = write_target(g->a[i], !app);
		if (r)
			return (r);
	}
	return (NULL);
}

static int	upload_arg(const char *a)
{
	return (a && (a[0] == '@' || ft_strnstr(a, "=@", ft_strlen(a))
			|| ft_strnstr(a, "=<", ft_strlen(a))));
}

static const char	*risk_download(t_seg *g, int s, const char *c)
{
	static const char	*data[] = {"-d", "--data", "--data-binary",
		"--data-raw", "--data-urlencode", "-F", "--form", NULL};
	int					i;
	const char			*r;

	i = s;
	while (++i < g->n)
	{
		if (is(g->a[i], "-T") || is(g->a[i], "--upload-file")
			|| (is(c, "curl") && g->a[i][0] == '-' && g->a[i][1] != '-'
				&& ft_strchr(g->a[i], 'T'))
			|| is(g->a[i], "--post-file") || is(g->a[i], "--body-file")
			|| starts(g->a[i], "--post-file=")
			|| (in_list(g->a[i], data) && i + 1 < g->n
				&& upload_arg(g->a[i + 1]))
			|| ((starts(g->a[i], "-d@") || starts(g->a[i], "-F")) && upload_arg(g->a[i] + 2)))
			return ("yerel dosyayı ağ üzerinden gönderme");
		if (i + 1 < g->n && ((is(c, "curl") && (is(g->a[i], "-o")
						|| is(g->a[i], "--output"))) || (is(c, "wget")
					&& (is(g->a[i], "-O") || is(g->a[i], "--output-document")))))
		{
			r = write_target(g->a[i + 1], 1);
			if (r)
				return (r);
		}
	}
	return (NULL);
}

static int	remote_arg(const char *a)
{
	const char	*colon;

	colon = ft_strchr(a, ':');
	return (a[0] != '/' && a[0] != '.' && a[0] != '-' && colon
		&& colon != a && !ft_strchr(a, '='));
}

static const char	*risk_remote_copy(t_seg *g, int s, const char *c)
{
	int	last;
	int	i;
	int	n;

	if (is(c, "rsync") && (has_word(g, s, "--delete")
			|| has_word(g, s, "--delete-after") || has_word(g, s, "--delete-before")
			|| has_word(g, s, "--remove-source-files")))
		return ("eşitlemede dosya silme (rsync --delete)");
	last = -1;
	i = s;
	while (++i < g->n)
		if (g->a[i][0] != '-')
			last = i;
	i = s;
	n = 0;
	while (++i < g->n)
		n += (g->a[i][0] != '-');
	if (n >= 2 && remote_arg(g->a[last]))
		return ("yerel dosyaları uzak sunucuya gönderme");
	return (NULL);
}

static int	octal_setid_or_world(const char *a)
{
	int	i;
	int	n;

	n = ft_strlen(a);
	if (n < 3 || n > 4)
		return (0);
	i = -1;
	while (a[++i])
		if (a[i] < '0' || a[i] > '7')
			return (0);
	if (n == 4 && a[0] != '0')
		return (1);
	return (a[n - 1] == '7' || a[n - 1] == '6' || a[n - 1] == '3'
		|| a[n - 1] == '2');
}

static const char	*risk_perm(t_seg *g, int s, const char *c)
{
	int			i;
	int			first;
	const char	*a;

	if (has_opt(g, s, "R", "--recursive") || has_word(g, s, "/"))
		return ("özyinelemeli izin/sahiplik değişikliği");
	i = s;
	while (++i < g->n)
		if (ft_strnstr(g->a[i], "$(", ft_strlen(g->a[i]))
			|| ft_strchr(g->a[i], '`'))
			return ("birçok dosyada toplu izin değişikliği");
	first = 1;
	i = s;
	while (++i < g->n)
	{
		a = g->a[i];
		if (a[0] == '-')
			continue ;
		if (first && is(c, "chmod") && (octal_setid_or_world(a)
				|| ft_strnstr(a, "+s", ft_strlen(a))
				|| ft_strnstr(a, "o+w", ft_strlen(a))
				|| ft_strnstr(a, "a+w", ft_strlen(a))
				|| is(a, "+w")))
			return ("herkese yazma ya da setuid izni verme");
		first = 0;
		if (a[0] == '/' && sensitive_path(a))
			return ("sistem dosyasının izinlerini değiştirme");
	}
	return (NULL);
}

/* sed -i (yedek son eki olmadan) ya da --in-place (son eksiz) */
static int	sed_inplace_nobackup(t_seg *g, int s)
{
	int			i;
	const char	*a;
	const char	*p;

	i = s;
	while (++i < g->n)
	{
		a = g->a[i];
		if (is(a, "--in-place"))
			return (1);
		if (a[0] != '-' || a[1] == '-')
			continue ;
		p = ft_strchr(a, 'i');
		if (p && (p[1] == '\0' || p[1] == 'E' || p[1] == 'r' || p[1] == 'n'
				|| p[1] == 's' || p[1] == 'u' || p[1] == 'z'))
			return (1);
	}
	return (0);
}

static const char	*risk_inplace(t_seg *g, int s, const char *c)
{
	int	i;

	if (is(c, "sed") && sed_inplace_nobackup(g, s))
		return ("dosyayı yerinde değiştirme (sed -i)");
	if (is(c, "dos2unix") || is(c, "unix2dos"))
		return ("dosyayı yerinde dönüştürme");
	if (is(c, "perl") && has_opt(g, s, "i", NULL))
		return ("dosyayı yerinde değiştirme (perl -i)");
	i = s;
	while ((is(c, "awk") || is(c, "gawk")) && ++i < g->n - 1)
		if (is(g->a[i], "-i") && is(g->a[i + 1], "inplace"))
			return ("dosyayı yerinde değiştirme (awk -i inplace)");
	return (NULL);
}

static int	dd_writes(t_seg *g, int s)
{
	int	i;

	i = s;
	while (++i < g->n)
		if (starts(g->a[i], "of=") && !is(g->a[i], "of=/dev/null"))
			return (1);
	return (0);
}

static const char	*risk_system(t_seg *g, int s, const char *c)
{
	static const char	*disk[] = {"dd", "mkfs", "fdisk", "sfdisk", "parted",
		"wipefs", "mkswap", "swapoff", "mount", "umount", "losetup", NULL};
	static const char	*power[] = {"shutdown", "reboot", "halt", "poweroff",
		"init", "telinit", NULL};
	static const char	*acct[] = {"userdel", "usermod", "useradd", "groupdel",
		"passwd", "chpasswd", "visudo", "chattr", "rmmod", "insmod", NULL};
	static const char	*svc[] = {"stop", "disable", "mask", "kill", "poweroff",
		"reboot", "halt", NULL};

	if ((in_list(c, disk) && !is(c, "dd") && g->n - s > 1)
		|| starts(c, "mkfs") || (is(c, "dd") && dd_writes(g, s)))
		return ("disk ya da dosya sistemi işlemi (dd/mkfs/mount)");
	if (in_list(c, power))
		return ("sistemi kapatma ya da yeniden başlatma");
	if (in_list(c, acct) || (is(c, "modprobe") && has_opt(g, s, "r", "--remove"))
		|| (is(c, "sysctl") && has_opt(g, s, "w", "--write")))
		return ("hesap, çekirdek ya da sistem ayarı değişikliği");
	if ((is(c, "systemctl") || is(c, "service")) && (has_word(g, s, svc[0])
			|| has_word(g, s, svc[1]) || has_word(g, s, svc[2])
			|| has_word(g, s, svc[3]) || has_word(g, s, svc[4])
			|| has_word(g, s, svc[5]) || has_word(g, s, svc[6])))
		return ("servisi durdurma ya da sistemi kapatma");
	if ((is(c, "iptables") || is(c, "ip6tables") || is(c, "nft"))
		&& (has_opt(g, s, "FX", "--flush") || has_word(g, s, "flush")))
		return ("güvenlik duvarı kurallarını silme");
	if (is(c, "ufw") && (has_word(g, s, "disable") || has_word(g, s, "reset")))
		return ("güvenlik duvarını kapatma");
	if (is(c, "kill") || is(c, "killall") || is(c, "pkill"))
		return ("süreç sonlandırma");
	if (is(c, "crontab") && has_opt(g, s, "r", NULL))
		return ("zamanlanmış görevleri silme (crontab -r)");
	return (NULL);
}

static const char	*risk_interp(t_seg *g, int s, const char *c)
{
	static const char	*interp[] = {"sh", "bash", "zsh", "dash", "ksh",
		"python", "python3", "perl", "ruby", "node", "php", NULL};
	int					i;

	if (!g->piped_in || !in_list(c, interp))
		return (NULL);
	i = s;
	while (++i < g->n)
		if (g->a[i][0] != '-')
			return (NULL);
	return ("boru hattından gelen içeriği yorumlayıcıda çalıştırma (| sh)");
}

const char	*risk_reason_depth(const char *cmd, int depth);

/* sh -c "komut" ve ssh sunucu "komut" biçimindeki gömülü komutlar. */
static const char	*risk_embedded(t_seg *g, int s, const char *c, int depth)
{
	static const char	*sh[] = {"sh", "bash", "zsh", "dash", "ksh", NULL};
	int					i;

	if (depth > 3)
		return (NULL);
	i = s;
	while (in_list(c, sh) && ++i < g->n - 1)
		if (is(g->a[i], "-c"))
			return (risk_reason_depth(g->a[i + 1], depth + 1));
	if (!is(c, "ssh"))
		return (NULL);
	i = s;
	while (++i < g->n)
		if (ft_strchr(g->a[i], ' '))
			return (risk_reason_depth(g->a[i], depth + 1));
	return (NULL);
}

static const char	*risk_of_seg(t_seg *g, int s, int depth)
{
	static const char	*net[] = {"nc", "ncat", "netcat", "socat", NULL};
	const char			*c;
	const char			*r;

	s = skip_wrappers(g, s);
	if (s >= g->n)
		return (NULL);
	c = base(g->a[s]);
	if (is(c, "sudo") || is(c, "su") || is(c, "doas") || is(c, "pkexec"))
		return ("yönetici yetkisiyle çalıştırma (sudo/su)");
	if (is(c, "rm"))
	{
		if (has_opt(g, s, "rRf", "--recursive") || has_word(g, s, "--force"))
			return ("özyinelemeli ya da zorla dosya silme (rm -r/-f)");
		return ("dosya silme (rm)");
	}
	if (depth > 0 && (is(c, "mv") || is(c, "chmod") || is(c, "chown")
			|| is(c, "chgrp")))
		return ("birçok dosyada toplu taşıma ya da izin değişikliği");
	if (is(c, "rename") || is(c, "prename") || is(c, "perl-rename"))
		return ("toplu yeniden adlandırma");
	if (is(c, "unlink") || is(c, "shred") || is(c, "srm") || is(c, "wipe"))
		return ("dosya silme ya da imha etme");
	if (is(c, "truncate"))
		return ("dosya içeriğini silme (truncate)");
	if (is(c, "xargs"))
		return (risk_xargs(g, s, depth));
	if (is(c, "find"))
		return (risk_find(g, s, depth));
	if (is(c, "git"))
		return (risk_git(g, s));
	if (is(c, "chmod") || is(c, "chown") || is(c, "chgrp"))
		return (risk_perm(g, s, c));
	if (is(c, "cp") || is(c, "mv") || is(c, "ln") || is(c, "install"))
		return (risk_copy(g, s, c));
	if (is(c, "tee"))
		return (risk_tee(g, s));
	if (is(c, "curl") || is(c, "wget"))
		return (risk_download(g, s, c));
	if (is(c, "scp") || is(c, "rsync"))
		return (risk_remote_copy(g, s, c));
	if (in_list(c, net))
		return ("ağ bağlantısı üzerinden veri aktarma (nc)");
	if (is(c, "ssh") && g->piped_in)
		return ("yerel veriyi uzak sunucuya gönderme (| ssh)");
	r = risk_embedded(g, s, c, depth);
	if (r)
		return (r);
	r = risk_inplace(g, s, c);
	if (!r)
		r = risk_system(g, s, c);
	if (!r)
		r = risk_interp(g, s, c);
	return (r);
}

/* ------------------------------------------------------------------ giriş */

static const char	*scan(t_words *w, int depth)
{
	t_seg		g;
	const char	*r;
	int			i;

	ft_bzero(&g, sizeof(g));
	i = 0;
	while (i <= w->n)
	{
		if (i == w->n || w->op[i] == OP_PIPE)
		{
			r = risk_of_seg(&g, 0, depth);
			if (r)
				return (r);
			g.n = 0;
			g.piped_in = 1;
		}
		else if ((w->op[i] == OP_OUT || w->op[i] == OP_APP) && i + 1 < w->n
			&& !w->op[i + 1])
		{
			r = write_target(w->w[i + 1], w->op[i] == OP_OUT);
			if (r)
				return (r);
			i++;
		}
		else if (w->op[i] && i + 1 < w->n && !w->op[i + 1])
			i++;
		else if (!w->op[i])
			g.a[g.n++] = w->w[i];
		i++;
	}
	return (NULL);
}

const char	*risk_reason_depth(const char *cmd, int depth)
{
	t_words		w;
	char		*buf;
	const char	*r;

	if (!cmd)
		return (NULL);
	if (ft_strnstr(cmd, ":(){", ft_strlen(cmd))
		|| ft_strnstr(cmd, ":() {", ft_strlen(cmd)))
		return ("çatallanma bombası");
	buf = malloc(ft_strlen(cmd) + 1);
	if (!buf)
		return (NULL);
	split_words(cmd, &w, buf);
	free(buf);
	r = scan(&w, depth);
	words_free(&w);
	return (r);
}

const char	*risk_reason(const char *cmd)
{
	return (risk_reason_depth(cmd, 0));
}
