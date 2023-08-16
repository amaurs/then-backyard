import boto3
from dependency_injector.containers import DeclarativeContainer
from dependency_injector.providers import Singleton

from services.photo import Photo
from boto3.resources.base import ServiceResource


class Container(DeclarativeContainer):

    s3_resource: Singleton[ServiceResource] = Singleton(
        boto3.resource,
        service_name="s3"
    )

    photo_service: Singleton[Photo] = Singleton(
        Photo,
        s3_resource=s3_resource,
    )


container = Container()
