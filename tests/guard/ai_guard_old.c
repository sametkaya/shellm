#include "minishell.h"

/*
** SheLLM v2: Two checks for AI suggestions.
**
**  syntax_issue(): If the suggestion contains Bash syntax that SheLLM does
**      not support, returns a short description (e.g. "&&", "$(...)").
**      Such suggestions would not behave as in Bash even if they were run.
**
**  risk_reason():  If the suggestion contains a command that could cause
**      data loss, privilege escalation or a system shutdown, returns a
**      reason. Risky suggestions ask the user to type "evet" ("yes") to
**      confirm.
**
** Both functions use a simple quote-aware scanner.
*/

#define MAXW 128

typedef struct s_words
{
	char	*w[MAXW];
	int		op[MAXW];
	int		n;
}	t_words;

static int	is_ident_char(char c, int first)
{
	if (c == '_' || (c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z'))
		return (1);
	return (!first && c >= '0' && c <= '9');
}

static int	brace_expansion_at(const char *s, int i)
{
	int	j;

	j = i + 1;
	while (s[j] && s[j] != '}' && s[j] != ' ')
	{
		if (s[j] == ',' || (s[j] == '.' && s[j + 1] == '.'))
			return (1);
		j++;
	}
	return (0);
}

static int	is_assignment_word(const char *s, int i)
{
	int	j;

	if (!is_ident_char(s[i], 1))
		return (0);
	j = i + 1;
	while (is_ident_char(s[j], 0))
		j++;
	return (s[j] == '=');
}

static const char	*check_unquoted(const char *s, int i, int word_start,
		int cmd_start)
{
	if (s[i] == ';')
		return ("command separator ';'");
	if (s[i] == '&' && s[i + 1] == '&')
		return ("'&&' operator");
	if (s[i] == '|' && s[i + 1] == '|')
		return ("'||' operator");
	if (s[i] == '|' && s[i + 1] == '&')
		return ("'|&' operator");
	if (s[i] == '&')
		return ("'&' (background or descriptor redirection)");
	if (s[i] == '`')
		return ("command substitution with backquotes");
	if (s[i] == '$' && s[i + 1] == '(')
		return ("'$(...)' command substitution");
	if (s[i] == '$' && s[i + 1] == '{')
		return ("'${...}' parameter expansion");
	if (s[i] == '(' || s[i] == ')')
		return ("subshell or process substitution '( )'");
	if (s[i] == '{' && brace_expansion_at(s, i))
		return ("brace expansion '{a,b}'");
	if (s[i] == '\\')
		return ("backslash escape");
	if (s[i] == '<' && s[i + 1] == '<' && s[i + 2] == '<')
		return ("'<<<' here-string");
	if (word_start && s[i] >= '0' && s[i] <= '9'
		&& (s[i + 1] == '>' || s[i + 1] == '<'))
		return ("file-descriptor redirection (e.g. 2>)");
	if (cmd_start && word_start && is_assignment_word(s, i))
		return ("variable assignment without export");
	return (NULL);
}

const char	*syntax_issue(const char *s)
{
	int			i;
	char		q;
	int			word_start;
	int			cmd_start;
	const char	*r;

	i = 0;
	q = 0;
	word_start = 1;
	cmd_start = 1;
	while (s && s[i])
	{
		if (q)
		{
			if (s[i] == q)
				q = 0;
			else if (q == '"' && ((s[i] == '$' && s[i + 1] == '(')
					|| s[i] == '`'))
				return ("command substitution inside double quotes");
			i++;
			continue ;
		}
		if (s[i] == '\'' || s[i] == '"')
		{
			q = s[i++];
			word_start = 0;
			continue ;
		}
		r = check_unquoted(s, i, word_start, cmd_start);
		if (r)
			return (r);
		if (s[i] == '|')
			cmd_start = 1;
		else if (s[i] != ' ' && s[i] != '\t')
			cmd_start = (s[i] == '<' || s[i] == '>') && cmd_start;
		word_start = (s[i] == ' ' || s[i] == '\t' || s[i] == '|'
				|| s[i] == '<' || s[i] == '>');
		i++;
	}
	return (NULL);
}

/* ------------------------------------------------------------------ */

static void	words_free(t_words *w)
{
	int	i;

	i = 0;
	while (i < w->n)
		free(w->w[i++]);
	w->n = 0;
}

static void	push_word(t_words *w, char *buf, int *len, int op)
{
	if (w->n >= MAXW)
		return ;
	if (op)
	{
		w->w[w->n] = ft_strdup(op == 1 ? "|" : ">");
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

/* Splits into words, removing quotes; | => op 1, > or >> => op 2. */
static void	split_words(const char *s, t_words *w, char *buf)
{
	int		i;
	int		len;
	char	q;

	i = 0;
	len = 0;
	q = 0;
	w->n = 0;
	while (s[i])
	{
		if (q && s[i] == q)
			q = 0;
		else if (q)
			buf[len++] = s[i];
		else if (s[i] == '\'' || s[i] == '"')
			q = s[i];
		else if (s[i] == ' ' || s[i] == '\t' || s[i] == '|' || s[i] == '>')
		{
			push_word(w, buf, &len, 0);
			if (s[i] == '|')
				push_word(w, buf, &len, 1);
			else if (s[i] == '>')
			{
				push_word(w, buf, &len, 2);
				if (s[i + 1] == '>')
					i++;
			}
		}
		else
			buf[len++] = s[i];
		i++;
	}
	push_word(w, buf, &len, 0);
}

static const char	*base(const char *p)
{
	const char	*b;

	b = ft_strrchr(p, '/');
	if (b)
		return (b + 1);
	return (p);
}

static int	in_list(const char *w, const char **list)
{
	int	i;

	i = 0;
	while (list[i])
		if (!ft_strcmp(w, list[i++]))
			return (1);
	return (0);
}

static int	has_opt(t_words *w, int from, int to, const char *chars,
		const char *longopt)
{
	int	i;
	int	j;

	i = from;
	while (++i < to)
	{
		if (longopt && !ft_strcmp(w->w[i], longopt))
			return (1);
		if (w->w[i][0] == '-' && w->w[i][1] != '-')
		{
			j = 0;
			while (w->w[i][++j])
				if (ft_strchr(chars, w->w[i][j]))
					return (1);
		}
	}
	return (0);
}

static int	has_word(t_words *w, int from, int to, const char *word)
{
	while (++from < to)
		if (!ft_strcmp(w->w[from], word))
			return (1);
	return (0);
}

static const char	*risk_of_cmd(t_words *w, int s, int e, int piped_in)
{
	static const char	*disk[] = {"dd", "mkfs", "mkfs.ext4", "mkfs.vfat",
		"mkfs.xfs", "fdisk", "sfdisk", "parted", "wipefs", "shred", "mkswap",
		NULL};
	static const char	*power[] = {"shutdown", "reboot", "halt", "poweroff",
		"init", "telinit", NULL};
	static const char	*interp[] = {"sh", "bash", "zsh", "dash", "ksh",
		"python", "python3", "perl", "ruby", NULL};
	const char			*c;

	if (s >= e)
		return (NULL);
	c = base(w->w[s]);
	if (!ft_strcmp(c, "sudo") || !ft_strcmp(c, "su") || !ft_strcmp(c, "doas"))
		return ("running with administrator rights (sudo/su)");
	if (!ft_strcmp(c, "rm"))
	{
		if (has_opt(w, s, e, "rRf", "--recursive") || has_word(w, s, e, "--force"))
			return ("recursive or forced deletion (rm -r/-f)");
		return ("file deletion (rm)");
	}
	if (in_list(c, disk) || !ft_strncmp(c, "mkfs", 4))
		return ("disk or data destruction (dd/mkfs/shred)");
	if (in_list(c, power) || (!ft_strcmp(c, "systemctl")
			&& (has_word(w, s, e, "poweroff") || has_word(w, s, e, "reboot")
				|| has_word(w, s, e, "halt"))))
		return ("shutting down or rebooting the system");
	if ((!ft_strcmp(c, "chmod") || !ft_strcmp(c, "chown")
			|| !ft_strcmp(c, "chgrp")) && (has_opt(w, s, e, "R", "--recursive")
			|| has_word(w, s, e, "777") || has_word(w, s, e, "/")))
		return ("recursive permission/ownership change");
	if (!ft_strcmp(c, "kill") || !ft_strcmp(c, "killall")
		|| !ft_strcmp(c, "pkill"))
		return ("killing processes");
	if (!ft_strcmp(c, "truncate"))
		return ("erasing file contents (truncate)");
	if (!ft_strcmp(c, "find") && (has_word(w, s, e, "-delete")
			|| (has_word(w, s, e, "-exec") && has_word(w, s, e, "rm"))))
		return ("mass file deletion (find -delete)");
	if (!ft_strcmp(c, "git") && ((has_word(w, s, e, "reset")
				&& has_word(w, s, e, "--hard")) || (has_word(w, s, e, "clean")
				&& has_opt(w, s, e, "f", NULL)) || has_word(w, s, e, "--force")))
		return ("irreversible git operation");
	if (!ft_strcmp(c, "crontab") && has_opt(w, s, e, "r", NULL))
		return ("deleting scheduled jobs (crontab -r)");
	if (piped_in && in_list(c, interp) && e - s == 1)
		return ("running piped content in an interpreter (| sh)");
	return (NULL);
}

static const char	*risk_of_redirs(t_words *w)
{
	int	i;

	i = -1;
	while (++i < w->n - 1)
	{
		if (w->op[i] != 2 || w->op[i + 1])
			continue ;
		if (!ft_strncmp(w->w[i + 1], "/dev/sd", 7)
			|| !ft_strncmp(w->w[i + 1], "/dev/nvme", 9)
			|| !ft_strncmp(w->w[i + 1], "/etc/", 5)
			|| !ft_strncmp(w->w[i + 1], "/boot", 5))
			return ("overwriting a system file or disk");
	}
	return (NULL);
}

const char	*risk_reason(const char *cmd)
{
	t_words		w;
	char		*buf;
	const char	*r;
	int			s;
	int			i;

	if (!cmd)
		return (NULL);
	if (ft_strnstr(cmd, ":(){", ft_strlen(cmd)))
		return ("fork bomb");
	buf = malloc(ft_strlen(cmd) + 1);
	if (!buf)
		return (NULL);
	split_words(cmd, &w, buf);
	free(buf);
	r = risk_of_redirs(&w);
	s = 0;
	i = 0;
	while (!r && i <= w.n)
	{
		if (i == w.n || w.op[i] == 1)
		{
			r = risk_of_cmd(&w, s, i, s > 0);
			s = i + 1;
		}
		else if (w.op[i] == 2 && i == s)
			s = i + 2;
		i++;
	}
	words_free(&w);
	return (r);
}
