NAME = SheLLM
VERSION = 1.0.0
CC = cc

# Install paths: make install PREFIX=$$HOME/.local  |  sudo make install
PREFIX ?= /usr/local
DESTDIR ?=
BINDIR = $(PREFIX)/bin
DATADIR = $(PREFIX)/share/shellm
DOCDIR = $(PREFIX)/share/doc/shellm

CFLAGS = -Wall -Wextra -Werror -g \
		 -DSHELLM_VERSION='"$(VERSION)"' \
		 -DSHELLM_DATADIR='"$(DATADIR)"' \
		 -I./libft \
		 -I./ast \
		 -I./builtins \
		 -I./env \
		 -I./redir \
		 -I./signal \
		 -I./tokens

SRCS = $(filter-out tests/%,$(wildcard *.c */*.c */*/*.c))
OBJS = $(SRCS:.c=.o)

LIBFT_DIR = ./libft
LIBFT = $(LIBFT_DIR)/libft.a

all: $(NAME)

$(NAME): $(OBJS) $(LIBFT)
	$(CC) $(CFLAGS) $(OBJS) $(LIBFT) -lreadline -o $(NAME)

$(LIBFT):
	$(MAKE) -C $(LIBFT_DIR)

clean:
	$(MAKE) -C $(LIBFT_DIR) clean
	rm -f $(OBJS)

fclean: clean
	$(MAKE) -C $(LIBFT_DIR) fclean
	rm -f $(NAME) $(LEGACY_GUARD) tests/guard/ai_guard_old.o

re: fclean all

leaks:
	@echo "Running valgrind..."
	@valgrind --leak-check=full \
			  --show-leak-kinds=all \
			  --track-origins=yes \
			  --track-fds=yes \
			  --verbose \
			  --suppressions=valgrind.supp \
			  ./$(NAME)

install: $(NAME)
	install -d $(DESTDIR)$(BINDIR) $(DESTDIR)$(DATADIR) $(DESTDIR)$(DOCDIR)
	install -m 755 $(NAME) $(DESTDIR)$(BINDIR)/shellm
	install -m 644 ai_helper.py $(DESTDIR)$(DATADIR)/ai_helper.py
	install -m 644 shellm_setup.py $(DESTDIR)$(DATADIR)/shellm_setup.py
	install -m 644 README.md INSTALL.md CHANGES.md $(DESTDIR)$(DOCDIR)/
	install -m 644 docs/INSTALL.tr.md $(DESTDIR)$(DOCDIR)/INSTALL.tr.md
	@echo "SheLLM $(VERSION) installed: $(DESTDIR)$(BINDIR)/shellm"

uninstall:
	rm -f $(DESTDIR)$(BINDIR)/shellm
	rm -rf $(DESTDIR)$(DATADIR) $(DESTDIR)$(DOCDIR)
	@echo "SheLLM removed (the settings in ~/.config/shellm are kept)."

# The guard rules before the review-driven revision (tests/guard/ai_guard_old.c),
# linked into the current shell; used as the "old" rules by the guard evaluations.
LEGACY_GUARD = tests/guard/shellm_old_guard
LEGACY_OBJS = $(filter-out ai_risk.o ai_guard.o,$(OBJS))

legacy-guard: $(LEGACY_GUARD)

$(LEGACY_GUARD): $(LEGACY_OBJS) $(LIBFT) tests/guard/ai_guard_old.c
	$(CC) $(CFLAGS) -I. -c tests/guard/ai_guard_old.c -o tests/guard/ai_guard_old.o
	$(CC) $(CFLAGS) $(LEGACY_OBJS) tests/guard/ai_guard_old.o $(LIBFT) -lreadline -o $@

test: $(NAME)
	cd tests && python3 check_conformance.py

# Source tarball for users: the recorded experiment results (tests/results) are
# left out to keep it small; they are in the repository.
dist: fclean
	tar --exclude-vcs --exclude='__pycache__' --exclude='*.deb' --exclude='./tests/results' \
		--exclude='./analysis/output' --exclude='./tests/data/all.*' \
		--exclude='.build.log' --exclude='*.o' --exclude='*.a' --exclude='./SheLLM' \
		--transform 's,^\.,shellm-$(VERSION),' -czf ../shellm-$(VERSION).tar.gz .

.PHONY: all clean fclean re install uninstall test dist legacy-guard