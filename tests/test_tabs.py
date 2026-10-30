import pytest

from handover_bot.sources import find_month_tab

TITLES = ['Issue Oktober 2026', 'Issue September 2026', 'Issue Mar 2026', 'Issue_Jan_2026', 'Issue Des 2025',
          'Issue Sept 2025', 'Issue Ags 25', 'Summary Issue Monthly', ' Issue Mei 25', 'Issue Agst 24',
          'Issue May 23', 'Sheet1']


@pytest.mark.parametrize("year, month, expected", [
    (2026, 10, 'Issue Oktober 2026'),
    (2026, 3, 'Issue Mar 2026'),
    (2026, 1, 'Issue_Jan_2026'),
    (2025, 9, 'Issue Sept 2025'),
    (2025, 8, 'Issue Ags 25'),
    (2025, 5, ' Issue Mei 25'),
    (2024, 8, 'Issue Agst 24'),
    (2023, 5, 'Issue May 23'),
    (2026, 11, None),
])
def test_find_month_tab(year, month, expected):
    assert find_month_tab(TITLES, year, month) == expected
