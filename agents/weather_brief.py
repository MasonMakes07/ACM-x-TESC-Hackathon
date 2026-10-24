"""Evidence-bound Grok interpretation of historical weather comparisons."""
import json
from agents.grok_client import GrokClient
from schemas.weather_comparison import WeatherExplanation

ACTIONS = {
    'cool': ('Move to an air-conditioned place and reduce strenuous outdoor activity.', 'https://www.cdc.gov/heat-health/about/'),
    'water': ('Stay hydrated and check on people who may need help staying cool.', 'https://www.cdc.gov/heat-health/about/'),
    'flood': ('Never walk or drive through floodwater; follow local evacuation instructions.', 'https://www.weather.gov/safety/flood'),
    'wind': ('Seek shelter in a sturdy building and stay away from windows and falling branches.', 'https://www.weather.gov/safety/wind'),
    'cold': ('Wear warm layers, stay dry, and limit exposure to cold.', 'https://www.weather.gov/safety/cold'),
    'alerts': ('Check your local weather service for warnings and instructions.', 'https://worldweather.wmo.int/'),
}


def explain(comparison, client=None):
    evidence = comparison.evidence()
    payload = comparison.model_dump(mode='json')
    for metric in payload['metrics']:
        metric.pop('samples')
    prompt = '''You are EarthWatch's Grok weather analyst. Explain this exact snapshot compared with
1991–2020 ERA5, matching local hour and calendar date +/-7 days. Current readings are model
estimates, not station observations. State whether screening detects an anomaly. Do not invent
weather, official warnings, records, or measurements. A statistical anomaly is not a hazard rating.
Describe possible physical causes as hypotheses, NEVER established causes: this snapshot lacks
pressure, circulation and attribution studies. Say what additional evidence would test each.
Do not assert climate change caused this event. Recommend relevant precaution IDs from the supplied
catalog and explain why each helps. Do not infer flooding from an hourly rain anomaly alone.
Return only JSON matching the schema. evidence_refs must be exact keys in evidence.
If history is unavailable explain that no historical anomaly can be established.'''
    response = (client or GrokClient()).chat([
        {'role': 'system', 'content': prompt},
        {'role': 'user', 'content': json.dumps({'snapshot': payload, 'evidence': evidence,
          'action_catalog': ACTIONS, 'schema': WeatherExplanation.model_json_schema()})},
    ])
    result = WeatherExplanation.model_validate_json(response['content'])
    if any(ref not in evidence for cause in result.possible_causes for ref in cause.evidence_refs):
        raise ValueError('Grok returned an unsupported evidence reference.')
    if any(action.action_id not in ACTIONS for action in result.actions):
        raise ValueError('Grok returned an unsupported precaution.')
    return result
