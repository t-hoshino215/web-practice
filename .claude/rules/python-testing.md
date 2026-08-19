---
paths:
  - "**/*.py"
---

# Python testing

## Framework

Use `pytest` as the testing framework for Python projects.

## Commands

```bash
# Run tests
uv run pytest

# Check coverage
uv run pytest --cov=src --cov-report=term-missing
```

## Naming conventions

- Test file location: under `tests/`
- Test file name: test_ + <lowercase snake_case> + .py
  Example: `tests/test_login.py`
- Test class name: Test +  <UpperCamelCase of the feature being tested>
  Example: `class TestLoginService:`
- Test function name: test_ + <what is being tested in lowercase snake_case>
  Example: `def test_login_returns_token_when_credentials_valid():`

## Writing rules

- Use `pytest.mark` to categorize tests
- Write tests using the AAA pattern
- As a rule, write one assertion per test function
- Define fixtures in conftest.py and set the appropriate scope
- Use unittest.mock.patch or pytest-mock for mocking external APIs
- Create test data using the factory pattern in `tests/factories/`
- Use `parametrize` to group similar test cases

Example:

```python
import pytest

@pytest.mark.unit
def test_addition():
    # Arrange: define variables
    a = 1
    b = 2

    # Act
    result = sum_numbers(a, b)

    # Assert
    assert result == 3

@pytest.mark.integration
def test_database_connection():
    ...
```
