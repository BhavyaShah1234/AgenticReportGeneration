from app.schemas.report import ReportFormatBody, WidgetSpec


def test_report_format_roundtrip():
    body = ReportFormatBody(
        name="Client Quarterly Review",
        params=[{"name": "client", "label": "Client", "type": "client", "column": "CLIENT_NAME"}],
        widgets=[
            {
                "id": "w1",
                "type": "line",
                "title": "Monthly sales",
                "archetype": {"id": "time_series", "params": {"date_column": "ORDER_DATE", "measure": "SALES"}},
            }
        ],
    )
    again = ReportFormatBody.model_validate_json(body.model_dump_json())
    assert again == body
    assert isinstance(again.widgets[0], WidgetSpec)
    assert again.widgets[0].layout.w == 6
