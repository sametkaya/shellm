

#include "../minishell.h"

/*
** SheLLM v2: The temporary file is created with mkstemp(3), with an
** unpredictable name and 0600 permissions. The fixed /tmp/minishell_heredoc_N
** names in the old version let concurrently running shells overwrite each
** other's heredoc contents and were open to symbolic link attacks.
*/
char	*create_heredoc_temp_file(t_shell *shell)
{
	char	*temp_file;
	int		fd;

	(void)shell;
	temp_file = ft_strdup("/tmp/shellm_heredoc_XXXXXX");
	if (!temp_file)
		return (NULL);
	fd = mkstemp(temp_file);
	if (fd == -1)
	{
		perror("shellm: heredoc");
		free(temp_file);
		return (NULL);
	}
	close(fd);
	return (temp_file);
}

void	cleanup_heredoc_child(t_shell *shell, t_env **env_list)
{
	rl_clear_history();
	if (shell->ast)
	{
		free_ast(shell->ast);
		shell->ast = NULL;
	}
	if (*env_list)
	{
		free_env_list(*env_list);
		*env_list = NULL;
	}
	if (shell->heredoc_temp_files)
		free_heredoc_list(shell);
}

int	setup_heredoc_child(t_shell *shell, const char *temp_file)
{
	int	fd;

	set_signal_mode(SIGMODE_HEREDOC, shell);
	free_heredoc(shell);
	fd = open(temp_file, O_WRONLY | O_CREAT | O_TRUNC, 0644);
	shell->heredoc_fd = fd;
	if (fd == -1)
	{
		perror("heredoc temp file");
		exit(1);
	}
	return (fd);
}

void	write_line_to_heredoc(int fd, char *line, int should_expand,
		t_shell *shell)
{
	char	*expanded_line;

	if (should_expand)
	{
		expanded_line = expand_string_with_vars(line, shell);
		if (expanded_line)
		{
			write(fd, expanded_line, ft_strlen(expanded_line));
			free(expanded_line);
		}
		else
			write(fd, line, ft_strlen(line));
	}
	else
		write(fd, line, ft_strlen(line));
	write(fd, "\n", 1);
}

static char	*heredoc_read(t_shell *shell)
{
	if (shell->interactive)
		return (readline("> "));
	return (read_line_fd(STDIN_FILENO));
}

void	heredoc_input_loop(int fd, const char *delimiter, int should_expand,
		t_shell *shell)
{
	char	*line;

	while (1)
	{
		line = heredoc_read(shell);
		if (!line)
		{
			ft_putstr_fd("shellm: warning: here-document delimited by "
				"end-of-file (wanted `", 2);
			ft_putstr_fd((char *)delimiter, 2);
			ft_putstr_fd("')\n", 2);
			break ;
		}
		if (ft_strcmp(line, delimiter) == 0)
		{
			free(line);
			break ;
		}
		write_line_to_heredoc(fd, line, should_expand, shell);
		free(line);
	}
}
