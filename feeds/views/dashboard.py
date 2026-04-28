from django.shortcuts import render

from feeds.data.dashboard import get_demo_dashboard_metrics


def index(request):
    context = {
        'dashboard_metrics': get_demo_dashboard_metrics(),
    }

    return render(request, 'pages/dashboard/index.html', context)
