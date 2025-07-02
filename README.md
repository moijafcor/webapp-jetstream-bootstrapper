# Laravel Jetstream Automated Setup

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
