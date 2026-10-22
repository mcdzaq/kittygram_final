"""Create a private local .env without overwriting existing configuration."""

import secrets
from pathlib import Path


def main():
    root = Path(__file__).resolve().parent.parent
    target = root / '.env'
    if target.exists():
        print('.env already exists; kept unchanged.')
        return
    source = (root / '.env.example').read_text()
    values = {
        'SECRET_KEY': secrets.token_urlsafe(64),
        'POSTGRES_PASSWORD': secrets.token_urlsafe(32),
    }
    lines = [
        f'{line.split("=", 1)[0]}={values[line.split("=", 1)[0]]}'
        if line.split('=', 1)[0] in values else line
        for line in source.splitlines()
    ]
    with target.open('x') as stream:
        target.chmod(0o600)
        stream.write('\n'.join(lines) + '\n')
    print('Created .env with generated secrets (mode 0600).')


if __name__ == '__main__':
    main()
