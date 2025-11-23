"""
Run coverage tests for AlpacaDB
This script runs all tests with coverage reporting
"""
import subprocess
import sys
import os

def run_coverage():
    """Run pytest with coverage"""
    print("=" * 70)
    print("Running AlpacaDB Coverage Tests")
    print("=" * 70)
    print()
    
    # Run pytest with coverage
    cmd = [
        sys.executable, "-m", "pytest",
        "test_coverage.py",
        "-v",
        "--cov=src",
        "--cov-report=html",
        "--cov-report=term-missing",
        "--cov-report=json",
        "--cov-config=.coveragerc"
    ]
    
    print(f"Command: {' '.join(cmd)}")
    print()
    
    result = subprocess.run(cmd, cwd=os.path.dirname(os.path.abspath(__file__)))
    
    print()
    print("=" * 70)
    print("Coverage Report Generated")
    print("=" * 70)
    print()
    print("HTML Report: Open 'htmlcov/index.html' in your browser")
    print("JSON Report: See 'coverage.json'")
    print()
    
    return result.returncode

if __name__ == "__main__":
    sys.exit(run_coverage())
