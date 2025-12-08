#!/usr/bin/env python3
"""Query Executor Orchestrator.

This script orchestrates the complete workflow:
1. Create virtual environment from user query
2. Generate Python code to fulfill the query
3. Save code to file
4. Execute the code
"""

import asyncio
import logging
import sys
from pathlib import Path
from typing import Optional

# Add project root to Python path so we can import lib modules
# This allows the script to be run from anywhere
try:
    _project_root = Path(__file__).parent.parent.resolve()
except NameError:
    # Fallback if __file__ is not available (e.g., when run with exec)
    _project_root = Path.cwd().resolve()
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from langchain.chat_models import init_chat_model
from langchain_core.prompts import PromptTemplate
from langchain_core.runnables import RunnableConfig

from lib.config.llm_models import gpt_5_model
from lib.workflows.claim_substantiation.context import ContextSchema

# Import existing components
# Since we're running from project root, we can import directly
from statistical_analysis_ver2.create_venv import VenvCreator
from statistical_analysis_ver2.execute_generated_code import CodeExecutor

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


class SimplePlanGenerator:
    """Simple plan generator that uses LLM to create execution plans from user queries."""

    def __init__(self, context: ContextSchema):
        """Initialize plan generator.

        Args:
            context: Context schema with API keys
        """
        self.context = context
        self.model = gpt_5_model
        self.temperature = 0.3
        self._llm = None

    @property
    def llm(self):
        """Lazy initialization of LLM."""
        if self._llm is None:
            init_kwargs = {
                "model": self.model.model_name,
                "temperature": self.temperature,
                "timeout": 300,
            }

            # For OpenAI models: use context API key if provided
            if (
                self.model.provider in ["openai", "azure_openai"]
                and self.context.openai_api_key
            ):
                init_kwargs["api_key"] = self.context.openai_api_key

            self._llm = init_chat_model(**init_kwargs)
        return self._llm

    async def generate_plan(
        self, user_query: str, config: RunnableConfig = None
    ) -> str:
        """Generate an execution plan from user query.

        Args:
            user_query: The user's query/request
            config: Optional runnable config

        Returns:
            Generated plan as string
        """
        logger.info(f"Generating plan for query: {user_query[:50]}...")

        # Create prompt
        prompt_result = _plan_generator_prompt.invoke({"user_query": user_query})

        # Convert to messages format for LangChain
        messages = [{"role": "user", "content": prompt_result.text}]

        # Generate plan
        response = await self.llm.ainvoke(messages, config=config)

        # Extract plan from response
        if hasattr(response, "content"):
            plan = response.content
        elif hasattr(response, "text"):
            plan = response.text
        else:
            plan = str(response)

        logger.info("Plan generation completed")
        return plan


_plan_generator_prompt = PromptTemplate.from_template(
    """
# Role
You are an expert software engineer and data analyst who creates detailed execution plans for code implementation.

# Task
Given a user query, create a comprehensive plan that outlines:
1. What the code needs to accomplish
2. The approach/algorithm to use
3. Required libraries and dependencies
4. Key steps in the implementation
5. Expected outputs and results
6. Any edge cases or considerations

# Requirements
- Be specific and actionable
- Break down the task into clear steps
- Identify the appropriate algorithms, data structures, or analysis methods
- List required Python libraries
- Describe the expected output format
- Note any potential challenges or edge cases

# User Query
{user_query}

# Output
Provide a clear, structured plan in plain text (not code). Use bullet points or numbered lists for clarity.
The plan should be comprehensive enough to guide code generation but concise enough to be readable.
"""
)


class SimpleCodeGenerator:
    """Simple code generator that uses LLM to generate Python code from user queries."""

    def __init__(self, context: ContextSchema):
        """Initialize code generator.

        Args:
            context: Context schema with API keys
        """
        self.context = context
        self.model = gpt_5_model
        self.temperature = 0.2
        self._llm = None

    @property
    def llm(self):
        """Lazy initialization of LLM."""
        if self._llm is None:
            init_kwargs = {
                "model": self.model.model_name,
                "temperature": self.temperature,
                "timeout": 300,
            }

            # For OpenAI models: use context API key if provided
            if (
                self.model.provider in ["openai", "azure_openai"]
                and self.context.openai_api_key
            ):
                init_kwargs["api_key"] = self.context.openai_api_key

            self._llm = init_chat_model(**init_kwargs)
        return self._llm

    async def generate_code(
        self, user_query: str, plan: Optional[str] = None, config: RunnableConfig = None
    ) -> str:
        """Generate Python code from user query and optional plan.

        Args:
            user_query: The user's query/request
            plan: Optional execution plan to guide code generation
            config: Optional runnable config

        Returns:
            Generated Python code as string
        """
        logger.info(f"Generating code for query: {user_query[:50]}...")
        if plan:
            logger.info("Using execution plan to guide code generation")

        # Create prompt with plan if available
        if plan:
            execution_plan_section = f"""# Execution Plan
Follow this execution plan when generating the code:
{plan}

The code you generate should implement the approach, use the libraries, and follow the steps outlined in the plan above.
"""
        else:
            execution_plan_section = ""

        prompt_kwargs = {
            "user_query": user_query,
            "execution_plan_section": execution_plan_section,
        }

        prompt_result = _code_generator_prompt.invoke(prompt_kwargs)

        # Convert to messages format for LangChain
        messages = [{"role": "user", "content": prompt_result.text}]

        # Generate code
        response = await self.llm.ainvoke(messages, config=config)

        # Extract code from response
        if hasattr(response, "content"):
            code = response.content
        elif hasattr(response, "text"):
            code = response.text
        else:
            code = str(response)

        # Try to extract code block if wrapped in markdown
        if "```python" in code:
            start = code.find("```python") + 9
            end = code.find("```", start)
            code = code[start:end].strip()
        elif "```" in code:
            start = code.find("```") + 3
            end = code.find("```", start)
            code = code[start:end].strip()

        logger.info("Code generation completed")
        return code


_code_generator_prompt = PromptTemplate.from_template(
    """
# Role
You are an expert Python programmer who writes clean, well-documented, executable code.

# Task
Generate Python code that fulfills the user's query. The code should be complete, self-contained, and executable.

{execution_plan_section}

# Requirements
1. Write complete, runnable Python code
2. Include necessary imports at the top
3. Add clear comments explaining the code
4. Print results in a clear, readable format
5. Handle edge cases and errors appropriately
6. Make the code modular and readable

# Code Style
- Use standard Python libraries when possible
- For data manipulation: use pandas, numpy
- For algorithms: implement clean, efficient solutions
- For visualizations: use matplotlib, seaborn if needed
- Include docstrings for functions
- Add comments for complex logic
- IMPORTANT: Do NOT include any package installation code (no subprocess calls to pip/uv).
  Simply import packages directly - missing packages will be installed automatically by the execution environment.

# Available Libraries
Common libraries are available: pandas, numpy, scipy, matplotlib, seaborn, scikit-learn, etc.
If you need additional libraries, import them directly - they will be installed automatically if missing.

# User Query
{user_query}

# Output
Generate complete, runnable Python code. Do not include markdown formatting, just the Python code.
The code should be self-contained and executable. Include a main() function or direct execution code.
"""
)


class QueryExecutor:
    """Orchestrates the complete query execution workflow."""

    def __init__(
        self,
        context: Optional[ContextSchema] = None,
        base_dir: Path = Path("query_venvs"),
    ):
        """Initialize query executor.

        Args:
            context: Optional context schema with API keys. If None, creates default context.
            base_dir: Base directory where venvs will be created
        """
        self.context = context or ContextSchema()
        self.venv_creator = VenvCreator(base_dir=base_dir)
        self.plan_generator = SimplePlanGenerator(self.context)
        self.code_generator = SimpleCodeGenerator(self.context)

    async def execute_query(self, user_query: str) -> dict:
        """Execute a complete workflow for a user query.

        Args:
            user_query: The user's query/request

        Returns:
            Dictionary with execution results:
            - success: bool
            - venv_dir: Path to venv directory
            - plan_file: Path to generated plan file
            - code_file: Path to generated code file
            - exit_code: Exit code from execution
            - stdout: Standard output (if available)
            - stderr: Standard error (if available)
        """
        result = {
            "success": False,
            "venv_dir": None,
            "plan_file": None,
            "code_file": None,
            "exit_code": None,
            "stdout": None,
            "stderr": None,
        }

        try:
            # Step 1: Create virtual environment
            print("\n" + "=" * 60)
            print("Step 1: Creating virtual environment...")
            print("=" * 60)
            venv_dir = await self.venv_creator.create_venv(user_query)

            if not venv_dir:
                print("❌ Failed to create virtual environment")
                return result

            result["venv_dir"] = venv_dir
            print(f"✅ Virtual environment created: {venv_dir}")

            # Step 2: Generate execution plan
            print("\n" + "=" * 60)
            print("Step 2: Generating execution plan...")
            print("=" * 60)
            plan = await self.plan_generator.generate_plan(user_query)

            if not plan:
                print("❌ Failed to generate plan")
                return result

            print("✅ Plan generated successfully")
            print("\n" + "-" * 60)
            print("EXECUTION PLAN")
            print("-" * 60)
            print(plan)
            print("-" * 60)

            # Save plan to file
            plan_file = venv_dir / "execution_plan.txt"
            plan_file.write_text(plan)
            result["plan_file"] = plan_file
            print(f"\n📄 Plan saved to: {plan_file}")

            # Step 3: Generate code
            print("\n" + "=" * 60)
            print("Step 3: Generating code...")
            print("=" * 60)
            code = await self.code_generator.generate_code(user_query, plan=plan)

            if not code:
                print("❌ Failed to generate code")
                return result

            print("✅ Code generated successfully")
            print(f"\nGenerated code preview (first 600 chars):\n{code[:600]}...")

            # Step 4: Save code to file
            print("\n" + "=" * 60)
            print("Step 4: Saving code to file...")
            print("=" * 60)
            code_file = venv_dir / "generated_code.py"
            code_file.write_text(code)
            result["code_file"] = code_file
            print(f"✅ Code saved to: {code_file}")

            # Step 5: Execute code
            print("\n" + "=" * 60)
            print("Step 5: Executing code...")
            print("=" * 60)
            executor = CodeExecutor(venv_dir=venv_dir)
            exit_code = await executor.execute_file(code_file, working_dir=venv_dir)
            result["exit_code"] = exit_code
            result["success"] = exit_code == 0

            if result["success"]:
                print("\n" + "=" * 60)
                print("✅ Workflow completed successfully!")
                print("=" * 60)
            else:
                print("\n" + "=" * 60)
                print("❌ Workflow completed with errors")
                print("=" * 60)

            return result

        except Exception as e:
            logger.error(f"Error in execute_query: {e}", exc_info=True)
            print(f"\n❌ Error: {e}")
            return result


async def main():
    """Main entry point."""
    # Get user query from command line or prompt
    if len(sys.argv) > 1:
        user_query = " ".join(sys.argv[1:])
    else:
        user_query = input("Enter your query: ").strip()
        if not user_query:
            print("Error: Query cannot be empty")
            sys.exit(1)

    print(f"\n📝 User Query: {user_query}\n")

    # Create query executor
    executor = QueryExecutor()

    # Execute query
    result = await executor.execute_query(user_query)

    # Print summary
    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)
    print(f"Success: {result['success']}")
    if result["venv_dir"]:
        print(f"Venv: {result['venv_dir']}")
    if result["plan_file"]:
        print(f"Plan file: {result['plan_file']}")
    if result["code_file"]:
        print(f"Code file: {result['code_file']}")
    if result["exit_code"] is not None:
        print(f"Exit code: {result['exit_code']}")

    sys.exit(0 if result["success"] else 1)


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
