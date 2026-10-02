#include "minishell.h"

/*
** SheLLM v2 fixes:
**  - An unmatched-quote error is written to standard error; exit status is 2.
**  - Parse errors set the shell->syntax_error flag (in script mode the shell
**    exits with status 2, as POSIX requires).
**  - The environment list is always accessed through shell->env_list, so no
**    dangling pointer is left when the variable at the head of the list is
**    unset.
*/

int	check_quotes(char *input)
{
	int	in_single;
	int	in_double;
	int	i;

	i = 0;
	in_single = 0;
	in_double = 0;
	while (input[i])
	{
		if (input[i] == '"' && !in_single)
			in_double = !in_double;
		else if (input[i] == '\'' && !in_double)
			in_single = !in_single;
		i++;
	}
	if (in_double || in_single)
	{
		ft_putstr_fd("shellm: syntax error: unmatched quote\n", 2);
		return (0);
	}
	return (1);
}

void	process_input(char *input, t_env *env_list, t_shell *shell)
{
	t_token	**tokens;

	(void)env_list;
	tokens = NULL;
	shell->ast = NULL;
	shell->cmd_not_found = 0;
	if (!input || !*input)
		return ;
	if (!check_quotes(input))
	{
		shell->exit_code = 2;
		shell->syntax_error = 1;
		shell->cmd_not_found = line_looks_like_text(input, shell->env_list);
		return ;
	}
	tokens = tokenize_with_expansion(input, shell);
	if (!tokens)
		return ;
	shell->ast = parse_tokens(tokens);
	freetokens(tokens);
	tokens = NULL;
	if (!shell->ast)
	{
		shell->exit_code = 2;
		shell->syntax_error = 1;
		return ;
	}
	shell->cmd_not_found = ast_has_unknown_command(shell->ast, shell->env_list);
	execute_ast(shell->ast, &shell->env_list, shell);
	if (shell->ast)
	{
		free_ast(shell->ast);
		shell->ast = NULL;
	}
}

void	initshell(t_shell *shell, char **envp)
{
	ft_bzero(shell, sizeof(*shell));
	shell->exit_code = 0;
	shell->envp = envp;
	shell->saved_stdin = -1;
	shell->saved_stdout = -1;
	shell->heredoc_fd = -1;
	shell->ai_pid = -1;
}

int	handle_exit(char *input, t_env *env_list)
{
	(void)env_list;
	(void)input;
	return (0);
}
