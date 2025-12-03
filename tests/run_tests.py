#!/usr/bin/env python3
"""
Test runner for Geomodelierung project

Usage:
    python tests/run_tests.py              # Run all tests
    python tests/run_tests.py --unit       # Run unit tests only
    python tests/run_tests.py --coverage   # Run with coverage report
    python tests/run_tests.py --fast       # Skip slow tests
"""

import sys
import subprocess
from pathlib import Path
import argparse

# Add src to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / 'src'))


def run_tests(args):
    """
    Run pytest with specified configuration

    Args:
        args: Parsed command-line arguments
    """
    pytest_args = ['pytest']

    # Add test path
    if args.unit:
        pytest_args.extend([
            'tests/test_client.py',
            'tests/test_extraction.py',
            'tests/test_storage.py',
            'tests/test_state.py',
            'tests/test_spatial.py'
        ])
    elif args.integration:
        pytest_args.append('tests/test_integration.py')
    else:
        pytest_args.append('tests/')

    # Add markers
    if args.fast:
        pytest_args.extend(['-m', 'not slow'])

    if args.no_network:
        pytest_args.extend(['-m', 'not network'])

    # Coverage
    if args.coverage:
        pytest_args.extend([
            '--cov=src',
            '--cov-report=html',
            '--cov-report=term-missing'
        ])

    # Verbosity
    if args.verbose:
        pytest_args.append('-vv')
    elif args.quiet:
        pytest_args.append('-q')

    # Parallel execution
    if args.parallel:
        pytest_args.extend(['-n', 'auto'])

    # Stop on first failure
    if args.exitfirst:
        pytest_args.append('-x')

    # Show local variables
    if args.showlocals:
        pytest_args.append('-l')

    # Specific test
    if args.test:
        pytest_args.extend(['-k', args.test])

    # Print command
    print(f"Running: {' '.join(pytest_args)}\n")

    # Run pytest
    try:
        result = subprocess.run(pytest_args, check=False)
        return result.returncode
    except FileNotFoundError:
        print("Error: pytest not found. Install with: pip install pytest")
        return 1


def check_dependencies():
    """Check if required test dependencies are installed"""
    required = ['pytest']
    optional = ['pytest-cov', 'pytest-xdist', 'pytest-timeout']

    missing_required = []
    missing_optional = []

    for package in required:
        try:
            __import__(package.replace('-', '_'))
        except ImportError:
            missing_required.append(package)

    for package in optional:
        try:
            __import__(package.replace('-', '_'))
        except ImportError:
            missing_optional.append(package)

    if missing_required:
        print(f"ERROR: Required packages missing: {', '.join(missing_required)}")
        print(f"Install with: pip install {' '.join(missing_required)}")
        return False

    if missing_optional:
        print(f"Note: Optional packages not installed: {', '.join(missing_optional)}")
        print(f"Install with: pip install {' '.join(missing_optional)}\n")

    return True


def main():
    parser = argparse.ArgumentParser(
        description='Run tests for Geomodelierung project',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python tests/run_tests.py                    # Run all tests
  python tests/run_tests.py --unit             # Unit tests only
  python tests/run_tests.py --integration      # Integration tests only
  python tests/run_tests.py --coverage         # With coverage report
  python tests/run_tests.py --fast             # Skip slow tests
  python tests/run_tests.py -k test_client     # Run specific test
  python tests/run_tests.py --parallel         # Run tests in parallel
        """
    )

    # Test selection
    test_group = parser.add_mutually_exclusive_group()
    test_group.add_argument(
        '--unit',
        action='store_true',
        help='Run unit tests only'
    )
    test_group.add_argument(
        '--integration',
        action='store_true',
        help='Run integration tests only'
    )

    # Test filtering
    parser.add_argument(
        '--fast',
        action='store_true',
        help='Skip slow tests'
    )
    parser.add_argument(
        '--no-network',
        action='store_true',
        help='Skip tests requiring network access'
    )
    parser.add_argument(
        '-k', '--test',
        type=str,
        help='Run tests matching given substring expression'
    )

    # Coverage
    parser.add_argument(
        '--coverage',
        action='store_true',
        help='Generate coverage report'
    )

    # Output options
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Verbose output'
    )
    parser.add_argument(
        '-q', '--quiet',
        action='store_true',
        help='Quiet output'
    )
    parser.add_argument(
        '-l', '--showlocals',
        action='store_true',
        help='Show local variables in tracebacks'
    )

    # Execution options
    parser.add_argument(
        '-x', '--exitfirst',
        action='store_true',
        help='Exit on first failure'
    )
    parser.add_argument(
        '-n', '--parallel',
        action='store_true',
        help='Run tests in parallel (requires pytest-xdist)'
    )

    # Check dependencies
    parser.add_argument(
        '--check-deps',
        action='store_true',
        help='Check test dependencies and exit'
    )

    args = parser.parse_args()

    # Check dependencies
    if args.check_deps:
        if check_dependencies():
            print("All required dependencies are installed!")
            return 0
        else:
            return 1

    # Check dependencies before running
    if not check_dependencies():
        return 1

    # Run tests
    return run_tests(args)


if __name__ == '__main__':
    sys.exit(main())
