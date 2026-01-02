# Production Deployment Guide for SmartAcca

This guide provides step-by-step instructions for deploying the SmartAcca Django application to a production environment on a Linux server.

We will use the following stack:
- **Nginx:** As a reverse proxy and to serve static files.
- **Gunicorn:** As the WSGI application server to run the Django app.
- **Unix Socket:** For efficient communication between Nginx and Gunicorn.
- **Systemd:** To manage the Gunicorn process and schedule recurring tasks.
- **Virtual Environment:** To isolate project dependencies.

---

### Prerequisites

- A Linux server (e.g., Ubuntu 22.04 or later).
- Superuser (sudo) privileges.
- Your domain name (`13.247.42.178`) pointing to your server's IP address.
- Python 3, pip, and venv installed (`sudo apt update && sudo apt install python3-full python3-pip python3-venv nginx`).

---

### Step 1: Server Setup & Application Installation

1.  **Clone the Repository**
    ```bash
    git clone <your_repository_url> /home/ubuntu/smartacca
    cd /home/ubuntu/smartacca
    ```

2.  **Create a Virtual Environment**
    ```bash
    python3 -m venv venv
    source venv/bin/activate
    ```

3.  **Install Dependencies**
    ```bash
    pip install -r requirements.txt
    pip install gunicorn
    ```

4.  **Configure Production Settings**
    - Open `smart_acca_project/settings.py` and make the following changes for production:
    - **`SECRET_KEY`**: Move the secret key to an environment variable. Do not leave the development key in production.
    - **`DEBUG`**: Set `DEBUG = False`.
    - **`ALLOWED_HOSTS`**: Add your domain and IP address: `ALLOWED_HOSTS = ['13.247.42.178', '127.0.0.1']`.
    - **`STATIC_ROOT`**: Define the directory for collected static files: `STATIC_ROOT = BASE_DIR / 'staticfiles'`.

5.  **Run Initial Setup Commands**
    ```bash
    # Collect all static files (CSS, JS, images) into STATIC_ROOT
    python manage.py collectstatic --noinput

    # Apply database migrations
    python manage.py migrate
    ```
    *Note: Ensure your database settings in `settings.py` are configured for your production database.*

---

### Step 2: Configure Gunicorn with Systemd

We will create a Systemd socket and service file to manage the Gunicorn process.

1.  **Create the Systemd Socket File**

    This file creates the socket for communication. Systemd will start the service automatically on the first connection to this socket.

    Create and edit `/etc/systemd/system/gunicorn.socket`:
    ```ini
    [Unit]
    Description=gunicorn socket

    [Socket]
    ListenStream=/run/gunicorn.sock

    [Install]
    WantedBy=sockets.target
    ```

2.  **Create the Systemd Service File**

    This file tells Systemd how to run Gunicorn. It will be started by the socket file.

    Create and edit `/etc/systemd/system/gunicorn.service`:
    ```ini
    [Unit]
    Description=gunicorn daemon
    Requires=gunicorn.socket
    After=network.target

    [Service]
    User=ubuntu
    Group=www-data
    WorkingDirectory=/home/ubuntu/smartacca
    ExecStart=/home/ubuntu/smartacca/venv/bin/gunicorn \
              --access-logfile - \
              --workers 3 \
              --bind unix:/run/gunicorn.sock \
              smart_acca_project.wsgi:application

    [Install]
    WantedBy=multi-user.target
    ```
    *Note: The `User` should be the user running the application. The `Group` is often set to `www-data` so Nginx can communicate with Gunicorn.*

3.  **Start and Enable the Gunicorn Service**
    ```bash
    sudo systemctl start gunicorn.socket
    sudo systemctl enable gunicorn.socket
    ```
    Check the status to ensure it's running: `sudo systemctl status gunicorn.socket`.

---

### Step 3: Configure Nginx as a Reverse Proxy

1.  **Create the Nginx Server Block File**

    Create and edit a new Nginx configuration file:
    ```bash
    sudo nano /etc/nginx/sites-available/smartacca
    ```

    Paste the following configuration, adjusting `server_name`:
    ```nginx
    server {
        listen 80;
        server_name 13.247.42.178;

        location = /favicon.ico { access_log off; log_not_found off; }

        location /static/ {
            root /home/ubuntu/smartacca/staticfiles;
        }

        location / {
            include proxy_params;
            proxy_pass http://unix:/run/gunicorn.sock;
        }
    }
    ```

2.  **Enable the Site**

    Link the configuration to the `sites-enabled` directory.
    ```bash
    sudo ln -s /etc/nginx/sites-available/smartacca /etc/nginx/sites-enabled
    sudo rm /etc/nginx/sites-enabled/default
    ```

3.  **Test and Restart Nginx**
    ```bash
    sudo nginx -t  # Test for syntax errors
    sudo systemctl restart nginx
    ```
    You may need to adjust firewall settings to allow HTTP traffic: `sudo ufw allow 'Nginx Full'`.

---

### Step 4: Schedule Tasks with Systemd Timers

We will create a service and a timer for each scheduled management command.

#### Job 1: Fetch Matches Daily at 7 AM

1.  **Create the Service File** (`fetch_matches.service`)
    Create `/etc/systemd/system/fetch_matches.service`:
    ```ini
    [Unit]
    Description=Fetch daily matches for SmartAcca

    [Service]
    Type=oneshot
    User=ubuntu
    WorkingDirectory=/home/ubuntu/smartacca
    ExecStart=/home/ubuntu/smartacca/venv/bin/python /home/ubuntu/smartacca/manage.py generate_daily_acca
    ```

2.  **Create the Timer File** (`fetch_matches.timer`)
    Create `/etc/systemd/system/fetch_matches.timer`:
    ```ini
    [Unit]
    Description=Run fetch_matches service daily at 7 AM

    [Timer]
    OnCalendar=*-*-* 07:00:00
    Persistent=true

    [Install]
    WantedBy=timers.target
    ```

#### Job 2: Fetch Results Hourly

1.  **Create the Service File** (`fetch_results.service`)
    Create `/etc/systemd/system/fetch_results.service`:
    ```ini
    [Unit]
    Description=Fetch match results for SmartAcca

    [Service]
    Type=oneshot
    User=ubuntu
    WorkingDirectory=/home/ubuntu/smartacca
    ExecStart=/home/ubuntu/smartacca/venv/bin/python /home/ubuntu/smartacca/manage.py fetch_results
    ```
    **Important**: The `fetch_results.py` script should contain its own logic to determine if it needs to run. It should check if there are any un-resulted matches for the day and exit gracefully if not.

2.  **Create the Timer File** (`fetch_results.timer`)
    Create `/etc/systemd/system/fetch_results.timer`:
    ```ini
    [Unit]
    Description=Run fetch_results service hourly

    [Timer]
    OnCalendar=hourly
    Persistent=true

    [Install]
    WantedBy=timers.target
    ```

#### Activating the Timers

1.  **Reload the Systemd Daemon**
    ```bash
    sudo systemctl daemon-reload
    ```

2.  **Start and Enable the Timers**
    ```bash
    sudo systemctl start fetch_matches.timer
    sudo systemctl enable fetch_matches.timer

    sudo systemctl start fetch_results.timer
    sudo systemctl enable fetch_results.timer
    ```

3.  **Verify the Timers**
    You can check that the timers are active and see when they are scheduled to run next:
    ```bash
    sudo systemctl list-timers --all
    ```

---

### Deployment Complete

Your SmartAcca application should now be running and accessible at `http://13.247.42.178`. The scheduled tasks will run automatically.

**Monitoring and Logs:**
- To check the Gunicorn application logs: `sudo journalctl -u gunicorn.service`
- To check logs for a scheduled task: `sudo journalctl -u fetch_results.service`
