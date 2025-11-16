#!/usr/bin/env python3
"""
Simple test for aggregate parsing
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.query import Lexer, Parser

def test_count_parsing():
    """Test basic COUNT parsing"""
    try:
        lexer = Lexer('SELECT COUNT(*) FROM users')
        tokens = lexer.tokenize()
        parser = Parser(tokens)
        ast = parser.parse()
        print('✓ Basic COUNT parsing works')
        print(f'  AST: {ast}')
        return True
    except Exception as e:
        print(f'✗ Error: {e}')
        return False

def test_group_by_parsing():
    """Test GROUP BY parsing"""
    try:
        lexer = Lexer('SELECT COUNT(*) FROM users GROUP BY department')
        tokens = lexer.tokenize()
        parser = Parser(tokens)
        ast = parser.parse()
        print('✓ GROUP BY parsing works')
        print(f'  AST: {ast}')
        print(f'  Group by: {ast.group_by}')
        return True
    except Exception as e:
        print(f'✗ Error: {e}')
        return False

if __name__ == '__main__':
    print("Testing aggregate parsing...")
    test_count_parsing()
    test_group_by_parsing()
    print("Done!")