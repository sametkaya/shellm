#include "../minishell.h"

/*
** SheLLM v2: Wildcard (glob) expansion.
** Words containing an unquoted *, ? or [ are expanded to file names with
** glob(3). If there is no match, the word is left as is (Bash's default
** behavior). Redirection targets and heredoc delimiters are not
** expanded.
*/

static int	count_tokens(t_token **t)
{
	int	n;

	n = 0;
	while (t && t[n])
		n++;
	return (n);
}

static int	is_redir_op(t_token *t)
{
	return (t->type >= T_INPUT && t->type <= T_HEREDOC);
}

static int	push(t_token ***arr, int *len, int *cap, t_token *tok)
{
	t_token	**n;
	int		i;

	if (!tok)
		return (0);
	if (*len + 1 >= *cap)
	{
		*cap = (*cap) * 2 + 8;
		n = malloc(sizeof(t_token *) * (*cap));
		if (!n)
			return (0);
		i = -1;
		while (++i < *len)
			n[i] = (*arr)[i];
		free(*arr);
		*arr = n;
	}
	(*arr)[(*len)++] = tok;
	(*arr)[*len] = NULL;
	return (1);
}

static int	expand_one(t_token *tok, t_token ***out, int *len, int *cap)
{
	glob_t	g;
	size_t	k;
	int		rc;

	rc = glob(tok->glob_pattern, 0, NULL, &g);
	if (rc != 0 || g.gl_pathc == 0)
	{
		if (rc == 0)
			globfree(&g);
		free(tok->glob_pattern);
		tok->glob_pattern = NULL;
		return (push(out, len, cap, tok));
	}
	k = 0;
	while (k < g.gl_pathc)
	{
		if (!push(out, len, cap, create_token_with_expansion(g.gl_pathv[k],
					T_WORD, Q_NONE, 1)))
			return (globfree(&g), 0);
		k++;
	}
	globfree(&g);
	free(tok->value);
	free(tok->glob_pattern);
	free(tok);
	return (1);
}

int	expand_glob_tokens(t_token ***tokens)
{
	t_token	**in;
	t_token	**out;
	int		len;
	int		cap;
	int		i;
	int		after_redir;
	int		redir_now;

	in = *tokens;
	cap = count_tokens(in) + 8;
	out = malloc(sizeof(t_token *) * cap);
	if (!out)
		return (0);
	len = 0;
	out[0] = NULL;
	after_redir = 0;
	i = -1;
	while (in[++i])
	{
		redir_now = is_redir_op(in[i]);
		if (in[i]->glob_pattern && !after_redir)
		{
			if (!expand_one(in[i], &out, &len, &cap))
				return (free(out), 0);
		}
		else if (!push(&out, &len, &cap, in[i]))
			return (free(out), 0);
		after_redir = redir_now;
	}
	free(in);
	*tokens = out;
	return (1);
}
