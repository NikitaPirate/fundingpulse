from fundingpulse.api.main import create_app


def test_historical_sums_openapi_excludes_normalization() -> None:
    schema = create_app().openapi()
    parameters = schema["paths"]["/api/v0/funding-data/historical_sums"]["get"]["parameters"]

    assert "normalize_to_interval" not in {parameter["name"] for parameter in parameters}
