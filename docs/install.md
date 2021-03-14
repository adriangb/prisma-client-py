# Install

As Prisma Client Python supports synchronous and asynchronous use cases, you can specify the http library that the client will use to communicate with the internal [query engine](https://www.prisma.io/docs/concepts/overview/under-the-hood#prisma-engines).

Currently supported third party libraries are:

* [aiohttp](https://github.com/aio-libs/aiohttp)
* [requests](https://github.com/psf/requests)

## Base Install

It is also possible to install prisma without specifying any http library, in this case the standard library `http.client` module will be used, resulting in a synchronous client. However it is not recommended to do this.

```shell script
pip install git+https://github.com/RobertCraigie/prisma-client-py
```

## Install Asynchronous Client

```shell script
pip install git+https://github.com/RobertCraigie/prisma-client-py#egg=prisma[aiohttp]
```

## Install Synchronous Client

```shell script
pip install git+https://github.com/RobertCraigie/prisma-client-py#egg=prisma[requests]
```
