"""Shared helpers for tests across apps."""

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group

TEST_PASSWORD = "test-pass-123!"


def make_user(username, *roles, **extra):
    user = get_user_model().objects.create_user(username=username, password=TEST_PASSWORD, **extra)
    for role in roles:
        user.groups.add(Group.objects.get_or_create(name=role)[0])
    return user
