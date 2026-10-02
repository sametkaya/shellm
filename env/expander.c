

#include "../minishell.h"

static int	process_char(char **result, const char *str, int *i, t_shell *shell)
{
	if (str[*i] == '$')
	{
		if (!handle_dollar_expansion(result, str, i, shell))
			return (0);
	}
	else
	{
		if (!add_char_to_result(result, str[*i]))
			return (0);
		(*i)++;
	}
	return (1);
}

static char	*init_expansion(const char *str, t_shell *shell)
{
	if (!str || !shell)
		return (NULL);
	if (!ft_strchr(str, '$'))
		return (ft_strdup(str));
	return (ft_strdup(""));
}

char	*expand_string_with_vars(const char *str, t_shell *shell)
{
	char	*result;
	int		i;

	result = init_expansion(str, shell);
	if (!result || !ft_strchr(str, '$'))
		return (result);
	i = 0;
	while (str[i])
	{
		if (!process_char(&result, str, &i, shell))
		{
			if (result)
				free(result);
			return (NULL);
		}
	}
	return (result);
}
