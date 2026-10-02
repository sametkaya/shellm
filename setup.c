#include "minishell.h"
#include <sys/types.h>
#include <sys/wait.h>
#include <signal.h>
#include <stdio.h>
#include <errno.h>

/*
** Setup wizard and first start.
** The wizard itself lives next to ai_helper.py (python3 ai_helper.py --setup);
** the shell only starts it and waits for it to finish. Settings are kept in
** $XDG_CONFIG_HOME/shellm/config (or ~/.config/shellm/config) with mode 0600,
** so that only the user can read them.
*/

#ifndef SHELLM_VERSION
# define SHELLM_VERSION "1.0.0"
#endif

const char	*shellm_version(void)
{
	return (SHELLM_VERSION);
}

static int	wait_child(pid_t pid)
{
	int	st;

	while (waitpid(pid, &st, 0) < 0)
	{
		if (errno != EINTR)
			return (1);
	}
	if (WIFEXITED(st))
		return (WEXITSTATUS(st));
	return (1);
}

int	shellm_run_setup(void)
{
	char	*helper;
	pid_t	pid;
	int		ret;
	void	(*old_int)(int);
	void	(*old_quit)(int);

	helper = ai_find_helper();
	if (!helper)
	{
		ft_putstr_fd(TR("SheLLM: ai_helper.py not found; cannot run setup.\n",
				"SheLLM: ai_helper.py bulunamadı; kurulum yapılamıyor.\n"), 2);
		return (1);
	}
	old_int = signal(SIGINT, SIG_IGN);
	old_quit = signal(SIGQUIT, SIG_IGN);
	pid = fork();
	if (pid == 0)
	{
		signal(SIGINT, SIG_DFL);
		signal(SIGQUIT, SIG_DFL);
		execlp("python3", "python3", helper, "--setup", (char *)NULL);
		perror("SheLLM: python3");
		_exit(127);
	}
	free(helper);
	ret = 1;
	if (pid > 0)
		ret = wait_child(pid);
	signal(SIGINT, old_int);
	signal(SIGQUIT, old_quit);
	ui_lang_reset();
	return (ret);
}

static int	config_exists(void)
{
	char		path[4096];
	const char	*xdg;
	const char	*home;

	xdg = getenv("XDG_CONFIG_HOME");
	home = getenv("HOME");
	if (xdg && *xdg)
		snprintf(path, sizeof(path), "%s/shellm/config", xdg);
	else if (home && *home)
		snprintf(path, sizeof(path), "%s/.config/shellm/config", home);
	else
		return (1);
	return (access(path, F_OK) == 0);
}

/* 1 if there is no settings file and no provider or key in the environment. */
int	shellm_needs_setup(void)
{
	static const char	*vars[] = {"SHELLM_BACKEND", "GEMINI_API_KEY",
		"GOOGLE_API_KEY", "ANTHROPIC_API_KEY", "OPENAI_API_KEY", NULL};
	const char			*v;
	int					i;

	v = getenv("SHELLM_AI");
	if ((v && !ft_strcmp(v, "0")) || getenv("SHELLM_NO_SETUP"))
		return (0);
	i = 0;
	while (vars[i])
	{
		v = getenv(vars[i++]);
		if (v && *v)
			return (0);
	}
	return (!config_exists());
}
