import boto3
from dependency_injector import containers
from dependency_injector import providers

from chalicelib.services.photo import Photo
from boto3.resources.base import ServiceResource


class Container(containers.DeclarativeContainer):

    s3_resource: providers.Singleton[ServiceResource] = providers.Singleton(
        boto3.resource,
        service_name="s3"
    )

    photo_service: providers.Singleton[Photo] = providers.Singleton(
        Photo,
        s3_resource=s3_resource,
    )


container = Container()
