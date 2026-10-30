"""Imported brief assessments must carry positive, current producer evidence."""

import copy
import json
from datetime import date, timedelta

import pytest

from scripts.content_brief_evidence import assess_relevance, assess_serp, brief_decision


def producer_assessments():
    today = date.today().isoformat()
    relevance = assess_relevance(
        {'purpose': 'Commercial HVAC maintenance', 'audience': 'Facility managers',
         'offerings': ['HVAC maintenance'], 'markets': ['US-NY'],
         'expertise': ['Licensed HVAC engineers']},
        'Commercial HVAC maintenance', market='US-NY',
    )
    serp = assess_serp(
        [{'url': 'https://reference.example/hvac', 'position': 1, 'page_type': 'guide',
          'intent': 'informational', 'last_updated': today, 'first_hand_evidence': True,
          'sources_cited': True, 'entities': ['HVAC', 'maintenance', 'facilities']}],
        {'query': 'Commercial HVAC maintenance', 'locale': 'en-US', 'device': 'mobile',
         'date': today, 'source': 'synthetic supplied export'},
        own_domain='ours.example', target_intent='informational',
    )
    return relevance, serp


def test_empty_assessments_cannot_approve_publication() -> None:
    decision = brief_decision({}, {}, ['A distinct first-hand test result.'])
    assert decision['publish'] is False


def test_genuine_current_producer_outputs_preserve_drafting_decision() -> None:
    relevance, serp = producer_assessments()
    assert relevance['verdict'] == 'RELEVANT'
    assert serp['status'] == 'OK'
    assert brief_decision(relevance, serp, ['First-hand maintenance test.'])['publish'] is True


@pytest.mark.parametrize('mutation', [
    'relevance_summary_only', 'relevance_unknown', 'relevance_empty_tokens',
    'relevance_empty_fields', 'serp_summary_only', 'serp_unknown', 'serp_capture_missing',
    'serp_capture_empty', 'serp_date_stale', 'serp_date_future', 'serp_date_invalid',
    'serp_empty_results', 'serp_forged_empty_row', 'serp_missing_observation',
    'serp_count_mismatch', 'serp_stale_flag_missing', 'serp_stale_flag_true',
])
def test_positive_labels_do_not_replace_producer_evidence(mutation) -> None:
    relevance, serp = copy.deepcopy(producer_assessments())
    if mutation == 'relevance_summary_only':
        relevance = {'verdict': 'RELEVANT'}
    elif mutation == 'relevance_unknown':
        relevance['verdict'] = 'APPROVED'
    elif mutation == 'relevance_empty_tokens':
        relevance['evidence']['matched_site_tokens'] = []
    elif mutation == 'relevance_empty_fields':
        relevance['evidence']['site_fields_supplied'] = []
    elif mutation == 'serp_summary_only':
        serp = {'status': 'OK'}
    elif mutation == 'serp_unknown':
        serp['status'] = 'SUFFICIENT'
    elif mutation == 'serp_capture_missing':
        del serp['capture']
    elif mutation == 'serp_capture_empty':
        serp['capture'] = {}
    elif mutation.startswith('serp_date_'):
        days = 31 if mutation.endswith('stale') else -1
        serp['capture']['date'] = ('invalid' if mutation.endswith('invalid') else
                                   (date.today() - timedelta(days=days)).isoformat())
    elif mutation == 'serp_empty_results':
        serp['competitors'] = []
    elif mutation == 'serp_forged_empty_row':
        serp['competitors'] = [{}]
    elif mutation == 'serp_missing_observation':
        serp['competitors'][0]['observed'] = {}
    elif mutation == 'serp_count_mismatch':
        serp['result_count'] = 999
    elif mutation == 'serp_stale_flag_missing':
        del serp['stale']
    else:
        serp['stale'] = True
    assert brief_decision(relevance, serp, ['A unique test.'])['publish'] is False


def test_imported_empty_brief_returns_blocked_cli_exit(tmp_path) -> None:
    from seoctl.cli import EXIT_BLOCKED, run

    relevance, serp, gains = (tmp_path / name for name in ('relevance.json', 'serp.json', 'gains.json'))
    relevance.write_text('{}', encoding='utf-8')
    serp.write_text('{}', encoding='utf-8')
    gains.write_text(json.dumps(['A claimed gain']), encoding='utf-8')
    payload, code = run(['content', 'brief-decision', '--relevance', str(relevance),
                         '--serp', str(serp), '--information-gain', str(gains)])
    assert code == EXIT_BLOCKED
    assert payload['status'] == 'blocked'
    assert payload['data']['publish'] is False


def test_conditional_producer_evidence_requires_explicit_resolution() -> None:
    _, serp = producer_assessments()
    relevance = assess_relevance(
        {'purpose': 'HVAC maintenance', 'audience': 'Facility managers',
         'offerings': ['HVAC maintenance'], 'markets': ['US-NY']}, 'HVAC maintenance',
    )
    assert relevance['verdict'] == 'CONDITIONALLY_RELEVANT'
    assert not brief_decision(relevance, serp, ['Field test.'])['publish']
    assert brief_decision(relevance, serp, ['Field test.'], conditions_resolved=True)['publish']


def test_mixed_intent_producer_evidence_requires_selected_intent() -> None:
    relevance, original = producer_assessments()
    row = original['competitors'][0]['observed']
    serp = assess_serp([row, dict(row, url='https://second.example/hvac', intent='transactional')],
                       original['capture'], own_domain='ours.example')
    assert serp['mixed_intent'] is True
    assert not brief_decision(relevance, serp, ['Field test.'])['publish']
    assert brief_decision(relevance, serp, ['Field test.'], selected_intent='informational')['publish']


@pytest.mark.parametrize('gains', [[''], ['   '], [None], [{}]])
def test_blank_or_untyped_information_gain_cannot_approve(gains) -> None:
    relevance, serp = producer_assessments()
    assert brief_decision(relevance, serp, gains)['publish'] is False


def test_producer_url_whitespace_is_preserved() -> None:
    relevance, original = producer_assessments()
    row = dict(original['competitors'][0]['observed'], url='  https://reference.example/hvac  ')
    serp = assess_serp([row], original['capture'], own_domain='ours.example')
    assert brief_decision(relevance, serp, ['Field test.'])['publish'] is True


def test_condition_resolution_is_an_explicit_boolean() -> None:
    _, serp = producer_assessments()
    relevance = assess_relevance({'purpose': 'HVAC maintenance', 'audience': 'Facilities',
                                  'offerings': ['HVAC maintenance']}, 'HVAC maintenance')
    assert not brief_decision(relevance, serp, ['Field test.'], conditions_resolved='false')['publish']


@pytest.mark.parametrize('field', ['bar_to_beat', 'signal'])
def test_oversized_numeric_evidence_is_rejected_without_overflow(field) -> None:
    relevance, serp = producer_assessments()
    if field == 'bar_to_beat':
        serp['bar_to_beat'] = 10 ** 1000
    else:
        serp['competitors'][0]['signals']['intent_fit'] = 10 ** 1000
    assert brief_decision(relevance, serp, ['Field test.'])['publish'] is False


@pytest.mark.parametrize('mutation', ['mixed_flag_downgrade', 'duplicate_competitor',
                                    'inconsistent_bar', 'missing_weights', 'invalid_signal'])
def test_imported_serp_summary_must_agree_with_observations(mutation) -> None:
    relevance, original = producer_assessments()
    row = original['competitors'][0]['observed']
    serp = assess_serp([row, dict(row, url='https://second.example/hvac', intent='transactional')],
                       original['capture'], own_domain='ours.example')
    if mutation == 'mixed_flag_downgrade':
        serp['mixed_intent'] = False
    elif mutation == 'duplicate_competitor':
        serp['competitors'].append(copy.deepcopy(serp['competitors'][0]))
        serp['result_count'] += 1
    elif mutation == 'inconsistent_bar':
        serp['bar_to_beat'] += 1
    elif mutation == 'missing_weights':
        del serp['weights']
    else:
        serp['competitors'][0]['signals']['intent_fit'] = float('nan')
    selected = 'informational' if mutation == 'duplicate_competitor' else None
    assert not brief_decision(relevance, serp, ['Field test.'], selected_intent=selected)['publish']


def test_contradicted_observations_cannot_keep_positive_serp_signals() -> None:
    relevance, serp = producer_assessments()
    row = serp['competitors'][0]
    row['observed'] = {'url': row['url'], 'inaccessible': True, 'fetch_error': 'not fetched',
                       'entities': [], 'intent': '', 'last_updated': '1900-01-01'}
    assert brief_decision(relevance, serp, ['First-hand maintenance test.'])['publish'] is False


@pytest.mark.parametrize('field,value', [
    ('inaccessible', True), ('fetch_error', 'not fetched'), ('entities', []),
    ('intent', ''), ('last_updated', '1900-01-01'), ('first_hand_evidence', False),
    ('sources_cited', False), ('conversion_path', True),
])
def test_each_observed_fact_must_agree_with_its_retained_signal(field, value) -> None:
    relevance, serp = producer_assessments()
    serp['competitors'][0]['observed'][field] = value
    assert not brief_decision(relevance, serp, ['First-hand maintenance test.'])['publish']


@pytest.mark.parametrize('field', ['first_hand_evidence', 'sources_cited'])
def test_imported_boolean_observations_cannot_be_truthy_strings(field) -> None:
    relevance, serp = producer_assessments()
    serp['competitors'][0]['observed'][field] = 'false'
    assert not brief_decision(relevance, serp, ['First-hand maintenance test.'])['publish']


def test_producer_keeps_only_boolean_presence_facts() -> None:
    _, original = producer_assessments()
    row = dict(original['competitors'][0]['observed'],
               first_hand_evidence='synthetic-private-note',
               sources_cited=['synthetic-private-source'],
               conversion_path='https://example.com/?token=synthetic-private-value')
    serp = assess_serp([row], original['capture'], own_domain='ours.example')
    observed = serp['competitors'][0]['observed']
    assert all(observed[field] is True for field in
               ('first_hand_evidence', 'sources_cited', 'conversion_path'))
    assert 'synthetic-private' not in str(observed)


def test_recorded_assessment_date_preserves_historical_scoring() -> None:
    relevance, original = producer_assessments()
    captured = date.today() - timedelta(days=2)
    row = dict(original['competitors'][0]['observed'],
               last_updated=(captured - timedelta(days=365)).isoformat())
    serp = assess_serp([row], dict(original['capture'], date=captured.isoformat()),
                       own_domain='ours.example', as_of=captured.isoformat())
    assert serp['competitors'][0]['signals']['freshness'] == 1
    assert brief_decision(relevance, serp, ['Historical field test.'])['publish']


@pytest.mark.parametrize('assessed', [None, 'invalid', '1900-01-01'])
def test_missing_or_contradictory_assessment_date_blocks(assessed) -> None:
    relevance, serp = producer_assessments()
    serp['assessed_as_of'] = assessed
    assert not brief_decision(relevance, serp, ['Field test.'])['publish']


def test_inaccessible_summary_cannot_also_claim_readable_competitor() -> None:
    relevance, serp = producer_assessments()
    serp['inaccessible'] = [{'url': serp['competitors'][0]['url'], 'reason': 'not fetched',
                             'evidence_state': 'Not Run'}]
    assert not brief_decision(relevance, serp, ['Field test.'])['publish']


def test_genuine_producer_discloses_other_inaccessible_rows_without_losing_readable_evidence() -> None:
    relevance, original = producer_assessments()
    serp = assess_serp([original['competitors'][0]['observed'],
                        {'url': 'https://blocked.example/hvac', 'fetch_error': 'not fetched'}],
                       original['capture'], own_domain='ours.example')
    assert serp['inaccessible'] and serp['result_count'] == 1
    assert brief_decision(relevance, serp, ['Field test.'])['publish']
