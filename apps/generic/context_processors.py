from earthengine.models import EarthEngineAccount


def earthengine_account(request):
    if not request.user.is_authenticated:
        return {}
    return {'earthengine_account': EarthEngineAccount.objects.filter(user=request.user).first()}