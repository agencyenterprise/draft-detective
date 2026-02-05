"""Field-by-field comparison with intelligent matching for array fields."""

from pydantic import BaseModel

from lib.models.array_matchers import ArrayMatcher
from lib.models.comparison_models import ComparisonExample, FieldComparison
from lib.models.comparison_utils import build_rationale, serialize_value, to_dict


class FieldComparator:
    """Handles field-by-field comparison with multiple matching strategies.

    This comparator intelligently matches array items using content-based and fuzzy
    matching, making it ideal for comparing non-deterministic LLM outputs.

    Usage:
        >>> # Compare scalar fields
        >>> comparator = FieldComparator({'field1', 'field2'})
        >>> results = comparator.compare_fields(expected, actual)

        >>> # Compare array fields
        >>> comparator = FieldComparator({
        ...     'claims': ['text', 'category']
        ... })
        >>> results = comparator.compare_fields(expected, actual)

        >>> # With custom thresholds
        >>> comparator = FieldComparator(
        ...     field_config={'claims': ['text']},
        ...     max_examples=10,
        ...     fuzzy_threshold=0.7
        ... )

    Matching Strategies:
        1. by_field: Match array items by field value (e.g., claim text)
        2. by_index: Positional matching when array lengths match
        3. best_effort: Fuzzy matching with similarity threshold
    """

    def __init__(
        self,
        field_config: dict | set,
        ignore_config: dict | set | None = None,
        max_examples: int = 5,
        fuzzy_threshold: float = 0.6,
        good_match_threshold: float = 0.8,
    ):
        """Initialize field comparator with configuration.

        Args:
            field_config: Field configuration (set of field names or dict with nested config)
            ignore_config: Fields to ignore during comparison
            max_examples: Maximum number of mismatch examples to collect
            fuzzy_threshold: Minimum similarity score for fuzzy matches (0.0-1.0)
            good_match_threshold: Minimum ratio for successful matching strategy
        """
        self.field_config = field_config
        self.ignore_config = ignore_config or set()
        self.max_examples = max_examples
        self.matcher = ArrayMatcher(
            fuzzy_threshold=fuzzy_threshold, good_match_threshold=good_match_threshold
        )

    def compare_fields(
        self,
        expected: BaseModel,
        result: BaseModel,
        comparison_type: str = "strict",  # "strict" | "llm"
    ) -> list[FieldComparison]:
        """Compare all configured fields and return detailed results.

        Args:
            expected: Expected output model
            result: Actual output model
            comparison_type: Type of comparison ("strict" or "llm")

        Returns:
            List of FieldComparison results with diagnostics

        Raises:
            ValueError: If a configured field doesn't exist on the models
        """
        comparisons = []

        if isinstance(self.field_config, set):
            # Top-level scalar fields
            for field_name in self.field_config:
                self._validate_field_exists(expected, result, field_name)
                comparison = self._compare_scalar_field(
                    expected, result, field_name, comparison_type
                )
                comparisons.append(comparison)

        elif isinstance(self.field_config, dict):
            # Nested fields (arrays/objects)
            for parent_field, child_config in self.field_config.items():
                self._validate_field_exists(expected, result, parent_field)

                if isinstance(child_config, dict) and "__all__" in child_config:
                    # Array with field specs
                    array_comparisons = self._compare_array_fields(
                        expected,
                        result,
                        parent_field,
                        child_config["__all__"],
                        comparison_type,
                    )
                    comparisons.extend(array_comparisons)
                elif isinstance(child_config, list):
                    # Direct list of fields
                    array_comparisons = self._compare_array_fields(
                        expected, result, parent_field, child_config, comparison_type
                    )
                    comparisons.extend(array_comparisons)

        return comparisons

    def _validate_field_exists(
        self, expected: BaseModel, result: BaseModel, field_name: str
    ) -> None:
        """Validate that a field exists on both models.

        Args:
            expected: Expected output model
            result: Actual output model
            field_name: Name of the field to validate

        Raises:
            ValueError: If field doesn't exist on either model
        """
        if not hasattr(expected, field_name):
            raise ValueError(
                f"Field '{field_name}' not found in expected output model "
                f"({type(expected).__name__})"
            )
        if not hasattr(result, field_name):
            raise ValueError(
                f"Field '{field_name}' not found in actual output model "
                f"({type(result).__name__})"
            )

    def _compare_scalar_field(
        self,
        expected: BaseModel,
        result: BaseModel,
        field_name: str,
        comparison_type: str,
    ) -> FieldComparison:
        """Compare a single scalar field.

        Args:
            expected: Expected output model
            result: Actual output model
            field_name: Name of the field to compare
            comparison_type: Type of comparison

        Returns:
            FieldComparison result
        """
        exp_val = getattr(expected, field_name, None)
        res_val = getattr(result, field_name, None)

        matched = self.matcher._values_match(exp_val, res_val)

        examples = []
        if not matched:
            examples.append(
                ComparisonExample(
                    instance_identifier=field_name,
                    expected_value=serialize_value(exp_val),
                    actual_value=serialize_value(res_val),
                    matched=False,
                    note="Direct field comparison",
                )
            )

        return FieldComparison(
            field_path=field_name,
            comparison_type=comparison_type,
            total_instances=1,
            passed_instances=1 if matched else 0,
            failed_instances=0 if matched else 1,
            passed=matched,
            rationale=build_rationale(field_name, matched, 1, 1 if matched else 0),
            examples=examples,
        )

    def _parse_array_field_config(
        self, field_config: list[str] | dict
    ) -> tuple[list[str], dict]:
        """Separate simple field names from nested array configurations.

        Args:
            field_config: Either a list of field names or a dict with nested configs

        Returns:
            Tuple of (simple_fields, nested_configs) where:
            - simple_fields: List of field names for direct comparison
            - nested_configs: Dict of {field_name: nested_config} for nested arrays
        """
        if isinstance(field_config, list):
            # Simple list of field names
            return field_config, {}

        if isinstance(field_config, dict):
            simple_fields = []
            nested_configs = {}

            for key, value in field_config.items():
                if isinstance(value, dict) and "__all__" in value:
                    # Nested array config: {field: {__all__: [...]}}
                    nested_configs[key] = value["__all__"]
                elif isinstance(value, list):
                    # Could be nested array with direct field list: {field: [...]}
                    # Treat as nested array config
                    nested_configs[key] = value
                else:
                    # Simple field name as key (unusual but handle it)
                    simple_fields.append(key)

            return simple_fields, nested_configs

        return [], {}

    def _compare_array_fields(
        self,
        expected: BaseModel,
        result: BaseModel,
        array_field: str,
        field_config: list[str] | dict,
        comparison_type: str,
        parent_path: str = "",
    ) -> list[FieldComparison]:
        """Compare fields across array items with intelligent matching.

        Supports nested array configurations for deeply nested structures.

        Args:
            expected: Expected output model
            result: Actual output model
            array_field: Name of the array field
            field_config: Field configuration - either list of field names or dict
                with nested configs (e.g., {'citations': {'__all__': [...]}})
            comparison_type: Type of comparison ("strict" or "llm")
            parent_path: Dot-separated path to parent (for nested comparisons)

        Returns:
            List of FieldComparison results for each field
        """
        exp_array = getattr(expected, array_field, [])
        res_array = getattr(result, array_field, [])

        # Convert to dicts if needed
        exp_items = [to_dict(item) for item in exp_array]
        res_items = [to_dict(item) for item in res_array]

        # Parse config to separate simple fields from nested array configs
        simple_fields, nested_configs = self._parse_array_field_config(field_config)

        # Try multiple matching strategies using simple fields
        matches, strategy = self.matcher.match_items(
            exp_items, res_items, simple_fields
        )

        # Build current path for field comparisons
        current_path = f"{parent_path}.{array_field}" if parent_path else array_field

        # Compare each simple field across matched items
        comparisons = []
        for field_name in simple_fields:
            comparison = self._compare_field_across_matches(
                matches, field_name, current_path, comparison_type, strategy
            )
            comparisons.append(comparison)

        # Recursively compare nested arrays
        for nested_field, nested_config in nested_configs.items():
            nested_comparisons = self._compare_nested_arrays(
                matches, nested_field, nested_config, current_path, comparison_type
            )
            comparisons.extend(nested_comparisons)

        return comparisons

    def _compare_field_across_matches(
        self,
        matches: list[tuple[dict | None, dict | None, str]],
        field_name: str,
        parent_path: str,
        comparison_type: str,
        matching_strategy: str,
    ) -> FieldComparison:
        """Compare a specific field across all matched pairs.

        Args:
            matches: List of (expected, actual, match_id) tuples
            field_name: Name of the field to compare
            parent_path: Dot-separated path to the parent (e.g., "results.citations")
            comparison_type: Type of comparison
            matching_strategy: Strategy used for matching

        Returns:
            FieldComparison result for this field
        """
        passed = 0
        failed = 0
        examples = []

        for exp_item, res_item, match_id in matches:
            if exp_item is None:
                # Extra item in result
                failed += 1
                if len(examples) < self.max_examples:
                    examples.append(
                        ComparisonExample(
                            instance_identifier=match_id,
                            expected_value=None,
                            actual_value=serialize_value(
                                res_item.get(field_name) if res_item else None
                            ),
                            matched=False,
                            note="Extra item in actual output",
                        )
                    )
            elif res_item is None:
                # Missing item in result
                failed += 1
                if len(examples) < self.max_examples:
                    examples.append(
                        ComparisonExample(
                            instance_identifier=match_id,
                            expected_value=serialize_value(exp_item.get(field_name)),
                            actual_value=None,
                            matched=False,
                            note="Missing from actual output",
                        )
                    )
            else:
                # Both items present - compare field
                exp_val = exp_item.get(field_name)
                res_val = res_item.get(field_name)
                matched = self.matcher._values_match(exp_val, res_val)

                if matched:
                    passed += 1
                else:
                    failed += 1
                    if len(examples) < self.max_examples:
                        examples.append(
                            ComparisonExample(
                                instance_identifier=match_id,
                                expected_value=serialize_value(exp_val),
                                actual_value=serialize_value(res_val),
                                matched=False,
                                note="Value mismatch",
                            )
                        )

        total = passed + failed
        field_path = f"{parent_path}.{field_name}" if parent_path else field_name

        return FieldComparison(
            field_path=field_path,
            comparison_type=comparison_type,
            total_instances=total,
            passed_instances=passed,
            failed_instances=failed,
            passed=(failed == 0),
            rationale=build_rationale(field_path, failed == 0, total, passed),
            examples=examples,
            matching_strategy=matching_strategy,
        )

    def _compare_nested_arrays(
        self,
        matches: list[tuple[dict | None, dict | None, str]],
        nested_field: str,
        nested_config: list[str] | dict,
        parent_path: str,
        comparison_type: str,
    ) -> list[FieldComparison]:
        """Compare nested arrays across all matched parent pairs.

        For each matched pair of parent items, extracts the nested array field
        and recursively compares items within those arrays.

        Args:
            matches: List of (expected_item, actual_item, match_id) tuples from parent
            nested_field: Name of the nested array field within each item
            nested_config: Field configuration for nested array items
            parent_path: Dot-separated path to the parent array
            comparison_type: Type of comparison ("strict" or "llm")

        Returns:
            List of FieldComparison results for all nested fields
        """
        # Parse nested config to get simple fields and further nested configs
        simple_fields, further_nested = self._parse_array_field_config(nested_config)

        # Collect all nested items across all matched pairs
        all_exp_nested = []
        all_res_nested = []

        for exp_item, res_item, _match_id in matches:
            if exp_item is not None:
                exp_nested = exp_item.get(nested_field, []) or []
                # Convert to dicts if needed
                all_exp_nested.extend([to_dict(item) for item in exp_nested])
            if res_item is not None:
                res_nested = res_item.get(nested_field, []) or []
                all_res_nested.extend([to_dict(item) for item in res_nested])

        # Match nested items using simple fields
        nested_matches, strategy = self.matcher.match_items(
            all_exp_nested, all_res_nested, simple_fields
        )

        # Build the nested field path
        nested_path = f"{parent_path}.{nested_field}"

        # Compare simple fields across matched nested items
        comparisons = []
        for field_name in simple_fields:
            comparison = self._compare_field_across_matches(
                nested_matches, field_name, nested_path, comparison_type, strategy
            )
            comparisons.append(comparison)

        # Recursively handle further nested arrays
        for further_field, further_config in further_nested.items():
            further_comparisons = self._compare_nested_arrays(
                nested_matches,
                further_field,
                further_config,
                nested_path,
                comparison_type,
            )
            comparisons.extend(further_comparisons)

        return comparisons
