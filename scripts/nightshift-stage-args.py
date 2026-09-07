"""Parse invocation-scoped auth without evaluating shell or inheriting authority."""
import json
import shlex
import sys

try:
    tokens = shlex.split(sys.argv[1])
    remaining = []
    auth = 'subscription'
    seen = False
    position = 0
    while position < len(tokens):
        token = tokens[position]
        if token == '--auth':
            if seen or position + 1 == len(tokens) or tokens[position + 1] not in ('api', 'subscription'):
                raise ValueError('one --auth subscription|api option is permitted')
            seen = True
            auth = tokens[position + 1]
            position += 2
        else:
            remaining.append(token)
            position += 1
    print(json.dumps(dict(auth=auth, arguments=' '.join(remaining), argv=remaining)))
except (ValueError, IndexError) as error:
    print(str(error), file=sys.stderr)
    sys.exit(64)
