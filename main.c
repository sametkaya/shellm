#include "minishell.h"
#include <sys/types.h>
#include <sys/wait.h>
#include <signal.h>
#include <stdio.h>
#include <strings.h>

/*
** SheLLM v2 main loop.
**
** Main fixes over v1:
**  - Interactive and script (non-tty) modes are separate. In script mode the
**    prompt, interface decorations and the AI are disabled; lines are read
**    byte by byte, and on a syntax error the shell exits with status 2, as
**    POSIX requires.
**  - The AI flow no longer resets the exit status: if a suggestion is skipped,
**    $? stays 127; if it is run, $? is the suggestion's exit status.
**  - The AI service is stopped explicitly and only in the main process, not in
**    an atexit handler. In v1 the atexit handler also ran in every forked child
**    (pipelines, here-documents) and killed the service.
**  - The environment list has a single source (shell->env_list).
*/

static pid_t	g_owner_pid = 0;
static t_shell	*g_shell = NULL;

static void	cleanup_at_exit(void)
{
	if (g_shell && getpid() == g_owner_pid)
		ai_stop(g_shell);
}

static int	only_space(char *input)
{
	int	i;

	i = 0;
	while (input[i])
	{
		if (!is_space(input[i]))
			return (0);
		i++;
	}
	return (1);
}

int	whitespace_check(char *input)
{
	if (input[0] == '\0' || only_space(input))
	{
		free(input);
		return (1);
	}
	return (0);
}

/* Runs one command line; returns 1 if the shell should exit. */
static int	run_line(char *input, t_shell *shell, int add_hist)
{
	if (add_hist)
		add_history(input);
	if (shell->needs_heredoc_cleanup && shell->heredoc_temp_files)
	{
		cleanup_heredoc_temp_files(shell);
		shell->needs_heredoc_cleanup = 0;
	}
	shell->syntax_error = 0;
	process_input(input, shell->env_list, shell);
	return (shell->should_exit);
}

/* ----------------------------- AI flow ----------------------------- */

/*
** Confirmation does not depend on the interface language: a risky suggestion
** runs only after the full word "yes" or "evet" (any case); an ordinary one
** also accepts "y" or "e". Any other answer skips the suggestion.
*/
static int	full_word(const char *answer)
{
	return (!strcasecmp(answer, "yes") || !ft_strcmp(answer, "evet")
		|| !ft_strcmp(answer, "EVET") || !ft_strcmp(answer, "Evet"));
}

static int	confirmed(const char *answer, const char *risk)
{
	if (!answer)
		return (0);
	if (full_word(answer))
		return (1);
	if (risk)
		return (0);
	return ((answer[0] == 'e' || answer[0] == 'E' || answer[0] == 'y'
			|| answer[0] == 'Y') && answer[1] == '\0');
}

static int	process_ai_suggestion(char *line, t_shell *shell)
{
	t_ai_reply	rep;
	int			r;
	char		*answer;
	const char	*risk;
	int			failed_code;
	char		msg[160];

	failed_code = shell->exit_code;
	risk = secret_reason(line);
	if (risk)
	{
		snprintf(msg, sizeof(msg), TR("line not sent to the model: %s",
				"satır modele gönderilmedi: %s"), risk);
		ui_notify(2, msg);
		return (0);
	}
	ui_spinner_start();
	r = ai_request(shell, line, failed_code, &rep);
	ui_spinner_clear();
	if (r <= 0)
	{
		if (r < 0)
			ui_notify(2, TR("AI request cancelled or timed out",
					"yapay zekâ isteği iptal edildi ya da zaman aşımına uğradı"));
		free(rep.text);
		shell->exit_code = failed_code;
		return (0);
	}
	risk = risk_reason(rep.text);
	ui_ai_suggestion(rep.text, risk, syntax_issue(rep.text));
	answer = readline("");
	if (confirmed(answer, risk))
	{
		free(answer);
		r = run_line(rep.text, shell, 1);
		free(rep.text);
		return (r);
	}
	free(answer);
	free(rep.text);
	shell->exit_code = failed_code;
	return (0);
}

/*
** A line of the form "# request" is never executed: if the AI is enabled it
** is sent directly to the helper, otherwise it is a comment, as in Bash. This
** is the explicit path for natural-language requests that start with a
** program name ("find all python files").
*/
static int	is_comment(const char *line)
{
	while (*line == ' ' || *line == '\t')
		line++;
	return (*line == '#');
}

static char	*explicit_request(char *line)
{
	while (*line == ' ' || *line == '\t')
		line++;
	if (*line != '#')
		return (NULL);
	line++;
	while (*line == ' ' || *line == '\t')
		line++;
	if (!*line)
		return (NULL);
	return (line);
}

/* ------------------------------ loops ------------------------------ */

static void	interactive_loop(t_shell *shell)
{
	char	*input;
	int		stop;

	ui_topbar(shell->ai_ready, shell->ai_status);
	while (1)
	{
		set_signal_mode(SIGMODE_PROMPT, shell);
		input = readline("🎀 sheLLM ");
		if (!input)
		{
			ft_putstr_fd("exit\n", STDERR_FILENO);
			break ;
		}
		if (whitespace_check(input))
			continue ;
		check_and_reset_signal(shell);
		set_signal_mode(SIGMODE_NEUTRAL, shell);
		if (is_comment(input))
		{
			add_history(input);
			if (shell->ai_ready && explicit_request(input))
				stop = process_ai_suggestion(explicit_request(input), shell);
		}
		else
		{
			stop = run_line(input, shell, 1);
			if (!stop && shell->ai_ready && shell->cmd_not_found)
				stop = process_ai_suggestion(input, shell);
		}
		free(input);
		if (stop)
			break ;
	}
	rl_clear_history();
}

static void	script_loop(t_shell *shell)
{
	char	*input;
	int		stop;

	while (1)
	{
		input = read_line_fd(STDIN_FILENO);
		if (!input)
			break ;
		if (whitespace_check(input))
			continue ;
		set_signal_mode(SIGMODE_NEUTRAL, shell);
		stop = run_line(input, shell, 0);
		free(input);
		if (stop || shell->syntax_error)
			break ;
	}
}

/* --check "command": helper mode for testing the suggestion checks. */
static int	check_mode(const char *cmd)
{
	const char	*r;
	const char	*s;

	r = risk_reason(cmd);
	s = syntax_issue(cmd);
	printf("risk\t%s\nsyntax\t%s\n", r ? r : "-", s ? s : "-");
	printf("secret\t%s\n", secret_reason(cmd) ? secret_reason(cmd) : "-");
	return ((r != NULL) | ((s != NULL) << 1));
}

static void	usage(int fd)
{
	ft_putstr_fd(TR("Usage: shellm [option]\n"
			"  (no option)           start the interactive shell\n"
			"  --setup               configure the language model and API key\n"
			"  --check \"command\"     show the risk and syntax checks for a command\n"
			"  --version, -v         show the version\n"
			"  --help, -h            show this help\n"
			"Settings file: ~/.config/shellm/config\n"
			"Interface language: English; set SHELLM_LANG=tr for Turkish.\n",
			"Kullanım: shellm [seçenek]\n"
			"  (seçeneksiz)          etkileşimli kabuğu başlatır\n"
			"  --setup               dil modeli ve API anahtarı ayarlarını yapar\n"
			"  --check \"komut\"       komutun risk ve sözdizimi denetimini gösterir\n"
			"  --version, -v         sürümü gösterir\n"
			"  --help, -h            bu yardımı gösterir\n"
			"Ayar dosyası: ~/.config/shellm/config\n"
			"Arayüz dili: Türkçe (SHELLM_LANG=en ile İngilizce).\n"), fd);
}

int	main(int argc, char **argv, char **envp)
{
	t_shell	shell;

	if (argc == 3 && !ft_strcmp(argv[1], "--check"))
		return (check_mode(argv[2]));
	if (argc == 2 && (!ft_strcmp(argv[1], "--version")
			|| !ft_strcmp(argv[1], "-v")))
		return (printf("SheLLM %s\n", shellm_version()), 0);
	if (argc == 2 && (!ft_strcmp(argv[1], "--help")
			|| !ft_strcmp(argv[1], "-h")))
		return (usage(1), 0);
	if (argc == 2 && !ft_strcmp(argv[1], "--setup"))
		return (shellm_run_setup());
	if (argc != 1)
		return (usage(2), 2);
	initshell(&shell, envp);
	shell.env_list = init_env_list(envp);
	shell.interactive = isatty(STDIN_FILENO);
	shell.mode = shell.interactive;
	g_owner_pid = getpid();
	g_shell = &shell;
	atexit(cleanup_at_exit);
	if (shell.interactive)
	{
		if (shellm_needs_setup())
			shellm_run_setup();
		ai_start(&shell, argv[0]);
		hide_api_keys(&shell);
		interactive_loop(&shell);
	}
	else
		script_loop(&shell);
	if (shell.heredoc_temp_files)
		cleanup_heredoc_temp_files(&shell);
	ai_stop(&shell);
	g_shell = NULL;
	free_env_list(shell.env_list);
	shell.env_list = NULL;
	return (shell.exit_code);
}
