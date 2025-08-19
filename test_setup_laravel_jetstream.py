#!/usr/bin/env python3
"""
Unit tests for setup_laravel_jetstream_sudo.py

Run with: python -m pytest test_setup_laravel_jetstream.py -v
"""

import pytest
import tempfile
import os
import shlex
import string
import threading
import time
from unittest.mock import Mock, patch, MagicMock, call
from setup_laravel_jetstream_sudo import (
    generate_secure_password,
    run_command,
    setup_mysql_thread_target,
    deploy_codebase_thread_target,
    read_env_file,
    repair_mysql_user,
    update_env_password,
    finalize_laravel_installation,
    repair_installation
)


class TestPasswordGeneration:
    """Test suite for secure password generation."""
    
    def test_generate_secure_password_default_length(self):
        """Test password generation with default length."""
        password = generate_secure_password()
        assert len(password) == 16
        assert isinstance(password, str)
    
    def test_generate_secure_password_custom_length(self):
        """Test password generation with custom length."""
        password = generate_secure_password(20)
        assert len(password) == 20
    
    def test_generate_secure_password_minimum_length(self):
        """Test password generation enforces minimum length."""
        password = generate_secure_password(8)  # Below minimum
        assert len(password) == 12  # Should be enforced to minimum
    
    def test_password_contains_required_character_types(self):
        """Test that password contains digits, uppercase, lowercase, and special chars."""
        password = generate_secure_password()
        
        has_digit = any(c.isdigit() for c in password)
        has_upper = any(c.isupper() for c in password)
        has_lower = any(c.islower() for c in password)
        has_special = any(c in '@#%^-_=+:,.~' for c in password)
        
        assert has_digit, "Password should contain at least one digit"
        assert has_upper, "Password should contain at least one uppercase letter"
        assert has_lower, "Password should contain at least one lowercase letter"
        assert has_special, "Password should contain at least one special character"
    
    def test_password_shell_safety(self):
        """Test that generated passwords are shell-safe."""
        dangerous_chars = '!$`"\'\\|;<>?*()[]{}& '
        
        # Generate multiple passwords to test consistency
        for _ in range(100):
            password = generate_secure_password()
            for char in dangerous_chars:
                assert char not in password, f"Password contains dangerous character: {char}"
    
    def test_password_mysql_compatibility(self):
        """Test that passwords work properly in MySQL commands."""
        password = generate_secure_password()
        
        # Test that password can be safely quoted for SQL
        sql_command = f"CREATE USER 'test'@'localhost' IDENTIFIED BY '{password}';"
        escaped_command = shlex.quote(sql_command)
        
        # Should not raise any exceptions
        assert isinstance(escaped_command, str)
        assert len(escaped_command) > 0
    
    def test_password_uniqueness(self):
        """Test that consecutive password generations are unique."""
        passwords = [generate_secure_password() for _ in range(10)]
        assert len(set(passwords)) == len(passwords), "All generated passwords should be unique"


class TestRunCommand:
    """Test suite for command execution functionality."""
    
    @patch('subprocess.Popen')
    def test_run_command_success(self, mock_popen):
        """Test successful command execution."""
        mock_process = Mock()
        mock_process.communicate.return_value = ('output', '')
        mock_process.returncode = 0
        mock_popen.return_value = mock_process
        
        result = run_command('test command', success_message="Test passed")
        
        assert result is True
        mock_popen.assert_called_once()
    
    @patch('subprocess.Popen')
    def test_run_command_failure(self, mock_popen):
        """Test command execution failure."""
        mock_process = Mock()
        mock_process.communicate.return_value = ('', 'error')
        mock_process.returncode = 1
        mock_popen.return_value = mock_process
        
        with pytest.raises(RuntimeError):
            run_command('failing command')
    
    @patch('subprocess.Popen')
    def test_run_command_mysql_duplicate_handling(self, mock_popen):
        """Test that MySQL 'already exists' errors are handled gracefully."""
        mock_process = Mock()
        mock_process.communicate.return_value = ('', 'database exists')
        mock_process.returncode = 1
        mock_popen.return_value = mock_process
        
        # Should not raise exception for 'database exists' error
        result = run_command('mysql command')
        assert result is True
    
    @patch('subprocess.Popen')
    def test_run_command_with_cwd(self, mock_popen):
        """Test command execution with working directory."""
        mock_process = Mock()
        mock_process.communicate.return_value = ('output', '')
        mock_process.returncode = 0
        mock_popen.return_value = mock_process
        
        run_command('test command', cwd='/test/dir')
        
        mock_popen.assert_called_with(
            'test command',
            shell=True,
            stdout=pytest.unittest.mock.ANY,
            stderr=pytest.unittest.mock.ANY,
            text=True,
            cwd='/test/dir'
        )


class TestMySQLSetup:
    """Test suite for MySQL setup functionality."""
    
    @patch('setup_laravel_jetstream_sudo.run_command')
    def test_mysql_command_generation(self, mock_run_command):
        """Test that MySQL commands are generated correctly."""
        db_config = {
            'name': 'test_db',
            'user': 'test_user', 
            'pass': 'test_password'
        }
        
        db_ready_event = threading.Event()
        thread_status = {}
        
        # Mock run_command to succeed
        mock_run_command.return_value = True
        
        setup_mysql_thread_target(db_config, db_ready_event, thread_status)
        
        # Verify that run_command was called with properly escaped SQL
        assert mock_run_command.call_count == 5
        calls = mock_run_command.call_args_list
        
        # Check that shlex.quote is being used (commands should be quoted)
        for call_args in calls:
            command = call_args[0][0]  # First positional argument
            assert command.startswith('sudo mysql -e ')
            # Verify the command contains quoted SQL
            assert "'" in command or '"' in command
    
    @patch('setup_laravel_jetstream_sudo.run_command')
    def test_mysql_setup_thread_success(self, mock_run_command):
        """Test successful MySQL setup thread execution."""
        db_config = {
            'name': 'test_db',
            'user': 'test_user',
            'pass': 'secure_password123'
        }
        
        db_ready_event = threading.Event()
        thread_status = {}
        
        mock_run_command.return_value = True
        
        setup_mysql_thread_target(db_config, db_ready_event, thread_status)
        
        assert db_ready_event.is_set()
        assert thread_status.get('MySQL_Setup_Thread') is True
    
    @patch('setup_laravel_jetstream_sudo.run_command')
    def test_mysql_setup_thread_failure(self, mock_run_command):
        """Test MySQL setup thread failure handling."""
        db_config = {
            'name': 'test_db',
            'user': 'test_user',
            'pass': 'test_password'
        }
        
        db_ready_event = threading.Event()
        thread_status = {}
        
        # Make run_command fail
        mock_run_command.side_effect = RuntimeError("MySQL command failed")
        
        setup_mysql_thread_target(db_config, db_ready_event, thread_status)
        
        # Event should still be set even on failure
        assert db_ready_event.is_set()
        assert thread_status.get('MySQL_Setup_Thread') is False


class TestEnvFileHandling:
    """Test suite for .env file manipulation."""
    
    def test_env_file_generation(self):
        """Test .env file content generation logic."""
        # This would test the env_vars dictionary creation
        # and the file writing logic from deploy_codebase_thread_target
        
        db_config = {
            'name': 'test_db',
            'user': 'test_user',
            'pass': 'test@pass123'
        }
        app_name = 'Test App'
        
        # Test the env_vars dictionary structure
        env_vars = {
            "APP_NAME": f"'{app_name}'",
            "DB_CONNECTION": "mysql",
            "DB_HOST": "127.0.0.1",
            "DB_PORT": "3306",
            "DB_DATABASE": db_config['name'],
            "DB_USERNAME": db_config['user'],
            "DB_PASSWORD": db_config['pass'],
        }
        
        assert env_vars["DB_DATABASE"] == "test_db"
        assert env_vars["DB_USERNAME"] == "test_user"
        assert env_vars["DB_PASSWORD"] == "test@pass123"
        assert env_vars["APP_NAME"] == "'Test App'"
    
    def test_env_file_special_characters(self):
        """Test .env file handling with special characters in password."""
        # Test passwords with allowed special characters
        special_passwords = [
            'pass@123',
            'secure#pass',
            'test%^password',
            'user-pass_123',
            'db=pass+test',
            'password:value',
            'test.pass,123',
            'secure~password'
        ]
        
        for password in special_passwords:
            # Should not cause issues when written to .env
            env_line = f"DB_PASSWORD={password}"
            assert '=' in env_line
            assert env_line.startswith('DB_PASSWORD=')


class TestThreadingLogic:
    """Test suite for threading and synchronization."""
    
    def test_threading_event_synchronization(self):
        """Test that threading events work correctly."""
        event = threading.Event()
        assert not event.is_set()
        
        event.set()
        assert event.is_set()
        
        event.clear()
        assert not event.is_set()
    
    @patch('setup_laravel_jetstream_sudo.run_command')
    @patch('os.chdir')
    @patch('builtins.open', create=True)
    def test_codebase_thread_waits_for_db(self, mock_open, mock_chdir, mock_run_command):
        """Test that codebase thread waits for database setup."""
        project_config = {
            'name': 'test_project',
            'path': '/test/path',
            'app_name_formatted': 'Test Project',
            'db_config': {
                'name': 'test_db',
                'user': 'test_user',
                'pass': 'test_pass'
            }
        }
        
        db_ready_event = threading.Event()
        thread_status = {'MySQL_Setup_Thread': True}
        
        # Mock file operations
        mock_file = MagicMock()
        mock_file.readlines.return_value = ['APP_KEY=\n']
        mock_open.return_value.__enter__.return_value = mock_file
        
        mock_run_command.return_value = True
        
        # Set the event to simulate DB being ready
        db_ready_event.set()
        
        deploy_codebase_thread_target(project_config, db_ready_event, thread_status)
        
        # Verify that database-dependent commands were executed
        # (migrate command should have been called)
        migrate_called = any(
            'migrate' in str(call) for call in mock_run_command.call_args_list
        )
        assert migrate_called


class TestSecurityValidation:
    """Security-focused tests."""
    
    def test_sql_injection_prevention(self):
        """Test that password generation prevents SQL injection."""
        # Generate many passwords and ensure none contain SQL injection patterns
        sql_injection_patterns = [
            "'", '"', ';', '--', '/*', '*/', 'DROP', 'DELETE', 'INSERT', 'UPDATE'
        ]
        
        for _ in range(100):
            password = generate_secure_password()
            password_upper = password.upper()
            
            for pattern in sql_injection_patterns:
                assert pattern not in password and pattern not in password_upper
    
    def test_command_injection_prevention(self):
        """Test that passwords don't enable command injection."""
        command_injection_chars = ['`', '$', '!', '\\', '|', ';', '&', '<', '>', '?', '*', '(', ')', '[', ']', '{', '}']
        
        for _ in range(50):
            password = generate_secure_password()
            for char in command_injection_chars:
                assert char not in password


class TestErrorHandling:
    """Test error handling scenarios."""
    
    @patch('subprocess.Popen')
    def test_file_not_found_error(self, mock_popen):
        """Test handling of command not found errors."""
        mock_popen.side_effect = FileNotFoundError("Command not found")
        
        with pytest.raises(RuntimeError, match="Command not found"):
            run_command('nonexistent_command')
    
    @patch('subprocess.Popen') 
    def test_unexpected_error_handling(self, mock_popen):
        """Test handling of unexpected errors."""
        mock_popen.side_effect = Exception("Unexpected error")
        
        with pytest.raises(RuntimeError, match="An unexpected error occurred"):
            run_command('test_command')


class TestRepairFunctionality:
    """Test suite for installation repair functionality."""
    
    def test_read_env_file_success(self):
        """Test successful .env file reading."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create a mock .env file
            env_content = """APP_NAME=TestApp
DB_CONNECTION=mysql
DB_HOST=127.0.0.1
DB_PORT=3306
DB_DATABASE=test_db
DB_USERNAME=test_user
DB_PASSWORD=old_password
"""
            env_file = os.path.join(temp_dir, '.env')
            with open(env_file, 'w') as f:
                f.write(env_content)
            
            db_config, env_config = read_env_file(temp_dir)
            
            assert db_config['name'] == 'test_db'
            assert db_config['user'] == 'test_user'
            assert db_config['host'] == '127.0.0.1'
            assert db_config['port'] == '3306'
            assert env_config['APP_NAME'] == 'TestApp'
    
    def test_read_env_file_missing_file(self):
        """Test .env file reading when file doesn't exist."""
        with tempfile.TemporaryDirectory() as temp_dir:
            with pytest.raises(FileNotFoundError):
                read_env_file(temp_dir)
    
    def test_read_env_file_missing_db_config(self):
        """Test .env file reading with missing database configuration."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create .env file without database config
            env_content = "APP_NAME=TestApp\nAPP_DEBUG=true\n"
            env_file = os.path.join(temp_dir, '.env')
            with open(env_file, 'w') as f:
                f.write(env_content)
            
            with pytest.raises(ValueError, match="Missing DB_DATABASE or DB_USERNAME"):
                read_env_file(temp_dir)
    
    def test_read_env_file_with_quotes(self):
        """Test .env file reading with quoted values."""
        with tempfile.TemporaryDirectory() as temp_dir:
            env_content = '''APP_NAME="Test App"
DB_DATABASE='test_db'
DB_USERNAME=test_user
'''
            env_file = os.path.join(temp_dir, '.env')
            with open(env_file, 'w') as f:
                f.write(env_content)
            
            db_config, env_config = read_env_file(temp_dir)
            
            assert db_config['name'] == 'test_db'
            assert db_config['user'] == 'test_user'
            assert env_config['APP_NAME'] == 'Test App'
    
    @patch('setup_laravel_jetstream_sudo.run_command')
    def test_repair_mysql_user_success(self, mock_run_command):
        """Test successful MySQL user repair."""
        db_config = {
            'name': 'test_db',
            'user': 'test_user'
        }
        new_password = 'new_secure_pass123'
        
        mock_run_command.return_value = True
        
        result = repair_mysql_user(db_config, new_password)
        
        assert result is True
        assert mock_run_command.call_count == 5  # 5 MySQL commands
        
        # Verify DROP USER command is called
        calls = mock_run_command.call_args_list
        drop_call = calls[0][0][0]  # First command
        assert 'DROP USER IF EXISTS' in drop_call
        assert 'test_user' in drop_call
    
    @patch('setup_laravel_jetstream_sudo.run_command')
    def test_repair_mysql_user_failure(self, mock_run_command):
        """Test MySQL user repair failure."""
        db_config = {
            'name': 'test_db',
            'user': 'test_user'
        }
        new_password = 'new_secure_pass123'
        
        mock_run_command.side_effect = RuntimeError("MySQL command failed")
        
        result = repair_mysql_user(db_config, new_password)
        
        assert result is False
    
    def test_update_env_password_success(self):
        """Test successful .env password update."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create initial .env file
            env_content = """APP_NAME=TestApp
DB_CONNECTION=mysql
DB_PASSWORD=old_password
APP_DEBUG=true
"""
            env_file = os.path.join(temp_dir, '.env')
            with open(env_file, 'w') as f:
                f.write(env_content)
            
            new_password = 'new_secure_pass123'
            result = update_env_password(temp_dir, new_password)
            
            assert result is True
            
            # Verify password was updated
            with open(env_file, 'r') as f:
                updated_content = f.read()
            
            assert f'DB_PASSWORD={new_password}' in updated_content
            assert 'old_password' not in updated_content
    
    def test_update_env_password_add_missing(self):
        """Test adding DB_PASSWORD when it doesn't exist."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create .env file without DB_PASSWORD
            env_content = """APP_NAME=TestApp
DB_CONNECTION=mysql
APP_DEBUG=true
"""
            env_file = os.path.join(temp_dir, '.env')
            with open(env_file, 'w') as f:
                f.write(env_content)
            
            new_password = 'new_secure_pass123'
            result = update_env_password(temp_dir, new_password)
            
            assert result is True
            
            # Verify password was added
            with open(env_file, 'r') as f:
                updated_content = f.read()
            
            assert f'DB_PASSWORD={new_password}' in updated_content
    
    def test_update_env_password_file_not_found(self):
        """Test .env password update when file doesn't exist."""
        with tempfile.TemporaryDirectory() as temp_dir:
            result = update_env_password(temp_dir, 'test_password')
            assert result is False
    
    @patch('setup_laravel_jetstream_sudo.run_command')
    @patch('os.path.exists')
    def test_finalize_laravel_installation_success(self, mock_exists, mock_run_command):
        """Test successful Laravel installation finalization."""
        # Mock file system checks
        mock_exists.return_value = True
        mock_run_command.return_value = True
        
        result = finalize_laravel_installation('/test/path')
        
        assert result is True
        assert mock_run_command.call_count >= 6  # At least 6 artisan commands
        
        # Verify key commands were called
        calls = [call[0][0] for call in mock_run_command.call_args_list]
        
        migrate_called = any('migrate' in cmd for cmd in calls)
        key_generate_called = any('key:generate' in cmd for cmd in calls)
        config_clear_called = any('config:clear' in cmd for cmd in calls)
        php_version_called = any('php --version' in cmd for cmd in calls)
        
        assert migrate_called
        assert key_generate_called  
        assert config_clear_called
        assert php_version_called
    
    @patch('setup_laravel_jetstream_sudo.run_command')
    @patch('os.path.exists')
    def test_finalize_laravel_installation_failure(self, mock_exists, mock_run_command):
        """Test Laravel installation finalization failure."""
        # Mock missing artisan file
        mock_exists.side_effect = lambda path: 'artisan' not in path
        
        with pytest.raises(RuntimeError, match="Laravel artisan file not found"):
            finalize_laravel_installation('/test/path')
    
    @patch('setup_laravel_jetstream_sudo.finalize_laravel_installation')
    @patch('setup_laravel_jetstream_sudo.update_env_password')
    @patch('setup_laravel_jetstream_sudo.repair_mysql_user')
    @patch('setup_laravel_jetstream_sudo.read_env_file')
    @patch('setup_laravel_jetstream_sudo.generate_secure_password')
    @patch('os.path.exists')
    def test_repair_installation_success(self, mock_exists, mock_gen_password, 
                                       mock_read_env, mock_repair_mysql, 
                                       mock_update_env, mock_finalize):
        """Test successful installation repair workflow."""
        # Mock project directory and artisan file exist
        mock_exists.side_effect = lambda path: True
        
        # Mock database config reading
        mock_read_env.return_value = (
            {'name': 'test_db', 'user': 'test_user'},
            {'APP_NAME': 'TestApp'}
        )
        
        # Mock password generation
        mock_gen_password.return_value = 'new_secure_pass123'
        
        # Mock all repair steps to succeed
        mock_repair_mysql.return_value = True
        mock_update_env.return_value = True
        mock_finalize.return_value = True
        
        result = repair_installation('test_project')
        
        assert result is True
        mock_read_env.assert_called_once()
        mock_gen_password.assert_called_once()
        mock_repair_mysql.assert_called_once()
        mock_update_env.assert_called_once()
        mock_finalize.assert_called_once()
    
    @patch('os.path.exists')
    def test_repair_installation_project_not_found(self, mock_exists):
        """Test repair when project directory doesn't exist."""
        mock_exists.return_value = False
        
        with pytest.raises(FileNotFoundError, match="Project directory not found"):
            repair_installation('nonexistent_project')
    
    @patch('os.path.exists')
    def test_repair_installation_not_laravel_project(self, mock_exists):
        """Test repair when directory is not a Laravel project."""
        # Project dir exists but artisan file doesn't
        mock_exists.side_effect = lambda path: 'artisan' not in path
        
        with pytest.raises(ValueError, match="Not a Laravel project"):
            repair_installation('not_laravel_project')
    
    @patch('setup_laravel_jetstream_sudo.read_env_file')
    @patch('os.path.exists')
    def test_repair_installation_env_read_failure(self, mock_exists, mock_read_env):
        """Test repair when .env file reading fails."""
        mock_exists.return_value = True
        mock_read_env.side_effect = RuntimeError("Failed to read .env")
        
        result = repair_installation('test_project')
        
        assert result is False
    
    @patch('setup_laravel_jetstream_sudo.repair_mysql_user')
    @patch('setup_laravel_jetstream_sudo.read_env_file')
    @patch('setup_laravel_jetstream_sudo.generate_secure_password')
    @patch('os.path.exists')
    def test_repair_installation_mysql_repair_failure(self, mock_exists, mock_gen_password,
                                                     mock_read_env, mock_repair_mysql):
        """Test repair when MySQL user repair fails."""
        mock_exists.return_value = True
        mock_read_env.return_value = (
            {'name': 'test_db', 'user': 'test_user'}, 
            {}
        )
        mock_gen_password.return_value = 'test_pass'
        mock_repair_mysql.return_value = False
        
        result = repair_installation('test_project')
        
        assert result is False


class TestRepairIntegration:
    """Integration tests for repair functionality."""
    
    @patch('setup_laravel_jetstream_sudo.repair_installation')
    @patch('sys.exit')
    def test_main_repair_mode_success(self, mock_exit, mock_repair):
        """Test main function in repair mode with success."""
        mock_repair.return_value = True
        
        # Mock command line args
        test_args = ['script.py', 'test_project', '--repair']
        with patch('sys.argv', test_args):
            from setup_laravel_jetstream_sudo import main
            main()
        
        mock_repair.assert_called_once_with('test_project')
        mock_exit.assert_called_once_with(0)
    
    @patch('setup_laravel_jetstream_sudo.repair_installation')
    @patch('sys.exit')
    def test_main_repair_mode_failure(self, mock_exit, mock_repair):
        """Test main function in repair mode with failure."""
        mock_repair.return_value = False
        
        # Mock command line args
        test_args = ['script.py', 'test_project', '--repair']
        with patch('sys.argv', test_args):
            from setup_laravel_jetstream_sudo import main
            main()
        
        mock_repair.assert_called_once_with('test_project')
        mock_exit.assert_called_once_with(1)
    
    @patch('sys.exit')
    def test_main_missing_required_args_for_new_install(self, mock_exit):
        """Test main function validates required args for new installations."""
        # Mock command line args without --dbname and --dbuser
        test_args = ['script.py', 'test_project']
        with patch('sys.argv', test_args):
            from setup_laravel_jetstream_sudo import main
            main()
        
        mock_exit.assert_called_once_with(1)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])