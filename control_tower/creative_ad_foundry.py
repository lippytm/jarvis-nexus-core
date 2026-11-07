"""Prompt #11 bounded creative ad-copy blueprints for organic marketing."""
from hashlib import sha256
import json
from control_tower.organic_marketing import BLOCKED_CHANNELS, FREE_CHANNELS, PRODUCTS

CAMPAIGN_UNIVERSES = {
    'join-space-aliens': {
        'name': 'Join the Space Aliens',
        'story_class': 'fictional_brand_theme',
        'master_hook': 'Join the Space Aliens in Intergalactic Corporate Services LLC Business of Life/Business Building.',
        'promise': 'Turn curiosity into building: learn, create, test, document, improve and evolve useful Life/Business systems.',
        'required_label': 'Creative/ANIMA brand universe - Space Aliens are a fictional storytelling layer.',
    },
    'entertainment-of-life': {
        'name': 'Entertainment of Life',
        'story_class': 'fiction_comedy_satire',
        'master_hook': 'Get Your Puns On! Join the Space Aliens for the Entertainment of Life and the Business of Life/Business Building.',
        'promise': 'Use comedy, satire, puns and wordplay to open doors to learning, building, collaboration and constructive discussion.',
        'required_label': 'Comedy/satire/fiction campaign - jokes and wordplay are creative framing, not factual claims or promises to prevent conflict.',
    },
    'evolutionary-evolutions': {
        'name': 'Evolutionary Evolutions',
        'story_class': 'brand_architecture',
        'master_hook': 'Build better systems by building, testing, documenting and improving the AI that helps build them.',
        'promise': 'AI Building AI with AI Jarvis Assistants Swarms Systems Communications Networks under Prompt #11 QA.',
        'required_label': 'Architecture and R&D campaign - planned capabilities remain distinct from tested ones.',
    },
    'build-the-multiverse': {
        'name': 'Build the Multiverse',
        'story_class': 'creative_product_theme',
        'master_hook': 'One idea can become a chapter, book, lesson, video, RPG quest, prototype and campaign universe.',
        'promise': 'Reuse reviewed source material through the Product Creation Machine while preserving evidence and release state.',
        'required_label': 'Creative product-development campaign - generated derivatives are not automatically published products.',
    },
    'life-is-code': {
        'name': 'Life Is Code',
        'story_class': 'educational_brand_theme',
        'master_hook': 'Life Is Code. Are You Coding Yet? Get Your Code On - Coding!',
        'promise': 'Use coding as a practical language for learning, business building, AI and robotics.',
        'required_label': 'Educational campaign - coding metaphors are creative framing.',
    },
}

TONE_MODES = {
    'pun_wordplay': 'Use clean puns, double meanings and playful technical/business wordplay.',
    'satirical_bureaucracy': 'Use absurd intergalactic departments, forms, committees and official-sounding nonsense.',
    'peace_through_wordplay': 'Satirize pointless conflict by redirecting the joke toward building, talking, coding and creating together; do not claim comedy actually prevents war.',
    'cosmic_comedy': 'Use friendly Space Alien misunderstandings about human business, coding and bureaucracy.',
}

SLOGAN_BANK = (
    'Get Your Puns On!',
    'Declare a War on Boring Ideas.',
    'Make Wordplay, Not Pointless Warfare.',
    'Intergalactic Peace Through Superior Wordplay - satire, not foreign policy.',
    'Join the Space Aliens - they came for the puns and stayed for the business plan.',
    'Take Me to Your Ledger.',
    'Less Fighting. More Building. Better Documentation.',
    'Code It Before You Complain About It.',
)

CHANNEL_COPY_SPECS = {k: {'format': v['format']} for k,v in FREE_CHANNELS.items()}

def _canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'))

def _digest(value):
    return sha256(_canonical(value).encode('utf-8')).hexdigest()

def _cta(product):
    if product.destination is None:
        return 'Follow the evolving project while its exact public release destination is being verified.'
    if product.journey_kind == 'funding_customer':
        return 'Review the provider information and decide whether the financing route fits your business needs.'
    if product.journey_kind == 'funding_partner':
        return 'Review the current partner information and decide whether the program fits your goals.'
    if product.journey_kind == 'technical':
        return 'Review the documented build, tests and current limitations.'
    return 'Explore the reviewed resource and choose your next useful step.'

def creative_blueprint(product_id, universe_id, channel, *, tone='pun_wordplay'):
    if product_id not in PRODUCTS: raise ValueError('unknown product')
    if universe_id not in CAMPAIGN_UNIVERSES: raise ValueError('unknown campaign universe')
    if channel in BLOCKED_CHANNELS: raise ValueError('blocked channel for owner')
    if channel not in FREE_CHANNELS: raise ValueError('unknown active channel')
    if tone not in TONE_MODES: raise ValueError('unknown tone')
    product = PRODUCTS[product_id]; universe = CAMPAIGN_UNIVERSES[universe_id]
    body = {
        'schema_version': 1, 'kind': 'jarvis.creative_ad_blueprint', 'state': 'unpublished_draft',
        'product_id': product_id, 'campaign_universe': universe_id, 'channel': channel,
        'channel_format': FREE_CHANNELS[channel]['format'], 'tone': tone,
        'opening_hook': universe['master_hook'], 'audience': product.audience,
        'value_promise': universe['promise'], 'tone_direction': TONE_MODES[tone],
        'story_label': universe['required_label'], 'slogan_candidates': list(SLOGAN_BANK[:4]),
        'product_objective': product.objective, 'cta': _cta(product), 'destination': product.destination,
        'disclosure': product.disclosure, 'prohibited_claims': list(product.prohibited_claims),
        'prompt_11_review': [
            'Separate fiction/comedy/satire from factual business, technical and financial claims.',
            'Do not claim jokes, satire or wordplay actually prevent warfare or guarantee social outcomes.',
            'Verify the product destination and release state before publication.',
            'Do not invent testimonials, metrics, revenue or outcomes.',
            'Preserve affiliate/referral disclosure where applicable.',
            'Do not publish or schedule without authorized account access and human release review.',
        ],
        'external_actions': 0, 'model_calls': 0,
    }
    return {**body, 'blueprint_sha256': _digest(body)}

def creative_campaign_family(product_id, universe_id, *, tone='pun_wordplay'):
    blueprints = [creative_blueprint(product_id, universe_id, channel, tone=tone) for channel in FREE_CHANNELS]
    body = {'schema_version':1,'kind':'jarvis.creative_campaign_family','state':'unpublished_drafts',
            'product_id':product_id,'campaign_universe':universe_id,'tone':tone,
            'active_channel_count':len(FREE_CHANNELS),'blocked_channels':BLOCKED_CHANNELS,
            'blueprints':blueprints,'external_actions':0,'publishing_actions':0,'actual_metrics':None}
    return {**body, 'family_sha256': _digest(body)}

def newsletter_feature(product_id, universe_id, *, tone='cosmic_comedy'):
    bp = creative_blueprint(product_id, universe_id, 'substack', tone=tone)
    return {'schema_version':1,'kind':'jarvis.newsletter_feature_blueprint','state':'unpublished_newsletter_candidate',
            'headline':bp['opening_hook'],'story_label':bp['story_label'],'audience':bp['audience'],
            'section_plan':['Cold-open joke or pun','Useful Life/Business idea','Space Alien satire beat','Real product/system connection','Prompt #11 reality check','Next quest / CTA'],
            'cta':bp['cta'],'destination':bp['destination'],'disclosure':bp['disclosure'],'external_actions':0}
