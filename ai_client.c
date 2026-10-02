#include "minishell.h"
#include <sys/socket.h>
#include <sys/un.h>
#include <sys/time.h>
#include <time.h>

/*
** SheLLM v2: AI bridge (C side).
**
** Changes over v1:
**  - A Unix domain socket in a private directory (mkdtemp, mode 0700) replaces
**    TCP 127.0.0.1:12345. Other users on the same machine cannot connect to
**    the service or replace suggestions with a fake server, and several SheLLM
**    instances no longer collide. The v1 code that killed any process holding
**    the port with "fuser" was removed.
**  - Message framing: request and reply are single lines ending in '\n' (the
**    request is JSON). The fixed 1024-byte buffer of v1, and its unchecked
**    buffer[valread] write (overflow / buffer[-1]), are gone.
**  - Timeout (SHELLM_AI_TIMEOUT, default 20 s) and cancellation with Ctrl+C.
**  - The helper runs in its own session (setsid); in v1, Ctrl+C at the prompt
**    also killed the Python process in the same process group.
**  - A readiness check (ping) replaces the fixed sleep(1) at startup.
**  - The helper script is found relative to the executable, not the current
**    working directory (see ai_find_helper).
*/

static volatile sig_atomic_t	g_ai_cancel = 0;

static void	ai_sigint(int sig)
{
	(void)sig;
	g_ai_cancel = 1;
}

char	*json_escape(const char *s)
{
	char	*out;
	size_t	i;
	size_t	j;

	out = malloc(ft_strlen(s) * 6 + 3);
	if (!out)
		return (NULL);
	i = 0;
	j = 0;
	out[j++] = '"';
	while (s[i])
	{
		if (s[i] == '"' || s[i] == '\\')
		{
			out[j++] = '\\';
			out[j++] = s[i];
		}
		else if ((unsigned char)s[i] < 0x20)
			j += snprintf(out + j, 7, "\\u%04x", (unsigned char)s[i]);
		else
			out[j++] = s[i];
		i++;
	}
	out[j++] = '"';
	out[j] = '\0';
	return (out);
}

static long	now_ms(void)
{
	struct timespec	ts;

	clock_gettime(CLOCK_MONOTONIC, &ts);
	return (ts.tv_sec * 1000L + ts.tv_nsec / 1000000L);
}

static int	ai_connect(t_shell *shell, int timeout_sec)
{
	int					fd;
	struct sockaddr_un	addr;
	struct timeval		tv;

	if (!shell->ai_socket)
		return (-1);
	fd = socket(AF_UNIX, SOCK_STREAM, 0);
	if (fd < 0)
		return (-1);
	ft_bzero(&addr, sizeof(addr));
	addr.sun_family = AF_UNIX;
	ft_strlcpy(addr.sun_path, shell->ai_socket, sizeof(addr.sun_path));
	if (connect(fd, (struct sockaddr *)&addr, sizeof(addr)) < 0)
		return (close(fd), -1);
	tv.tv_sec = timeout_sec;
	tv.tv_usec = 0;
	setsockopt(fd, SOL_SOCKET, SO_RCVTIMEO, &tv, sizeof(tv));
	setsockopt(fd, SOL_SOCKET, SO_SNDTIMEO, &tv, sizeof(tv));
	return (fd);
}

static int	send_all(int fd, const char *s)
{
	size_t	len;
	ssize_t	w;

	len = ft_strlen(s);
	while (len > 0)
	{
		w = send(fd, s, len, MSG_NOSIGNAL);
		if (w <= 0)
			return (-1);
		s += w;
		len -= (size_t)w;
	}
	return (0);
}

/* Reads one line ending in '\n' (at most 64 KB). */
static char	*recv_line(int fd)
{
	char	*buf;
	size_t	len;
	ssize_t	r;

	buf = malloc(65536);
	if (!buf)
		return (NULL);
	len = 0;
	while (len < 65535)
	{
		r = recv(fd, buf + len, 1, 0);
		if (r <= 0)
			return (free(buf), NULL);
		if (buf[len] == '\n')
			break ;
		len++;
	}
	buf[len] = '\0';
	return (buf);
}

/* Reply format: "OK\t<text>" | "NONE\t" | "ERR\t<message>" */
static int	parse_reply(char *line, t_ai_reply *reply)
{
	char	*tab;

	tab = ft_strchr(line, '\t');
	reply->text = ft_strdup(tab ? tab + 1 : "");
	if (!ft_strncmp(line, "OK\t", 3))
		reply->ok = 1;
	else
		reply->ok = 0;
	return (reply->ok);
}

static int	timeout_seconds(void)
{
	char	*t;
	int		v;

	t = getenv("SHELLM_AI_TIMEOUT");
	if (!t)
		return (20);
	v = ft_atoi(t);
	if (v <= 0)
		return (20);
	return (v);
}

/*
** Returns: 1 suggestion available, 0 no suggestion or error (reply->text
**          explains), -1 cancelled or timed out.
*/
int	ai_request(t_shell *shell, const char *input, int exit_code,
		t_ai_reply *reply)
{
	struct sigaction	sa;
	struct sigaction	old;
	char				*msg;
	char				*line;
	char				*e_in;
	char				*e_cwd;
	char				cwd[4096];
	int					fd;

	reply->ok = 0;
	reply->text = NULL;
	fd = ai_connect(shell, timeout_seconds());
	if (fd < 0)
		return (0);
	if (!getcwd(cwd, sizeof(cwd)))
		cwd[0] = '\0';
	e_in = json_escape(input);
	e_cwd = json_escape(cwd);
	msg = malloc(ft_strlen(e_in) + ft_strlen(e_cwd) + 96);
	if (!msg || !e_in || !e_cwd)
		return (free(msg), free(e_in), free(e_cwd), close(fd), 0);
	sprintf(msg, "{\"op\":\"suggest\",\"input\":%s,\"cwd\":%s,\"exit_code\":%d}\n",
		e_in, e_cwd, exit_code);
	free(e_in);
	free(e_cwd);
	ft_bzero(&sa, sizeof(sa));
	sa.sa_handler = ai_sigint;
	sigemptyset(&sa.sa_mask);
	sa.sa_flags = 0;
	g_ai_cancel = 0;
	sigaction(SIGINT, &sa, &old);
	line = NULL;
	if (send_all(fd, msg) == 0)
		line = recv_line(fd);
	sigaction(SIGINT, &old, NULL);
	free(msg);
	close(fd);
	if (!line)
		return (-1);
	parse_reply(line, reply);
	free(line);
	return (reply->ok);
}

/* ------------------------------------------------------------------ */

#ifndef SHELLM_DATADIR
# define SHELLM_DATADIR "/usr/local/share/shellm"
#endif

/*
** ai_helper.py is searched in this order: SHELLM_HELPER; next to the
** executable (build in the source tree); ../share/shellm (relocatable install,
** e.g. ~/.local/bin -> ~/.local/share/shellm); SHELLM_DATADIR given at build
** time. The current directory is deliberately not searched: a shell started
** in an untrusted directory must not run an ai_helper.py placed there.
*/
static char	*helper_beside_exe(const char *rel)
{
	char	exe[4096];
	char	*slash;
	ssize_t	n;

	n = readlink("/proc/self/exe", exe, sizeof(exe) - 64);
	if (n <= 0)
		return (NULL);
	exe[n] = '\0';
	slash = ft_strrchr(exe, '/');
	if (!slash)
		return (NULL);
	ft_strlcpy(slash + 1, rel, 64);
	if (access(exe, R_OK) == 0)
		return (ft_strdup(exe));
	return (NULL);
}

char	*ai_find_helper(void)
{
	char	*env;
	char	*p;

	env = getenv("SHELLM_HELPER");
	if (env && access(env, R_OK) == 0)
		return (ft_strdup(env));
	p = helper_beside_exe("ai_helper.py");
	if (!p)
		p = helper_beside_exe("../share/shellm/ai_helper.py");
	if (!p && access(SHELLM_DATADIR "/ai_helper.py", R_OK) == 0)
		p = ft_strdup(SHELLM_DATADIR "/ai_helper.py");
	return (p);
}

static void	spawn_helper(const char *helper, t_shell *shell)
{
	int		fd;
	char	*log;

	setsid();
	signal(SIGINT, SIG_IGN);
	signal(SIGQUIT, SIG_IGN);
	fd = open("/dev/null", O_RDONLY);
	if (fd >= 0)
		dup2(fd, STDIN_FILENO);
	log = ft_strjoin(shell->ai_dir, "/ai.log");
	fd = open(log, O_WRONLY | O_CREAT | O_TRUNC, 0600);
	if (fd >= 0)
	{
		dup2(fd, STDOUT_FILENO);
		dup2(fd, STDERR_FILENO);
		close(fd);
	}
	execlp("python3", "python3", helper, "--socket", shell->ai_socket,
		(char *)NULL);
	_exit(127);
}

static void	set_status(t_shell *shell, const char *s)
{
	ft_strlcpy(shell->ai_status, s, sizeof(shell->ai_status));
}

static void	wait_ready(t_shell *shell)
{
	long		deadline;
	t_ai_reply	rep;
	int			fd;
	char		*line;

	deadline = now_ms() + 5000;
	while (now_ms() < deadline)
	{
		if (waitpid(shell->ai_pid, NULL, WNOHANG) == shell->ai_pid)
		{
			shell->ai_pid = -1;
			return (set_status(shell, TR("off (helper did not start)", "kapalı (yardımcı süreç başlamadı)")));
		}
		fd = ai_connect(shell, 3);
		if (fd >= 0)
		{
			line = NULL;
			if (send_all(fd, "{\"op\":\"ping\"}\n") == 0)
				line = recv_line(fd);
			close(fd);
			if (!line)
				return (set_status(shell, TR("off (no reply)", "kapalı (yanıt yok)")));
			parse_reply(line, &rep);
			free(line);
			shell->ai_ready = rep.ok;
			set_status(shell, rep.ok ? TR("connected", "bağlı") : TR("off", "kapalı"));
			ft_strlcat(shell->ai_status, " (", sizeof(shell->ai_status));
			ft_strlcat(shell->ai_status, rep.text, sizeof(shell->ai_status));
			ft_strlcat(shell->ai_status, ")", sizeof(shell->ai_status));
			return (free(rep.text));
		}
		usleep(20000);
	}
	set_status(shell, TR("off (timed out)", "kapalı (zaman aşımı)"));
}

int	ai_start(t_shell *shell, const char *argv0)
{
	char	tmpl[32];
	char	*helper;

	(void)argv0;
	set_status(shell, TR("off", "kapalı"));
	if (getenv("SHELLM_AI") && !ft_strcmp(getenv("SHELLM_AI"), "0"))
		return (set_status(shell, TR("off (SHELLM_AI=0)", "kapalı (SHELLM_AI=0)")), 0);
	helper = ai_find_helper();
	if (!helper)
		return (set_status(shell, TR("off (ai_helper.py not found)", "kapalı (ai_helper.py bulunamadı)")), 0);
	ft_strlcpy(tmpl, "/tmp/shellm-XXXXXX", sizeof(tmpl));
	if (!mkdtemp(tmpl))
		return (free(helper), 0);
	shell->ai_dir = ft_strdup(tmpl);
	shell->ai_socket = ft_strjoin(tmpl, "/ai.sock");
	shell->ai_pid = fork();
	if (shell->ai_pid == 0)
		spawn_helper(helper, shell);
	free(helper);
	if (shell->ai_pid < 0)
		return (set_status(shell, TR("off (fork failed)", "kapalı (fork başarısız)")), 0);
	wait_ready(shell);
	return (shell->ai_ready);
}

void	ai_stop(t_shell *shell)
{
	char	*log;

	if (shell->ai_pid > 0)
	{
		kill(shell->ai_pid, SIGTERM);
		waitpid(shell->ai_pid, NULL, 0);
		shell->ai_pid = -1;
	}
	if (shell->ai_socket)
		unlink(shell->ai_socket);
	if (shell->ai_dir)
	{
		log = ft_strjoin(shell->ai_dir, "/ai.log");
		if (log && !getenv("SHELLM_KEEP_LOG"))
			unlink(log);
		free(log);
		rmdir(shell->ai_dir);
	}
	free(shell->ai_socket);
	free(shell->ai_dir);
	shell->ai_socket = NULL;
	shell->ai_dir = NULL;
	shell->ai_ready = 0;
}
