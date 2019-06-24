from functools import partial

import boto3


class Boto3Client:
    boto3 = boto3

    def __init__(self, **kwargs):
        self._session = Boto3Client.boto3.session.Session(**kwargs)

    def client(self, *args, **kwargs):
        return self._session.client(*args, **kwargs)


def get_boto3_proxy_session(session_config, boto3pkg=boto3):
    def get_config():
        return session_config

    return Boto3SessionProxy(
        session_config["region_name"], boto3_factory(get_config), boto3pkg
    )


def get_boto_session_config(event):
    return {
        "aws_access_key_id": event["requestData"]["credentials"]["accessKeyId"],
        "aws_secret_access_key": event["requestData"]["credentials"]["secretAccessKey"],
        "aws_session_token": event["requestData"]["credentials"]["sessionToken"],
        "region_name": event["region"],
    }


def boto3_factory(provider, boto3pkg=boto3):
    class Boto3Proxy:
        def __init__(self, boto3_type, service_name, region_name):
            self._boto3_type = boto3_type
            for boto3_method in self._get_boto3_methods(service_name, region_name):
                api_wrapper = partial(
                    self._wrapper,
                    service_name=service_name,
                    region_name=region_name,
                    boto3_method=boto3_method,
                )
                setattr(self, boto3_method, api_wrapper)

        def _wrapper(self, service_name, region_name, boto3_method, **kwargs):
            session = boto3pkg.session.Session(**provider())
            boto3_instance = getattr(session, self._boto3_type)(
                service_name, region_name=region_name
            )
            boto3_method = getattr(boto3_instance, boto3_method)
            return boto3_method(**kwargs)

        def _get_boto3_methods(self, service_name, region_name):
            f = getattr(boto3pkg, self._boto3_type)(
                service_name,
                aws_access_key_id="",
                aws_secret_access_key="",
                region_name=region_name,
            )
            return [m for m in dir(f) if not m.startswith("_")]

    return Boto3Proxy


class Boto3SessionProxy:
    def __init__(self, region_name, proxy, boto3pkg=boto3):
        self.proxy = proxy
        self.region_name = region_name
        self.boto3pkg = boto3pkg

    def client(self, service_name, region_name=None):
        if not region_name:
            region_name = self.region_name
        client = self.proxy("client", service_name, region_name)
        return client

    def resource(self, service_name, region_name=None):
        if not region_name:
            region_name = self.region_name
        resource = self.proxy("resource", service_name, region_name)
        return resource
