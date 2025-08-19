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
    ---
    1. **Load seed data**
       **instructions**: Populate tables with initial records from seed_data.json
       **context_identifiers**:
         - db.load_seed
         - data/seed_data.json
    ---
    *** End Steps
    """
    steps = parse_steps_markdown(md)
    assert len(steps) == 2
    assert steps[0]["step"] == 0
    assert steps[0]["description"] == "Initialize database"
    assert "SQLite database" in steps[0]["instructions"]
    assert steps[0]["context_identifiers"] == ["db.init_schema", "config/db.yaml"]
    assert steps[1]["step"] == 1
    assert steps[1]["context_identifiers"][1] == "data/seed_data.json"

def test_single_step():
    md = """
    *** Begin Steps
    0. **Do everything**
       **instructions**: Perform all required tasks in a single step.
       **context_identifiers**:
         - utils.main_handler
    ---
    *** End Steps
    """
    steps = parse_steps_markdown(md)
    assert len(steps) == 1
    assert steps[0]["step"] == 0
    assert steps[0]["description"] == "Do everything"
    assert "single step" in steps[0]["instructions"]
    assert steps[0]["context_identifiers"] == ["utils.main_handler"]

def test_missing_context_identifiers():
    md = """
    *** Begin Steps
    0. **No context**
       **instructions**: Just explain something here
       **context_identifiers**:
    ---
    *** End Steps
    """
    steps = parse_steps_markdown(md)
    assert len(steps) == 1
    assert steps[0]["context_identifiers"] == []

def test_malformed_but_parsable_step():
    md = """
    *** Begin Steps
    0. **Incomplete step**
       **instructions**: This has no context identifiers
       **context_identifiers**:
         - 
    ---
    *** End Steps
    """
    steps = parse_steps_markdown(md)
    assert len(steps) == 1
    assert steps[0]["description"] == "Incomplete step"
    assert steps[0]["context_identifiers"] == []

def test_multiple_hyphen_indented_contexts():
    md = """
    *** Begin Steps
    0. **Handle multi-line**
       **instructions**: Implement complex logic here
       **context_identifiers**:
         - module.first
         - module.second
         - module.third
    ---
    *** End Steps
    """
    steps = parse_steps_markdown(md)
    assert len(steps) == 1
    assert steps[0]["context_identifiers"] == ["module.first", "module.second", "module.third"]

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
