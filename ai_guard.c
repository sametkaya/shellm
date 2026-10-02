#include "minishell.h"

/*
** SheLLM v2: two checks for AI suggestions.
**
**  syntax_issue(): returns a short explanation if a suggestion uses Bash
**      syntax that SheLLM does not support (e.g. "&&", "$(...)"). Such a
**      suggestion would not behave as in Bash even if it were run.
**
**  risk_reason():  see ai_risk.c.
**
** A simple quote-aware scanner is used.
*/

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
		return (TR("command separator ';'", "komut ayırıcı ';'"));
	if (s[i] == '&' && s[i + 1] == '&')
		return (TR("'&&' operator", "'&&' işleci"));
	if (s[i] == '|' && s[i + 1] == '|')
		return (TR("'||' operator", "'||' işleci"));
	if (s[i] == '|' && s[i + 1] == '&')
		return (TR("'|&' operator", "'|&' işleci"));
	if (s[i] == '&')
		return (TR("'&' (background or descriptor redirection)",
			"'&' (arka plan ya da tanımlayıcı yönlendirmesi)"));
	if (s[i] == '`')
		return (TR("command substitution with backquotes",
			"ters tırnakla komut ikamesi"));
	if (s[i] == '$' && s[i + 1] == '(')
		return (TR("'$(...)' command substitution",
			"'$(...)' komut ikamesi"));
	if (s[i] == '$' && s[i + 1] == '{')
		return (TR("'${...}' parameter expansion",
			"'${...}' parametre genişletmesi"));
	if (s[i] == '(' || s[i] == ')')
		return (TR("subshell or process substitution '( )'",
			"alt kabuk ya da süreç ikamesi '( )'"));
	if (s[i] == '{' && brace_expansion_at(s, i))
		return (TR("brace expansion '{a,b}'",
			"süslü parantez genişletmesi '{a,b}'"));
	if (s[i] == '\\')
		return (TR("backslash escape", "ters eğik çizgiyle kaçış"));
	if (s[i] == '<' && s[i + 1] == '<' && s[i + 2] == '<')
		return ("'<<<' here-string");
	if (word_start && s[i] >= '0' && s[i] <= '9'
		&& (s[i + 1] == '>' || s[i + 1] == '<'))
		return (TR("file-descriptor redirection (e.g. 2>)",
			"dosya tanımlayıcısı yönlendirmesi (ör. 2>)"));
	if (cmd_start && word_start && is_assignment_word(s, i))
		return (TR("variable assignment without export",
			"export'suz değişken ataması"));
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
				return (TR("command substitution inside double quotes",
			"çift tırnak içinde komut ikamesi"));
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

