

#include "../minishell.h"

void	freetokens(t_token **tokens)
{
	int	i;

	i = 0;
	if (!tokens)
		return ;
	while (tokens[i])
	{
		if (tokens[i]->value)
			free(tokens[i]->value);
		free(tokens[i]->glob_pattern);
		free(tokens[i]);
		i++;
	}
	free(tokens);
}

int	is_space(char c)
{
	return (c == ' ' || c == '\t' || c == '\n' || c == '\r' || c == '\f'
		|| c == '\v');
}

int	skip_spaces(char *input, int i)
{
	while (input[i] && is_space(input[i]))
	{
		i++;
	}
	return (i);
}
