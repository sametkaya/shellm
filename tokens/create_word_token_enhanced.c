
#include "../minishell.h"

void	reset_token_ctx(t_token_ctx *ctx)
{
	ft_bzero(ctx, sizeof(*ctx));
}

int	is_break_char(char c)
{
	return (c == '|' || c == '<' || c == '>');
}

static int	build_result(t_token_ctx *ctx)
{
	int	j;

	j = expand_leading_tilde(ctx);
	if (j < 0)
		return (-1);
	while (j < ctx->i)
	{
		if (ctx->input[j] == '\'' || ctx->input[j] == '\"')
			j = append_quoted(ctx, j);
		else
			j = append_unquoted(ctx, j);
		if (j < 0)
			return (-1);
	}
	return (0);
}

int	create_word_token_enhanced(t_token_ctx *ctx)
{
	init_token_ctx(ctx);
	if (!scan_input(ctx))
		return (-1);
	if (build_result(ctx) < 0)
	{
		free(ctx->result);
		free(ctx->pattern);
		return (-1);
	}
	if (!finalize_token(ctx))
		return (-1);
	return (ctx->i);
}
