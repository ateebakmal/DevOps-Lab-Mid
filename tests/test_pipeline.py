"""Pipeline tests: run after train.py, inside the deployable image."""
import json
from pathlib import Path

import joblib
import pandas as pd
import pytest
from fastapi.testclient import TestClient

import app as service

CONFIG = json.loads(Path('config.json').read_text())
REQUIRED_METRIC_KEYS = {
    'student_id', 'accuracy', 'training_rows', 'model_version', 'git_sha'
}


@pytest.fixture(scope='module')
def metrics():
    path = Path('artifacts/metrics.json')
    assert path.exists(), 'artifacts/metrics.json missing - run train.py first'
    return json.loads(path.read_text())


@pytest.fixture(scope='module')
def client():
    return TestClient(service.app)


# ---------------------------------------------------------------- artifacts

def test_model_artifact_exists():
    assert Path('artifacts/model.joblib').exists()


def test_metrics_contain_required_keys(metrics):
    assert REQUIRED_METRIC_KEYS.issubset(metrics)


def test_student_id_matches_config(metrics):
    assert metrics['student_id'] == CONFIG['student_id'] == 'FA23-BDS-004'


def test_training_rows_meet_minimum(metrics):
    assert metrics['training_rows'] >= 100


def test_accuracy_is_valid_and_better_than_chance(metrics):
    assert 0.0 <= metrics['accuracy'] <= 1.0
    assert metrics['accuracy'] >= 0.60, 'model is no better than a coin flip'


def test_model_version_tracks_dataset(metrics):
    assert metrics['model_version'] == metrics['dataset_sha256'][:12]


# ----------------------------------------------------------------- dataset

def test_dataset_has_required_columns():
    df = pd.read_csv('dataset/train.csv')
    assert set(CONFIG['features'] + ['label']).issubset(df.columns)
    assert df['label'].nunique() == 2


def test_dataset_row_count_matches_metrics(metrics):
    assert len(pd.read_csv('dataset/train.csv')) == metrics['training_rows']


# ------------------------------------------------------------------- model

def test_model_bundle_predicts():
    bundle = joblib.load('artifacts/model.joblib')
    assert bundle['features'] == CONFIG['features']
    row = pd.DataFrame([{f: 0.5 for f in CONFIG['features']}])
    assert bundle['model'].predict(row).shape == (1,)


# --------------------------------------------------------------- endpoints

def test_health_endpoint(client):
    assert client.get('/health').json() == {'status': 'ok'}


def test_metrics_endpoint(client, metrics):
    response = client.get('/metrics')
    assert response.status_code == 200
    assert REQUIRED_METRIC_KEYS.issubset(response.json())
    assert response.json()['student_id'] == 'FA23-BDS-004'


def test_predict_endpoint(client):
    records = [{f: 0.4 for f in CONFIG['features']},
               {f: -1.2 for f in CONFIG['features']}]
    response = client.post('/predict', json={'records': records})
    assert response.status_code == 200
    body = response.json()
    assert len(body['predictions']) == 2
    assert all(p in (0, 1) for p in body['predictions'])
    assert all(0.0 <= p <= 1.0 for p in body['probabilities'])


def test_predict_handles_missing_feature(client):
    response = client.post('/predict', json={'records': [{}]})
    assert response.status_code == 200


def test_predict_rejects_empty_batch(client):
    assert client.post('/predict', json={'records': []}).status_code == 422
