

#include "../minishell.h"


void	init_child_shell(t_shell *child_shell, t_shell *parent_shell)
{
	ft_bzero(child_shell, sizeof(t_shell));
	child_shell->saved_stdin = -2;
	child_shell->saved_stdout = -1;
	child_shell->env_list = parent_shell->env_list;
	child_shell->interactive = parent_shell->interactive;
	child_shell->exit_code = parent_shell->exit_code;
	copy_heredoc_info_to_child(parent_shell, child_shell);
}

void	setup_right_child_pipe(int pipe_fd[2], t_shell *child_shell,
		t_env *env_list, t_ast *root_ast)
{
	t_cleanup_ctx	ctx;

	if (dup2(pipe_fd[0], STDIN_FILENO) == -1)
	{
		perror("dup2 right child stdin");
		ctx = (t_cleanup_ctx){child_shell, env_list, NULL, root_ast, 1};
		child_cleanup_and_exit(&ctx);
	}
	close(pipe_fd[0]);
	close(pipe_fd[1]);
	set_signal_mode(SIGMODE_CHILD, NULL);
}

static void	handle_redir_or_error(t_ast *right, t_env *env_list,
	t_shell *child_shell, t_ast *root_ast)
{
	t_env			*env_copy;
	int				result;
	t_cleanup_ctx	ctx;

	if (right->type == NODE_REDIR)
	{
		env_copy = env_list;
		result = execute_redirection(right, &env_copy, child_shell);
		ctx = (t_cleanup_ctx){child_shell, env_list, NULL, root_ast, result};
		child_cleanup_and_exit(&ctx);
	}
	else
	{
		ft_putstr_fd("shellm: unhandled node type\n", 2);
		ctx = (t_cleanup_ctx){child_shell, env_list, NULL, root_ast, 1};
		child_cleanup_and_exit(&ctx);
	}
}

void	handle_right_child_node(t_ast *right, t_env *env_list,
	t_shell *child_shell, t_ast *root_ast)
{
	t_cleanup_ctx	ctx;
	int				result;

	if (right->type == NODE_COMMAND)
	{
		if (setup_command_redirections(right, &env_list, child_shell) != 0)
		{
			ctx = (t_cleanup_ctx){child_shell, env_list, NULL, root_ast, 1};
			child_cleanup_and_exit(&ctx);
		}
		execute_command_in_child(right, env_list, child_shell, root_ast);
	}
	else if (right->type == NODE_PIPE)
	{
		result = execute_pipe(right, env_list, child_shell, root_ast);
		ctx = (t_cleanup_ctx){child_shell, env_list, NULL, root_ast, result};
		child_cleanup_and_exit(&ctx);
	}
	else
		handle_redir_or_error(right, env_list, child_shell, root_ast);
}

/*
** SheLLM v2: The waitpid status word is decoded with the POSIX macros. For
** processes terminated by a signal, 128 + the signal number is returned, as
** in Bash (e.g. SIGTERM -> 143, SIGKILL -> 137). The old version used the
** raw status value directly as the exit status (SIGTERM -> 15).
*/
int	shell_status_from_wait(int status, t_shell *shell)
{
	int	sig;

	if (WIFEXITED(status))
		shell->exit_code = WEXITSTATUS(status);
	else if (WIFSIGNALED(status))
	{
		sig = WTERMSIG(status);
		if (sig == SIGINT && shell->interactive)
			write(STDOUT_FILENO, "\n", 1);
		else if (sig != SIGINT && sig != SIGPIPE)
		{
			ft_putstr_fd(strsignal(sig), STDERR_FILENO);
			if (WCOREDUMP(status))
				ft_putstr_fd(" (core dumped)", STDERR_FILENO);
			ft_putstr_fd("\n", STDERR_FILENO);
		}
		shell->exit_code = 128 + sig;
	}
	else
		shell->exit_code = 1;
	return (shell->exit_code);
}

int	handle_process_status(int status, t_shell *shell)
{
	return (shell_status_from_wait(status, shell));
}
