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
            "best practices for the project's tech stack. If no tests exist, create a full testing suite from "
            "scratch, including unit tests, integration tests, and any other relevant types. Prioritize critical "
            "components and ensure maintainability."
        ),
        "icon": "/public/test.svg"
    },
    {
        "label": "Create Containerized Deployment",
        "message": (
            "Examine the project’s structure, dependencies, and services to either create new or update existing "
            "Docker-related files for containerized deployment. If Docker configuration exists, improve it for "
            "efficiency, security, and adherence to best practices (multi-stage builds, environment variables, "
            "network configuration). If none exists, create optimized Dockerfile and docker-compose.yml files "
            "from scratch, including configurations for any required services like databases or caches."
        ),
        "icon": "/public/docker.svg"
    }
]
