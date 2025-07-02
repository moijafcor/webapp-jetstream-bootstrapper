# Webapp Automated Setup Powered by Laravel|Jetstream|Livewire 

This repository contains a Python script designed to fully automate the setup of a new Laravel project with **Laravel Jetstream (Livewire stack, with Teams and Dark Mode support)** and configure its MySQL database. This script streamlines the initial setup, handling common dependencies and configurations, including secure password generation and `.env` file population.

## Table of Contents

1.  [Features](#features)
2.  [System Requirements](#system-requirements)
3.  [Important Pre-requisites](#important-pre-requisites)
    * [MySQL Root Access (Sudoers Configuration)](#mysql-root-access-sudoers-configuration)
4.  [How to Use the Script](#how-to-use-the-script)
    * [Arguments](#arguments)
    * [Example Usage](#example-usage)
5.  [Generated Database Password](#generated-database-password)
6.  [Post-Installation Steps](#post-installation-steps)
7.  [Troubleshooting](#troubleshooting)

## Features

* **Fully Automated Setup:** Installs Laravel, Jetstream (Livewire stack with Teams and Dark Mode).
* **MySQL Database Provisioning:** Creates the database and a dedicated user with necessary privileges.
* **Secure Password Generation:** Automatically generates a strong, policy-compliant password for the database user.
* **`.env` File Configuration:** Populates the `.env` file with all essential application and database settings.
* **Concurrent Execution:** Utilizes Python threading to run MySQL setup and codebase deployment concurrently, optimizing for different phase durations.
* **Idempotent Database Operations:** MySQL commands use `IF NOT EXISTS` to prevent errors if resources already exist.
* **Progress Indicators & Error Handling:** Provides clear output for each step and robust error handling.

## System Requirements

Before running the script, ensure you have the following installed on your system:

* **Python 3.x:** (Tested with Python 3.8+)
* **PHP:** (Latest stable version, compatible with Laravel 10/11)
* **Composer:** PHP dependency manager.
* **Node.js & npm (or Yarn):** For frontend dependencies and asset compilation.
* **MySQL Server:** (Version 8.0+ recommended)
* **Git:** For version control (though the script creates the project, Git is essential for managing the repo).
* **`sudo` access:** Your system user must have `sudo` privileges.

## Important Pre-requisites

### MySQL Root Access (Sudoers Configuration)

This script uses `sudo mysql` to perform database creation and user management. For a smooth, non-interactive execution, your system user must be able to execute `sudo mysql` **without being prompted for a password**.

**To verify this:**

Open your terminal and run:

```bash
sudo mysql -e "SELECT USER();"
```

## How to Use the Script

Clone this repository:

```bash
git clone git@github.com:moijafcor/webapp-jetstream-bootstrap.git
cd webapp-jetstream-bootstrap
```

Or, if you're just using the script, download setup_laravel_jetstream_sudo.py directly.

Make the script executable (Linux/macOS):

```bash
chmod +x setup_laravel_jetstream_sudo.py
```

Run the script from your terminal:

```bash
python setup_laravel_jetstream_sudo.py [project_name] --dbname [database_name] --dbuser [database_user]
```

### Arguments

[project_name] (positional, required): The name of your new Laravel project. This will also be the name of the directory created for your project.

--dbname (required): The name for the new MySQL database.

--dbuser (required): The username for the new MySQL database user.

Example Usage

```bash
python setup_laravel_jetstream_sudo.py my-awesome-app --dbname my_app_db --dbuser app_dev_user
```

The script will:

* Ask for confirmation before proceeding.
* Generate a secure password for app_dev_user.
* Start setting up the MySQL database concurrently with the Laravel project creation.
* Install Laravel Jetstream (Livewire, Teams, Dark Mode).
* Install Node.js dependencies and build frontend assets.
* Populate the .env file with all necessary configurations, including the generated database password.
* Run database migrations.
* Generate the application key and clear caches.
* Generated Database Password
* The script will print the generated database password to your console. Please make a note of this password. It will also be automatically written into your new Laravel project's .env file.

Example output during execution:

```bash
Generated database password for 'app_dev_user': Y0urS3cur3P@ssw0rd!
Please make a note of this password. It will also be written to your .env file.
```

### Post-Installation Steps

After the script completes successfully:

Navigate into your new Laravel project directory:

```bash
cd [your_project_name]
```

Start the Laravel development server:

```bash
php artisan serve
```

In a separate terminal, start the frontend development server (for hot-reloading assets during development):

```bash
npm run dev
```

Access your application in your web browser:

Open http://127.0.0.1:8000 (or the URL displayed by php artisan serve).

## Troubleshooting

If you encounter any issues, especially "Access denied" errors or the script hanging during MySQL setup, consider these common solutions:

MySQL Root Access (Sudoers Configuration):

Most likely cause: The script relies on your system user being able to execute sudo mysql without a password prompt.

Verify: Run sudo mysql -e "SELECT USER();" in a new terminal. If it asks for a password, you need to configure your sudoers file as described in Important Pre-requisites.

Verify .env File:

Open your project's .env file (e.g., my-awesome-app/.env).

Ensure that DB_DATABASE, DB_USERNAME, and DB_PASSWORD exactly match the database name, user, and the generated password.

Manual MySQL Connection Test:

Open a new terminal and try to connect to your MySQL database manually using the generated credentials:

```bash
mysql -u [your_db_user] -p
```

(Paste the generated password when prompted)

If this fails, the problem is specifically with the database user's permissions or password within MySQL, independent of the Laravel application.

Firewall Issues:

Ensure no firewall software (e.g., ufw, firewalld, SELinux) on your system is blocking TCP port 3306 (the default MySQL port).

Enjoy building your Laravel application!
