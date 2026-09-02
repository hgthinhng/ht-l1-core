from hlpp_l0_contracts.schemas.normalized import NewsHeadlineNormalized


def test_source_name_optional_and_accepted() -> None:
    fields = NewsHeadlineNormalized.model_fields
    assert "source_name" in fields and fields["source_name"].default is None
