from app.schemas.analysis import AnalysisResult

def test_response_schema_abstains_by_default():
    result=AnalysisResult(input_type='text')
    assert result.verdict=='INCONCLUSIVE'
    assert result.supporting_evidence==[]
