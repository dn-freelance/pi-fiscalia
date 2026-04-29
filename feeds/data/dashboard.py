def get_demo_dashboard_metrics():
    return [
        {
            'label': 'Total de Informativos',
            'value': 10,
            'icon': 'bar-chart-2',
            'variant': 'blue',
        },
        {
            'label': 'Não Lidos',
            'value': 7,
            'icon': 'eye',
            'variant': 'orange',
        },
        {
            'label': 'Alta Relevância',
            'value': 6,
            'icon': 'alert-triangle',
            'variant': 'red',
        },
        {
            'label': 'Vigentes este Mês',
            'value': 2,
            'icon': 'calendar',
            'variant': 'green',
        },
    ]
