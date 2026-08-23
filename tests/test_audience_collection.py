"""
Stage 2 tests. Deliberately narrow, per the task instructions: only the
cleaning/quality/merge/human-review logic, using small synthetic fixture
rows clearly marked as test data (never real Wealthsimple comments -- no
live network collection is exercised here, since collectors need real
internet access this test environment does not have).
"""

import csv

from src.audience_collection.cleaning.clean_pipeline import clean_platform
from src.audience_collection.cleaning.dedup import compute_near_duplicate_groups, flag_exact_duplicates
from src.audience_collection.cleaning.quality_flags import apply_quality_flags
from src.audience_collection.collectors.base import append_new_raw_rows, empty_raw_row, make_comment_id
from src.audience_collection.human_review import build_human_review_csv
from src.audience_collection.merge import merge_cleaned_files
from src.audience_collection.schema import CLEANED_FIELDS, HUMAN_FILL_IN_FIELDS, HUMAN_REVIEW_FIELDS, QUALITY_FIELDS, RAW_FIELDS


def make_row(platform="reddit", comment_id=None, text="[TEST FIXTURE] a normal comment about wealthsimple", username="test_user", url="https://example.invalid/thread/1"):
    row = empty_raw_row()
    row.update(
        {
            "comment_id": comment_id or make_comment_id(platform, "abc123"),
            "platform": platform,
            "source_url": url,
            "thread_or_page_title": "[TEST FIXTURE] thread title",
            "public_username": username,
            "comment_text": text,
            "comment_date": "2024-10-15T00:00:00+00:00",
            "collected_at": "2024-10-16T00:00:00+00:00",
            "likes_or_upvotes": 3,
            "reply_count": 0,
            "parent_comment_id": "",
            "brand": "Wealthsimple",
            "product": "Wealthsimple App (general)",
            "campaign_or_event": "[TEST FIXTURE]",
            "raw_status": "COLLECTED",
        }
    )
    return row


# --- 1 & 2: raw files created, never overwritten -----------------------------

def test_append_new_raw_rows_creates_file(tmp_path):
    path = tmp_path / "reddit_raw.csv"
    rows = [make_row(comment_id="reddit_1"), make_row(comment_id="reddit_2")]
    report = append_new_raw_rows(path, rows)
    assert path.exists()
    assert report == {"existing": 0, "appended": 2, "skipped_duplicate_id": 0, "total": 2}


def test_append_new_raw_rows_never_overwrites_existing(tmp_path):
    path = tmp_path / "reddit_raw.csv"
    first_batch = [make_row(comment_id="reddit_1", text="[TEST FIXTURE] original text")]
    append_new_raw_rows(path, first_batch)

    # second run: one duplicate ID (must be skipped, original text preserved)
    # and one genuinely new row (must be appended)
    second_batch = [
        make_row(comment_id="reddit_1", text="[TEST FIXTURE] a DIFFERENT text -- must NOT overwrite"),
        make_row(comment_id="reddit_2", text="[TEST FIXTURE] a new row"),
    ]
    report = append_new_raw_rows(path, second_batch)

    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    assert report == {"existing": 1, "appended": 1, "skipped_duplicate_id": 1, "total": 2}
    assert len(rows) == 2
    row1 = next(r for r in rows if r["comment_id"] == "reddit_1")
    assert row1["comment_text"] == "[TEST FIXTURE] original text"  # untouched


# --- 3: exact duplicate detection --------------------------------------------

def test_exact_duplicate_detection():
    rows = [
        make_row(comment_id="a", text="[TEST FIXTURE] Great app, love it!"),
        make_row(comment_id="b", text="[TEST FIXTURE] Great app, love it!"),
        make_row(comment_id="c", text="[TEST FIXTURE] Something totally different here."),
    ]
    flag_exact_duplicates(rows)
    assert rows[0]["is_exact_duplicate"] is False
    assert rows[1]["is_exact_duplicate"] is True
    assert rows[2]["is_exact_duplicate"] is False


# --- 4: near-duplicate logic ------------------------------------------------

def test_near_duplicate_grouping():
    rows = [
        make_row(comment_id="a", text="[TEST FIXTURE] I switched to Questrade last month", username="user1"),
        make_row(comment_id="b", text="[TEST FIXTURE] I switched to Questrade last week", username="user2"),
        make_row(comment_id="c", text="[TEST FIXTURE] completely unrelated comment about coffee", username="user3"),
    ]
    groups = compute_near_duplicate_groups(rows)
    assert len(groups) == 1
    assert set(groups[0]) == {0, 1}


# --- 5: quality flags populated ---------------------------------------------

def test_quality_flags_populate_every_field():
    rows = [
        make_row(comment_id="a", text="[TEST FIXTURE] Wealthsimple fees are too high honestly"),
        make_row(comment_id="b", text="wealthsimple ok"),  # on-topic (brand keyword present) but low information
        make_row(comment_id="c", text="[TEST FIXTURE] check my bio for a promo code!! DM me now"),
        make_row(comment_id="d", text="[TEST FIXTURE] totally unrelated, no brand mention at all"),
    ]
    apply_quality_flags(rows)
    for row in rows:
        for field in QUALITY_FIELDS:
            assert field in row  # every quality field must be populated, even if falsy (False/0.0)

    assert rows[1]["low_information"] is True
    assert rows[1]["quality_status"] == "LOW_INFORMATION"
    assert rows[2]["possible_spam"] is True
    assert rows[2]["quality_status"] == "POSSIBLE_SPAM"
    assert rows[3]["irrelevant"] is True
    assert rows[3]["quality_status"] == "IRRELEVANT"
    assert rows[0]["quality_status"] == "VALID"


def test_possible_coordinated_post_flags_cross_user_near_duplicates():
    rows = [
        make_row(comment_id="a", text="[TEST FIXTURE] Wealthsimple locked my account for no reason", username="alice"),
        make_row(comment_id="b", text="[TEST FIXTURE] Wealthsimple locked my account for no reason!", username="bob"),
    ]
    apply_quality_flags(rows)
    assert rows[0]["possible_coordinated_post"] is True
    assert rows[1]["possible_coordinated_post"] is True
    assert rows[0]["quality_status"] == "POSSIBLE_COORDINATED"


def test_possible_bot_never_asserted_without_signal():
    rows = [make_row(comment_id="a", text="[TEST FIXTURE] Wealthsimple has been great for my TFSA", username="regular_person")]
    apply_quality_flags(rows)
    assert rows[0]["possible_bot"] is False


# --- 9: comment text is readable (cleaned_text) -------------------------------

def test_cleaned_text_decodes_html_entities_and_stays_readable():
    rows = [make_row(comment_id="a", text="[TEST FIXTURE] Wealthsimple&#39;s fees &amp; features are good")]
    apply_quality_flags(rows)
    assert rows[0]["cleaned_text"] == "[TEST FIXTURE] Wealthsimple's fees & features are good"


# --- 6, 8, 10: master merge works, source URLs preserved, counts reported ---

def _write_cleaned_csv(path, rows):
    apply_quality_flags(rows)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CLEANED_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in CLEANED_FIELDS})


def test_merge_reports_counts_and_preserves_source_url(tmp_path):
    reddit_rows = [make_row(platform="reddit", comment_id="reddit_1", url="https://reddit.example/thread/1")]
    play_rows = [
        make_row(platform="google_play", comment_id="google_play_1", url="https://play.example/app/1"),
        make_row(platform="google_play", comment_id="google_play_2", url="https://play.example/app/1"),
    ]
    reddit_path = tmp_path / "reddit_cleaned.csv"
    play_path = tmp_path / "google_play_cleaned.csv"
    _write_cleaned_csv(reddit_path, reddit_rows)
    _write_cleaned_csv(play_path, play_rows)

    master_path = tmp_path / "audience_master_cleaned.csv"
    counts = merge_cleaned_files({"reddit": reddit_path, "google_play": play_path}, master_path)

    assert counts == {"reddit": 1, "google_play": 2}
    with open(master_path, newline="", encoding="utf-8") as f:
        master_rows = list(csv.DictReader(f))
    assert len(master_rows) == 3
    urls = {row["source_url"] for row in master_rows}
    assert urls == {"https://reddit.example/thread/1", "https://play.example/app/1"}


# --- 7: human-review CSV opens correctly, has the right columns -------------

def test_human_review_csv_has_exact_columns_and_blank_fill_in_fields(tmp_path):
    rows = [make_row(comment_id="a", text="[TEST FIXTURE] a valid comment about wealthsimple fees")]
    master_path = tmp_path / "audience_master_cleaned.csv"
    _write_cleaned_csv(master_path, rows)

    output_path = tmp_path / "wealthsimple_audience_manual_review.csv"
    n = build_human_review_csv(master_path, output_path)
    assert n == 1

    with open(output_path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        assert reader.fieldnames == HUMAN_REVIEW_FIELDS
        review_rows = list(reader)

    assert len(review_rows) == 1
    for field in HUMAN_FILL_IN_FIELDS:
        assert review_rows[0][field] == ""
    assert review_rows[0]["comment_text"] == "[TEST FIXTURE] a valid comment about wealthsimple fees"


def test_human_review_csv_handles_missing_master_gracefully(tmp_path):
    output_path = tmp_path / "review.csv"
    n = build_human_review_csv(tmp_path / "does_not_exist.csv", output_path)
    assert n == 0
    with open(output_path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        assert reader.fieldnames == HUMAN_REVIEW_FIELDS
        assert list(reader) == []


# --- end-to-end: clean_platform (raw -> cleaned) preserves raw fields -------

def test_clean_platform_end_to_end(tmp_path):
    raw_path = tmp_path / "reddit_raw.csv"
    append_new_raw_rows(
        raw_path,
        [make_row(comment_id="reddit_1", text="[TEST FIXTURE] Wealthsimple support was actually helpful today")],
    )
    cleaned_path = tmp_path / "reddit_cleaned.csv"
    cleaned_rows = clean_platform(raw_path, cleaned_path)

    assert cleaned_path.exists()
    assert len(cleaned_rows) == 1
    with open(cleaned_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        assert reader.fieldnames == CLEANED_FIELDS
        rows = list(reader)
    assert rows[0]["quality_status"] == "VALID"
    for field in RAW_FIELDS:
        # CSV round-trip reads everything back as strings; compare on that basis
        assert rows[0][field] == str(cleaned_rows[0][field])
