# LinkedIn Hero - Phase 1 Technical Plan

## Overview
LinkedIn Hero is a Flask-based SaaS application that generates LinkedIn posts from news articles using AI. Phase 1 focuses on core infrastructure and authentication.

---

## 1. Technology Stack
- **Backend:** Flask (application factory pattern)
- **ORM:** SQLAlchemy
- **Database:** PostgreSQL (Azure free tier compatible)
- **Migrations:** Flask-Migrate
- **Authentication:** Flask-Login (session management), Google OAuth (Flask-Dance/Authlib)
- **Forms:** WTForms (with CSRF protection)
- **Frontend:** Jinja2 templates, custom CSS/JS, Google Fonts (Inter)
- **Session:** Secure cookies, no localStorage/sessionStorage
- **Config:** Environment variables via `.env`

---

## 2. Project Structure
```
linkedin_hero/
├── app/
│   ├── __init__.py
│   ├── models.py
│   ├── auth/
│   │   ├── __init__.py
│   │   ├── routes.py
│   │   └── forms.py
│   ├── main/
│   │   ├── __init__.py
│   │   └── routes.py
│   └── static/
│       ├── css/
│       │   └── styles.css
│       ├── js/
│       │   └── main.js
│       └── images/
├── templates/
│   ├── base.html
│   ├── index.html
│   ├── auth/
│   │   ├── login.html
│   │   ├── register.html
│   │   └── profile.html
│   └── main/
│       └── dashboard.html
├── migrations/
├── requirements.txt
├── config.py
├── run.py
├── .env
├── .gitignore
└── scope.md
```

---

## 3. Database Schema
- **User**: id, email, username, password_hash, provider, provider_id, is_active, subscription_tier, posts_used_this_month, created_at, last_login
- **Post**: id, user_id, original_url, article_title, generated_content, ai_model_used, created_at, is_favorite
- **Waitlist**: id, email, created_at, is_notified
- **Usage**: id, user_id, posts_count, month_year, subscription_tier

---

## 4. Authentication
- **Flask-Login**: UserMixin, login manager, session protection, remember_me, logout
- **Google OAuth**: Flask-Dance/Authlib, scopes (openid, email, profile), auto user creation, email linking
- **Security**: Werkzeug password hashing, CSRF, secure sessions, secrets in .env

---

## 5. Frontend Design
- **Colors**: #FFFFFF, #2563EB, #3B82F6, #1F2937, #6B7280, #10B981, #EF4444
- **Typography**: Inter (headings), system fonts (body)
- **Layout**: Fixed nav, hero section, responsive grid, footer
- **Animations**: Button hover, hero icons, page transitions, form focus, loading spinner

---

## 6. Routing Structure
- **Main**: `/`, `/dashboard`, `/pricing`, `/waitlist`
- **Auth**: `/login`, `/register`, `/logout`, `/auth/google`, `/auth/google/callback`, `/profile`

---

## 7. Configuration
- **config.py**: Loads from .env (SECRET_KEY, DATABASE_URL, GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET)
- **.env**: All secrets and DB URL

---

## 8. Forms
- **Registration**: email, username, password, confirm_password
- **Login**: email, password, remember_me

---

## 9. Error Handling
- Custom 404/500 pages, form error display, flash messages, DB/OAuth error handling

---

## 10. Implementation Steps
1. **Project scaffolding**: Create structure, config, requirements, .env, .gitignore
2. **App factory**: `app/__init__.py`, extension init, blueprint registration
3. **Models**: `app/models.py` with all schema
4. **Migrations**: Flask-Migrate setup
5. **Auth**: User model, Flask-Login, Google OAuth, forms, routes
6. **Main**: Homepage, dashboard, pricing, waitlist
7. **Templates**: `base.html`, all pages, error pages
8. **Static**: CSS, JS, images, animations
9. **Testing**: All routes, auth flows, error handling
10. **Docs**: Update `scope.md` as needed

---

## 11. Constraints
- All DB via SQLAlchemy ORM
- All forms via WTForms
- Mobile responsive
- No localStorage/sessionStorage
- Professional code, imports, docs
- Git with .gitignore

---

## 12. Open Questions
- None for Phase 1. Will clarify with product owner if needed for future phases. 