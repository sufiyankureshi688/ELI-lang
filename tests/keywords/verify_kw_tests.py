#!/usr/bin/env python3
"""Verify test output against expected values."""

expected = [
    ('TEST 1: assign + read',      '42'),
    ('TEST 2: print',              '99'),
    ('TEST 3: println',            '77'),
    ('TEST 4: printchar',          'A'),
    ('TEST 5a: abs(-9)',           '9'),
    ('TEST 5b: abs(7)',            '7'),
    ('TEST 6a: sign(-5)',          '-1'),
    ('TEST 6b: sign(0)',           '0'),
    ('TEST 6c: sign(7)',           '1'),
    ('TEST 7: min(3,7)',           '3'),
    ('TEST 8: max(3,7)',           '7'),
    ('TEST 9a: clamp(99,0,10)',    '10'),
    ('TEST 9b: clamp(-5,0,10)',    '0'),
    ('TEST 9c: clamp(5,0,10)',     '5'),
    ('TEST 10a: swap a',           '2'),
    ('TEST 10b: swap b',           '1'),
    ('TEST 11: if(no else)',       '111'),
    ('TEST 12: if/else',           '333'),
    ('TEST 13a: while 3',          '3'),
    ('TEST 13b: while 2',          '2'),
    ('TEST 13c: while 1',          '1'),
    ('TEST 14a: ++',               '11'),
    ('TEST 14b: --',               '10'),
    ('TEST 14c: +=',               '15'),
    ('TEST 14d: -=',               '12'),
    ('TEST 14e: *=',               '24'),
    ('TEST 14f: /=',               '6'),
    ('TEST 15a: for 1',            '1'),
    ('TEST 15b: for 2',            '2'),
    ('TEST 15c: for 3',            '3'),
    ('TEST 16a: square(5)',        '25'),
    ('TEST 16b: square(7)',        '49'),
    ('TEST 17: double(6)',         '12'),
    ('TEST 18: factorial(5)',      '120'),
    ('TEST 19: assert',            '5'),
    ('TEST 20: lenarray',          '5'),
    ('TEST 21a: getarray[0]',      '10'),
    ('TEST 21b: getarray[1]',      '20'),
    ('TEST 21c: getarray[2]',      '30'),
    ('TEST 22a: arr1[0]',          '100'),
    ('TEST 22b: arr2[0]',          '200'),
    ('TEST 23: match single',      '888'),
    ('TEST 24: match multi',       '903'),
    ('TEST 25a: memoize first',    '49'),
    ('TEST 25b: memoize cached',   '49'),
    ('TEST 26: pipeline',          '11'),
    ('TEST 27: typedef',           '555'),
    ('TEST 28: tassign',           '42'),
    ('TEST 29: own',               '666'),
    ('TEST 30: buse',              '15'),
    ('TEST 31: move',              '777'),
    ('TEST 32: tinfer plus',       '7'),
    ('TEST 33: tinfer times',      '30'),
]

import subprocess, sys

r = subprocess.run(
    ['python3', 'src/alpha_p3.py', '--run', 'tests/test_all_kw.eli2'],
    capture_output=True, text=True, cwd='.'
)

output = r.stdout
lines = output.strip().split('\n')

# First line is compiled opcode dump; runtime output starts at line 2
runtime_lines = [l.strip() for l in lines[1:]]
runtime_lines = [l for l in runtime_lines if not l.startswith('Final stack')]

passed = 0
failed = 0

for i, (label, exp) in enumerate(expected):
    if i < len(runtime_lines):
        actual = runtime_lines[i]
        if actual == exp:
            passed += 1
            print(f"  \u2713 {label}: {actual}")
        else:
            failed += 1
            print(f"  \u2717 {label}: expected '{exp}', got '{actual}'")
    else:
        failed += 1
        print(f"  \u2717 {label}: NO OUTPUT (expected '{exp}')")

if len(runtime_lines) > len(expected):
    for i in range(len(expected), len(runtime_lines)):
        print(f"  ? EXTRA line {i+1}: '{runtime_lines[i]}'")

print(f"\n{'='*50}")
print(f"RESULTS: {passed} passed, {failed} failed, {len(runtime_lines)} total output lines")

if r.stderr:
    stderr_lines = [l for l in r.stderr.strip().split('\n') if l.strip()]
    if stderr_lines:
        print(f"\nSTDERR ({len(stderr_lines)} lines):")
        for l in stderr_lines[:10]:
            print(f"  {l}")

sys.exit(0 if failed == 0 else 1)
