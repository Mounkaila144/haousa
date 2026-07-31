from hausa_numbers import generate, parse


def test_round_trip_representative_range():
    values = list(range(10_000)) + [
        25_750,
        100_000,
        999_999,
        1_000_000,
        2_500_000,
        12_345_000,
        1_000_000_000,
        1_000_000_000_000,
    ]
    for value in values:
        assert parse(generate(value)) == value, value
