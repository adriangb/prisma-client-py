# WARNING: if you are editing this file you must stage it before running tests
#
# NOTE: we don't care which http method we use here as this file is replaced
# with the method that the user specifies


import warnings


HTTP = None


try:
    import aiohttp
except ImportError:
    pass
else:
    from ._aiohttp_http import HTTP, Response, client


try:
    import requests
except ImportError:
    pass
else:
    from ._requests_http import HTTP, Response, client


if HTTP is None:
    warnings.warn(
        'Falling back to the stdlib http library\n'
        'it is highly recommended to install prisma with either aiohttp or requests\n'
        'e.g. pip install git+https://github.com/RobertCraigie/prisma-client-py#egg=prisma[aiohttp]'
    )
    from ._stdlib_http import HTTP, Response, client
