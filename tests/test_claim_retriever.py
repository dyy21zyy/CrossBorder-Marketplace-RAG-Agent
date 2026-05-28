from src.preprocessing.claim_group_builder import ClaimGroup
from src.retrieval.claim_retriever import ClaimRetriever


def test_build_claim_documents() -> None:
    retriever = ClaimRetriever(chroma_dir='indexes/chroma_test', bm25_path='indexes/bm25/claim_test.pkl', collection_name='claim_test')
    docs = retriever.build_claim_documents(
        [
            ClaimGroup(
                patent_id='US1',
                independent_claim_number='1',
                dependent_claim_numbers=['2'],
                claim_group_text='Claim 1: A charger. Claim 2: The charger of claim 1.',
                claim_count=2,
                source='Patent Claims Research Dataset',
                context_path='data/processed/claim_groups/claim_groups.jsonl',
            )
        ]
    )
    assert len(docs) == 1
    assert docs[0]['patent_id'] == 'US1'
    assert 'Claim 1' in docs[0]['text']
