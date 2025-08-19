import subprocess
import sys
import os
import argparse
import re
import random
import string
import threading
import time
import shlex 

def generate_secure_password(length=16):
    """Generates a secure password meeting strict requirements, shell-safe and .env-safe."""
    if length < 12:
        length = 12 

    digits = string.digits
    uppercase = string.ascii_uppercase
    lowercase = string.ascii_lowercase
    # Use only shell-safe and .env-safe special characters
    # Removed: ! $ ` " ' \ | ; < > ? * ( ) [ ] { } & 
    special_chars = '@#%^-_=+:,.~'

    password = [
        random.choice(digits),
        random.choice(uppercase),
        random.choice(lowercase),
        random.choice(special_chars)
    ]

    all_chars = digits + uppercase + lowercase + special_chars
    password.extend(random.choice(all_chars) for _ in range(length - len(password)))

    random.shuffle(password) 
    return "".join(password)

def run_command(command, cwd=None, success_message="Completed.", error_message="Failed.", ignore_error_codes=None):
    """
    Executes a shell command, captures all output, prints it, and handles success/error.
    """
    if ignore_error_codes is None:
        ignore_error_codes = []

    print(f"\n--- Running: {command.split(' ')[0]} in thread '{threading.current_thread().name}' ---")
    try:
        process = subprocess.Popen(
            command,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=cwd
        )
        
        stdout_full, stderr_full = process.communicate()
        
        if stdout_full:
            print(f"STDOUT ({threading.current_thread().name}):\n{stdout_full}", end='')
        if stderr_full:
            print(f"STDERR ({threading.current_thread().name}):\n{stderr_full}", end='')

        if process.returncode != 0:
            if ("database exists" in stderr_full.lower() or 
                "user exists" in stderr_full.lower() or 
                "can't create database" in stderr_full.lower() or 
                "duplicate entry" in stderr_full.lower()):
                print(f"INFO ({threading.current_thread().name}): MySQL command skipped (resource already existed, or specific info message).")
            elif process.returncode in ignore_error_codes:
                print(f"INFO ({threading.current_thread().name}): Command finished with ignored error code {process.returncode}: {success_message}")
            else:
                print(f"ERROR ({threading.current_thread().name}): {error_message} (Exit code: {process.returncode})")
                raise RuntimeError(f"Command failed: {command}") 
        else:
            print(f"SUCCESS ({threading.current_thread().name}): {success_message}")
        
        return True
    except FileNotFoundError:
        raise RuntimeError(f"Command not found: {command.split(' ')[0]}")
    except Exception as e:
        raise RuntimeError(f"An unexpected error occurred executing '{command.split(' ')[0]}': {e}")

# --- Thread Target Functions ---

def setup_mysql_thread_target(db_config, db_ready_event, thread_status):
    """Function to be run in a separate thread for MySQL setup."""
    db_name = db_config['name']
    db_user = db_config['user']
    db_pass = db_config['pass']
    thread_name = threading.current_thread().name
    
    print(f"\n--- Phase 1 ({thread_name}): Setting up MySQL Database ---")
    try:
        mysql_commands = [
            f"CREATE DATABASE IF NOT EXISTS {db_name} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;",
            f"CREATE USER IF NOT EXISTS '{db_user}'@'localhost' IDENTIFIED BY '{db_pass}';",
            f"ALTER USER '{db_user}'@'localhost' IDENTIFIED WITH mysql_native_password BY '{db_pass}';", 
            f"GRANT ALL PRIVILEGES ON {db_name}.* TO '{db_user}'@'localhost';",
            "FLUSH PRIVILEGES;"
        ]

        for cmd_sql in mysql_commands:
            print(f"Executing MySQL command: {cmd_sql.split(';')[0]}...") 
            # Use shlex.quote to properly escape the SQL command for shell execution
            escaped_sql = shlex.quote(cmd_sql)
            run_command(f"sudo mysql -e {escaped_sql}", 
                        success_message="MySQL command executed.",
                        error_message="MySQL command failed.")
        
        db_ready_event.set() 
        thread_status[thread_name] = True
        print(f"\n--- Phase 1 ({thread_name}): MySQL Database setup completed and signaled. ---")

    except Exception as e:
        print(f"ERROR ({thread_name}): Failed to set up MySQL database: {e}")
        thread_status[thread_name] = False
    finally:
        if not db_ready_event.is_set():
             db_ready_event.set()


def deploy_codebase_thread_target(project_config, db_ready_event, thread_status):
    """Function to be run in a separate thread for codebase deployment."""
    project_name = project_config['name']
    project_path = project_config['path']
    app_name_formatted = project_config['app_name_formatted']
    db_config = project_config['db_config'] 
    thread_name = threading.current_thread().name

    try:
        print(f"\n--- Phase 2 ({thread_name}): Installing Laravel Project ---")
        run_command(
            f"composer create-project laravel/laravel {project_name}",
            success_message=f"Laravel project '{project_name}' created successfully."
        )

        # IMPORTANT: Change directory for the *script's execution context* for subsequent commands
        os.chdir(project_path)
        print(f"Changed current directory to: {os.getcwd()} in thread '{thread_name}'")

        # --- Generate Application Key EARLY ---
        # This will populate the APP_KEY in the newly created .env file
        run_command(
            "php artisan key:generate",
            success_message="Application key generated.",
            cwd=project_path # Ensure command runs in project directory
        )

        # --- Update .env file with database credentials and custom vars ---
        # This must happen AFTER composer create-project (creates .env) and key:generate (sets APP_KEY)
        env_path = os.path.join(project_path, '.env')
        env_vars = {
            "APP_NAME": f"'{app_name_formatted}'",
            "APP_ENV": "local",
            # "APP_KEY": "" - Leave this empty here, it will be generated by artisan key:generate
            "APP_DEBUG": "true",
            "APP_URL": "http://localhost",
            "LOG_CHANNEL": "stack",
            "LOG_LEVEL": "debug",
            "DB_CONNECTION": "mysql",
            "DB_HOST": "127.0.0.1",
            "DB_PORT": "3306",
            "DB_DATABASE": db_config['name'],
            "DB_USERNAME": db_config['user'],
            "DB_PASSWORD": db_config['pass'],
            "BROADCAST_DRIVER": "log",
            "CACHE_DRIVER": "file",
            "FILESYSTEM_DISK": "local",
            "QUEUE_CONNECTION": "sync",
            "SESSION_DRIVER": "file",
            "SESSION_LIFETIME": "120",
            "MEMCACHED_HOST": "127.0.0.1",
            "REDIS_HOST": "127.0.0.1",
            "REDIS_PORT": "6379",
            "REDIS_PASSWORD": "null",
            "MAIL_MAILER": "log",
            "MAIL_HOST": "mailpit",
            "MAIL_PORT": "1025",
            "MAIL_USERNAME": "null",
            "MAIL_PASSWORD": "null",
            "MAIL_ENCRYPTION": "null",
            "MAIL_FROM_ADDRESS": "hello@example.com",
            "MAIL_FROM_NAME": f"'{app_name_formatted}'",
            "AWS_ACCESS_KEY_ID": "",
            "AWS_SECRET_ACCESS_KEY": "",
            "AWS_DEFAULT_REGION": "us-east-1",
            "AWS_BUCKET": "",
            "PUSHER_APP_ID": "",
            "PUSHER_APP_KEY": "",
            "PUSHER_APP_SECRET": "",
            "PUSHER_HOST": "null",
            "PUSHER_PORT": "443",
            "PUSHER_SCHEME": "https",
            "VITE_APP_NAME": f"'{app_name_formatted}'",
            "VITE_PUSHER_APP_KEY": f"'${{PUSHER_APP_KEY}}'",
            "VITE_PUSHER_HOST": f"'${{PUSHER_HOST}}'",
            "VITE_PUSHER_PORT": f"'${{PUSHER_PORT}}'",
            "VITE_PUSHER_SCHEME": f"'${{PUSHER_SCHEME}}'",
            "VITE_PUSHER_APP_CLUSTER": "mt1"
        }

        with open(env_path, 'r') as f:
            lines = f.readlines()

        new_env_lines = []
        updated_keys = set()
        for line in lines:
            matched = False
            for key in env_vars:
                # Ensure we only update if the key exists in our managed list
                if line.strip().startswith(f"{key}="):
                    new_env_lines.append(f"{key}={env_vars[key]}\n")
                    updated_keys.add(key)
                    matched = True
                    break
            # Special handling for APP_KEY: if it was generated, keep it, don't overwrite with ""
            if line.strip().startswith("APP_KEY=") and "APP_KEY" not in updated_keys:
                new_env_lines.append(line)
                updated_keys.add("APP_KEY") # Mark as handled to avoid re-adding
            elif not matched:
                new_env_lines.append(line)
        
        # Add any missing keys that weren't in the original .env or our managed list
        for key, value in env_vars.items():
            if key not in updated_keys:
                if new_env_lines and not new_env_lines[-1].endswith('\n'):
                    new_env_lines.append('\n') 
                new_env_lines.append(f"{key}={value}\n")
                
        with open(env_path, 'w') as f:
            f.writelines(new_env_lines)
        print(f"SUCCESS ({thread_name}): .env file updated with all essential configurations.")

        run_command(
            "composer require laravel/jetstream",
            success_message="Laravel Jetstream package required.",
            cwd=project_path
        )

        run_command(
            "php artisan jetstream:install livewire --teams --dark",
            success_message="Laravel Jetstream scaffolding installed.",
            cwd=project_path
        )

        print(f"\n--- Phase 3 ({thread_name}): Frontend Setup ---")
        run_command(
            "npm install",
            success_message="Node.js dependencies installed.",
            cwd=project_path
        )

        run_command(
            "npm run build",
            success_message="Frontend assets built successfully.",
            cwd=project_path
        )

        print(f"\n--- Phase 4 ({thread_name}): Laravel Database Setup ---")
        # --- Wait for DB to be ready BEFORE migration ---
        print(f"({thread_name}): Waiting for database setup to complete in MySQL_Setup_Thread...")
        db_ready_event.wait() 
        
        if not thread_status.get('MySQL_Setup_Thread', False): 
            raise RuntimeError("Database setup failed in MySQL_Setup_Thread, cannot proceed with migration.")

        run_command(
            "php artisan migrate",
            success_message="Database migrations completed.",
            cwd=project_path
        )

        run_command(
            "php artisan optimize:clear",
            success_message="Laravel caches cleared.",
            cwd=project_path
        )
        
        thread_status[thread_name] = True
        print(f"\n--- Phase 4 ({thread_name}): Codebase deployment and final setup completed. ---")

    except Exception as e:
        print(f"ERROR ({thread_name}): Codebase deployment failed: {e}")
        thread_status[thread_name] = False


# --- Repair Functionality ---

def read_env_file(project_path):
    """
    Reads the .env file and extracts database configuration.
    Returns a dictionary with database settings or None if not found.
    """
    env_path = os.path.join(project_path, '.env')
    
    if not os.path.exists(env_path):
        raise FileNotFoundError(f".env file not found at {env_path}")
    
    env_config = {}
    
    try:
        with open(env_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    # Remove quotes if present
                    value = value.strip('\'"')
                    env_config[key] = value
        
        # Extract database configuration
        db_config = {
            'name': env_config.get('DB_DATABASE'),
            'user': env_config.get('DB_USERNAME'),
            'host': env_config.get('DB_HOST', '127.0.0.1'),
            'port': env_config.get('DB_PORT', '3306')
        }
        
        # Validate required fields
        if not db_config['name'] or not db_config['user']:
            raise ValueError("Missing DB_DATABASE or DB_USERNAME in .env file")
        
        return db_config, env_config
        
    except Exception as e:
        raise RuntimeError(f"Failed to read .env file: {e}")


def repair_mysql_user(db_config, new_password):
    """
    Resets the MySQL user password and ensures proper permissions.
    """
    db_name = db_config['name']
    db_user = db_config['user']
    
    print(f"\n--- Repairing MySQL User '{db_user}' ---")
    
    try:
        mysql_commands = [
            # Drop user if exists to ensure clean state
            f"DROP USER IF EXISTS '{db_user}'@'localhost';",
            # Recreate user with new password
            f"CREATE USER '{db_user}'@'localhost' IDENTIFIED BY '{new_password}';",
            f"ALTER USER '{db_user}'@'localhost' IDENTIFIED WITH mysql_native_password BY '{new_password}';",
            f"GRANT ALL PRIVILEGES ON {db_name}.* TO '{db_user}'@'localhost';",
            "FLUSH PRIVILEGES;"
        ]
        
        for cmd_sql in mysql_commands:
            print(f"Executing MySQL command: {cmd_sql.split(';')[0]}...")
            escaped_sql = shlex.quote(cmd_sql)
            run_command(f"sudo mysql -e {escaped_sql}",
                        success_message="MySQL command executed.",
                        error_message="MySQL command failed.")
        
        print(f"SUCCESS: MySQL user '{db_user}' repaired with new password.")
        return True
        
    except Exception as e:
        print(f"ERROR: Failed to repair MySQL user: {e}")
        return False


def update_env_password(project_path, new_password):
    """
    Updates the .env file with the new database password.
    """
    env_path = os.path.join(project_path, '.env')
    
    try:
        with open(env_path, 'r') as f:
            lines = f.readlines()
        
        new_lines = []
        password_updated = False
        
        for line in lines:
            if line.strip().startswith('DB_PASSWORD='):
                new_lines.append(f'DB_PASSWORD={new_password}\n')
                password_updated = True
            else:
                new_lines.append(line)
        
        # Add DB_PASSWORD if it wasn't found
        if not password_updated:
            new_lines.append(f'DB_PASSWORD={new_password}\n')
        
        with open(env_path, 'w') as f:
            f.writelines(new_lines)
        
        print(f"SUCCESS: .env file updated with new password.")
        return True
        
    except Exception as e:
        print(f"ERROR: Failed to update .env file: {e}")
        return False


def finalize_laravel_installation(project_path):
    """
    Completes the Laravel installation by running migrations and clearing caches.
    """
    print(f"\n--- Finalizing Laravel Installation ---")
    
    # Validate Laravel project structure
    artisan_path = os.path.join(project_path, 'artisan')
    if not os.path.exists(artisan_path):
        raise RuntimeError(f"Laravel artisan file not found at {artisan_path}")
    
    env_path = os.path.join(project_path, '.env')
    if not os.path.exists(env_path):
        raise RuntimeError(f"Laravel .env file not found at {env_path}")
    
    print(f"Laravel project structure validated at: {project_path}")
    
    try:
        # Test PHP availability
        run_command(
            "php --version",
            success_message="PHP availability confirmed.",
            cwd=project_path
        )
        
        # Clear configuration cache (safe to do before DB setup)
        run_command(
            "php artisan config:clear",
            success_message="Configuration cache cleared.",
            cwd=project_path,
            error_message="Config cache clear failed - continuing anyway"
        )
        
        # Test basic database connection
        try:
            # First try a simple artisan command to test Laravel setup
            run_command(
                "php artisan --version",
                success_message="Laravel artisan is working.",
                cwd=project_path
            )
            
            # Try to test database connection
            run_command(
                "php artisan migrate:status",
                success_message="Database connection verified.",
                cwd=project_path
            )
        except RuntimeError as e:
            print(f"WARNING: Database connection test failed ({e})")
            print("Attempting to proceed with migrations - this may create the required tables...")
        
        # Create cache table migration if using database cache driver
        try:
            run_command(
                "php artisan cache:table",
                success_message="Cache table migration created.",
                cwd=project_path
            )
        except RuntimeError as e:
            print(f"INFO: Cache table migration creation failed ({e})")
            print("This is normal if the migration already exists.")
        
        # Run migrations to create all required tables including cache table
        try:
            run_command(
                "php artisan migrate --force",
                success_message="Database migrations completed.",
                cwd=project_path
            )
        except RuntimeError as e:
            print(f"ERROR: Migration failed - {e}")
            print("Checking if this is due to missing migrations...")
            
            # Try to run migrations without --force first
            try:
                run_command(
                    "php artisan migrate",
                    success_message="Database migrations completed (without force).",
                    cwd=project_path
                )
            except RuntimeError:
                raise RuntimeError(f"Database migrations failed: {e}")
        
        # Generate fresh application key if needed
        run_command(
            "php artisan key:generate --force",
            success_message="Application key generated.",
            cwd=project_path
        )
        
        # Now safely clear application cache (after cache table exists)
        run_command(
            "php artisan cache:clear", 
            success_message="Application cache cleared.",
            cwd=project_path,
            error_message="Cache clear failed (cache table may not exist - this is not critical)",
            ignore_error_codes=[1]  # Ignore cache clear failures
        )
        
        # Clear and optimize
        run_command(
            "php artisan optimize:clear",
            success_message="Laravel optimization cleared.",
            cwd=project_path
        )
        
        print("SUCCESS: Laravel installation finalized.")
        return True
        
    except Exception as e:
        print(f"ERROR: Failed to finalize Laravel installation: {e}")
        return False


def repair_installation(project_name):
    """
    Main repair function that orchestrates the repair process.
    """
    current_dir = os.getcwd()
    project_path = os.path.join(current_dir, project_name)
    
    print(f"\n--- Starting Installation Repair for '{project_name}' ---")
    
    # Validate project directory exists
    if not os.path.exists(project_path):
        raise FileNotFoundError(f"Project directory not found: {project_path}")
    
    # Check if it's a Laravel project
    if not os.path.exists(os.path.join(project_path, 'artisan')):
        raise ValueError(f"Not a Laravel project: {project_path} (artisan file not found)")
    
    try:
        # Step 1: Read existing configuration
        print("Step 1: Reading existing .env configuration...")
        db_config, env_config = read_env_file(project_path)
        print(f"Found database: '{db_config['name']}' with user: '{db_config['user']}'")
        
        # Step 2: Generate new secure password
        print("Step 2: Generating new secure password...")
        new_password = generate_secure_password()
        print(f"Generated new password: \033[93m{new_password}\033[0m")
        
        # Step 3: Repair MySQL user
        print("Step 3: Repairing MySQL user...")
        if not repair_mysql_user(db_config, new_password):
            raise RuntimeError("MySQL user repair failed")
        
        # Step 4: Update .env file
        print("Step 4: Updating .env file...")
        if not update_env_password(project_path, new_password):
            raise RuntimeError(".env file update failed")
        
        # Step 5: Finalize Laravel installation
        print("Step 5: Finalizing Laravel installation...")
        if not finalize_laravel_installation(project_path):
            raise RuntimeError("Laravel finalization failed")
        
        print(f"\n" + "="*60)
        print(" 🔧 REPAIR COMPLETED SUCCESSFULLY! 🔧 ".center(60))
        print("="*60)
        print(f"\nProject '{project_name}' has been repaired!")
        print(f"Database: '{db_config['name']}' with user: '{db_config['user']}'")
        print(f"New password: \033[93m{new_password}\033[0m")
        print(f"\nYour Laravel application should now be working properly.")
        print(f"\nTo test, run:")
        print(f"cd {project_name}")
        print(f"php artisan serve")
        
        return True
        
    except Exception as e:
        print(f"\n" + "="*60)
        print(" ❌ REPAIR FAILED! ❌ ".center(60))
        print("="*60)
        print(f"Error: {e}")
        return False


# --- Main Script Logic ---
def main():
    parser = argparse.ArgumentParser(
        description="Automates Laravel Jetstream (Livewire, Teams, Dark Mode) installation with MySQL database setup.",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("project_name", help="The name of your Laravel project (e.g., my-app). This will be the directory name.")
    parser.add_argument("--dbname", help="MySQL database name for the project. Required for new installations.")
    parser.add_argument("--dbuser", help="MySQL database username for the project. Required for new installations.")
    parser.add_argument("--repair", action="store_true", 
                        help="Repair a broken installation by reading existing .env, generating new password, and completing setup.")

    args = parser.parse_args()

    project_name = args.project_name

    # Handle repair mode
    if args.repair:
        print("\n" + "="*60)
        print(" Laravel Jetstream Installation Repair ".center(60))
        print("="*60)
        print(f"\nRepairing Laravel project '{project_name}'...")
        
        try:
            success = repair_installation(project_name)
            sys.exit(0 if success else 1)
        except Exception as e:
            print(f"FATAL ERROR: {e}")
            sys.exit(1)
    
    # Validate required arguments for new installations
    if not args.dbname or not args.dbuser:
        print("ERROR: --dbname and --dbuser are required for new installations.")
        print("Use --repair flag to repair an existing installation.")
        parser.print_help()
        sys.exit(1)

    db_name = args.dbname
    db_user = args.dbuser
    db_pass = generate_secure_password()

    current_dir = os.getcwd()
    project_path = os.path.join(current_dir, project_name)

    app_name_formatted = project_name.replace('-', ' ').title()

    db_config = {
        'name': db_name,
        'user': db_user,
        'pass': db_pass
    }
    project_config = {
        'name': project_name,
        'path': project_path,
        'app_name_formatted': app_name_formatted,
        'db_config': db_config 
    }

    print("\n" + "="*60)
    print(" Laravel Jetstream Automated Installer (Threaded) ".center(60))
    print("="*60)
    print(f"\nThis script will set up a new Laravel project '{project_name}'")
    print(f"in the directory: '{project_path}'")
    print(f"It will configure a MySQL database '{db_name}' with user '{db_user}' using a generated secure password.")
    print("\n\033[91m!!! IMPORTANT MySQL ROOT ACCESS REQUIREMENT !!!\033[0m")
    print("-------------------------------------------------")
    print("This script uses 'sudo mysql' to perform database operations. For this to work")
    print("without interruption, your system user (the one running this script) must be")
    print("able to execute 'sudo mysql' **without being prompted for a password**.")
    print("\nTo test this, open a new terminal and run:")
    print("  \033[96msudo mysql -e \"SELECT USER();\"\033[0m")
    print("It should immediately show 'root@localhost' or similar without a password prompt.")
    print("If it prompts you for a password, you need to configure your 'sudoers' file.")
    print("Consult your Linux distribution's documentation on how to edit 'sudoers' safely (e.g., `sudo visudo`).")
    print("A common entry looks like: `your_username ALL=(ALL) NOPASSWD: /usr/bin/mysql`")
    print("-------------------------------------------------\n")
    print("WARNING: This script will create a new directory and modify system databases.")
    print("         Ensure you have necessary permissions and have backed up critical data.")

    confirmation = input("Do you wish to proceed? (yes/no): ").lower()
    if confirmation != 'yes':
        print("Installation cancelled.")
        sys.exit(0)
    
    print(f"\nGenerated database password for '{db_user}': \033[93m{db_pass}\033[0m")
    print("Please make a note of this password. It will also be written to your .env file.")

    db_ready_event = threading.Event()
    thread_status = {} 

    mysql_thread = threading.Thread(
        target=setup_mysql_thread_target,
        name="MySQL_Setup_Thread",
        args=(db_config, db_ready_event, thread_status)
    )

    codebase_thread = threading.Thread(
        target=deploy_codebase_thread_target,
        name="Codebase_Deployment_Thread",
        args=(project_config, db_ready_event, thread_status)
    )

    mysql_thread.start()
    codebase_thread.start()

    mysql_thread.join()
    codebase_thread.join()

    overall_success = thread_status.get("MySQL_Setup_Thread", False) and thread_status.get("Codebase_Deployment_Thread", False)

    if not overall_success:
        print("\n" + "="*60)
        print(" ❌ INSTALLATION FAILED! ❌ ".center(60))
        print("="*60)
        print("One or more setup phases failed. Please review the errors above.")
        sys.exit(1)

    print("\n" + "="*60)
    print(" 🎉 Installation Complete! 🎉 ".center(60))
    print("="*60)
    print(f"\nYour Laravel Jetstream project '{project_name}' is ready!")
    print(f"\nDatabase user '{db_user}' password: \033[93m{db_pass}\033[0m (This is also in your project's .env file)")
    print(f"\nTo start the development server, navigate into your project directory:")
    print(f"cd {project_name}")
    print(f"\nThen run:")
    print(f"php artisan serve")
    print(f"\nAnd in a separate terminal, to run the frontend development server (for hot-reloading):")
    print(f"npm run dev")
    print(f"\nAccess your application in the browser at: http://127.0.0.1:8000")
    print("\n\n--- TROUBLESHOOTING TIPS ---")
    print("If you encounter 'Access denied' errors or the script hangs on MySQL setup:")
    print(f"1. **Re-check Sudoers (most likely):** Ensure you can run `sudo mysql -e \"SELECT USER();\"` without a password prompt. Adjust your `sudoers` file if needed.")
    print(f"2. **Verify .env file:** Open `{project_name}/.env` and double-check DB_DATABASE, DB_USERNAME, DB_PASSWORD for exact match with the generated password.")
    print("3. **Manual MySQL Test:** Open a new terminal and try to connect to MySQL manually with the *generated* credentials:")
    print(f"   \033[96mmysql -u {db_user} -p\033[0m")
    print("   (Paste the generated password when prompted)")
    print("   If this fails, the problem is specifically with the database user's permissions or password.")
    print("4. **Firewall:** Ensure no firewall (e.g., ufw, firewalld, SELinux) is blocking TCP port 3306 for MySQL connections.")
    print("-----------------------------\n")
    print("Happy coding!")

if __name__ == "__main__":
    main()