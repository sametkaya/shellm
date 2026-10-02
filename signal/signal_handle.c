

#include "../minishell.h"

void	handle_sigint_parent(int sig)
{
	(void)sig;
	g_interrupt_flag = 1;
	write(STDOUT_FILENO, "\n", 1);
	rl_replace_line("", 0);
	rl_on_new_line();
	rl_redisplay();
}

void	handle_sigint_child(int sig)
{
	(void)sig;
	exit(130);
}

void	handle_sigint_heredoc(int sig)
{
	(void)sig;
	free_heredoc(NULL);
	exit(130);
}

void	handle_sigquit_child(int sig)
{
	(void)sig;
	exit(131);
}
