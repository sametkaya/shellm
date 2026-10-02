

#include "../minishell.h"

static void	set_token_prev_fields(t_token **tokens)
{
	int	i;

	if (!tokens)
		return ;
	i = 0;
	while (tokens[i])
	{
		if (i > 0)
			tokens[i]->prev = tokens[i - 1];
		else
			tokens[i]->prev = NULL;
		i++;
	}
}

t_token	**tokenize_with_expansion(char *input, t_shell *shell)
{
	t_token	**tokens;
	int		token_count;

	token_count = count_tokens_enhanced(input);
	tokens = (t_token **)malloc(sizeof(t_token *) * (token_count + 1));
	if (!tokens)
		return (NULL);
	if (!fill_tokens_enhanced_with_expansion(input, tokens, shell))
	{
		freetokens(tokens);
		return (NULL);
	}
	tokens[token_count] = NULL;
	if (!expand_glob_tokens(&tokens))
	{
		freetokens(tokens);
		return (NULL);
	}
	set_token_prev_fields(tokens);
	return (tokens);
}
