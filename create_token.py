#!/usr/bin/env python
"""
Helper script to create API token for a user.
Usage: python create_token.py <username>
"""
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'surveillance_backend.settings')
django.setup()

from django.contrib.auth.models import User
from rest_framework.authtoken.models import Token


def create_token(username):
    """Create or get API token for user."""
    try:
        user = User.objects.get(username=username)
    except User.DoesNotExist:
        print(f"Error: User '{username}' not found.")
        print("Available users:")
        for u in User.objects.all():
            print(f"  - {u.username}")
        sys.exit(1)
    
    token, created = Token.objects.get_or_create(user=user)
    
    if created:
        print(f"✓ Token created for user '{username}'")
    else:
        print(f"✓ Token already exists for user '{username}'")
    
    print(f"\nAPI Token: {token.key}")
    print(f"\nAdd this to your cctv/.env file:")
    print(f"DJANGO_API_TOKEN={token.key}")
    
    return token.key


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python create_token.py <username>")
        sys.exit(1)
    
    username = sys.argv[1]
    create_token(username)

