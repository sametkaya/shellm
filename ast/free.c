

#include "../minishell.h"

void	free_env_list(t_env *env_list)
{
	t_env	*temp;

	temp = NULL;
	while (env_list)
	{
		temp = env_list;
		env_list = env_list->next;
		free(temp->key);
		free(temp->value);
		free(temp);
	}
}

void	free_env_array(char **envp)
{
	int	i;

	i = 0;
	while (envp && envp[i])
		free(envp[i++]);
	free(envp);
}

void	free_key_value(char *key, char *value)
{
	if (key)
		free(key);
	if (value)
		free(value);
}
