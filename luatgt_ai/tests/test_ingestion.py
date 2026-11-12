from scripts.ingest_corpus import parse_articles, validate_articles


def test_parser_preserves_article_and_clause_structure():
    pages = [{
        "page": 1,
        "text": "Điều 1. Phạm vi điều chỉnh\n1. Nội dung khoản một.\n2. Nội dung khoản hai.\nĐiều 2. Điều tiếp theo\nNội dung.",
    }]
    articles = parse_articles(pages)
    assert [article["article_no"] for article in articles] == [1, 2]
    assert articles[0]["clauses"][1]["clause_no"] == 2
    assert validate_articles(articles, expected_articles=2) == []
