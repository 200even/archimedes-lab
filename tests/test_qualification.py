from archimedes_v0.qualification import (
    QUALIFICATION_CORPUS_SIZE,
    QUALIFICATION_EXPECTED_DIGEST,
    QUALIFICATION_MAX_DEPTH,
    generate_qualification_corpus,
    qualification_corpus_digest,
    qualification_corpus_stats,
    qualification_tree_counts,
    unrank_qualification_expr,
)


def test_exact_uniform_grammar_counts_are_frozen():
    counts = qualification_tree_counts(5)
    assert counts == {
        1: 10,
        2: 404130,
        3: 1486184841970,
        4: 19878708520438490059242450,
        5: 3556467471964984402981299531165583146592179712091410,
    }


def test_rank_unrank_boundaries_are_valid():
    counts = qualification_tree_counts(3)
    first = unrank_qualification_expr(3, 0)
    last = unrank_qualification_expr(3, counts[3] - 1)
    assert first.kind == "var" and first.name == "q"
    assert last.kind == "eq_mask"


def test_frozen_1000_ast_corpus_digest_is_reproducible():
    corpus = generate_qualification_corpus()
    assert len(corpus) == QUALIFICATION_CORPUS_SIZE
    assert qualification_corpus_digest(corpus) == QUALIFICATION_EXPECTED_DIGEST
    stats = qualification_corpus_stats(corpus)
    assert stats.depth_counts == {QUALIFICATION_MAX_DEPTH: QUALIFICATION_CORPUS_SIZE}
    assert stats.digest_sha256 == QUALIFICATION_EXPECTED_DIGEST


def test_qualification_module_does_not_depend_on_hidden_generator():
    import archimedes_v0.qualification as qualification

    names = set(qualification.__dict__)
    assert "generate_world" not in names
    assert "HiddenWorldRuntime" not in names
