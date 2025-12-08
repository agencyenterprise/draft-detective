#!/usr/bin/env python3
"""Binary search algorithm example.

This script demonstrates binary search on a sorted list of numbers.
"""


def binary_search(arr: list[int], target: int) -> int | None:
    """Perform binary search on a sorted array.

    Args:
        arr: Sorted list of integers
        target: Value to search for

    Returns:
        Index of target if found, None otherwise
    """
    left, right = 0, len(arr) - 1

    while left <= right:
        mid = (left + right) // 2

        if arr[mid] == target:
            return mid
        elif arr[mid] < target:
            left = mid + 1
        else:
            right = mid - 1

    return None


def main():
    """Main function to demonstrate binary search."""
    # Sample sorted sequence
    numbers = [1, 3, 5, 7, 9, 11, 13, 15, 17, 19, 21, 23, 25]

    print("Binary Search Algorithm Demo")
    print("=" * 40)
    print(f"Sorted array: {numbers}")
    print()

    # Test cases
    test_values = [7, 15, 2, 25, 30]

    for target in test_values:
        result = binary_search(numbers, target)
        if result is not None:
            print(f"✓ Found {target} at index {result}")
        else:
            print(f"✗ {target} not found in array")

    print()
    print("=" * 40)
    print("Binary search completed successfully!")


if __name__ == "__main__":
    main()
