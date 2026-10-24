"""Dated, source-linked report for the early October 2026 San Diego heat wave.

This retrospective is distinct from NOAA's week-2/3 probability contours.
Evidence summaries are editorial paraphrases, not model-generated observations.
"""
from datetime import date

EVENT_ID = 'san-diego-heat-2026-10'
LATITUDE, LONGITUDE = 32.7157, -117.1611
TITLE = 'San Diego heat wave · early October 2026'
VERIFIED_ON = date(2026, 10, 24)
SOURCES = {
    'nws-local': {
        'title': 'NWS San Diego forecast discussion · 5 October 2026, 02:36 PDT',
        'url': 'https://forecast.weather.gov/product.php?format=ci&glossary=0&highlight=on&issuedby=SGX&product=AFD&site=SGX&version=26',
        'date': '2026-10-05',
        'note': 'The NWS version-number link is a rolling archive. The report cites the dated bulletin reviewed on 24 October, not whatever later replaces that version.',
    },
    'kpbs-impacts': {
        'title': 'KPBS · county emergency-call reporting, updated 9 October 2026',
        'url': 'https://www.kpbs.org/news/health/2026/10/06/county-data-show-record-heat-related-911-calls-where-and-who-is-calling',
        'date': '2026-10-09',
    },
    'sdge': {
        'title': 'SDG&E · extreme heat and power-system update, 4 October 2026',
        'url': 'https://www.sdgetoday.com/news/psps-conditions-have-passed-customers-no-longer-risk-public-safety-power-shutoffs',
        'date': '2026-10-04',
    },
    'scripps': {
        'title': 'UC San Diego / Scripps · El Niño context, 20 October 2026',
        'url': 'https://today.ucsd.edu/story/10-things-to-know-about-this-very-strong-el-nino',
        'date': '2026-10-20',
    },
    'noaa-enso': {
        'title': 'NOAA CPC · October 2026 ENSO Diagnostic Discussion',
        'url': 'https://www.cpc.ncep.noaa.gov/products/analysis_monitoring/enso_advisory/ensodisc.shtml',
        'date': '2026-10-08',
    },
}
FINDINGS = [
    {
        'section': 'What happened', 'status': 'Documented observations', 'refs': ['nws-local'],
        'text': 'NWS reported airport highs of 105°F on 3 October and 100°F on 4 October, both daily records. The 4 October low was 74°F. These are airport observations, not readings for every San Diego neighborhood. The 5 October bulletin continued major to locally extreme HeatRisk for coastal areas and western valleys through Thursday.',
    },
    {
        'section': 'Damage and disruption', 'status': 'Reported impacts', 'refs': ['kpbs-impacts'],
        'text': 'KPBS reported 925 metro-zone dispatch calls on 3 October, a 42% increase, and more than 400 ambulance hospital transports that Saturday. These were all-cause totals during the heat wave; the report does not identify how many were caused by heat. Extra ambulances and longer cooling-center hours were added. Separately, the county had logged 378 heat-related calls by 17 September: a year-to-date figure, not an October-event total.',
    },
    {
        'section': 'Damage and disruption', 'status': 'Infrastructure pressure; losses unquantified', 'refs': ['sdge'],
        'text': 'SDG&E described sustained heat, increased cooling demand, and possible localized outages. It also tracked separate dry offshore-wind and wildfire-weather conditions. Its 4 October update ended the potential shutoff alert. The cited update does not quantify heat-caused outages, property losses, or economic damage; high temperatures alone do not trigger preventive fire-weather shutoffs.',
    },
    {
        'section': 'Why it happened', 'status': 'Local weather mechanism', 'refs': ['sdge', 'nws-local'],
        'text': 'Dry offshore flow helped hot conditions reach the coastal region; weaker ocean cooling allowed heat to persist. SDG&E documented offshore winds during the heat wave, and NWS described the eventual return of a cooling sea breeze. These local circulation changes help explain the event’s timing and coastal intensity.',
    },
    {
        'section': 'El Niño connection', 'status': 'Climate influence; event contribution not quantified', 'refs': ['scripps', 'noaa-enso'],
        'text': 'El Niño was active: NOAA’s October discussion reported a strengthening event. Scripps explains that El Niño adds ocean and atmospheric warmth and can amplify regional heat-wave activity on top of long-term warming. That provides a plausible background influence here, but these sources do not isolate El Niño’s contribution to this specific San Diego heat wave. The report therefore does not claim that El Niño alone caused it or assign a percentage of the heat to El Niño.',
    },
    {
        'section': 'What remains unknown', 'status': 'Evidence gap', 'refs': ['kpbs-impacts', 'sdge'],
        'text': 'The reviewed sources do not establish an event-specific death toll, total heat-attributable hospitalizations, property-damage bill, or financial loss. Those require dated public-health, incident, utility, and loss records. No missing total is treated as zero.',
    },
]


def evidence_payload():
    return dict(event_id=EVENT_ID, title=TITLE, verified_on=VERIFIED_ON.isoformat(),
                coordinates=[LATITUDE, LONGITUDE], sources=SOURCES, findings=FINDINGS)


def report_markdown():
    lines = [f'# {TITLE}', '', f'Retrospective report · sources checked {VERIFIED_ON:%d %B %Y}', '',
             'Report window: early October 2026. This report is separate from the live NOAA outlook.', '']
    previous = None
    for finding in FINDINGS:
        if finding['section'] != previous:
            lines += [f"## {finding['section']}", '']
            previous = finding['section']
        lines += [f"**{finding['status']}**", '', finding['text'], '',
                  'Sources: ' + ', '.join(f"[{SOURCES[ref]['title']}]({SOURCES[ref]['url']})" for ref in finding['refs']) + '.', '']
    lines += ['## Source notes', '']
    for source in SOURCES.values():
        if source.get('note'):
            lines += [source['note'], '']
    return '\n'.join(lines)
