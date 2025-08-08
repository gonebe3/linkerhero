# LinkedIn Hero - cPanel Deployment Guide

## Prerequisites
- cPanel access on Spaceship.com
- MySQL database created in cPanel
- Domain: linkerhero.com

## Step 1: Create MySQL Database in cPanel
1. Log into cPanel
2. Go to "MySQL® Databases"
3. Create a new database (e.g., `ctkfigide_linkedin_hero`)
4. Create a database user with full privileges
5. Note down: database name, username, password, and host

## Step 2: Set Up Python App in cPanel
1. Go to "Setup Python App"
2. Create new application:
   - **Application root**: `/home/ctkfigide/linkerhero.com`
   - **Application URL**: `linkerhero.com`
   - **Application startup file**: `app.py`
   - **Application entry point**: `application`
   - **Python version**: 3.12 (or latest available)

## Step 3: Configure Environment Variables
In cPanel Python App settings, add these environment variables:
```
FLASK_ENV=production
SECRET_KEY=your-very-long-random-secret-key-here
DATABASE_URL=mysql+pymysql://username:password@localhost/database_name
GOOGLE_CLIENT_ID=your-google-client-id
GOOGLE_CLIENT_SECRET=your-google-client-secret
```

## Step 4: Upload Project Files
1. Use cPanel File Manager or SFTP
2. Upload all project files to `/home/ctkfigide/linkerhero.com/`
3. Ensure `app.py` is in the root directory

## Step 5: Install Dependencies
1. Open cPanel Terminal or SSH
2. Activate virtual environment:
   ```bash
   source /home/ctkfigide/virtualenv/linkerhero.com/3.12/bin/activate
   cd /home/ctkfigide/linkerhero.com
   ```
3. Install requirements:
   ```bash
   pip install -r requirements.txt
   ```

## Step 6: Initialize Database
1. In the same terminal session:
   ```bash
   export FLASK_APP=app.py
   flask db init
   flask db migrate -m "Initial migration"
   flask db upgrade
   ```

## Step 7: Restart Application
1. Go back to "Setup Python App"
2. Click "Restart" button
3. Wait for the application to start

## Step 8: Test
1. Visit https://linkerhero.com
2. You should see the LinkedIn Hero homepage
3. Test registration and login functionality

## Troubleshooting
- Check error logs in cPanel
- Ensure all environment variables are set correctly
- Verify database connection string format
- Make sure `app.py` contains the correct WSGI entry point

## File Structure on Server
```
/home/ctkfigide/linkerhero.com/
├── app.py (WSGI entry point)
├── requirements.txt
├── config.py
├── app/
│   ├── __init__.py
│   ├── models.py
│   ├── auth/
│   └── main/
├── templates/
├── static/
└── migrations/
``` 