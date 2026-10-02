#include "minishell.h"

/*
** Triggering the AI layer and the checks made before sending.
**
**  ast_has_unknown_command(): returns 1 if the shell itself, before
**      execution, cannot resolve the command name of any pipeline stage.
**      Triggering thus rests on the shell's own "command not found" decision
**      rather than on `$? == 127`: a 127 returned by a child (env, xargs,
**      scripts) does not trigger, while a failing first stage such as
**      `grpe x | wc -l` does.
**
**  line_looks_like_text(): returns 1 if a line that cannot be parsed because
**      of an unmatched quote does not start with a command. Lines with a
**      Turkish apostrophe ("notlar.txt'yi sil", "delete notlar.txt"), which
**      the lexer sees as a single quote, then also reach the helper.
**
**  secret_reason(): returns a reason if the line seems to contain a password,
**      access key or token; such lines are never sent to the model.
**
**  hide_api_keys(): after the helper has started, removes the provider keys
**      from the shell's environment list, so that programs started by the
**      shell do not inherit them and `env` cannot show them.
*/

static const char	*g_builtins[] = {"echo", "cd", "pwd", "export", "unset",
	"env", "exit", NULL};

static int	name_resolves(const char *name, t_env *env)
{
	struct stat	st;
	char		*p;
	int			i;

	if (!name || !*name)
		return (1);
	i = 0;
	while (g_builtins[i])
		if (!ft_strcmp(name, g_builtins[i++]))
			return (1);
	if (ft_strchr(name, '/'))
		return (stat(name, &st) == 0 && !S_ISDIR(st.st_mode));
	p = find_exec((char *)name, env);
	if (!p)
		return (0);
	free(p);
	return (1);
}

int	ast_has_unknown_command(t_ast *n, t_env *env)
{
	if (!n)
		return (0);
	if (n->type == NODE_REDIR)
		return (ast_has_unknown_command(n->left, env));
	if (n->type == NODE_PIPE)
		return (ast_has_unknown_command(n->left, env)
			|| ast_has_unknown_command(n->right, env));
	if (n->type == NODE_COMMAND && n->args && n->args[0])
		return (!name_resolves(n->args[0], env));
	return (0);
}

int	line_looks_like_text(const char *line, t_env *env)
{
	char	word[256];
	int		i;
	int		n;

	i = 0;
	while (line[i] == ' ' || line[i] == '\t')
		i++;
	n = 0;
	while (line[i] && line[i] != ' ' && line[i] != '\t' && line[i] != '\''
		&& line[i] != '"' && line[i] != '|' && line[i] != '<'
		&& line[i] != '>' && n < 255)
		word[n++] = line[i++];
	word[n] = '\0';
	if (n == 0)
		return (0);
	return (!name_resolves(word, env));
}

/* ------------------------------------------------------------------ */

static int	ci_contains(const char *s, int len, const char *needle)
{
	int	i;
	int	j;
	int	m;

	m = ft_strlen(needle);
	i = 0;
	while (i + m <= len)
	{
		j = 0;
		while (j < m && ft_tolower((unsigned char)s[i + j]) == needle[j])
			j++;
		if (j == m)
			return (1);
		i++;
	}
	return (0);
}

/* Character set used in tokens (base64/hex-like). */
static int	token_char(char c)
{
	return (ft_isalnum((unsigned char)c) || c == '-' || c == '_' || c == '+'
		|| c == '/' || c == '=');
}

static int	looks_random(const char *s, int len)
{
	int	seen[256];
	int	distinct;
	int	kinds[3];
	int	i;

	if (len < 20)
		return (0);
	ft_bzero(seen, sizeof(seen));
	ft_bzero(kinds, sizeof(kinds));
	distinct = 0;
	i = -1;
	while (++i < len)
	{
		if (!token_char(s[i]) || s[i] == '/')
			return (0);
		if (!seen[(unsigned char)s[i]]++)
			distinct++;
		kinds[0] |= (s[i] >= 'A' && s[i] <= 'Z');
		kinds[1] |= (s[i] >= 'a' && s[i] <= 'z');
		kinds[2] |= (s[i] >= '0' && s[i] <= '9');
	}
	return (kinds[0] && kinds[1] && kinds[2] && distinct >= 12
		&& distinct * 2 >= len);
}

/* Known key prefixes: at the start of a token or after ':' '@' '=' '/'. */
static int	known_prefix(const char *s, int len)
{
	static const char	*prefixes[] = {"AKIA", "ASIA", "AIza", "sk-", "ghp_",
		"gho_", "ghs_", "ghu_", "github_pat_", "xoxb-", "xoxp-", "glpat-",
		"AQ.", "eyJ", NULL};
	int					i;
	int					k;
	int					n;

	k = -1;
	while (++k < len)
	{
		if (k > 0 && s[k - 1] != ':' && s[k - 1] != '@' && s[k - 1] != '='
			&& s[k - 1] != '/')
			continue ;
		i = -1;
		while (prefixes[++i])
		{
			n = ft_strlen(prefixes[i]);
			if (len - k > n + 8 && !ft_strncmp(s + k, prefixes[i], n)
				&& token_char(s[k + n]))
				return (1);
		}
	}
	return (0);
}

/* NAME=value: the name suggests a password/key and the value is plain text. */
static int	secret_assignment(const char *s, int len)
{
	static const char	*names[] = {"pass", "pwd", "secret", "token", "key",
		"auth", "credential", NULL};
	static const char	*plain[] = {"yes", "no", "true", "false", "none",
		"null", "ask", NULL};
	const char			*eq;
	const char			*v;
	int					vlen;
	int					i;

	eq = ft_memchr(s, '=', len);
	if (!eq || eq == s)
		return (0);
	v = eq + 1;
	vlen = len - (v - s);
	if (vlen < 4 || v[0] == '$' || v[0] == '`' || v[0] == '(')
		return (0);
	i = -1;
	while (plain[++i])
		if (vlen == (int)ft_strlen(plain[i]) && ci_contains(v, vlen, plain[i]))
			return (0);
	i = -1;
	while (names[++i])
		if (ci_contains(s, eq - s, names[i]))
			return (1);
	return (0);
}

static const char	*token_secret(const char *s, int len)
{
	const char	*eq;

	if (known_prefix(s, len))
		return (TR("a value that looks like an access key",
			"erişim anahtarı biçiminde bir değer"));
	if (secret_assignment(s, len))
		return (TR("assignment of a password or key",
			"parola ya da anahtar ataması"));
	eq = ft_memchr(s, '=', len);
	if (eq)
	{
		len -= (eq + 1) - s;
		s = eq + 1;
	}
	if (looks_random(s, len))
		return (TR("a long random-looking value (possible token)",
			"rastgele görünen uzun bir değer (olası belirteç)"));
	return (NULL);
}

/* Command-line passwords such as mysql -pPASSWORD, sshpass -p PASSWORD. */
static int	password_option(const char *line)
{
	static const char	*db[] = {"mysql", "mysqldump", "mysqladmin", "mariadb",
		NULL};
	char				w[32];
	int					i;
	int					n;
	const char			*p;

	i = 0;
	while (line[i] == ' ' || line[i] == '\t')
		i++;
	n = 0;
	while (line[i] && line[i] != ' ' && line[i] != '\t' && n < 31)
		w[n++] = line[i++];
	w[n] = '\0';
	p = ft_strnstr(line, " -p", ft_strlen(line));
	if (!ft_strcmp(w, "sshpass") && p)
		return (1);
	i = -1;
	while (db[++i])
		if (!ft_strcmp(w, db[i]) && p && p[3] && p[3] != ' ')
			return (1);
	return (0);
}

const char	*secret_reason(const char *line)
{
	const char	*r;
	int			i;
	int			st;

	if (!line)
		return (NULL);
	if (ft_strnstr(line, "PRIVATE KEY", ft_strlen(line)))
		return (TR("private key content", "özel anahtar içeriği"));
	if (password_option(line))
		return (TR("password on the command line", "komut satırında parola"));
	i = 0;
	while (line[i])
	{
		while (line[i] == ' ' || line[i] == '\t' || line[i] == '\''
			|| line[i] == '"')
			i++;
		st = i;
		while (line[i] && line[i] != ' ' && line[i] != '\t'
			&& line[i] != '\'' && line[i] != '"')
			i++;
		if (i > st)
		{
			r = token_secret(line + st, i - st);
			if (r)
				return (r);
		}
	}
	return (NULL);
}

/* ------------------------------------------------------------------ */

void	hide_api_keys(t_shell *shell)
{
	static char	*keys[] = {"GEMINI_API_KEY", "GOOGLE_API_KEY",
		"ANTHROPIC_API_KEY", "OPENAI_API_KEY", NULL};
	int			i;

	if (getenv("SHELLM_KEEP_KEYS"))
		return ;
	i = 0;
	while (keys[i])
		remove_env(&shell->env_list, keys[i++]);
}
