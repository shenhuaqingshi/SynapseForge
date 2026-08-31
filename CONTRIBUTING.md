# Contributing to SynapseForge

Thank you for contributing to SynapseForge! We welcome contributions from both human researchers/engineers and autonomous AI agents.

## Development Workflow

1. Fork the repository and clone locally.
2. Install dependencies:
   ```bash
   pip install -e .
   pip install pytest pyyaml requests markdown jinja2
   ```
3. Run test suite:
   ```bash
   pytest -v tests/
   ```
4. Run document linter:
   ```bash
   synapseforge lint
   ```
5. Follow the [Linter Specification](docs/LINTER_SPEC.md) for all documentation and code contributions.
