# Testing Guide

This document describes how to run and contribute to the test suite for the Laravel Jetstream Bootstrapper.

## Quick Start

### Prerequisites

```bash
# Install development dependencies
pip install -r requirements-dev.txt

# Or use make
make install-dev
```

### Running Tests

```bash
# Run all tests
make test

# Run with coverage
make test-cov

# Run only unit tests
make test-unit

# Run only security tests
make test-security
```

## Test Structure

### Test Categories

Our test suite is organized into several categories:

- **Unit Tests**: Test individual functions in isolation
- **Integration Tests**: Test component interactions  
- **Security Tests**: Validate security measures
- **Error Handling Tests**: Test failure scenarios
- **Repair Tests**: Test installation repair functionality

### Test Files

- `test_setup_laravel_jetstream.py` - Main test suite (650+ lines)
- `pytest.ini` - Pytest configuration
- `requirements-dev.txt` - Test dependencies

### New Repair Test Classes

- `TestRepairFunctionality` - Tests for repair functions
- `TestRepairIntegration` - End-to-end repair workflow tests

## Test Coverage

### What's Tested

✅ **Password Generation**
- Character composition (digits, letters, special chars)
- Length validation (minimum 12 characters)
- Shell safety (no dangerous characters)
- MySQL compatibility
- Uniqueness across generations

✅ **Command Execution** 
- Success/failure handling
- MySQL error tolerance ("database exists")
- Working directory support
- Error message handling

✅ **MySQL Setup**
- SQL command generation
- Shell escaping with `shlex.quote()`
- Thread synchronization
- Error recovery

✅ **Security**
- SQL injection prevention
- Command injection prevention
- Shell escape validation

✅ **Threading Logic**
- Event synchronization
- Thread status tracking
- Failure handling

✅ **Repair Functionality**
- .env file parsing and validation
- MySQL user password reset
- Laravel project structure validation
- Database connection recovery
- Migration execution and error handling
- Cache table creation and management

### Coverage Reports

Generate detailed coverage reports:

```bash
make test-cov
```

This creates:
- Terminal coverage report
- HTML coverage report in `htmlcov/`

## Writing Tests

### Test Structure

```python
class TestFeatureName:
    """Test suite for specific feature."""
    
    def test_specific_behavior(self):
        """Test description."""
        # Arrange
        input_data = "test_input"
        
        # Act
        result = function_under_test(input_data)
        
        # Assert
        assert result == expected_value
```

### Mocking Guidelines

Use `@patch` for external dependencies:

```python
@patch('subprocess.Popen')
def test_command_execution(self, mock_popen):
    """Test command execution with mocked subprocess."""
    mock_process = Mock()
    mock_process.returncode = 0
    mock_popen.return_value = mock_process
    
    result = run_command('test command')
    assert result is True
```

### Test Markers

Use pytest markers to categorize tests:

```python
@pytest.mark.unit
def test_password_generation():
    """Unit test for password generation."""
    pass

@pytest.mark.security  
def test_sql_injection_prevention():
    """Security test for SQL injection prevention."""
    pass
```

## Continuous Integration

### GitHub Actions

The project uses GitHub Actions for CI/CD:

- **Tests**: Run on Python 3.8-3.11
- **Security Scanning**: Bandit + Safety checks
- **Coverage**: Codecov integration

### Adding New Tests

When adding features:

1. Write tests first (TDD approach)
2. Ensure tests cover happy path and error cases
3. Add security tests for user inputs
4. Update this documentation if needed

### Running CI Locally

Simulate CI environment:

```bash
# Test against multiple Python versions (requires pyenv)
for version in 3.8 3.9 3.10 3.11; do
    echo "Testing Python $version"
    pyenv local $version
    make test
done
```

## Security Testing

### Automated Security Scans

```bash
# Run security linting
make lint

# Manual security checks
bandit -r setup_laravel_jetstream_sudo.py
safety check
```

### Security Test Categories

1. **Input Validation**: Password character restrictions
2. **Command Injection**: Shell escape validation  
3. **SQL Injection**: Password content validation
4. **File System**: Path traversal prevention

## Performance Testing

While not currently implemented, consider adding:

```python
def test_password_generation_performance():
    """Test password generation performance."""
    import time
    
    start_time = time.time()
    for _ in range(1000):
        generate_secure_password()
    duration = time.time() - start_time
    
    assert duration < 1.0  # Should complete in under 1 second
```

## Troubleshooting Tests

### Common Issues

1. **Import Errors**: Ensure the main script is in Python path
2. **Mock Failures**: Check mock object configuration
3. **Threading Tests**: Use proper synchronization primitives

### Debugging Tests

```bash
# Run with verbose output
pytest -vvv test_setup_laravel_jetstream.py::TestClassName::test_method

# Run with pdb debugger
pytest --pdb test_setup_laravel_jetstream.py

# Print test coverage gaps
pytest --cov-report=term-missing
```

## Contributing

When contributing tests:

1. Follow existing naming conventions
2. Add docstrings to test methods
3. Group related tests in classes
4. Mock external dependencies
5. Test both success and failure cases
6. Add security considerations

### Test Checklist

- [ ] Function works with valid inputs
- [ ] Function handles invalid inputs gracefully
- [ ] Security implications are tested
- [ ] Edge cases are covered
- [ ] Error messages are appropriate
- [ ] Performance is acceptable
- [ ] Thread safety (if applicable)

## Future Enhancements

Consider adding:

- **Integration Tests**: Test with real MySQL (Docker)
- **End-to-End Tests**: Full script execution
- **Property-Based Testing**: Hypothesis for password generation
- **Load Testing**: Threading performance under stress
- **Compatibility Tests**: Different OS/MySQL versions