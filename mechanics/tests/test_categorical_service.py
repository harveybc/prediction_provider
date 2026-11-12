import numpy as np
import pytest
from fastapi.testclient import TestClient

from prediction_provider_mechanics.categorical_sac import CategoricalSAC
from prediction_provider_mechanics.categorical_service import create_app
from prediction_provider_mechanics.loader import ArtifactVerificationError


def fixture_policy():
    policy = CategoricalSAC.__new__(CategoricalSAC)
    policy.columns = ['first', 'second']
    policy.recipe_identity = 'fixture'
    policy.shape = (2, 2)
    policy.manifest = {'files': {'model.pt': 'fixture-hash'}}
    policy._logits = lambda x: np.array([[0., 1., 2.]], dtype=np.float32)
    return policy


def test_valid_replay_is_not_execution_authority():
    policy = fixture_policy()
    result = policy.replay('fixture', policy.columns, [[1., 2.], [3., 4.]])
    assert result['action'] == 2
    assert result['execution_authorized'] is False
    assert result['evidence_class'] == 'REPLAY_ONLY'


@pytest.mark.parametrize('identity,columns,window', [
    ('wrong', ['first','second'], [[1,2],[3,4]]),
    ('fixture', ['second','first'], [[1,2],[3,4]]),
    ('fixture', ['first','second'], [[1,2]]),
    ('fixture', ['first','second'], [[1,2],[3,float('nan')]]),
    ('fixture', ['first','second'], [[1,2],[3,float('inf')]]),
])
def test_rejects_invalid_tensor_contract(identity, columns, window):
    with pytest.raises(ValueError):
        fixture_policy().replay(identity, columns, window)


def test_manifest_checked_before_native_deserialization(tmp_path):
    (tmp_path / 'MANIFEST.json').write_text('{}')
    with pytest.raises(ArtifactVerificationError):
        CategoricalSAC(tmp_path, '0'*64, tmp_path)


def test_http_refuses_live_claim_and_bad_order():
    policy = fixture_policy()
    client = TestClient(create_app(policy))
    data = dict(recipe_identity='fixture', columns=policy.columns, window=[[1,2],[3,4]])
    assert client.get('/health').json()['live_ready'] is False
    assert client.post('/v1/replay', json=data).json()['action'] == 2
    assert client.post('/v1/replay', json=dict(data, live=True)).status_code == 422
    assert client.post('/v1/replay', json=dict(data, columns=['second','first'])).status_code == 422
    assert client.post('/v1/live', json=data).status_code == 404
