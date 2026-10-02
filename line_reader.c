#include "minishell.h"

/*
** SheLLM v2: Line reading in script (non-tty) mode.
** As Bash does, input is read one byte at a time, so the child process that
** reads a heredoc body and the parent process can share the same file
** descriptor without buffering problems.
*/
char	*read_line_fd(int fd)
{
	char	*buf;
	char	*tmp;
	size_t	len;
	size_t	cap;
	char	c;
	ssize_t	r;

	cap = 128;
	len = 0;
	buf = malloc(cap);
	if (!buf)
		return (NULL);
	while (1)
	{
		r = read(fd, &c, 1);
		if (r < 0 && errno == EINTR)
			continue ;
		if (r <= 0)
			break ;
		if (c == '\n')
			break ;
		if (len + 2 > cap)
		{
			tmp = malloc(cap * 2);
			if (!tmp)
				return (free(buf), NULL);
			ft_memcpy(tmp, buf, len);
			free(buf);
			buf = tmp;
			cap *= 2;
		}
		buf[len++] = c;
	}
	if (r <= 0 && len == 0)
		return (free(buf), NULL);
	buf[len] = '\0';
	return (buf);
}
