#include "minishell.h"

/* Language selection: see TR() in minishell.h. Cached; reset after setup. */
static int	starts_with_tr(const char *v)
{
	return (v && (v[0] == 't' || v[0] == 'T') && (v[1] == 'r' || v[1] == 'R'));
}

/* SHELLM_LANG from the settings file: 1 tr, 0 other, -1 not set. */
static int	lang_from_config(void)
{
	char		path[4096];
	char		line[256];
	const char	*v;
	FILE		*f;
	int			r;

	v = getenv("XDG_CONFIG_HOME");
	if (v && *v)
		snprintf(path, sizeof(path), "%s/shellm/config", v);
	else if (getenv("HOME") && *getenv("HOME"))
		snprintf(path, sizeof(path), "%s/.config/shellm/config", getenv("HOME"));
	else
		return (-1);
	f = fopen(path, "r");
	if (!f)
		return (-1);
	r = -1;
	while (fgets(line, sizeof(line), f))
	{
		if (!ft_strncmp(line, "SHELLM_LANG=", 12))
		{
			v = line + 12;
			if (*v == '"' || *v == '\'')
				v++;
			r = starts_with_tr(v);
		}
	}
	fclose(f);
	return (r);
}

static int	g_lang = -1;

/* Forget the cached choice (called after the setup wizard has run). */
void	ui_lang_reset(void)
{
	g_lang = -1;
}

/* Order: SHELLM_LANG, then the settings file, then the locale. */
int	ui_lang_tr(void)
{
	const char	*v;

	if (g_lang >= 0)
		return (g_lang);
	v = getenv("SHELLM_LANG");
	if (v && *v)
		g_lang = starts_with_tr(v);
	else
		g_lang = lang_from_config();
	if (g_lang < 0)
	{
		v = getenv("LC_ALL");
		if (!v || !*v)
			v = getenv("LC_MESSAGES");
		if (!v || !*v)
			v = getenv("LANG");
		g_lang = starts_with_tr(v);
	}
	return (g_lang);
}

int	ui_term_width(void)
{
	struct winsize	w;

	if (ioctl(STDOUT_FILENO, TIOCGWINSZ, &w) == 0 && w.ws_col > 0)
		return (w.ws_col);
	return (80);
}

void	ui_hline(int width)
{
	int	i;

	i = 0;
	while (i < width)
	{
		write(STDOUT_FILENO, "─", 3);
		i++;
	}
}

void	ui_topbar(int ai_connected, const char *status)
{
	int	w;

	w = ui_term_width();
	printf("\n  " UI_PINK UI_BOLD "sheLLM" UI_RESET "  ");
	if (ai_connected)
		printf(UI_SECONDARY "● AI %s" UI_RESET, status);
	else
		printf(UI_GRAY "● AI %s" UI_RESET, status);
	printf("\n  " UI_GRAY_DIM);
	fflush(stdout);
	ui_hline(w - 4);
	printf(UI_RESET "\n\n");
	fflush(stdout);
}

/* ── Notification line ──────────────────────────────────────────────── */
/*
** kind 0 = ok   → green ✓
** kind 1 = err  → red ✗
** kind 2 = warn → yellow ⚠
**
**   ▌ ✗  git: psuh: command not found
*/
void	ui_notify(int kind, const char *msg)
{
	const char	*icon;
	const char	*bar_col;
	const char	*text_col;

	if (kind == 0)
	{
		icon = "✓";
		bar_col = "\033[38;5;28m";
		text_col = UI_GREEN_DIM;
	}
	else if (kind == 1)
	{
		icon = "✗";
		bar_col = "\033[38;5;160m";
		text_col = "\033[38;5;203m";
	}
	else
	{
		icon = "⚠";
		bar_col = "\033[38;5;136m";
		text_col = UI_PINK;
	}
	printf("  %s▌\033[0m %s%s\033[0m  %s%s\033[0m\n",
		bar_col, bar_col, icon, text_col, msg);
}

/* ── AI spinner ─────────────────────────────────────────────────────── */
void	ui_spinner_start(void)
{
	printf("\n  \033[38;5;71m⠸\033[0m \033[38;5;240m%s\033[0m",
		TR("AI is thinking... (cancel: Ctrl+C)",
			"AI düşünüyor... (iptal: Ctrl+C)"));
	fflush(stdout);
}

void	ui_spinner_clear(void)
{
	printf("\r\033[2K");
	fflush(stdout);
}

/*
** SheLLM v2: suggestion box. A risky suggestion gets a red warning and must be
** confirmed with the full word ("yes" or "evet"); a suggestion that uses syntax
** SheLLM does not support gets a yellow warning.
*/
void	ui_ai_suggestion(const char *suggestion, const char *risk,
			const char *syntax)
{
	if (!suggestion)
		return ;
	printf("\n");
	printf("  \033[38;5;183m┃\033[0m \033[38;5;205m◆ %s\033[0m\n",
		TR("shellm suggestion", "shellm önerisi"));
	printf("  \033[38;5;183m┃\033[0m \033[38;5;213m\033[1m%s\033[0m\n", suggestion);
	if (risk)
		printf("  \033[38;5;183m┃\033[0m \033[38;5;196m\033[1m⚠ %s: %s"
			"\033[0m\n", TR("CAUTION", "DİKKAT"), risk);
	if (syntax)
		printf("  \033[38;5;183m┃\033[0m \033[38;5;178m⚠ %s: %s\033[0m\n",
			TR("SheLLM does not support this syntax",
				"SheLLM bu sözdizimini desteklemiyor"), syntax);
	printf("  \033[38;5;183m┃\033[0m\n");
	printf("  \033[38;5;183m┃\033[0m \033[38;5;141m[%s]\033[0m "
		"\033[38;5;245m%s\033[0m", risk ? TR("yes", "evet") : TR("y", "e"),
		TR("run", "çalıştır"));
	printf("   \033[38;5;141m[%s]\033[0m \033[38;5;239m%s\033[0m\n\n",
		TR("n", "h"), TR("skip", "geç"));
	fflush(stdout);
}

/* ── Error line ─────────────────────────────────────────────────────── */
void	ui_error_line(const char *cmd)
{
	char	buf[256];

	snprintf(buf, sizeof(buf), TR("%s: command not found",
			"%s: komut bulunamadı"), cmd);
	ui_notify(1, buf);
}

/* ── Info line ──────────────────────────────────────────────────────── */
void	ui_info_line(const char *msg)
{
	ui_notify(0, msg);
}