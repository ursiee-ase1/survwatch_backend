# Django Surveillance Backend

Django backend for CCTV analytics platform.

## Setup

1. Create virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Configure environment:
   ```bash
   cp .env.example .env
   # Edit .env with your settings
   ```

4. Run migrations:
   ```bash
   python manage.py migrate
   ```

5. Create superuser:
   ```bash
   python manage.py createsuperuser
   ```

6. Create API token:
   ```bash
   python create_token.py <username>
   ```

7. Start server:
   ```bash
   python manage.py runserver
   ```

## Access Points

- Admin: http://localhost:8000/admin
- Dashboard: http://localhost:8000/dashboard/
- API: http://localhost:8000/api/
