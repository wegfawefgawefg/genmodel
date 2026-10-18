"""Tiny s-expression reader for our data files: nested lists of strings."""


def parse_sexp(text):
    """Nested lists of strings; ; starts a comment, "quoted" strings keep their spaces."""
    tokens, i = [], 0
    while i < len(text):
        c = text[i]
        if c == ";":
            while i < len(text) and text[i] != "\n":
                i += 1
        elif c in "()":
            tokens.append(c)
            i += 1
        elif c == '"':
            j = text.index('"', i + 1)
            tokens.append(text[i + 1 : j])
            i = j + 1
        elif c.isspace():
            i += 1
        else:
            j = i
            while j < len(text) and not text[j].isspace() and text[j] not in '();"':
                j += 1
            tokens.append(text[i:j])
            i = j
    stack = [[]]
    for t in tokens:
        if t == "(":
            stack.append([])
        elif t == ")":
            done = stack.pop()
            stack[-1].append(done)
        else:
            stack[-1].append(t)
    return stack[0]


def field(form, head, default=None):
    for f in form:
        if isinstance(f, list) and f and f[0] == head:
            return f[1:]
    return default
