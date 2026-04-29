SOURCE_CATEGORIES = ('Federal', 'Estadual', 'Municipal')


def get_demo_sources():
    return [
        {
            'id': 1,
            'name': 'Receita Federal do Brasil',
            'category': 'Federal',
            'description': 'Instruções normativas, atos declaratórios e comunicados oficiais.',
            'url': 'https://www.gov.br/receitafederal/pt-br/assuntos/noticias/rss',
            'active': True,
        },
        {
            'id': 2,
            'name': 'CONFAZ',
            'category': 'Estadual',
            'description': 'Convênios ICMS, ajustes SINIEF e despachos publicados pelo conselho.',
            'url': 'https://www.confaz.fazenda.gov.br/legislacao/rss',
            'active': True,
        },
        {
            'id': 3,
            'name': 'Portal SPED',
            'category': 'Federal',
            'description': 'Notícias sobre EFD, ECD, NF-e e demais obrigações acessórias.',
            'url': 'http://sped.rfb.gov.br/rss/noticias',
            'active': True,
        },
        {
            'id': 4,
            'name': 'SEFAZ São Paulo',
            'category': 'Federal',
            'description': 'Portarias, comunicados CAT e atualizações da administração tributária paulista.',
            'url': 'https://portal.fazenda.sp.gov.br/rss/noticias',
            'active': False,
        },
    ]
