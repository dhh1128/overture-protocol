import warnings

import pytest
from keri.app import habbing
from keri.core.signing import Salter

warnings.filterwarnings("ignore", category=DeprecationWarning)
warnings.filterwarnings("ignore", category=SyntaxWarning)


def party(name, raw, **kwa):
    """A Habery and one Hab made from fixed salts, so keys and signatures are repeatable."""
    salt = Salter(raw=raw).qb64
    cm = habbing.openHby(name=name, temp=True, salt=salt)
    hby = cm.__enter__()
    hab = hby.makeHab(name=name, **kwa)
    return cm, hby, hab


@pytest.fixture
def parties():
    made = {}
    managers = []
    for name, raw, kwa in [
        ("requester", b"requester-salt-0", {}),
        ("agent", b"agent-salt-00000", {}),
        ("principal", b"principal-salt-0", {}),
        ("stranger", b"stranger-salt-00", {}),
        ("ephemeral", b"ephemeral-salt-0", {"transferable": False}),
    ]:
        cm, hby, hab = party(name, raw, **kwa)
        managers.append(cm)
        made[name] = hab
    yield made
    for cm in reversed(managers):
        cm.__exit__(None, None, None)
