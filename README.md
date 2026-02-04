# AI Reviewer

AI-powered assistant for academic peer review. Built with LangGraph, this tool validates references against claims, flags unsupported assertions, performs literature reviews, and suggests relevant citations — helping reviewers and researchers assess rigor more efficiently.

**Note**: This project is under active development and not yet ready for production use. The authors will continue to update this repository with the latest work and evaluation results.

Project funded by RAND: https://rand.org/

## Goals

The main goal of AI Reviewer is to assist and streamline the academic peer review process by reducing manual workload and improving the consistency, transparency, and rigor of evaluations.

## Features

- **Validate reference against claims**: Check the content of each citation to ensure that it backs up the statements made in the text
- **Identify unsupported assertions**: checks whether any statements need the addition of a reference
- **Suggests citations**: suggests references to add to statements made in the text
- **Literature review**: conducts literature review over statements made in the text by searching the web, looking for newer, supporting and contradictory evidences

## Architecture

![Architecture diagram](docs/architecture.png)

## Development

For detailed development setup instructions, see [DEVELOPMENT.md](DEVELOPMENT.md).

## Deployment

- **Railway**: See [docs/railway-deployment.md](docs/railway-deployment.md) for production deployment on Railway
- **Kubernetes**: See [k8s/README.md](k8s/README.md) for Kubernetes/OpenShift deployment

## Testing

Tests are organized by type:

- **`tests/unit/`** - Fast, isolated unit tests
- **`tests/integration/`** - Multi-component integration tests  
- **`tests/evals/`** - LLM-based evaluations (explicit only)

```bash
# Run standard tests (default)
uv run pytest

# Run evaluations
uv run pytest tests/evals/
```

## License

See [LICENSE](LICENSE) file
