# This file represents a model.py built from a complex schema to test that ser/de is
# happening as expected
# pylint: disable=invalid-name, too-many-instance-attributes, protected-access, abstract-method

import sys
from dataclasses import dataclass
from inspect import getmembers, isclass
from typing import (
    AbstractSet,
    Any,
    Mapping,
    MutableMapping,
    Optional,
    Sequence,
    Type,
    TypeVar,
)

from cloudformation_cli_python_lib.interface import (
    BaseModel,
    BaseResourceHandlerRequest,
)
from cloudformation_cli_python_lib.recast import recast_object
from cloudformation_cli_python_lib.utils import deserialize_list

T = TypeVar("T")


@dataclass
class ResourceHandlerRequest(BaseResourceHandlerRequest):
    # pylint: disable=invalid-name
    desiredResourceState: Optional["ResourceModel"]
    previousResourceState: Optional["ResourceModel"]


@dataclass
class ResourceModel(BaseModel):
    ListListAny: Optional[Sequence[Sequence[Any]]]
    ListSetInt: Optional[Sequence[AbstractSet[int]]]
    ListListInt: Optional[Sequence[Sequence[int]]]
    ASet: Optional[AbstractSet[Any]]
    AnotherSet: Optional[AbstractSet[str]]
    AFreeformDict: Optional[MutableMapping[str, Any]]
    APrimitiveTypeDict: Optional[MutableMapping[str, bool]]
    AnInt: Optional[int]
    ABool: Optional[bool]
    NestedList: Optional[Sequence[Sequence["_NestedList"]]]
    AList: Optional[Sequence["_AList"]]
    ADict: Optional["_ADict"]
    AccessToken: Optional[str]
    Name: Optional[str]
    Org: Optional[str]
    Visibility: Optional[str]
    SshUrl: Optional[str]
    HttpsUrl: Optional[str]
    Namespace: Optional[str]
    Id: Optional[int]

    @classmethod
    def _deserialize(
        cls: Type["_ResourceModel"], json_data: Optional[Mapping[str, Any]]
    ) -> Optional["_ResourceModel"]:
        dataclasses = {n: o for n, o in getmembers(sys.modules[__name__]) if isclass(o)}
        recast_object(cls, json_data, dataclasses)
        return cls(
            ListSetInt=json_data.get("ListSetInt"),
            ListListInt=json_data.get("ListListInt"),
            ListListAny=json_data.get("ListListAny"),
            ASet=json_data.get("ASet"),
            AnotherSet=json_data.get("AnotherSet"),
            AFreeformDict=json_data.get("AFreeformDict"),
            APrimitiveTypeDict=json_data.get("APrimitiveTypeDict"),
            AnInt=json_data.get("AnInt"),
            ABool=json_data.get("ABool"),
            NestedList=deserialize_list(json_data.get("NestedList"), NestedList),
            AList=deserialize_list(json_data.get("AList"), AList),
            ADict=ADict._deserialize(json_data.get("ADict")),
            AccessToken=json_data.get("AccessToken"),
            Name=json_data.get("Name"),
            Org=json_data.get("Org"),
            Visibility=json_data.get("Visibility"),
            SshUrl=json_data.get("SshUrl"),
            HttpsUrl=json_data.get("HttpsUrl"),
            Namespace=json_data.get("Namespace"),
            Id=json_data.get("Id"),
        )


# work around possible type aliasing issues when variable has same name as a model
_ResourceModel = ResourceModel


@dataclass
class NestedList(BaseModel):
    NestedListInt: Optional[bool]
    NestedListList: Optional[Sequence[float]]

    @classmethod
    def _deserialize(
        cls: Type["_NestedList"], json_data: Optional[Mapping[str, Any]]
    ) -> Optional["_NestedList"]:
        return cls(
            NestedListInt=json_data.get("NestedListInt"),
            NestedListList=json_data.get("NestedListList"),
        )


# work around possible type aliasing issues when variable has same name as a model
_NestedList = NestedList


@dataclass
class AList(BaseModel):
    DeeperBool: Optional[bool]
    DeeperList: Optional[Sequence[int]]
    DeeperDictInList: Optional["_DeeperDictInList"]

    @classmethod
    def _deserialize(
        cls: Type["_AList"], json_data: Optional[Mapping[str, Any]]
    ) -> Optional["_AList"]:
        return cls(
            DeeperBool=json_data.get("DeeperBool"),
            DeeperList=json_data.get("DeeperList"),
            DeeperDictInList=DeeperDictInList._deserialize(
                json_data.get("DeeperDictInList")
            ),
        )


# work around possible type aliasing issues when variable has same name as a model
_AList = AList


@dataclass
class DeeperDictInList(BaseModel):
    DeepestBool: Optional[bool]
    DeepestList: Optional[Sequence[int]]

    @classmethod
    def _deserialize(
        cls: Type["_DeeperDictInList"], json_data: Optional[Mapping[str, Any]]
    ) -> Optional["_DeeperDictInList"]:
        return cls(
            DeepestBool=json_data.get("DeepestBool"),
            DeepestList=json_data.get("DeepestList"),
        )


# work around possible type aliasing issues when variable has same name as a model
_DeeperDictInList = DeeperDictInList


@dataclass
class ADict(BaseModel):
    DeepBool: Optional[bool]
    DeepList: Optional[Sequence[int]]
    DeepDict: Optional["_DeepDict"]

    @classmethod
    def _deserialize(
        cls: Type["_ADict"], json_data: Optional[Mapping[str, Any]]
    ) -> Optional["_ADict"]:
        return cls(
            DeepBool=json_data.get("DeepBool"),
            DeepList=json_data.get("DeepList"),
            DeepDict=DeepDict._deserialize(json_data.get("DeepDict")),
        )


# work around possible type aliasing issues when variable has same name as a model
_ADict = ADict


@dataclass
class DeepDict(BaseModel):
    DeeperBool: Optional[bool]
    DeeperList: Optional[Sequence[int]]
    DeeperDict: Optional["_DeeperDict"]

    @classmethod
    def _deserialize(
        cls: Type["_DeepDict"], json_data: Optional[Mapping[str, Any]]
    ) -> Optional["_DeepDict"]:
        return cls(
            DeeperBool=json_data.get("DeeperBool"),
            DeeperList=json_data.get("DeeperList"),
            DeeperDict=DeeperDict._deserialize(json_data.get("DeeperDict")),
        )


# work around possible type aliasing issues when variable has same name as a model
_DeepDict = DeepDict


@dataclass
class DeeperDict(BaseModel):
    DeepestBool: Optional[bool]
    DeepestList: Optional[Sequence[int]]

    @classmethod
    def _deserialize(
        cls: Type["_DeeperDict"], json_data: Optional[Mapping[str, Any]]
    ) -> Optional["_DeeperDict"]:
        return cls(
            DeepestBool=json_data.get("DeepestBool"),
            DeepestList=json_data.get("DeepestList"),
        )


# work around possible type aliasing issues when variable has same name as a model
_DeeperDict = DeeperDict


@dataclass
class SimpleResourceModel(BaseModel):
    AnInt: Optional[int]
    ABool: Optional[bool]


_SimpleResourceModel = SimpleResourceModel
