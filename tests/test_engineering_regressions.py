from controlplane.detectors.engineering import (
    contains_destructive_operation,
    contains_unbounded_delete,
)


def test_unbounded_delete_is_not_masked_by_later_prose_where():
    candidate = (
        "Run DELETE FROM sessions to clear old sessions. "
        "This helps where users report stale logins."
    )

    assert contains_unbounded_delete(candidate)
    assert contains_destructive_operation(candidate)


def test_delete_with_where_is_not_classified_as_unbounded():
    assert not contains_unbounded_delete(
        "DELETE FROM sessions WHERE expired_at < CURRENT_TIMESTAMP;"
    )


def test_multiline_delete_with_where_is_not_classified_as_unbounded():
    assert not contains_unbounded_delete(
        "DELETE FROM sessions\nWHERE expired_at < CURRENT_TIMESTAMP;"
    )


def test_newline_prose_cannot_mask_unbounded_delete():
    assert contains_unbounded_delete(
        "DELETE FROM sessions\nThis explains where stale logins originate."
    )


def test_where_inside_sql_string_cannot_mask_unbounded_delete():
    assert contains_unbounded_delete("DELETE FROM sessions RETURNING 'where';")


def test_where_inside_sql_comments_cannot_mask_unbounded_delete():
    assert contains_unbounded_delete(
        "DELETE FROM sessions -- where cleanup is required"
    )
    assert contains_unbounded_delete(
        "DELETE FROM sessions /* where cleanup is required */;"
    )


def test_comment_between_delete_and_real_where_does_not_create_false_positive():
    assert not contains_unbounded_delete(
        "DELETE FROM sessions\n-- remove only expired rows\n"
        "WHERE expired_at < CURRENT_TIMESTAMP;"
    )
