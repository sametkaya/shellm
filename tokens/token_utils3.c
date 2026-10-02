

#include "../minishell.h"

t_token	*create_token(char *value, t_token_type type)
{
	return (create_token_with_quote(value, type, Q_NONE));
}

t_token	*create_token_with_expansion(char *value, t_token_type type,
		int quote_type, int was_expanded)
{
	t_token	*token;

	token = create_token_with_quote(value, type, quote_type);
	if (token)
		token->was_expanded = was_expanded;
	return (token);
}
