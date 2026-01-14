"""File operations for eval package generation."""

import zipfile
import yaml
from datetime import datetime
from typing import TYPE_CHECKING, List, Set, Dict, NamedTuple

if TYPE_CHECKING:
    from lib.services.eval_generator.generator import EvalPackageData


class AgentConfig(NamedTuple):
    """Configuration for agent evaluation datasets."""

    key: str
    yaml_filename: str
    dataset_name_template: str
    description: str
    needs_supporting_files: bool
    test_config: Dict


# Agent configurations - single source of truth
AGENT_CONFIGS = {
    "citations": AgentConfig(
        key="citations",
        yaml_filename="citation_detector.yaml",
        dataset_name_template="Citation Detector Dataset ({test_name})",
        description="Citation detection test cases",
        needs_supporting_files=False,
        test_config={
            "strict_fields": {
                "citations": {
                    "__all__": [
                        "text",
                        "needs_bibliography",
                        "associated_bibliography",
                        "index_of_associated_bibliography",
                    ]
                }
            }
        },
    ),
    "claims": AgentConfig(
        key="claims",
        yaml_filename="claim_extractor.yaml",
        dataset_name_template="Claim Extractor Dataset ({test_name})",
        description="Claim extraction test cases",
        needs_supporting_files=False,
        test_config={
            "strict_fields": {"claims": {"__all__": ["text"]}},
            "llm_fields": {"claims": {"__all__": ["claim"]}},
        },
    ),
    "substantiation": AgentConfig(
        key="substantiation",
        yaml_filename="claim_verifier.yaml",
        dataset_name_template="Claim Verifier Dataset ({test_name})",
        description="Claim verifier test cases",
        needs_supporting_files=True,
        test_config={
            "strict_fields": ["is_substantiated", "severity"],
            "llm_fields": ["rationale", "feedback"],
        },
    ),
    "references": AgentConfig(
        key="references",
        yaml_filename="reference_extractor.yaml",
        dataset_name_template="Reference Extractor Dataset ({test_name})",
        description="Reference extraction test cases",
        needs_supporting_files=True,
        test_config={
            "strict_fields": {
                "references": {
                    "__all__": [
                        "text",
                        "has_associated_supporting_document",
                        "index_of_associated_supporting_document",
                        "name_of_associated_supporting_document",
                    ]
                }
            }
        },
    ),
}


class DataFileManager:
    """Manages data files within the eval package."""

    @classmethod
    def get_required_files(cls, selected_agents: List[str]) -> Set[str]:
        """Determine which files are required based on selected agents."""
        required_files = {"main_document"}  # Always needed

        for agent in selected_agents:
            config = AGENT_CONFIGS.get(agent)
            if config and config.needs_supporting_files:
                required_files.add("supporting_documents")
                break

        return required_files

    @classmethod
    def save_data_files(
        cls, zip_file: zipfile.ZipFile, data: "EvalPackageData", test_name: str
    ):
        """Save all document files to the zip."""
        cls._save_main_document(zip_file, data, test_name)
        cls._save_supporting_documents(zip_file, data, test_name)

    @classmethod
    def save_required_data_files(
        cls,
        zip_file: zipfile.ZipFile,
        data: "EvalPackageData",
        test_name: str,
        selected_agents: List[str],
    ):
        """Save only the required data files based on agent needs."""
        required_files = cls.get_required_files(selected_agents)

        cls._save_main_document(zip_file, data, test_name)

        if "supporting_documents" in required_files:
            cls._save_supporting_documents(zip_file, data, test_name)

    @classmethod
    def _save_main_document(
        cls, zip_file: zipfile.ZipFile, data: "EvalPackageData", test_name: str
    ):
        """Save the main document."""
        main_file = data.file
        zip_file.writestr(
            f"data/{test_name}/main_document.md",
            main_file.markdown if main_file else "",
        )

    @classmethod
    def _save_supporting_documents(
        cls, zip_file: zipfile.ZipFile, data: "EvalPackageData", test_name: str
    ):
        """Save all supporting documents."""
        supporting_files = data.supporting_files
        for i, support_doc in enumerate(supporting_files):
            zip_file.writestr(
                f"data/{test_name}/supporting_{i+1}.md", support_doc.markdown
            )


class YamlFileWriter:
    """Handles YAML file creation and writing."""

    @classmethod
    def write_dataset(
        cls,
        zip_file: zipfile.ZipFile,
        filename: str,
        dataset_name: str,
        items: List[Dict],
        description: str,
        test_config: Dict = None,
    ):
        """Generic method to write YAML dataset files."""
        if not items:
            return

        dataset_dict = {
            "name": dataset_name,
            "description": f"Generated from analysis: {description}",
        }

        if test_config:
            dataset_dict["test_config"] = test_config

        dataset_dict["items"] = items

        yaml_content = yaml.dump(
            {"dataset": dataset_dict}, default_flow_style=False, sort_keys=False
        )

        zip_file.writestr(filename, yaml_content)

    @classmethod
    def write_selective_yaml_files(
        cls,
        zip_file: zipfile.ZipFile,
        agent_test_cases: Dict[str, List[Dict]],
        test_name: str,
        description: str,
        selected_agents: List[str],
    ):
        """Write YAML files only for selected agents."""
        for agent_key in selected_agents:
            config = AGENT_CONFIGS.get(agent_key)
            test_cases = agent_test_cases.get(agent_key, [])

            if config and test_cases:
                dataset_name = config.dataset_name_template.format(test_name=test_name)
                cls.write_dataset(
                    zip_file=zip_file,
                    filename=config.yaml_filename,
                    dataset_name=dataset_name,
                    items=test_cases,
                    description=description,
                    test_config=config.test_config,
                )


class ReadmeGenerator:
    """Generates README files for eval packages."""

    @classmethod
    def add_readme(cls, zip_file: zipfile.ZipFile, test_name: str, description: str):
        """Add README with setup instructions for all agents."""
        all_agents = list(AGENT_CONFIGS.keys())
        readme_content = cls._generate_readme_content(
            test_name=test_name,
            description=description,
            title_prefix="Generated Evaluation Test",
            selected_agents=all_agents,
        )
        zip_file.writestr("README.md", readme_content)

    @classmethod
    def add_chunk_readme(
        cls,
        zip_file: zipfile.ZipFile,
        test_name: str,
        description: str,
        chunk_index: int,
        selected_agents: List[str],
    ):
        """Add README with chunk-specific information."""
        required_files = DataFileManager.get_required_files(selected_agents)

        extra_sections = f"""## Source
Generated from chunk {chunk_index} analysis results

## Files Included
- Main document: ✅ Always included
- Supporting documents: {'✅ Included' if 'supporting_documents' in required_files else '❌ Not needed for selected agents'}

## Optimization
This package only includes files required by the selected agents:
- Claims/Citations: Only need main document
- References/Substantiation: Need main + supporting documents
"""

        readme_content = cls._generate_readme_content(
            test_name=test_name,
            description=description,
            title_prefix="Generated Chunk Evaluation Test",
            selected_agents=selected_agents,
            extra_sections=extra_sections,
        )
        zip_file.writestr("README.md", readme_content)

    @classmethod
    def _generate_readme_content(
        cls,
        test_name: str,
        description: str,
        title_prefix: str,
        selected_agents: List[str],
        extra_sections: str = "",
    ) -> str:
        """Generate README content with common structure."""
        # Get YAML files for selected agents
        yaml_files = []
        for agent in selected_agents:
            config = AGENT_CONFIGS.get(agent)
            if config:
                yaml_files.append(f"`{config.yaml_filename}` - {config.description}")

        files_list = "\n".join(f"- {file_desc}" for file_desc in yaml_files)
        agents_list = ", ".join(selected_agents)

        return f"""# {title_prefix}: {test_name}

## Description
{description}
{extra_sections}
## Agents Tested
{agents_list}

## Generated Files
{files_list}
- `data/{test_name}/` - Test data files

## Usage
1. Copy the YAML files to `tests/datasets/`
2. Copy the `data/` folder to `tests/`
3. Run tests with pytest

## Generated on
{datetime.now().isoformat()}
"""
