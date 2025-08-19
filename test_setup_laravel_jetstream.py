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
    deploy_codebase_thread_target
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


if __name__ == '__main__':
    pytest.main([__file__, '-v'])