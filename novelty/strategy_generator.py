"""
Strategy generation for novel task problem-solving.

Creates custom problem-solving strategies for tasks that don't fit existing patterns.
Includes task analysis, naming detection, scaffold generation, and convention application.
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from datetime import datetime


@dataclass
class StrategyComponent:
    """Component of problem-solving strategy."""

    component_type: str  # analysis, naming, scaffold, conventions, index
    content: str
    description: str


@dataclass
class ProblemSolvingStrategy:
    """Complete problem-solving strategy for novel task."""

    task_id: str
    task_description: str
    strategy_name: str
    created_at: str
    components: List[StrategyComponent]
    estimated_implementation_hours: float
    estimated_lines_of_code: int
    risk_level: str  # low, medium, high


class StrategyGenerator:
    """
    Generates custom problem-solving strategies for novel tasks.

    Creates actionable strategies that include:
    - Task analysis and decomposition
    - Naming convention detection
    - Code scaffold generation
    - Convention application
    - File structure index
    """

    def __init__(self):
        """Initialize StrategyGenerator."""
        self.generated_strategies = {}
        self.strategy_templates = self._load_templates()

    def generate_strategy(
        self,
        task_id: str,
        task_description: str,
        task_structure: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> ProblemSolvingStrategy:
        """
        Generate complete problem-solving strategy.

        Args:
            task_id: Unique task identifier
            task_description: Description of the task
            task_structure: Detected code structure
            context: Optional context information

        Returns:
            ProblemSolvingStrategy with all components
        """
        components = []

        # 1. Task Analysis Component
        analysis_component = self._generate_task_analysis(task_description, task_structure)
        components.append(analysis_component)

        # 2. Naming Detection Component
        naming_component = self._detect_naming_conventions(task_description, context)
        components.append(naming_component)

        # 3. Scaffold Generation Component
        scaffold_component = self._generate_code_scaffold(task_description, task_structure)
        components.append(scaffold_component)

        # 4. Conventions Application Component
        conventions_component = self._apply_conventions(context)
        components.append(conventions_component)

        # 5. File Index Component
        index_component = self._generate_file_index(scaffold_component.content)
        components.append(index_component)

        strategy = ProblemSolvingStrategy(
            task_id=task_id,
            task_description=task_description,
            strategy_name=f"Custom Strategy for {task_id}",
            created_at=datetime.utcnow().isoformat() + "Z",
            components=components,
            estimated_implementation_hours=self._estimate_implementation_time(scaffold_component.content),
            estimated_lines_of_code=self._count_estimated_lines(scaffold_component.content),
            risk_level=self._assess_risk_level(task_description),
        )

        self.generated_strategies[task_id] = strategy
        return strategy

    def _generate_task_analysis(
        self,
        task_description: str,
        task_structure: str,
    ) -> StrategyComponent:
        """
        Generate task analysis component.

        Args:
            task_description: Task description
            task_structure: Code structure

        Returns:
            Task analysis component
        """
        analysis = f"""Task Analysis for Novel Problem

Description:
{task_description}

Detected Structure:
{task_structure}

Approach:
1. Break down task into smaller sub-tasks
2. Identify core requirements
3. Design modular solution
4. Plan implementation phases
5. Define success criteria

Key Considerations:
- This task doesn't match existing patterns
- Custom solution required
- Requires careful architecture design
- Plan for testing at each phase
"""

        return StrategyComponent(
            component_type="analysis",
            content=analysis,
            description="Task analysis and decomposition"
        )

    def _detect_naming_conventions(
        self,
        task_description: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> StrategyComponent:
        """
        Detect naming conventions from task context.

        Args:
            task_description: Task description
            context: Optional context

        Returns:
            Naming conventions component
        """
        conventions = """Naming Conventions

Variables and Methods:
- Use camelCase for variables: myVariable, getUserId()
- Use descriptive names: user, not u; getUserProfile, not get()
- Avoid single letters except in loops: for i in range(10)

Classes and Types:
- Use PascalCase: UserProfile, DatabaseConnection
- Use nouns for classes: User, not GetUser
- Use adjectives for boolean: isActive, hasPermission

Constants:
- Use UPPER_CASE: MAX_RETRIES, DEFAULT_TIMEOUT
- Group related constants together

File and Directory:
- Use lowercase with underscores: user_profile.py
- Use plural for collections: models/, services/
- One class per file convention: user.py contains UserProfile class
"""

        return StrategyComponent(
            component_type="naming",
            content=conventions,
            description="Naming convention guidelines"
        )

    def _generate_code_scaffold(
        self,
        task_description: str,
        task_structure: str,
    ) -> StrategyComponent:
        """
        Generate code scaffold for the task.

        Args:
            task_description: Task description
            task_structure: Code structure

        Returns:
            Code scaffold component
        """
        scaffold = f"""# Generated Code Scaffold

"""

        # Detect task type and generate appropriate scaffold
        if "database" in task_description.lower():
            scaffold += self._scaffold_database_task()
        elif "api" in task_description.lower():
            scaffold += self._scaffold_api_task()
        elif "test" in task_description.lower():
            scaffold += self._scaffold_testing_task()
        else:
            scaffold += self._scaffold_generic_task()

        return StrategyComponent(
            component_type="scaffold",
            content=scaffold,
            description="Generated code scaffold"
        )

    def _scaffold_database_task(self) -> str:
        """Generate scaffold for database-related task."""
        return """## Database Task Scaffold

class DatabaseConnection:
    def __init__(self, connection_string):
        self.connection = None
        # Initialize connection

    def connect(self):
        # Implement connection logic
        pass

    def execute(self, query):
        # Execute query safely
        pass

    def close(self):
        # Cleanup connection
        pass

class DatabaseModel:
    # Base class for database entities
    pass

class UserModel(DatabaseModel):
    # Specific implementation
    pass
"""

    def _scaffold_api_task(self) -> str:
        """Generate scaffold for API-related task."""
        return """## API Task Scaffold

class APIEndpoint:
    def __init__(self, base_url):
        self.base_url = base_url

    @method.get('/')
    def get_resources(self):
        # List all resources
        return []

    @method.post('/')
    def create_resource(self, data):
        # Create new resource
        return None

    @method.get('/{id}')
    def get_resource(self, id):
        # Get specific resource
        return None

    @method.put('/{id}')
    def update_resource(self, id, data):
        # Update resource
        return None

    @method.delete('/{id}')
    def delete_resource(self, id):
        # Delete resource
        pass
"""

    def _scaffold_testing_task(self) -> str:
        """Generate scaffold for testing-related task."""
        return """## Testing Task Scaffold

class TestNovelFeature:
    def setup_method(self):
        # Setup test fixtures
        pass

    def test_basic_functionality(self):
        # Test primary use case
        assert True

    def test_error_handling(self):
        # Test error scenarios
        assert True

    def test_edge_cases(self):
        # Test boundary conditions
        assert True

    def teardown_method(self):
        # Cleanup after tests
        pass
"""

    def _scaffold_generic_task(self) -> str:
        """Generate generic code scaffold."""
        return """## Generic Task Scaffold

class NovelTask:
    def __init__(self, config=None):
        self.config = config or {}

    def execute(self):
        # Main task execution
        result = self._analyze_requirements()
        processed = self._process_data(result)
        return self._finalize(processed)

    def _analyze_requirements(self):
        # Step 1: Analyze requirements
        return None

    def _process_data(self, data):
        # Step 2: Process data
        return None

    def _finalize(self, data):
        # Step 3: Finalize results
        return data

# Main execution
if __name__ == "__main__":
    task = NovelTask()
    result = task.execute()
"""

    def _apply_conventions(self, context: Optional[Dict[str, Any]]) -> StrategyComponent:
        """
        Apply code conventions component.

        Args:
            context: Optional context

        Returns:
            Conventions component
        """
        conventions = """Code Conventions and Best Practices

Code Style:
- Indentation: 4 spaces (not tabs)
- Line length: 100 characters maximum
- Blank lines: 2 between top-level definitions, 1 between methods

Documentation:
- Add docstrings to all functions and classes
- Use Google-style docstrings
- Document parameters and return types

Error Handling:
- Use specific exception types
- Never silently ignore exceptions
- Log errors with context

Testing:
- Write tests as you code (TDD approach)
- Aim for >80% code coverage
- Test both happy path and error cases

Version Control:
- Commit frequently with clear messages
- One feature per commit
- Reference task ID in commit messages
"""

        return StrategyComponent(
            component_type="conventions",
            content=conventions,
            description="Code conventions and best practices"
        )

    def _generate_file_index(self, scaffold: str) -> StrategyComponent:
        """
        Generate file structure index component.

        Args:
            scaffold: Generated scaffold content

        Returns:
            File index component
        """
        # Count estimated files from scaffold
        estimated_files = scaffold.count("class ") + 1
        estimated_lines = len(scaffold.split("\n"))

        index = f"""Generated File Structure

Files to Create:
- src/novel_task.py (Core implementation, ~{estimated_lines} lines)
- src/models.py (Data models)
- src/utils.py (Utility functions)
- tests/test_novel_task.py (Unit tests)
- README.md (Documentation)

Directory Structure:
src/
├── novel_task.py
├── models.py
├── utils.py
└── __init__.py

tests/
├── test_novel_task.py
└── __init__.py

Total Estimated Implementation:
- Files: {estimated_files}
- Lines of Code: {estimated_lines}
- Time Estimate: 4-8 hours
- Complexity: Medium
"""

        return StrategyComponent(
            component_type="index",
            content=index,
            description="Generated file structure and index"
        )

    def _estimate_implementation_time(self, scaffold: str) -> float:
        """Estimate implementation time in hours."""
        lines = len(scaffold.split("\n"))
        # Rough estimate: 20 lines per hour
        return max(2.0, lines / 20.0)

    def _count_estimated_lines(self, scaffold: str) -> int:
        """Count estimated lines of code."""
        return len(scaffold.split("\n"))

    def _assess_risk_level(self, task_description: str) -> str:
        """Assess task risk level."""
        keywords_high = ["critical", "mission", "security", "payment", "authentication"]
        keywords_med = ["important", "complex", "integration", "api"]

        desc_lower = task_description.lower()

        if any(kw in desc_lower for kw in keywords_high):
            return "high"
        elif any(kw in desc_lower for kw in keywords_med):
            return "medium"
        else:
            return "low"

    def _load_templates(self) -> Dict[str, str]:
        """Load strategy templates."""
        return {
            "database": "Database task template",
            "api": "API task template",
            "testing": "Testing task template",
        }

    def format_strategy(self, strategy: ProblemSolvingStrategy) -> str:
        """
        Format strategy for human-readable display.

        Args:
            strategy: Generated strategy

        Returns:
            Formatted strategy text
        """
        lines = [
            "=" * 80,
            f"Problem-Solving Strategy for Task: {strategy.task_id}",
            "=" * 80,
            "",
            f"Task: {strategy.task_description}",
            f"Created: {strategy.created_at}",
            f"Risk Level: {strategy.risk_level}",
            f"Estimated Time: {strategy.estimated_implementation_hours:.1f} hours",
            f"Estimated Lines: {strategy.estimated_lines_of_code}",
            "",
        ]

        for component in strategy.components:
            lines.append("=" * 80)
            lines.append(f"{component.component_type.upper()}: {component.description}")
            lines.append("=" * 80)
            lines.append(component.content)
            lines.append("")

        return "\n".join(lines)
