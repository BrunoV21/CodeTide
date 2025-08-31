from codetide.agents.tide.utils import parse_steps_markdown
import pytest

def generate_steps_md(n):
    """
    Generate markdown with n well-formed steps.
    """
    steps_md = ["*** Begin Steps"]
    for i in range(n):
        steps_md.append(f"""{i}. **Step {i} description**
   **instructions**: Perform task {i} with detailed steps
   **context_identifiers**:
     - module.{i}
     - path/to/file_{i}.py
   **modify_identifiers**:
     - output/result_{i}.py
     - config/settings_{i}.json
---""")
    steps_md.append("*** End Steps")
    return "\n".join(steps_md)


def test_parse_multiple_steps():
    md = """
    *** Begin Steps
    0. **Initialize database**
       **instructions**: Set up a new SQLite database and define schema
       **context_identifiers**:
         - db.init_schema
         - config/db.yaml
       **modify_identifiers**:
         - database/schema.sql
         - config/database.ini
    ---
    1. **Load seed data**
       **instructions**: Populate tables with initial records from seed_data.json
       **context_identifiers**:
         - db.load_seed
         - data/seed_data.json
       **modify_identifiers**:
         - database/populated.db
         - logs/seed_import.log
    ---
    *** End Steps
    """
    steps = parse_steps_markdown(md)

    assert len(steps) == 2
    
    # Test step 0
    assert steps[0]["step"] == 0
    assert steps[0]["description"] == "Initialize database"
    assert "SQLite database" in steps[0]["instructions"]
    assert steps[0]["context_identifiers"] == ["db.init_schema", "config/db.yaml"]
    assert steps[0]["modify_identifiers"] == ["database/schema.sql", "config/database.ini"]
    
    # Test step 1
    assert steps[1]["step"] == 1
    assert steps[1]["context_identifiers"][1] == "data/seed_data.json"
    assert steps[1]["modify_identifiers"] == ["database/populated.db", "logs/seed_import.log"]

def test_single_step():
    md = """
    *** Begin Steps
    0. **Do everything**
       **instructions**: Perform all required tasks in a single step.
       **context_identifiers**:
         - utils.main_handler
       **modify_identifiers**:
         - output/final_result.txt
    ---
    *** End Steps
    """
    steps = parse_steps_markdown(md)
    assert len(steps) == 1
    assert steps[0]["step"] == 0
    assert steps[0]["description"] == "Do everything"
    assert "single step" in steps[0]["instructions"]
    assert steps[0]["context_identifiers"] == ["utils.main_handler"]
    assert steps[0]["modify_identifiers"] == ["output/final_result.txt"]

def test_empty_identifiers():
    md = """
    *** Begin Steps
    0. **No identifiers**
       **instructions**: Just explain something here
       **context_identifiers**:
       **modify_identifiers**:
    ---
    *** End Steps
    """
    steps = parse_steps_markdown(md)
    assert len(steps) == 1
    assert steps[0]["context_identifiers"] == []
    assert steps[0]["modify_identifiers"] == []

def test_partial_empty_identifiers():
    md = """
    *** Begin Steps
    0. **Only context**
       **instructions**: Has context but no modify identifiers
       **context_identifiers**:
         - some.module
         - some/file.py
       **modify_identifiers**:
    ---
    1. **Only modify**
       **instructions**: Has modify but no context identifiers
       **context_identifiers**:
       **modify_identifiers**:
         - output/result.json
         - logs/activity.log
    ---
    *** End Steps
    """
    steps = parse_steps_markdown(md)
    assert len(steps) == 2
    
    # Step with only context
    assert steps[0]["context_identifiers"] == ["some.module", "some/file.py"]
    assert steps[0]["modify_identifiers"] == []
    
    # Step with only modify
    assert steps[1]["context_identifiers"] == []
    assert steps[1]["modify_identifiers"] == ["output/result.json", "logs/activity.log"]

def test_malformed_but_parsable_step():
    md = """
    *** Begin Steps
    0. **Incomplete step**
       **instructions**: This has empty identifier lines
       **context_identifiers**:
         - 
       **modify_identifiers**:
         - 
    ---
    *** End Steps
    """
    steps = parse_steps_markdown(md)
    assert len(steps) == 1
    assert steps[0]["description"] == "Incomplete step"
    assert steps[0]["context_identifiers"] == []
    assert steps[0]["modify_identifiers"] == []

def test_multiple_hyphen_indented_identifiers():
    md = """
    *** Begin Steps
    0. **Handle multi-line**
       **instructions**: Implement complex logic here
       **context_identifiers**:
         - module.first
         - module.second
         - module.third
       **modify_identifiers**:
         - output/first.py
         - output/second.py
         - output/third.py
         - logs/process.log
    ---
    *** End Steps
    """
    steps = parse_steps_markdown(md)
    assert len(steps) == 1
    assert steps[0]["context_identifiers"] == ["module.first", "module.second", "module.third"]
    assert steps[0]["modify_identifiers"] == ["output/first.py", "output/second.py", "output/third.py", "logs/process.log"]

def test_mixed_whitespace_handling():
    md = """
    *** Begin Steps
    0. **Whitespace test**
       **instructions**: Test various whitespace scenarios
       **context_identifiers**:
         - module.with.spaces  
         -    indented.module
         - normal.module
       **modify_identifiers**:
         - output/spaced.file  
         -    output/indented.file
         - output/normal.file
    ---
    *** End Steps
    """
    steps = parse_steps_markdown(md)
    assert len(steps) == 1
    # Should strip whitespace from identifier names
    assert steps[0]["context_identifiers"] == ["module.with.spaces", "indented.module", "normal.module"]
    assert steps[0]["modify_identifiers"] == ["output/spaced.file", "output/indented.file", "output/normal.file"]

@pytest.mark.parametrize("count", [5, 10, 50])
def test_large_number_of_steps(count):
    md = generate_steps_md(count)
    steps = parse_steps_markdown(md)

    assert len(steps) == count

    for i, step in enumerate(steps):
        assert step["step"] == i
        assert step["description"] == f"Step {i} description"
        assert f"task {i}" in step["instructions"]
        assert step["context_identifiers"] == [f"module.{i}", f"path/to/file_{i}.py"]
        assert step["modify_identifiers"] == [f"output/result_{i}.py", f"config/settings_{i}.json"]

def test_complex_real_world_example():
    """Test with a more realistic example that might be seen in practice."""
    md = """
    *** Begin Steps
    0. **Setup authentication system**
       **instructions**: Create user authentication with JWT tokens and bcrypt password hashing
       **context_identifiers**:
         - auth.models.User
         - auth.utils.jwt_helper
         - config/security.yaml
         - requirements.txt
       **modify_identifiers**:
         - auth/models.py
         - auth/views.py
         - auth/serializers.py
         - config/settings.py
    ---
    1. **Implement API endpoints**
       **instructions**: Create REST API endpoints for user registration, login, and profile management
       **context_identifiers**:
         - auth.models.User
         - api.base_views
         - docs/api_spec.md
       **modify_identifiers**:
         - api/auth_views.py
         - api/urls.py
         - tests/test_auth_api.py
    ---
    *** End Steps
    """
    steps = parse_steps_markdown(md)
    assert len(steps) == 2
    
    # Verify complex step structure
    assert steps[0]["description"] == "Setup authentication system"
    assert "JWT tokens" in steps[0]["instructions"]
    assert len(steps[0]["context_identifiers"]) == 4
    assert len(steps[0]["modify_identifiers"]) == 4
    
    assert steps[1]["description"] == "Implement API endpoints"
    assert "REST API" in steps[1]["instructions"]
    assert len(steps[1]["context_identifiers"]) == 3
    assert len(steps[1]["modify_identifiers"]) == 3