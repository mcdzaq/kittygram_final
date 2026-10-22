"""Exercise the real HTTP gateway; seed before recreation, verify afterwards."""

import argparse
import base64
import json
import re
import secrets
import struct
import urllib.error
import urllib.parse
import urllib.request
import zlib
from pathlib import Path


def png():
    def chunk(kind, data):
        return (struct.pack('!I', len(data)) + kind + data
                + struct.pack('!I', zlib.crc32(kind + data)))

    # A real RGB PNG fixture, generated without optional imaging dependencies.
    pixels = b''.join(b'\0' + b'\x80\x60\x40' * 32 for _ in range(32))
    return (b'\x89PNG\r\n\x1a\n'
            + chunk(b'IHDR', struct.pack('!2I5B', 32, 32, 8, 2, 0, 0, 0))
            + chunk(b'IDAT', zlib.compress(pixels)) + chunk(b'IEND', b''))


class Client:
    def __init__(self, base):
        self.base = base.rstrip('/')
        self.token = None

    def request(self, path, method='GET', data=None, status=200, raw=False):
        headers = {}
        if self.token:
            headers['Authorization'] = f'Token {self.token}'
        if data is not None:
            headers['Content-Type'] = 'application/json'
        request = urllib.request.Request(
            self.base + path, method=method, headers=headers,
            data=json.dumps(data).encode() if data is not None else None,
        )
        try:
            response = urllib.request.urlopen(request, timeout=20)
        except urllib.error.HTTPError as error:
            response = error
        with response:
            body = response.read()
            if response.status != status:
                # Do not print credentials from request/response payloads.
                raise AssertionError(
                    f'{method} {path}: expected {status}, got {response.status}'
                )
        if raw:
            return body
        return json.loads(body) if body else None

    def infrastructure(self):
        document = self.request('/', raw=True)
        html = document.decode()
        assert 'Kittygram' in html
        for route in ('/signin', '/cats/1'):
            assert self.request(route, raw=True) == document, route
        assets = re.findall(r'(?:src|href)="(/static/[^\"]+\.(?:js|css))"', html)
        assert assets, 'Frontend build has no static asset references'
        for asset in assets:
            content = self.request(asset, raw=True)
            assert content and not content.startswith(b'<!doctype html>'), asset
        css = self.request('/static/admin/css/base.css', raw=True)
        assert b'body' in css
        assert b'csrfmiddlewaretoken' in self.request('/admin/login/', raw=True)
        self.request('/api/cats/', status=401)
        self.request('/static/missing-smoke.js', status=404, raw=True)


def seed(client, state_path):
    assert not state_path.exists(), 'State exists; verify it or choose another --state'
    client.infrastructure()
    username = 'smoke_' + secrets.token_hex(5)
    password = secrets.token_urlsafe(24)
    account = {'username': username, 'password': password}
    user = client.request('/api/users/', 'POST', account, status=201)
    client.token = client.request('/api/token/login/', 'POST', account)['auth_token']
    cat = client.request('/api/cats/', 'POST', {
        'name': 'Барсик', 'color': '#000000', 'birth_year': 2022,
        'achievements': [{'achievement_name': 'Пережил перезапуск'}],
        'image': 'data:image/png;base64,' + base64.b64encode(png()).decode(),
    }, status=201)
    assert cat['owner'] == user['id']
    assert cat['color'] == 'black'
    media = urllib.parse.urlsplit(cat['image_url']).path
    assert media.startswith('/media/')
    assert client.request(media, raw=True) == png()
    state_path.parent.mkdir(parents=True, exist_ok=True)
    with state_path.open('x') as stream:
        state_path.chmod(0o600)
        json.dump({**account, 'token': client.token, 'cat_id': cat['id'],
                   'media': media, 'base': client.base}, stream)
    print('PASS: SPA, frontend/admin static, auth, registration, cat and photo.')
    print(f'Saved private smoke state to {state_path}. Recreate containers, then verify.')


def verify(client, state_path):
    state = json.loads(state_path.read_text())
    assert state['base'] == client.base, 'Use the same --url as the seed run'
    client.infrastructure()
    account = {key: state[key] for key in ('username', 'password')}
    token = client.request('/api/token/login/', 'POST', account)['auth_token']
    assert token == state['token'], 'Authentication token did not persist'
    client.token = token
    path = f'/api/cats/{state["cat_id"]}/'
    cat = client.request(path)
    assert cat['name'] == 'Барсик'
    assert cat['achievements'][0]['achievement_name'] == 'Пережил перезапуск'
    cats = client.request('/api/cats/')
    assert cats['count'] >= 1
    assert client.request(state['media'], raw=True) == png()
    updated = client.request(path, 'PATCH', {'birth_year': 2021})
    assert updated['birth_year'] == 2021
    client.request(path, 'PATCH', {'birth_year': 2022})
    temporary = client.request('/api/cats/', 'POST', {
        'name': 'Удаляемый', 'color': '#FFFFFF', 'birth_year': 2020,
    }, status=201)
    temporary_path = f'/api/cats/{temporary["id"]}/'
    client.request(temporary_path, 'DELETE', status=204)
    client.request(temporary_path, status=404)
    print('PASS: PostgreSQL user/token/cat/achievements and media survive recreation; CRUD works.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=('seed', 'verify'))
    parser.add_argument('--url', default='http://localhost:9000')
    parser.add_argument('--state', type=Path, default=Path('.local/smoke.json'))
    args = parser.parse_args()
    client = Client(args.url)
    (seed if args.phase == 'seed' else verify)(client, args.state)


if __name__ == '__main__':
    main()
