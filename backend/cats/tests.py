import base64
from http import HTTPStatus
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory

from django.contrib.auth import get_user_model
from django.test import override_settings
from PIL import Image
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from .models import Achievement, Cat


class CatsAPITestCase(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(username='cat_owner')
        cls.token = Token.objects.create(user=cls.user)

    def setUp(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token.key}')
        media_dir = TemporaryDirectory()
        self.addCleanup(media_dir.cleanup)
        self.media_root = Path(media_dir.name)
        media_settings = override_settings(MEDIA_ROOT=self.media_root)
        media_settings.enable()
        self.addCleanup(media_settings.disable)

    def create_cat(self, **overrides):
        payload = {'name': 'Мурка', 'color': '#FFFFFF', 'birth_year': 2020}
        payload.update(overrides)
        response = self.client.post('/api/cats/', payload, format='json')
        self.assertEqual(response.status_code, HTTPStatus.CREATED, response.data)
        return response

    def test_api_requires_authentication(self):
        self.client.credentials()
        for path in ('/api/cats/', '/api/achievements/'):
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, HTTPStatus.UNAUTHORIZED)

    def test_frontend_registration_login_and_logout(self):
        self.client.credentials()
        credentials = {
            'username': 'new_cat_owner',
            'password': 'A4-strong-kitty-password!92',
        }
        signup = self.client.post('/api/users/', credentials, format='json')
        self.assertEqual(signup.status_code, HTTPStatus.CREATED, signup.data)

        login = self.client.post('/api/token/login/', credentials, format='json')
        self.assertEqual(login.status_code, HTTPStatus.OK, login.data)
        self.client.credentials(
            HTTP_AUTHORIZATION=f'Token {login.data["auth_token"]}'
        )
        profile = self.client.get('/api/users/me/')
        self.assertEqual(profile.status_code, HTTPStatus.OK)
        self.assertEqual(profile.data['id'], signup.data['id'])

        logout = self.client.post('/api/token/logout/')
        self.assertEqual(logout.status_code, HTTPStatus.NO_CONTENT)
        self.assertEqual(
            self.client.get('/api/cats/').status_code, HTTPStatus.UNAUTHORIZED
        )

    def test_create_read_update_and_delete_cat(self):
        other_user = get_user_model().objects.create_user(username='other_owner')
        created = self.create_cat(owner=other_user.pk)
        self.assertEqual(created.data['owner'], self.user.pk)
        self.assertEqual(created.data['color'], 'white')
        self.assertEqual(created.data['achievements'], [])
        detail_url = f'/api/cats/{created.data["id"]}/'
        detail = self.client.get(detail_url)
        self.assertEqual(detail.status_code, HTTPStatus.OK)
        self.assertEqual(detail.data['name'], 'Мурка')

        updated = self.client.patch(
            detail_url, {'name': 'Барсик', 'color': '#000000'}, format='json'
        )
        self.assertEqual(updated.status_code, HTTPStatus.OK, updated.data)
        self.assertEqual(updated.data['name'], 'Барсик')
        self.assertEqual(updated.data['color'], 'black')
        self.assertEqual(updated.data['birth_year'], 2020)

        self.assertEqual(
            self.client.delete(detail_url).status_code, HTTPStatus.NO_CONTENT
        )
        self.assertEqual(
            self.client.get(detail_url).status_code, HTTPStatus.NOT_FOUND
        )

    def test_achievements_survive_partial_update_and_can_be_cleared(self):
        achievements = [{'achievement_name': 'Поймал мышь'}]
        first = self.create_cat(achievements=achievements)
        self.create_cat(name='Барсик', achievements=achievements)
        self.assertEqual(Achievement.objects.count(), 1)
        detail_url = f'/api/cats/{first.data["id"]}/'

        renamed = self.client.patch(detail_url, {'name': 'Мурзик'}, format='json')
        self.assertEqual(renamed.status_code, HTTPStatus.OK, renamed.data)
        self.assertEqual(
            renamed.data['achievements'][0]['achievement_name'], 'Поймал мышь'
        )
        replaced = self.client.patch(
            detail_url,
            {'achievements': [{'achievement_name': 'Спит весь день'}]},
            format='json',
        )
        self.assertEqual(replaced.status_code, HTTPStatus.OK, replaced.data)
        self.assertEqual(
            [item['achievement_name'] for item in replaced.data['achievements']],
            ['Спит весь день'],
        )
        cleared = self.client.patch(
            detail_url, {'achievements': []}, format='json'
        )
        self.assertEqual(cleared.status_code, HTTPStatus.OK)
        self.assertEqual(cleared.data['achievements'], [])
        available = self.client.get('/api/achievements/')
        self.assertEqual(available.status_code, HTTPStatus.OK)
        self.assertEqual(len(available.data), 2)

    def test_base64_photo_is_saved_and_can_be_detached(self):
        image = BytesIO()
        Image.new('RGB', (2, 2), color='orange').save(image, format='PNG')
        image_bytes = image.getvalue()
        photo = 'data:image/png;base64,' + base64.b64encode(image_bytes).decode()
        created = self.create_cat(image=photo)
        self.assertTrue(created.data['image_url'].startswith('/media/cats/images/'))
        self.assertTrue(created.data['image'].endswith(created.data['image_url']))
        cat = Cat.objects.get(pk=created.data['id'])
        self.assertEqual(Path(cat.image.path).read_bytes(), image_bytes)

        updated = self.client.patch(
            f'/api/cats/{cat.pk}/', {'image': None}, format='json'
        )
        self.assertEqual(updated.status_code, HTTPStatus.OK, updated.data)
        self.assertIsNone(updated.data['image'])
        self.assertIsNone(updated.data['image_url'])

    def test_invalid_color_and_image_return_validation_errors(self):
        for field, value in (('color', '#xyzxyz'), ('image', 'not-an-image')):
            with self.subTest(field=field):
                payload = {'name': 'Мурка', 'color': '#FFFFFF', 'birth_year': 2020}
                payload[field] = value
                response = self.client.post('/api/cats/', payload, format='json')
                self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)
                self.assertIn(field, response.data)
        self.assertFalse(Cat.objects.exists())

    def test_list_has_frontend_pagination_contract(self):
        Cat.objects.bulk_create([
            Cat(name=f'Cat {number}', color='white', birth_year=2020, owner=self.user)
            for number in range(11)
        ])
        first_page = self.client.get('/api/cats/')
        self.assertEqual(first_page.status_code, HTTPStatus.OK)
        self.assertEqual(first_page.data['count'], 11)
        self.assertEqual(len(first_page.data['results']), 10)
        second_page = self.client.get(first_page.data['next'])
        self.assertEqual(second_page.status_code, HTTPStatus.OK)
        self.assertEqual(len(second_page.data['results']), 1)
        self.assertIsNone(second_page.data['next'])
