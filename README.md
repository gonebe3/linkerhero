# LinkedIn Hero

A Flask-based SaaS application that generates LinkedIn posts from news articles using AI.

## 🚀 Features

- **AI-Powered Content Generation**: Transform news articles into engaging LinkedIn posts
- **User Authentication**: Secure login with Google OAuth integration
- **Subscription Management**: Tier-based usage tracking
- **Modern UI**: Clean, responsive design with Inter font
- **Post Management**: Save, favorite, and track your generated posts

## 🛠️ Tech Stack

- **Backend**: Flask (application factory pattern)
- **Database**: PostgreSQL with SQLAlchemy ORM
- **Authentication**: Flask-Login with Google OAuth
- **Frontend**: Jinja2 templates, custom CSS/JS
- **Deployment**: cPanel compatible

## 📁 Project Structure

```
linkedin_hero/
├── app/
│   ├── auth/          # Authentication routes and forms
│   ├── main/          # Main application routes
│   ├── static/        # CSS, JS, and images
│   └── models.py      # Database models
├── templates/         # Jinja2 templates
├── migrations/        # Database migrations
├── config.py          # Application configuration
├── requirements.txt   # Python dependencies
└── run.py            # Application entry point
```

## 🚀 Quick Start

1. **Clone the repository**
   ```bash
   git clone https://github.com/yourusername/linkedin-hero.git
   cd linkedin-hero
   ```

2. **Install dependencies**
   ```bash
   pip install -r linkedin_hero/requirements.txt
   ```

3. **Set up environment variables**
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

4. **Run the application**
   ```bash
   cd linkedin_hero
   python run.py
   ```

## 🌐 Live Demo

Visit [linkerhero.com](https://linkerhero.com) to see the application in action!

## 📝 License

This project is licensed under the MIT License.

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

---

**LinkedIn Hero** - Transform news into engaging LinkedIn content with AI. 