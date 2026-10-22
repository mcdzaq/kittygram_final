"""Send a successful CI result to the configured owner's Telegram chat."""

import json
import os
import urllib.error
import urllib.parse
import urllib.request


def main():
    token = os.environ['TELEGRAM_TOKEN']
    chat = os.environ['TELEGRAM_TO']
    if not token or not chat:
        raise SystemExit('Set TELEGRAM_TOKEN and TELEGRAM_TO repository secrets.')
    repo = os.environ['GITHUB_REPOSITORY']
    run = os.environ['GITHUB_RUN_ID']
    commit = os.environ['GITHUB_SHA'][:12]
    text = (
        f'Kittygram: CI успешно завершён ({commit}).\n'
        'Backend, frontend и контейнеры проверены; три образа опубликованы.\n'
        'Развёртывание на учебном сервере — отдельный этап.\n'
        f'https://github.com/{repo}/actions/runs/{run}'
    )
    data = urllib.parse.urlencode({'chat_id': chat, 'text': text}).encode()
    request = urllib.request.Request(
        f'https://api.telegram.org/bot{token}/sendMessage', data=data,
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            result = json.load(response)
    except (urllib.error.URLError, TimeoutError):
        # Exception URLs contain the token, so never print exception details.
        raise SystemExit('Telegram notification failed; inspect bot/chat setup.') from None
    if not result.get('ok'):
        raise SystemExit('Telegram rejected the notification.')
    print('Telegram notification sent.')


if __name__ == '__main__':
    main()
