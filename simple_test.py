#!/usr/bin/env python3
"""
Simple test for aggregate parsing
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def test_basic():
    try:
        from src.query import Lexer, Parser
        lexer = Lexer('SELECT COUNT(*) FROM users')
        tokens = lexer.tokenize()
        parser = Parser(tokens)
        ast = parser.parse()
        print('✓ Basic COUNT parsing works')
        print(f'  AST: {ast}')
        print(f'  Aggregates: {ast.aggregates}')
        return True
    except Exception as e:
        print(f'✗ Error: {e}')
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    print("Testing aggregate parsing...")
    success = test_basic()
    print(f"Test {'PASSED' if success else 'FAILED'}")