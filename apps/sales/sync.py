from functools import partial

from apps.integrations.models import ExternalSystem
from apps.integrations.oplacrm.provider import get_provider
from apps.integrations.runner import run_sync

from . import services

# Accounts first so opportunities can link to them.
ENTITIES = {
    "accounts": services.sync_accounts,
    "opportunities": services.sync_opportunities,
}


def run_oplacrm_sync(entities=tuple(ENTITIES), user=None):
    """Run the requested OplaCRM sync jobs; returns one SyncRun per entity.

    Raises IntegrationDisabled / IntegrationNotReady before any run is
    recorded if the provider cannot be built.
    """
    provider = get_provider()
    return [
        run_sync(ExternalSystem.OPLACRM, entity, provider.mode, partial(ENTITIES[entity], provider), user=user)
        for entity in ENTITIES
        if entity in entities
    ]
