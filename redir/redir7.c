

#include "../minishell.h"

int	read_heredoc(const char *delimiter, int should_expand,
		t_shell *shell, const char *temp_file)
{
	int		fd;
	pid_t	child_pid;
	int		status;

	child_pid = fork();
	if (child_pid == -1)
	{
		perror("fork heredoc");
		return (-1);
	}
	if (child_pid == 0)
	{
		fd = setup_heredoc_child(shell, temp_file);
		heredoc_input_loop(fd, delimiter, should_expand, shell);
		close(fd);
		cleanup_heredoc_child(shell, &shell->env_list);
		exit(0);
	}
	waitpid(child_pid, &status, 0);
	return (handle_child_exit_status(status, shell, temp_file));
}

/*
** SheLLM v2: In Bash, if any part of the delimiter is quoted (single or
** double), no expansion is performed in the body. The old version performed
** expansion when the delimiter was double-quoted.
*/
void	set_heredoc_delimiter_and_expansion(t_redirection *redir)
{
	redir->delimiter = ft_strdup(redir->filename);
	redir->should_expand = (redir->quote_type == Q_NONE);
}
