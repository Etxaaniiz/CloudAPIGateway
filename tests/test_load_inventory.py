import os
import textwrap
from lambdas.load_inventory import app


def test_parse_csv_rows_simple():
    csv_text = textwrap.dedent('''
        Store,Item,Count
        A,apple,10
        B,banana,5
        C,carrot,not-a-number
    ''')
    rows = list(app.parse_csv_rows(csv_text))
    assert rows[0] == ('A', 'apple', 10)
    assert rows[1] == ('B', 'banana', 5)
    # non-numeric count -> 0
    assert rows[2] == ('C', 'carrot', 0)
