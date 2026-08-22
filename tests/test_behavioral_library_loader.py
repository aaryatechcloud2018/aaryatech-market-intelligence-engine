from src.behavioral_library.loader import load_mechanisms, validate_mechanisms


def test_library_loads_and_has_expected_size():
    mechanisms = load_mechanisms()
    assert 25 <= len(mechanisms) <= 35


def test_library_passes_structural_validation():
    mechanisms = load_mechanisms()
    report = validate_mechanisms(mechanisms)
    assert report.duplicate_ids == []
    assert report.duplicate_names == []
    assert report.missing_fields == {}
    assert report.broken_related_pattern_refs == {}
    assert report.is_valid


def test_validate_detects_duplicate_id():
    mechanisms = [
        {"Pattern_ID": "BM-001", "Pattern_Name": "A", "Related_Patterns": []},
        {"Pattern_ID": "BM-001", "Pattern_Name": "B", "Related_Patterns": []},
    ]
    report = validate_mechanisms(mechanisms)
    assert "BM-001" in report.duplicate_ids
    assert not report.is_valid


def test_validate_detects_broken_related_pattern_reference():
    mechanisms = [
        {"Pattern_ID": "BM-001", "Pattern_Name": "A", "Related_Patterns": ["BM-999"]},
    ]
    report = validate_mechanisms(mechanisms)
    assert report.broken_related_pattern_refs == {"BM-001": ["BM-999"]}
    assert not report.is_valid


def test_validate_detects_missing_required_field():
    mechanisms = [
        {"Pattern_ID": "BM-001", "Related_Patterns": []},
    ]
    report = validate_mechanisms(mechanisms)
    assert "Pattern_Name" in report.missing_fields["BM-001"]
    assert not report.is_valid
