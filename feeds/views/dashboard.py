from django.shortcuts import render

from feeds.data.dashboard import get_dashboard_context


def index(request):
    context = get_dashboard_context()
    return render(request, 'pages/dashboard/index.html', context)
