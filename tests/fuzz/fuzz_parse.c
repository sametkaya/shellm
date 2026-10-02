/*
** libFuzzer target: SheLLM's lexer, parser and suggestion checks. The input
** is not executed; only the quote check, word splitting and expansion ($VAR,
** ~, glob), AST construction/freeing, and the risk, syntax and secret checks
** are run. Must be run in an empty directory (because of glob expansion).
*/
#include "../../minishell.h"
#include <stdint.h>

extern char	**environ;

int	LLVMFuzzerTestOneInput(const uint8_t *data, size_t size)
{
	static t_shell	sh;
	static int		init;
	char			*s;
	t_token			**t;
	t_ast			*a;
	size_t			i;

	if (!init)
	{
		initshell(&sh, environ);
		sh.env_list = init_env_list(environ);
		init = 1;
	}
	if (size > 4096)
		return (0);
	s = malloc(size + 1);
	if (!s)
		return (0);
	memcpy(s, data, size);
	s[size] = '\0';
	for (i = 0; i < size; i++)
		if (s[i] == '\n' || s[i] == '\0')
			s[i] = ' ';
	(void)risk_reason(s);
	(void)syntax_issue(s);
	(void)secret_reason(s);
	if (!check_quotes(s))
		(void)line_looks_like_text(s, sh.env_list);
	else
	{
		t = tokenize_with_expansion(s, &sh);
		if (t)
		{
			a = parse_tokens(t);
			freetokens(t);
			if (a)
			{
				(void)ast_has_unknown_command(a, sh.env_list);
				free_ast(a);
			}
		}
	}
	free(s);
	return (0);
}
