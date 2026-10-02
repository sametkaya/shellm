#include "../minishell.h"

/*
** SheLLM v2: Two strings are built together for each word:
**   result  : the final value, with quotes removed and variables expanded
**   pattern : the pattern for glob(3); wildcard characters inside quotes
**             are escaped with a backslash, so only unquoted *, ? and [
**             characters are interpreted as wildcards.
*/

void	init_token_ctx(t_token_ctx *ctx)
{
	ctx->start = ctx->i;
	ctx->result = ft_strdup("");
	ctx->pattern = ft_strdup("");
	ctx->has_glob = 0;
	ctx->quote_type = Q_NONE;
	ctx->single_quote_count = 0;
	ctx->double_quote_count = 0;
	ctx->only_var_expand = 1;
	ctx->should_expand = 1;
	if (*ctx->token_index > 0 && ctx->tokens[*ctx->token_index - 1]
		&& ctx->tokens[*ctx->token_index - 1]->type == T_HEREDOC)
		ctx->should_expand = 0;
}

int	scan_input(t_token_ctx *ctx)
{
	int	temp_i;

	temp_i = ctx->i;
	while (ctx->input[temp_i] && !is_space(ctx->input[temp_i]))
	{
		if (is_break_char(ctx->input[temp_i]))
			break ;
		temp_i = handle_quotes_and_vars(ctx, temp_i);
	}
	set_quote_type(ctx);
	ctx->i = temp_i;
	return (1);
}

/* Appends a piece to the pattern; if quoted, all wildcards are escaped. */
static int	pattern_append(t_token_ctx *ctx, const char *s, int quoted)
{
	char	*esc;
	char	*tmp;
	size_t	i;
	size_t	j;

	esc = malloc(ft_strlen(s) * 2 + 1);
	if (!esc)
		return (0);
	i = 0;
	j = 0;
	while (s[i])
	{
		if (s[i] == '\\' || (quoted && (s[i] == '*' || s[i] == '?'
					|| s[i] == '[' || s[i] == ']')))
			esc[j++] = '\\';
		else if (!quoted && (s[i] == '*' || s[i] == '?' || s[i] == '['))
			ctx->has_glob = 1;
		esc[j++] = s[i++];
	}
	esc[j] = '\0';
	tmp = ft_strjoin(ctx->pattern, esc);
	free(esc);
	free(ctx->pattern);
	ctx->pattern = tmp;
	return (tmp != NULL);
}

/* Appends content (expanded if needed) to result and pattern; frees content. */
static int	append_part(t_token_ctx *ctx, char *content, int expand, int quoted)
{
	char	*expanded;
	char	*tmp;

	if (expand && ft_strchr(content, '$'))
	{
		expanded = expand_string_with_vars(content, ctx->shell);
		free(content);
		if (!expanded)
			return (0);
		content = expanded;
	}
	tmp = ft_strjoin(ctx->result, content);
	free(ctx->result);
	ctx->result = tmp;
	if (!tmp || !pattern_append(ctx, content, quoted))
		return (free(content), 0);
	free(content);
	return (1);
}

int	append_quoted(t_token_ctx *ctx, int j)
{
	int		quote_start;
	char	*quoted_content;

	quote_start = ++j;
	while (j < ctx->i && ctx->input[j] != ctx->input[quote_start - 1])
		j++;
	quoted_content = ft_substr(ctx->input, quote_start, j - quote_start);
	if (!quoted_content)
		return (-1);
	if (!append_part(ctx, quoted_content,
			ctx->input[quote_start - 1] != '\'' && ctx->should_expand, 1))
		return (-1);
	return (j + (j < ctx->i));
}

int	append_unquoted(t_token_ctx *ctx, int j)
{
	int		start;
	char	*unquoted_content;

	start = j;
	while (j < ctx->i && ctx->input[j] != '\'' && ctx->input[j] != '\"')
		j++;
	unquoted_content = ft_substr(ctx->input, start, j - start);
	if (!unquoted_content)
		return (-1);
	if (!append_part(ctx, unquoted_content, ctx->should_expand,
			!ctx->should_expand))
		return (-1);
	return (j);
}

/*
** Replaces an unquoted ~ or ~/ at the start of a word with HOME.
** Not applied to heredoc delimiters (should_expand == 0).
*/
int	expand_leading_tilde(t_token_ctx *ctx)
{
	char	*home;
	int		s;

	s = ctx->start;
	if (!ctx->should_expand || ctx->input[s] != '~')
		return (s);
	if (s + 1 < ctx->i && ctx->input[s + 1] != '/')
		return (s);
	home = get_env_value(ctx->shell->env_list, "HOME");
	if (!home || !*home)
		return (s);
	ctx->only_var_expand = 0;
	if (!append_part(ctx, ft_strdup(home), 0, 1))
		return (-1);
	return (s + 1);
}

int	finalize_token(t_token_ctx *ctx)
{
	t_token	*tok;

	if (ctx->only_var_expand && ft_strlen(ctx->result) == 0)
	{
		free(ctx->result);
		free(ctx->pattern);
		return (1);
	}
	tok = create_token_with_expansion(ctx->result, T_WORD, ctx->quote_type, 1);
	ctx->tokens[*ctx->token_index] = tok;
	free(ctx->result);
	if (!tok)
		return (free(ctx->pattern), 0);
	if (ctx->has_glob && ctx->should_expand)
		tok->glob_pattern = ctx->pattern;
	else
		free(ctx->pattern);
	(*ctx->token_index)++;
	return (1);
}
