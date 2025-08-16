AGENT_TIDE_PORT = 9753

STARTERS = [
    {
        "label": "Generate Mermaid Class Diagram",
        "message": (
            "Generate me a mermaid class diaram representing the repo's structure and main modules! Make it visually appealing and clean"
        ),
        "icon": "/public/diagram.svg"
    },
    {
        "label": "Implement Missing Tests",
        "message": (
            "Review the project’s existing tests (if present) to understand patterns, coverage, and structure. "
            "If tests already exist, enhance them by filling coverage gaps, improving clarity, and following "
            "best practices for the project's tech stack. If no tests exist, come up with a plan for a full testing suite from "
            "scratch, including unit tests, integration tests, and any other relevant types. Prioritize critical "
            "components and ensure maintainability."
        ),
        "icon": "/public/test.svg"
    },
    {
        "label": "Create Containerized Deployment",
        "message": (
            "Examine the project’s structure, dependencies, and services and come up with a detailed plan to either create new or update existing "
            "Docker-related files for containerized deployment. Make sure to ask me to review your plan before moving on! If Docker configuration exists, improve it for "
            "efficiency, security, and adherence to best practices (multi-stage builds, environment variables, "
            "network configuration). If none exists, create optimized Dockerfile and docker-compose.yml files "
            "from scratch, including configurations for any required services like databases or caches."
        ),
        "icon": "/public/docker.svg"
    }
]

MISSING_CONFIG_MESSAGE = """
A valid configuration was not found at `{agent_tide_config_path}` Please provide a valid `{config_file}` by editing the following config example and uploading it below.

```yml
{example_config}
```
"""

AICORE_CONFIG_EXAMPLE = """
# learn more about the LlmConfig class at https://github.com/BrunoV21/AiCore/tree/main/config
llm:
  temperature: 0
  max_tokens: 32000

  # provider: "groq"
  # api_key: "YOUR-SUPER-SCECRET-GROQ-API-KEY"
  # model: "openai/gpt-oss-20b"

  provider: "openai"
  api_key: "YOUR-SUPER-SCECRET-OPENAI-API-KEY"
  model: "gpt-4.1"

  # provider: "anthropic"
  # model: "claude-sonnet-4-20250514"
  # api_key: "YOUR-SUPER-SCRET-CLAUDE-API-KEY"
"""

EXCEPTION_MESSAGE = """
Here is the original exception:
```json
{exception}
```
"""


